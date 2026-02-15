"""Tests for SkillSeekersAdapter."""

import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import subprocess

from pipeline.seekers.adapter import SkillSeekersAdapter, TIMEOUT_SECONDS
from pipeline.core.errors import SeekersError
from pipeline.core.logger import PipelineLogger


PYTHON3_TEST_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "output", "python3-test"
)


@pytest.fixture
def logger():
    return PipelineLogger(build_id="test_adapter")


@pytest.fixture
def adapter(logger):
    return SkillSeekersAdapter(logger=logger)


@pytest.fixture
def tmp_dir():
    d = tempfile.mkdtemp(prefix="adapter_test_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


# ── load_baseline ──────────────────────────────────────


class TestLoadBaseline:
    """Test load_baseline using real output/python3-test/ data."""

    @pytest.mark.skipif(
        not os.path.exists(PYTHON3_TEST_DIR),
        reason="output/python3-test/ not found — run scrape first",
    )
    def test_load_baseline_real_data(self, adapter):
        result = adapter.load_baseline(PYTHON3_TEST_DIR)

        assert "skill_md" in result
        assert "references" in result
        assert "topics" in result

        assert len(result["skill_md"]) > 0
        assert "SKILL" in result["skill_md"] or "Skill" in result["skill_md"]

        assert isinstance(result["references"], list)
        assert len(result["references"]) > 0
        for ref in result["references"]:
            assert "filename" in ref
            assert "content" in ref

        assert isinstance(result["topics"], list)
        assert len(result["topics"]) > 0

    def test_load_baseline_synthetic(self, adapter, tmp_dir):
        skill_md = Path(tmp_dir) / "SKILL.md"
        skill_md.write_text(
            "# Test\n## Topic One\nContent.\n### Sub Topic\nMore.\n",
            encoding="utf-8",
        )
        refs_dir = Path(tmp_dir) / "references"
        refs_dir.mkdir()
        (refs_dir / "guide.md").write_text("Guide content", encoding="utf-8")

        result = adapter.load_baseline(tmp_dir)

        assert result["skill_md"].startswith("# Test")
        assert len(result["references"]) == 1
        assert result["references"][0]["filename"] == "guide.md"
        assert result["topics"] == ["Topic One", "Sub Topic"]

    def test_load_baseline_missing_skill_md(self, adapter, tmp_dir):
        with pytest.raises(SeekersError, match="SKILL.md not found"):
            adapter.load_baseline(tmp_dir)

    def test_load_baseline_no_references_dir(self, adapter, tmp_dir):
        (Path(tmp_dir) / "SKILL.md").write_text("# Skill\n", encoding="utf-8")
        result = adapter.load_baseline(tmp_dir)
        assert result["references"] == []


# ── scrape_docs cache ──────────────────────────────────


class TestScrapeDocsCache:
    """Test that scrape_docs skips when SKILL.md exists."""

    def test_scrape_docs_with_cache(self, adapter, tmp_dir):
        skill_md = Path(tmp_dir) / "SKILL.md"
        skill_md.write_text("# Cached skill\n", encoding="utf-8")

        with patch.object(adapter, "_run_cli") as mock_cli:
            result = adapter.scrape_docs("fake_config.json", tmp_dir)

            mock_cli.assert_not_called()
            assert result == Path(tmp_dir)

    def test_scrape_github_with_cache(self, adapter, tmp_dir):
        skill_md = Path(tmp_dir) / "SKILL.md"
        skill_md.write_text("# Cached skill\n", encoding="utf-8")

        with patch.object(adapter, "_run_cli") as mock_cli:
            result = adapter.scrape_github("owner/repo", tmp_dir)

            mock_cli.assert_not_called()
            assert result == Path(tmp_dir)


# ── timeout handling ───────────────────────────────────


class TestTimeout:
    """Test that CLI timeout raises SeekersError."""

    def test_scrape_docs_timeout(self, adapter, tmp_dir):
        with patch("pipeline.seekers.adapter.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(
                cmd=["skill-seekers"], timeout=TIMEOUT_SECONDS,
            )
            with pytest.raises(SeekersError, match="timed out"):
                adapter._run_cli(
                    ["skill-seekers", "scrape", "--config", "x.json"],
                    context="scrape --config x.json",
                )

    def test_cli_not_found(self, adapter, tmp_dir):
        with patch("pipeline.seekers.adapter.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            with pytest.raises(SeekersError, match="not found"):
                adapter._run_cli(
                    ["skill-seekers", "scrape"],
                    context="scrape",
                )

    def test_cli_nonzero_exit(self, adapter):
        with patch("pipeline.seekers.adapter.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=["skill-seekers"], returncode=1,
                stdout="", stderr="Some error occurred",
            )
            with pytest.raises(SeekersError, match="failed"):
                adapter._run_cli(
                    ["skill-seekers", "scrape"],
                    context="scrape",
                )
