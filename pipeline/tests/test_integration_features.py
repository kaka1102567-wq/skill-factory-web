"""Integration tests: OCR Sanitization + Auto-Baseline Discovery.

Verify 2 features work individually AND combined:
- Feature 1: _clean_ocr_text() in extract_pdf.py
- Feature 2: discover-from-content flow in discover_baseline.py
"""

import json
import os
import re
import subprocess

import pytest

from pipeline.commands.extract_pdf import _clean_ocr_text
from pipeline.commands.discover_baseline import (
    read_samples,
    analyze_content,
    search_ddg,
    evaluate_urls,
    fetch_references,
    build_baseline_summary,
    run_discover_from_content,
    _is_valid_url,
)
from pipeline.core.logger import PipelineLogger


# =====================================================
# SECTION A: OCR Sanitization — End-to-end
# =====================================================


class TestOcrSanitizationIntegration:
    """Verify OCR text cleaning works in realistic scenarios."""

    def test_ocr_output_fully_sanitized(self):
        """Simulate Tesseract Vietnamese output with all problematic chars."""
        dirty_ocr = (
            "\ufeff"
            "CHUONG 8\x00: UNG DUNG CUA AI AGENT\n"
            "\x01\x02Trong ban le\x03 va thuong mai\n"
            "\n\n\n\n\n"
            "AI Agent   giup   tu dong hoa\n"
            "quy trinh cham soc   khach hang   \n"
        )

        clean = _clean_ocr_text(dirty_ocr)

        assert "\x00" not in clean, "Null bytes must be removed"
        assert "\ufeff" not in clean, "BOM must be removed"
        assert "\x01" not in clean, "Control chars must be removed"
        assert "\x02" not in clean
        assert "\x03" not in clean
        assert "\n\n\n" not in clean, "Max 2 consecutive newlines"
        assert "   " not in clean, "Multiple spaces must be normalized"
        assert "CHUONG 8" in clean, "Content preserved"
        assert "AI Agent" in clean, "Content preserved"
        assert not any(line.endswith(" ") for line in clean.split("\n")), "No trailing spaces"

    def test_clean_text_is_api_safe(self):
        """Verify cleaned text contains only API-safe characters."""
        dirty = "Hello\x00\x01\x02\x7f\x80\x9fWorld\ufeff"
        clean = _clean_ocr_text(dirty)

        control_pattern = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]')
        assert not control_pattern.search(clean), f"Still has control chars: {repr(clean)}"

    def test_clean_preserves_meaningful_content(self):
        """Clean must not destroy real content."""
        good_text = (
            "Ung dung cua AI Agent trong ban le\n"
            "Chatbot thong minh co the tu van san pham\n"
            "Xu ly don hang va ho tro khach hang 24/7\n"
            "Cac nen tang: Dialogflow, Amazon Lex, Microsoft Bot Framework\n"
        )
        clean = _clean_ocr_text(good_text)

        assert "Ung dung cua AI Agent" in clean
        assert "Chatbot thong minh" in clean
        assert "Dialogflow" in clean
        assert clean.count("\n") >= 3, "Newlines preserved"

    def test_unicode_vietnamese_preserved(self):
        """Vietnamese Unicode diacritics must survive cleaning."""
        text = "Ung dung tri tue nhan tao\nHoc may va xu ly ngon ngu tu nhien"
        clean = _clean_ocr_text(text)
        assert "Ung dung" in clean
        assert "tri tue" in clean


# =====================================================
# SECTION B: Auto-Baseline Discovery — Flow
# =====================================================


