"""CLI command: extract-pdf — Extract text from PDF files and convert to Markdown.

Usage:
  cli.py extract-pdf --input file.pdf --output-dir ./input
  cli.py extract-pdf --input-dir ./uploads --output-dir ./input
"""

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

MAX_PAGES = 500
MAX_FILE_SIZE = 200 * 1024 * 1024  # 200MB
MIN_TEXT_LENGTH = 20  # Minimum chars per page to consider extraction successful


def _log(level: str, message: str) -> None:
    """Print JSON log line to stdout."""
    print(json.dumps({
        "event": "log", "level": level,
        "phase": "fetch", "message": message,
    }, ensure_ascii=False), flush=True)


def _clean_text(text: str) -> str:
    """Clean extracted PDF text: fix hyphenation, normalize whitespace."""
    # Merge hyphenated words at line breaks: "exam-\nple" -> "example"
    text = re.sub(r'(\w)-\n(\w)', r'\1\2', text)
    # Fix multiple newlines -> max 2
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Remove standalone page numbers (lines that are just digits)
    text = re.sub(r'^\s*\d+\s*$', '', text, flags=re.MULTILINE)
    return text.strip()


def _detect_repeated_header_footer(pages_text: list[str]) -> tuple[str, str]:
    """Detect repeated first/last lines across pages as headers/footers."""
    if len(pages_text) < 3:
        return "", ""

    # Check first line of each page
    first_lines = []
    last_lines = []
    for pt in pages_text:
        lines = [l.strip() for l in pt.split('\n') if l.strip()]
        if lines:
            first_lines.append(lines[0])
            last_lines.append(lines[-1])

    # If > 50% of pages share the same first line, it's a header
    header = ""
    if first_lines:
        from collections import Counter
        common_first = Counter(first_lines).most_common(1)[0]
        if common_first[1] > len(pages_text) * 0.5:
            header = common_first[0]

    footer = ""
    if last_lines:
        from collections import Counter
        common_last = Counter(last_lines).most_common(1)[0]
        if common_last[1] > len(pages_text) * 0.5:
            footer = common_last[0]

    return header, footer


def _remove_header_footer(text: str, header: str, footer: str) -> str:
    """Remove detected repeated headers/footers from page text."""
    if header:
        text = text.replace(header, '', 1).strip()
    if footer:
        # Remove last occurrence
        idx = text.rfind(footer)
        if idx >= 0:
            text = text[:idx] + text[idx + len(footer):]
    return text.strip()


def _check_tesseract() -> bool:
    """Check if Tesseract OCR binary is available."""
    import shutil
    return shutil.which("tesseract") is not None


def _ocr_page(page, language: str = "vie+eng", dpi: int = 300) -> str:
    """OCR a single PDF page using PyMuPDF pixmap + pytesseract."""
    try:
        import pytesseract
        from PIL import Image
        import io
    except ImportError:
        return ""

    try:
        pix = page.get_pixmap(dpi=dpi)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        text = pytesseract.image_to_string(img, lang=language)
        return text.strip()
    except Exception as e:
        _log("debug", f"OCR failed for page: {e}")
        return ""


def _detect_heading(line: str, spans: list | None = None) -> int:
    """Detect if a line is likely a heading. Returns heading level (1-3) or 0."""
    line = line.strip()
    if not line or len(line) > 100:
        return 0

    # ALL CAPS short text -> likely heading
    if line.isupper() and len(line) > 3:
        return 1

    # Title Case with no ending punctuation
    if line.istitle() and not line.endswith(('.', ',', ';', ':', '?', '!')):
        if len(line) < 60:
            return 2

    # If we have font info from spans, check size
    if spans:
        avg_size = sum(s.get('size', 12) for s in spans) / max(len(spans), 1)
        if avg_size > 16:
            return 1
        if avg_size > 13:
            return 2

    return 0


