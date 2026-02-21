"""Tests for discover-from-content: content-based baseline auto-discovery."""

import json
import os

import pytest

from pipeline.commands.discover_baseline import (
    read_samples,
    analyze_content,
    search_ddg,
    evaluate_urls,
    fetch_references,
    build_baseline_summary,
    run_discover_from_content,
    _extract_ddg_url,
    _is_valid_url,
    _parse_json,
)
from pipeline.core.logger import PipelineLogger


# ===== Step 1: Read Samples =====


class TestReadSamples:
    def test_reads_md_files(self, tmp_path):
        (tmp_path / "doc1.md").write_text("# Title\nSome content here about testing and various topics that span multiple sentences for proper length.", encoding="utf-8")
        (tmp_path / "doc2.md").write_text("# Another\nMore content for analysis covering different subjects with enough text to pass the threshold.", encoding="utf-8")
        samples = read_samples(str(tmp_path))
        assert len(samples) == 2
        assert samples[0]["filename"] == "doc1.md"

    def test_ignores_non_md_files(self, tmp_path):
        (tmp_path / "doc.md").write_text("# Test\nValid content that is long enough to pass the minimum length threshold for samples.", encoding="utf-8")
        (tmp_path / "data.json").write_text('{"key": "value"}', encoding="utf-8")
        (tmp_path / "notes.txt").write_text("Plain text file", encoding="utf-8")
        samples = read_samples(str(tmp_path))
        assert len(samples) == 1
        assert samples[0]["filename"] == "doc.md"

    def test_strips_yaml_frontmatter(self, tmp_path):
        content = "---\ntitle: Test\ndate: 2024-01-01\n---\n# Actual Content\nBody text here with enough content to pass minimum length threshold for sample reading."
        (tmp_path / "doc.md").write_text(content, encoding="utf-8")
        samples = read_samples(str(tmp_path))
        assert len(samples) == 1
        assert "---" not in samples[0]["content"][:10]
        assert "Actual Content" in samples[0]["content"]

    def test_empty_dir_returns_empty(self, tmp_path):
        samples = read_samples(str(tmp_path))
        assert samples == []

    def test_nonexistent_dir_returns_empty(self):
        samples = read_samples("/nonexistent/path/abc123")
        assert samples == []

    def test_skips_short_files(self, tmp_path):
        (tmp_path / "short.md").write_text("Hi", encoding="utf-8")
        (tmp_path / "long.md").write_text("# Title\n" + "Content. " * 20, encoding="utf-8")
        samples = read_samples(str(tmp_path))
        assert len(samples) == 1
        assert samples[0]["filename"] == "long.md"

    def test_truncates_long_files(self, tmp_path):
        long_text = "# Title\n" + "Word " * 2000
        (tmp_path / "long.md").write_text(long_text, encoding="utf-8")
        samples = read_samples(str(tmp_path))
        assert len(samples) == 1
        assert len(samples[0]["content"]) <= 3200  # MAX_CHARS_PER_FILE + truncation marker

    def test_max_sample_files_limit(self, tmp_path):
        for i in range(10):
            (tmp_path / f"doc_{i:02d}.md").write_text(f"# Document {i}\nThis is content number {i} for testing with enough text to pass the minimum length threshold.", encoding="utf-8")
        samples = read_samples(str(tmp_path))
        assert len(samples) == 5  # MAX_SAMPLE_FILES


# ===== Step 2: Analyze Content =====


class TestAnalyzeContent:
    def test_returns_domain(self, mock_claude):
        samples = [{"filename": "test.md", "content": "# Test Content\nSome text."}]
        result = analyze_content(samples, mock_claude)
        assert result["domain"] == "Facebook Ads"

    def test_returns_topics(self, mock_claude):
        samples = [{"filename": "test.md", "content": "# Test\nContent."}]
        result = analyze_content(samples, mock_claude)
        assert len(result["topics"]) >= 1
        assert "campaign management" in result["topics"]

    def test_returns_search_queries(self, mock_claude):
        samples = [{"filename": "test.md", "content": "# Test\nContent."}]
        result = analyze_content(samples, mock_claude)
        assert len(result["search_queries"]) >= 1

    def test_handles_error_gracefully(self, mock_claude_error):
        samples = [{"filename": "test_doc.md", "content": "# Test\nContent."}]
        result = analyze_content(samples, mock_claude_error)
        assert result["domain"] != ""
        assert isinstance(result["search_queries"], list)
        assert len(result["search_queries"]) >= 1

    def test_uses_light_model(self, mock_claude):
        samples = [{"filename": "test.md", "content": "# Test\nContent."}]
        analyze_content(samples, mock_claude)
        assert mock_claude.model_usage["light"] >= 1


