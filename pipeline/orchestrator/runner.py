"""Main pipeline runner — sequences P0 through P6."""

import json
import os
import uuid
from datetime import datetime

from ..core.types import BuildConfig, PipelineState, PHASE_MODEL_MAP
from ..core.embeddings import EmbeddingClient
from ..core.logger import PipelineLogger
from ..core.utils import read_json, write_json
from ..clients.claude_client import ClaudeClient, CreditExhaustedError
from ..seekers.cache import SeekersCache
from ..seekers.lookup import SeekersLookup
from ..phases.p0_baseline import run_p0
from ..phases.p1_audit import run_p1
from ..phases.p2_extract import run_p2
from ..phases.p3_dedup import run_p3
from ..phases.p4_verify import run_p4
from ..phases.p5_build import run_p5
from ..phases.p6_optimize import run_p6
from ..phases.p55_smoke_test import run_p55
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
    ("p6", "Optimize", run_p6),
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
                model_light=config.claude_model_light,
                base_url=config.claude_base_url or None,
                logger=self.logger,
                cache_dir=os.path.join(config.seekers_cache_dir, "claude"),
                base_url_light=config.claude_base_url_light or None,
                api_key_light=config.claude_api_key_light or None,
                model_premium=config.claude_model_premium or None,
            )

        # Initialize EmbeddingClient (always created; falls back to TF-IDF if no key)
        embedding_client = EmbeddingClient(
            api_key=config.embedding_api_key,
            model=config.embedding_model,
            base_url=config.embedding_base_url,
        )
        config.embedding_client = embedding_client  # type: ignore[attr-defined]

        # Initialize Seekers
        self.cache = SeekersCache(
            config.seekers_cache_dir,
            config.seekers_cache_ttl_hours,
        )
        self.lookup = SeekersLookup(self.cache, self.logger)

    def run(self) -> int:
        """Run the full pipeline P0→P6.

        Returns exit code: 0=success, 1=failed, 2=paused (conflicts).
        """
        self.logger.info(f"Pipeline bắt đầu: {self.config.name} (build {self.build_id})")
        self.logger.info(f"Domain: {self.config.domain}, Tier: {self.config.quality_tier}")
        self.logger.debug(f"Thư mục output: {self.config.output_dir}")
        self.logger.debug(f"Đường dẫn config: {self.config.config_path}")
        self.logger.debug(f"Transcripts tìm thấy: {len(self.config.transcript_paths)}")
        for tp in self.config.transcript_paths:
            self.logger.debug(f"  transcript: {tp}")

        # Load or create state
        state = load_checkpoint(self.config.output_dir)
        if state:
            self.logger.info(f"Tiếp tục từ checkpoint: phase {state.current_phase}")
        else:
            state = PipelineState(build_id=self.build_id)

        # Initialize model hints from quality tier
        model_map = PHASE_MODEL_MAP.get(
            self.config.quality_tier, PHASE_MODEL_MAP["standard"]
        )
        self.config.phase_model_hints = model_map

        try:
            for phase_id, phase_name, phase_func in PHASES:
                # Skip completed phases
                if should_skip_phase(state, phase_id):
                    self.logger.info(f"Bỏ qua {phase_name} (đã hoàn thành)")
                    continue

                # P1+ require Claude client
                if phase_id != "p0" and self.claude is None:
                    self.logger.error(
                        f"Không thể chạy {phase_name}: CLAUDE_API_KEY chưa được đặt",
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
                        f"Pipeline dừng: {phase_name} thất bại — {result.error_message}"
                    )
                    return 1

                # P3 conflicts → pause for review
                # Exit 0 so build-runner.ts sees "completed" — the conflict event
                # already set status="paused" on the TS side (line 227-234)
                if state.is_paused:
                    self.logger.info(
                        f"Pipeline tạm dừng: {state.pause_reason}. "
                        "Đang chờ xem xét xung đột."
                    )
                    return 0

                # P55 Smoke Test — inline after P5 (non-blocking sub-step)
                if phase_id == "p5" and result.status == "done":
                    try:
                        p55_result = run_p55(
                            self.config, self.claude, self.cache, self.lookup, self.logger
                        )
                        update_state_with_result(state, p55_result)
                        save_checkpoint(state, self.config.output_dir)
                    except Exception as e:
                        self.logger.warn(f"Lỗi smoke test (không nghiêm trọng): {e}")

        except CreditExhaustedError as e:
            self.logger.error(str(e))
            self.logger.error(
                "Pipeline dừng. Vui lòng thêm credit API, sau đó thử lại build này."
            )
            save_checkpoint(state, self.config.output_dir)
            return 1

        # Compute and emit final score after all phases
        _emit_final_score(self.config, state, self.logger)

        # All phases complete
        self.logger.info(
            f"Pipeline hoàn thành! Tổng chi phí: ${state.total_cost_usd:.4f}, "
            f"Tokens: {state.total_tokens}"
        )
        return 0

    def resume_after_resolve(self, resolutions: dict) -> int:
        """Resume pipeline after conflict resolution.

        Applies resolutions to atoms_deduplicated.json, then runs P4→P5.
        """
        self.logger.info("Tiếp tục pipeline sau khi giải quyết xung đột")

        state = load_checkpoint(self.config.output_dir)
        if not state:
            self.logger.error("Không tìm thấy checkpoint — không thể tiếp tục")
            return 1

        # Apply resolutions to deduplicated atoms
        _apply_resolutions(self.config.output_dir, resolutions, self.logger)

        # Clear pause state
        state.is_paused = False
        state.pause_reason = None

        # Run remaining phases (P4, P5, P6)
        resume_phases = [p for p in PHASES if p[0] in ("p4", "p5", "p6")]

        for phase_id, phase_name, phase_func in resume_phases:
            if should_skip_phase(state, phase_id):
                self.logger.info(f"Bỏ qua {phase_name} (đã hoàn thành)")
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
                    f"Pipeline dừng: {phase_name} thất bại — {result.error_message}"
                )
                return 1

            # P55 Smoke Test — inline after P5 (non-blocking sub-step)
            if phase_id == "p5" and result.status == "done":
                try:
                    p55_result = run_p55(
                        self.config, self.claude, self.cache, self.lookup, self.logger
                    )
                    update_state_with_result(state, p55_result)
                    save_checkpoint(state, self.config.output_dir)
                except Exception as e:
                    self.logger.warn(f"Lỗi smoke test (không nghiêm trọng): {e}")

        _emit_final_score(self.config, state, self.logger)

        self.logger.info(
            f"Pipeline hoàn thành! Tổng chi phí: ${state.total_cost_usd:.4f}, "
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
        logger.warn("atoms_deduplicated.json không tìm thấy — bỏ qua áp dụng resolution")
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

    logger.info(f"Đã áp dụng {len(resolutions)} resolutions → còn lại {len(resolved_atoms)} atoms")


def _emit_final_score(config: BuildConfig, state: PipelineState,
                      logger: PipelineLogger) -> None:
    """Compute final score: Pipeline×0.6 + SmokeTestAvg×0.3 + TriggerTest×0.1

    Reads P5 quality_score, smoke_test_report.json, and p6_optimization_report.json
    from the output directory. Emits a 'final_score' log event for build-runner.ts.
    """
    out = config.output_dir

    # Pipeline score from P5 result
    p5_data = state.phase_results.get("p5", {})
    pipeline_score = p5_data.get("quality_score", 0.0)

    # Smoke test average score (0-100 scale)
    smoke_avg = 0.0
    try:
        smoke = read_json(os.path.join(out, "smoke_test_report.json"))
        smoke_avg = float(smoke.get("score", 0)) * 100  # stored as 0-1
    except Exception:
        pass

    # Trigger test score from P6 (use best_test_score, 0-100 scale)
    trigger_score = 0.0
    try:
        p6 = read_json(os.path.join(out, "p6_optimization_report.json"))
        trigger_score = float(p6.get("best_test_score", 0)) * 100  # stored as 0-1
    except Exception:
        pass

    final = pipeline_score * 0.6 + smoke_avg * 0.3 + trigger_score * 0.1
    final = min(100.0, max(0.0, round(final, 1)))

    logger.info(
        f"Final Score: pipeline={pipeline_score:.1f}*0.6 + "
        f"smoke={smoke_avg:.1f}*0.3 + trigger={trigger_score:.1f}*0.1 "
        f"= {final}",
        phase="final",
    )

    # Emit structured event for build-runner.ts to parse
    logger._emit({
        "event": "final_score",
        "final_score": final,
        "pipeline_score": round(pipeline_score, 1),
        "smoke_test_avg": round(smoke_avg, 1),
        "trigger_test_score": round(trigger_score, 1),
    })

    # ── Quality Recommendation ──
    if final >= 80:
        grade, verdict = "A", "Production-ready"
    elif final >= 65:
        grade, verdict = "B", "Usable — minor improvements possible"
    elif final >= 50:
        grade, verdict = "C", "Usable with caveats — consider rebuilding"
    elif final >= 35:
        grade, verdict = "D", "Below standard — rebuild recommended"
    else:
        grade, verdict = "F", "Not usable — needs significant rework"

    strengths = []
    weaknesses = []

    if pipeline_score >= 80:
        strengths.append(f"Strong pipeline quality ({pipeline_score:.0f}/100)")
    elif pipeline_score < 60:
        weaknesses.append(f"Low pipeline quality ({pipeline_score:.0f}/100)")

    if smoke_avg >= 70:
        strengths.append(f"Good smoke test results ({smoke_avg:.0f}%)")
    elif smoke_avg > 0 and smoke_avg < 50:
        weaknesses.append(
            f"Low smoke test ({smoke_avg:.0f}%) — skill may answer incorrectly"
        )
    elif smoke_avg == 0:
        weaknesses.append("No smoke test results — quality unverified")

    if trigger_score >= 80:
        strengths.append(f"Excellent trigger accuracy ({trigger_score:.0f}%)")
    elif trigger_score > 0 and trigger_score < 60:
        weaknesses.append(
            f"Low trigger accuracy ({trigger_score:.0f}%) — skill may not activate"
        )

    recommendation = {
        "composite_score": final,
        "grade": grade,
        "verdict": verdict,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "components": {
            "pipeline_score": round(pipeline_score, 1),
            "smoke_test_avg": round(smoke_avg, 1),
            "trigger_test_score": round(trigger_score, 1),
        },
    }

    # Write recommendation into existing metadata.json
    meta_path = os.path.join(out, "metadata.json")
    try:
        meta = read_json(meta_path)
        meta["quality_recommendation"] = recommendation
        write_json(meta, meta_path)
        logger.info(
            f"Quality: {grade} ({final:.1f}) — {verdict}",
            phase="final",
        )
    except Exception as e:
        logger.warn(f"Could not update metadata.json with recommendation: {e}")

    # Emit recommendation event
    logger._emit({
        "event": "quality_recommendation",
        "recommendation": recommendation,
    })
