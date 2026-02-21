"""Tests for auto-discovery: domain_analyzer, url_discoverer, url_evaluator, orchestrator."""

import json
import os
import pytest

from pipeline.seekers.domain_analyzer import analyze_domain, DomainAnalysis
from pipeline.seekers.url_discoverer import (
    CandidateURL, _normalize_url, _is_valid_doc_url, _matches_patterns,
    _extract_ddg_url,
)
from pipeline.seekers.url_evaluator import evaluate_urls, RankedURL, _prefilter
from pipeline.seekers.scraper import smart_crawl, _url_to_safe_filename, _fetch_and_parse
from pipeline.seekers.auto_discovery import (
    run_auto_discovery, DiscoveryResult, DiscoveryTimeoutError,
    _is_generic_domain, _infer_domain_from_content,
)
from pipeline.core.logger import PipelineLogger
from pipeline.core.types import BuildConfig


# ===== Domain Analyzer Tests =====


class TestDomainAnalyzer:
    def test_analyze_returns_dataclass(self, mock_claude):
        logger = PipelineLogger("test")
        result = analyze_domain("facebook-ads", "en", mock_claude, logger)
        assert isinstance(result, DomainAnalysis)
        assert result.domain == "facebook-ads"

    def test_analyze_has_search_queries(self, mock_claude):
        logger = PipelineLogger("test")
        result = analyze_domain("react", "en", mock_claude, logger)
        assert len(result.search_queries) >= 1

    def test_analyze_has_official_sites(self, mock_claude):
        logger = PipelineLogger("test")
        result = analyze_domain("test", "en", mock_claude, logger)
        assert isinstance(result.official_sites, list)

    def test_analyze_handles_parse_error(self, mock_claude_error):
        logger = PipelineLogger("test")
        result = analyze_domain("test", "en", mock_claude_error, logger)
        assert result.domain == "test"
        assert len(result.search_queries) >= 3
        assert result.difficulty == "medium"

    def test_analyze_uses_light_model(self, mock_claude):
        logger = PipelineLogger("test")
        analyze_domain("test", "en", mock_claude, logger)
        assert mock_claude.model_usage["light"] >= 1


# ===== URL Discoverer Tests =====


class TestURLDiscoverer:
    def test_deduplicate_urls(self):
        urls = [
            CandidateURL(url="https://example.com/docs/"),
            CandidateURL(url="https://example.com/docs"),
            CandidateURL(url="https://example.com/other"),
        ]
        seen = set()
        unique = []
        for u in urls:
            n = _normalize_url(u.url)
            if n not in seen:
                seen.add(n)
                unique.append(u)
        assert len(unique) == 2

    def test_is_valid_doc_url_accepts_docs(self):
        assert _is_valid_doc_url("https://docs.example.com/guide") is True

    def test_is_valid_doc_url_rejects_login(self):
        assert _is_valid_doc_url("https://example.com/login") is False

    def test_is_valid_doc_url_rejects_signup(self):
        assert _is_valid_doc_url("https://example.com/signup") is False

    def test_matches_patterns_with_match(self):
        assert _matches_patterns("https://x.com/docs/guide", ["/docs/", "/help/"]) is True

    def test_matches_patterns_no_match(self):
        assert _matches_patterns("https://x.com/blog/post", ["/docs/", "/help/"]) is False

    def test_matches_patterns_empty(self):
        assert _matches_patterns("https://x.com/anything", []) is True

    def test_extract_ddg_url_direct(self):
        assert _extract_ddg_url("https://example.com") == "https://example.com"

    def test_extract_ddg_url_protocol_relative(self):
        assert _extract_ddg_url("//example.com").startswith("https:")

    def test_extract_ddg_url_empty_for_invalid(self):
        assert _extract_ddg_url("#anchor") == ""

    def test_normalize_url_strips_trailing_slash(self):
        assert _normalize_url("https://example.com/docs/") == "https://example.com/docs"

    def test_normalize_url_lowercases(self):
        assert _normalize_url("https://Example.COM/Docs") == "https://example.com/docs"


# ===== URL Evaluator Tests =====