# ===== Step 3: DuckDuckGo Search =====


class TestSearchDDG:
    def test_extract_ddg_url_direct(self):
        assert _extract_ddg_url("https://example.com") == "https://example.com"

    def test_extract_ddg_url_redirect(self):
        href = "https://duckduckgo.com/y.js?uddg=https%3A%2F%2Fexample.com%2Fdocs"
        result = _extract_ddg_url(href)
        assert result == "https://example.com/docs"

    def test_extract_ddg_url_protocol_relative(self):
        assert _extract_ddg_url("//example.com/page").startswith("https:")

    def test_extract_ddg_url_empty_for_invalid(self):
        assert _extract_ddg_url("#anchor") == ""

    def test_is_valid_url_accepts_docs(self):
        assert _is_valid_url("https://docs.example.com/guide") is True

    def test_is_valid_url_rejects_login(self):
        assert _is_valid_url("https://example.com/login") is False

    def test_is_valid_url_rejects_signup(self):
        assert _is_valid_url("https://example.com/signup") is False

    def test_is_valid_url_rejects_youtube_watch(self):
        assert _is_valid_url("https://youtube.com/watch?v=abc") is False


# ===== Step 4: Evaluate URLs =====


class TestEvaluateURLs:
    def test_returns_scored_list(self, mock_claude):
        candidates = [
            {"url": "https://docs.example.com/guide", "title": "Guide", "snippet": "Official"},
        ]
        result = evaluate_urls(candidates, "Test Domain", ["topic1"], mock_claude)
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_empty_candidates_returns_empty(self, mock_claude):
        result = evaluate_urls([], "Test", [], mock_claude)
        assert result == []

    def test_handles_error_with_fallback(self, mock_claude_error):
        candidates = [
            {"url": "https://example.com/doc1", "title": "Doc", "snippet": "..."},
            {"url": "https://example.com/doc2", "title": "Doc2", "snippet": "..."},
        ]
        result = evaluate_urls(candidates, "Test", ["topic"], mock_claude_error)
        assert isinstance(result, list)
        assert len(result) >= 1  # Should fallback to unsorted candidates


# ===== Step 5: Build Baseline Summary =====


class TestBuildBaselineSummary:
    def test_creates_json_file(self, tmp_path):
        refs = [
            {"path": "ref1.md", "content": "Content 1", "url": "https://example.com", "tokens": 100},
        ]
        path = build_baseline_summary("Test Domain", ["topic1"], refs, str(tmp_path))
        assert os.path.exists(path)
        assert path.endswith("baseline_summary.json")

    def test_json_has_required_keys(self, tmp_path):
        refs = [
            {"path": "ref1.md", "content": "Content 1", "url": "https://ex.com", "tokens": 100},
        ]
        path = build_baseline_summary("Test", ["t1"], refs, str(tmp_path))
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        required = {"source", "domain", "skill_md", "references", "topics", "total_tokens", "score"}
        assert required.issubset(data.keys())
        assert data["source"] == "auto-discovery-content"
        assert data["domain"] == "Test"

    def test_score_range(self, tmp_path):
        # 0 refs => 30.0 (empty baseline), many short refs => low score
        refs_0 = build_baseline_summary("T", [], [], str(tmp_path / "a"))
        with open(refs_0) as f:
            assert json.load(f)["score"] == 30.0

        # 20 refs with very short content → low depth score
        refs_many = [{"path": f"r{i}.md", "content": "C", "url": "u", "tokens": 10} for i in range(20)]
        refs_20 = build_baseline_summary("T", [], refs_many, str(tmp_path / "b"))
        with open(refs_20) as f:
            score = json.load(f)["score"]
            # Short content + no topics → low score, but count bonus helps
            assert 20.0 <= score <= 95.0

    def test_references_have_path_and_content(self, tmp_path):
        refs = [
            {"path": "ref1.md", "content": "Some content", "url": "https://ex.com", "tokens": 50},
            {"path": "ref2.md", "content": "More content", "url": "https://ex.com/2", "tokens": 60},
        ]
        path = build_baseline_summary("Test", ["t1"], refs, str(tmp_path))
        with open(path) as f:
            data = json.load(f)
        for ref in data["references"]:
            assert "path" in ref
            assert "content" in ref
            assert len(ref["content"]) > 0

    def test_metadata_included(self, tmp_path):
        meta = {"content_type": "course", "language": "vi"}
        path = build_baseline_summary("T", [], [], str(tmp_path), metadata=meta)
        with open(path) as f:
            data = json.load(f)
        assert data["discovery_metadata"]["content_type"] == "course"
        assert data["discovery_metadata"]["language"] == "vi"

    def test_p0_prebuilt_compatibility(self, tmp_path):
        """baseline_summary.json should work with p0_baseline._run_p0_prebuilt."""
        refs = [{"path": "r.md", "content": "Content", "url": "u", "tokens": 100}]
        path = build_baseline_summary("Test", ["topic1"], refs, str(tmp_path))

        # Simulate what p0_baseline._run_p0_prebuilt does
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        refs_count = len(data.get("references", []))
        topics_count = len(data.get("topics", []))
        score = data.get("score", 85.0)
        total_tokens = data.get("total_tokens", 0)

        assert refs_count == 1
        assert topics_count == 1
        assert score >= 20.0  # Relevance-based; short content = low score
        assert total_tokens >= 0


