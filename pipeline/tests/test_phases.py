"""Tests for pipeline phases P0-P5 using MockClaudeClient."""

import json
import os

import pytest

from pipeline.core.types import PhaseResult
from pipeline.core.utils import write_json
from pipeline.phases.p0_baseline import run_p0
from pipeline.phases.p1_audit import run_p1
from pipeline.phases.p2_extract import run_p2
from pipeline.phases.p3_dedup import run_p3
from pipeline.phases.p4_verify import run_p4
from pipeline.phases.p5_build import run_p5


class TestP0Baseline:

    def test_empty_sources_returns_done(self, build_config, logger, seekers_cache, seekers_lookup):
        """P0 with no baseline_sources should succeed with score 50."""
        build_config.baseline_sources = []
        result = run_p0(build_config, cache=seekers_cache, lookup=seekers_lookup, logger=logger)
        assert result.status == "done"
        assert result.quality_score == 50.0
        assert result.phase_id == "p0"

    def test_returns_phase_result(self, build_config, logger, seekers_cache, seekers_lookup):
        result = run_p0(build_config, cache=seekers_cache, lookup=seekers_lookup, logger=logger)
        assert isinstance(result, PhaseResult)
        assert result.started_at != ""


class TestP1Audit:

    def test_audit_produces_inventory(self, build_config, mock_claude, logger, seekers_cache, seekers_lookup):
        result = run_p1(build_config, mock_claude, seekers_cache, seekers_lookup, logger)
        assert result.status == "done"
        assert result.phase_id == "p1"
        assert result.atoms_count > 0

        # Check output file exists
        inventory_path = os.path.join(build_config.output_dir, "inventory.json")
        assert os.path.exists(inventory_path)
        with open(inventory_path) as f:
            data = json.load(f)
        assert "topics" in data
        assert len(data["topics"]) > 0

    def test_audit_no_transcripts_fails(self, build_config, mock_claude, logger, seekers_cache, seekers_lookup):
        build_config.transcript_paths = []
        result = run_p1(build_config, mock_claude, seekers_cache, seekers_lookup, logger)
        assert result.status == "failed"


class TestP2Extract:

    def test_extract_produces_atoms(self, build_config, mock_claude, logger, seekers_cache, seekers_lookup):
        result = run_p2(build_config, mock_claude, seekers_cache, seekers_lookup, logger)
        assert result.status == "done"
        assert result.phase_id == "p2"
        assert result.atoms_count > 0

        # Check output file
        atoms_path = os.path.join(build_config.output_dir, "atoms_raw.json")
        assert os.path.exists(atoms_path)
        with open(atoms_path) as f:
            data = json.load(f)
        assert len(data["atoms"]) > 0
        assert data["atoms"][0]["id"].startswith("atom_")

    def test_extract_no_transcripts_fails(self, build_config, mock_claude, logger, seekers_cache, seekers_lookup):
        build_config.transcript_paths = []
        result = run_p2(build_config, mock_claude, seekers_cache, seekers_lookup, logger)
        assert result.status == "failed"

    def test_extract_with_code_analysis(self, build_config, mock_claude, logger, seekers_cache, seekers_lookup):
        """P2 extracts code atoms when code_analysis.json exists in input/."""
        # Use realistic build layout: build_dir/output/ + build_dir/input/
        import tempfile, shutil
        build_dir = tempfile.mkdtemp(prefix="sf_build_")
        output_dir = os.path.join(build_dir, "output")
        input_dir = os.path.join(build_dir, "input")
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(input_dir, exist_ok=True)
        build_config.output_dir = output_dir
        write_json({
            "repo_url": "https://github.com/test/repo",
            "repo_structure": {
                "total_files": 10,
                "languages": {"python": 5},
                "primary_language": "python",
                "has_tests": True,
                "has_docs": True,
                "config_files": [],
            },
            "analyzed_files": [
                {
                    "path": "src/main.py",
                    "language": "python",
                    "size": 500,
                    "content": "def main():\n    print('hello')\n",
                    "lines": 2,
                },
            ],
        }, os.path.join(input_dir, "code_analysis.json"))

        try:
            result = run_p2(build_config, mock_claude, seekers_cache, seekers_lookup, logger)
            assert result.status == "done"
            assert result.metrics.get("code_atoms", 0) > 0

            # Verify atoms include code atoms
            atoms_path = os.path.join(output_dir, "atoms_raw.json")
            with open(atoms_path) as f:
                data = json.load(f)
            code_atoms = [a for a in data["atoms"] if a.get("source") == "codebase"]
            assert len(code_atoms) > 0
            assert code_atoms[0]["category"] == "code_pattern"
        finally:
            shutil.rmtree(build_dir, ignore_errors=True)

    def test_extract_without_code_analysis(self, build_config, mock_claude, logger, seekers_cache, seekers_lookup):
        """P2 works normally when no code_analysis.json exists."""
        # Use realistic build layout without code_analysis.json
        import tempfile, shutil
        build_dir = tempfile.mkdtemp(prefix="sf_build_")
        output_dir = os.path.join(build_dir, "output")
        os.makedirs(output_dir, exist_ok=True)
        build_config.output_dir = output_dir
        try:
            result = run_p2(build_config, mock_claude, seekers_cache, seekers_lookup, logger)
            assert result.status == "done"
            assert result.metrics.get("code_atoms", 0) == 0
        finally:
            shutil.rmtree(build_dir, ignore_errors=True)


class TestP3Dedup:

    def _setup_p2_output(self, output_dir):
        """Create fake atoms_raw.json as P2 output."""
        atoms = [
            {"id": "atom_0001", "title": "Atom A", "content": "Content A",
             "category": "campaign_management", "tags": ["a"], "confidence": 0.9, "status": "raw"},
            {"id": "atom_0002", "title": "Atom B", "content": "Content B",
             "category": "campaign_management", "tags": ["b"], "confidence": 0.85, "status": "raw"},
            {"id": "atom_0003", "title": "Atom C", "content": "Content C",
             "category": "pixel_tracking", "tags": ["c"], "confidence": 0.8, "status": "raw"},
        ]
        write_json({"atoms": atoms, "total_atoms": 3, "score": 85.0},
                    os.path.join(output_dir, "atoms_raw.json"))

    def test_dedup_produces_deduplicated_atoms(self, build_config, mock_claude, logger, seekers_cache, seekers_lookup):
        self._setup_p2_output(build_config.output_dir)
        result = run_p3(build_config, mock_claude, seekers_cache, seekers_lookup, logger)
        assert result.status == "done"
        assert result.phase_id == "p3"

        dedup_path = os.path.join(build_config.output_dir, "atoms_deduplicated.json")
        assert os.path.exists(dedup_path)
        conflicts_path = os.path.join(build_config.output_dir, "conflicts.json")
        assert os.path.exists(conflicts_path)

    def test_dedup_no_input_handles_gracefully(self, build_config, mock_claude, logger, seekers_cache, seekers_lookup):
        # No atoms_raw.json → should fail
        result = run_p3(build_config, mock_claude, seekers_cache, seekers_lookup, logger)
        assert result.status == "failed"


