"""CLI command: analyze-repo — Clone/scan GitHub repo and extract docs + code analysis."""

import json
import subprocess
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from ..core.utils import write_json, write_file

IGNORE_DIRS = {
    '.git', 'node_modules', '__pycache__', '.venv', 'venv',
    'dist', 'build', '.next', '.cache', 'vendor', 'target',
    '.idea', '.vscode', 'coverage', '.tox', 'egg-info',
    '.mypy_cache', '.pytest_cache', '.ruff_cache',
}

IGNORE_FILES = {
    '.gitignore', '.dockerignore', 'package-lock.json',
    'yarn.lock', 'Pipfile.lock', 'poetry.lock', 'pnpm-lock.yaml',
}

LANG_MAP = {
    '.py': 'python', '.js': 'javascript', '.ts': 'typescript',
    '.jsx': 'react', '.tsx': 'react-typescript',
    '.go': 'go', '.rs': 'rust', '.java': 'java',
    '.rb': 'ruby', '.php': 'php', '.swift': 'swift',
    '.kt': 'kotlin', '.cs': 'csharp', '.cpp': 'cpp',
    '.c': 'c', '.sh': 'shell', '.sql': 'sql',
}

DOC_EXTENSIONS = {'.md', '.rst', '.txt', '.adoc'}
SOURCE_EXTENSIONS = set(LANG_MAP.keys())

CONFIG_FILENAMES = {
    'package.json', 'setup.py', 'pyproject.toml', 'Cargo.toml',
    'Makefile', 'Dockerfile', 'docker-compose.yml', 'tsconfig.json',
    '.env.example', 'requirements.txt', 'go.mod', 'Gemfile',
}

ENTRY_PATTERNS = [
    'main.py', 'app.py', 'cli.py', 'index.ts', 'index.js',
    'server.py', 'server.ts', 'manage.py', '__main__.py',
    'src/index.ts', 'src/main.ts', 'src/app.ts',
    'src/index.js', 'src/main.js', 'src/app.js',
]

MAX_SOURCE_FILES = 20
MAX_CODE_ATOMS = 15
MAX_FILE_CONTENT_CHARS = 10000
MAX_DOCS = 10


def _log(level: str, message: str) -> None:
    """Print JSON log line to stdout for build-runner parsing."""
    print(json.dumps({
        "event": "log", "level": level, "phase": "fetch",
        "message": message,
    }, ensure_ascii=True), flush=True)


def clone_repo(repo_url: str, target_dir: str) -> str:
    """Clone GitHub repo (shallow). Returns path to cloned repo."""
    if Path(repo_url).exists():
        _log("info", f"Using local repo: {repo_url}")
        return repo_url

    # Validate: must contain github.com as a domain (not substring of another domain)
    import re
    if not re.search(r'(?:^|[/.])github\.com(?:[/:]|$)', repo_url):
        raise ValueError(f"Only GitHub repos supported: {repo_url}")

    # Normalize URL
    url = repo_url.strip().rstrip('/')
    if not url.startswith('http'):
        url = f"https://{url}"
    if not url.endswith('.git'):
        url = f"{url}.git"

    repo_dir = Path(target_dir) / "_repo_clone"
    repo_dir.mkdir(parents=True, exist_ok=True)

    _log("info", f"Cloning repository: {repo_url}")

    try:
        subprocess.run(
            ['git', 'clone', '--depth', '1', url, str(repo_dir)],
            timeout=120, check=True,
            capture_output=True, text=True,
        )
    except FileNotFoundError:
        raise RuntimeError("Git is required for repo analysis. Install git first.")
    except subprocess.TimeoutExpired:
        raise RuntimeError("Clone timed out after 120 seconds")
    except subprocess.CalledProcessError as e:
        stderr = e.stderr[:300] if e.stderr else ""
        raise RuntimeError(
            f"Cannot clone repository: {stderr}. "
            "Ensure the URL is correct and the repo is public."
        )

    return str(repo_dir)


def scan_repo(repo_dir: str) -> dict:
    """Scan repo structure, identify important files."""
    result = {
        "readme": None,
        "docs": [],
        "source_files": [],
        "config_files": [],
        "test_files": [],
        "total_files": 0,
        "languages": {},
    }

    repo_path = Path(repo_dir)
    for path in sorted(repo_path.rglob('*')):
        if any(part in IGNORE_DIRS for part in path.parts):
            continue
        if not path.is_file():
            continue
        if path.name in IGNORE_FILES:
            continue

        result["total_files"] += 1
        rel_path = str(path.relative_to(repo_path)).replace('\\', '/')

        # README detection
        if path.name.lower().startswith('readme'):
            if result["readme"] is None:
                result["readme"] = rel_path
        elif path.name in CONFIG_FILENAMES:
            result["config_files"].append(rel_path)
        elif 'doc' in str(path.parent).lower() and path.suffix in DOC_EXTENSIONS:
            result["docs"].append(rel_path)
        elif 'test' in rel_path.lower() and path.suffix in SOURCE_EXTENSIONS:
            result["test_files"].append(rel_path)
        elif path.suffix in SOURCE_EXTENSIONS:
            result["source_files"].append(rel_path)
            lang = LANG_MAP.get(path.suffix, 'other')
            result["languages"][lang] = result["languages"].get(lang, 0) + 1

    return result


