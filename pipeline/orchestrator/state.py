"""Checkpoint/resume state manager for pipeline runs."""

import os
from ..core.types import PipelineState, PhaseResult


CHECKPOINT_FILE = "state.json"


def save_checkpoint(state: PipelineState, output_dir: str) -> str:
    """Save pipeline state to output_dir/state.json."""
    path = os.path.join(output_dir, CHECKPOINT_FILE)
    os.makedirs(output_dir, exist_ok=True)
    state.checkpoint_path = path
    state.save(path)
    return path


def load_checkpoint(output_dir: str) -> PipelineState | None:
    """Load pipeline state from output_dir/state.json. Returns None if not found."""
    path = os.path.join(output_dir, CHECKPOINT_FILE)
    if not os.path.exists(path):
        return None
    try:
        return PipelineState.load(path)
    except Exception:
        return None


def should_skip_phase(state: PipelineState | None, phase_id: str) -> bool:
    """Return True if phase already completed in a previous run."""
    if state is None:
        return False
    result = state.phase_results.get(phase_id)
    if not result:
        return False
    # Skip only if status is "done" — retry failed/skipped phases
    if isinstance(result, dict):
        return result.get("status") == "done"
    return False


def update_state_with_result(state: PipelineState, result: PhaseResult) -> None:
    """Update pipeline state after a phase completes."""
    state.current_phase = result.phase_id
    state.phase_results[result.phase_id] = result.to_dict()
    state.total_cost_usd += result.api_cost_usd
    state.total_tokens += result.tokens_used

    # Check if P3 detected unresolved conflicts
    if result.phase_id == "p3" and result.metrics.get("is_paused"):
        state.is_paused = True
        state.pause_reason = (
            f"{result.metrics.get('conflicts_unresolved', 0)} unresolved conflicts"
        )