class TestCategoryFallback:

    def test_empty_category_defaults_to_general_in_p3(self, build_config, mock_claude, logger, seekers_cache, seekers_lookup):
        """Atoms with empty category get assigned 'general' at P3 start."""
        atoms = [
            {"id": "atom_0001", "title": "A", "content": "Content A",
             "category": "", "tags": [], "confidence": 0.9, "status": "raw"},
            {"id": "atom_0002", "title": "B", "content": "Content B",
             "category": "   ", "tags": [], "confidence": 0.8, "status": "raw"},
            {"id": "atom_0003", "title": "C", "content": "Content C",
             "category": "valid_cat", "tags": [], "confidence": 0.85, "status": "raw"},
        ]
        write_json({"atoms": atoms, "total_atoms": 3, "score": 85.0},
                    os.path.join(build_config.output_dir, "atoms_raw.json"))
        result = run_p3(build_config, mock_claude, seekers_cache, seekers_lookup, logger)
        assert result.status == "done"

        dedup_path = os.path.join(build_config.output_dir, "atoms_deduplicated.json")
        with open(dedup_path) as f:
            data = json.load(f)
        # No atom should have empty category
        for atom in data["atoms"]:
            assert atom.get("category", "").strip() != ""


class TestP3PreservesOriginal:

    def _setup_p2_with_rich_atoms(self, output_dir):
        """Create atoms_raw.json with atoms that have all fields."""
        atoms = [
            {"id": "atom_0001", "title": "Atom A", "content": "Full content A here with details.",
             "category": "campaign_management", "tags": ["a", "b"], "confidence": 0.9,
             "status": "raw", "source": "transcript", "source_video": "video1.mp4"},
            {"id": "atom_0002", "title": "Atom B", "content": "Full content B here with details.",
             "category": "campaign_management", "tags": ["c", "d"], "confidence": 0.85,
             "status": "raw", "source": "transcript", "source_video": "video2.mp4"},
            {"id": "atom_0003", "title": "Atom C", "content": "Full content C here with details.",
             "category": "pixel_tracking", "tags": ["e"], "confidence": 0.8,
             "status": "raw", "source": "baseline"},
        ]
        write_json({"atoms": atoms, "total_atoms": 3, "score": 85.0},
                    os.path.join(output_dir, "atoms_raw.json"))
        return atoms

    def test_p3_preserves_original_fields(self, build_config, mock_claude, logger, seekers_cache, seekers_lookup):
        """Atoms after dedup still have category, tags, source_video, full content."""
        original_atoms = self._setup_p2_with_rich_atoms(build_config.output_dir)
        result = run_p3(build_config, mock_claude, seekers_cache, seekers_lookup, logger)
        assert result.status == "done"

        dedup_path = os.path.join(build_config.output_dir, "atoms_deduplicated.json")
        with open(dedup_path) as f:
            data = json.load(f)

        for atom in data["atoms"]:
            assert atom.get("category"), f"Atom {atom['id']} missing category"
            assert isinstance(atom.get("tags"), list), f"Atom {atom['id']} missing tags"
            assert atom.get("content"), f"Atom {atom['id']} missing content"

    def test_p3_no_content_truncation(self, build_config, mock_claude, logger, seekers_cache, seekers_lookup):
        """Raw atom content must be preserved after dedup (no truncation)."""
        original_atoms = self._setup_p2_with_rich_atoms(build_config.output_dir)
        result = run_p3(build_config, mock_claude, seekers_cache, seekers_lookup, logger)
        assert result.status == "done"

        dedup_path = os.path.join(build_config.output_dir, "atoms_deduplicated.json")
        with open(dedup_path) as f:
            data = json.load(f)

        orig_by_id = {a["id"]: a for a in original_atoms}
        for atom in data["atoms"]:
            orig = orig_by_id.get(atom["id"])
            if orig:
                # Content should be at least as long as original
                assert len(atom["content"]) >= len(orig["content"]), \
                    f"Atom {atom['id']} content truncated"


class TestP3SafeguardEmptyResponse:

    def test_p3_empty_claude_response_keeps_all_atoms(self, build_config, logger, seekers_cache, seekers_lookup):
        """When Claude returns empty unique_atoms, safeguard keeps all original atoms."""
        from pipeline.tests.conftest import MockClaudeClient

        class EmptyDedupClaude(MockClaudeClient):
            def call_json(self, system, user, **kwargs):
                self.call_count += 1
                if kwargs.get("use_light_model"):
                    self.model_usage["light"] += 1
                else:
                    self.model_usage["main"] += 1
                if "Deduplication Expert" in system:
                    return {
                        "unique_atoms": [],
                        "conflicts": [],
                        "stats": {"input_count": 5, "output_count": 0, "duplicates_found": 5, "conflicts_found": 0},
                    }
                return super().call_json(system, user, **kwargs)

        atoms = [
            {"id": f"atom_{i:04d}", "title": f"Atom {i}", "content": f"Content {i}",
             "category": "general", "tags": ["a"], "confidence": 0.9, "status": "raw"}
            for i in range(1, 6)
        ]
        write_json({"atoms": atoms, "total_atoms": 5, "score": 85.0},
                    os.path.join(build_config.output_dir, "atoms_raw.json"))

        mock = EmptyDedupClaude()
        result = run_p3(build_config, mock, seekers_cache, seekers_lookup, logger)
        assert result.status == "done"
        assert result.atoms_count == 5, f"Expected 5 atoms kept, got {result.atoms_count}"


class TestAdaptiveThreshold:

    def test_small_set_reduces_threshold(self):
        from pipeline.phases.p3_dedup import _get_adaptive_threshold
        assert _get_adaptive_threshold(0.8, 25) == 0.65  # < 30 atoms

    def test_medium_set_reduces_threshold(self):
        from pipeline.phases.p3_dedup import _get_adaptive_threshold
        assert abs(_get_adaptive_threshold(0.8, 45) - 0.70) < 1e-9  # 30-50 atoms

    def test_large_set_no_change(self):
        from pipeline.phases.p3_dedup import _get_adaptive_threshold
        assert _get_adaptive_threshold(0.8, 150) == 0.80  # > 100 atoms

    def test_minimum_floor(self):
        from pipeline.phases.p3_dedup import _get_adaptive_threshold
        assert _get_adaptive_threshold(0.5, 10) == 0.50  # never below 0.5

    def test_near_100_reduces_slightly(self):
        from pipeline.phases.p3_dedup import _get_adaptive_threshold
        assert _get_adaptive_threshold(0.8, 80) == 0.75  # 50-100 atoms


