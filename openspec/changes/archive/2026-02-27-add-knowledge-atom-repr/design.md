# Design: KnowledgeAtom __repr__

## Context

`KnowledgeAtom` is a `@dataclass` with 16 fields. Dataclass auto-generates `__repr__` that dumps everything — including the verbose `content` field.

## Goals / Non-Goals

**Goals:**
- Concise single-line repr for debugging
- Show only identifying fields: `id`, `title`, `status`, `confidence`

**Non-Goals:**
- Changing `__str__` behavior
- Modifying serialization (`to_dict`, `to_json`)
- Adding repr to other dataclasses (scope creep)

## Decisions

### Decision 1: Override `__repr__` only, not `__str__`

Dataclass `__repr__` and `__str__` both use the generated repr by default. By overriding only `__repr__`, `str(atom)` will also use our concise version (since `__str__` falls back to `__repr__`). This is the desired behavior — no need to override both.

### Decision 2: Truncate title at 50 characters

50 chars keeps repr under ~120 chars total, fitting in one terminal line. Truncation uses `...` suffix.
