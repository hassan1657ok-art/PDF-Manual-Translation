"""
main.py — FastAPI Application

Endpoints:
  POST /upload          → accepts PDF + target_lang, creates job, returns job_id
  WS   /ws/{job_id}    → streams pipeline status messages in real time
  GET  /download/{job_id} → serves the completed translated PDF
"""

from __future__ import annotations

import asyncio
import os
import uuid
import logging
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv
from fastapi import (
    BackgroundTasks,
    FastAPI,
    File,
    Form,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from extractor import ScannedPageError, extract, extract_page_info
from orchestrator import translate_all_chunks
from reconstructor import reconstruct,reconstruct_selected_pages

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

load_dotenv()
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = FastAPI(title="DocuPreserve AI", version="1.0.0")

# FRONTEND_URL can be set to the deployed Vercel/Netlify URL in production.
_FRONTEND_URL = os.getenv("FRONTEND_URL", "")
_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    *( [_FRONTEND_URL] if _FRONTEND_URL else [] ),
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    """Railway / Docker health-check probe."""
    return {"status": "ok"}

# ---------------------------------------------------------------------------
# Storage paths
# ---------------------------------------------------------------------------

UPLOAD_DIR = Path("uploads")
OUTPUT_DIR = Path("outputs")
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# In-memory job registry
# job_queues : job_id → asyncio.Queue of status strings
# job_status : job_id → "running" | "done" | "error"
# ---------------------------------------------------------------------------

job_queues: Dict[str, asyncio.Queue] = {}
job_status: Dict[str, str] = {}

# Sentinel value pushed after the pipeline finishes.
_DONE_SENTINEL = "__DONE__"

# ---------------------------------------------------------------------------
# Pipeline runner (background task)
# ---------------------------------------------------------------------------

async def _run_pipeline(
    job_id: str,
    pdf_path: Path,
    target_lang: str,
    selected_pages: Optional[List[int]] = None,
) -> None:
    """Full pipeline: extract → translate → reconstruct → signal done."""
    queue = job_queues[job_id]

    async def emit(msg: str) -> None:
        await queue.put(msg)
        log.info("[%s] %s", job_id, msg)

    try:
        # ── Stage 1: Extraction ──────────────────────────────────────────
        await emit("Extracting Layout...")
        result = extract(str(pdf_path))

        await emit("Chunking Text...")
        chunks = result["chunks"]
        images = result["images"]
        page_sizes = result["page_sizes"]

        # ── Stage 2: Translation ─────────────────────────────────────────
        loop = asyncio.get_running_loop()

        def sync_status(msg: str) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, msg)

        translated = await translate_all_chunks(
            chunks, target_lang, on_status=sync_status
        )

        # ── Stage 3: Validation tag ──────────────────────────────────────
        await emit("Judge Validating...")

        # ── Stage 4: Reconstruction ──────────────────────────────────────
        await emit("Reconstructing PDF...")

        def recon_status(msg: str) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, msg)

        def run_reconstruct():
            # Set up an event loop for this thread to avoid
            # "no current event loop" errors from libraries that need it
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                # No event loop in this thread, create one
                loop_thread = asyncio.new_event_loop()
                asyncio.set_event_loop(loop_thread)
            
            # Use selected pages if provided, otherwise process all pages
            if selected_pages is not None and len(selected_pages) > 0:
                return reconstruct_selected_pages(
                    chunks, translated, images, page_sizes, selected_pages, recon_status
                )
            else:
                return reconstruct(chunks, translated, images, page_sizes, recon_status)

        pdf_bytes = await loop.run_in_executor(None, run_reconstruct)

        out_path = OUTPUT_DIR / f"{job_id}.pdf"
        out_path.write_bytes(pdf_bytes)

        await emit("Done")
        job_status[job_id] = "done"

    except ScannedPageError as exc:
        await emit(f"ERROR: {exc}")
        job_status[job_id] = "error"

    except Exception as exc:
        log.exception("Pipeline failed for job %s", job_id)
        await emit(f"ERROR: {exc}")
        job_status[job_id] = "error"

    finally:
        await queue.put(_DONE_SENTINEL)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/preview")
async def preview(file: UploadFile = File(...)) -> dict:
    """Extract page thumbnails and info for preview before processing."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")
    
    # Save temporarily
    temp_id = str(uuid.uuid4())
    temp_path = UPLOAD_DIR / f"preview_{temp_id}.pdf"
    temp_path.write_bytes(await file.read())
    
    try:
        pages_info = extract_page_info(str(temp_path))
        return {"pages": pages_info}
    finally:
        # Clean up temp file
        if temp_path.exists():
            temp_path.unlink()


@app.post("/upload")
async def upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    target_lang: str = Form(...),
    selected_pages: Optional[str] = Form(None),
) -> dict:
    """Accept a PDF, queue it for processing, return job_id.
    
    Args:
        selected_pages: Optional JSON string of page numbers to process (e.g., "[0,1,2]")
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    job_id = str(uuid.uuid4())
    pdf_path = UPLOAD_DIR / f"{job_id}.pdf"
    pdf_path.write_bytes(await file.read())
    
    # Parse selected pages if provided
    pages_list: Optional[List[int]] = None
    if selected_pages:
        import json
        try:
            pages_list = json.loads(selected_pages)
            if not isinstance(pages_list, list):
                raise HTTPException(status_code=400, detail="selected_pages must be a JSON array")
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="selected_pages must be valid JSON")

    job_queues[job_id] = asyncio.Queue()
    job_status[job_id] = "running"

    background_tasks.add_task(_run_pipeline, job_id, pdf_path, target_lang, pages_list)
    return {"job_id": job_id}


@app.websocket("/ws/{job_id}")
async def ws_stream(websocket: WebSocket, job_id: str) -> None:
    """Stream pipeline status messages to the connected client."""
    await websocket.accept()

    if job_id not in job_queues:
        await websocket.send_text("ERROR: Unknown job_id")
        await websocket.close()
        return

    queue = job_queues[job_id]
    try:
        while True:
            msg: str = await queue.get()
            if msg == _DONE_SENTINEL:
                break
            await websocket.send_text(msg)
    except WebSocketDisconnect:
        log.info("Client disconnected from job %s", job_id)
    finally:
        await websocket.close()


@app.get("/download/{job_id}")
async def download(job_id: str) -> FileResponse:
    """Serve the completed translated PDF."""
    if job_status.get(job_id) != "done":
        raise HTTPException(status_code=404, detail="Output not ready or job not found.")

    out_path = OUTPUT_DIR / f"{job_id}.pdf"
    if not out_path.exists():
        raise HTTPException(status_code=404, detail="Output file missing.")

    return FileResponse(
        path=str(out_path),
        media_type="application/pdf",
        filename="translated.pdf",
    )
