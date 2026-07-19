"""
Conversion endpoints: Image to PDF and PDF to Image.
"""

import io
import zipfile
from typing import List

import fitz  # PyMuPDF
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from fastapi.responses import Response

router = APIRouter(prefix="/api/convert", tags=["convert"])


@router.post("/images-to-pdf")
async def images_to_pdf(files: List[UploadFile] = File(...)):
    """
    Convert one or more images to a single PDF.
    Images are added as full pages in the order uploaded.
    """
    if not files:
        raise HTTPException(400, "No files provided")

    doc = fitz.open()

    for file in files:
        img_bytes = await file.read()
        if not img_bytes:
            continue

        try:
            # Open image to get dimensions
            img_doc = fitz.open(stream=img_bytes, filetype=_guess_image_type(file.filename))
            img_pdf = fitz.open("pdf", img_doc.convert_to_pdf())
            
            # Insert the image page into our document
            doc.insert_pdf(img_pdf)
            
            img_pdf.close()
            img_doc.close()
        except Exception as e:
            raise HTTPException(400, f"Error processing {file.filename}: {str(e)}")

    if len(doc) == 0:
        raise HTTPException(400, "No valid images provided")

    output = io.BytesIO()
    doc.save(output, garbage=4, deflate=True)
    doc.close()

    return Response(
        content=output.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=images_converted.pdf"},
    )


@router.post("/pdf-to-images")
async def pdf_to_images(
    file: UploadFile = File(...),
    format: str = Form(default="png"),
    zoom: float = Form(default=2.0),
):
    """
    Convert a PDF to images. Returns a ZIP file containing one image per page.
    Supports png, jpeg formats.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are supported")

    content = await file.read()
    if not content:
        raise HTTPException(400, "Empty file")

    img_format = format.lower()
    if img_format not in ("png", "jpeg", "jpg"):
        raise HTTPException(400, "Supported formats: png, jpeg")
    if img_format == "jpg":
        img_format = "jpeg"

    try:
        doc = fitz.open(stream=content, filetype="pdf")
    except Exception as e:
        raise HTTPException(400, f"Invalid PDF: {str(e)}")

    # Create ZIP with all page images
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for page_num in range(len(doc)):
            page = doc[page_num]
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)

            if img_format == "png":
                img_bytes = pix.tobytes("png")
                ext = "png"
            else:
                img_bytes = pix.tobytes("jpeg")
                ext = "jpg"

            zf.writestr(f"page_{page_num + 1:03d}.{ext}", img_bytes)

    doc.close()

    return Response(
        content=zip_buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=pdf_pages.zip"},
    )


@router.post("/pdf-to-single-image")
async def pdf_to_single_image(
    file: UploadFile = File(...),
    page: int = Form(default=0),
    format: str = Form(default="png"),
    zoom: float = Form(default=2.0),
):
    """Convert a single page of a PDF to an image."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are supported")

    content = await file.read()
    try:
        doc = fitz.open(stream=content, filetype="pdf")
    except Exception as e:
        raise HTTPException(400, f"Invalid PDF: {str(e)}")

    if page < 0 or page >= len(doc):
        raise HTTPException(400, f"Invalid page number. PDF has {len(doc)} pages.")

    pg = doc[page]
    mat = fitz.Matrix(zoom, zoom)
    pix = pg.get_pixmap(matrix=mat)

    img_format = format.lower()
    if img_format in ("jpg", "jpeg"):
        img_bytes = pix.tobytes("jpeg")
        media_type = "image/jpeg"
        ext = "jpg"
    else:
        img_bytes = pix.tobytes("png")
        media_type = "image/png"
        ext = "png"

    doc.close()

    return Response(
        content=img_bytes,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename=page_{page + 1}.{ext}"},
    )


def _guess_image_type(filename: str) -> str:
    """Guess image type from filename extension."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    mapping = {
        "png": "png",
        "jpg": "jpeg",
        "jpeg": "jpeg",
        "gif": "gif",
        "bmp": "bmp",
        "tiff": "tiff",
        "tif": "tiff",
        "webp": "webp",
    }
    return mapping.get(ext, "png")