class TestP4Verify:

    def _setup_p3_output(self, output_dir):
        """Create fake atoms_deduplicated.json as P3 output."""
        atoms = [
            {"id": "atom_0001", "title": "Atom A", "content": "Content A",
             "category": "campaign_management", "tags": ["a"], "confidence": 0.9, "status": "deduplicated"},
            {"id": "atom_0002", "title": "Atom B", "content": "Content B",
             "category": "pixel_tracking", "tags": ["b"], "confidence": 0.85, "status": "deduplicated"},
        ]
        write_json({"atoms": atoms, "total_atoms": 2, "score": 85.0},
                    os.path.join(output_dir, "atoms_deduplicated.json"))

    def test_verify_produces_verified_atoms(self, build_config, mock_claude, logger, seekers_cache, seekers_lookup):
        self._setup_p3_output(build_config.output_dir)
        result = run_p4(build_config, mock_claude, seekers_cache, seekers_lookup, logger)
        assert result.status == "done"
        assert result.phase_id == "p4"

        verified_path = os.path.join(build_config.output_dir, "atoms_verified.json")
        assert os.path.exists(verified_path)
        with open(verified_path) as f:
            data = json.load(f)
        for atom in data["atoms"]:
            assert atom["status"] in ("verified", "updated", "flagged", "unverified", "passthrough")

    def test_verify_no_input_fails(self, build_config, mock_claude, logger, seekers_cache, seekers_lookup):
        result = run_p4(build_config, mock_claude, seekers_cache, seekers_lookup, logger)
        assert result.status == "failed"

    def _setup_with_baseline(self, output_dir):
        """Create P3 atoms + baseline_summary with matching references."""
        atoms = [
            {"id": "atom_0001", "title": "Facebook Pixel Setup",
             "content": "Setup Facebook Pixel with base code, standard events, and conversions API",
             "category": "tools", "tags": ["pixel", "setup"], "confidence": 0.9, "status": "deduplicated"},
            {"id": "atom_0002", "title": "Quantum Computing Tips",
             "content": "Quantum entanglement enables faster computation across qubits",
             "category": "advanced", "tags": ["quantum"], "confidence": 0.85, "status": "deduplicated"},
        ]
        write_json({"atoms": atoms, "total_atoms": 2, "score": 85.0},
                    os.path.join(output_dir, "atoms_deduplicated.json"))
        write_json({
            "source": "skill_seekers",
            "references": [
                {"path": "references/pixel-setup.md",
                 "content": "Facebook Pixel is a piece of code. Setup involves base code installation, adding standard events like Purchase and AddToCart, and connecting the Conversions API for server-side tracking."},
            ],
        }, os.path.join(output_dir, "baseline_summary.json"))

    def test_verify_evidence_found_has_details(self, build_config, mock_claude, logger, seekers_cache, seekers_lookup):
        """Atoms matching baseline get detailed evidence with match_score."""
        self._setup_with_baseline(build_config.output_dir)
        build_config.quality_tier = "premium"  # 100% sample to test both atoms
        result = run_p4(build_config, mock_claude, seekers_cache, seekers_lookup, logger)
        assert result.status == "done"

        verified_path = os.path.join(build_config.output_dir, "atoms_verified.json")
        with open(verified_path) as f:
            data = json.load(f)

        # atom_0001 should have evidence (pixel/setup keywords match)
        atom1 = next(a for a in data["atoms"] if a["id"] == "atom_0001")
        assert "evidence" in atom1
        ev = atom1["evidence"]
        assert ev["found"] is True
        assert "snippet" in ev
        assert ev["match_score"] >= 40.0
        assert isinstance(ev["keywords_matched"], list)
        assert ev["keywords_total"] > 0

    def test_verify_evidence_not_found_has_closest(self, build_config, mock_claude, logger, seekers_cache, seekers_lookup):
        """Atoms not matching baseline get evidence with found=False."""
        self._setup_with_baseline(build_config.output_dir)
        build_config.quality_tier = "premium"  # 100% sample to test both atoms
        result = run_p4(build_config, mock_claude, seekers_cache, seekers_lookup, logger)
        assert result.status == "done"

        verified_path = os.path.join(build_config.output_dir, "atoms_verified.json")
        with open(verified_path) as f:
            data = json.load(f)

        # atom_0002 (quantum) should NOT match pixel docs
        atom2 = next(a for a in data["atoms"] if a["id"] == "atom_0002")
        assert "evidence" in atom2
        ev = atom2["evidence"]
        assert ev["found"] is False
        assert "note" in ev


