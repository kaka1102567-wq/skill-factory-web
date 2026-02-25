# Code Standards & Guidelines

**Project:** skill-factory-web | **Version:** 2.12.1 | **Updated:** 2026-02-25

This document defines coding conventions, patterns, and best practices used throughout the codebase.

## TypeScript/JavaScript Frontend

### File Organization

**Naming Convention:**
- Files: `kebab-case` with descriptive names
- Components: `PascalCase` (e.g., `BuildWizard.tsx`)
- Utilities: `kebab-case` (e.g., `format-date.ts`)
- Hooks: `kebab-case` (e.g., `use-auth.ts`)

**Example Structure:**
```typescript
// components/build/build-wizard.tsx
export interface BuildWizardProps {
  onComplete: (buildId: string) => void;
}

export function BuildWizard({ onComplete }: BuildWizardProps) {
  // Functional component body
  return <form>{/* ... */}</form>;
}
```

### TypeScript Strict Mode

**Enforced Rules:**
- No `any` types (except in exceptional cases with JSDoc comment)
- Explicit return types on functions
- Non-null assertions (`!`) only when 100% sure
- Use `type` vs `interface` based on semantic meaning:
  - `type` for unions, primitives, utility types
  - `interface` for objects (encourages extension)

**Example:**
```typescript
// GOOD
interface BuildProps {
  id: string;
  status: BuildStatus;
  onRetry: () => Promise<void>;
}

function BuildCard({ id, status, onRetry }: BuildProps): JSX.Element {
  return <div>{/* ... */}</div>;
}

// BAD
function BuildCard(props: any) {
  // any is forbidden
}
```

### React Patterns

**Functional Components Only:**
- No class components
- Use `React.FC<Props>` for typed components (or just return JSX.Element)

**Custom Hooks:**
```typescript
// hooks/use-build-stream.ts
interface UseBuildStreamResult {
  logs: BuildLog[];
  currentPhase: PhaseId | null;
  isConnected: boolean;
}

export function useBuildStream(buildId: string): UseBuildStreamResult {
  const [logs, setLogs] = useState<BuildLog[]>([]);
  const [currentPhase, setCurrentPhase] = useState<PhaseId | null>(null);
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    // SSE subscription
    const eventSource = new EventSource(`/api/builds/${buildId}/logs`);

    eventSource.addEventListener("log", (e) => {
      const log = JSON.parse(e.data) as BuildLog;
      setLogs((prev) => [...prev, log]);
    });

    return () => eventSource.close();
  }, [buildId]);

  return { logs, currentPhase, isConnected };
}
```

**State Management:**
- Use React hooks (useState, useReducer) for local state
- useContext for global auth state
- Avoid external libraries (Redux, Zustand) for now

**Component Composition:**
- Break components into smaller pieces (max 200 LOC per component)
- Extract reusable logic into custom hooks
- Use compound components for complex UIs

**Example:**
```typescript
// BAD: One large component
function BuildWizard() {
  const [step, setStep] = useState(0);
  // 500 lines of template selection, upload, config, review...
}

// GOOD: Separate components + hooks
function BuildWizard() {
  const [step, setStep] = useState(0);
  return (
    <div>
      {step === 0 && <StepTemplate onNext={() => setStep(1)} />}
      {step === 1 && <StepUpload onNext={() => setStep(2)} />}
      {/* ... */}
    </div>
  );
}
```

### Styling

**Tailwind CSS 4 + shadcn/ui:**
- Use Tailwind utility classes (not custom CSS)
- Import shadcn/ui components from `@/components/ui`
- Theme: new-york style (from shadcn preset)
- Icons: lucide-react (always 18px or context-sized)

**Example:**
```typescript
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ChevronRight } from "lucide-react";

export function BuildCard() {
  return (
    <Card className="p-4 border-l-4 border-blue-500">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Build Name</h3>
        <ChevronRight className="h-5 w-5 text-gray-400" />
      </div>
    </Card>
  );
}
```

**Guidelines:**
- Use semantic color classes: `text-destructive`, `bg-secondary`, `border-primary`
- Responsive design: `md:`, `lg:` prefixes
- Spacing: stick to Tailwind scale (4px units)
- No inline styles (always use Tailwind classes)

### Error Handling

**Async Operations:**
```typescript
async function handleBuildCreate(config: BuildConfig) {
  try {
    const response = await fetch("/api/builds", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(config),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.message || "Build creation failed");
    }

    const build = await response.json() as Build;
    return build;
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown error";
    console.error("Build creation error:", message);
    throw error; // Re-throw for caller to handle (toast, UI update)
  }
}
```

