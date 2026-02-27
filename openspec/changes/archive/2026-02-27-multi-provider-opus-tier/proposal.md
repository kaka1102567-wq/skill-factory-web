# Proposal: Multi-Provider LLM + Opus Premium Tier

## Why

Pipeline currently uses a single LLM provider (Anthropic) for all phases. Light model (Haiku) shares the same API key/endpoint. This creates two problems:

1. **Cost**: Sonnet at $3/M input for simple tasks (P1 audit, P3 dedup) when DeepSeek at $0.14/M would suffice
2. **Quality ceiling**: No way to use Opus for premium-tier builds where quality matters most (P5/P6)

## What Changes

- Light model MUST support a separate provider (base_url + api_key), enabling DeepSeek/Gemini for cheap phases
- Premium model MUST reuse the main client with a different model name (Opus), no separate client
- 2 SDK clients max (main + light), premium swaps model on main client
- All new fields backward compatible — empty = old behavior

## Capabilities

### New Capabilities
- `multi-provider-light-model`: Light model (P1/P3/P4) can use a separate API provider with its own base_url and api_key
- `premium-model-tier`: Premium quality tier routes P5/P6 calls through a higher-capability model (e.g., Opus)

### Modified Capabilities
- `claude-client-initialization`: ClaudeClient creates up to 2 SDK clients (main + optional separate light)
- `api-credentials-resolver`: build-runner.ts resolves 3 additional settings for light provider and premium model
- `settings-ui`: Settings page shows 3 model tier sections (Main, Light, Premium)

## Impact

**Python pipeline (5 files):**
- `pipeline/core/types.py`: +3 BuildConfig fields
- `pipeline/clients/claude_client.py`: Separate light client, premium model swap, cache key fix, dual credit counters
- `pipeline/core/config.py`: +3 env var reads
- `pipeline/orchestrator/runner.py`: Pass new params to ClaudeClient
- `pipeline/phases/p5_build.py`: use_premium_model for premium tier
- `pipeline/phases/p6_optimize.py`: use_premium_model for premium tier

**TypeScript web app (3 files):**
- `lib/db-schema.ts`: +3 settings seed entries
- `lib/build-runner.ts`: Resolve + pass 3 new env vars
- `app/settings/page.tsx`: UI for 3 model tier sections

**Cost impact:** Standard tier $1.09 → $0.50-0.65 (~50% savings)
