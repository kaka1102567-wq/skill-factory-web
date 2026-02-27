## MODIFIED Requirements

### Requirement: Concise repr output

KnowledgeAtom MUST provide a short, human-readable repr showing only essential fields for quick identification during debugging.

#### Scenario: Default repr shows key fields only

- **WHEN** a KnowledgeAtom instance is printed or repr() is called
- **THEN** output shows `id`, `title` (truncated to 50 chars), `status`, and `confidence`
- **AND** the format is: `KnowledgeAtom(id='...', title='...', status='...', confidence=0.85)`

#### Scenario: Long titles are truncated

- **WHEN** `title` exceeds 50 characters
- **THEN** it is truncated with `...` suffix
- **AND** total repr stays readable on a single line

#### Scenario: Full data access unaffected

- **WHEN** `to_dict()` or `to_json()` is called
- **THEN** all 16 fields are included as before
- **AND** no data is lost from the repr change

## ADDED Requirements

### Requirement: 4-level Confidence Map in P5
P5 `_generate_confidence_map()` SHALL categorize atoms into 4 levels based on P4 embedding verification scores: HIGH (≥0.70), MEDIUM (0.50-0.70), LOW (<0.50), UNKNOWN (future use). Upgraded from 2-level.

#### Scenario: Atoms with embedding scores
- **WHEN** atoms have verification_note containing `score X.XX`
- **THEN** they are categorized: ≥0.70 → HIGH, 0.50-0.70 → MEDIUM, <0.50 → LOW

#### Scenario: Backward compatible without scores
- **WHEN** atoms have no score in verification_note but have baseline_reference
- **THEN** they are categorized as HIGH (has reference) or LOW (no reference)

#### Scenario: Score extraction
- **WHEN** `_extract_verification_score(note)` is called
- **THEN** it parses float from `score\s+([\d.]+)` regex pattern
- **AND** returns None if no match

### Requirement: Conditional multi-source enrichment in P5
P5 SHALL enrich atoms when build has ≥3 source files. Atoms covering same topic (embedding similarity > 0.80 from different sources) get cross-reference note "Corroborated by X sources". Skip if <3 files or no embedding client.

#### Scenario: 3+ sources enrichment
- **WHEN** build has ≥3 source files and embedding client available
- **THEN** system clusters similar atoms from different sources
- **AND** adds cross-reference notes to clustered atoms

#### Scenario: Less than 3 sources skip
- **WHEN** build has <3 source files
- **THEN** enrichment is skipped entirely, atoms returned unchanged

#### Scenario: No embedding client skip
- **WHEN** embedding client is unavailable
- **THEN** enrichment is skipped entirely, atoms returned unchanged
