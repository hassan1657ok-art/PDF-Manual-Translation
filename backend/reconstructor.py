"""
reconstructor.py — Layout-Preserving PDF Reconstructor

Takes translated text chunks + original image elements and rebuilds
the PDF using ReportLab. Dynamic font scaling ensures translated
text never overflows its original bounding box.
"""

from __future__ import annotations

import io
import logging
import re
from typing import Callable, Dict, List, Optional, Tuple

from reportlab.lib.colors import Color, black
from reportlab.lib.units import pt
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as rl_canvas

from extractor import ImageElement, SemanticChunk

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Font configuration
# ---------------------------------------------------------------------------

# Standard PDF fonts that are always available
STANDARD_FONTS = {
    "Courier", "Courier-Bold", "Courier-Oblique", "Courier-BoldOblique",
    "Helvetica", "Helvetica-Bold", "Helvetica-Oblique", "Helvetica-BoldOblique",
    "Times-Roman", "Times-Bold", "Times-Italic", "Times-BoldItalic",
    "Symbol", "ZapfDingbats"
}

# Font mapping for common font name variations
FONT_MAPPING = {
    # Arial family
    "Arial": "Helvetica",
    "ArialMT": "Helvetica",
    "Arial-Bold": "Helvetica-Bold",
    "Arial-BoldMT": "Helvetica-Bold",
    "Arial-Italic": "Helvetica-Oblique",
    "Arial-BoldItalic": "Helvetica-BoldOblique",
    # Times family
    "TimesNewRoman": "Times-Roman",
    "TimesNewRomanPS": "Times-Roman",
    "TimesNewRomanPSMT": "Times-Roman",
    "TimesNewRoman-Bold": "Times-Bold",
    "TimesNewRomanPS-Bold": "Times-Bold",
    "TimesNewRomanPS-BoldMT": "Times-Bold",
    "TimesNewRoman-Italic": "Times-Italic",
    "TimesNewRomanPS-Italic": "Times-Italic",
    "TimesNewRomanPS-ItalicMT": "Times-Italic",
    "TimesNewRoman-BoldItalic": "Times-BoldItalic",
    # Courier family
    "CourierNew": "Courier",
    "CourierNewPS": "Courier",
    "CourierNewPSMT": "Courier",
    "CourierNew-Bold": "Courier-Bold",
    "CourierNewPS-Bold": "Courier-Bold",
    "CourierNewPS-BoldMT": "Courier-Bold",
    "CourierNew-Italic": "Courier-Oblique",
    "CourierNewPS-Italic": "Courier-Oblique",
    "CourierNewPS-ItalicMT": "Courier-Oblique",
    "CourierNew-BoldItalic": "Courier-BoldOblique",
    # Common sans-serif
    "Verdana": "Helvetica",
    "Verdana-Bold": "Helvetica-Bold",
    "Tahoma": "Helvetica",
    "Geneva": "Helvetica",
    "Calibri": "Helvetica",
    "Calibri-Bold": "Helvetica-Bold",
    # Common serif
    "Georgia": "Times-Roman",
    "Garamond": "Times-Roman",
    "Cambria": "Times-Roman",
    "Cambria-Bold": "Times-Bold",
    # Common monospace
    "Consolas": "Courier",
    "Consolas-Bold": "Courier-Bold",
    "Lucida Console": "Courier",
    "Lucida Console-Bold": "Courier-Bold",
}

# Fallback font name used when the original font is unavailable.
FALLBACK_FONT = "Helvetica"

# Minimum font size after scaling — prevents text from becoming invisible.
MIN_FONT_SIZE = 6.0

# Font size decrement step per overflow iteration.
FONT_STEP = 0.25

