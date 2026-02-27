# cache-key-safety Specification

## Purpose
TBD - created by archiving change multi-provider-opus-tier. Update Purpose after archive.
## Requirements
### Requirement: Cache key MUST include model name

Cache key computation MUST include the active model name to prevent cross-model/cross-provider cache collisions.

#### Scenario: Different models produce different cache keys

- **WHEN** the same system+user prompt is called with model A then model B
- **THEN** the cache keys MUST be different
- **AND** model B call SHALL NOT return model A's cached response

#### Scenario: Same model produces same cache key

- **WHEN** the same system+user prompt is called twice with the same model
- **THEN** the cache key MUST be identical
- **AND** the second call SHALL return the cached response

