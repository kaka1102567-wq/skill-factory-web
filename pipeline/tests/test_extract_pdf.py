"""Tests for the extract-pdf CLI command."""

import os
import pytest

from pipeline.commands.extract_pdf import (
    _clean_text,
    _clean_ocr_text,
    _detect_heading,
    _detect_repeated_header_footer,
    _diagnose_text,
    extract_single_pdf,
    run_extract_pdf,
)


# ── Fixtures ──

@pytest.fixture
def sample_pdf(tmp_path):
    """Create a small test PDF with PyMuPDF."""
    import fitz
    doc = fitz.open()
    # Page 1
    page = doc.new_page()
    page.insert_text((72, 72), "Test Document Title", fontsize=18)
    page.insert_text((72, 120), "This is the first paragraph of content.", fontsize=12)
    page.insert_text((72, 150), "Second paragraph with more details about the topic.", fontsize=12)
    # Page 2
    page2 = doc.new_page()
    page2.insert_text((72, 72), "CHAPTER TWO", fontsize=16)
    page2.insert_text((72, 120), "Content of chapter two goes here with enough text to be meaningful.", fontsize=12)

    pdf_path = str(tmp_path / "test_doc.pdf")
    doc.save(pdf_path)
    doc.close()
    return pdf_path


@pytest.fixture
def empty_pdf(tmp_path):
    """Create a PDF with no text (simulates scanned)."""
    import fitz
    doc = fitz.open()
    doc.new_page()  # blank page
    pdf_path = str(tmp_path / "empty.pdf")
    doc.save(pdf_path)
    doc.close()
    return pdf_path


# ── Unit tests ──

def test_clean_text_merges_hyphens():
    assert _clean_text("exam-\nple text") == "example text"


def test_clean_text_removes_page_numbers():
    result = _clean_text("Some content\n  42  \nMore content")
    assert "42" not in result
    assert "Some content" in result


def test_clean_text_normalizes_newlines():
    result = _clean_text("A\n\n\n\n\nB")
    assert result == "A\n\nB"


def test_detect_heading_all_caps():
    assert _detect_heading("CHAPTER ONE") > 0


def test_detect_heading_normal_text():
    assert _detect_heading("this is normal text with some content.") == 0


def test_detect_heading_title_case():
    assert _detect_heading("Introduction To Machine Learning") > 0


def test_detect_repeated_header_footer():
    pages = [
        "My Header\nContent page 1\nPage 1",
        "My Header\nContent page 2\nPage 2",
        "My Header\nContent page 3\nPage 3",
        "My Header\nContent page 4\nPage 4",
    ]
    header, footer = _detect_repeated_header_footer(pages)
    assert header == "My Header"


# ── Integration tests ──

def test_extract_single_pdf(sample_pdf, tmp_path):
    output_dir = str(tmp_path / "output")
    result = extract_single_pdf(sample_pdf, output_dir)

    assert result is not None
    assert os.path.isfile(result)

    content = open(result, encoding="utf-8").read()
    assert "source_file: test_doc.pdf" in content
    assert "pages: 2" in content
    assert "first paragraph" in content
    assert "chapter two" in content.lower()


def test_extract_empty_pdf(empty_pdf, tmp_path):
    output_dir = str(tmp_path / "output")
    result = extract_single_pdf(empty_pdf, output_dir)
    # Empty PDF should return None (no extractable text)
    assert result is None


def test_extract_nonexistent_pdf(tmp_path):
    result = extract_single_pdf(str(tmp_path / "nope.pdf"), str(tmp_path / "out"))
    assert result is None


def test_run_extract_pdf_with_dir(sample_pdf, tmp_path):
    output_dir = str(tmp_path / "output")
    input_dir = os.path.dirname(sample_pdf)
    code = run_extract_pdf(input_path=None, input_dir=input_dir, output_dir=output_dir)
    assert code == 0
    assert len(os.listdir(output_dir)) >= 1


def test_run_extract_pdf_no_files(tmp_path):
    code = run_extract_pdf(input_path=None, input_dir=str(tmp_path), output_dir=str(tmp_path / "out"))
    assert code == 1


# ── OCR text sanitization tests ──