# Font mapping for common font name variations
FONT_MAPPING = {
    # Arial family
    "Arial": "Helvetica",
    "ArialMT": "Helvetica",
    "Arial-Bold": "Helvetica-Bold",
    "Arial-BoldMT": "Helvetica-Bold",
    "Arial-Italic": "Helvetica-Oblique",
    "Arial-BoldItalic": "Helvetica-BoldOblique",
    # Times family
    "TimesNewRoman": "Times-Roman",
    "TimesNewRomanPS": "Times-Roman",
    "TimesNewRomanPSMT": "Times-Roman",
    "TimesNewRoman-Bold": "Times-Bold",
    "TimesNewRomanPS-Bold": "Times-Bold",
    "TimesNewRomanPS-BoldMT": "Times-Bold",
    "TimesNewRoman-Italic": "Times-Italic",
    "TimesNewRomanPS-Italic": "Times-Italic",
    "TimesNewRomanPS-ItalicMT": "Times-Italic",
    "TimesNewRoman-BoldItalic": "Times-BoldItalic",
    # Courier family
    "CourierNew": "Courier",
    "CourierNewPS": "Courier",
    "CourierNewPSMT": "Courier",
    "CourierNew-Bold": "Courier-Bold",
    "CourierNewPS-Bold": "Courier-Bold",
    "CourierNewPS-BoldMT": "Courier-Bold",
    "CourierNew-Italic": "Courier-Oblique",
    "CourierNewPS-Italic": "Courier-Oblique",
    "CourierNewPS-ItalicMT": "Courier-Oblique",
    "CourierNew-BoldItalic": "Courier-BoldOblique",
    # Common sans-serif
    "Verdana": "Helvetica",
    "Verdana-Bold": "Helvetica-Bold",
    "Tahoma": "Helvetica",
    "Geneva": "Helvetica",
    "Calibri": "Helvetica",
    "Calibri-Bold": "Helvetica-Bold",
    # Common serif
    "Georgia": "Times-Roman",
    "Garamond": "Times-Roman",
    "Cambria": "Times-Roman",
    "Cambria-Bold": "Times-Bold",
    # Common monospace
    "Consolas": "Courier",
    "Consolas-Bold": "Courier-Bold",
    "Lucida Console": "Courier",
    "Lucida Console-Bold": "Courier-Bold",
}

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

BBox = Tuple[float, float, float, float]
StatusCallback = Callable[[str], None]


# ---------------------------------------------------------------------------
# Font utilities
# ---------------------------------------------------------------------------

def _normalize_font_name(font_name: str) -> str:
    """Normalize font name by removing subset prefixes and variants."""
    if not font_name:
        return FALLBACK_FONT
    
    # Remove subset prefixes like "AAAAAA+FontName"
    if "+" in font_name:
        font_name = font_name.split("+", 1)[1]
    
    # Remove common suffixes
    font_name = re.sub(r",(Bold|Italic|Regular|Medium|Light|SemiBold)$", "", font_name)
    font_name = re.sub(r"-(Regular|Normal)$", "", font_name)
    
    return font_name.strip()


def _resolve_font(font_name: str) -> str:
    """
    Return the best matching available font.
    
    1. Check if it's a standard font
    2. Check font mapping
    3. Try to infer from name patterns
    4. Return fallback
    """
    if not font_name:
        return FALLBACK_FONT
    
    # Normalize the font name
    normalized = _normalize_font_name(font_name)
    
    # Direct match with standard fonts
    if normalized in STANDARD_FONTS:
        return normalized
    
    # Check mapping
    if normalized in FONT_MAPPING:
        return FONT_MAPPING[normalized]
    
    # Try pattern matching for bold/italic variants
    is_bold = "bold" in normalized.lower() or "heavy" in normalized.lower()
    is_italic = "italic" in normalized.lower() or "oblique" in normalized.lower()
    
    if is_bold and is_italic:
        return "Helvetica-BoldOblique"
    elif is_bold:
        return "Helvetica-Bold"
    elif is_italic:
        return "Helvetica-Oblique"
    
    # Check for serif/sans-serif hints
    if any(s in normalized.lower() for s in ["times", "roman", "serif", "georgia", "garamond"]):
        return "Times-Roman"
    elif any(m in normalized.lower() for m in ["courier", "mono", "console", "typewriter"]):
        return "Courier"
    
    return FALLBACK_FONT


def _string_width(text: str, font: str, size: float) -> float:
    """Return rendered string width in points (ReportLab units)."""
    try:
        return pdfmetrics.stringWidth(text, font, size)
    except Exception:
        try:
            return pdfmetrics.stringWidth(text, FALLBACK_FONT, size)
        except Exception:
            # Last resort: estimate based on character count
            return len(text) * size * 0.6


def _scale_font_to_fit(
    text: str,
    font: str,
    start_size: float,
    max_width: float,
    max_iterations: int = 50,
) -> float:
    """
    Decrement font size until the text fits within *max_width*.
    Uses binary search for faster convergence.
    """
    if max_width <= 0:
        return MIN_FONT_SIZE
    
    # Quick check: if it fits at start size, return that
    if _string_width(text, font, start_size) <= max_width:
        return start_size
    
    # Binary search for optimal size
    low, high = MIN_FONT_SIZE, start_size
    best_size = MIN_FONT_SIZE
    
    for _ in range(max_iterations):
        mid = (low + high) / 2
        width = _string_width(text, font, mid)
        
        if width <= max_width:
            best_size = mid
            low = mid  # Try larger
        else:
            high = mid  # Must go smaller
        
        if high - low < 0.1:
            break
    
    return best_size


# ---------------------------------------------------------------------------
# Color utilities
# ---------------------------------------------------------------------------

