# PDF & Image Editor — Task Tracker

## Completed ✅

### Phase 1: PDF Editor (Core)
| # | Task | Status |
|---|------|--------|
| 1 | Project scaffolding (FastAPI, requirements.txt, directory structure) | ✅ Done |
| 2 | PDF upload endpoint with session management | ✅ Done |
| 3 | PDF page rendering as PNG (PyMuPDF) | ✅ Done |
| 4 | Text extraction with position, font, size, color metadata | ✅ Done |
| 5 | Frontend: Upload UI with drag-drop | ✅ Done |
| 6 | Frontend: Page rendering with navigation (prev/next) | ✅ Done |
| 7 | Frontend: Editable text overlays positioned over PDF text | ✅ Done |
| 8 | Backend: Redaction-based text replacement (proper content removal) | ✅ Done |
| 9 | Background preservation during redaction (fill=False) | ✅ Done |
| 10 | Image preservation during redaction (IMAGE_NONE flag) | ✅ Done |
| 11 | Font mapping (PDF font names → fitz built-in fonts) | ✅ Done |
| 12 | Freehand drawing tool on canvas overlay | ✅ Done |
| 13 | Page deletion | ✅ Done |
| 14 | Download edited PDF with all modifications | ✅ Done |
| 15 | Coordinate conversion (canvas pixels → PDF points) | ✅ Done |

### Phase 2: Conversion Tools
| # | Task | Status |
|---|------|--------|
| 16 | Image to PDF: Multi-image upload with preview | ✅ Done |
| 17 | Image to PDF: Convert and download as PDF | ✅ Done |
| 18 | PDF to Image: Upload PDF, select format/quality | ✅ Done |
| 19 | PDF to Image: Convert all pages, download as ZIP | ✅ Done |
| 20 | Tab-based navigation between features | ✅ Done |

### Phase 3: Image Editor
| # | Task | Status |
|---|------|--------|
| 21 | Image upload with OCR text detection (pytesseract) | ✅ Done |
| 22 | Word-level OCR with bounding boxes | ✅ Done |
| 23 | Text classification: printed vs filled (heuristic-based) | ✅ Done |
| 24 | Frontend: Editable text overlays with color coding (orange/gray) | ✅ Done |
| 25 | Select blocks for removal (Ctrl+Click) | ✅ Done |
| 26 | Remove selected blocks with smart inpainting | ✅ Done |
| 27 | "Remove All Filled Data" — clears only classified filled content | ✅ Done |
| 28 | Background-aware inpainting (median sampling, dark pixel filtering) | ✅ Done |
| 29 | Image rotation (90° left/right) with OCR re-run | ✅ Done |
| 30 | Inline text replacement on images | ✅ Done |

### Phase 4: Bug Fixes & Improvements
| # | Task | Status |
|---|------|--------|
| 31 | Fixed: White patch on colored backgrounds (PDF editor) | ✅ Done |
| 32 | Fixed: Icon/image doubling in PDF edits | ✅ Done |
| 33 | Fixed: PyMuPDF version compatibility (1.24.9 → 1.28.0) | ✅ Done |
| 34 | Fixed: OCR grouping printed labels with filled data (line→word level) | ✅ Done |

---

## Known Issues / Pending 🔧

| # | Issue | Priority | Notes |
|---|-------|----------|-------|
| P1 | "Remove All Filled Data" uses generic heuristic — may misclassify on some forms | P1 | Works well for cab bills; may need tuning for other form types |
| P2 | PDF font substitution: Helvetica used when original font not available as built-in | P2 | Text looks slightly different with non-standard fonts |
| P3 | Inline text editing doesn't support multi-line text reflow | P2 | Each line is edited independently |
| P4 | Session data is in-memory — lost on server restart | P1 | No persistent storage |
| P5 | No undo/redo functionality in editors | P1 | Users must re-upload to reset |
| P6 | Large PDF rendering can be slow (>10 pages) | P2 | Pages rendered one at a time |

---

## Future Improvements 🚀

### High Priority
| # | Improvement | Description |
|---|-------------|-------------|
| F1 | **Template-based form cleaning** | Let users draw rectangles to define "fillable regions" on a form. Save as template. Apply template to remove filled data from any copy of that form. |
| F2 | **Undo/Redo** | Track edit history with ability to undo/redo changes before download. |
| F3 | **Persistent storage** | Use SQLite or file-based storage so sessions survive server restarts. |
| F4 | **Custom font embedding** | Extract and re-embed original fonts for exact text reproduction in PDF edits. |
| F5 | **Batch processing** | Upload multiple PDFs/images and apply the same edits to all. |

### Medium Priority
| # | Improvement | Description |
|---|-------------|-------------|
| F6 | **AI-powered text classification** | Train a small model to distinguish handwritten vs printed text more accurately than heuristics. |
| F7 | **PDF form field detection** | Auto-detect form fields (AcroForm) and allow editing form values directly. |
| F8 | **Image crop/resize tools** | Basic image manipulation before/after OCR processing. |
| F9 | **PDF merge/split** | Combine multiple PDFs or extract page ranges. |
| F10 | **Zoom controls** | Zoom in/out on the editor canvas for precision editing. |
| F11 | **Text search & replace** | Find all instances of text across pages and batch replace. |
| F12 | **Page reordering** | Drag-and-drop page thumbnails to reorder PDF pages. |

### Low Priority / Nice-to-Have
| # | Improvement | Description |
|---|-------------|-------------|
| F13 | **Collaborative editing** | WebSocket-based real-time multi-user editing. |
| F14 | **PDF password/encryption support** | Open password-protected PDFs, apply/remove encryption. |
| F15 | **OCR language support** | Support for non-English text recognition (Hindi, etc.). |
| F16 | **Export to Word/HTML** | Convert PDF to editable Word or HTML format. |
| F17 | **Watermark tools** | Add/remove watermarks from PDFs and images. |
| F18 | **Digital signature** | Add digital signature fields to PDFs. |
| F19 | **Cloud deployment** | Dockerize and deploy to AWS/GCP with user authentication. |
| F20 | **Mobile responsive UI** | Touch-friendly editing on tablets/phones. |

---

## Project Structure

```
pdfEditor/
├── docs/
│   ├── REQUIREMENTS.md          ← This file
│   ├── ARCHITECTURE.md          ← System architecture
│   └── TASKS.md                 ← Task tracker (this file)
├── app/
│   ├── __init__.py
│   ├── main.py                  ← FastAPI server + routing
│   ├── pdf_engine.py            ← PDF manipulation (PyMuPDF)
│   ├── image_editor.py          ← Image OCR + inpainting
│   └── convert.py               ← Format conversion
├── static/
│   ├── index.html               ← Single-page app HTML
│   ├── styles.css               ← Dark theme CSS
│   ├── editor.js                ← PDF editor frontend
│   ├── image-editor.js          ← Image editor frontend
│   ├── convert.js               ← Conversion + tab navigation
│   └── api.js                   ← API client module
└── requirements.txt             ← Python dependencies
```

---

## How to Run

```bash
# Install system dependency
brew install tesseract          # macOS
# apt install tesseract-ocr    # Ubuntu/Debian

# Install Python dependencies
cd pdfEditor
pip install -r requirements.txt

# Run the server
uvicorn app.main:app --reload --port 7070

# Open in browser
open http://localhost:7070
```
