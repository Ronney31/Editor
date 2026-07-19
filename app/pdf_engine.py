"""
PDF manipulation engine using PyMuPDF (fitz).
Uses proper redaction to remove original text content and re-insert edited text,
preserving the PDF background, images, and formatting.
"""

import io
import base64
from typing import List

import fitz  # PyMuPDF


class PDFEngine:
    """Handles all PDF operations: rendering, text extraction, and applying edits."""

    def __init__(self, pdf_bytes: bytes):
        self.original_bytes = pdf_bytes
        self.doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    @property
    def page_count(self) -> int:
        return len(self.doc)

    def render_page(self, page_num: int, zoom: float = 2.0) -> bytes:
        """Render a page as PNG image for frontend display."""
        page = self.doc[page_num]
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        return pix.tobytes("png")

    def get_page_dimensions(self, page_num: int) -> dict:
        """Get original page dimensions (in points)."""
        page = self.doc[page_num]
        rect = page.rect
        return {"width": rect.width, "height": rect.height}

    def extract_text_blocks(self, page_num: int) -> List[dict]:
        """
        Extract all text spans from a page with their exact position and formatting.
        Groups spans per line for inline editing.
        """
        page = self.doc[page_num]
        blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]

        text_items = []
        block_id = 0

        for block in blocks:
            if block["type"] != 0:
                continue

            for line in block["lines"]:
                line_spans = []
                for span in line["spans"]:
                    if not span["text"].strip():
                        continue
                    line_spans.append(span)

                if not line_spans:
                    continue

                line_bbox = line["bbox"]
                first_span = line_spans[0]
                full_text = "".join(s["text"] for s in line_spans)

                color_int = first_span.get("color", 0)
                color_hex = "#{:06x}".format(color_int)

                text_items.append({
                    "id": f"p{page_num}_b{block_id}",
                    "text": full_text,
                    "x": line_bbox[0],
                    "y": line_bbox[1],
                    "width": line_bbox[2] - line_bbox[0],
                    "height": line_bbox[3] - line_bbox[1],
                    "fontSize": first_span["size"],
                    "fontName": first_span["font"],
                    "color": color_hex,
                    "flags": first_span.get("flags", 0),
                })
                block_id += 1

        return text_items

    def apply_edits(self, edits: List[dict]) -> bytes:
        """
        Apply edits and return modified PDF bytes.
        Uses redaction for text replacement to properly remove original content.
        """
        doc = fitz.open(stream=self.original_bytes, filetype="pdf")

        pages_to_delete = []
        content_edits = []

        for edit in edits:
            if edit.get("type") == "delete_page":
                pages_to_delete.append(edit["page"])
            else:
                content_edits.append(edit)

        # Group inline_text edits by page so we can batch redactions
        page_text_edits = {}
        other_edits = []
        for edit in content_edits:
            if edit["type"] == "inline_text":
                pg = edit["page"]
                if pg not in page_text_edits:
                    page_text_edits[pg] = []
                page_text_edits[pg].append(edit)
            else:
                other_edits.append(edit)

        # Apply text edits using redaction (proper content removal)
        for page_num, text_edits in page_text_edits.items():
            page = doc[page_num]
            self._apply_text_redactions(page, text_edits)

        # Apply other edits (draw, image, etc.)
        for edit in other_edits:
            page = doc[edit["page"]]
            if edit["type"] == "add_text":
                self._apply_add_text(page, edit)
            elif edit["type"] == "add_image":
                self._apply_add_image(doc, page, edit)
            elif edit["type"] == "draw":
                self._apply_draw(page, edit)

        # Delete pages
        if pages_to_delete:
            for pg in sorted(pages_to_delete, reverse=True):
                doc.delete_page(pg)

        output = io.BytesIO()
        doc.save(output, garbage=4, deflate=True)
        doc.close()
        return output.getvalue()

    def _apply_text_redactions(self, page: fitz.Page, edits: List[dict]):
        """
        Use PyMuPDF redaction to properly remove original text and re-insert new text.
        Redaction removes content from the PDF content stream entirely, preserving
        the background (colors, images, shapes behind the text stay intact).
        """
        # Step 1: Add redaction annotations for each text area
        # We use fill=False so the redaction doesn't paint any fill color -
        # it just removes the text content, leaving the background untouched.
        for edit in edits:
            rect = fitz.Rect(
                edit["x"],
                edit["y"],
                edit["x"] + edit["width"],
                edit["y"] + edit["height"]
            )
            # Add redaction that removes text but preserves background
            # text="" means don't add replacement text via redaction itself
            page.add_redact_annot(
                rect,
                text="",
                fill=False,  # Don't fill with any color - preserve background
            )

        # Step 2: Apply all redactions - this removes the original text from content stream
        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)

        # Step 3: Re-insert the new text at the original positions
        for edit in edits:
            new_text = edit.get("text", "")
            if not new_text:
                continue

            font_size = edit.get("fontSize", 12)
            color = self._parse_color(edit.get("color", "#000000"))
            font_name = edit.get("fontName", "helv")
            fitz_font = self._map_font_name(font_name)

            # Calculate baseline position
            # In PDF, text is positioned at baseline. The bbox top is ascender.
            # Baseline ≈ top + fontSize * 0.85 (approximate ascender ratio)
            x = edit["x"]
            y = edit["y"] + font_size * 0.85

            page.insert_text(
                fitz.Point(x, y),
                new_text,
                fontsize=font_size,
                fontname=fitz_font,
                color=color,
            )

    def _apply_add_text(self, page: fitz.Page, edit: dict):
        """Add new text at a position."""
        font_size = edit.get("fontSize", 12)
        color = self._parse_color(edit.get("color", "#000000"))
        font_name = self._map_font_name(edit.get("fontName", "helv"))
        page.insert_text(
            fitz.Point(edit["x"], edit["y"]),
            edit["text"],
            fontsize=font_size,
            fontname=font_name,
            color=color,
        )

    def _apply_add_image(self, doc: fitz.Document, page: fitz.Page, edit: dict):
        """Add an image at a position."""
        img_data = base64.b64decode(edit["imageData"])
        rect = fitz.Rect(edit["x"], edit["y"], edit["x"] + edit["width"], edit["y"] + edit["height"])
        page.insert_image(rect, stream=img_data)

    def _apply_draw(self, page: fitz.Page, edit: dict):
        """Draw freehand paths."""
        shape = page.new_shape()
        points = edit.get("points", [])
        color = self._parse_color(edit.get("color", "#000000"))
        width = edit.get("lineWidth", 2)

        if len(points) < 2:
            return

        for i in range(1, len(points)):
            shape.draw_line(
                fitz.Point(points[i - 1]["x"], points[i - 1]["y"]),
                fitz.Point(points[i]["x"], points[i]["y"])
            )
        shape.finish(color=color, width=width)
        shape.commit()

    def _map_font_name(self, font_name: str) -> str:
        """Map extracted PDF font names to fitz built-in font names."""
        name_lower = font_name.lower()
        if "bold" in name_lower and ("italic" in name_lower or "oblique" in name_lower):
            return "hebi"
        elif "bold" in name_lower:
            return "hebo"
        elif "italic" in name_lower or "oblique" in name_lower:
            return "heit"
        elif "courier" in name_lower or "mono" in name_lower:
            if "bold" in name_lower:
                return "cobo"
            return "cour"
        elif "times" in name_lower:
            if "bold" in name_lower:
                return "tibo"
            elif "italic" in name_lower:
                return "tiit"
            return "tiro"
        elif "arial" in name_lower:
            return "helv"  # Helvetica is closest to Arial
        else:
            return "helv"

    def _parse_color(self, hex_color: str) -> tuple:
        """Convert hex color (#RRGGBB) to RGB tuple (0-1 range)."""
        hex_color = hex_color.lstrip("#")
        if len(hex_color) < 6:
            hex_color = hex_color.ljust(6, '0')
        r = int(hex_color[0:2], 16) / 255.0
        g = int(hex_color[2:4], 16) / 255.0
        b = int(hex_color[4:6], 16) / 255.0
        return (r, g, b)

    def close(self):
        self.doc.close()
