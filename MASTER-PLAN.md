# 🏭 SKILL FACTORY PIPELINE — MASTER IMPLEMENTATION PLAN
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# This is the SINGLE SOURCE OF TRUTH for implementation.
# Claude Code: Read this → execute tasks in order → test → move on.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## SITUATION BRIEFING

**What exists:** Skill Factory Web — Next.js 15 app deployed on Coolify.
UI layer 100% complete (Dashboard, Wizard, Live View, Conflict Review, Quality Report).
Python pipeline is a MOCK SIMULATOR (`mock_cli.py`) using `random.uniform()` + `time.sleep()`.

**What to build:** Replace mock with REAL pipeline engine that:
1. Scrapes official docs (Seekers) → builds knowledge base
2. Calls Claude API → extracts Knowledge Atoms from video transcripts
3. Deduplicates, verifies, and packages into production AI Skill files

**Architecture (KEEP AS-IS):**
```
Browser ↔ Next.js 15 (API Routes + SSE) ↔ Python CLI (subprocess stdout → JSON lines) ↔ SQLite
```
Next.js spawns: `python3 pipeline/cli.py build --config X --output Y --json-logs`
Python prints JSON to stdout → Next.js reads line-by-line → SSE → UI updates.

**CRITICAL RULE: DO NOT modify any Next.js files** except where explicitly specified.
The Python pipeline must conform to the existing stdout JSON contract.

---

## EXECUTION ORDER — 25 Tasks in 6 Epics

```
SESSION 1 ─── EPIC 1: Foundation (Tasks 1.1-1.7)     ~4h   → All shared infrastructure
SESSION 2 ─── EPIC 2: Seekers   (Tasks 2.1-2.4)      ~4h   → Knowledge base engine
SESSION 3 ─── EPIC 3a: Phases P0-P2 (Tasks 3.0-3.2)  ~4h   → First 3 pipeline phases
SESSION 4 ─── EPIC 3b: Phases P3-P5 (Tasks 3.3-3.5)  ~5h   → Last 3 pipeline phases
SESSION 5 ─── EPIC 4: Orchestrator (Tasks 4.1-4.2)    ~3h   → CLI + phase sequencer
SESSION 6 ─── EPIC 5+6: Integration + Test (5.1-6.3)  ~4h   → Deploy + validate
```

---

## STDOUT JSON CONTRACT (DO NOT CHANGE)

Python must print these JSON events to stdout (one per line, flushed):

```python
# 1. Phase progress → drives UI phase stepper
{"event": "phase", "phase": "p0", "name": "Baseline", "status": "running", "progress": 45}
{"event": "phase", "phase": "p0", "name": "Baseline", "status": "done", "progress": 100}

# 2. Log messages → live log panel
{"event": "log", "level": "info", "phase": "p0", "message": "Scraping Meta docs..."}

# 3. Quality scores → quality gate UI
{"event": "quality", "phase": "p1", "score": 88.5, "pass": true, "atoms_count": 47}

# 4. Aggregate quality (final) → build summary
{"event": "quality", "quality_score": 91.2, "atoms_extracted": 487, "atoms_deduplicated": 198, "atoms_verified": 185, "compression_ratio": 0.103}

# 5. Cost tracking → cost counter UI
{"event": "cost", "api_cost_usd": 3.45, "tokens_used": 234500}

# 6. Conflicts → pauses build, triggers review UI
{"event": "conflict", "conflicts": [...], "count": 6}

# 7. Package ready → enables download button
{"event": "package", "path": "/path/to/package.zip", "output_dir": "/path/to/output/"}
```

---

## TARGET FILE STRUCTURE

```
pipeline/
├── cli.py                              # Main entry point (replaces mock_cli.py)
├── requirements.txt                    # Python dependencies
├── __init__.py
│
├── core/
│   ├── __init__.py
│   ├── types.py                        # All dataclasses + enums
│   ├── logger.py                       # JSON stdout logger
│   ├── config.py                       # YAML config parser
│   ├── errors.py                       # Custom exceptions
│   └── utils.py                        # File I/O, text chunking, zip
│
├── clients/
│   ├── __init__.py
│   ├── claude_client.py                # Claude API wrapper + cost tracking
│   └── web_client.py                   # Rate-limited HTTP client
│
├── seekers/
│   ├── __init__.py
│   ├── scraper.py                      # URL fetcher
│   ├── parser.py                       # HTML → structured sections
│   ├── cache.py                        # SQLite cache with TTL
│   ├── lookup.py                       # Query interface
│   ├── taxonomy.py                     # Category trees per domain
│   └── sources/
│       ├── __init__.py
│       └── meta_ads.py                 # Meta/Facebook URL patterns
│
├── phases/
│   ├── __init__.py
│   ├── p0_baseline.py                  # Seekers → build KB
│   ├── p1_audit.py                     # Claude → topic inventory
│   ├── p2_extract.py                   # Claude → Knowledge Atoms
│   ├── p3_dedup.py                     # Claude + Seekers → deduplicate
│   ├── p4_verify.py                    # Seekers + Claude → verify
│   └── p5_build.py                     # Claude → SKILL.md + knowledge/
│
├── prompts/
│   ├── __init__.py
│   ├── p1_audit_prompts.py
│   ├── p2_extract_prompts.py
│   ├── p3_dedup_prompts.py
│   ├── p4_verify_prompts.py
│   └── p5_build_prompts.py
│
├── orchestrator/
│   ├── __init__.py
│   ├── runner.py                       # Phase sequencer P0→P5
│   └── state.py                        # Checkpoint/resume
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_logger.py
│   ├── test_claude_client.py
│   ├── test_seekers.py
│   ├── test_phases.py
│   └── fixtures/
│       ├── sample_transcript_vi.txt
│       ├── sample_config.yaml
│       └── sample_atoms.json
│
├── mock_cli.py                         # KEEP as fallback
└── data/                               # Runtime (gitignored)
    ├── cache/
    └── builds/
```

