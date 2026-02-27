# Proposal: Add KnowledgeAtom __repr__

## Why

`KnowledgeAtom` is the core data structure used across all 7 pipeline phases. The default dataclass `__repr__` dumps all 16 fields including the lengthy `content` field, making debug output unreadable during pipeline runs.

## What Changes

- Add a concise `__repr__` to `KnowledgeAtom` showing only key identifiers: `id`, `title` (truncated), `status`, `confidence`
- Default `__str__` behavior unchanged (full dump via dataclass)

## Capabilities

### Modified Capabilities
- `knowledge-atom-debug-output`: Concise repr for faster debugging and log readability

## Impact

- `pipeline/core/types.py`: Add `__repr__` method to `KnowledgeAtom` class
