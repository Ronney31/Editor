"""
FastAPI backend for PDF Editor.
Handles file upload, page rendering, text extraction, applying edits, and download.
"""

import uuid
import os
from typing import Dict

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import Response, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

from app.pdf_engine import PDFEngine
from app.convert import router as convert_router
from app.image_editor import router as image_editor_router

app = FastAPI(title="PDF Editor", version="1.0.0")
app.include_router(convert_router)
app.include_router(image_editor_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for active sessions
sessions: Dict[str, PDFEngine] = {}

# Serve static frontend files
STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# --- Models ---

class EditOperation(BaseModel):
    type: str
    page: Optional[int] = None
    x: Optional[float] = None
    y: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None
    text: Optional[str] = None
    fontSize: Optional[float] = 12
    fontName: Optional[str] = "helv"
    color: Optional[str] = "#000000"
    imageData: Optional[str] = None
    points: Optional[List[dict]] = None
    lineWidth: Optional[float] = 2


class EditRequest(BaseModel):
    session_id: str
    edits: List[EditOperation]


# --- Endpoints ---

@app.get("/")
async def index():
    """Serve the main editor page."""
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "PDF Editor API"}


@app.post("/api/upload")
async def upload_pdf(file: UploadFile = File(...)):
    """Upload a PDF and create a session."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are supported")

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(400, "Empty file")

    session_id = str(uuid.uuid4())
    try:
        engine = PDFEngine(content)
    except Exception as e:
        raise HTTPException(400, f"Invalid PDF: {str(e)}")

    sessions[session_id] = engine

    return {
        "session_id": session_id,
        "filename": file.filename,
        "page_count": engine.page_count,
        "pages": [engine.get_page_dimensions(i) for i in range(engine.page_count)],
    }


@app.get("/api/page/{session_id}/{page_num}")
async def get_page_image(session_id: str, page_num: int):
    """Render a page as PNG for display."""
    engine = sessions.get(session_id)
    if not engine:
        raise HTTPException(404, "Session not found")
    if page_num < 0 or page_num >= engine.page_count:
        raise HTTPException(400, "Invalid page number")

    png_bytes = engine.render_page(page_num, zoom=2.0)
    return Response(content=png_bytes, media_type="image/png")


@app.get("/api/text/{session_id}/{page_num}")
async def get_page_text(session_id: str, page_num: int):
    """Extract text blocks with formatting from a page for inline editing."""
    engine = sessions.get(session_id)
    if not engine:
        raise HTTPException(404, "Session not found")
    if page_num < 0 or page_num >= engine.page_count:
        raise HTTPException(400, "Invalid page number")

    text_blocks = engine.extract_text_blocks(page_num)
    return {"page": page_num, "blocks": text_blocks}


@app.post("/api/edit")
async def apply_edits(request: EditRequest):
    """Apply edits and return the modified PDF."""
    engine = sessions.get(request.session_id)
    if not engine:
        raise HTTPException(404, "Session not found")

    try:
        edits_raw = [edit.model_dump(exclude_none=True) for edit in request.edits]
        modified_pdf = engine.apply_edits(edits_raw)
    except Exception as e:
        raise HTTPException(500, f"Error applying edits: {str(e)}")

    return Response(
        content=modified_pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=edited.pdf"},
    )


@app.delete("/api/session/{session_id}")
async def close_session(session_id: str):
    """Clean up a session."""
    engine = sessions.pop(session_id, None)
    if engine:
        engine.close()
    return {"status": "ok"}