---

# ═══════════════════════════════════════════════════════
# SESSION 1: EPIC 1 — FOUNDATION LAYER
# ═══════════════════════════════════════════════════════

## TASK 1.7: Project Setup

Create all package files and `__init__.py` stubs.

**File: `pipeline/requirements.txt`**
```
anthropic>=0.40.0
pyyaml>=6.0
httpx>=0.27.0
beautifulsoup4>=4.12.0
lxml>=5.0
tenacity>=8.2.0
python-dotenv>=1.0.0
pytest>=8.0
pytest-mock>=3.12.0
```

**Create all `__init__.py` files** (empty) for:
`pipeline/`, `pipeline/core/`, `pipeline/clients/`, `pipeline/seekers/`, 
`pipeline/seekers/sources/`, `pipeline/phases/`, `pipeline/prompts/`, 
`pipeline/orchestrator/`, `pipeline/tests/`

**Test:** `pip install -r pipeline/requirements.txt` succeeds.

---

## TASK 1.1: Core Types

**File: `pipeline/core/types.py`**

```python
"""All shared data types for the Skill Factory pipeline."""

from dataclasses import dataclass, field, asdict
from typing import Optional, Any
from enum import Enum
import json


class PhaseId(str, Enum):
    P0_BASELINE = "p0"
    P1_AUDIT = "p1"
    P2_EXTRACT = "p2"
    P3_DEDUP = "p3"
    P4_VERIFY = "p4"
    P5_BUILD = "p5"


class PhaseStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


class AtomStatus(str, Enum):
    RAW = "raw"
    DEDUPLICATED = "deduplicated"
    VERIFIED = "verified"
    UPDATED = "updated"
    FLAGGED = "flagged"
    DISCARDED = "discarded"


class ConflictResolution(str, Enum):
    KEEP_A = "keep_a"
    KEEP_B = "keep_b"
    MERGE = "merge"
    DISCARD = "discard"
    PENDING = "pending"


class QualityTier(str, Enum):
    DRAFT = "draft"
    STANDARD = "standard"
    PREMIUM = "premium"


@dataclass
class KnowledgeAtom:
    id: str
    title: str
    content: str
    category: str
    tags: list[str] = field(default_factory=list)
    source_video: str = ""
    source_page: Optional[int] = None
    source_timestamp: Optional[str] = None
    confidence: float = 0.0
    status: str = "raw"  # Use string for JSON serialization simplicity
    verification_note: Optional[str] = None
    baseline_reference: Optional[str] = None
    created_at: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict) -> 'KnowledgeAtom':
        # Filter to only known fields
        known = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


@dataclass
class Conflict:
    id: str
    atom_a: dict  # KnowledgeAtom as dict for JSON compatibility
    atom_b: dict
    conflict_type: str  # "contradictory_data" | "overlapping_scope" | "outdated_info"
    description: str
    baseline_evidence: Optional[str] = None
    auto_resolved: bool = False
    resolution: str = "pending"
    resolution_note: Optional[str] = None
    merged_atom: Optional[dict] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BaselineEntry:
    id: str
    title: str
    content: str
    source_url: str
    source_type: str
    section_path: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    last_scraped: str = ""
    content_hash: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class InventoryItem:
    topic: str
    videos_mentioning: list[str] = field(default_factory=list)
    mention_count: int = 0
    quality_score: float = 0.0
    baseline_coverage: bool = False
    gap_type: Optional[str] = None
    recommended_action: Optional[str] = None


@dataclass
class PhaseResult:
    phase_id: str
    status: str  # "done" | "failed" | "skipped"
    started_at: str = ""
    completed_at: Optional[str] = None
    duration_seconds: float = 0.0
    quality_score: float = 0.0
    atoms_count: int = 0
    api_cost_usd: float = 0.0
    tokens_used: int = 0
    output_files: list[str] = field(default_factory=list)
    error_message: Optional[str] = None
    metrics: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BuildConfig:
    name: str
    domain: str
    language: str = "vi"
    quality_tier: str = "standard"
    platforms: list[str] = field(default_factory=lambda: ["claude"])
    baseline_sources: list[dict] = field(default_factory=list)
    transcript_paths: list[str] = field(default_factory=list)
    output_dir: str = ""
    config_path: str = ""
    # API
    claude_api_key: str = ""
    claude_model: str = "claude-sonnet-4-20250514"
    max_retries: int = 3
    # Seekers
    seekers_cache_dir: str = "./data/cache"
    seekers_cache_ttl_hours: int = 168
    # Quality
    min_phase_score: float = 70.0
    auto_resolve_threshold: float = 0.8


@dataclass
class PipelineState:
    build_id: str
    current_phase: str = "p0"
    phase_results: dict = field(default_factory=dict)
    is_paused: bool = False
    pause_reason: Optional[str] = None
    total_cost_usd: float = 0.0
    total_tokens: int = 0
    checkpoint_path: Optional[str] = None

    def save(self, path: str) -> None:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(asdict(self), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path: str) -> 'PipelineState':
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls(**{k: v for k, v in data.items() 
                      if k in {f.name for f in cls.__dataclass_fields__.values()}})
```

