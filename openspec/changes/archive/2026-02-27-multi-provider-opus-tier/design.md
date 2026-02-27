# Design: Multi-Provider LLM + Opus Premium Tier

## Context

Current `ClaudeClient` creates ONE SDK client (`self.client`) — either Anthropic or OpenAI-compatible based on `base_url`. Light model (`use_light_model=True`) simply swaps model name on the same client. This prevents using cheaper providers (DeepSeek $0.14/M vs Sonnet $3/M) for simple phases.

Current cache key is `sha256(system + user)` — missing model name, causing cross-model cache collisions.

## Goals / Non-Goals

**Goals:**
- Enable separate provider for light model (2 SDK clients max)
- Enable premium model swap on main client for P5/P6
- Fix cache key to include model name
- Separate credit exhaustion counters per provider
- Backward compatible: all new fields empty = old behavior

**Non-Goals:**
- 3+ SDK clients (premium gets its own client)
- Changing phase function signatures (`run_p0`...`run_p6`)
- Changing JSON SSE event format
- Modifying `mock_cli.py`

## Decisions

### Decision 1: 2 clients architecture (main + light)

```
┌─────────────────────────────────────────────┐
│  ClaudeClient                               │
│                                             │
│  main_client ──→ Anthropic or OpenAI SDK    │
│    ├─ model (Sonnet) — standard calls       │
│    └─ model_premium (Opus) — premium calls  │
│                                             │
│  light_client ──→ OpenAI SDK (or = main)    │
│    └─ model_light (DeepSeek/Haiku)          │
└─────────────────────────────────────────────┘
```

Premium reuses `main_client` — only swaps model name. No 3rd client.
When `base_url_light` is empty, `light_client = main_client` (backward compatible).

### Decision 2: Model selection priority in call()

```
use_premium_model=True + model_premium set → premium model on main_client
use_light_model=True + model_light set    → light model on light_client
else                                      → main model on main_client
```

Premium > main > light. If both flags True, premium wins.

### Decision 3: Cache key = sha256(model + system + user)

Adding model to cache key input prevents collisions when same prompt goes to different models.

### Decision 4: Credit exhaustion — 2 counters

- `_credit_errors_main`: Shared by main + premium (same provider)
- `_credit_errors_light`: Only for light model (may be different provider)

Reset on successful call to respective provider.

### Decision 5: TypeScript — extend _resolveApiCredentials

Add 3 new fields to `ApiCredentials` interface:
- `baseUrlLight`, `apiKeyLight`, `modelPremium`

Read from DB settings → env vars (same pattern as existing fields).
Pass as env vars to Python subprocess.

### Decision 6: Settings UI — 3 sections

- **Main Model**: existing fields (model, base_url, api_key)
- **Light Model**: existing model_light + NEW base_url_light, api_key_light
- **Premium Model**: NEW model_premium only + helper text "Uses Main Model API Key & Base URL"

### Decision 7: PRICING dict extensibility

Add DeepSeek and Opus to `ClaudeClient.PRICING` dict for accurate cost tracking. Unknown models fall back to Sonnet pricing.
