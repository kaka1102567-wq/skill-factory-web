"""Integration tests for Quality Score Sprint 1+2 overhaul.

Verifies scoring formulas, source detection, and differentiation
across all pipeline phases (P0-P5).
"""

import inspect
import re

import pytest


# ── Category A: P0 Score Differentiation ──


class TestP0ScoreDifferentiation:
    """Verify _score_baseline_quality produces meaningful score spread."""

    @pytest.fixture()
    def scorer(self):
        from pipeline.phases.p0_baseline import _score_baseline_quality
        return _score_baseline_quality

    def _make_refs(self, texts: list[str]) -> list[dict]:
        return [{"content": t} for t in texts]

    def test_good_baseline_high_score(self, scorer):
        """Good refs matching domain should score > 70."""
        topics = [
            "Facebook Ads targeting allows advertisers to reach specific "
            "audiences based on demographics, interests, and behaviors. "
            "Detailed targeting options include location age gender and "
            "language settings for campaign optimization purposes. " * 10,
            "The Facebook pixel tracks conversions and enables retargeting "
            "of website visitors through JavaScript code snippets. "
            "Standard events include purchase lead and add-to-cart actions "
            "measured across advertising campaigns. " * 10,
            "Custom audiences can be created from customer lists or website "
            "traffic data collected via the tracking pixel integration. "
            "Engagement audiences capture interactions from video views and "
            "lead form submissions on the platform. " * 10,
            "Lookalike audiences help find new users similar to existing "
            "customers using algorithmic modeling and expansion features. "
            "Source audience quality determines the effectiveness of "
            "lookalike targeting for acquisition campaigns. " * 10,
            "Campaign budget optimization distributes spend across ad sets "
            "automatically for best performance results and efficiency. "
            "Minimum budget requirements vary by bidding strategy and "
            "optimization event selection choices. " * 10,
            "Facebook ads creative best practices include using high quality "
            "imagery compelling headlines and clear call to action buttons. "
            "Video ads generally achieve higher engagement rates compared "
            "to static image formats in feed placements. " * 10,
            "Facebook ads bidding strategies include lowest cost target cost "
            "and bid cap options for controlling campaign expenditure. "
            "Auction dynamics determine actual cost per result based on "
            "competition and estimated action rates. " * 10,
            "Facebook ads placement options span feed stories marketplace "
            "and audience network for cross-platform reach distribution. "
            "Automatic placements allow the delivery system to find the "
            "most efficient inventory allocation. " * 10,
            "Facebook ads reporting provides metrics like reach impressions "
            "clicks and conversions for measuring campaign effectiveness. "
            "Attribution windows define the lookback period for counting "
            "conversion events after ad interactions. " * 10,
            "Facebook ads account structure uses campaigns ad sets and ads "
            "hierarchy for organized management of advertising initiatives. "
            "Naming conventions help teams collaborate efficiently when "
            "managing multiple campaigns simultaneously. " * 10,
        ]
        refs = self._make_refs(topics)
        score = scorer(refs, "facebook-ads")
        assert score > 70, f"Good baseline score {score} should be > 70"

    def test_bad_baseline_low_score(self, scorer):
        """Unrelated refs should score < 55."""
        refs = self._make_refs([
            (
                "Python API documentation covers Flask and Django REST "
                "framework for building web APIs. SQLAlchemy provides ORM "
                "capabilities for database operations. The requests library "
                "simplifies HTTP client operations in Python applications. "
                "Virtual environments isolate project dependencies. " * 5
            )
            for _ in range(10)
        ])
        score = scorer(refs, "ai-agent-customer-service")
        assert score < 55, f"Bad baseline score {score} should be < 55"

    def test_score_gap_minimum_20(self, scorer):
        """Good and bad baseline scores should differ by >= 20."""
        good_refs = self._make_refs([
            (
                "Facebook Ads targeting allows advertisers to reach audiences "
                "using pixel tracking, custom audiences, and lookalike modeling. "
                "Campaign budget optimization helps distribute ad spend. "
                "Retargeting website visitors through the Facebook pixel. " * 5
            )
            for _ in range(10)
        ])
        bad_refs = self._make_refs([
            (
                "Python API documentation covers Flask and Django REST "
                "framework for building web APIs. SQLAlchemy provides ORM "
                "capabilities for database operations. " * 5
            )
            for _ in range(10)
        ])
        good_score = scorer(good_refs, "facebook-ads")
        bad_score = scorer(bad_refs, "ai-agent-customer-service")
        gap = good_score - bad_score
        assert gap >= 20, (
            f"Score gap {gap:.1f} (good={good_score:.1f}, bad={bad_score:.1f}) "
            f"should be >= 20"
        )

    def test_empty_refs(self, scorer):
        """Empty refs should score <= 30."""
        score = scorer([], "facebook-ads")
        assert score <= 30, f"Empty refs score {score} should be <= 30"

    def test_stub_refs_penalized(self, scorer):
        """Short stub refs should score lower than full-length refs."""
        stub_refs = self._make_refs([
            "Facebook ads targeting basics overview."
            for _ in range(10)
        ])
        full_refs = self._make_refs([
            (
                "Facebook Ads targeting allows advertisers to reach specific "
                "audiences based on demographics, interests, and behaviors. "
                "The Facebook pixel tracks conversions and enables retargeting "
                "of website visitors. Custom audiences can be built from "
                "multiple data sources. Lookalike audiences find similar users. "
                "Campaign budget optimization distributes spend for best ROI. " * 4
            )
            for _ in range(10)
        ])
        stub_score = scorer(stub_refs, "facebook-ads")
        full_score = scorer(full_refs, "facebook-ads")
        assert stub_score < full_score, (
            f"Stub score {stub_score:.1f} should be < full score {full_score:.1f}"
        )