**File: `pipeline/core/errors.py`**

```python
"""Custom exceptions for the pipeline."""


class PipelineError(Exception):
    """Base pipeline exception."""
    pass


class PhaseError(PipelineError):
    def __init__(self, phase_id: str, message: str, retryable: bool = True):
        self.phase_id = phase_id
        self.retryable = retryable
        super().__init__(f"[{phase_id}] {message}")


class SeekersError(PipelineError):
    pass


class ClaudeAPIError(PipelineError):
    def __init__(self, message: str, status_code: int = 0, retryable: bool = True):
        self.status_code = status_code
        self.retryable = retryable
        super().__init__(message)


class ConfigError(PipelineError):
    pass


class PhaseNotImplementedError(PipelineError):
    """Phase not yet implemented — use mock fallback."""
    pass
```

**Test:** `python3 -c "from pipeline.core.types import KnowledgeAtom, BuildConfig, PipelineState; print('Types OK')"`

---

## TASK 1.2: JSON Pipeline Logger

**File: `pipeline/core/logger.py`**

```python
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
```

**Test:** Run logger methods → capture stdout → verify JSON parseable, event types correct.

---

## TASK 1.3: Config Parser

**File: `pipeline/core/config.py`**

```python
"""YAML config parser. Reads config generated by Next.js Wizard."""

import os
import yaml
from pathlib import Path
from .types import BuildConfig
from .errors import ConfigError


def load_config(config_path: str, output_dir: str) -> BuildConfig:
    path = Path(config_path)
    if not path.exists():
        raise ConfigError(f"Config not found: {config_path}")

    with open(path, 'r', encoding='utf-8') as f:
        raw = yaml.safe_load(f) or {}

    if not isinstance(raw, dict):
        raise ConfigError(f"Invalid config format: {config_path}")

    # Auto-discover transcripts from uploads dir
    upload_dir = Path(output_dir).parent / "uploads"
    transcript_paths = []
    if upload_dir.exists():
        transcript_paths = sorted(
            str(p) for p in upload_dir.glob("*")
            if p.suffix in ('.txt', '.md', '.srt', '.vtt')
        )
    # Also check output dir itself for uploaded files
    for p in Path(output_dir).glob("*.txt"):
        if str(p) not in transcript_paths:
            transcript_paths.append(str(p))

    tier_map = {"draft": "draft", "standard": "standard", "premium": "premium"}

    return BuildConfig(
        name=raw.get("name", "Untitled"),
        domain=raw.get("domain", "custom"),
        language=raw.get("language", "vi"),
        quality_tier=tier_map.get(raw.get("quality_tier", "standard"), "standard"),
        platforms=raw.get("platforms", ["claude"]),
        baseline_sources=raw.get("baseline_sources", []),
        transcript_paths=transcript_paths,
        output_dir=output_dir,
        config_path=config_path,
        claude_api_key=os.environ.get("CLAUDE_API_KEY", ""),
        claude_model=os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-20250514"),
        seekers_cache_dir=os.environ.get("SEEKERS_CACHE_DIR", "./data/cache"),
        seekers_cache_ttl_hours=int(os.environ.get("SEEKERS_CACHE_TTL_HOURS", "168")),
    )


def get_tier_params(tier: str) -> dict:
    return {
        "draft": {"max_atoms_per_chunk": 20, "verify_sample_pct": 30, "dedup_threshold": 0.7},
        "standard": {"max_atoms_per_chunk": 15, "verify_sample_pct": 70, "dedup_threshold": 0.8},
        "premium": {"max_atoms_per_chunk": 10, "verify_sample_pct": 100, "dedup_threshold": 0.9},
    }.get(tier, {"max_atoms_per_chunk": 15, "verify_sample_pct": 70, "dedup_threshold": 0.8})
```

---

## TASK 1.4: File Utilities

**File: `pipeline/core/utils.py`**

