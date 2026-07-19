"""
Image Editor backend: OCR text extraction, inpainting/removal of filled data,
inline text editing, and download.

Key improvement: Uses word-level OCR blocks and confidence-based filtering
to distinguish printed form labels from handwritten filled data.
"""

import io
import uuid
import base64
from typing import Dict, List, Optional

import pytesseract
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

router = APIRouter(prefix="/api/image-editor", tags=["image-editor"])

# In-memory session storage
image_sessions: Dict[str, dict] = {}


class ImageEditOperation(BaseModel):
    type: str  # "remove_text", "add_text", "inpaint_region", "replace_text"
    x: Optional[float] = None
    y: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None
    text: Optional[str] = None
    fontSize: Optional[float] = 14
    color: Optional[str] = "#000000"
    block_ids: Optional[List[int]] = None


class ImageEditRequest(BaseModel):
    session_id: str
    edits: List[ImageEditOperation]


@router.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    """Upload an image and extract text with OCR."""
    content = await file.read()
    if not content:
        raise HTTPException(400, "Empty file")

    try:
        img = Image.open(io.BytesIO(content))
        img = img.convert("RGB")
    except Exception as e:
        raise HTTPException(400, f"Invalid image: {str(e)}")

    session_id = str(uuid.uuid4())

    # Run OCR at word level
    text_blocks = _run_ocr(img)

    # Store session
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="PNG")
    img_bytes = img_bytes.getvalue()

    image_sessions[session_id] = {
        "original_bytes": img_bytes,
        "width": img.width,
        "height": img.height,
        "text_blocks": text_blocks,
        "filename": file.filename,
    }

    return {
        "session_id": session_id,
        "width": img.width,
        "height": img.height,
        "filename": file.filename,
        "text_blocks": text_blocks,
    }


@router.get("/image/{session_id}")
async def get_image(session_id: str):
    """Get the current image for display."""
    session = image_sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return Response(content=session["original_bytes"], media_type="image/png")


@router.get("/text/{session_id}")
async def get_text_blocks(session_id: str):
    """Get OCR-detected text blocks."""
    session = image_sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return {"text_blocks": session["text_blocks"]}


@router.post("/rotate")
async def rotate_image(session_id: str = "", direction: str = "right"):
    """Rotate the image 90 degrees left or right and re-run OCR."""
    session = image_sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    img = Image.open(io.BytesIO(session["original_bytes"])).convert("RGB")

    if direction == "left":
        img = img.rotate(90, expand=True)
    else:
        img = img.rotate(-90, expand=True)

    img_bytes = io.BytesIO()
    img.save(img_bytes, format="PNG")
    img_bytes = img_bytes.getvalue()

    text_blocks = _run_ocr(img)

    session["original_bytes"] = img_bytes
    session["width"] = img.width
    session["height"] = img.height
    session["text_blocks"] = text_blocks

    return {
        "session_id": session_id,
        "width": img.width,
        "height": img.height,
        "text_blocks": text_blocks,
    }