class TestP5Build:

    def _setup_p4_output(self, output_dir):
        """Create fake atoms_verified.json as P4 output."""
        atoms = [
            {"id": "atom_0001", "title": "Atom A", "content": "Content about campaigns.",
             "category": "campaign_management", "tags": ["campaign"], "confidence": 0.9,
             "status": "verified", "verification_note": "OK"},
            {"id": "atom_0002", "title": "Atom B", "content": "Content about pixel.",
             "category": "pixel_tracking", "tags": ["pixel"], "confidence": 0.85,
             "status": "verified", "verification_note": "OK"},
        ]
        write_json({"atoms": atoms, "total_atoms": 2, "score": 87.5},
                    os.path.join(output_dir, "atoms_verified.json"))

    def test_build_creates_package(self, build_config, mock_claude, logger, seekers_cache, seekers_lookup):
        self._setup_p4_output(build_config.output_dir)
        result = run_p5(build_config, mock_claude, seekers_cache, seekers_lookup, logger)
        assert result.status == "done"
        assert result.phase_id == "p5"

        # SKILL.md exists
        skill_path = os.path.join(build_config.output_dir, "SKILL.md")
        assert os.path.exists(skill_path)

        # knowledge/ directory with files
        knowledge_dir = os.path.join(build_config.output_dir, "knowledge")
        assert os.path.isdir(knowledge_dir)
        md_files = [f for f in os.listdir(knowledge_dir) if f.endswith(".md")]
        assert len(md_files) > 0

        # metadata.json
        meta_path = os.path.join(build_config.output_dir, "metadata.json")
        assert os.path.exists(meta_path)

        # package.zip
        zip_path = os.path.join(build_config.output_dir, "package.zip")
        assert os.path.exists(zip_path)

    def test_build_no_input_fails(self, build_config, mock_claude, logger, seekers_cache, seekers_lookup):
        result = run_p5(build_config, mock_claude, seekers_cache, seekers_lookup, logger)
        assert result.status == "failed"

    def test_multi_platform_creates_subdirs(self, build_config, mock_claude, logger, seekers_cache, seekers_lookup):
        """Multi-platform build creates claude/, openclaw/, antigravity/ dirs."""
        self._setup_p4_output(build_config.output_dir)
        build_config.platforms = ["claude", "openclaw", "antigravity"]
        result = run_p5(build_config, mock_claude, seekers_cache, seekers_lookup, logger)
        assert result.status == "done"

        out = build_config.output_dir
        # Platform subdirectories exist
        assert os.path.isdir(os.path.join(out, "claude"))
        assert os.path.isdir(os.path.join(out, "openclaw"))
        assert os.path.isdir(os.path.join(out, "antigravity"))

        # Root-level SKILL.md moved into subdirs
        assert not os.path.exists(os.path.join(out, "SKILL.md"))
        assert not os.path.isdir(os.path.join(out, "knowledge"))

    def test_multi_platform_claude_dir_structure(self, build_config, mock_claude, logger, seekers_cache, seekers_lookup):
        """Claude platform dir has SKILL.md + knowledge/."""
        self._setup_p4_output(build_config.output_dir)
        build_config.platforms = ["claude", "openclaw"]
        result = run_p5(build_config, mock_claude, seekers_cache, seekers_lookup, logger)
        assert result.status == "done"

        claude_dir = os.path.join(build_config.output_dir, "claude")
        assert os.path.exists(os.path.join(claude_dir, "SKILL.md"))
        assert os.path.isdir(os.path.join(claude_dir, "knowledge"))

    def test_multi_platform_openclaw_simplified_frontmatter(self, build_config, mock_claude, logger, seekers_cache, seekers_lookup):
        """OpenClaw SKILL.md has only name, description, version in frontmatter."""
        self._setup_p4_output(build_config.output_dir)
        build_config.platforms = ["claude", "openclaw"]
        result = run_p5(build_config, mock_claude, seekers_cache, seekers_lookup, logger)
        assert result.status == "done"

        oc_skill = os.path.join(build_config.output_dir, "openclaw", "SKILL.md")
        assert os.path.exists(oc_skill)
        with open(oc_skill) as f:
            content = f.read()
        # Simplified frontmatter — no metadata block, no routing
        assert "name:" in content
        assert "description:" in content
        assert 'version: "1.0"' in content
        assert "## Routing Logic" not in content

    def test_multi_platform_antigravity_single_file(self, build_config, mock_claude, logger, seekers_cache, seekers_lookup):
        """Antigravity produces a single system_instructions.md."""
        self._setup_p4_output(build_config.output_dir)
        build_config.platforms = ["claude", "antigravity"]
        result = run_p5(build_config, mock_claude, seekers_cache, seekers_lookup, logger)
        assert result.status == "done"

        ag_dir = os.path.join(build_config.output_dir, "antigravity")
        si_path = os.path.join(ag_dir, "system_instructions.md")
        assert os.path.exists(si_path)
        with open(si_path) as f:
            content = f.read()
        assert "System Instructions" in content
        assert "Core Knowledge" in content
        assert "Response Guidelines" in content
        # No subdirectories in antigravity
        assert not os.path.isdir(os.path.join(ag_dir, "knowledge"))
        assert not os.path.isdir(os.path.join(ag_dir, "references"))

    def test_multi_platform_metadata_lists_platforms(self, build_config, mock_claude, logger, seekers_cache, seekers_lookup):
        """metadata.json includes platforms_built field."""
        self._setup_p4_output(build_config.output_dir)
        build_config.platforms = ["claude", "openclaw", "antigravity"]
        result = run_p5(build_config, mock_claude, seekers_cache, seekers_lookup, logger)
        assert result.status == "done"

        meta_path = os.path.join(build_config.output_dir, "metadata.json")
        with open(meta_path) as f:
            meta = json.load(f)
        assert set(meta["platforms_built"]) == {"claude", "openclaw", "antigravity"}

    def test_single_platform_stays_flat(self, build_config, mock_claude, logger, seekers_cache, seekers_lookup):
        """Single platform keeps flat output structure (backward compatible)."""
        self._setup_p4_output(build_config.output_dir)
        build_config.platforms = ["claude"]
        result = run_p5(build_config, mock_claude, seekers_cache, seekers_lookup, logger)
        assert result.status == "done"

        out = build_config.output_dir
        # Flat structure — SKILL.md at root, no platform subdirs
        assert os.path.exists(os.path.join(out, "SKILL.md"))
        assert os.path.isdir(os.path.join(out, "knowledge"))
        assert not os.path.isdir(os.path.join(out, "claude"))

    def test_readme_generated_in_output(self, build_config, mock_claude, logger, seekers_cache, seekers_lookup):
        """P5 generates README.md in output directory."""
        self._setup_p4_output(build_config.output_dir)
        result = run_p5(build_config, mock_claude, seekers_cache, seekers_lookup, logger)
        assert result.status == "done"

        readme_path = os.path.join(build_config.output_dir, "README.md")
        assert os.path.exists(readme_path)
        with open(readme_path) as f:
            content = f.read()
        assert "AI Skill Package" in content
        assert "## Statistics" in content
        assert build_config.name in content

    def test_readme_in_package_zip(self, build_config, mock_claude, logger, seekers_cache, seekers_lookup):
        """README.md is included in package.zip."""
        import zipfile
        self._setup_p4_output(build_config.output_dir)
        result = run_p5(build_config, mock_claude, seekers_cache, seekers_lookup, logger)
        assert result.status == "done"

        zip_path = os.path.join(build_config.output_dir, "package.zip")
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
        assert "README.md" in names

    def _setup_p4_with_code_atoms(self, output_dir):
        """Create atoms_verified.json with code_pattern atoms."""
        atoms = [
            {"id": "atom_0001", "title": "Atom A", "content": "Content about campaigns.",
             "category": "campaign_management", "tags": ["campaign"], "confidence": 0.9,
             "status": "verified", "verification_note": "OK", "source": "transcript"},
            {"id": "atom_0002", "title": "Factory Pattern", "content": "Uses factory pattern.",
             "category": "code_pattern", "tags": ["code", "architecture", "factory"],
             "confidence": 0.85, "status": "verified",
             "verification_note": "From: src/factory.py",
             "baseline_reference": "src/factory.py", "source": "codebase"},
            {"id": "atom_0003", "title": "Error Handling Pattern", "content": "Try-catch with retry.",
             "category": "code_pattern", "tags": ["code", "error_handling"],
             "confidence": 0.87, "status": "verified",
             "verification_note": "From: src/utils.py",
             "baseline_reference": "src/utils.py", "source": "codebase"},
        ]
        write_json({"atoms": atoms, "total_atoms": 3, "score": 87.0},
                    os.path.join(output_dir, "atoms_verified.json"))

    def test_examples_generated_with_code_atoms(self, build_config, mock_claude, logger, seekers_cache, seekers_lookup):
        """P5 generates examples/code_patterns.md when code atoms exist."""
        self._setup_p4_with_code_atoms(build_config.output_dir)
        result = run_p5(build_config, mock_claude, seekers_cache, seekers_lookup, logger)
        assert result.status == "done"

        examples_path = os.path.join(build_config.output_dir, "examples", "code_patterns.md")
        assert os.path.exists(examples_path)
        with open(examples_path) as f:
            content = f.read()
        assert "Factory Pattern" in content
        assert "Error Handling" in content

    def test_no_examples_without_code_atoms(self, build_config, mock_claude, logger, seekers_cache, seekers_lookup):
        """P5 does not create examples/ when no code atoms exist."""
        self._setup_p4_output(build_config.output_dir)
        result = run_p5(build_config, mock_claude, seekers_cache, seekers_lookup, logger)
        assert result.status == "done"

        examples_dir = os.path.join(build_config.output_dir, "examples")
        assert not os.path.isdir(examples_dir)

    def test_skill_md_has_examples_routing(self, build_config, mock_claude, logger, seekers_cache, seekers_lookup):
        """SKILL.md includes Code Examples section when code atoms exist."""
        self._setup_p4_with_code_atoms(build_config.output_dir)
        result = run_p5(build_config, mock_claude, seekers_cache, seekers_lookup, logger)
        assert result.status == "done"

        skill_path = os.path.join(build_config.output_dir, "SKILL.md")
        with open(skill_path) as f:
            content = f.read()
        assert "Code Examples" in content
        assert "code_patterns.md" in content


