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
    seekers_output_dir: str = ""
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