# ── Category B: P4 Evidence Differentiation ──


class TestP4EvidenceDifferentiation:
    """Verify _search_baseline finds matching atoms and rejects unrelated."""

    @pytest.fixture()
    def searcher(self):
        from pipeline.phases.p4_verify import _search_baseline
        return _search_baseline

    @pytest.fixture()
    def baseline_refs(self):
        return [
            {
                "path": "facebook-ads-targeting.md",
                "content": (
                    "Facebook Ads targeting uses interest targeting and "
                    "lookalike audiences to reach potential customers. "
                    "Advertisers can create custom audiences from website "
                    "visitors via the Facebook pixel. Detailed targeting "
                    "options include demographics, interests, and behaviors."
                ),
            },
            {
                "path": "facebook-pixel-tracking.md",
                "content": (
                    "The Facebook pixel is a piece of JavaScript code that "
                    "tracks visitor actions on your website. It enables "
                    "conversion tracking, retargeting, and building custom "
                    "audiences for Facebook advertising campaigns."
                ),
            },
        ]

    def test_matching_atom_found(self, searcher, baseline_refs):
        """Atom about Facebook Ad Targeting should be found."""
        result = searcher(
            "Facebook Ad Targeting",
            "interest targeting lookalike audiences custom audiences",
            baseline_refs,
        )
        assert result["found"] is True

    def test_unrelated_atom_not_found(self, searcher, baseline_refs):
        """Atom about Kubernetes should not be found."""
        result = searcher(
            "Kubernetes Deployment",
            "Helm charts container orchestration kubectl apply pods services",
            baseline_refs,
        )
        assert result["found"] is False

    def test_found_has_higher_match_score(self, searcher, baseline_refs):
        """Matched atom should have match_score > 0."""
        result = searcher(
            "Facebook Ad Targeting",
            "interest targeting lookalike audiences custom audiences",
            baseline_refs,
        )
        assert result.get("match_score", 0) > 0


# ── Category C: Code Inspection Tests ──


