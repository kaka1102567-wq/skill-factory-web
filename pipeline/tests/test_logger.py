"""Tests for PipelineLogger JSON output format."""

import json
import io
import sys

from pipeline.core.logger import PipelineLogger


def _capture_logger_output(fn):
    """Capture stdout from a logger call, return parsed JSON lines."""
    old_stdout = sys.stdout
    sys.stdout = buf = io.StringIO()
    try:
        fn()
    finally:
        sys.stdout = old_stdout
    lines = [l for l in buf.getvalue().strip().split("\n") if l.strip()]
    return [json.loads(l) for l in lines]


class TestLoggerEvents:

    def test_phase_start_emits_phase_and_log(self):
        logger = PipelineLogger(build_id="test")
        events = _capture_logger_output(
            lambda: logger.phase_start("p0", "Baseline", tool="Seekers")
        )
        assert len(events) == 2
        # First: phase event
        assert events[0]["event"] == "phase"
        assert events[0]["phase"] == "p0"
        assert events[0]["name"] == "Baseline"
        assert events[0]["status"] == "running"
        assert events[0]["progress"] == 0
        # Second: log event
        assert events[1]["event"] == "log"
        assert events[1]["level"] == "info"

    def test_phase_progress_clamps_0_100(self):
        logger = PipelineLogger()
        events = _capture_logger_output(
            lambda: logger.phase_progress("p1", "Audit", 150)
        )
        assert events[0]["progress"] == 100

        events = _capture_logger_output(
            lambda: logger.phase_progress("p1", "Audit", -10)
        )
        assert events[0]["progress"] == 0

    def test_phase_complete_emits_quality_and_phase(self):
        logger = PipelineLogger()
        events = _capture_logger_output(
            lambda: logger.phase_complete("p2", "Extract", score=88.5, atoms_count=47)
        )
        assert len(events) == 3
        # Quality event
        assert events[0]["event"] == "quality"
        assert events[0]["phase"] == "p2"
        assert events[0]["score"] == 88.5
        assert events[0]["pass"] is True
        assert events[0]["atoms_count"] == 47
        # Phase done
        assert events[1]["event"] == "phase"
        assert events[1]["status"] == "done"
        assert events[1]["progress"] == 100

    def test_phase_failed_emits_phase_and_error(self):
        logger = PipelineLogger()
        events = _capture_logger_output(
            lambda: logger.phase_failed("p3", "Dedup", "Connection timeout")
        )
        assert events[0]["event"] == "phase"
        assert events[0]["status"] == "failed"
        assert events[1]["event"] == "log"
        assert events[1]["level"] == "error"

    def test_log_levels(self):
        logger = PipelineLogger()
        for level in ["info", "warn", "error", "debug"]:
            fn = getattr(logger, level)
            events = _capture_logger_output(lambda: fn(f"test {level}", phase="p0"))
            assert events[0]["event"] == "log"
            assert events[0]["level"] == level
            assert events[0]["phase"] == "p0"

    def test_report_cost(self):
        logger = PipelineLogger()
        events = _capture_logger_output(
            lambda: logger.report_cost(3.45, 234500)
        )
        assert events[0]["event"] == "cost"
        assert events[0]["api_cost_usd"] == 3.45
        assert events[0]["tokens_used"] == 234500

    def test_report_quality_aggregate(self):
        logger = PipelineLogger()
        events = _capture_logger_output(
            lambda: logger.report_quality(91.2, 487, 198, 185, 0.103)
        )
        assert events[0]["event"] == "quality"
        assert events[0]["quality_score"] == 91.2
        assert events[0]["atoms_extracted"] == 487
        assert events[0]["atoms_deduplicated"] == 198
        assert events[0]["atoms_verified"] == 185
        assert events[0]["compression_ratio"] == 0.103

    def test_report_conflicts(self):
        logger = PipelineLogger()
        conflicts = [{"id": "c1", "type": "contradictory"}]
        events = _capture_logger_output(
            lambda: logger.report_conflicts(conflicts)
        )
        assert events[0]["event"] == "conflict"
        assert events[0]["count"] == 1
        assert events[0]["conflicts"] == conflicts

    def test_report_package(self):
        logger = PipelineLogger()
        events = _capture_logger_output(
            lambda: logger.report_package("/out/package.zip", "/out/")
        )
        assert events[0]["event"] == "package"
        assert events[0]["path"] == "/out/package.zip"
        assert events[0]["output_dir"] == "/out/"

    def test_all_output_is_valid_json(self):
        logger = PipelineLogger(build_id="json_test")
        events = _capture_logger_output(lambda: (
            logger.phase_start("p0", "Test"),
            logger.phase_progress("p0", "Test", 50),
            logger.info("msg"),
            logger.report_cost(1.0, 1000),
            logger.phase_complete("p0", "Test", 80.0, 10),
        ))
        # Every line must be valid JSON
        for e in events:
            assert isinstance(e, dict)
            assert "event" in e