def extract_docs(repo_dir: str, repo_url: str, scan: dict,
                 output_dir: str) -> list[str]:
    """Extract README and docs as markdown input files."""
    created = []
    now = datetime.now(timezone.utc).isoformat()

    # README -> repo_readme.md
    if scan["readme"]:
        readme_path = Path(repo_dir) / scan["readme"]
        try:
            content = readme_path.read_text(encoding='utf-8', errors='replace')
            output = (
                f"---\nsource_type: github_readme\n"
                f"source_repo: {repo_url}\n"
                f"extracted_at: {now}\n---\n\n{content}\n"
            )
            out_path = Path(output_dir) / "repo_readme.md"
            write_file(str(out_path), output)
            created.append(str(out_path))
        except Exception:
            pass

    # Docs -> repo_docs_*.md (max 10)
    for i, doc_path in enumerate(scan["docs"][:MAX_DOCS]):
        full_path = Path(repo_dir) / doc_path
        try:
            content = full_path.read_text(encoding='utf-8', errors='replace')
            stem = Path(doc_path).stem
            out_name = f"repo_docs_{i+1:03d}_{stem}.md"
            output = (
                f"---\nsource_type: github_docs\n"
                f"source_file: {doc_path}\n"
                f"source_repo: {repo_url}\n"
                f"extracted_at: {now}\n---\n\n{content}\n"
            )
            out_path = Path(output_dir) / out_name
            write_file(str(out_path), output)
            created.append(str(out_path))
        except Exception:
            pass

    return created


def _file_importance(repo_dir: str, path_str: str) -> int:
    """Score file importance for ranking."""
    score = 0
    if any(path_str.endswith(p) or path_str == p for p in ENTRY_PATTERNS):
        score += 100
    # Shorter path depth = more important
    score += max(0, 10 - path_str.count('/')) * 5
    try:
        size = (Path(repo_dir) / path_str).stat().st_size
        score += min(size // 1000, 20)
    except OSError:
        pass
    return score


def analyze_code(repo_dir: str, repo_url: str, scan: dict,
                 output_dir: str, max_files: int = MAX_SOURCE_FILES) -> str:
    """Analyze source code, write code_analysis.json. Returns output path."""
    ranked = sorted(
        scan["source_files"],
        key=lambda p: _file_importance(repo_dir, p),
        reverse=True,
    )
    top_files = ranked[:max_files]

    primary_lang = (
        max(scan["languages"], key=scan["languages"].get)
        if scan["languages"] else "unknown"
    )

    analysis = {
        "repo_url": repo_url,
        "repo_structure": {
            "total_files": scan["total_files"],
            "languages": scan["languages"],
            "primary_language": primary_lang,
            "has_tests": len(scan["test_files"]) > 0,
            "has_docs": len(scan["docs"]) > 0,
            "config_files": scan["config_files"][:5],
        },
        "analyzed_files": [],
    }

    for file_path in top_files:
        full_path = Path(repo_dir) / file_path
        try:
            content = full_path.read_text(encoding='utf-8', errors='replace')
            if len(content) > MAX_FILE_CONTENT_CHARS:
                content = content[:MAX_FILE_CONTENT_CHARS] + "\n\n# ... (truncated)"
            analysis["analyzed_files"].append({
                "path": file_path,
                "language": LANG_MAP.get(full_path.suffix, "other"),
                "size": full_path.stat().st_size,
                "content": content,
                "lines": content.count('\n') + 1,
            })
        except Exception:
            pass

    out_path = str(Path(output_dir) / "code_analysis.json")
    write_json(analysis, out_path)
    return out_path


def run_analyze_repo(repo_url: str, output_dir: str,
                     analyze_code_flag: bool = True) -> int:
    """Main entry point for analyze-repo command. Returns exit code."""
    try:
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        # Step 1: Clone
        tmp_dir = None
        try:
            if Path(repo_url).exists():
                repo_dir = repo_url
            else:
                tmp_dir = tempfile.mkdtemp(prefix="sf_repo_")
                repo_dir = clone_repo(repo_url, tmp_dir)
        except Exception as e:
            _log("error", str(e))
            return 1

        # Step 2: Scan
        scan = scan_repo(repo_dir)
        lang_summary = ", ".join(
            f"{lang}: {count}" for lang, count in
            sorted(scan["languages"].items(), key=lambda x: -x[1])[:5]
        )
        _log("info",
             f"Repo: {scan['total_files']} files"
             f"{f', languages: {lang_summary}' if lang_summary else ''}")

        # Step 3: Extract docs
        docs = extract_docs(repo_dir, repo_url, scan, output_dir)
        _log("info", f"Extracted {len(docs)} doc files to input/")

        # Step 4: Analyze code (optional)
        if analyze_code_flag and scan["source_files"]:
            code_path = analyze_code(repo_dir, repo_url, scan, output_dir)
            file_count = len(scan["source_files"][:MAX_SOURCE_FILES])
            _log("info", f"Analyzed {file_count} source files -> code_analysis.json")
        elif not scan["source_files"]:
            _log("info", "No source files found, skipping code analysis")
        else:
            _log("info", "Code analysis skipped (docs only mode)")

        # Cleanup cloned repo
        if tmp_dir:
            try:
                shutil.rmtree(tmp_dir, ignore_errors=True)
            except Exception:
                pass

        # Result summary
        print(json.dumps({
            "event": "log", "level": "info", "phase": "fetch",
            "message": (
                f"Repo analysis complete: {len(docs)} docs"
                f"{', code_analysis.json' if analyze_code_flag and scan['source_files'] else ''}"
            ),
        }, ensure_ascii=True), flush=True)

        return 0

    except Exception as e:
        _log("error", f"Repo analysis failed: {e}")
        return 1
