"""Shared pytest fixtures for pipeline tests."""

import json
import os
import shutil
import tempfile

import pytest

from pipeline.core.types import BuildConfig
from pipeline.core.logger import PipelineLogger
from pipeline.seekers.cache import SeekersCache
from pipeline.seekers.lookup import SeekersLookup


# ── Mock Claude Client ──────────────────────────────────


class MockClaudeClient:
    """Fake Claude client that returns structurally correct JSON without API calls."""

    def __init__(self, api_key: str = "mock-key", model: str = "mock-sonnet",
                 model_light: str = "mock-haiku", base_url: str = None,
                 base_url_light: str = None, api_key_light: str = None,
                 model_premium: str = None):
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost_usd = 0.0
        self.call_count = 0
        self.model = model
        self.model_light = model_light
        self.base_url = base_url
        self.base_url_light = base_url_light
        self.api_key_light = api_key_light
        self.model_premium = model_premium or ""
        self._use_openai_format = False
        self._consecutive_credit_errors = 0
        self.model_usage = {"main": 0, "light": 0}
        self._call_history = []  # Track calls with their flags

    def call(self, system, user, **kwargs):
        self.call_count += 1
        self.total_input_tokens += 100
        self.total_output_tokens += 200
        use_light = kwargs.get("use_light_model", False)
        use_premium = kwargs.get("use_premium_model", False)
        if use_light:
            self.model_usage["light"] += 1
        else:
            self.model_usage["main"] += 1
        # Track call with flags for test assertions
        self._call_history.append({
            "type": "call",
            "use_light_model": use_light,
            "use_premium_model": use_premium,
        })

        # Domain Analyzer
        if "Documentation Research Expert" in system:
            return json.dumps({
                "official_sites": ["https://docs.example.com"],
                "doc_patterns": ["/docs/", "/guide/"],
                "search_queries": [
                    "example documentation",
                    "example tutorial",
                    "example API",
                ],
                "expected_topics": [
                    "getting started", "configuration", "api reference",
                ],
                "difficulty": "easy",
                "notes": "",
            })

        # Domain inference from content (auto_discovery)
        if "chuyen gia phan tich" in system.lower() or "content analyst" in system.lower():
            return json.dumps({
                "inferred_domain": "ai-agent-retail",
                "display_name": "AI Agent trong Ban le",
                "key_topics": [
                    "AI agent", "retail", "ecommerce", "chatbot",
                    "sales automation",
                ],
                "search_terms": [
                    "AI agent retail ecommerce",
                    "AI chatbot customer service",
                    "sales automation AI",
                    "LLM agent business applications",
                    "conversational AI retail",
                    "AI agent ban le thuong mai",
                ],
            })

        # Content Analysis (discover-from-content)
        if "Content Analysis Expert" in system:
            return json.dumps({
                "domain": "Facebook Ads",
                "language": "vi",
                "topics": [
                    "campaign management", "audience targeting",
                    "ad creative", "budget optimization",
                ],
                "search_queries": [
                    "Facebook Ads official documentation",
                    "Meta Ads Manager guide",
                    "Facebook advertising best practices",
                ],
                "official_sites": ["https://www.facebook.com/business/help"],
                "content_type": "course",
            })

        # URL Evaluator
        if "Documentation Quality Evaluator" in system:
            return json.dumps([
                {
                    "url": "https://docs.example.com/guide",
                    "score": 85, "reason": "Official documentation",
                },
            ])

        return '{"result": "mock"}'

    def call_json(self, system, user, **kwargs):
        self.call_count += 1
        self.total_input_tokens += 100
        self.total_output_tokens += 200
        use_light = kwargs.get("use_light_model", False)
        use_premium = kwargs.get("use_premium_model", False)
        if use_light:
            self.model_usage["light"] += 1
        else:
            self.model_usage["main"] += 1
        # Track call with flags for test assertions
        self._call_history.append({
            "type": "call_json",
            "use_light_model": use_light,
            "use_premium_model": use_premium,
        })

        # P1 Audit
        if "Knowledge Auditor" in system:
            return {
                "filename": "test.txt",
                "language": "vi",
                "topics": [
                    {
                        "topic": "Campaign Management",
                        "category": "campaign_management",
                        "quality_score": 85,
                        "mentions": 3,
                        "summary": "Hướng dẫn cấu trúc chiến dịch Facebook Ads",
                        "depth": "deep",
                    },
                    {
                        "topic": "Audience Targeting",
                        "category": "audience_targeting",
                        "quality_score": 78,
                        "mentions": 2,
                        "summary": "Nhắm mục tiêu đối tượng quảng cáo",
                        "depth": "moderate",
                    },
                ],
                "total_topics": 2,
                "transcript_quality": "high",
            }

        # P2 Code Pattern Extract
        if "Code Pattern Extractor" in system:
            return {
                "atoms": [
                    {
                        "title": "Factory Pattern for Data Processing",
                        "content": "The codebase uses a factory pattern to create data processors.",
                        "tags": ["factory", "design-pattern"],
                        "code_snippet": "class ProcessorFactory:\n    def create(self, type): ...",
                        "file_reference": "src/factory.py",
                        "pattern_type": "architecture",
                        "confidence": 0.88,
                    },
                ],
                "atoms_count": 1,
            }

        # P2 Extract
        if "Knowledge Atom Extractor" in system:
            return {
                "chunk_index": 1,
                "atoms": [
                    {
                        "title": "Cấu trúc tài khoản Facebook Ads",
                        "content": "Tài khoản Facebook Ads gồm 3 cấp: Campaign, Ad Set, Ad.",
                        "category": "campaign_management",
                        "tags": ["campaign", "structure", "facebook"],
                        "confidence": 0.92,
                        "source_timestamp": None,
                    },
                    {
                        "title": "Facebook Pixel là gì",
                        "content": "Facebook Pixel là đoạn mã JavaScript cài trên website để theo dõi hành vi.",
                        "category": "pixel_tracking",
                        "tags": ["pixel", "tracking", "javascript"],
                        "confidence": 0.88,
                        "source_timestamp": None,
                    },
                ],
                "atoms_count": 2,
                "chunk_quality": "high",
            }

        # P3 Dedup
        if "Deduplication Expert" in system:
            return {
                "unique_atoms": [
                    {
                        "id": "atom_0001",
                        "title": "Cấu trúc tài khoản Facebook Ads",
                        "content": "Tài khoản Facebook Ads gồm 3 cấp: Campaign, Ad Set, Ad.",
                        "category": "campaign_management",
                        "tags": ["campaign", "structure"],
                        "confidence": 0.92,
                        "status": "deduplicated",
                        "merged_from": [],
                    },
                    {
                        "id": "atom_0002",
                        "title": "Facebook Pixel là gì",
                        "content": "Facebook Pixel là đoạn mã JavaScript cài trên website.",
                        "category": "pixel_tracking",
                        "tags": ["pixel", "tracking"],
                        "confidence": 0.88,
                        "status": "deduplicated",
                        "merged_from": [],
                    },
                ],
                "duplicates_merged": 0,
                "overlaps_merged": 0,
                "conflicts": [],
                "stats": {
                    "input_count": 2,
                    "output_count": 2,
                    "duplicates_found": 0,
                    "conflicts_found": 0,
                },
            }

        # P4 Batch Verify
        if "batch" in system.lower() or "Knowledge Verification Expert" in system:
            # Parse atom count from user prompt if possible
            import re
            batch_match = re.search(r'batch of (\d+)', user)
            batch_size = int(batch_match.group(1)) if batch_match else 10
            return {
                "results": [
                    {
                        "atom_id": f"atom_{j:04d}",
                        "status": "verified",
                        "confidence_adjustment": 0.05,
                        "verification_note": "Mock batch verified",
                        "baseline_reference": None,
                    }
                    for j in range(1, batch_size + 1)
                ]
            }

        # P4 Verify (legacy single)
        if "Verification Expert" in system:
            return {
                "atom_id": "atom_0001",
                "status": "verified",
                "confidence": 0.90,
                "note": "Confirmed by baseline documentation",
                "updated_content": None,
                "evidence_source": "https://example.com",
                "verification_details": {
                    "claims_checked": 2,
                    "claims_supported": 2,
                    "claims_contradicted": 0,
                    "claims_unverifiable": 0,
                },
            }

        # P5 Build — SKILL.md
        if "AI Skill Architect" in system:
            return {
                "content": (
                    "---\n"
                    "name: Test Skill\n"
                    "description: >\n"
                    "  Use this skill for Facebook Ads knowledge including campaign management,\n"
                    "  audience targeting, ad creative, and budget optimization in Vietnam.\n"
                    "  Covers pixel tracking, conversion events, and performance metrics.\n"
                    'version: "1.0"\n'
                    "---\n\n"
                    "# Test Skill\n\n## Overview\nTest skill package.\n"
                ),
                "metadata": {
                    "name": "Test Skill",
                    "domain": "fb_ads",
                    "language": "vi",
                    "version": "1.0.0",
                    "atom_count": 2,
                    "pillar_count": 2,
                    "quality_tier": "draft",
                },
            }

        # P5 Build — Knowledge file
        if "Knowledge File Writer" in system:
            return {
                "pillar": "test",
                "content": (
                    "# Test Pillar\n\n"
                    "> Contains test knowledge atoms.\n\n"
                    "## Table of Contents\n"
                    "1. Core Concepts\n2. Detailed Analysis\n"
                    "3. Expert Insights\n\n---\n\n"
                    "## \U0001f511 Core\n\n"
                    "### Atom 1\nTest content.\n\n"
                    "## \U0001f4da Detail\n\n"
                    "### Detailed Atom\nDetailed content.\n\n"
                    "## \U0001f4a1 Insights\n\n"
                    "### Expert Insight\nExpert analysis.\n"
                ),
                "atom_ids": ["atom_0001"],
                "word_count": 20,
            }

        # P6 Optimize — eval query generation
        if "AI Skill Evaluation Designer" in system:
            return [
                {"query": "How to set up Facebook Ads campaign?", "should_trigger": True},
                {"query": "What is audience targeting in Facebook Ads?", "should_trigger": True},
                {"query": "How to optimize ad budget?", "should_trigger": True},
                {"query": "Facebook pixel tracking setup", "should_trigger": True},
                {"query": "How to write Python code?", "should_trigger": False},
                {"query": "What is the weather today?", "should_trigger": False},
            ]

        return {"result": "unknown_prompt"}

    def get_cost_summary(self):
        return {
            "calls": self.call_count,
            "input_tokens": self.total_input_tokens,
            "output_tokens": self.total_output_tokens,
            "cost_usd": 0.0,
        }

    def report_cost(self, usd, tokens):
        pass


