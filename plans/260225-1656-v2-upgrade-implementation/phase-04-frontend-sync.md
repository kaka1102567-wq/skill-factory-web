# Phase 4: Frontend Sync

## Context Links
- Source: `UPGRADE-PLAN-FINAL.md` Tasks 4E, 4F, 4G, 14
- Sprint: 2 (Core Features)
- Patches: P5 (4 frontend sync points)

## Overview
- **Priority**: P0
- **Status**: complete
- **Description**: Add P6 to TypeScript types, PHASES array, INITIAL_PHASES, PHASE_COLORS, and refactor parseInt to PHASE_ORDER
- **Estimated effort**: 0.5 days

## Dependencies
- **Depends on**: Phase 3 (Python phases must exist before frontend references them)
- **Blocks**: Phase 5, Phase 6

## File Ownership

| File | Action | Task |
|------|--------|------|
| `types/build.ts` | **MODIFY** PhaseId type + PHASES array | Task 4E |
| `components/build/phase-stepper.tsx` | **MODIFY** PHASE_COLORS | Task 4F |
| `hooks/use-build-stream.ts` | **MODIFY** INITIAL_PHASES + PHASE_ORDER refactor | Task 4G + Task 14 |

## Key Insights

### PATCH P5: 4 Frontend Sync Points
The frontend has 4 separate places that enumerate phases. ALL must include P6:

```
1. types/build.ts      -> PhaseId type has "p6"
2. types/build.ts      -> PHASES array has P6 entry
3. use-build-stream.ts -> INITIAL_PHASES has P6 entry
4. phase-stepper.tsx   -> PHASE_COLORS has p6 color
```

Missing ANY of these = P6 invisible or broken on stepper.

### P55 NOT added to frontend
- P55 is a sub-step that logs under phase="p5"
- Frontend never sees "p55" as a phase
- parseInt("p55") = 55 would break stepper indexing

### PHASE_ORDER Refactor (Task 14)
- Current code uses `parseInt(phase.replace("p",""))` in 3 places
- Works now because p0-p6 are sequential (index = parseInt value)
- Refactor to `PHASE_ORDER` map for future-proofing

## Implementation Steps

### Task 4E: Update types/build.ts (UPGRADE-PLAN lines 1241-1258)

1. Update PhaseId type:
```typescript
export type PhaseId = "p0" | "p1" | "p2" | "p3" | "p4" | "p5" | "p6";
// Do NOT add "p55"
```

2. Update PHASES array:
```typescript
export const PHASES: Omit<PhaseInfo, "status" | "score" | "progress">[] = [
  { id: "p0", name: "Baseline", icon: "📖", tool: "Seekers" },
  { id: "p1", name: "Audit", icon: "🔍", tool: "Claude" },
  { id: "p2", name: "Extract", icon: "⚛️", tool: "Claude" },
  { id: "p3", name: "Deduplicate", icon: "🔄", tool: "Claude+Seekers" },
  { id: "p4", name: "Verify", icon: "✅", tool: "Seekers+Claude" },
  { id: "p5", name: "Architect", icon: "📦", tool: "Claude+Seekers" },
  { id: "p6", name: "Optimize", icon: "🎯", tool: "Claude" },
];
```

### Task 4F: Update phase-stepper.tsx (UPGRADE-PLAN lines 1260-1274)

Add P6 color to PHASE_COLORS:
```typescript
const PHASE_COLORS: Record<string, string> = {
  p0: "text-indigo-400 border-indigo-400",
  p1: "text-amber-400 border-amber-400",
  p2: "text-emerald-400 border-emerald-400",
  p3: "text-purple-400 border-purple-400",
  p4: "text-red-400 border-red-400",
  p5: "text-cyan-400 border-cyan-400",
  p6: "text-rose-400 border-rose-400",
};
```

### Task 4G: Update use-build-stream.ts (UPGRADE-PLAN lines 1276-1298)

1. Update INITIAL_PHASES:
```typescript
const INITIAL_PHASES: PhaseState[] = [
  { id: "p0", status: "pending", progress: 0, score: null, name: "Baseline" },
  { id: "p1", status: "pending", progress: 0, score: null, name: "Audit" },
  { id: "p2", status: "pending", progress: 0, score: null, name: "Extract" },
  { id: "p3", status: "pending", progress: 0, score: null, name: "Deduplicate" },
  { id: "p4", status: "pending", progress: 0, score: null, name: "Verify" },
  { id: "p5", status: "pending", progress: 0, score: null, name: "Architect" },
  { id: "p6", status: "pending", progress: 0, score: null, name: "Optimize" },
];
// Do NOT add P55
```

### Task 14: PHASE_ORDER Refactor (UPGRADE-PLAN lines 2284-2319)

In `hooks/use-build-stream.ts`, AFTER INITIAL_PHASES, add:

```typescript
const PHASE_ORDER: Record<string, number> =
  Object.fromEntries(INITIAL_PHASES.map((p, i) => [p.id, i]));
const phaseRank = (id: string) => PHASE_ORDER[id] ?? -1;
```

Replace 3 `parseInt` usages:

**"state" handler (around line 79)**:
```typescript
const currentRank = phaseRank(data.current_phase);
setPhases((prev) =>
  prev.map((p) => {
    const thisRank = phaseRank(p.id);
    if (thisRank < currentRank) return { ...p, status: "done", progress: 100 };
    if (thisRank === currentRank)
      return { ...p, status: "running", progress: data.phase_progress || 0 };
    return p;
  })
);
```

**"phase" handler (around lines 111-112)**:
```typescript
const incomingRank = phaseRank(data.phase);
const thisRank = phaseRank(p.id);
if (thisRank < incomingRank && p.status !== "done") {
  return { ...p, status: "done", progress: 100 };
}
```

## Validation

```bash
# TypeScript compile check
npm run build

# Verify P6 renders on stepper
npm run dev
# Manual: navigate to a build page, verify 7 phases shown (P0-P6)
```

## TODO
- [ ] Task 4E: Update PhaseId type in build.ts
- [ ] Task 4E: Add P6 to PHASES array in build.ts
- [ ] Task 4F: Add p6 color to PHASE_COLORS in phase-stepper.tsx
- [ ] Task 4G: Add P6 to INITIAL_PHASES in use-build-stream.ts
- [ ] Task 14: Add PHASE_ORDER + phaseRank helper
- [ ] Task 14: Replace 3 parseInt usages with phaseRank
- [ ] Run `npm run build` -- compiles without errors

## Success Criteria
- `npm run build` succeeds (TypeScript type-checks all PhaseId usages)
- Phase stepper shows 7 phases (P0-P6)
- P6 has rose-400 color
- No "p55" anywhere in frontend code

## Risk Assessment
- **Low**: Small, focused changes to existing constants/types
- **Medium**: parseInt replacement must be exact -- test stepper behavior with a running build
