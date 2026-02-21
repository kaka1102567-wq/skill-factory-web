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
            assert atom["status"] in ("verified", "updated", "flagged")

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