def _int_to_color(color_int: int) -> Color:
    """Convert PDF color integer to ReportLab Color."""
    try:
        # PDF colors are typically 0xRRGGBB
        r = ((color_int >> 16) & 0xFF) / 255.0
        g = ((color_int >> 8) & 0xFF) / 255.0
        b = (color_int & 0xFF) / 255.0
        return Color(r, g, b)
    except Exception:
        return black


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def _bbox_width(bbox: BBox) -> float:
    return max(0, bbox[2] - bbox[0])


def _bbox_height(bbox: BBox) -> float:
    return max(0, bbox[3] - bbox[1])


def _pdf_y(page_height: float, y_top: float) -> float:
    """
    Convert from PDF top-left origin to ReportLab bottom-left origin.
    PDF: (0,0) is top-left, y increases downward
    ReportLab: (0,0) is bottom-left, y increases upward
    """
    return page_height - y_top


def _iou(a: BBox, b: BBox) -> float:
    """
    Intersection over Union for two axis-aligned rectangles.
    """
    ix0 = max(a[0], b[0])
    iy0 = max(a[1], b[1])
    ix1 = min(a[2], b[2])
    iy1 = min(a[3], b[3])

    inter_w = max(0.0, ix1 - ix0)
    inter_h = max(0.0, iy1 - iy0)
    inter = inter_w * inter_h

    if inter == 0.0:
        return 0.0

    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


# ---------------------------------------------------------------------------
# IoU validation
# ---------------------------------------------------------------------------

def _check_overlaps(
    text_bboxes: List[BBox],
    image_bboxes: List[BBox],
    threshold: float = 0.0,
) -> int:
    """
    Log warnings for every text/image pair whose IoU exceeds *threshold*.
    Returns the count of overlapping pairs.
    """
    overlaps = 0
    for tb in text_bboxes:
        for ib in image_bboxes:
            score = _iou(tb, ib)
            if score > threshold:
                log.warning(
                    "[WARN] Text/image overlap detected "
                    "(IoU=%.3f) text=%s image=%s",
                    score, tb, ib,
                )
                overlaps += 1
    return overlaps


# ---------------------------------------------------------------------------
# ReportLab drawing helpers
# ---------------------------------------------------------------------------

def _draw_text_element(
    c: rl_canvas.Canvas,
    text: str,
    bbox: BBox,
    font_name: str,
    font_size: float,
    color_int: int,
    page_height: float,
) -> BBox:
    """
    Draw *text* inside *bbox* on the canvas, preserving font and color.
    
    Returns the final bbox used.
    """
    if not text or not text.strip():
        return bbox
    
    max_w = _bbox_width(bbox)
    max_h = _bbox_height(bbox)
    
    if max_w <= 0 or max_h <= 0:
        log.warning("Invalid bbox dimensions: %s", bbox)
        return bbox
    
    # Resolve and set font
    font = _resolve_font(font_name)
    
    # Calculate optimal font size
    # Start with original font size, scale down if needed
    fitted_size = _scale_font_to_fit(text, font, font_size, max_w)
    
    # Also check height - text shouldn't exceed bbox height
    # Rough estimate: text height is approx font size * 1.2 (for descenders)
    if fitted_size > max_h / 1.2:
        fitted_size = max(MIN_FONT_SIZE, max_h / 1.2)
    
    if fitted_size < font_size:
        log.debug(
            "Font scaled: %.1f → %.1f for '%s...'",
            font_size, fitted_size, text[:30],
        )
    
    # Calculate position
    # PDF coordinates: (0,0) is top-left, y increases downward
    # bbox[3] is the top of the text (y1 in PDF coordinates)
    # bbox[1] is the bottom of the text (y0 in PDF coordinates)
    # ReportLab: (0,0) is bottom-left, y increases upward
    # drawString draws from the baseline
    
    x = bbox[0]
    # For ReportLab, we need the y position at the baseline
    # The bbox[3] in PDF is the visual top of the text
    # We need to account for ascenders when calculating the baseline position
    y = _pdf_y(page_height, bbox[3])  # Convert PDF top to ReportLab bottom
    
    # Set color
    color = _int_to_color(color_int)
    c.setFillColor(color)
    
    # Set font and draw
    c.setFont(font, fitted_size)
    c.drawString(x, y, text)
    
    return bbox