```python
"""File I/O, text processing, and packaging utilities."""

import json
import os
import re
import zipfile
from pathlib import Path
from typing import Any


def read_transcript(path: str) -> str:
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def read_all_transcripts(paths: list[str]) -> list[dict]:
    results = []
    for p in paths:
        try:
            content = read_transcript(p)
            results.append({
                "filename": os.path.basename(p),
                "path": p,
                "content": content,
                "word_count": len(content.split()),
            })
        except Exception as e:
            results.append({"filename": os.path.basename(p), "path": p, 
                           "content": "", "word_count": 0, "error": str(e)})
    return results


def chunk_text(text: str, max_tokens: int = 6000, overlap: int = 200) -> list[str]:
    """Split text into chunks respecting paragraph boundaries."""
    max_chars = max_tokens * 4  # ~4 chars per token for Vietnamese
    overlap_chars = overlap * 4

    if len(text) <= max_chars:
        return [text]

    paragraphs = text.split('\n\n')
    chunks = []
    current = ""

    for para in paragraphs:
        if len(current) + len(para) + 2 > max_chars:
            if current:
                chunks.append(current.strip())
            # Start new chunk with overlap from end of previous
            if chunks and overlap_chars > 0:
                current = chunks[-1][-overlap_chars:] + "\n\n" + para
            else:
                current = para
            # Handle single paragraph longer than max
            if len(current) > max_chars:
                sentences = re.split(r'(?<=[.!?])\s+', current)
                current = ""
                for sent in sentences:
                    if len(current) + len(sent) > max_chars:
                        if current:
                            chunks.append(current.strip())
                        current = sent
                    else:
                        current += " " + sent if current else sent
        else:
            current += "\n\n" + para if current else para

    if current.strip():
        chunks.append(current.strip())

    return [c for c in chunks if len(c.strip()) > 50]  # Skip tiny fragments


def estimate_tokens(text: str) -> int:
    return len(text) // 4  # Rough estimate: ~4 chars per token


def write_json(data: Any, path: str) -> None:
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def read_json(path: str) -> Any:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def write_file(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)


def create_zip(source_dir: str, output_path: str) -> str:
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        base = Path(source_dir)
        for file_path in base.rglob('*'):
            if file_path.is_file() and file_path.name != 'package.zip':
                if file_path.name.startswith('.') or 'checkpoint' in file_path.name:
                    continue
                arcname = file_path.relative_to(base)
                zf.write(file_path, arcname)
    return output_path
```

---

## TASK 1.5: Claude API Client

**File: `pipeline/clients/claude_client.py`**

```python
"""Claude API wrapper with retry, cost tracking, and JSON response parsing."""

import json
import re
import time
import hashlib
import os
from typing import Optional

import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from ..core.logger import PipelineLogger
from ..core.errors import ClaudeAPIError


class ClaudeClient:
    PRICING = {
        "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
        "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.0},
    }

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514",
                 logger: Optional[PipelineLogger] = None, cache_dir: Optional[str] = None):
        if not api_key:
            raise ClaudeAPIError("CLAUDE_API_KEY not set", retryable=False)
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.logger = logger or PipelineLogger()
        self.cache_dir = cache_dir  # Optional response cache

        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost_usd = 0.0
        self.call_count = 0

    def _cache_key(self, system: str, user: str) -> str:
        return hashlib.sha256((system + user).encode()).hexdigest()[:16]

    def _get_cached(self, key: str) -> Optional[str]:
        if not self.cache_dir:
            return None
        path = os.path.join(self.cache_dir, f"claude_{key}.json")
        if os.path.exists(path):
            with open(path, 'r') as f:
                return json.load(f).get("response")
        return None

    def _set_cache(self, key: str, response: str) -> None:
        if not self.cache_dir:
            return
        os.makedirs(self.cache_dir, exist_ok=True)
        path = os.path.join(self.cache_dir, f"claude_{key}.json")
        with open(path, 'w') as f:
            json.dump({"response": response}, f)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        retry=retry_if_exception_type((anthropic.RateLimitError, anthropic.APIStatusError)),
    )
    def call(self, system: str, user: str, max_tokens: int = 4096,
             temperature: float = 0.0, phase: str = None) -> str:
        """Call Claude API. Returns response text."""
        # Check cache
        cache_key = self._cache_key(system, user)
        cached = self._get_cached(cache_key)
        if cached:
            self.logger.debug(f"Cache hit: {cache_key}", phase=phase)
            return cached

        start = time.time()
        try:
            response = self.client.messages.create(
                model=self.model, max_tokens=max_tokens,
                temperature=temperature, system=system,
                messages=[{"role": "user", "content": user}],
            )
        except anthropic.RateLimitError:
            self.logger.warn("Rate limited, retrying...", phase=phase)
            raise
        except anthropic.APIStatusError as e:
            if e.status_code >= 500:
                self.logger.warn(f"Server error ({e.status_code}), retrying...", phase=phase)
                raise
            raise ClaudeAPIError(str(e), status_code=e.status_code, retryable=False)

        # Track cost
        inp_tok = response.usage.input_tokens
        out_tok = response.usage.output_tokens
        self.total_input_tokens += inp_tok
        self.total_output_tokens += out_tok
        pricing = self.PRICING.get(self.model, {"input": 3.0, "output": 15.0})
        cost = (inp_tok * pricing["input"] + out_tok * pricing["output"]) / 1_000_000
        self.total_cost_usd += cost
        self.call_count += 1

        self.logger.debug(
            f"API #{self.call_count}: {inp_tok}+{out_tok} tok, ${cost:.4f}, {time.time()-start:.1f}s",
            phase=phase)
        self.logger.report_cost(self.total_cost_usd, self.total_input_tokens + self.total_output_tokens)

        text = response.content[0].text
        self._set_cache(cache_key, text)
        return text

    def call_json(self, system: str, user: str, max_tokens: int = 4096,
                  phase: str = None) -> dict | list:
        """Call Claude expecting JSON. Strips code fences, retries on parse failure."""
        raw = self.call(system, user, max_tokens=max_tokens, temperature=0.0, phase=phase)
        text = raw.strip()
        
        # Strip ```json ... ```
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Fallback: extract JSON from mixed content
            match = re.search(r'[\[{].*[\]}]', text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            raise ClaudeAPIError(f"Non-JSON response: {text[:200]}...", retryable=True)

    def get_cost_summary(self) -> dict:
        return {
            "calls": self.call_count,
            "input_tokens": self.total_input_tokens,
            "output_tokens": self.total_output_tokens,
            "cost_usd": round(self.total_cost_usd, 4),
        }
```