# ===== JSON Parsing =====


class TestParseJSON:
    def test_plain_json(self):
        result = _parse_json('{"key": "value"}')
        assert result["key"] == "value"

    def test_json_with_code_fence(self):
        result = _parse_json('```json\n{"key": "value"}\n```')
        assert result["key"] == "value"

    def test_json_array(self):
        result = _parse_json('[{"a": 1}]')
        assert isinstance(result, list)

    def test_extracts_json_from_mixed_content(self):
        text = 'Some text before\n{"key": "value"}\nSome text after'
        result = _parse_json(text)
        assert result["key"] == "value"


# ===== Orchestrator =====


class TestOrchestrator:
    def test_empty_input_returns_failure(self, mock_claude, tmp_path):
        logger = PipelineLogger("test")
        from pipeline.clients.web_client import WebClient
        web = WebClient(rpm=60, timeout=5)
        try:
            result = run_discover_from_content(
                str(tmp_path / "empty"), str(tmp_path / "out"),
                mock_claude, web, logger,
            )
        finally:
            web.close()
        assert result["success"] is False
        assert result["refs_count"] == 0

    def test_no_md_files_returns_failure(self, mock_claude, tmp_path):
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        (input_dir / "data.json").write_text('{}', encoding="utf-8")

        logger = PipelineLogger("test")
        from pipeline.clients.web_client import WebClient
        web = WebClient(rpm=60, timeout=5)
        try:
            result = run_discover_from_content(
                str(input_dir), str(tmp_path / "out"),
                mock_claude, web, logger,
            )
        finally:
            web.close()
        assert result["success"] is False


# ===== CLI Integration =====


class TestCLIIntegration:
    def test_discover_from_content_help(self):
        """CLI discover-from-content subparser should be registered."""
        import subprocess
        result = subprocess.run(
            ["py", "-m", "pipeline.cli", "discover-from-content", "--help"],
            capture_output=True, text=True, timeout=10,
            cwd="C:/Users/Kaka/Projects/skill-factory/skill-factory-web",
        )
        assert result.returncode == 0
        assert "--input-dir" in result.stdout
        assert "--output-dir" in result.stdout
        assert "--api-key" in result.stdout

    def test_existing_commands_still_work(self):
        """Other CLI commands should not be broken."""
        import subprocess
        for cmd in ["build", "fetch-urls", "extract-pdf", "discover-baseline"]:
            result = subprocess.run(
                ["py", "-m", "pipeline.cli", cmd, "--help"],
                capture_output=True, text=True, timeout=10,
                cwd="C:/Users/Kaka/Projects/skill-factory/skill-factory-web",
            )
            assert result.returncode == 0, f"CLI {cmd} --help failed"