class TestCleanOcrText:
    def test_removes_null_bytes(self):
        result = _clean_ocr_text("hello\x00world")
        assert "\x00" not in result
        assert "hello" in result and "world" in result

    def test_removes_control_chars(self):
        result = _clean_ocr_text("hello\x01\x02\x03world")
        assert result == "helloworld"

    def test_preserves_newlines_and_tabs(self):
        result = _clean_ocr_text("line1\nline2\ttab")
        assert "\n" in result

    def test_removes_bom(self):
        result = _clean_ocr_text("\ufeffHello")
        assert result == "Hello"

    def test_normalizes_whitespace(self):
        result = _clean_ocr_text("hello    world")
        assert result == "hello world"

    def test_reduces_blank_lines(self):
        result = _clean_ocr_text("a\n\n\n\n\nb")
        assert result == "a\n\nb"

    def test_handles_vietnamese_text(self):
        text = "Ung dung\x00 AI Agent trong\x01 ban le va thuong mai dien tu"
        result = _clean_ocr_text(text)
        assert "Ung dung" in result
        assert "AI Agent" in result
        assert "\x00" not in result
        assert "\x01" not in result

    def test_empty_string(self):
        assert _clean_ocr_text("") == ""

    def test_strips_trailing_whitespace(self):
        result = _clean_ocr_text("hello   \nworld   ")
        assert result == "hello\nworld"

    def test_nfc_normalizes_vietnamese(self):
        import unicodedata
        decomposed = "a\u0306"  # NFD: a + combining breve = a breve
        result = _clean_ocr_text(decomposed)
        assert result == unicodedata.normalize("NFC", decomposed)

    def test_removes_pua_chars(self):
        result = _clean_ocr_text("hello\ue000\uf8ffworld")
        assert "\ue000" not in result
        assert "\uf8ff" not in result
        assert "helloworld" == result

    def test_removes_non_bmp(self):
        result = _clean_ocr_text("hello\U0001F600world")
        assert "\U0001F600" not in result
        assert "helloworld" == result

    def test_removes_replacement_char(self):
        result = _clean_ocr_text("hello\ufffdworld")
        assert "\ufffd" not in result

    def test_removes_reverse_bom(self):
        result = _clean_ocr_text("\ufffeHello")
        assert "\ufffe" not in result
        assert "Hello" in result

    def test_removes_c1_control_chars(self):
        result = _clean_ocr_text("hello\x7f\x80\x9fworld")
        assert "\x7f" not in result
        assert "\x80" not in result
        assert "\x9f" not in result

    def test_realistic_ocr_garbage(self):
        dirty = (
            "\ufeff"
            "CHUONG 8\x00: UNG DUNG CUA AI AGENT\n"
            "\x01\x02Trong ban le\x03 va thuong mai\n"
            "Chatbot\x7f thong\x80 minh\x9f tu van\n"
            "\ue001Dialogflow\uf000, Amazon Lex\n"
        )
        result = _clean_ocr_text(dirty)
        assert "CHUONG 8" in result
        assert "AI AGENT" in result
        assert "Chatbot" in result
        assert "Dialogflow" in result
        assert "\x00" not in result
        assert "\ufeff" not in result
        assert "\ue001" not in result


# ── Diagnostic tests ──

class TestDiagnoseText:
    def test_detects_null_bytes(self):
        diag = _diagnose_text("hello\x00world")
        assert diag["has_null"] is True

    def test_detects_bom(self):
        diag = _diagnose_text("\ufeffhello")
        assert diag["has_bom"] is True

    def test_detects_control_chars(self):
        diag = _diagnose_text("hello\x01\x02world")
        assert len(diag["control_chars"]) >= 2

    def test_detects_pua_chars(self):
        diag = _diagnose_text("hello\ue000world")
        assert diag["pua_count"] >= 1

    def test_clean_text_has_no_problems(self):
        diag = _diagnose_text("Hello, clean text here.")
        assert diag["has_null"] is False
        assert diag["has_bom"] is False
        assert len(diag["control_chars"]) == 0
        assert diag["non_bmp_count"] == 0
        assert diag["pua_count"] == 0