**UI Error Display:**
- Use `sonner` toast library for notifications
- Show user-friendly messages (no raw API errors)
- Log full errors to console for debugging

```typescript
import { toast } from "sonner";

async function retryBuild(buildId: string) {
  try {
    await fetch(`/api/builds/${buildId}/retry`, { method: "POST" });
    toast.success("Build retry started");
  } catch (error) {
    toast.error("Failed to retry build");
    console.error(error);
  }
}
```

## Next.js API Routes

### Route Handler Pattern

**File Structure:**
```
app/api/builds/route.ts       # GET /api/builds, POST /api/builds
app/api/builds/[id]/route.ts  # GET /api/builds/[id], DELETE /api/builds/[id]
app/api/builds/[id]/logs/route.ts  # GET /api/builds/[id]/logs (SSE)
```

**Handler Signature:**
```typescript
import { NextRequest, NextResponse } from "next/server";
import { getDb } from "@/lib/db";
import { validateAuth } from "@/lib/auth";

// GET request
export async function GET(request: NextRequest) {
  // 1. Auth check
  if (!validateAuth(request)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  // 2. Parse query parameters
  const { searchParams } = new URL(request.url);
  const status = searchParams.get("status") || "all";

  // 3. Fetch from DB
  const builds = getDb().prepare("SELECT * FROM builds WHERE status = ?").all(status);

  // 4. Return response
  return NextResponse.json(builds);
}

// POST request
export async function POST(request: NextRequest) {
  if (!validateAuth(request)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    const body = await request.json();

    // Validate input
    if (!body.name || !body.config_yaml) {
      return NextResponse.json(
        { error: "Missing required fields" },
        { status: 400 }
      );
    }

    // Create in DB
    const db = getDb();
    const id = crypto.randomUUID();
    db.prepare(`
      INSERT INTO builds (id, name, config_yaml, status)
      VALUES (?, ?, ?, 'pending')
    `).run(id, body.name, body.config_yaml);

    return NextResponse.json({ id }, { status: 201 });
  } catch (error) {
    console.error("Build creation error:", error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
```

### SSE Streaming Pattern

```typescript
// app/api/builds/[id]/logs/route.ts
import { subscribe, unsubscribe } from "@/lib/sse-manager";

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  if (!validateAuth(request)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  // Create response with SSE headers
  const response = new NextResponse(null, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      "Connection": "keep-alive",
    },
  });

  // Subscribe to events
  subscribe(params.id, response);

  // Cleanup on disconnect
  request.signal.addEventListener("abort", () => {
    unsubscribe(params.id, response);
  });

  return response;
}
```

### Input Validation

**Always validate API inputs:**
```typescript
export async function POST(request: NextRequest) {
  const body = await request.json();

  // Type guard
  if (typeof body.name !== "string" || body.name.length === 0) {
    return NextResponse.json(
      { error: "name must be non-empty string" },
      { status: 400 }
    );
  }

  if (!["pending", "running", "completed"].includes(body.status)) {
    return NextResponse.json(
      { error: "Invalid status value" },
      { status: 400 }
    );
  }

  // Process
  // ...
}
```

**Future:** Consider Zod for schema validation.

## Middleware

**Pattern:**
```typescript
// middleware.ts
import { NextRequest, NextResponse } from "next/server";
import { getAuthToken } from "@/lib/auth";

export function middleware(request: NextRequest) {
  // Skip auth for public routes
  if (request.nextUrl.pathname === "/api/auth") {
    return NextResponse.next();
  }

  // Guard /api/* routes
  if (request.nextUrl.pathname.startsWith("/api/")) {
    const token = getAuthToken(request);
    if (!token) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon).*)"],
};
```

## Database (SQLite + better-sqlite3)

### Connection Singleton

```typescript
// lib/db.ts
import Database from "better-sqlite3";

let db: Database.Database | null = null;

export function getDb(): Database.Database {
  if (!db) {
    db = new Database("data/skill-factory.db");
    db.pragma("journal_mode = WAL");      // Enable WAL
    db.pragma("foreign_keys = ON");       // Enable constraints
    db.pragma("busy_timeout = 5000");     // Wait 5s for lock
  }
  return db;
}
```

### Query Patterns

**Parameterized Queries (prevent SQL injection):**
```typescript
// GOOD: Parameterized
const db = getDb();
const build = db.prepare("SELECT * FROM builds WHERE id = ?").get(buildId) as Build;

// BAD: String interpolation
const build = db.prepare(`SELECT * FROM builds WHERE id = '${buildId}'`).get();
```

**Transactions:**
```typescript
const db = getDb();
const transaction = db.transaction((buildId: string) => {
  db.prepare("UPDATE builds SET status = 'running' WHERE id = ?").run(buildId);
  db.prepare("INSERT INTO build_logs (build_id, message) VALUES (?, ?)").run(
    buildId,
    "Build started"
  );
});

transaction(buildId);
```

