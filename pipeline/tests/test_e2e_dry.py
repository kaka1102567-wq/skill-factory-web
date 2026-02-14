"""End-to-end dry-run test — full pipeline P0→P5 with MockClaudeClient."""

import io
import json
import os
import shutil
import sys
import tempfile

import pytest

from pipeline.core.types import BuildConfig
from pipeline.core.logger import PipelineLogger
from pipeline.seekers.cache import SeekersCache
from pipeline.seekers.lookup import SeekersLookup
from pipeline.orchestrator.runner import PHASES
from pipeline.orchestrator.state import (
    save_checkpoint, load_checkpoint, should_skip_phase, update_state_with_result,
)
from pipeline.core.types import PipelineState

from pipeline.tests.conftest import MockClaudeClient


class TestE2EDryRun:
    """Run full pipeline P0→P5 without calling any real API."""

    @pytest.fixture(autouse=True)
    def setup_env(self, tmp_path):
        """Set up temp directories and config for each test."""
        self.output_dir = str(tmp_path / "output")
        self.cache_dir = str(tmp_path / "cache")
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.cache_dir, exist_ok=True)

        # Copy sample transcript
        fixtures_dir = os.path.join(os.path.dirname(__file__), "fixtures")
        transcript_src = os.path.join(fixtures_dir, "sample_transcript_vi.txt")
        self.transcript_path = str(tmp_path / "transcript.txt")
        shutil.copy2(transcript_src, self.transcript_path)

        # Write config YAML
        self.config_path = str(tmp_path / "config.yaml")
        with open(self.config_path, "w", encoding="utf-8") as f:
            f.write(
                "name: E2E Test Skill\n"
                "domain: fb_ads\n"
                "language: vi\n"
                "quality_tier: draft\n"
                "platforms:\n"
                "  - claude\n"
                "baseline_sources: []\n"
            )

        self.config = BuildConfig(
            name="E2E Test Skill",
            domain="fb_ads",
            language="vi",
            quality_tier="draft",
            platforms=["claude"],
            baseline_sources=[],
            transcript_paths=[self.transcript_path],
            output_dir=self.output_dir,
            config_path=self.config_path,
            claude_api_key="fake-key",
            claude_model="claude-sonnet-4-20250514",
            seekers_cache_dir=self.cache_dir,
        )

        self.mock_claude = MockClaudeClient()
        self.logger = PipelineLogger(build_id="e2e_test")
        self.cache = SeekersCache(self.cache_dir, ttl_hours=168)
        self.lookup = SeekersLookup(self.cache, self.logger)

    def _run_full_pipeline(self):
        """Run all 6 phases sequentially, mimicking PipelineRunner.run()."""
        state = PipelineState(build_id="e2e_test")

        for phase_id, phase_name, phase_func in PHASES:
            if should_skip_phase(state, phase_id):
                continue

            result = phase_func(
                self.config,
                self.mock_claude,
                self.cache,
                self.lookup,
                self.logger,
            )

            update_state_with_result(state, result)
            save_checkpoint(state, self.config.output_dir)

            if result.status == "failed":
                return state, 1

            if state.is_paused:
                return state, 0

        return state, 0

    def test_full_pipeline_completes(self):
        """Pipeline P0→P5 runs to completion with exit code 0."""
        state, exit_code = self._run_full_pipeline()
        assert exit_code == 0, f"Pipeline failed at phase {state.current_phase}"
        assert state.current_phase == "p5"
        assert not state.is_paused

    def test_all_phases_recorded_in_state(self):
        """Every phase P0-P5 has a result in the checkpoint."""
        state, _ = self._run_full_pipeline()
        for phase_id in ["p0", "p1", "p2", "p3", "p4", "p5"]:
            assert phase_id in state.phase_results, f"Missing result for {phase_id}"
            assert state.phase_results[phase_id]["status"] == "done"

    def test_checkpoint_saved_and_loadable(self):
        """state.json is written and can be loaded back."""
        self._run_full_pipeline()
        loaded = load_checkpoint(self.output_dir)
        assert loaded is not None
        assert loaded.build_id == "e2e_test"
        assert loaded.current_phase == "p5"

    def test_output_files_exist(self):
        """All intermediate and final output files are created."""
        self._run_full_pipeline()

        expected_files = [
            # baseline_summary.json only created when baseline_sources is non-empty
            "inventory.json",
            "atoms_raw.json",
            "atoms_deduplicated.json",
            "conflicts.json",
            "atoms_verified.json",
            "SKILL.md",
            "metadata.json",
            "package.zip",
            "state.json",
        ]
        for fname in expected_files:
            fpath = os.path.join(self.output_dir, fname)
            assert os.path.exists(fpath), f"Missing output: {fname}"

    def test_knowledge_dir_has_md_files(self):
        """knowledge/ directory is created with .md files per pillar."""
        self._run_full_pipeline()
        knowledge_dir = os.path.join(self.output_dir, "knowledge")
        assert os.path.isdir(knowledge_dir)
        md_files = [f for f in os.listdir(knowledge_dir) if f.endswith(".md")]
        assert len(md_files) > 0, "No knowledge .md files generated"

    def test_atoms_raw_has_valid_structure(self):
        """atoms_raw.json contains atoms with IDs and required fields."""
        self._run_full_pipeline()
        with open(os.path.join(self.output_dir, "atoms_raw.json")) as f:
            data = json.load(f)
        assert "atoms" in data
        assert data["total_atoms"] > 0
        for atom in data["atoms"]:
            assert atom["id"].startswith("atom_")
            assert "title" in atom
            assert "content" in atom
            assert "category" in atom

    def test_atoms_verified_has_status(self):
        """atoms_verified.json atoms all have a verification status."""
        self._run_full_pipeline()
        with open(os.path.join(self.output_dir, "atoms_verified.json")) as f:
            data = json.load(f)
        for atom in data["atoms"]:
            assert atom["status"] in ("verified", "updated", "flagged")

    def test_metadata_json_structure(self):
        """metadata.json has correct fields."""
        self._run_full_pipeline()
        with open(os.path.join(self.output_dir, "metadata.json")) as f:
            meta = json.load(f)
        assert meta["name"] == "E2E Test Skill"
        assert meta["domain"] == "fb_ads"
        assert meta["language"] == "vi"
        assert "pillars" in meta
        assert meta["atoms_included"] > 0

    def test_package_zip_is_valid(self):
        """package.zip is a valid zip file with contents."""
        import zipfile
        self._run_full_pipeline()
        zip_path = os.path.join(self.output_dir, "package.zip")
        assert zipfile.is_zipfile(zip_path)
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            assert any("SKILL.md" in n for n in names)

    def test_stdout_emits_valid_json_events(self, capsys):
        """All stdout output is parseable JSON with 'event' field."""
        self._run_full_pipeline()
        captured = capsys.readouterr()
        lines = [l for l in captured.out.strip().split("\n") if l.strip()]
        assert len(lines) > 0, "No stdout output captured"

        events_seen = set()
        for line in lines:
            parsed = json.loads(line)
            assert "event" in parsed
            events_seen.add(parsed["event"])

        # Must have seen these event types
        assert "phase" in events_seen
        assert "log" in events_seen
        assert "quality" in events_seen
        assert "package" in events_seen

    def test_phase_events_cover_all_phases(self, capsys):
        """Phase events emitted for every phase p0-p5."""
        self._run_full_pipeline()
        captured = capsys.readouterr()

        phase_events = []
        for line in captured.out.strip().split("\n"):
            if not line.strip():
                continue
            parsed = json.loads(line)
            if parsed.get("event") == "phase":
                phase_events.append(parsed)

        # Each phase should have at least a "running" and "done" event
        phases_started = {e["phase"] for e in phase_events if e["status"] == "running"}
        phases_done = {e["phase"] for e in phase_events if e["status"] == "done"}

        for pid in ["p0", "p1", "p2", "p3", "p4", "p5"]:
            assert pid in phases_started, f"Phase {pid} never started"
            assert pid in phases_done, f"Phase {pid} never completed"
