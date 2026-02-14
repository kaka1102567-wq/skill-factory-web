"""JSON stdout logger compatible with Next.js build-runner.ts SSE streaming."""

import json
import sys
import time
from typing import Optional


class PipelineLogger:
    """
    Emits JSON lines to stdout that build-runner.ts parses.

    Event types handled by build-runner.ts:
    - "phase"    → updates phase stepper UI
    - "log"      → appends to live log panel
    - "quality"  → updates quality scores
    - "cost"     → updates cost tracker
    - "conflict" → pauses build for review
    - "package"  → enables download button
    """

    def __init__(self, build_id: str = ""):
        self.build_id = build_id
        self._start = time.time()

    def _emit(self, data: dict) -> None:
        print(json.dumps(data, ensure_ascii=False), flush=True)

    # ── Phase events ──

    def phase_start(self, phase: str, name: str, tool: str = "Claude") -> None:
        self._emit({"event": "phase", "phase": phase, "name": name,
                     "status": "running", "progress": 0})
        self.info(f"▶ Starting {name} phase ({tool})...", phase=phase)

    def phase_progress(self, phase: str, name: str, progress: int) -> None:
        self._emit({"event": "phase", "phase": phase, "name": name,
                     "status": "running", "progress": max(0, min(100, progress))})

    def phase_complete(self, phase: str, name: str, score: float = 0, atoms_count: int = 0) -> None:
        self._emit({"event": "quality", "phase": phase, "score": round(score, 1),
                     "pass": score >= 70.0, "atoms_count": atoms_count})
        self._emit({"event": "phase", "phase": phase, "name": name,
                     "status": "done", "progress": 100})
        self.info(f"✅ {name} complete — {atoms_count} atoms, score {score:.1f}%", phase=phase)

    def phase_failed(self, phase: str, name: str, error: str) -> None:
        self._emit({"event": "phase", "phase": phase, "name": name,
                     "status": "failed", "progress": 0})
        self.error(f"❌ {name} failed: {error}", phase=phase)

    # ── Log events ──

    def info(self, msg: str, phase: Optional[str] = None) -> None:
        self._emit({"event": "log", "level": "info", "phase": phase, "message": msg})

    def warn(self, msg: str, phase: Optional[str] = None) -> None:
        self._emit({"event": "log", "level": "warn", "phase": phase, "message": msg})

    def error(self, msg: str, phase: Optional[str] = None) -> None:
        self._emit({"event": "log", "level": "error", "phase": phase, "message": msg})

    def debug(self, msg: str, phase: Optional[str] = None) -> None:
        self._emit({"event": "log", "level": "debug", "phase": phase, "message": msg})

    # ── Cost ──

    def report_cost(self, usd: float, tokens: int) -> None:
        self._emit({"event": "cost", "api_cost_usd": round(usd, 4), "tokens_used": tokens})

    # ── Quality aggregate ──

    def report_quality(self, quality_score: float, atoms_extracted: int,
                       atoms_deduplicated: int, atoms_verified: int,
                       compression_ratio: float) -> None:
        self._emit({"event": "quality", "quality_score": round(quality_score, 1),
                     "atoms_extracted": atoms_extracted,
                     "atoms_deduplicated": atoms_deduplicated,
                     "atoms_verified": atoms_verified,
                     "compression_ratio": round(compression_ratio, 4)})

    # ── Conflict ──

    def report_conflicts(self, conflicts: list[dict]) -> None:
        self._emit({"event": "conflict", "conflicts": conflicts, "count": len(conflicts)})

    # ── Package ──

    def report_package(self, zip_path: str, output_dir: str) -> None:
        self._emit({"event": "package", "path": zip_path, "output_dir": output_dir})
