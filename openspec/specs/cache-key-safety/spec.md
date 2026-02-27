# cache-key-safety Specification

## Purpose
TBD - created by archiving change multi-provider-opus-tier. Update Purpose after archive.
## Requirements
### Requirement: Cache key MUST include model name
Cache keys for all cache layers (Claude response cache, build cache atoms, build cache inventory, build cache embeddings) MUST include the model identifier. Different models SHALL produce different cache keys. Additionally, build-level cache keys MUST include `prompt_version` and `quality_tier` to prevent stale results when prompts or tier settings change.

#### Scenario: Different models produce different keys
- **WHEN** the same input is processed with model A then model B
- **THEN** each SHALL have a separate cache entry (no cross-model collision)

#### Scenario: Same model returns cached response
- **WHEN** a second call uses the same model, input, prompt version, and tier
- **THEN** the system SHALL return the cached response

#### Scenario: Prompt version change invalidates cache
- **WHEN** `PROMPT_VERSION` is bumped in a prompt file
- **THEN** all cache entries using the old version SHALL be treated as misses

#### Scenario: Tier change invalidates cache
- **WHEN** `quality_tier` changes between builds (e.g., standard → premium)
- **THEN** cache entries from the previous tier SHALL be treated as misses