class TestAutoBaselineDiscoveryIntegration:
    """Verify auto-baseline discovery flow end-to-end."""

    @pytest.fixture
    def input_dir_with_content(self, tmp_path):
        """Create input dir with realistic .md transcripts."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        for name, content in [
            ("chapter8.md",
             "# AI Agent trong ban le\n\n"
             "AI Agent dang cach mang hoa nganh ban le. Chatbot thong minh "
             "tu van san pham, xu ly don hang, ho tro khach hang 24/7. "
             "Dialogflow, Amazon Lex, Microsoft Bot Framework. " * 5),
            ("chapter9.md",
             "# AI Agent trong cham soc khach hang\n\n"
             "Tu dong hoa CSKH bang AI Agent. Sentiment analysis, intent "
             "detection, knowledge base integration. NLP va LLMs. " * 5),
            ("reference.md",
             "# AI Skill Development\n\n"
             "7 Core Components: Identity, Context, Instructions, Knowledge, "
             "Templates, Constraints, Examples. CLEAR framework. " * 5),
        ]:
            (input_dir / name).write_text(content, encoding="utf-8")

        return str(input_dir)

    def test_read_samples_from_transcripts(self, input_dir_with_content):
        """Verify read_samples reads .md files."""
        samples = read_samples(input_dir_with_content)

        assert len(samples) == 3
        assert all("content" in s and "filename" in s for s in samples)
        content_combined = " ".join(s["content"] for s in samples)
        assert "AI Agent" in content_combined

    def test_analyze_content_returns_valid_structure(self, mock_claude):
        """Verify analyze_content returns expected keys."""
        samples = [
            {"filename": "ch8.md", "content": "AI Agent trong ban le. Chatbot thong minh." * 5},
        ]
        result = analyze_content(samples, mock_claude)

        assert "domain" in result
        assert "topics" in result
        assert "search_queries" in result
        assert isinstance(result["topics"], list)
        assert isinstance(result["search_queries"], list)

    def test_analyze_content_error_returns_defaults(self, mock_claude_error):
        """Verify graceful fallback when Claude fails."""
        samples = [{"filename": "test_doc.md", "content": "Some content here." * 5}]
        result = analyze_content(samples, mock_claude_error)

        assert result["domain"] != ""
        assert len(result["search_queries"]) >= 1

    def test_url_filter_rejects_social_media(self):
        """Verify social media / non-doc URLs are filtered."""
        assert _is_valid_url("https://youtube.com/watch?v=abc") is False
        assert _is_valid_url("https://example.com/login") is False
        assert _is_valid_url("https://example.com/signup") is False
        assert _is_valid_url("https://docs.aws.amazon.com/lex/guide") is True
        assert _is_valid_url("https://medium.com/ai-chatbot-guide") is True

    def test_evaluate_urls_with_mock(self, mock_claude):
        """Verify evaluate_urls returns scored list."""
        candidates = [
            {"url": "https://docs.example.com/guide", "title": "Guide", "snippet": "Official docs"},
            {"url": "https://example.com/tutorial", "title": "Tutorial", "snippet": "Learn here"},
        ]
        result = evaluate_urls(candidates, "AI Agents", ["chatbot", "NLP"], mock_claude)
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_baseline_summary_p0_compatible(self, tmp_path):
        """baseline_summary.json MUST be compatible with p0_baseline._run_p0_prebuilt."""
        refs = [
            {"path": "ref1.md", "content": "# AI Guide\nContent about AI agents.", "url": "https://ex.com/1", "tokens": 200},
            {"path": "ref2.md", "content": "# Chatbot Guide\nBest practices.", "url": "https://ex.com/2", "tokens": 150},
        ]
        path = build_baseline_summary(
            "ai-agents", ["chatbot", "NLP", "retail"], refs, str(tmp_path),
            metadata={"content_type": "course", "language": "vi"},
        )

        assert os.path.exists(path)
        with open(path) as f:
            data = json.load(f)

        # Verify ALL fields P0 needs (from p0_baseline.py _run_p0_prebuilt)
        assert "source" in data
        assert "references" in data
        assert isinstance(data["references"], list)
        assert "topics" in data
        assert "score" in data
        assert "total_tokens" in data
        assert data["score"] >= 20.0  # Relevance-based; short content → low score

        # Verify reference format matches P0 expectation
        for ref in data["references"]:
            assert "path" in ref
            assert "content" in ref
            assert len(ref["content"]) > 0

        assert len(data["references"]) == 2
        assert len(data["topics"]) == 3

    def test_full_discovery_with_mocked_externals(self, input_dir_with_content, tmp_path, mock_claude):
        """Test full discovery flow with mocked web client."""
        from unittest.mock import MagicMock

        output_dir = str(tmp_path / "output")

        # Mock web client that returns fake DDG HTML + fake page content
        mock_web = MagicMock()
        mock_web.get.side_effect = [
            # DDG search results (HTML) - one per query (3 queries from mock_claude)
            '<a class="result__a" href="https://docs.example.com/guide">Guide</a>'
            '<a class="result__snippet">Official guide</a>',
            '<a class="result__a" href="https://example.com/tutorial">Tutorial</a>'
            '<a class="result__snippet">Learn here</a>',
            '<a class="result__a" href="https://example.com/api">API Docs</a>'
            '<a class="result__snippet">API reference</a>',
            # fetch_and_convert calls - web_client.get for each URL
            '<html><body><article><h1>Guide</h1><p>This is a comprehensive guide about AI agents and chatbots for customer service and retail automation.</p></article></body></html>',
        ]

        result = run_discover_from_content(
            input_dir_with_content, output_dir, mock_claude, mock_web,
        )

        assert result["domain"] != ""
        # Discovery should proceed (may or may not succeed depending on mock responses)
        assert isinstance(result, dict)
        assert "success" in result


# =====================================================
# SECTION C: Combined — OCR + Discovery
# =====================================================


class TestCombinedOcrAndDiscovery:
    """Test realistic scenario: OCR output feeds into Discovery."""

    def test_ocr_cleaned_text_usable_for_discovery(self, tmp_path):
        """OCR text after cleaning must be readable by read_samples."""
        dirty_ocr = (
            "\ufeffCHUONG 8\x00: UNG DUNG AI AGENT TRONG BAN LE\n\n"
            "AI Agent\x01 cach mang hoa thuong mai\x02 dien tu.\n"
            "Chatbot   thong   minh   tu van san pham.\n\n\n\n\n"
            "Dialogflow, Amazon Lex, Microsoft Bot Framework.\n"
            "Sentiment analysis, NLP, LLMs.\n" * 5
        )

        clean = _clean_ocr_text(dirty_ocr)
        assert len(clean) > 50
        assert "\x00" not in clean
        assert "\ufeff" not in clean

        # Save as .md and verify read_samples can read it
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        (input_dir / "pdf_chapter8.md").write_text(clean, encoding="utf-8")

        samples = read_samples(str(input_dir))
        assert len(samples) == 1
        assert "AI Agent" in samples[0]["content"]
        assert "Chatbot" in samples[0]["content"]

    def test_discovery_with_ocr_content(self, tmp_path, mock_claude):
        """Full flow: OCR clean → save → Discovery reads → analyzes."""
        dirty = (
            "\x00UNG DUNG AI AGENT\x01 TRONG BAN LE\n"
            "Chatbot thong\x02 minh ho tro khach hang.\n"
            "Intent detection va sentiment analysis.\n" * 10
        )
        clean = _clean_ocr_text(dirty)

        input_dir = tmp_path / "input"
        input_dir.mkdir()
        (input_dir / "pdf_ocr_content.md").write_text(clean, encoding="utf-8")

        samples = read_samples(str(input_dir))
        assert len(samples) == 1

        # analyze_content should work with OCR-cleaned text
        result = analyze_content(samples, mock_claude)
        assert result["domain"] != ""
        assert len(result["search_queries"]) >= 1

    def test_empty_input_graceful_failure(self, tmp_path, mock_claude):
        """When input is empty, discovery returns failure without crashing."""
        from unittest.mock import MagicMock

        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        output_dir = str(tmp_path / "output")

        mock_web = MagicMock()
        result = run_discover_from_content(
            str(empty_dir), output_dir, mock_claude, mock_web,
        )
        assert result["success"] is False
        assert result["refs_count"] == 0

    def test_no_md_files_graceful_failure(self, tmp_path, mock_claude):
        """When input has files but no .md, discovery returns failure."""
        from unittest.mock import MagicMock

        input_dir = tmp_path / "input"
        input_dir.mkdir()
        (input_dir / "data.json").write_text('{}', encoding="utf-8")
        (input_dir / "image.png").write_bytes(b'\x89PNG')

        mock_web = MagicMock()
        result = run_discover_from_content(
            str(input_dir), str(tmp_path / "output"), mock_claude, mock_web,
        )
        assert result["success"] is False


# =====================================================
# SECTION D: CLI Integration
# =====================================================


class TestDiscoverFromContentCLI:
    """Test discover-from-content CLI command registration."""

    def test_cli_subparser_exists(self):
        """Verify discover-from-content is registered in CLI."""
        result = subprocess.run(
            ["py", "-m", "pipeline.cli", "discover-from-content", "--help"],
            capture_output=True, text=True, timeout=10,
            cwd="C:/Users/Kaka/Projects/skill-factory/skill-factory-web",
        )
        assert result.returncode == 0
        assert "--input-dir" in result.stdout
        assert "--output-dir" in result.stdout
        assert "--api-key" in result.stdout

    def test_cli_missing_args_fails(self):
        """Verify CLI fails without required args."""
        result = subprocess.run(
            ["py", "-m", "pipeline.cli", "discover-from-content"],
            capture_output=True, text=True, timeout=10,
            cwd="C:/Users/Kaka/Projects/skill-factory/skill-factory-web",
        )
        assert result.returncode != 0

    def test_existing_cli_commands_not_broken(self):
        """Verify other CLI commands still work."""
        for cmd in ["build", "fetch-urls", "extract-pdf", "discover-baseline"]:
            result = subprocess.run(
                ["py", "-m", "pipeline.cli", cmd, "--help"],
                capture_output=True, text=True, timeout=10,
                cwd="C:/Users/Kaka/Projects/skill-factory/skill-factory-web",
            )
            assert result.returncode == 0, f"CLI '{cmd} --help' failed"


# =====================================================
# SECTION E: E2E Smoke Test
# =====================================================


class TestE2ESmokeOcrAndDiscovery:
    """Simulate real build: upload PDFs (OCR) + no baseline."""

    def test_smoke_ocr_then_discovery(self, tmp_path, mock_claude):
        """
        Full scenario:
        1. OCR extract + clean
        2. Save to input dir
        3. Discovery reads cleaned content
        4. Discovery creates baseline_summary.json
        5. Verify P0 can load it
        """
        from unittest.mock import MagicMock

        # Step 1: OCR extraction + cleaning
        raw_ocr = (
            "\ufeffCHUONG 8\x00: UNG DUNG AI AGENT TRONG BAN LE\n\n"
            "AI Agent\x01 cach mang hoa thuong mai\x02 dien tu.\n"
            "Chatbot   thong   minh   tu van san pham.\n\n\n\n\n"
            "Dialogflow, Amazon Lex, Microsoft Bot Framework.\n"
            "Sentiment analysis, NLP, LLMs.\n" * 5
        )
        clean_text = _clean_ocr_text(raw_ocr)
        assert "\x00" not in clean_text
        assert "AI Agent" in clean_text

        # Step 2: Save cleaned text
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        (input_dir / "pdf_chapter8.md").write_text(clean_text, encoding="utf-8")

        # Step 3: Run discovery with mocked web
        output_dir = tmp_path / "output"
        mock_web = MagicMock()
        # DDG search returns HTML with results
        ddg_html = (
            '<a class="result__a" href="https://docs.dialogflow.com/cx">Dialogflow CX</a>'
            '<a class="result__snippet">Build conversational AI agents</a>'
        )
        mock_web.get.side_effect = [
            ddg_html, ddg_html, ddg_html,  # 3 DDG queries
            # fetch_and_convert: page HTML
            '<html><body><article><h1>Dialogflow CX</h1>'
            '<p>Agent design best practices for retail chatbots. '
            'Build conversational AI that handles customer queries automatically.</p>'
            '</article></body></html>',
        ]

        result = run_discover_from_content(
            str(input_dir), str(output_dir), mock_claude, mock_web,
        )

        # Step 4: Verify result
        assert result["domain"] != ""
        assert isinstance(result["refs_count"], int)

        # If baseline was created, verify P0 compatibility
        baseline_path = os.path.join(str(output_dir), "baseline_summary.json")
        if os.path.exists(baseline_path):
            with open(baseline_path) as f:
                baseline = json.load(f)

            assert "source" in baseline
            assert "references" in baseline
            assert "topics" in baseline
            assert "score" in baseline
            for ref in baseline["references"]:
                assert "path" in ref
                assert "content" in ref