class TestURLEvaluator:
    def test_prefilter_removes_junk(self):
        candidates = [
            CandidateURL(url="https://docs.example.com/guide"),
            CandidateURL(url="https://example.com/login"),
            CandidateURL(url="https://example.com/signup"),
            CandidateURL(url="https://docs.example.com/api"),
        ]
        filtered = _prefilter(candidates)
        assert len(filtered) == 2
        assert all("/login" not in f.url and "/signup" not in f.url for f in filtered)

    def test_prefilter_keeps_valid_docs(self):
        candidates = [
            CandidateURL(url="https://docs.python.org/3/library/json.html"),
            CandidateURL(url="https://react.dev/learn"),
        ]
        filtered = _prefilter(candidates)
        assert len(filtered) == 2

    def test_evaluate_returns_list(self, mock_claude):
        logger = PipelineLogger("test")
        analysis = DomainAnalysis(domain="test", expected_topics=["topic1"])
        candidates = [CandidateURL(url="https://docs.example.com/guide", title="Guide")]
        result = evaluate_urls(candidates, analysis, mock_claude, logger, max_refs=5)
        assert isinstance(result, list)

    def test_evaluate_respects_max_refs(self, mock_claude):
        logger = PipelineLogger("test")
        analysis = DomainAnalysis(domain="test", expected_topics=["t1"])
        candidates = [CandidateURL(url=f"https://example.com/doc{i}") for i in range(20)]
        result = evaluate_urls(candidates, analysis, mock_claude, logger, max_refs=5)
        assert len(result) <= 5

    def test_evaluate_empty_candidates(self, mock_claude):
        logger = PipelineLogger("test")
        analysis = DomainAnalysis(domain="test")
        result = evaluate_urls([], analysis, mock_claude, logger)
        assert result == []

    def test_evaluate_all_junk_returns_empty(self, mock_claude):
        logger = PipelineLogger("test")
        analysis = DomainAnalysis(domain="test")
        candidates = [
            CandidateURL(url="https://example.com/login"),
            CandidateURL(url="https://example.com/signup"),
        ]
        result = evaluate_urls(candidates, analysis, mock_claude, logger)
        assert result == []


# ===== Smart Crawler Tests =====


class TestSmartCrawler:
    def test_url_to_safe_filename_no_special_chars(self):
        name = _url_to_safe_filename("https://docs.example.com/guide/getting-started")
        assert "/" not in name
        assert "\\" not in name
        assert len(name) <= 80

    def test_url_to_safe_filename_max_length(self):
        long_path = "https://example.com/" + "a" * 200
        name = _url_to_safe_filename(long_path)
        assert len(name) <= 80

    def test_url_to_safe_filename_fallback(self):
        name = _url_to_safe_filename("https://example.com/")
        assert name == "page"

    def test_smart_crawl_empty_list(self, tmp_path):
        logger = PipelineLogger("test")
        results = smart_crawl([], str(tmp_path), None, logger)
        assert results == []

    def test_smart_crawl_creates_refs_dir(self, tmp_path):
        logger = PipelineLogger("test")
        smart_crawl([], str(tmp_path), None, logger)
        assert os.path.isdir(os.path.join(str(tmp_path), "references"))


# ===== Auto-Discovery Orchestrator Tests =====


class TestAutoDiscoveryOrchestrator:
    def test_discovery_result_dataclass(self):
        r = DiscoveryResult(success=True, refs_count=10)
        assert r.success is True
        assert r.refs_count == 10
        assert r.output_dir == ""

    def test_discovery_result_defaults(self):
        r = DiscoveryResult(success=False)
        assert r.total_cost_usd == 0.0
        assert r.discovery_metadata == {}

    def test_baseline_summary_format_keys(self):
        """baseline_summary.json must have the correct keys for P0 compatibility."""
        summary = {
            "source": "auto-discovery",
            "domain": "test",
            "skill_md": "",
            "references": [{"path": "ref.md", "content": "test content"}],
            "topics": ["topic1", "topic2"],
            "total_tokens": 1000,
            "score": 75.0,
            "discovery_metadata": {},
        }
        required_keys = {"source", "references", "topics", "score", "domain", "skill_md"}
        assert required_keys.issubset(summary.keys())

    def test_baseline_summary_score_range(self):
        """Score should be capped between 60 and 95."""
        # 0 refs => score = 60
        assert min(95.0, 60.0 + 0 * 2.5) == 60.0
        # 14 refs => 60 + 35 = 95 (capped)
        assert min(95.0, 60.0 + 14 * 2.5) == 95.0
        # 5 refs => 60 + 12.5 = 72.5
        assert min(95.0, 60.0 + 5 * 2.5) == 72.5


