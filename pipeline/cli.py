#!/usr/bin/env python3
"""
Skill Factory Pipeline CLI.
Replaces mock_cli.py with the real pipeline engine.

Usage:
  python3 pipeline/cli.py build --config config.yaml --output ./output --json-logs
  python3 pipeline/cli.py resolve --output ./output --resolutions resolutions.json
  python3 pipeline/cli.py status --output ./output
"""

import argparse
import json
import os
import sys

from dotenv import load_dotenv


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="Skill Factory Pipeline CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # ── build ──
    build_parser = subparsers.add_parser("build", help="Run full pipeline build")
    build_parser.add_argument("--config", required=True, help="Config YAML path")
    build_parser.add_argument("--output", required=True, help="Output directory")
    build_parser.add_argument("--json-logs", action="store_true", help="JSON log output")

    # ── resolve ──
    resolve_parser = subparsers.add_parser("resolve", help="Resume after conflict resolution")
    resolve_parser.add_argument("--output", required=True, help="Build output directory")
    resolve_parser.add_argument("--resolutions", required=True, help="Resolutions JSON file")
    resolve_parser.add_argument("--json-logs", action="store_true", help="JSON log output")

    # ── status ──
    status_parser = subparsers.add_parser("status", help="Check build status")
    status_parser.add_argument("--output", required=True, help="Build output directory")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "build":
        sys.exit(cmd_build(args))
    elif args.command == "resolve":
        sys.exit(cmd_resolve(args))
    elif args.command == "status":
        sys.exit(cmd_status(args))


def cmd_build(args) -> int:
    """Run the full pipeline build."""
    from .core.config import load_config
    from .core.errors import PipelineError
    from .orchestrator.runner import PipelineRunner

    try:
        config = load_config(args.config, args.output)
    except PipelineError as e:
        _error_json(f"Config error: {e}")
        return 1

    try:
        runner = PipelineRunner(config)
        return runner.run()
    except PipelineError as e:
        _error_json(f"Pipeline error: {e}")
        return 1
    except Exception as e:
        _error_json(f"Unexpected error: {e}")
        return 1


def cmd_resolve(args) -> int:
    """Resume pipeline after conflict resolution."""
    from .core.config import load_config
    from .core.errors import PipelineError
    from .core.utils import read_json
    from .orchestrator.runner import PipelineRunner
    from .orchestrator.state import load_checkpoint

    # Find config path from checkpoint
    state = load_checkpoint(args.output)
    if not state:
        _error_json("No checkpoint found in output directory")
        return 1

    # Load resolutions
    try:
        resolutions = read_json(args.resolutions)
    except FileNotFoundError:
        _error_json(f"Resolutions file not found: {args.resolutions}")
        return 1

    # Find config path — look for config.yaml in output parent
    config_path = _find_config(args.output)
    if not config_path:
        _error_json("Cannot find config.yaml for this build")
        return 1

    try:
        config = load_config(config_path, args.output)
        runner = PipelineRunner(config)
        return runner.resume_after_resolve(resolutions)
    except PipelineError as e:
        _error_json(f"Resume error: {e}")
        return 1
    except Exception as e:
        _error_json(f"Unexpected error: {e}")
        return 1


def cmd_status(args) -> int:
    """Print current build status as JSON."""
    from .orchestrator.state import load_checkpoint

    state = load_checkpoint(args.output)
    if not state:
        print(json.dumps({"status": "not_found"}, indent=2))
        return 0

    from dataclasses import asdict
    print(json.dumps(asdict(state), indent=2, ensure_ascii=False))
    return 0


def _find_config(output_dir: str) -> str | None:
    """Find config.yaml by checking common locations."""
    candidates = [
        os.path.join(output_dir, "config.yaml"),
        os.path.join(os.path.dirname(output_dir), "config.yaml"),
        os.path.join(output_dir, "..", "config.yaml"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return os.path.abspath(path)
    return None


def _error_json(message: str) -> None:
    """Print error as JSON log line to stdout."""
    print(json.dumps({
        "event": "log", "level": "error", "phase": None,
        "message": message,
    }, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