---

## TASK 1.6: Web HTTP Client

**File: `pipeline/clients/web_client.py`**

```python
"""Rate-limited HTTP client for scraping documentation."""

import time
import httpx
from ..core.errors import SeekersError


class WebClient:
    def __init__(self, rpm: int = 10, timeout: int = 30):
        self.min_interval = 60.0 / rpm
        self._last = 0.0
        self._client = httpx.Client(
            timeout=timeout,
            headers={"User-Agent": "SkillFactory/1.0 (knowledge-base-builder)"},
            follow_redirects=True,
        )

    def get(self, url: str) -> str:
        elapsed = time.time() - self._last
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        try:
            r = self._client.get(url)
            self._last = time.time()
            r.raise_for_status()
            return r.text
        except httpx.HTTPStatusError as e:
            raise SeekersError(f"HTTP {e.response.status_code}: {url}")
        except httpx.RequestError as e:
            raise SeekersError(f"Request failed: {url} — {e}")

    def get_batch(self, urls: list[str]) -> dict[str, str | None]:
        results = {}
        for url in urls:
            try:
                results[url] = self.get(url)
            except SeekersError:
                results[url] = None
        return results

    def close(self):
        self._client.close()
```

**SESSION 1 COMPLETE CHECK:**
```bash
cd pipeline
pip install -r requirements.txt
python3 -c "
from core.types import KnowledgeAtom, BuildConfig, PipelineState, PhaseId
from core.logger import PipelineLogger
from core.config import load_config
from core.errors import PipelineError, PhaseError
from core.utils import chunk_text, estimate_tokens
from clients.claude_client import ClaudeClient
from clients.web_client import WebClient
print('✅ Session 1: All Foundation imports OK')
"
```

---

# ═══════════════════════════════════════════════════════
# SESSION 2: EPIC 2 — SEEKERS ENGINE
# ═══════════════════════════════════════════════════════

## TASK 2.1: Scraper

**File: `pipeline/seekers/scraper.py`**

```python
"""Fetch content from documentation URLs."""

import hashlib
import re
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Optional

from ..clients.web_client import WebClient
from ..core.logger import PipelineLogger
from ..core.errors import SeekersError


@dataclass
class ScrapedPage:
    url: str
    title: str
    content_html: str
    content_text: str
    source_type: str
    scraped_at: str
    content_hash: str
    status: str  # "success" | "failed"
    error: Optional[str] = None


class SeeksScraper:
    def __init__(self, web_client: WebClient, logger: PipelineLogger):
        self.client = web_client
        self.logger = logger

    def scrape_url(self, url: str, source_type: str = "auto") -> ScrapedPage:
        if source_type == "auto":
            source_type = self._detect_type(url)

        try:
            if source_type == "github":
                html = self._fetch_github(url)
            else:
                html = self.client.get(url)

            # Extract title from <title> tag
            import re as _re
            title_match = _re.search(r'<title[^>]*>([^<]+)</title>', html, _re.IGNORECASE)
            title = title_match.group(1).strip() if title_match else url.split('/')[-1]

            # Basic text extraction for content_text
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'lxml')
            text = soup.get_text(separator='\n', strip=True)

            return ScrapedPage(
                url=url, title=title, content_html=html, content_text=text,
                source_type=source_type,
                scraped_at=datetime.now(timezone.utc).isoformat(),
                content_hash=hashlib.sha256(html.encode()).hexdigest()[:16],
                status="success",
            )
        except Exception as e:
            return ScrapedPage(
                url=url, title="", content_html="", content_text="",
                source_type=source_type,
                scraped_at=datetime.now(timezone.utc).isoformat(),
                content_hash="", status="failed", error=str(e),
            )

    def scrape_batch(self, sources: list[dict]) -> list[ScrapedPage]:
        results = []
        for src in sources:
            url = src.get("url", "")
            stype = src.get("type", "documentation")
            self.logger.debug(f"Scraping {url}...")
            results.append(self.scrape_url(url, stype))
        return results

    def _detect_type(self, url: str) -> str:
        if "github.com" in url:
            return "github"
        if "developers.facebook.com" in url:
            return "api_docs"
        if "business/help" in url:
            return "help_center"
        return "html"

    def _fetch_github(self, url: str) -> str:
        """Convert GitHub blob URL to raw content URL."""
        raw_url = url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
        return self.client.get(raw_url)
```

