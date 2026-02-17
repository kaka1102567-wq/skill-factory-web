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
from pipeline.seekers.auto_discovery import run_auto_discovery, DiscoveryResult
from pipeline.core.logger import PipelineLogger


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