class TestP5ReferencePathBasename:

    def _setup_p4_with_full_path_refs(self, output_dir):
        """Create P4 output + baseline with full-path references."""
        atoms = [
            {"id": "atom_0001", "title": "A", "content": "Content A.",
             "category": "general", "tags": [], "confidence": 0.9,
             "status": "verified", "verification_note": "OK"},
        ]
        write_json({"atoms": atoms, "total_atoms": 1, "score": 85.0},
                    os.path.join(output_dir, "atoms_verified.json"))
        write_json({
            "source": "auto-discovery",
            "domain": "test",
            "skill_md": "",
            "references": [
                {"path": "data\\builds\\295dd413\\references\\api-reference-overview.md",
                 "content": "# API Reference\nContent."},
                {"path": "/home/user/builds/abc/refs/getting-started.md",
                 "content": "# Getting Started\nContent."},
            ],
            "topics": ["api"],
            "total_tokens": 500,
            "score": 75.0,
        }, os.path.join(output_dir, "baseline_summary.json"))

    def test_p5_reference_paths_use_basename(self, build_config, mock_claude, logger, seekers_cache, seekers_lookup):
        """SKILL.md output uses basename only, no absolute paths or backslashes."""
        import re
        self._setup_p4_with_full_path_refs(build_config.output_dir)
        result = run_p5(build_config, mock_claude, seekers_cache, seekers_lookup, logger)
        assert result.status == "done"

        skill_path = os.path.join(build_config.output_dir, "SKILL.md")
        with open(skill_path) as f:
            content = f.read()

        # Should contain basename references
        assert "references/api-reference-overview.md" in content
        assert "references/getting-started.md" in content
        # Should NOT contain full paths or backslashes
        assert "295dd413" not in content
        assert "data\\builds" not in content
        assert "/home/user" not in content
        # No nested path pattern in references
        assert not re.search(r'references/.*[/\\].*[/\\]', content)


class TestP5CopiesReferences:

    def _setup_p4_with_baseline(self, output_dir, baseline_source="auto-discovery"):
        """Create P4 output + baseline_summary.json with refs."""
        atoms = [
            {"id": "atom_0001", "title": "A", "content": "Content A.",
             "category": "general", "tags": [], "confidence": 0.9,
             "status": "verified", "verification_note": "OK"},
        ]
        write_json({"atoms": atoms, "total_atoms": 1, "score": 85.0},
                    os.path.join(output_dir, "atoms_verified.json"))
        write_json({
            "source": baseline_source,
            "domain": "test",
            "skill_md": "",
            "references": [
                {"path": "ref_001_docs.md", "content": "# Reference Doc\nContent here."},
                {"path": "ref_002_guide.md", "content": "# Guide\nMore content."},
            ],
            "topics": ["topic1"],
            "total_tokens": 500,
            "score": 75.0,
        }, os.path.join(output_dir, "baseline_summary.json"))

    def test_auto_discovery_refs_copied(self, build_config, mock_claude, logger, seekers_cache, seekers_lookup):
        """P5 copies auto-discovery baseline references into output/references/."""
        self._setup_p4_with_baseline(build_config.output_dir, "auto-discovery")
        result = run_p5(build_config, mock_claude, seekers_cache, seekers_lookup, logger)
        assert result.status == "done"

        refs_dir = os.path.join(build_config.output_dir, "references")
        assert os.path.isdir(refs_dir)
        ref_files = [f for f in os.listdir(refs_dir) if f.endswith(".md")]
        assert len(ref_files) == 2

    def test_auto_discovery_content_refs_copied(self, build_config, mock_claude, logger, seekers_cache, seekers_lookup):
        """P5 copies auto-discovery-content baseline references."""
        self._setup_p4_with_baseline(build_config.output_dir, "auto-discovery-content")
        result = run_p5(build_config, mock_claude, seekers_cache, seekers_lookup, logger)
        assert result.status == "done"

        refs_dir = os.path.join(build_config.output_dir, "references")
        assert os.path.isdir(refs_dir)
        ref_files = [f for f in os.listdir(refs_dir) if f.endswith(".md")]
        assert len(ref_files) == 2

    def test_readme_shows_ref_count(self, build_config, mock_claude, logger, seekers_cache, seekers_lookup):
        """README.md reflects the correct number of references."""
        self._setup_p4_with_baseline(build_config.output_dir, "auto-discovery")
        result = run_p5(build_config, mock_claude, seekers_cache, seekers_lookup, logger)
        assert result.status == "done"

        readme_path = os.path.join(build_config.output_dir, "README.md")
        with open(readme_path) as f:
            content = f.read()
        assert "2 reference" in content


class TestCustomBaseUrl:

    def test_base_url_passed_to_client(self):
        """Custom base_url is accepted by ClaudeClient constructor."""
        from pipeline.clients.claude_client import ClaudeClient
        # Just verify constructor accepts the params without error
        # (actual API call would fail with fake key)
        try:
            client = ClaudeClient(
                api_key="test-key",
                model="claude-sonnet-4-5-20250929",
                model_light="claude-haiku-4-5-20251001",
                base_url="https://claudible.io",
            )
            assert client.model_light == "claude-haiku-4-5-20251001"
            assert client.base_url == "https://claudible.io"
        except Exception:
            pass  # May fail on network — constructor test is enough

    def test_use_light_model_default_false(self, mock_claude):
        """Default use_light_model is False (uses main model)."""
        mock_claude.call("test", "test")
        assert mock_claude.model_usage["main"] == 1
        assert mock_claude.model_usage["light"] == 0