---

## TASK 2.2: Parser

**File: `pipeline/seekers/parser.py`**

```python
"""Parse HTML/Markdown into structured BaselineEntry objects."""

import re
import hashlib
from datetime import datetime, timezone
from bs4 import BeautifulSoup

from ..core.types import BaselineEntry


# Vietnamese + English stop words
STOP_WORDS = frozenset({
    'là', 'và', 'của', 'các', 'có', 'được', 'cho', 'trong', 'với', 'này', 'một', 'để',
    'không', 'khi', 'thì', 'từ', 'đã', 'sẽ', 'như', 'nhưng', 'cũng', 'về', 'theo',
    'the', 'a', 'an', 'and', 'or', 'is', 'in', 'to', 'for', 'of', 'with', 'on', 'at',
    'by', 'this', 'that', 'it', 'be', 'as', 'are', 'was', 'were', 'been', 'has', 'have',
})


class SeekersParser:

    def parse_html(self, html: str, url: str, source_type: str) -> list[BaselineEntry]:
        soup = BeautifulSoup(html, 'lxml')
        for tag in soup.find_all(['script', 'style', 'nav', 'footer', 'header', 'aside']):
            tag.decompose()

        main = soup.find('main') or soup.find('article') or soup.find('div', class_=re.compile(r'content|body|main'))
        if not main:
            main = soup.body or soup

        sections = self._split_by_headings(main, url)
        entries = []
        for sec in sections:
            if len(sec['content'].strip()) < 50:
                continue
            entry_id = hashlib.md5((url + sec['title']).encode()).hexdigest()[:10]
            entries.append(BaselineEntry(
                id=f"bl_{entry_id}",
                title=sec['title'],
                content=sec['content'],
                source_url=url,
                source_type=source_type,
                section_path=sec['path'],
                keywords=self._extract_keywords(sec['content']),
                last_scraped=datetime.now(timezone.utc).isoformat(),
                content_hash=hashlib.sha256(sec['content'].encode()).hexdigest()[:16],
            ))
        return entries

    def _split_by_headings(self, element, base_url: str) -> list[dict]:
        sections = []
        current_title = "Introduction"
        current_content = []
        current_path = [current_title]

        for child in element.children:
            if hasattr(child, 'name') and child.name and re.match(r'^h[1-3]$', child.name):
                # Save previous section
                if current_content:
                    text = '\n'.join(current_content).strip()
                    if text:
                        sections.append({
                            'title': current_title,
                            'content': text,
                            'path': list(current_path),
                        })
                current_title = child.get_text(strip=True) or "Untitled"
                current_content = []
                level = int(child.name[1])
                current_path = current_path[:level-1] + [current_title]
            else:
                text = child.get_text(strip=True) if hasattr(child, 'get_text') else str(child).strip()
                if text:
                    current_content.append(text)

        # Last section
        if current_content:
            text = '\n'.join(current_content).strip()
            if text:
                sections.append({'title': current_title, 'content': text, 'path': list(current_path)})

        return sections

    def _extract_keywords(self, text: str, max_kw: int = 10) -> list[str]:
        words = re.findall(r'\b\w{3,}\b', text.lower())
        freq = {}
        for w in words:
            if w not in STOP_WORDS and not w.isdigit():
                freq[w] = freq.get(w, 0) + 1
        return sorted(freq, key=freq.get, reverse=True)[:max_kw]

    def parse_markdown(self, markdown: str, url: str) -> list[BaselineEntry]:
        """Parse Markdown by splitting on # headings."""
        sections = []
        current_title = "Introduction"
        current_lines = []

        for line in markdown.split('\n'):
            match = re.match(r'^(#{1,3})\s+(.+)', line)
            if match:
                if current_lines:
                    content = '\n'.join(current_lines).strip()
                    if content:
                        sections.append({'title': current_title, 'content': content, 'path': [current_title]})
                current_title = match.group(2).strip()
                current_lines = []
            else:
                current_lines.append(line)

        if current_lines:
            content = '\n'.join(current_lines).strip()
            if content:
                sections.append({'title': current_title, 'content': content, 'path': [current_title]})

        entries = []
        for sec in sections:
            if len(sec['content']) < 50:
                continue
            eid = hashlib.md5((url + sec['title']).encode()).hexdigest()[:10]
            entries.append(BaselineEntry(
                id=f"bl_{eid}", title=sec['title'], content=sec['content'],
                source_url=url, source_type="markdown", section_path=sec['path'],
                keywords=self._extract_keywords(sec['content']),
                last_scraped=datetime.now(timezone.utc).isoformat(),
                content_hash=hashlib.sha256(sec['content'].encode()).hexdigest()[:16],
            ))
        return entries
```

---

## TASK 2.3: Cache

**File: `pipeline/seekers/cache.py`**

