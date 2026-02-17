"""Tests for auto-discovery: domain_analyzer, url_discoverer, url_evaluator, orchestrator."""

import json
import pytest

from pipeline.seekers.domain_analyzer import analyze_domain, DomainAnalysis
from pipeline.seekers.url_discoverer import (
    CandidateURL, _normalize_url, _is_valid_doc_url, _matches_patterns,
    _extract_ddg_url,
)
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