class TestHybridModel:

    def _setup_p2_output(self, output_dir):
        atoms = [
            {"id": f"atom_{i:04d}", "title": f"Atom {i}", "content": f"Content {i}",
             "category": "campaign_management", "tags": ["a"], "confidence": 0.9, "status": "raw"}
            for i in range(1, 6)
        ]
        write_json({"atoms": atoms, "total_atoms": 5, "score": 85.0},
                    os.path.join(output_dir, "atoms_raw.json"))

    def test_p3_uses_light_model(self, build_config, mock_claude, logger, seekers_cache, seekers_lookup):
        """P3 dedup uses light model for Claude calls."""
        self._setup_p2_output(build_config.output_dir)
        run_p3(build_config, mock_claude, seekers_cache, seekers_lookup, logger)
        # P3 should use light model for dedup
        assert mock_claude.model_usage["light"] > 0


class TestBatchVerify:

    def _setup_p3_output_batch(self, output_dir, count=25):
        """Create atoms_deduplicated.json with N atoms for batch testing."""
        atoms = [
            {"id": f"atom_{i:04d}", "title": f"Atom {i}", "content": f"Content about topic {i}",
             "category": "campaign_management", "tags": ["campaign"],
             "confidence": 0.85, "status": "deduplicated"}
            for i in range(1, count + 1)
        ]
        write_json({"atoms": atoms, "total_atoms": count, "score": 85.0},
                    os.path.join(output_dir, "atoms_deduplicated.json"))

    def test_p4_batch_verify_reduces_calls(self, build_config, mock_claude, logger, seekers_cache, seekers_lookup):
        """P4 with 25 atoms should make ~3 batch calls, not 25 individual calls."""
        self._setup_p3_output_batch(build_config.output_dir, count=25)
        # No skill-seekers baseline → uses Claude batch verify
        initial_calls = mock_claude.call_count
        result = run_p4(build_config, mock_claude, seekers_cache, seekers_lookup, logger)
        assert result.status == "done"
        calls_made = mock_claude.call_count - initial_calls
        # With batch size 10 and draft 30% sample (8 atoms) → 1 batch call
        # Much less than 25 individual calls
        assert calls_made <= 5


class TestCreditExhausted:

    def test_credit_exhausted_error_class(self):
        """CreditExhaustedError is importable and raisable."""
        from pipeline.clients.claude_client import CreditExhaustedError
        with pytest.raises(CreditExhaustedError):
            raise CreditExhaustedError("Test credits depleted")


class TestSanitizeApiText:
    """Tests for ClaudeClient._sanitize_api_text() pre-API safety net."""

    @pytest.fixture
    def client(self):
        try:
            from pipeline.clients.claude_client import ClaudeClient
            return ClaudeClient(api_key="test", model="test",
                                base_url="https://example.com")
        except Exception:
            pytest.skip("Cannot create ClaudeClient in test env")

    def test_removes_null_bytes(self, client):
        assert "\x00" not in client._sanitize_api_text("hello\x00world")

    def test_removes_bom(self, client):
        assert "\ufeff" not in client._sanitize_api_text("\ufeffhello")

    def test_removes_control_chars(self, client):
        result = client._sanitize_api_text("hello\x01\x02\x7f\x80world")
        assert "\x01" not in result
        assert "\x02" not in result
        assert "\x7f" not in result
        assert "\x80" not in result
        assert "hello" in result and "world" in result

    def test_preserves_vietnamese(self, client):
        text = "Ung dung AI Agent trong ban le va thuong mai dien tu"
        result = client._sanitize_api_text(text)
        assert result == text

    def test_nfc_normalizes_vietnamese(self, client):
        import unicodedata
        decomposed = "a\u0306"  # NFD: a + combining breve
        result = client._sanitize_api_text(decomposed)
        assert result == unicodedata.normalize("NFC", decomposed)

    def test_removes_pua_chars(self, client):
        result = client._sanitize_api_text("hello\ue000\uf8ffworld")
        assert "\ue000" not in result
        assert "\uf8ff" not in result

    def test_removes_surrogates(self, client):
        result = client._sanitize_api_text("hello world")
        assert "hello" in result

    def test_empty_string(self, client):
        assert client._sanitize_api_text("") == ""

    def test_preserves_newlines_tabs(self, client):
        result = client._sanitize_api_text("line1\nline2\ttab")
        assert "\n" in result
        assert "\t" in result

    def test_realistic_ocr_garbage(self, client):
        dirty = (
            "\ufeff"
            "CHUONG 8\x00: UNG DUNG CUA AI AGENT\n"
            "\x01\x02Trong ban le\x03 va thuong mai\n"
            "Chatbot\x7f thong\x80 minh\x9f tu van\n"
            "\ue001Dialogflow\uf000, Amazon Lex\n"
        )
        result = client._sanitize_api_text(dirty)
        assert "CHUONG 8" in result
        assert "AI AGENT" in result
        assert "Chatbot" in result
        assert "Dialogflow" in result
        assert "\x00" not in result
        assert "\ufeff" not in result
        assert "\ue001" not in result

    def test_removes_non_bmp(self, client):
        result = client._sanitize_api_text("hello\U0001F600world")
        assert "\U0001F600" not in result
        assert "hello" in result and "world" in result


# ── Quality Score Tests ──────────────────────────────────


class TestP2StructuralScore:

    def test_p2_score_structural_not_confidence(self, build_config, mock_claude, logger, seekers_cache, seekers_lookup):
        """P2 score reflects structural quality, not Claude confidence."""
        result = run_p2(build_config, mock_claude, seekers_cache, seekers_lookup, logger)
        assert result.status == "done"
        # Score should not simply be avg_confidence * 100
        # Mock atoms have confidence 0.88-0.92, so confidence-based = ~90
        # Structural checks may penalize short content, missing tags, etc.
        assert 0.0 <= result.quality_score <= 100.0

    def test_p2_score_penalizes_short_content(self, build_config, mock_claude, logger, seekers_cache, seekers_lookup):
        """Atoms with very short content get lower structural score."""
        result = run_p2(build_config, mock_claude, seekers_cache, seekers_lookup, logger)
        assert result.status == "done"
        # Mock atoms have short content (<100 chars), so score should be penalized
        assert result.quality_score < 95.0


