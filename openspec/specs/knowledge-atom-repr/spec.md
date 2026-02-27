# knowledge-atom-repr Specification

## Purpose
TBD - created by archiving change add-knowledge-atom-repr. Update Purpose after archive.
## Requirements
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