**Type-safe Results:**
```typescript
interface Build {
  id: string;
  name: string;
  status: BuildStatus;
  // ...
}

const builds = db.prepare("SELECT * FROM builds").all() as Build[];
```

## Python Pipeline

### Code Structure

**Naming Convention:**
- Modules: `snake_case` (e.g., `p0_baseline.py`)
- Classes: `PascalCase` (e.g., `BuildConfig`)
- Functions: `snake_case` (e.g., `extract_atoms()`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `MAX_TOKENS`)

### Type Hints & Dataclasses

```python
from dataclasses import dataclass
from typing import Optional, List

@dataclass
class BuildConfig:
    """Build configuration (immutable)."""
    name: str
    domain: str
    quality_tier: str  # draft, standard, premium
    sources: dict[str, List[str]]  # {transcripts: [...], urls: [...]}
    output_dir: str
    template_id: Optional[str] = None

    def __post_init__(self):
        """Validate on creation."""
        if self.quality_tier not in ("draft", "standard", "premium"):
            raise ValueError(f"Invalid quality_tier: {self.quality_tier}")
```

### Error Handling

**Custom Exception Hierarchy:**
```python
# core/errors.py
class PipelineError(Exception):
    """Base exception."""
    pass

class PhaseError(PipelineError):
    """Phase-specific error."""
    def __init__(self, phase_id: str, message: str):
        self.phase_id = phase_id
        super().__init__(f"[{phase_id}] {message}")

class ConfigError(PipelineError):
    """Invalid configuration."""
    pass
```

**Usage:**
```python
try:
    atoms = extract_atoms(config)
except PhaseError as e:
    logger.error(f"Phase failed: {e.phase_id}")
    broadcast_event("error", {"phase": e.phase_id, "message": str(e)})
    raise
```

### Logging Pattern

**Structured JSON Output:**
```python
import json
import sys
from datetime import datetime

def log_event(event_type: str, phase: Optional[str] = None, **data):
    """Emit SSE event to stdout."""
    event = {
        "type": event_type,
        "timestamp": datetime.utcnow().isoformat(),
        "phase": phase,
        **data,
    }
    print(json.dumps(event))
    sys.stdout.flush()

# Usage
log_event("phase", phase="p0", status="running", progress=0)
log_event("log", phase="p0", level="info", message="Starting baseline extraction")
log_event("quality", phase="p0", score=85, details={"depth": 40, "diversity": 30})
```

### Claude API Calling

**With Retry Logic:**
```python
from tenacity import retry, stop_after_attempt, wait_exponential
from anthropic import Anthropic

client = Anthropic()

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def call_claude(model: str, messages: list[dict], max_tokens: int = 4096) -> str:
    """Call Claude API with automatic retries."""
    response = client.messages.create(
        model=model,  # claude-3-5-sonnet-20241022, claude-3-5-haiku-20241022
        max_tokens=max_tokens,
        messages=messages,
    )

    # Track tokens + cost
    tokens = response.usage.input_tokens + response.usage.output_tokens
    cost_usd = (response.usage.input_tokens * 0.003 +
                response.usage.output_tokens * 0.015) / 1000

    log_event("cost", phase="p2", tokens=tokens, usd=round(cost_usd, 4))

    return response.content[0].text
```

### Phase Implementation Template

```python
# phases/p0_baseline.py
from core.types import BuildConfig, PhaseResult
from core.logger import log_event

def run_phase_0(config: BuildConfig) -> PhaseResult:
    """P0: Baseline extraction via skill-seekers."""
    try:
        log_event("phase", phase="p0", status="running", progress=0)

        # 1. Discover URLs from domain
        urls = discover_urls_for_domain(config.domain)
        log_event("log", phase="p0", level="info", message=f"Found {len(urls)} URLs")

        # 2. Scrape + parse
        content = scrape_urls(urls)
        baseline_summary = summarize_content(content)
        log_event("log", phase="p0", level="info", message=f"Extracted {len(baseline_summary['topics'])} topics")

        # 3. Calculate quality
        quality_score = calculate_baseline_quality(baseline_summary)
        log_event("quality", phase="p0", score=quality_score)

        # 4. Write output
        write_json(config.output_dir / "baseline_summary.json", baseline_summary)

        log_event("phase", phase="p0", status="done", progress=100)
        return PhaseResult(phase="p0", status="done", quality_score=quality_score)

    except Exception as e:
        log_event("error", phase="p0", level="error", message=str(e))
        raise PhaseError("p0", str(e)) from e
```