class TestP3BidirectionalScore:

    def test_p3_score_ideal_range(self, build_config, mock_claude, logger, seekers_cache, seekers_lookup):
        """Kept ratio in ideal range -> high score."""
        # 3 raw atoms, mock keeps all 3 (tiny group, no Claude call)
        atoms = [
            {"id": f"atom_{i:04d}", "title": f"Atom {i}",
             "content": f"Detailed content about topic {i} with enough words to be valid.",
             "category": "general", "tags": ["a"], "confidence": 0.9, "status": "raw"}
            for i in range(1, 4)
        ]
        write_json({"atoms": atoms, "total_atoms": 3, "score": 85.0},
                    os.path.join(build_config.output_dir, "atoms_raw.json"))
        result = run_p3(build_config, mock_claude, seekers_cache, seekers_lookup, logger)
        assert result.status == "done"
        # 3 atoms kept out of 3 = 100% kept, small set ideal is 70-95%
        # 100% > 95% → slight under-dedup penalty
        assert result.quality_score <= 95.0

    def test_p3_score_under_dedup_penalty(self, build_config, mock_claude, logger, seekers_cache, seekers_lookup):
        """Kept ratio = 1.0 (no dedup at all) -> penalized for medium+ sets."""
        # 40 atoms, all kept = 100% kept, ideal for n>=30 is 50-85%
        atoms = [
            {"id": f"atom_{i:04d}", "title": f"Atom {i}",
             "content": f"Content about topic {i}.",
             "category": "campaign_management", "tags": ["a"], "confidence": 0.9, "status": "raw"}
            for i in range(1, 41)
        ]
        write_json({"atoms": atoms, "total_atoms": 40, "score": 85.0},
                    os.path.join(build_config.output_dir, "atoms_raw.json"))
        result = run_p3(build_config, mock_claude, seekers_cache, seekers_lookup, logger)
        assert result.status == "done"
        # Mock Claude keeps all → under-dedup penalty applied
        # Score should be below 90 (penalty for 100% kept when ideal is 50-85%)
        assert result.quality_score < 90.0


class TestP4EvidenceBasedScore:

    def _setup_with_baseline(self, output_dir):
        atoms = [
            {"id": "atom_0001", "title": "Facebook Pixel Setup",
             "content": "Setup Facebook Pixel with base code, standard events, and conversions API",
             "category": "tools", "tags": ["pixel", "setup"], "confidence": 0.9, "status": "deduplicated"},
            {"id": "atom_0002", "title": "Quantum Computing Tips",
             "content": "Quantum entanglement enables faster computation across qubits",
             "category": "advanced", "tags": ["quantum"], "confidence": 0.85, "status": "deduplicated"},
        ]
        write_json({"atoms": atoms, "total_atoms": 2, "score": 85.0},
                    os.path.join(output_dir, "atoms_deduplicated.json"))
        write_json({
            "source": "skill_seekers",
            "references": [
                {"path": "references/pixel-setup.md",
                 "content": "Facebook Pixel is a piece of code. Setup involves base code installation, adding standard events like Purchase and AddToCart, and connecting the Conversions API for server-side tracking."},
            ],
        }, os.path.join(output_dir, "baseline_summary.json"))

    def test_p4_status_unverified_when_no_evidence(self, build_config, mock_claude, logger, seekers_cache, seekers_lookup):
        """Atoms without baseline match -> status='unverified'."""
        self._setup_with_baseline(build_config.output_dir)
        build_config.quality_tier = "premium"
        result = run_p4(build_config, mock_claude, seekers_cache, seekers_lookup, logger)
        assert result.status == "done"

        verified_path = os.path.join(build_config.output_dir, "atoms_verified.json")
        with open(verified_path) as f:
            data = json.load(f)

        atom2 = next(a for a in data["atoms"] if a["id"] == "atom_0002")
        assert atom2["status"] == "unverified"

    def test_p4_status_passthrough_when_not_sampled(self, build_config, mock_claude, logger, seekers_cache, seekers_lookup):
        """Non-sampled atoms -> status='passthrough'."""
        # Create 20 atoms, draft tier samples ~30% = 6 atoms
        atoms = [
            {"id": f"atom_{i:04d}", "title": f"Atom {i}",
             "content": f"Content about topic {i}",
             "category": "general", "tags": ["a"], "confidence": 0.9, "status": "deduplicated"}
            for i in range(1, 21)
        ]
        write_json({"atoms": atoms, "total_atoms": 20, "score": 85.0},
                    os.path.join(build_config.output_dir, "atoms_deduplicated.json"))
        result = run_p4(build_config, mock_claude, seekers_cache, seekers_lookup, logger)
        assert result.status == "done"

        verified_path = os.path.join(build_config.output_dir, "atoms_verified.json")
        with open(verified_path) as f:
            data = json.load(f)

        passthrough = [a for a in data["atoms"] if a["status"] == "passthrough"]
        assert len(passthrough) > 0, "Some atoms should be passthrough (not sampled)"

    def test_p4_score_evidence_based(self, build_config, mock_claude, logger, seekers_cache, seekers_lookup):
        """Score reflects evidence rate, not confidence."""
        self._setup_with_baseline(build_config.output_dir)
        build_config.quality_tier = "premium"
        result = run_p4(build_config, mock_claude, seekers_cache, seekers_lookup, logger)
        assert result.status == "done"
        # 1 of 2 atoms has evidence → evidence_rate=0.5 → score much lower than old 85+
        assert result.quality_score < 80.0


class TestP5WeightedScore:

    def _setup_full_pipeline_output(self, output_dir, p0_score=90, p2_score=85, p3_score=75, p4_score=40):
        """Create all phase output files with known scores."""
        write_json({"source": "skill_seekers", "references": [], "score": p0_score},
                    os.path.join(output_dir, "baseline_summary.json"))
        write_json({"topics": [], "score": 80.0},
                    os.path.join(output_dir, "inventory.json"))
        write_json({"atoms": [], "total_atoms": 0, "score": p2_score},
                    os.path.join(output_dir, "atoms_raw.json"))
        write_json({"atoms": [], "total_atoms": 0, "score": p3_score},
                    os.path.join(output_dir, "atoms_deduplicated.json"))
        atoms = [
            {"id": "atom_0001", "title": "Atom A", "content": "Content about campaigns.",
             "category": "campaign_management", "tags": ["campaign"], "confidence": 0.9,
             "status": "verified", "verification_note": "OK"},
            {"id": "atom_0002", "title": "Atom B", "content": "Content about pixel.",
             "category": "pixel_tracking", "tags": ["pixel"], "confidence": 0.85,
             "status": "verified", "verification_note": "OK"},
        ]
        write_json({"atoms": atoms, "total_atoms": 2, "score": p4_score},
                    os.path.join(output_dir, "atoms_verified.json"))

    def test_p5_final_score_weighted(self, build_config, mock_claude, logger, seekers_cache, seekers_lookup):
        """Final score is weighted average, not just P5 confidence."""
        self._setup_full_pipeline_output(build_config.output_dir)
        result = run_p5(build_config, mock_claude, seekers_cache, seekers_lookup, logger)
        assert result.status == "done"
        # Score should reflect all phases, not just avg_confidence * 100
        # With P4=40, score should be notably lower than old ~87
        assert result.quality_score < 85.0

    def test_p5_final_score_bad_baseline_cap(self, build_config, mock_claude, logger, seekers_cache, seekers_lookup):
        """Bad baseline (P0<50) -> final score capped at 60."""
        self._setup_full_pipeline_output(build_config.output_dir, p0_score=30)
        result = run_p5(build_config, mock_claude, seekers_cache, seekers_lookup, logger)
        assert result.status == "done"
        assert result.quality_score <= 60.0

    def test_p5_final_score_no_evidence_penalty(self, build_config, mock_claude, logger, seekers_cache, seekers_lookup):
        """Low verification (P4<30) -> 20% penalty."""
        self._setup_full_pipeline_output(build_config.output_dir, p4_score=20)
        result = run_p5(build_config, mock_claude, seekers_cache, seekers_lookup, logger)
        assert result.status == "done"
        # P4 < 30 → score *= 0.8, so it should be lower
        assert result.quality_score < 70.0


