"""Adapter for skill-seekers CLI integration."""

import os
import subprocess
from pathlib import Path
from typing import Optional

from ..core.logger import PipelineLogger
from ..core.errors import SeekersError

TIMEOUT_SECONDS = 3600  # 1 hour


class SkillSeekersAdapter:
    """Wraps skill-seekers CLI to scrape docs, GitHub repos, and load baselines."""

    def __init__(self, logger: Optional[PipelineLogger] = None):
        self.logger = logger or PipelineLogger()
        self._verify_cli()

    def _verify_cli(self) -> None:
        """Check that skill-seekers CLI is installed and reachable."""
        try:
            result = subprocess.run(
                ["skill-seekers", "--version"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                raise SeekersError("skill-seekers CLI not available")
            self.logger.debug(f"skill-seekers {result.stdout.strip()}")
        except FileNotFoundError:
            raise SeekersError(
                "skill-seekers CLI not found — pip install skill-seekers"
            )

    def scrape_docs(
        self, config_path: str, output_dir: str, enhance: bool = True,
    ) -> Path:
        """Scrape documentation using a config file.

        Returns Path to output dir containing SKILL.md + references/.
        Skips scraping if SKILL.md already exists (cache hit).
        """
        output = Path(output_dir)
        skill_md = output / "SKILL.md"

        if skill_md.exists():
            self.logger.info(
                f"Cache hit: {skill_md} exists, skipping scrape"
            )
            return output

        output.mkdir(parents=True, exist_ok=True)

        cmd = ["skill-seekers", "scrape", "--config", str(config_path)]
        if enhance:
            cmd.append("--enhance")

        self._run_cli(cmd, context=f"scrape --config {config_path}")
        return output

    def scrape_github(self, repo: str, output_dir: str) -> Path:
        """Scrape a GitHub repository.

        Returns Path to output dir containing SKILL.md + references/.
        Skips scraping if SKILL.md already exists (cache hit).
        """
        output = Path(output_dir)
        skill_md = output / "SKILL.md"

        if skill_md.exists():
            self.logger.info(
                f"Cache hit: {skill_md} exists, skipping scrape"
            )
            return output

        output.mkdir(parents=True, exist_ok=True)

        name = repo.replace("/", "-")
        cmd = [
            "skill-seekers", "github",
            "--repo", repo,
            "--name", name,
            "--non-interactive",
        ]

        self._run_cli(cmd, context=f"github --repo {repo}")
        return output

    def load_baseline(self, output_dir: str) -> dict:
        """Load SKILL.md and reference files from a skill-seekers output dir.

        Returns dict with keys: skill_md, references, topics.
        """
        output = Path(output_dir)
        skill_md_path = output / "SKILL.md"

        if not skill_md_path.exists():
            raise SeekersError(f"SKILL.md not found in {output_dir}")

        skill_md = skill_md_path.read_text(encoding="utf-8")

        references = []
        refs_dir = output / "references"
        if refs_dir.is_dir():
            for ref_file in sorted(refs_dir.iterdir()):
                if not ref_file.is_file():
                    continue
                try:
                    references.append({
                        "filename": ref_file.name,
                        "content": ref_file.read_text(encoding="utf-8"),
                    })
                except (UnicodeDecodeError, OSError) as e:
                    self.logger.warn(f"Skipping {ref_file.name}: {e}")

        topics = self._extract_topics(skill_md)

        self.logger.info(
            f"Loaded baseline: SKILL.md ({len(skill_md)} chars), "
            f"{len(references)} refs, {len(topics)} topics"
        )

        return {
            "skill_md": skill_md,
            "references": references,
            "topics": topics,
        }

    def _run_cli(
        self, cmd: list[str], context: str,
    ) -> subprocess.CompletedProcess:
        """Execute a skill-seekers CLI command with timeout and error handling."""
        self.logger.info(f"Running: skill-seekers {context}")
        try:
            env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
            result = subprocess.run(
                cmd,
                capture_output=True, text=True,
                timeout=TIMEOUT_SECONDS, env=env,
            )
            if result.returncode != 0:
                self.logger.error(f"stderr: {result.stderr[:500]}")
                raise SeekersError(
                    f"skill-seekers {context} failed "
                    f"(exit {result.returncode}): {result.stderr[:200]}"
                )
            if result.stdout:
                self.logger.debug(result.stdout[:300])
            return result
        except subprocess.TimeoutExpired:
            raise SeekersError(
                f"skill-seekers {context} timed out "
                f"after {TIMEOUT_SECONDS}s"
            )
        except FileNotFoundError:
            raise SeekersError(
                "skill-seekers CLI not found — pip install skill-seekers"
            )

    def _extract_topics(self, skill_md: str) -> list[str]:
        """Extract topic headings (## and ###) from SKILL.md."""
        topics = []
        for line in skill_md.splitlines():
            if line.startswith("## ") or line.startswith("### "):
                topic = line.lstrip("#").strip()
                if topic:
                    topics.append(topic)
        return topics
