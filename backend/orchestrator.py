"""
orchestrator.py — LangGraph LLM Translation & Validation Workflow

Nodes:
  1. translator  — calls GPT-4o to translate text → JSON
  2. judge       — evaluates output for accuracy / hallucination → JSON
  
Edge logic:
  judge passed=True  → END
  judge passed=False, retries < MAX_RETRIES → translator (with feedback)
  judge passed=False, retries == MAX_RETRIES → END (best-effort result)
"""

from __future__ import annotations

import json
import asyncio
import hashlib
import os
from typing import Callable, List, Optional, TypedDict

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from extractor import SemanticChunk

# ---------------------------------------------------------------------------
# Caching Configuration
# ---------------------------------------------------------------------------

CACHE_FILE = "outputs/translation_cache.json"

def _load_cache() -> dict:
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def _save_cache(cache: dict):
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

_TRANSLATION_CACHE = _load_cache()

def _get_cache_key(text: str, target_lang: str) -> str:
    return hashlib.md5(f"{target_lang}:{text}".encode("utf-8")).hexdigest()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_RETRIES = 3
LLM_TIMEOUT = 30  # seconds


# ---------------------------------------------------------------------------
# LangGraph state schema
# ---------------------------------------------------------------------------

class TranslationState(TypedDict):
    source_text: str
    target_lang: str
    translated_text: str
    feedback: str
    passed: bool
    retries: int


# ---------------------------------------------------------------------------
# LLM factory  (single instance per call avoids repeated network init)
# ---------------------------------------------------------------------------

def _make_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model="gpt-4o",
        temperature=0.1,
        timeout=LLM_TIMEOUT,
        response_format={"type": "json_object"},
    )


# ---------------------------------------------------------------------------
# Node helpers
# ---------------------------------------------------------------------------

TRANSLATOR_SYSTEM = (
    "You are an expert technical translator. "
    "Return ONLY valid JSON: {\"translated_text\": \"...\"}"
)

JUDGE_SYSTEM = (
    "You are a translation quality evaluator. "
    "Return ONLY valid JSON: {\"passed\": true/false, \"feedback\": \"...\"}"
)


def _build_translator_prompt(state: TranslationState) -> str:
    parts = [
        f"Target language: {state['target_lang']}",
        f"Source text: {state['source_text']}",
    ]
    if state["feedback"]:
        parts.append(f"Previous translation feedback: {state['feedback']}")
    return "\n".join(parts)


def _build_judge_prompt(state: TranslationState) -> str:
    return (
        f"Source: {state['source_text']}\n"
        f"Translation: {state['translated_text']}\n"
        "Evaluate for hallucination, omission, and technical accuracy."
    )


def _parse_json(raw: str, fallback: dict) -> dict:
    """Safely parse JSON from an LLM response."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return fallback


# ---------------------------------------------------------------------------
# Graph nodes
# ---------------------------------------------------------------------------

async def translator_node(state: TranslationState) -> TranslationState:
    llm = _make_llm()
    prompt = _build_translator_prompt(state)
    messages = [
        SystemMessage(content=TRANSLATOR_SYSTEM),
        HumanMessage(content=prompt),
    ]
    response = await llm.ainvoke(messages)
    raw = response.content
    result = _parse_json(raw, {"translated_text": state["source_text"]})
    return {
        **state,
        "translated_text": result.get("translated_text", state["source_text"]),
        "retries": state["retries"] + 1,
    }


async def judge_node(state: TranslationState) -> TranslationState:
    llm = _make_llm()
    prompt = _build_judge_prompt(state)
    messages = [
        SystemMessage(content=JUDGE_SYSTEM),
        HumanMessage(content=prompt),
    ]
    response = await llm.ainvoke(messages)
    raw = response.content
    result = _parse_json(raw, {"passed": True, "feedback": ""})
    return {
        **state,
        "passed": result.get("passed", True),
        "feedback": result.get("feedback", ""),
    }


# ---------------------------------------------------------------------------
# Edge condition
# ---------------------------------------------------------------------------

def _should_retry(state: TranslationState) -> str:
    if not state["passed"] and state["retries"] < MAX_RETRIES:
        return "translator"
    return END


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def _build_graph() -> StateGraph:
    graph = StateGraph(TranslationState)
    graph.add_node("translator", translator_node)
    graph.add_node("judge", judge_node)
    graph.set_entry_point("translator")
    graph.add_edge("translator", "judge")
    graph.add_conditional_edges("judge", _should_retry)
    return graph.compile()


_GRAPH = _build_graph()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

StatusCallback = Callable[[str], None]


async def translate_chunk(
    chunk: SemanticChunk,
    target_lang: str,
    on_status: Optional[StatusCallback] = None,
) -> str:
    """
    Translate a single SemanticChunk, running the LangGraph pipeline.

    Returns the best translated text (or original on unrecoverable error).
    """
    cache_key = _get_cache_key(chunk.text, target_lang)
    if cache_key in _TRANSLATION_CACHE:
        if on_status:
            on_status(f"[INFO] Using cached translation for: '{chunk.text[:40]}...'")
        return _TRANSLATION_CACHE[cache_key]

    initial: TranslationState = {
        "source_text": chunk.text,
        "target_lang": target_lang,
        "translated_text": "",
        "feedback": "",
        "passed": False,
        "retries": 0,
    }

    if on_status:
        on_status(f"[INFO] Translating chunk: '{chunk.text[:40]}...'")

    try:
        final: TranslationState = await _GRAPH.ainvoke(initial)
        
        translated = final["translated_text"] or chunk.text
        
        # Cache successful translations
        if translated and translated != chunk.text:
            _TRANSLATION_CACHE[cache_key] = translated
            _save_cache(_TRANSLATION_CACHE)

        if on_status:
            status = "passed" if final["passed"] else "best-effort"
            on_status(f"[INFO] Judge verdict: {status}")

        return translated
        
    except Exception as e:
        if on_status:
            on_status(f"[ERROR] LLM API Error: {str(e)[:100]}. Falling back to original text.")
        return chunk.text


async def translate_all_chunks(
    chunks: List[SemanticChunk],
    target_lang: str,
    on_status: Optional[StatusCallback] = None,
) -> List[str]:
    """
    Translate every chunk sequentially to stay within API rate limits.

    Returns a list of translated strings, one per input chunk.
    """
    results: List[str] = []
    total = len(chunks)
    for idx, chunk in enumerate(chunks, start=1):
        if on_status:
            on_status(f"[INFO] Translating chunk {idx}/{total} (page {chunk.page + 1})")
        translated = await translate_chunk(chunk, target_lang, on_status)
        results.append(translated)
    return results
