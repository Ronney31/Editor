# PDF & Image Editor — Architecture Document

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Browser (Client)                       │
│                                                         │
│  ┌──────────┐  ┌──────────┐  ┌────────┐  ┌──────────┐ │
│  │PDF Editor│  │Img Editor│  │Img→PDF │  │PDF→Img   │ │
│  │  Tab     │  │  Tab     │  │  Tab   │  │  Tab     │ │
│  └────┬─────┘  └────┬─────┘  └───┬────┘  └────┬─────┘ │
│       │              │            │             │        │
│  ┌────┴──────────────┴────────────┴─────────────┴────┐  │
│  │              Static JS Modules                     │  │
│  │  editor.js | image-editor.js | convert.js | api.js│  │
│  └────────────────────────┬───────────────────────────┘  │
└───────────────────────────┼──────────────────────────────┘
                            │ HTTP REST API
┌───────────────────────────┼──────────────────────────────┐
│                    FastAPI Server                         │
│                                                         │
│  ┌─────────────────────────────────────────────────────┐ │
│  │                   main.py (Router)                   │ │
│  │  /api/upload  /api/page  /api/text  /api/edit       │ │
│  └──────┬──────────────┬──────────────────┬────────────┘ │
│         │              │                  │              │
│  ┌──────┴──────┐ ┌─────┴───────┐ ┌───────┴──────────┐  │
│  │ pdf_engine  │ │image_editor │ │    convert.py    │  │
│  │  .py        │ │   .py       │ │                  │  │
│  │             │ │             │ │ images-to-pdf    │  │
│  │ • Render    │ │ • OCR       │ │ pdf-to-images    │  │
│  │ • Extract   │ │ • Classify  │ │ pdf-to-single    │  │
│  │ • Redact    │ │ • Inpaint   │ │                  │  │
│  │ • Edit      │ │ • Rotate    │ │                  │  │
│  └──────┬──────┘ └──────┬──────┘ └───────┬──────────┘  │
│         │              │                  │              │
│  ┌──────┴──────────────┴──────────────────┴──────────┐  │
│  │              Libraries                             │  │
│  │  PyMuPDF (fitz) | Pillow (PIL) | pytesseract      │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

---

## Component Details

### Backend (Python/FastAPI)

| Module | Responsibility | Key Dependencies |
|--------|---------------|-----------------|
| `app/main.py` | HTTP server, routing, static file serving, session management | FastAPI, uvicorn |
| `app/pdf_engine.py` | PDF rendering, text extraction, redaction-based editing | PyMuPDF (fitz) |
| `app/image_editor.py` | OCR, text classification, inpainting, rotation | pytesseract, Pillow |
| `app/convert.py` | Format conversion (images↔PDF) | PyMuPDF, Pillow |

### Frontend (Vanilla JS/HTML/CSS)

| Module | Responsibility |
|--------|---------------|
| `static/index.html` | Page structure, tab layout, all UI elements |
| `static/styles.css` | Dark theme, responsive layout, component styling |
| `static/editor.js` | PDF editor: upload, page rendering, inline text editing, tools |
| `static/image-editor.js` | Image editor: upload, OCR overlays, selection, removal |
| `static/convert.js` | Conversion tabs: image-to-PDF, PDF-to-image, tab navigation |
| `static/api.js` | HTTP client module for backend communication |

---

## Data Flow

### PDF Editing Flow
```
Upload PDF → Store in memory → Render pages as PNG
                                      ↓
                              Extract text (positions + fonts)
                                      ↓
                              Display editable overlays in browser
                                      ↓
                              User edits text inline
                                      ↓
                              On Download: Apply redactions
                                 ├─ Remove original text (content stream)
                                 ├─ Preserve background (fill=False)
                                 ├─ Preserve images (IMAGE_NONE)
                                 └─ Re-insert new text (same font/color/position)
                                      ↓
                              Return modified PDF bytes
```

### Image Editing Flow
```
Upload Image → Store in memory → Run OCR (word-level)
                                      ↓
                              Classify each word: printed vs filled
                                      ↓
                              Display overlays (orange=filled, gray=printed)
                                      ↓
                              User selects blocks or clicks "Remove All Filled"
                                      ↓
                              On Apply:
                                 ├─ Sample background color from region edges
                                 ├─ Filter out dark pixels (text) from samples
                                 ├─ Fill region with median background color
                                 └─ Apply edge blending
                                      ↓
                              Return modified image
```

---

## API Endpoints

### PDF Editor
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/upload` | Upload PDF, create session |
| GET | `/api/page/{session_id}/{page_num}` | Render page as PNG |
| GET | `/api/text/{session_id}/{page_num}` | Extract text blocks with formatting |
| POST | `/api/edit` | Apply edits, return modified PDF |
| DELETE | `/api/session/{session_id}` | Close session |

### Image Editor
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/image-editor/upload` | Upload image, run OCR |
| GET | `/api/image-editor/image/{session_id}` | Get current image |
| GET | `/api/image-editor/text/{session_id}` | Get text blocks |
| POST | `/api/image-editor/apply` | Apply edits |
| POST | `/api/image-editor/rotate` | Rotate 90° and re-OCR |
| POST | `/api/image-editor/remove-all-filled` | Remove all filled data |

### Conversion
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/convert/images-to-pdf` | Multiple images → single PDF |
| POST | `/api/convert/pdf-to-images` | PDF → ZIP of images |
| POST | `/api/convert/pdf-to-single-image` | Single page → image |

---

## Session Management

- **In-memory storage**: Sessions stored in Python dicts (not persistent)
- **Session ID**: UUID4 generated on upload
- **Lifecycle**: Created on upload, destroyed on explicit delete or server restart
- **Data stored**: Original file bytes, page dimensions, extracted text blocks

---

## Key Design Decisions

1. **Redaction over overlay**: PDF text editing uses PyMuPDF's redaction API to actually remove content from the PDF content stream, rather than painting white rectangles on top. This preserves background colors and prevents text bleeding through.

2. **Word-level OCR**: Image editor uses word-level (not line-level) OCR to get fine-grained bounding boxes. This allows removing individual filled words without affecting adjacent printed labels.

3. **Confidence-based classification**: Text is classified as printed vs filled using OCR confidence scores, keyword matching, and text pattern analysis — no ML model required.

4. **Background-aware inpainting**: When removing text from images, the system samples surrounding pixels, filters out dark text pixels, and uses the median of light pixels as the fill color.

5. **No external dependencies at runtime**: All processing is local — no cloud APIs, no internet required during use.

---

## Technology Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Language | Python | 3.10+ |
| Web Framework | FastAPI | 0.115.0 |
| ASGI Server | uvicorn | 0.30.6 |
| PDF Engine | PyMuPDF (fitz) | 1.28.0 |
| Image Processing | Pillow | 10.4.0 |
| OCR | pytesseract + Tesseract | 0.3.13 |
| Frontend | Vanilla HTML/CSS/JS | ES Modules |
| File Upload | python-multipart | 0.0.9 |
