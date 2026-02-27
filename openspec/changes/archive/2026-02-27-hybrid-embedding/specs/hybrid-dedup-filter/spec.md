## ADDED Requirements

### Requirement: Embedding pre-filter before LLM dedup
P3 dedup SHALL compute embedding similarity for all atom pairs BEFORE sending to LLM. Three zones: auto-merge (≥0.85), uncertain (0.60-0.85, send to LLM), unique (<0.60, skip LLM).

#### Scenario: Auto-merge high similarity
- **WHEN** two atoms have cosine similarity ≥ 0.85
- **THEN** system auto-merges them (keep higher confidence atom, mark other as duplicate)
- **AND** LLM is NOT called for this pair

#### Scenario: Uncertain range sent to LLM
- **WHEN** two atoms have cosine similarity between 0.60 and 0.85
- **THEN** system sends the pair to LLM for classification (DUPLICATE/CONTRADICTION/OUTDATED/UNIQUE)

#### Scenario: Low similarity skipped
- **WHEN** two atoms have cosine similarity < 0.60
- **THEN** system marks both as UNIQUE
- **AND** LLM is NOT called for this pair

### Requirement: LLM still required for contradiction and outdated
Embedding pre-filter SHALL only auto-resolve DUPLICATE. CONTRADICTION and OUTDATED detection MUST go through LLM because embedding cannot distinguish semantic nuance (e.g., "CPC $0.50" vs "CPC $1.20" = high cosine but OUTDATED).

#### Scenario: High cosine but contradicting data
- **WHEN** atoms have cosine ≥ 0.85 but contain conflicting values
- **THEN** auto-merge treats them as duplicate (keeps higher confidence)
- **AND** this is acceptable trade-off — embedding is a filter, not classifier

### Requirement: Cross-source dedup scope only
Embedding pre-filter SHALL only apply to cross-source dedup step. Per-category dedup logic SHALL remain unchanged (LLM-only).

#### Scenario: Per-category dedup unchanged
- **WHEN** per-category dedup runs
- **THEN** existing LLM-only logic is used regardless of embedding availability

### Requirement: Backward compatible without embedding
When no embedding API key is configured, P3 SHALL fall back to existing LLM-only dedup behavior. No functionality regression.

#### Scenario: No embedding key
- **WHEN** `embedding_api_key` is empty
- **THEN** P3 runs existing LLM-only dedup flow (identical to pre-Sprint 3)

### Requirement: Log embedding filter stats
P3 SHALL log the count of auto-merge, uncertain, and unique pairs after embedding filter via PipelineLogger.

#### Scenario: Stats logged
- **WHEN** embedding pre-filter completes
- **THEN** logger outputs: auto-merge count, uncertain count, unique count