# ── Fixtures ────────────────────────────────────────────


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture
def fixtures_dir():
    return FIXTURES_DIR


@pytest.fixture
def sample_transcript_path():
    return os.path.join(FIXTURES_DIR, "sample_transcript_vi.txt")


@pytest.fixture
def sample_config_path():
    return os.path.join(FIXTURES_DIR, "sample_config.yaml")


@pytest.fixture
def tmp_output_dir():
    d = tempfile.mkdtemp(prefix="pipeline_test_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def tmp_cache_dir():
    d = tempfile.mkdtemp(prefix="pipeline_cache_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def mock_claude():
    return MockClaudeClient()


@pytest.fixture
def logger():
    return PipelineLogger(build_id="test_build")


@pytest.fixture
def seekers_cache(tmp_cache_dir):
    return SeekersCache(tmp_cache_dir, ttl_hours=168)


@pytest.fixture
def seekers_lookup(seekers_cache, logger):
    return SeekersLookup(seekers_cache, logger)


@pytest.fixture
def build_config(sample_config_path, sample_transcript_path, tmp_output_dir, tmp_cache_dir):
    return BuildConfig(
        name="Test Skill",
        domain="fb_ads",
        language="vi",
        quality_tier="draft",
        platforms=["claude"],
        baseline_sources=[],
        transcript_paths=[sample_transcript_path],
        output_dir=tmp_output_dir,
        config_path=sample_config_path,
        claude_api_key="test-key",
        claude_model="claude-sonnet-4-5-20250929",
        seekers_cache_dir=tmp_cache_dir,
    )


class _ErrorClaudeClient(MockClaudeClient):
    """MockClaudeClient that always returns invalid JSON."""

    def call(self, system, user, **kwargs):
        self.call_count += 1
        return "INVALID JSON {{{"

    def call_json(self, system, user, **kwargs):
        self.call_count += 1
        raise ValueError("Forced JSON parse error")


@pytest.fixture
def mock_claude_error():
    return _ErrorClaudeClient()
