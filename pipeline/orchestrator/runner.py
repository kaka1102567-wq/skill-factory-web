"""Main pipeline runner — sequences P0 through P5."""

import os
import uuid
from datetime import datetime, timezone

from ..core.types import BuildConfig, PipelineState
from ..core.logger import PipelineLogger
from ..core.errors import PipelineError
from ..clients.claude_client import ClaudeClient
from ..seekers.cache import SeekersCache
from ..seekers.lookup import SeekersLookup
from ..phases.p0_baseline import run_p0
from ..phases.p1_audit import run_p1
from ..phases.p2_extract import run_p2
from ..phases.p3_dedup import run_p3
from ..phases.p4_verify import run_p4
from ..phases.p5_build import run_p5
from .state import (
    save_checkpoint, load_checkpoint,
    should_skip_phase, update_state_with_result,
)


PHASES = [
    ("p0", "Baseline", run_p0),
    ("p1", "Audit", run_p1),
    ("p2", "Extract", run_p2),
    ("p3", "Deduplicate", run_p3),
    ("p4", "Verify", run_p4),
    ("p5", "Build", run_p5),
]


class PipelineRunner:
    def __init__(self, config: BuildConfig):
        self.config = config
        self.build_id = f"build_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        self.logger = PipelineLogger(build_id=self.build_id)

        # Ensure output dir
        os.makedirs(config.output_dir, exist_ok=True)

        # Initialize Claude client (may raise if no API key)
        self.claude = None
        if config.claude_api_key:
            self.claude = ClaudeClient(
                api_key=config.claude_api_key,
                model=config.claude_model,
                logger=self.logger,
                cache_dir=os.path.join(config.seekers_cache_dir, "claude"),
            )

        # Initialize Seekers
        self.cache = SeekersCache(
            config.seekers_cache_dir,
            config.seekers_cache_ttl_hours,
        )
        self.lookup = SeekersLookup(self.cache, self.logger)

    def run(self) -> int:
        """Run the full pipeline P0→P5.

        Returns exit code: 0=success, 1=failed, 2=paused (conflicts).
        """
        self.logger.info(f"Pipeline started: {self.config.name} (build {self.build_id})")
        self.logger.info(f"Domain: {self.config.domain}, Tier: {self.config.quality_tier}")
        self.logger.debug(f"Output dir: {self.config.output_dir}")
        self.logger.debug(f"Config path: {self.config.config_path}")
        self.logger.debug(f"Transcripts found: {len(self.config.transcript_paths)}")
        for tp in self.config.transcript_paths:
            self.logger.debug(f"  transcript: {tp}")

        # Load or create state
        state = load_checkpoint(self.config.output_dir)
        if state:
            self.logger.info(f"Resuming from checkpoint: phase {state.current_phase}")
        else:
            state = PipelineState(build_id=self.build_id)

        for phase_id, phase_name, phase_func in PHASES:
            # Skip completed phases
            if should_skip_phase(state, phase_id):
                self.logger.info(f"Skipping {phase_name} (already done)")
                continue

            # P1+ require Claude client
            if phase_id != "p0" and self.claude is None:
                self.logger.error(
                    f"Cannot run {phase_name}: CLAUDE_API_KEY not set",
                    phase=phase_id,
                )
                return 1

            # Run phase
            result = phase_func(
                self.config,
                self.claude,
                self.cache,
                self.lookup,
                self.logger,
            )

            # Update state and checkpoint
            update_state_with_result(state, result)
            save_checkpoint(state, self.config.output_dir)

            # Phase failed → stop
            if result.status == "failed":
                self.logger.error(
                    f"Pipeline stopped: {phase_name} failed — {result.error_message}"
                )
                return 1

            # P3 conflicts → pause for review
            # Exit 0 so build-runner.ts sees "completed" — the conflict event
            # already set status="paused" on the TS side (line 227-234)
            if state.is_paused:
                self.logger.info(
                    f"Pipeline paused: {state.pause_reason}. "
                    "Waiting for conflict review."
                )
                return 0

        # All phases complete
        self.logger.info(
            f"Pipeline complete! Total cost: ${state.total_cost_usd:.4f}, "
            f"Tokens: {state.total_tokens}"
        )
        return 0

    def resume_after_resolve(self, resolutions: dict) -> int:
        """Resume pipeline after conflict resolution.

        Applies resolutions to atoms_deduplicated.json, then runs P4→P5.
        """
        self.logger.info("Resuming pipeline after conflict resolution")

        state = load_checkpoint(self.config.output_dir)
        if not state:
            self.logger.error("No checkpoint found — cannot resume")
            return 1

        # Apply resolutions to deduplicated atoms
        _apply_resolutions(self.config.output_dir, resolutions, self.logger)

        # Clear pause state
        state.is_paused = False
        state.pause_reason = None

        # Run remaining phases (P4, P5)
        resume_phases = [p for p in PHASES if p[0] in ("p4", "p5")]

        for phase_id, phase_name, phase_func in resume_phases:
            if should_skip_phase(state, phase_id):
                self.logger.info(f"Skipping {phase_name} (already done)")
                continue

            result = phase_func(
                self.config,
                self.claude,
                self.cache,
                self.lookup,
                self.logger,
            )

            update_state_with_result(state, result)
            save_checkpoint(state, self.config.output_dir)

            if result.status == "failed":
                self.logger.error(
                    f"Pipeline stopped: {phase_name} failed — {result.error_message}"
                )
                return 1

        self.logger.info(
            f"Pipeline complete! Total cost: ${state.total_cost_usd:.4f}, "
            f"Tokens: {state.total_tokens}"
        )
        return 0


def _apply_resolutions(output_dir: str, resolutions: dict, logger: PipelineLogger) -> None:
    """Apply conflict resolutions to atoms_deduplicated.json."""
    from ..core.utils import read_json, write_json

    dedup_path = os.path.join(output_dir, "atoms_deduplicated.json")
    try:
        data = read_json(dedup_path)
    except FileNotFoundError:
        logger.warn("atoms_deduplicated.json not found — skipping resolution apply")
        return

    atoms = data.get("atoms", [])
    atoms_by_id = {a.get("id"): a for a in atoms}

    for conflict_id, resolution in resolutions.items():
        action = resolution.get("action", "keep_a")
        atom_a_id = resolution.get("atom_a_id")
        atom_b_id = resolution.get("atom_b_id")

        if action == "keep_a" and atom_b_id in atoms_by_id:
            del atoms_by_id[atom_b_id]
        elif action == "keep_b" and atom_a_id in atoms_by_id:
            del atoms_by_id[atom_a_id]
        elif action == "merge" and resolution.get("merged_content"):
            if atom_a_id in atoms_by_id:
                atoms_by_id[atom_a_id]["content"] = resolution["merged_content"]
                atoms_by_id[atom_a_id]["status"] = "deduplicated"
            if atom_b_id in atoms_by_id:
                del atoms_by_id[atom_b_id]
        elif action == "discard":
            atoms_by_id.pop(atom_a_id, None)
            atoms_by_id.pop(atom_b_id, None)

    resolved_atoms = list(atoms_by_id.values())
    data["atoms"] = resolved_atoms
    data["total_atoms"] = len(resolved_atoms)
    write_json(data, dedup_path)

    logger.info(f"Applied {len(resolutions)} resolutions → {len(resolved_atoms)} atoms remain")
