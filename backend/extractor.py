"""
extractor.py — Layout-Aware PDF Extraction Engine

Extracts text elements, images, and semantic chunks from a PDF
using PyMuPDF. All coordinates are preserved exactly as stored
in the source document.
"""

from __future__ import annotations

import fitz  # PyMuPDF
from dataclasses import dataclass, field
from typing import Generator, List, Tuple
from PIL import Image
import pytesseract
import io

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

BBox = Tuple[float, float, float, float]  # (x0, y0, x1, y1)


@dataclass(frozen=True)
class TextElement:
    """A single styled text span from the PDF."""
    text: str
    bbox: BBox
    font_name: str
    font_size: float
    color: int
    page: int


@dataclass(frozen=True)
class ImageElement:
    """A raster image extracted from the PDF."""
    image_bytes: bytes
    bbox: BBox
    page: int


@dataclass
class SemanticChunk:
    """A group of vertically adjacent TextElements forming a logical paragraph."""
    elements: List[TextElement] = field(default_factory=list)
    page: int = 0

    @property
    def text(self) -> str:
        return " ".join(e.text for e in self.elements)

    @property
    def bbox(self) -> BBox:
        x0 = min(e.bbox[0] for e in self.elements)
        y0 = min(e.bbox[1] for e in self.elements)
        x1 = max(e.bbox[2] for e in self.elements)
        y1 = max(e.bbox[3] for e in self.elements)
        return (x0, y0, x1, y1)

    @property
    def font_name(self) -> str:
        return self.elements[0].font_name if self.elements else ""

    @property
    def font_size(self) -> float:
        return self.elements[0].font_size if self.elements else 12.0

    @property
    def color(self) -> int:
        return self.elements[0].color if self.elements else 0


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class ScannedPageError(Exception):
    """Raised when a page contains no machine-readable text layer."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

Y_CLUSTER_THRESHOLD = 5.0  # points; tune to taste


def _spans_from_page(page: fitz.Page) -> Generator[dict, None, None]:
    """Yield every span dict from the page's text blocks."""
    blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
    for block in blocks:
        if block.get("type") != 0:  # skip image blocks
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                if span["text"].strip():
                    yield span


def _span_to_element(span: dict, page_num: int) -> TextElement:
    """Convert a raw PyMuPDF span dict to a TextElement."""
    # Extract color - handle different PyMuPDF versions
    color = span.get("color", 0)
    if isinstance(color, (list, tuple)):
        # RGB array - convert to int
        if len(color) >= 3:
            color = (int(color[0] * 255) << 16) | (int(color[1] * 255) << 8) | int(color[2] * 255)
        else:
            color = 0
    elif not isinstance(color, int):
        color = 0
    
    return TextElement(
        text=span["text"].strip(),
        bbox=tuple(span["bbox"]),     # type: ignore[arg-type]
        font_name=span.get("font", "Helvetica"),
        font_size=round(span.get("size", 12), 2),
        color=color,
        page=page_num,
    )


def _cluster_elements(elements: List[TextElement]) -> List[SemanticChunk]:
    """
    Group elements into chunks by Y-axis proximity.

    Time:  O(n log n) — sort then single pass
    Space: O(n)
    """
    if not elements:
        return []

    sorted_els = sorted(elements, key=lambda e: (e.bbox[1], e.bbox[0]))
    chunks: List[SemanticChunk] = []
    current = SemanticChunk(elements=[sorted_els[0]], page=sorted_els[0].page)

    for el in sorted_els[1:]:
        prev_y1 = current.elements[-1].bbox[3]
        gap = el.bbox[1] - prev_y1
        if gap <= Y_CLUSTER_THRESHOLD:
            current.elements.append(el)
        else:
            chunks.append(current)
            current = SemanticChunk(elements=[el], page=el.page)

    chunks.append(current)
    return chunks


def _images_from_page(page: fitz.Page, page_num: int) -> List[ImageElement]:
    """Extract all raster images and their bounding boxes from a page."""
    images: List[ImageElement] = []
    for img_info in page.get_images(full=True):
        xref = img_info[0]
        rect = page.get_image_rects(xref)
        if not rect:
            continue
        bbox = tuple(rect[0])  # first occurrence rect   # type: ignore[arg-type]
        raw = page.parent.extract_image(xref)
        if raw:
            images.append(ImageElement(
                image_bytes=raw["image"],
                bbox=bbox,
                page=page_num,
            ))
    return images


