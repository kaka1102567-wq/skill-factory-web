#!/usr/bin/env python3
"""
Skill Factory Pipeline CLI.
Replaces mock_cli.py with the real pipeline engine.

Usage:
  python3 pipeline/cli.py build --config config.yaml --output ./output --json-logs
  python3 pipeline/cli.py resolve --output ./output --resolutions resolutions.json
  python3 pipeline/cli.py status --output ./output
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import json

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

    # ── fetch-urls ──
    fetch_parser = subparsers.add_parser("fetch-urls", help="Fetch URLs and convert to Markdown")
    fetch_parser.add_argument("--urls", required=True, help="Comma or newline separated URLs")
    fetch_parser.add_argument("--output-dir", required=True, help="Output directory for .md files")

    # ── extract-pdf ──
    pdf_parser = subparsers.add_parser("extract-pdf", help="Extract text from PDFs to Markdown")
    pdf_parser.add_argument("--input", default=None, help="Single PDF file path")
    pdf_parser.add_argument("--input-dir", default=None, help="Directory containing PDF files")
    pdf_parser.add_argument("--output-dir", required=True, help="Output directory for .md files")

    # ── analyze-repo ──
    repo_parser = subparsers.add_parser("analyze-repo", help="Analyze GitHub repo for code patterns")
    repo_parser.add_argument("--repo", required=True, help="GitHub URL or local path")
    repo_parser.add_argument("--output-dir", required=True, help="Output directory for analysis files")
    repo_parser.add_argument("--no-code", action="store_true", help="Skip code analysis, docs only")

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
    elif args.command == "fetch-urls":
        sys.exit(cmd_fetch_urls(args))
    elif args.command == "extract-pdf":
        sys.exit(cmd_extract_pdf(args))
    elif args.command == "analyze-repo":
        sys.exit(cmd_analyze_repo(args))


def cmd_build(args) -> int:
    """Run the full pipeline build."""
    from pipeline.core.config import load_config
    from pipeline.core.errors import PipelineError
    from pipeline.orchestrator.runner import PipelineRunner

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
    from pipeline.core.config import load_config
    from pipeline.core.errors import PipelineError
    from pipeline.core.utils import read_json
    from pipeline.orchestrator.runner import PipelineRunner
    from pipeline.orchestrator.state import load_checkpoint

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
    from pipeline.orchestrator.state import load_checkpoint

    state = load_checkpoint(args.output)
    if not state:
        print(json.dumps({"status": "not_found"}, indent=2))
        return 0

    from dataclasses import asdict
    print(json.dumps(asdict(state), indent=2, ensure_ascii=False))
    return 0


def cmd_fetch_urls(args) -> int:
    """Fetch URLs and convert to Markdown input files."""
    from pipeline.commands.fetch_urls import run_fetch_urls
    return run_fetch_urls(args.urls, args.output_dir)


def cmd_extract_pdf(args) -> int:
    """Extract text from PDF files to Markdown."""
    from pipeline.commands.extract_pdf import run_extract_pdf
    if not args.input and not args.input_dir:
        _error_json("Either --input or --input-dir is required")
        return 1
    return run_extract_pdf(
        input_path=args.input,
        input_dir=args.input_dir,
        output_dir=args.output_dir,
    )


def cmd_analyze_repo(args) -> int:
    """Analyze a GitHub repository for code patterns and docs."""
    from pipeline.commands.analyze_repo import run_analyze_repo
    return run_analyze_repo(
        repo_url=args.repo,
        output_dir=args.output_dir,
        analyze_code_flag=not args.no_code,
    )


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