@router.post("/apply")
async def apply_edits(request: ImageEditRequest):
    """Apply edits to the image and return the result."""
    session = image_sessions.get(request.session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    img = Image.open(io.BytesIO(session["original_bytes"])).convert("RGB")

    for edit in request.edits:
        if edit.type == "remove_text":
            if edit.block_ids:
                for block_id in edit.block_ids:
                    block = _find_block(session["text_blocks"], block_id)
                    if block:
                        _smart_inpaint(img, block["x"], block["y"],
                                       block["width"], block["height"])
            elif edit.x is not None:
                _smart_inpaint(img, int(edit.x), int(edit.y),
                               int(edit.width), int(edit.height))

        elif edit.type == "inpaint_region":
            _smart_inpaint(img, int(edit.x), int(edit.y),
                           int(edit.width), int(edit.height))

        elif edit.type == "add_text":
            draw = ImageDraw.Draw(img)
            color = _hex_to_rgb(edit.color or "#000000")
            font = _get_font(edit.fontSize or 14)
            draw.text((edit.x, edit.y), edit.text, fill=color, font=font)

        elif edit.type == "replace_text":
            if edit.x is not None:
                _smart_inpaint(img, int(edit.x), int(edit.y),
                               int(edit.width), int(edit.height))
                draw = ImageDraw.Draw(img)
                color = _hex_to_rgb(edit.color or "#000000")
                font = _get_font(edit.fontSize or 14)
                draw.text((edit.x, edit.y + 2), edit.text or "", fill=color, font=font)

    output = io.BytesIO()
    img.save(output, format="PNG")
    return Response(
        content=output.getvalue(),
        media_type="image/png",
        headers={"Content-Disposition": f"attachment; filename=edited_{session['filename']}"},
    )


@router.post("/remove-all-filled")
async def remove_all_filled_data(session_id: str = ""):
    """
    Remove only the handwritten/filled data from the image.
    Uses confidence scores and text pattern analysis to distinguish
    printed form labels from handwritten content.
    """
    session = image_sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    img = Image.open(io.BytesIO(session["original_bytes"])).convert("RGB")

    # Only remove blocks that look like filled/handwritten data
    for block in session["text_blocks"]:
        if block.get("is_filled", False):
            _smart_inpaint(img, block["x"], block["y"],
                           block["width"], block["height"])

    output = io.BytesIO()
    img.save(output, format="PNG")
    return Response(
        content=output.getvalue(),
        media_type="image/png",
        headers={"Content-Disposition": "attachment; filename=cleaned.png"},
    )


# ============ OCR & Text Detection ============

def _run_ocr(img: Image.Image) -> List[dict]:
    """
    Run OCR at WORD level to get fine-grained text blocks.
    Each word gets its own bounding box and confidence score.
    Classifies each as 'printed' (form label) or 'filled' (user data).
    """
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    blocks = []
    block_id = 0

    n = len(data["text"])
    for i in range(n):
        text = data["text"][i].strip()
        if not text:
            continue
        conf = int(data["conf"][i])
        if conf < 0:
            continue

        x = data["left"][i]
        y = data["top"][i]
        w = data["width"][i]
        h = data["height"][i]

        # Classify: is this printed form text or filled/handwritten data?
        is_filled = _classify_as_filled(text, conf, x, y, w, h, img)

        blocks.append({
            "id": block_id,
            "text": text,
            "x": x,
            "y": y,
            "width": w,
            "height": h,
            "confidence": conf,
            "is_filled": is_filled,
            "category": "filled" if is_filled else "printed",
        })
        block_id += 1

    return blocks


def _classify_as_filled(text: str, confidence: int, x: int, y: int,
                         w: int, h: int, img: Image.Image) -> bool:
    """
    Heuristic to determine if a text block is handwritten/filled data
    vs printed form label.
    
    Strategy:
    - Known form keywords at any confidence = printed
    - Contains only dots/dashes/underscores = filler pattern (filled area)
    - Contains '..' pattern (fill-in blanks) = filled
    - Low confidence (< 50%) = filled (handwriting is hard to OCR)
    - Pure numbers = filled (form numbers, amounts, dates)
    - High confidence clean English words = printed
    """
    # Common form label words
    form_keywords = {
        'date', 'name', 'amount', 'total', 'no', 'no.', 'km', 'kms',
        'hours', 'driver', 'customer', 'pickup', 'drop', 'place',
        'opening', 'closing', 'remarks', 'note', 'extra', 'charges',
        'per', 'day', 'rate', 'bill', 'cash', 'signature', 'balance',
        'advance', 'particulars', 'vehicle', 'mob', 'parking', 'toll',
        'permit', 'bata', 'check', 'post', 'trip', 'minimum', 'outstation',
        'responsible', 'loss', 'airport', 'the', 'and', 'for', 'will',
        'not', 'be', 'is', 'are', 'from', 'after', 'if', 'we',
        'at', 'applicable', 'reading', 'meter', 'timings', 'calculated',
        'hours', 'kms.', 'km.', 'km:', 'your',
    }

    text_lower = text.lower().rstrip(':.,;')
    text_clean = text_lower.strip('.:,;()[]')

    # Rule 1: Known form keyword = printed (regardless of confidence)
    if text_clean in form_keywords:
        return False

    # Rule 2: Only dots/dashes/underscores/spaces = filler pattern
    if all(c in '.…_-–—  ' for c in text):
        return True

    # Rule 3: Contains '..' pattern (fill-in-the-blank) = filled
    if '..' in text or '...' in text:
        return True

    # Rule 4: Low confidence = likely handwritten
    if confidence < 50:
        return True

    # Rule 5: Pure numbers or numbers with punctuation = filled data
    # (bill numbers, dates, amounts, km readings)
    stripped = text.replace(' ', '').replace(',', '').replace('.', '').replace('-', '').replace('/', '')
    if stripped.isdigit() and len(stripped) >= 1:
        return True

    # Rule 6: High confidence common English word patterns = printed
    # Multi-word sentences that OCR reads cleanly
    if confidence >= 85 and len(text) > 5:
        words = text_lower.split()
        form_word_count = sum(1 for w in words if w.rstrip(':.,;') in form_keywords)
        if form_word_count >= len(words) * 0.5:
            return False
        # Clean alpha text with good confidence = printed
        if text.replace(' ', '').replace('.', '').replace(',', '').replace(':', '').isalpha():
            return False

    # Rule 7: Medium confidence (50-85) short text that's not a keyword = filled
    if confidence < 85 and len(text) <= 4 and text_clean not in form_keywords:
        return True

    # Rule 8: Contains name-like patterns with colons = label (printed)
    if text.endswith(':') and text_clean.rstrip(':') in form_keywords:
        return False

    # Default: medium-high confidence longer text = printed
    if confidence >= 70 and len(text) > 4:
        return False

    return True


def _find_block(blocks: List[dict], block_id: int) -> Optional[dict]:
    for b in blocks:
        if b["id"] == block_id:
            return b
    return None


# ============ Inpainting ============

def _smart_inpaint(img: Image.Image, x: int, y: int, w: int, h: int, padding: int = 2):
    """
    Smart inpainting: samples background from edges of the region and fills.
    Uses a slight blur at edges for smoother blending.
    """
    x1 = max(0, x - padding)
    y1 = max(0, y - padding)
    x2 = min(img.width, x + w + padding)
    y2 = min(img.height, y + h + padding)

    # Sample background color from surrounding pixels
    bg_color = _sample_background_robust(img, x1, y1, x2, y2)

    # Fill the region
    draw = ImageDraw.Draw(img)
    draw.rectangle([x1, y1, x2, y2], fill=bg_color)

    # Optional: slight blur at edges for blending (1px border)
    _blend_edges(img, x1, y1, x2, y2)


def _sample_background_robust(img: Image.Image, x1: int, y1: int, x2: int, y2: int) -> tuple:
    """
    Robustly sample background by taking pixels from outside the region,
    filtering out dark pixels (which are likely text/lines), and using
    the mode/median of the remaining light pixels.
    """
    pixels = []
    border = 5

    # Sample strips outside each edge
    for sx in range(x1, x2, 2):
        # Above
        sy = max(0, y1 - border)
        if 0 <= sx < img.width and 0 <= sy < img.height:
            pixels.append(img.getpixel((sx, sy)))
        # Below
        sy = min(img.height - 1, y2 + border)
        if 0 <= sx < img.width and 0 <= sy < img.height:
            pixels.append(img.getpixel((sx, sy)))

    for sy in range(y1, y2, 2):
        # Left
        sx = max(0, x1 - border)
        if 0 <= sx < img.width and 0 <= sy < img.height:
            pixels.append(img.getpixel((sx, sy)))
        # Right
        sx = min(img.width - 1, x2 + border)
        if 0 <= sx < img.width and 0 <= sy < img.height:
            pixels.append(img.getpixel((sx, sy)))

    if not pixels:
        return (255, 255, 255)

    # Filter: keep only "light" pixels (likely background, not text)
    # Text is typically dark (< 128 brightness)
    light_pixels = [p for p in pixels if (p[0] + p[1] + p[2]) / 3 > 180]

    # If most pixels are light, use them; otherwise fall back to all pixels
    if len(light_pixels) >= len(pixels) * 0.3:
        pixels = light_pixels

    # Median per channel
    r_vals = sorted(p[0] for p in pixels)
    g_vals = sorted(p[1] for p in pixels)
    b_vals = sorted(p[2] for p in pixels)
    mid = len(r_vals) // 2

    return (r_vals[mid], g_vals[mid], b_vals[mid])


def _blend_edges(img: Image.Image, x1: int, y1: int, x2: int, y2: int):
    """Apply a subtle blend at the edges of the inpainted region."""
    # Crop a slightly larger area, blur just the border pixels
    border = 1
    bx1 = max(0, x1 - border)
    by1 = max(0, y1 - border)
    bx2 = min(img.width, x2 + border)
    by2 = min(img.height, y2 + border)

    region = img.crop((bx1, by1, bx2, by2))
    blurred = region.filter(ImageFilter.GaussianBlur(radius=0.5))

    # Only paste the border pixels back (not the interior)
    # For simplicity, paste the full blurred region — effect is subtle
    img.paste(blurred, (bx1, by1))


# ============ Utils ============

def _get_font(size: float):
    """Get a font for text rendering."""
    try:
        return ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", int(size))
    except Exception:
        try:
            return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", int(size))
        except Exception:
            return ImageFont.load_default()


def _hex_to_rgb(hex_color: str) -> tuple:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