def _draw_image_element(
    c: rl_canvas.Canvas,
    img: ImageElement,
    page_height: float,
) -> None:
    """Embed a raster image at its original position and size."""
    x = img.bbox[0]
    w = _bbox_width(img.bbox)
    h = _bbox_height(img.bbox)
    
    if w <= 0 or h <= 0:
        log.warning("Invalid image dimensions: %s", img.bbox)
        return
    
    # Convert coordinates: PDF top-left to ReportLab bottom-left
    y = _pdf_y(page_height, img.bbox[1]) - h
    
    try:
        img_io = io.BytesIO(img.image_bytes)
        c.drawImage(img_io, x, y, width=w, height=h, mask="auto")
    except Exception as e:
        log.error("Failed to draw image: %s", e)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def reconstruct(
    chunks: List[SemanticChunk],
    translated_texts: List[str],
    images: List[ImageElement],
    page_sizes: List[Tuple[float, float]],
    on_status: Optional[StatusCallback] = None,
) -> bytes:
    """
    Build and return the translated PDF as raw bytes.
    
    Preserves:
    - Original page dimensions
    - Text positioning and bounding boxes
    - Font styles (with fallback to standard fonts)
    - Text colors
    - Image positions and sizes
    """
    if not page_sizes:
        raise ValueError("No page sizes provided")
    
    if len(chunks) != len(translated_texts):
        raise ValueError(f"Mismatched chunks ({len(chunks)}) and texts ({len(translated_texts)})")
    
    buf = io.BytesIO()

    # Group images by page
    images_by_page: Dict[int, List[ImageElement]] = {}
    for img in images:
        images_by_page.setdefault(img.page, []).append(img)

    # Create canvas with first page size
    first_w, first_h = page_sizes[0]
    c = rl_canvas.Canvas(buf, pagesize=(first_w, first_h))

    # Group chunks by page
    chunks_by_page: Dict[int, List[Tuple[SemanticChunk, str]]] = {}
    for chunk, trans in zip(chunks, translated_texts):
        chunks_by_page.setdefault(chunk.page, []).append((chunk, trans))

    num_pages = len(page_sizes)

    for page_num in range(num_pages):
        pw, ph = page_sizes[page_num]
        c.setPageSize((pw, ph))

        if on_status:
            on_status(f"[INFO] Reconstructing Page {page_num + 1}/{num_pages}")

        text_bboxes: List[BBox] = []

        # Draw translated text chunks
        page_chunks = chunks_by_page.get(page_num, [])
        for chunk, trans_text in page_chunks:
            # Get color from first element if available
            color = chunk.color if hasattr(chunk, 'color') else 0
            
            drawn_bbox = _draw_text_element(
                c, 
                trans_text, 
                chunk.bbox,
                chunk.font_name, 
                chunk.font_size,
                color,
                ph,
            )
            text_bboxes.append(drawn_bbox)

        # Draw original images
        page_imgs = images_by_page.get(page_num, [])
        for img in page_imgs:
            _draw_image_element(c, img, ph)

        # Check for overlaps
        img_bboxes = [img.bbox for img in page_imgs]
        overlaps = _check_overlaps(text_bboxes, img_bboxes)
        if overlaps and on_status:
            on_status(
                f"[WARN] Page {page_num + 1}: "
                f"{overlaps} text/image overlap(s) detected"
            )

        c.showPage()

    c.save()
    buf.seek(0)
    return buf.read()


def reconstruct_selected_pages(
    chunks: List[SemanticChunk],
    translated_texts: List[str],
    images: List[ImageElement],
    page_sizes: List[Tuple[float, float]],
    selected_pages: List[int],
    on_status: Optional[StatusCallback] = None,
) -> bytes:
    """
    Build and return the translated PDF with only selected pages.
    """
    if not page_sizes:
        raise ValueError("No page sizes provided")
    
    if not selected_pages:
        raise ValueError("No pages selected")
    
    # Validate selected pages
    valid_pages = [p for p in selected_pages if 0 <= p < len(page_sizes)]
    if not valid_pages:
        raise ValueError("No valid pages selected")
    
    # Filter data to only selected pages
    selected_set = set(valid_pages)
    
    # Filter chunks
    filtered_chunks = [c for c in chunks if c.page in selected_set]
    filtered_texts = [t for c, t in zip(chunks, translated_texts) if c.page in selected_set]
    
    # Remap page numbers to be sequential
    page_mapping = {old: new for new, old in enumerate(valid_pages)}
    
    # Create new chunks with remapped page numbers
    remapped_chunks = []
    for chunk in filtered_chunks:
        new_chunk = SemanticChunk(
            elements=chunk.elements,
            page=page_mapping[chunk.page]
        )
        remapped_chunks.append(new_chunk)
    
    # Filter and remap images
    filtered_images = []
    for img in images:
        if img.page in selected_set:
            new_img = ImageElement(
                image_bytes=img.image_bytes,
                bbox=img.bbox,
                page=page_mapping[img.page]
            )
            filtered_images.append(new_img)
    
    # Filter page sizes
    filtered_page_sizes = [page_sizes[p] for p in valid_pages]
    
    # Call main reconstruct with filtered data
    return reconstruct(
        remapped_chunks,
        filtered_texts,
        filtered_images,
        filtered_page_sizes,
        on_status,
    )