class TestCodeInspection:
    """Inspect source code to verify Sprint 1+2 scoring formulas."""

    def test_p1_no_avg_quality(self):
        """P1 should NOT use avg_quality (old formula)."""
        from pipeline.phases import p1_audit
        source = inspect.getsource(p1_audit.run_p1)
        assert "avg_quality" not in source, (
            "P1 still contains 'avg_quality' — old formula not removed"
        )

    def test_p1_has_measurable_components(self):
        """P1 score should use density, depth, category, balance components."""
        from pipeline.phases import p1_audit
        source = inspect.getsource(p1_audit.run_p1)
        for component in ["density_score", "depth_score",
                          "category_score", "balance_score"]:
            assert component in source, (
                f"P1 missing scoring component: {component}"
            )

    def test_p3_no_inverted_formula(self):
        """P3 should NOT use the old inverted formula."""
        from pipeline.phases import p3_dedup
        source = inspect.getsource(p3_dedup.run_p3)
        assert "65.0 + kept_ratio * 35" not in source, (
            "P3 still contains old inverted formula '65.0 + kept_ratio * 35'"
        )
        assert "65 + kept" not in source, (
            "P3 still contains old inverted formula '65 + kept'"
        )

    def test_p3_has_ideal_ranges(self):
        """P3 should use ideal_low, ideal_high, ratio_score."""
        from pipeline.phases import p3_dedup
        source = inspect.getsource(p3_dedup.run_p3)
        for component in ["ideal_low", "ideal_high", "ratio_score"]:
            assert component in source, (
                f"P3 missing scoring component: {component}"
            )

    def test_p4_score_uses_evidence(self):
        """P4 score block should use evidence_rate, avg_match, sampling_factor
        and NOT use 'confidence'."""
        from pipeline.phases import p4_verify
        source = inspect.getsource(p4_verify.run_p4)

        # Find the score calculation block
        calc_start = source.find("Calculate score")
        save_start = source.find("Save output")
        assert calc_start >= 0, "P4 missing 'Calculate score' block"
        assert save_start >= 0, "P4 missing 'Save output' block"

        score_block = source[calc_start:save_start]
        for component in ["evidence_rate", "avg_match", "sampling_factor"]:
            assert component in score_block, (
                f"P4 score block missing component: {component}"
            )
        # Should NOT reference old 'confidence' variable in scoring
        # (atom-level confidence is fine, but the score variable shouldn't)
        assert "confidence" not in score_block, (
            "P4 score block still references 'confidence' — "
            "should use evidence_rate/avg_match instead"
        )

    def test_p5_reads_all_phase_files(self):
        """P5 should read output from all prior phases."""
        from pipeline.phases import p5_build
        source = inspect.getsource(p5_build.run_p5)
        for fname in [
            "baseline_summary.json",
            "inventory.json",
            "atoms_raw.json",
            "atoms_deduplicated.json",
            "atoms_verified.json",
        ]:
            assert fname in source, (
                f"P5 missing phase file read: {fname}"
            )

    def test_p5_weights_sum_one(self):
        """P5 phase weights should sum to 1.0."""
        from pipeline.phases import p5_build
        source = inspect.getsource(p5_build.run_p5)

        # Extract weights dict
        weights_match = re.search(
            r'weights\s*=\s*\{([^}]+)\}', source,
        )
        assert weights_match, "P5 missing weights dict"

        weight_values = re.findall(
            r':\s*([\d.]+)', weights_match.group(1),
        )
        total = sum(float(v) for v in weight_values)
        assert abs(total - 1.0) < 0.001, (
            f"P5 weights sum to {total}, expected 1.0"
        )


# ── Category D: Source Detection Consistency ──


class TestSourceDetectionConsistency:
    """Verify all phases recognize the three baseline source types."""

    REQUIRED_SOURCES = ["skill_seekers", "auto-discovery", "auto-discovery-content"]

    @pytest.mark.parametrize("module_path", [
        "pipeline/phases/p1_audit.py",
        "pipeline/phases/p2_extract.py",
        "pipeline/phases/p4_verify.py",
        "pipeline/phases/p5_build.py",
    ])
    def test_source_detection(self, module_path):
        """Each phase should recognize all three source types."""
        with open(module_path, "r", encoding="utf-8") as f:
            content = f.read()

        for source in self.REQUIRED_SOURCES:
            assert source in content, (
                f"{module_path} missing source type: '{source}'"
            )


# ── Category E: Discovery Score ──


class TestDiscoveryScore:
    """Verify auto-discovery files use relevance heuristic, not count-based."""

    def test_auto_discovery_no_count_formula(self):
        """auto_discovery.py should NOT use count-based scoring."""
        with open(
            "pipeline/seekers/auto_discovery.py", "r", encoding="utf-8",
        ) as f:
            content = f.read()
        assert "60.0 + len(ok_refs) * 2.5" not in content, (
            "auto_discovery.py still uses count-based formula"
        )
        assert "_score_refs_quality" in content, (
            "auto_discovery.py missing _score_refs_quality"
        )

    def test_discover_baseline_no_count_formula(self):
        """discover_baseline.py should NOT use count-based scoring."""
        with open(
            "pipeline/commands/discover_baseline.py", "r", encoding="utf-8",
        ) as f:
            content = f.read()
        assert "60.0 + len(references) * 3.0" not in content, (
            "discover_baseline.py still uses count-based formula"
        )
        assert "_score_refs_quality" in content, (
            "discover_baseline.py missing _score_refs_quality"
        )