### Testing

**Pytest Pattern:**
```python
# tests/test_p0_baseline.py
import pytest
from phases.p0_baseline import run_phase_0
from core.types import BuildConfig

@pytest.fixture
def sample_config():
    return BuildConfig(
        name="Test Build",
        domain="facebook-ads",
        quality_tier="draft",
        sources={"urls": ["https://example.com"]},
        output_dir="/tmp/test_output",
    )

def test_phase_0_success(sample_config):
    result = run_phase_0(sample_config)
    assert result.status == "done"
    assert result.quality_score > 0

def test_phase_0_invalid_domain(sample_config):
    sample_config.domain = "invalid-domain-xyz"
    with pytest.raises(PhaseError):
        run_phase_0(sample_config)
```

## Git Conventions

### Commit Messages

**Format:** Conventional Commits

```
feat: add build retry functionality
fix: resolve SSE connection timeout issue
docs: update README with deployment steps
refactor: simplify quality scoring logic
test: add tests for conflict resolution
chore: update dependencies
```

**Rules:**
- Present tense ("add" not "added")
- No AI references ("feat: AI improved..." → "feat: improved...")
- Lowercase first letter
- Max 50 chars for subject, 72 chars for body lines
- Reference issues: `fix: #123 SSE timeout issue`

### Branch Naming

```
feature/build-retry
bugfix/sse-timeout
docs/readme-update
refactor/quality-scoring
test/conflict-resolution
```

## Performance Guidelines

### Frontend
- Keep components < 200 LOC
- Memoize expensive computations (useMemo)
- Defer long lists with virtual scrolling (future)
- Images: lazy load, optimize formats

### Backend
- DB queries: use indexes, avoid N+1
- Subprocess: timeout 3600s (catch TIMEOUT error)
- SSE: batch events if > 10/sec
- Caching: use in-memory for settings (refresh on POST)

### Python
- Batch API calls when possible
- Stream large responses (not load into memory)
- Use generator expressions for large datasets
- Profile with `cProfile` before optimizing

## Security Guidelines

**Auth:**
- Never log passwords or API keys
- Use environment variables (never hardcode)
- Validate all API inputs
- CSRF: N/A (SPA with httpOnly cookies)

**Database:**
- Use parameterized queries (always)
- Enable foreign keys + constraints
- Regular backups of SQLite file

**API:**
- No sensitive data in logs
- Scrub error messages for external users
- Rate limiting (future)

## Documentation

**Code Comments:**
- Explain "why", not "what" (code shows what)
- Use JSDoc for public APIs
- Update comments when changing logic

**Example:**
```typescript
/**
 * Format build cost in USD with 2 decimal places.
 * @param costUsd - Cost in dollars
 * @returns Formatted string (e.g., "$5.00")
 */
function formatCost(costUsd: number): string {
  return `$${costUsd.toFixed(2)}`;
}

// GOOD: Explains why
const QUALITY_WEIGHTS = [0.15, 0.10, 0.25, 0.15, 0.20, 0.15];
// Weighted average favors P2 extraction (25%) and P4 verification (20%)
// P1 audit weighted lower (10%) as mostly preprocessing

// BAD: Obvious from code
const MAX_BUILDS = 100;  // Maximum number of builds
```

## Common Pitfalls to Avoid

| Pitfall | Problem | Solution |
|---------|---------|----------|
| Using `any` type | Loses type safety | Use generics or `unknown` + type guard |
| Unhandled promise rejections | Silent failures | Always `.catch()` or `try/catch` in async |
| Hardcoded values | Difficult to configure | Use env vars or settings DB |
| Mixing concerns | Hard to test | Single responsibility per module |
| No error boundaries | App crashes on error | Wrap components in error boundaries |
| SQL injection | Security vulnerability | Always parameterize queries |
| Unvalidated API inputs | Crashes or garbage data | Validate type, length, format |
| SSE memory leaks | Connection hanging | Always call `eventSource.close()` |

## Tools & Linting

**TypeScript:**
- ESLint (config: `eslint.config.mjs`)
- Run: `npm run lint`

**Python:**
- pytest (test runner)
- Run: `pytest pipeline/tests/`

**Before commit:**
```bash
npm run lint           # Check TS/JS
npm run build         # Verify build
pytest pipeline/      # Run Python tests
```

## Further Reading

- [Next.js Documentation](https://nextjs.org/docs)
- [React Hooks Guide](https://react.dev/reference/react)
- [Tailwind CSS Docs](https://tailwindcss.com/docs)
- [better-sqlite3 Guide](https://github.com/WiseLibs/better-sqlite3)
- [Anthropic API Reference](https://docs.anthropic.com)