def _has_text(page: fitz.Page) -> bool:
    """Return True iff the page has any machine-readable text."""
    return bool(page.get_text("text").strip())


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract(pdf_path: str) -> dict:
    """
    Extract all content from *pdf_path*.

    Returns:
        {
            "chunks":  List[SemanticChunk],
            "images":  List[ImageElement],
            "page_sizes": List[(width, height)],
        }

    Raises:
        ScannedPageError: if the entire document has no text layer.
    """
    doc = fitz.open(pdf_path)
    all_elements: List[TextElement] = []
    all_images: List[ImageElement] = []
    page_sizes: List[Tuple[float, float]] = []

    for page_num, page in enumerate(doc):
        page_sizes.append((page.rect.width, page.rect.height))

        has_native_text = False
        for span in _spans_from_page(page):
            has_native_text = True
            all_elements.append(_span_to_element(span, page_num))

        # If PyMuPDF found zero text spans on this page, check raw text as fallback
        # Some PDFs have searchable text that doesn't come through as spans
        if not has_native_text and _has_text(page):
            # Try to get text with different flags - sometimes 'blocks' works better than 'dict'
            text_blocks = page.get_text("blocks")
            if text_blocks.strip():
                # Create a single chunk for the page text
                # This preserves the text without exact bbox info
                all_elements.append(TextElement(
                    text=text_blocks.strip(),
                    bbox=(0, 0, page.rect.width, page.rect.height),
                    font_name="PDF-Text-Fallback",
                    font_size=12.0,
                    color=0,
                    page=page_num,
                ))
                has_native_text = True

        # If still no text found, run Tesseract OCR as last resort.
        if not has_native_text:
            pix = page.get_pixmap(dpi=150)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            
            # Use tesseract to extract data dictionary including bounding boxes
            ocr_data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
            
            for i in range(len(ocr_data['text'])):
                text = ocr_data['text'][i].strip()
                if not text:
                    continue
                    
                # Scale coordinates from Pixmap DPI (150) back to PDF points (72 DPI)
                scale = 72 / 150
                x0 = ocr_data['left'][i] * scale
                y0 = ocr_data['top'][i] * scale
                w = ocr_data['width'][i] * scale
                h = ocr_data['height'][i] * scale
                x1, y1 = x0 + w, y0 + h
                
                all_elements.append(TextElement(
                    text=text,
                    bbox=(x0, y0, x1, y1),
                    font_name="OCR-Fallback",
                    font_size=12.0,
                    color=0x000000,  # Black
                    page=page_num
                ))

        all_images.extend(_images_from_page(page, page_num))

    doc.close()

    if not all_elements:
        raise ScannedPageError(
            "Document has no text layer. "
            "OCR Required: Please upload a searchable PDF."
        )

    chunks = _cluster_elements(all_elements)
    return {
        "chunks": chunks,
        "images": all_images,
        "page_sizes": page_sizes,
    }


# ---------------------------------------------------------------------------
# Page Preview API
# ---------------------------------------------------------------------------

def extract_page_info(pdf_path: str) -> List[dict]:
    """
    Extract page thumbnails and basic info for preview.
    
    Returns a list of page info dicts with:
        - page_num: int
        - thumbnail: base64 encoded PNG image
        - has_text: bool
        - width: float
        - height: float
    """
    import base64
    
    doc = fitz.open(pdf_path)
    pages_info = []
    
    for page_num, page in enumerate(doc):
        # Check if page has text
        has_text = _has_text(page)
        
        # Generate thumbnail (lower DPI for smaller size)
        pix = page.get_pixmap(dpi=72)
        img_data = pix.tobytes("png")
        thumbnail_b64 = base64.b64encode(img_data).decode('utf-8')
        
        pages_info.append({
            "page_num": page_num,
            "thumbnail": f"data:image/png;base64,{thumbnail_b64}",
            "has_text": has_text,
            "width": page.rect.width,
            "height": page.rect.height,
        })
    
    doc.close()
    return pages_info
