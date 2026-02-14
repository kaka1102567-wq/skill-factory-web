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
