## ADDED Requirements

### Requirement: P2 atoms SHALL be cached per source file
The system SHALL cache extracted atoms per source file using a composite key of `file_content_hash + model + prompt_version + tier`. On subsequent builds, files with matching cache keys SHALL skip Claude API extraction and return cached atoms directly.

#### Scenario: Cache hit on unchanged file
- **WHEN** a transcript file has identical content hash, model, prompt version, and tier as a previous build
- **THEN** the system SHALL return cached atoms without calling Claude API

#### Scenario: Cache miss on new file
- **WHEN** a transcript file has no matching cache entry
- **THEN** the system SHALL extract atoms normally via Claude API and save results to cache

#### Scenario: Cache miss on changed content
- **WHEN** a transcript file content has changed since last build (different content hash)
- **THEN** the system SHALL re-extract atoms and update cache with new results

#### Scenario: Cache miss on different model
- **WHEN** the build uses a different Claude model than the cached entry
- **THEN** the system SHALL re-extract atoms for that file

#### Scenario: Cache miss on prompt version bump
- **WHEN** the prompt version constant has been incremented since cached entry
- **THEN** the system SHALL re-extract atoms for that file

### Requirement: P1 inventory SHALL be cached per domain and file set
The system SHALL cache audit inventory using a composite key of `domain + sorted(file_content_hashes) + model + tier`. Cache hit requires EXACT same file set — adding or removing any file SHALL result in a cache miss.

#### Scenario: Cache hit on identical file set
- **WHEN** a build has the same domain, sorted file content hashes, model, and tier as a cached inventory
- **THEN** the system SHALL return cached inventory without running P1 audit

#### Scenario: Cache miss on file set change
- **WHEN** a file is added to or removed from the transcript set
- **THEN** the system SHALL run full P1 audit and cache the new inventory

### Requirement: Embeddings SHALL be cached per text and model
The system SHALL cache embedding vectors using a composite key of `text_hash + embedding_model`. Cached vectors SHALL be returned without calling the embedding API.

#### Scenario: Cache hit on identical text
- **WHEN** embedding is requested for text with an existing cache entry using the same embedding model
- **THEN** the system SHALL return cached vectors without API call

#### Scenario: Cache miss on different embedding model
- **WHEN** a different embedding model is specified
- **THEN** the system SHALL compute new embeddings and cache them

### Requirement: Cache SHALL use content-based file hashing
File identity SHALL be determined by SHA256 hash of file content (truncated to 16 hex chars), NOT by filename or path. Renaming a file without changing content SHALL result in a cache hit.

#### Scenario: File renamed but content unchanged
- **WHEN** a transcript file is renamed but content is identical
- **THEN** the system SHALL return cached atoms (same content hash)

#### Scenario: Same filename but different content
- **WHEN** a transcript file has the same name but different content
- **THEN** the system SHALL re-extract (different content hash)

### Requirement: Cache SHALL expire after TTL
Cache entries SHALL have a configurable TTL (default 30 days). Expired entries SHALL be deleted on read and treated as cache misses.

#### Scenario: Entry within TTL
- **WHEN** a cache entry timestamp is within TTL period
- **THEN** the system SHALL return cached data

#### Scenario: Entry past TTL
- **WHEN** a cache entry timestamp exceeds TTL period
- **THEN** the system SHALL delete the entry and return cache miss

### Requirement: Cache SHALL degrade gracefully
Cache failures (corrupt JSON, missing directory, write errors) SHALL NOT crash the pipeline. The system SHALL log a warning and proceed with normal processing.

#### Scenario: Corrupt cache file
- **WHEN** a cache JSON file is malformed
- **THEN** the system SHALL delete the corrupt file, return cache miss, and continue processing

#### Scenario: Cache directory write failure
- **WHEN** cache write fails due to OS error
- **THEN** the system SHALL skip cache save silently and continue pipeline execution

### Requirement: Cache SHALL use atomic writes
Cache writes SHALL use a write-to-temp-then-rename pattern to prevent partial/corrupt files from concurrent access.

#### Scenario: Concurrent write safety
- **WHEN** cache writes to a .tmp file and renames atomically
- **THEN** readers SHALL never see partial JSON content

### Requirement: P2 SHALL only cache Stream A transcript extraction
Gap-fill atoms (Stream B) and code atoms (Stream C) SHALL NOT be cached because they depend on P1 inventory output which may change between builds.

#### Scenario: Stream B not cached
- **WHEN** gap-fill atoms are extracted in P2
- **THEN** the system SHALL NOT cache these atoms (they depend on current P1 inventory)

### Requirement: CLI SHALL provide cache management commands
The system SHALL provide `cache-stats` and `cache-clear` CLI subcommands. Output SHALL be JSON format for both human reading and machine parsing.

#### Scenario: cache-stats shows usage
- **WHEN** user runs `cache-stats` command
- **THEN** the system SHALL output JSON with atom_entries, inventory_entries, embedding_entries, total_size_mb, oldest_days, newest_days

#### Scenario: cache-clear with --all
- **WHEN** user runs `cache-clear --all`
- **THEN** the system SHALL delete all cache entries and report count cleared

#### Scenario: cache-clear with --older-than
- **WHEN** user runs `cache-clear --older-than 30`
- **THEN** the system SHALL delete only entries older than 30 days

### Requirement: Prompt files SHALL declare version constants
Each prompt file SHALL export a `PROMPT_VERSION` string constant. This version SHALL be included in cache keys. Changing a prompt template MUST be accompanied by a version bump to invalidate cached results.

#### Scenario: Version constant exists
- **WHEN** `p1_audit_prompts.py` and `p2_extract_prompts.py` are loaded
- **THEN** each SHALL have a `PROMPT_VERSION` constant (e.g., `"p1_audit_v1"`, `"p2_extract_v1"`)