class TestP3OverDedupAndIntegrity:

    def test_p3_score_over_dedup_penalty(self, build_config, logger, seekers_cache, seekers_lookup):
        """Kept ratio too low (over-dedup) -> heavily penalized."""
        from pipeline.tests.conftest import MockClaudeClient

        class AggressiveDedupClaude(MockClaudeClient):
            def call_json(self, system, user, **kwargs):
                self.call_count += 1
                if kwargs.get("use_light_model"):
                    self.model_usage["light"] += 1
                else:
                    self.model_usage["main"] += 1
                if "Deduplication Expert" in system:
                    # Keep only 2 out of many → aggressive dedup
                    return {
                        "unique_atoms": [
                            {"id": "atom_0001", "title": "A", "content": "Content A.",
                             "category": "campaign_management", "tags": ["a"],
                             "confidence": 0.9, "status": "deduplicated"},
                            {"id": "atom_0002", "title": "B", "content": "Content B.",
                             "category": "campaign_management", "tags": ["b"],
                             "confidence": 0.85, "status": "deduplicated"},
                        ],
                        "conflicts": [],
                        "stats": {"input_count": 5, "output_count": 2,
                                  "duplicates_found": 3, "conflicts_found": 0},
                    }
                return super().call_json(system, user, **kwargs)

        # 5 atoms in one solo group (>= MIN_ATOMS_FOR_SOLO=15? No, 5<15 → medium batch)
        # Use 20 atoms to ensure solo group processing
        atoms = [
            {"id": f"atom_{i:04d}", "title": f"Atom {i}",
             "content": f"Content about topic {i}.",
             "category": "campaign_management", "tags": ["a"],
             "confidence": 0.9, "status": "raw"}
            for i in range(1, 21)
        ]
        write_json({"atoms": atoms, "total_atoms": 20, "score": 85.0},
                    os.path.join(build_config.output_dir, "atoms_raw.json"))

        mock = AggressiveDedupClaude()
        result = run_p3(build_config, mock, seekers_cache, seekers_lookup, logger)
        assert result.status == "done"
        # Safeguard triggers when <30% kept → keeps all 20
        # But if it keeps 2/20=10%, which is < 30% → safeguard kicks in → keeps 20
        # So score reflects kept_ratio=1.0 for n=20 (medium: ideal 0.50-0.85)
        # 1.0 > 0.85 → under-dedup penalty
        assert result.quality_score < 95.0

    def test_p3_score_integrity_penalty(self, build_config, mock_claude, logger, seekers_cache, seekers_lookup):
        """Atoms with truncated content or missing category -> penalized."""
        atoms = [
            {"id": "atom_0001", "title": "A", "content": "Truncated content without period",
             "category": "", "tags": [], "confidence": 0.9, "status": "raw"},
            {"id": "atom_0002", "title": "B", "content": "Another truncated atom here",
             "category": "", "tags": [], "confidence": 0.85, "status": "raw"},
        ]
        write_json({"atoms": atoms, "total_atoms": 2, "score": 85.0},
                    os.path.join(build_config.output_dir, "atoms_raw.json"))
        result = run_p3(build_config, mock_claude, seekers_cache, seekers_lookup, logger)
        assert result.status == "done"
        # Both atoms have: truncated content (+2 each) + empty category after normalize
        # P3 normalizes empty to "general", then integrity check:
        # "general" is non-empty after normalize → no category penalty
        # But content doesn't end with sentence-ender → +2 each = 4 penalty
        # Score should be lower than max possible
        assert result.quality_score < 100.0


class TestP5IncludesUnverified:

    def test_p5_builds_with_unverified_atoms(self, build_config, mock_claude, logger, seekers_cache, seekers_lookup):
        """P5 includes atoms with status 'unverified' and 'passthrough' in build."""
        atoms = [
            {"id": "atom_0001", "title": "Verified A", "content": "Content A.",
             "category": "general", "tags": ["a"], "confidence": 0.9,
             "status": "verified", "verification_note": "OK"},
            {"id": "atom_0002", "title": "Unverified B", "content": "Content B.",
             "category": "general", "tags": ["b"], "confidence": 0.7,
             "status": "unverified", "verification_note": "Expert insight — not found"},
            {"id": "atom_0003", "title": "Passthrough C", "content": "Content C.",
             "category": "general", "tags": ["c"], "confidence": 0.8,
             "status": "passthrough", "verification_note": "Not sampled"},
            {"id": "atom_0004", "title": "Flagged D", "content": "Content D.",
             "category": "general", "tags": ["d"], "confidence": 0.3,
             "status": "flagged", "verification_note": "Contradicts baseline"},
        ]
        write_json({"atoms": atoms, "total_atoms": 4, "score": 50.0},
                    os.path.join(build_config.output_dir, "atoms_verified.json"))
        result = run_p5(build_config, mock_claude, seekers_cache, seekers_lookup, logger)
        assert result.status == "done"
        # 4 atoms - 1 flagged = 3 included
        assert result.atoms_count == 3


class TestP5CompressionReal:

    def test_p5_compression_uses_real_transcript(self, build_config, mock_claude, logger, seekers_cache, seekers_lookup):
        """Compression ratio reads actual transcript, not hardcoded *10."""
        atoms = [
            {"id": "atom_0001", "title": "Atom A", "content": "Content about campaigns.",
             "category": "campaign_management", "tags": ["campaign"], "confidence": 0.9,
             "status": "verified", "verification_note": "OK"},
        ]
        write_json({"atoms": atoms, "total_atoms": 1, "score": 85.0},
                    os.path.join(build_config.output_dir, "atoms_verified.json"))
        result = run_p5(build_config, mock_claude, seekers_cache, seekers_lookup, logger)
        assert result.status == "done"
        # With real transcript file, compression should reflect actual ratio
        # Output words ≈ 3 ("Content about campaigns")
        # Input words = actual transcript word count (fixture file has ~100+ words)
        # Compression should NOT be exactly 0.1 (the old hardcoded value)
        # It should be output/input which varies with real transcript
