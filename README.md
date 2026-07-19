# PDF Editor

A simple browser-based PDF editor built with FastAPI and a static frontend.

## Features

- Upload a PDF file
- Render PDF pages as images
- Extract text from pages
- Apply edits and download the modified PDF
- Serve a static frontend from the `static/` folder

## Requirements

- Python 3.11+
- `pip`

## Setup

1. Create and activate a Python virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

## Running the App

Start the FastAPI server with Uvicorn:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Then open your browser at:

```text
http://127.0.0.1:8000/
```

## Docker

Build the Docker image:

```bash
docker build -t pdf-editor .
```

Run the app in a container:

```bash
docker run --rm -p 8000:8000 pdf-editor
```

Open the app at:

```text
http://127.0.0.1:8000/
```

> The Docker image includes Tesseract OCR, which is required by the image editor features.

## Docker Compose

Start the app with Docker Compose:

```bash
docker compose up --build
```

Stop the service with:

```bash
docker compose down
```

This mounts the repository into the container so code changes are available immediately.

## Project Structure

- `app/`
  - `main.py` — FastAPI application and endpoint definitions
  - `pdf_engine.py` — PDF rendering, text extraction, and edit logic
  - `convert.py` — conversion-related API routes
  - `image_editor.py` — image editing API routes
- `static/` — frontend HTML, JavaScript, and CSS assets
- `requirements.txt` — Python dependencies

## Notes

- The app stores sessions in memory and is intended for local development.
- Uploaded PDFs are handled in-memory by `PyMuPDF`.
- If the frontend is not available, the root endpoint serves a JSON fallback.