def extract_single_pdf(pdf_path: str, output_dir: str) -> str | None:
    """Extract text from a single PDF and save as Markdown.

    Returns the output file path, or None on failure.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        _log("error", "PyMuPDF not installed. Run: pip install PyMuPDF")
        return None

    pdf_path = os.path.abspath(pdf_path)
    if not os.path.isfile(pdf_path):
        _log("error", f"PDF file not found: {pdf_path}")
        return None
    file_size = os.path.getsize(pdf_path)

    if file_size > MAX_FILE_SIZE:
        _log("error", f"PDF too large: {file_size / 1024 / 1024:.1f}MB (max {MAX_FILE_SIZE // 1024 // 1024}MB)")
        return None

    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        _log("error", f"Cannot open PDF {pdf_path}: {e}")
        return None

    page_count = len(doc)
    if page_count == 0:
        _log("warn", f"PDF has no pages: {pdf_path}")
        doc.close()
        return None

    truncated = False
    if page_count > MAX_PAGES:
        _log("warn", f"PDF has {page_count} pages, truncating to {MAX_PAGES}")
        page_count = MAX_PAGES
        truncated = True

    # Extract text per page (fast pass)
    pages_text = []
    empty_pages = 0
    for i in range(page_count):
        page = doc[i]
        text = page.get_text()
        pages_text.append(text)
        if len(text.strip()) < MIN_TEXT_LENGTH:
            empty_pages += 1

    # OCR fallback for scanned/image-based PDFs
    needs_ocr = empty_pages > page_count * 0.5
    if needs_ocr:
        has_tesseract = _check_tesseract()
        if has_tesseract:
            _log("info", f"Scanned PDF detected ({empty_pages}/{page_count} pages empty). Using OCR (slower)...")
            ocr_count = 0
            for i in range(page_count):
                if len(pages_text[i].strip()) < MIN_TEXT_LENGTH:
                    ocr_text = _ocr_page(doc[i])
                    if ocr_text:
                        pages_text[i] = ocr_text
                        ocr_count += 1
            _log("info", f"OCR extracted text from {ocr_count}/{empty_pages} pages")
        else:
            _log("warn",
                "Scanned PDF requires Tesseract OCR but it is not installed. "
                "Install: choco install tesseract (Windows) or apt install tesseract-ocr (Linux). "
                "Skipping OCR — text extraction will be limited."
            )

    # Detect title from first page or filename
    basename = Path(pdf_path).stem
    title = basename.replace('_', ' ').replace('-', ' ').title()
    # Try to find a better title from first page large text
    if pages_text and pages_text[0].strip():
        first_lines = [l.strip() for l in pages_text[0].split('\n') if l.strip()]
        if first_lines:
            candidate = first_lines[0]
            if len(candidate) < 100:
                title = candidate

    # Detect and remove repeated headers/footers
    header, footer = _detect_repeated_header_footer(pages_text)

    # Build Markdown output
    md_lines = []
    for i, pt in enumerate(pages_text):
        if header or footer:
            pt = _remove_header_footer(pt, header, footer)

        cleaned = _clean_text(pt)
        if not cleaned:
            continue

        # Try to detect headings within the text
        result_lines = []
        for line in cleaned.split('\n'):
            heading_level = _detect_heading(line)
            if heading_level > 0:
                result_lines.append(f"\n{'#' * (heading_level + 1)} {line.strip()}\n")
            else:
                result_lines.append(line)

        md_lines.append(f"## Page {i + 1}\n")
        md_lines.append('\n'.join(result_lines))
        md_lines.append('')

    doc.close()

    content = '\n'.join(md_lines).strip()
    if not content:
        _log("warn", f"No extractable text from {pdf_path}")
        return None

    if truncated:
        content += f"\n\n*[Truncated: showing {MAX_PAGES} of {len(doc)} pages]*"

    # Build output file
    now = datetime.now(timezone.utc).isoformat()
    output = f"""---
source_file: {os.path.basename(pdf_path)}
extracted_at: {now}
pages: {page_count}
title: "{title}"
---

# {title}

{content}
"""
    os.makedirs(output_dir, exist_ok=True)
    out_name = f"pdf_{basename}.md"
    out_path = os.path.join(output_dir, out_name)

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(output)

    _log("info", f"Extracted {page_count} pages from {os.path.basename(pdf_path)}")
    return out_path


def run_extract_pdf(input_path: str | None, input_dir: str | None,
                    output_dir: str) -> int:
    """Main entry point for extract-pdf command.

    Returns exit code: 0 on success (even partial), 1 on total failure.
    """
    pdf_files = []

    if input_path:
        if not os.path.isfile(input_path):
            _log("error", f"PDF file not found: {input_path}")
            return 1
        pdf_files.append(input_path)

    if input_dir:
        if not os.path.isdir(input_dir):
            _log("error", f"Directory not found: {input_dir}")
            return 1
        for f in sorted(Path(input_dir).iterdir()):
            if f.suffix.lower() == '.pdf':
                pdf_files.append(str(f))

    if not pdf_files:
        _log("error", "No PDF files found")
        return 1

    _log("info", f"Extracting {len(pdf_files)} PDF(s)...")

    created = []
    for pdf in pdf_files:
        result = extract_single_pdf(pdf, output_dir)
        if result:
            created.append(result)

    if created:
        _log("info", f"Extracted {len(created)}/{len(pdf_files)} PDFs successfully")
        print(json.dumps({
            "event": "extract-pdf-done",
            "files": created,
            "total": len(pdf_files),
            "success": len(created),
        }, ensure_ascii=False), flush=True)
        return 0
    else:
        _log("error", "All PDF extractions failed")
        return 1