```python
"""SQLite-backed cache for Seekers baseline knowledge base."""

import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone, timedelta

from ..core.types import BaselineEntry


class SeekersCache:
    def __init__(self, cache_dir: str, ttl_hours: int = 168):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = str(self.cache_dir / "seekers_cache.db")
        self.ttl = timedelta(hours=ttl_hours)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS baseline_entries (
                id TEXT PRIMARY KEY, title TEXT NOT NULL, content TEXT NOT NULL,
                source_url TEXT, source_type TEXT, section_path TEXT,
                keywords TEXT, last_scraped TEXT, content_hash TEXT)""")
            conn.execute("""CREATE TABLE IF NOT EXISTS scrape_status (
                url TEXT PRIMARY KEY, last_scraped TEXT,
                entry_count INTEGER, content_hash TEXT, status TEXT)""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_src ON baseline_entries(source_url)")

    def store_entries(self, entries: list[BaselineEntry]) -> int:
        with sqlite3.connect(self.db_path) as conn:
            for e in entries:
                conn.execute("""INSERT OR REPLACE INTO baseline_entries
                    (id, title, content, source_url, source_type, section_path, keywords, last_scraped, content_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (e.id, e.title, e.content, e.source_url, e.source_type,
                     json.dumps(e.section_path), json.dumps(e.keywords),
                     e.last_scraped, e.content_hash))
            # Update scrape status
            if entries:
                url = entries[0].source_url
                conn.execute("""INSERT OR REPLACE INTO scrape_status
                    (url, last_scraped, entry_count, content_hash, status)
                    VALUES (?, ?, ?, ?, ?)""",
                    (url, entries[0].last_scraped, len(entries), entries[0].content_hash, "success"))
        return len(entries)

    def get_all_entries(self) -> list[BaselineEntry]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("SELECT * FROM baseline_entries").fetchall()
        return [self._row_to_entry(r) for r in rows]

    def get_entries_by_source(self, url: str) -> list[BaselineEntry]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("SELECT * FROM baseline_entries WHERE source_url = ?", (url,)).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def search_entries(self, keyword: str) -> list[BaselineEntry]:
        kw = f"%{keyword.lower()}%"
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM baseline_entries WHERE LOWER(title) LIKE ? OR LOWER(content) LIKE ? OR LOWER(keywords) LIKE ?",
                (kw, kw, kw)).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def is_fresh(self, url: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT last_scraped FROM scrape_status WHERE url = ?", (url,)).fetchone()
        if not row or not row[0]:
            return False
        scraped = datetime.fromisoformat(row[0].replace('Z', '+00:00'))
        return datetime.now(timezone.utc) - scraped < self.ttl

    def get_entry_count(self) -> int:
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute("SELECT COUNT(*) FROM baseline_entries").fetchone()[0]

    def clear(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM baseline_entries")
            conn.execute("DELETE FROM scrape_status")

    def _row_to_entry(self, row) -> BaselineEntry:
        return BaselineEntry(
            id=row[0], title=row[1], content=row[2], source_url=row[3],
            source_type=row[4], section_path=json.loads(row[5] or '[]'),
            keywords=json.loads(row[6] or '[]'), last_scraped=row[7] or "",
            content_hash=row[8] or "",
        )
```

---

## TASK 2.4: Lookup & Taxonomy

**File: `pipeline/seekers/lookup.py`**

```python
"""Query interface for the Seekers knowledge base."""

from .cache import SeekersCache
from ..core.types import BaselineEntry
from ..core.logger import PipelineLogger


class SeekersLookup:
    def __init__(self, cache: SeekersCache, logger: PipelineLogger):
        self.cache = cache
        self.logger = logger

    def lookup_by_topic(self, topic: str, max_results: int = 5) -> list[BaselineEntry]:
        keywords = [w for w in topic.lower().split() if len(w) >= 3]
        results = []
        seen = set()
        for kw in keywords:
            for entry in self.cache.search_entries(kw):
                if entry.id not in seen:
                    seen.add(entry.id)
                    results.append(entry)
        return results[:max_results]

    def lookup_by_keyword(self, keyword: str) -> list[BaselineEntry]:
        return self.cache.search_entries(keyword)

    def verify_claim(self, claim: str, topic: str) -> dict:
        relevant = self.lookup_by_topic(topic, max_results=3)
        if not relevant:
            return {"verified": False, "confidence": 0.0, "evidence": "",
                    "source_url": "", "match_type": "no_match"}

        claim_words = set(claim.lower().split())
        best, best_score = None, 0.0
        for entry in relevant:
            words = set(entry.content.lower().split())
            score = len(claim_words & words) / max(len(claim_words), 1)
            if score > best_score:
                best_score, best = score, entry

        return {
            "verified": best_score > 0.3,
            "confidence": round(best_score, 2),
            "evidence": best.content[:500] if best else "",
            "source_url": best.source_url if best else "",
            "match_type": "exact" if best_score > 0.7 else "partial" if best_score > 0.3 else "no_match",
        }

    def get_coverage_matrix(self, topics: list[str]) -> list[dict]:
        results = []
        for topic in topics:
            hits = self.lookup_by_topic(topic, max_results=1)
            results.append({
                "topic": topic,
                "covered": len(hits) > 0,
                "entries_count": len(hits),
                "confidence": hits[0].keywords.__len__() / 10 if hits else 0,
            })
        return results
```

**File: `pipeline/seekers/taxonomy.py`**