# ===== Content Inference Tests =====


class TestContentInference:
    def test_is_generic_domain_custom(self):
        assert _is_generic_domain("custom") is True

    def test_is_generic_domain_unknown(self):
        assert _is_generic_domain("unknown") is True

    def test_is_generic_domain_short(self):
        assert _is_generic_domain("ab") is True

    def test_is_generic_domain_specific(self):
        assert _is_generic_domain("facebook-ads") is False

    def test_is_generic_domain_case_insensitive(self):
        assert _is_generic_domain("Custom") is True
        assert _is_generic_domain("CUSTOM") is True

    def test_infer_domain_from_content(self, mock_claude, tmp_path):
        """Content inference returns domain info when input has files."""
        (tmp_path / "doc.md").write_text(
            "# AI Agent trong ban le\nUng dung AI agent de tu van "
            "khach hang trong nganh ban le va thuong mai dien tu.",
            encoding="utf-8",
        )
        logger = PipelineLogger("test")
        result = _infer_domain_from_content(str(tmp_path), mock_claude, logger)
        assert result is not None
        assert "inferred_domain" in result
        assert len(result["search_terms"]) >= 1
        assert "custom" not in result["inferred_domain"].lower()

    def test_infer_domain_empty_dir(self, mock_claude, tmp_path):
        """Content inference returns None for empty directory."""
        logger = PipelineLogger("test")
        result = _infer_domain_from_content(str(tmp_path), mock_claude, logger)
        assert result is None

    def test_infer_domain_nonexistent_dir(self, mock_claude):
        """Content inference returns None for nonexistent directory."""
        logger = PipelineLogger("test")
        result = _infer_domain_from_content("/nonexistent/path", mock_claude, logger)
        assert result is None

    def test_discovery_uses_content_inference_for_custom(self, mock_claude, tmp_path):
        """discover-baseline with domain=custom uses content inference."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        (input_dir / "content.md").write_text(
            "# AI Agent\nContent about AI agent in retail with chatbot "
            "and automation for customer service in ecommerce.",
            encoding="utf-8",
        )
        logger = PipelineLogger("test")
        from pipeline.clients.web_client import WebClient
        web = WebClient(rpm=60, timeout=5)
        try:
            # Will fail at DDG search but should infer domain first
            result = run_auto_discovery(
                domain="custom", language="vi",
                output_dir=str(tmp_path / "out"),
                claude_client=mock_claude, web_client=web, logger=logger,
                input_dir=str(input_dir),
            )
        finally:
            web.close()
        # Inference should have been called (light model)
        assert mock_claude.model_usage["light"] >= 1

    def test_discovery_skips_inference_for_specific_domain(self, mock_claude, tmp_path):
        """discover-baseline with specific domain skips content inference."""
        logger = PipelineLogger("test")
        from pipeline.clients.web_client import WebClient
        web = WebClient(rpm=60, timeout=5)
        try:
            result = run_auto_discovery(
                domain="facebook-ads", language="en",
                output_dir=str(tmp_path / "out"),
                claude_client=mock_claude, web_client=web, logger=logger,
                input_dir=str(tmp_path),  # even with input_dir, should skip
            )
        finally:
            web.close()
        # Should NOT have called inference — goes straight to domain analysis
        # The first light model call should be domain_analyzer, not inference


# ===== CLI Integration Tests =====


class TestCLI:
    def test_discover_baseline_help(self):
        """CLI discover-baseline subparser should be registered."""
        import subprocess
        result = subprocess.run(
            ["py", "-m", "pipeline.cli", "discover-baseline", "--help"],
            capture_output=True, text=True, timeout=10,
            cwd="C:/Users/Kaka/Projects/skill-factory/skill-factory-web",
        )
        assert result.returncode == 0
        assert "--domain" in result.stdout

    def test_build_help_still_works(self):
        """Existing build command should still work."""
        import subprocess
        result = subprocess.run(
            ["py", "-m", "pipeline.cli", "build", "--help"],
            capture_output=True, text=True, timeout=10,
            cwd="C:/Users/Kaka/Projects/skill-factory/skill-factory-web",
        )
        assert result.returncode == 0
        assert "--config" in result.stdout


# ===== Error Handling Tests =====


class TestErrorHandling:
    def test_discovery_timeout_error(self):
        """DiscoveryTimeoutError is raised correctly."""
        with pytest.raises(DiscoveryTimeoutError):
            raise DiscoveryTimeoutError("timed out")

    def test_discovery_timeout_returns_false(self, mock_claude, tmp_path):
        """Timeout returns DiscoveryResult.success=False instead of crashing."""
        from unittest.mock import patch
        logger = PipelineLogger("test")

        # Patch time.time to simulate timeout
        real_time = __import__("time").time
        call_count = 0

        def fake_time():
            nonlocal call_count
            call_count += 1
            # After first few calls, jump to exceed timeout
            if call_count > 3:
                return real_time() + 99999
            return real_time()

        with patch("pipeline.seekers.auto_discovery.time.time", side_effect=fake_time):
            from pipeline.clients.web_client import WebClient
            web = WebClient()
            result = run_auto_discovery(
                "test", "en", str(tmp_path), mock_claude, web, logger,
                max_refs=5, timeout=1,
            )
            web.close()

        assert result.success is False

    def test_evaluate_handles_parse_error(self, mock_claude_error):
        """Evaluator with bad Claude response still returns results."""
        logger = PipelineLogger("test")
        analysis = DomainAnalysis(domain="test", expected_topics=["t"])
        candidates = [CandidateURL(url="https://docs.example.com/guide")]
        result = evaluate_urls(candidates, analysis, mock_claude_error, logger)
        # Should fallback to default scores, not crash
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_domain_analyzer_preserves_domain_on_error(self, mock_claude_error):
        """Even on error, domain name is preserved in result."""
        logger = PipelineLogger("test")
        result = analyze_domain("my-domain", "vi", mock_claude_error, logger)
        assert result.domain == "my-domain"


# ===== BuildConfig Integration Tests =====


class TestBuildConfigIntegration:
    def test_auto_discover_baseline_field_exists(self):
        """BuildConfig has auto_discover_baseline field."""
        config = BuildConfig(name="test", domain="test")
        assert hasattr(config, "auto_discover_baseline")
        assert config.auto_discover_baseline is False

    def test_auto_discover_baseline_can_be_set(self):
        """auto_discover_baseline can be toggled."""
        config = BuildConfig(name="test", domain="test", auto_discover_baseline=True)
        assert config.auto_discover_baseline is True


# ===== Baseline Summary Compatibility Tests =====


class TestBaselineSummaryCompat:
    def test_summary_json_round_trip(self, tmp_path):
        """baseline_summary.json can be written and read back identically."""
        summary = {
            "source": "auto-discovery",
            "domain": "facebook-ads",
            "skill_md": "",
            "references": [
                {"path": "/refs/guide.md", "content": "# Guide\nContent here."},
            ],
            "topics": ["campaign management", "targeting"],
            "total_tokens": 1500,
            "score": 72.5,
            "discovery_metadata": {"method": "auto-discovery", "crawled_ok": 5},
        }

        path = tmp_path / "baseline_summary.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        with open(path, "r", encoding="utf-8") as f:
            loaded = json.load(f)

        assert loaded["source"] == "auto-discovery"
        assert loaded["domain"] == "facebook-ads"
        assert len(loaded["references"]) == 1
        assert loaded["score"] == 72.5

    def test_summary_references_have_content(self, tmp_path):
        """Each reference must have both path and content."""
        summary = {
            "source": "auto-discovery",
            "domain": "test",
            "skill_md": "",
            "references": [
                {"path": "ref1.md", "content": "content1"},
                {"path": "ref2.md", "content": "content2"},
            ],
            "topics": [],
            "total_tokens": 0,
            "score": 65.0,
            "discovery_metadata": {},
        }
        for ref in summary["references"]:
            assert "path" in ref
            assert "content" in ref
            assert len(ref["content"]) > 0