```python
"""Domain-specific category taxonomies for Knowledge Atom tagging."""

TAXONOMIES = {
    "fb_ads": {
        "name": "Facebook Ads",
        "categories": [
            {"id": "campaign_management", "name": "Campaign Management",
             "subcategories": ["campaign_creation", "campaign_types", "objectives", "campaign_budget"]},
            {"id": "audience_targeting", "name": "Audience & Targeting",
             "subcategories": ["custom_audience", "lookalike", "interest_targeting", "retargeting"]},
            {"id": "ad_creative", "name": "Ad Creative",
             "subcategories": ["ad_formats", "copywriting", "images_video", "cta"]},
            {"id": "pixel_tracking", "name": "Pixel & Tracking",
             "subcategories": ["pixel_setup", "events", "conversions", "attribution"]},
            {"id": "optimization", "name": "Optimization & Scaling",
             "subcategories": ["ab_testing", "scaling", "budget_optimization", "performance"]},
            {"id": "policy_compliance", "name": "Policies & Compliance",
             "subcategories": ["ad_policies", "account_health", "review_process", "restricted"]},
        ]
    },
    "google_ads": {
        "name": "Google Ads",
        "categories": [
            {"id": "search_ads", "name": "Search Ads", "subcategories": ["keywords", "match_types", "quality_score"]},
            {"id": "display_ads", "name": "Display Network", "subcategories": ["placements", "audiences", "creative"]},
            {"id": "shopping", "name": "Shopping Ads", "subcategories": ["feed", "merchant_center", "campaigns"]},
            {"id": "bidding", "name": "Bidding Strategies", "subcategories": ["smart_bidding", "manual", "target_roas"]},
            {"id": "analytics", "name": "Analytics & Tracking", "subcategories": ["conversion", "ga4", "attribution"]},
            {"id": "optimization", "name": "Optimization", "subcategories": ["testing", "scripts", "automation"]},
        ]
    },
    "custom": {
        "name": "Custom",
        "categories": [
            {"id": "fundamentals", "name": "Fundamentals", "subcategories": ["concepts", "terminology", "principles"]},
            {"id": "procedures", "name": "Procedures", "subcategories": ["workflows", "steps", "best_practices"]},
            {"id": "tools", "name": "Tools & Technology", "subcategories": ["setup", "configuration", "integration"]},
            {"id": "strategy", "name": "Strategy", "subcategories": ["planning", "analysis", "decision_making"]},
            {"id": "advanced", "name": "Advanced Topics", "subcategories": ["optimization", "troubleshooting", "edge_cases"]},
            {"id": "compliance", "name": "Compliance & Rules", "subcategories": ["regulations", "guidelines", "safety"]},
        ]
    }
}


def get_taxonomy(domain: str) -> dict:
    return TAXONOMIES.get(domain, TAXONOMIES["custom"])


def get_all_categories(domain: str) -> list[str]:
    tax = get_taxonomy(domain)
    return [c["id"] for c in tax.get("categories", [])]


def get_all_subcategories(domain: str) -> list[str]:
    tax = get_taxonomy(domain)
    result = []
    for cat in tax.get("categories", []):
        result.extend(cat.get("subcategories", []))
    return result
```

**SESSION 2 COMPLETE CHECK:**
```bash
python3 -c "
from pipeline.seekers.scraper import SeeksScraper, ScrapedPage
from pipeline.seekers.parser import SeekersParser
from pipeline.seekers.cache import SeekersCache
from pipeline.seekers.lookup import SeekersLookup
from pipeline.seekers.taxonomy import get_taxonomy, get_all_categories
print('✅ Session 2: Seekers Engine imports OK')
print(f'  FB Ads categories: {get_all_categories(\"fb_ads\")}')
"
```

---

# ═══════════════════════════════════════════════════════
# SESSION 3-6: Phases, Orchestrator, Integration
# ═══════════════════════════════════════════════════════
# 
# Remaining sessions detailed in companion files:
# → ROADMAP-PART1-TASKS.md (Tasks 3.0-3.5, 4.1-4.2, 5.1-5.3, 6.1-6.3)
# → ROADMAP-PART2-CONTRACTS.md (Data schemas, API strategy, migration checklist)
# → ROADMAP-PART3-PROMPTS-TIMELINE.md (Prompt library, Gantt, risks)
#
# For Claude Code: Read Session 1 + 2 code above first,
# then follow ROADMAP-PART1-TASKS.md for phase implementations.
# ═══════════════════════════════════════════════════════

# IMPORTANT: After Session 2, continue with these phases in order:

# SESSION 3: Create all prompt files (pipeline/prompts/p1-p5)
#             Then implement p0_baseline.py, p1_audit.py, p2_extract.py

# SESSION 4: Implement p3_dedup.py, p4_verify.py, p5_build.py

# SESSION 5: Create orchestrator/runner.py, orchestrator/state.py, cli.py

# SESSION 6: Integration (swap mock→real), .env update, Dockerfile, tests

# Each phase implementation follows the pattern:
# 1. Import from core + clients + seekers
# 2. def run_pN(config, claude, seekers, logger) -> PhaseResult
# 3. Use logger.phase_start/progress/complete for UI updates
# 4. Write output JSON to config.output_dir
# 5. Return PhaseResult with scores and metrics
