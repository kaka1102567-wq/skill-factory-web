# Tasks: Multi-Provider LLM + Opus Premium Tier

## 1. Python — BuildConfig (types.py)

- [x] 1.1 Add 3 fields to `BuildConfig`: `claude_base_url_light`, `claude_api_key_light`, `claude_model_premium` (all default empty string)

## 2. Python — ClaudeClient (claude_client.py)

- [x] 2.1 Add `base_url_light`, `api_key_light`, `model_premium` params to `__init__()`
- [x] 2.2 Create separate `light_client` + `light_sdk_type` when `base_url_light` provided; fall back to `main_client` when empty
- [x] 2.3 Store `self.model_premium` for premium model swap
- [x] 2.4 Add `use_premium_model` param to `call()` with priority: premium > main > light
- [x] 2.5 Add `use_premium_model` param to `call_json()` and pass through to `call()`
- [x] 2.6 Fix `_cache_key()` to include model name: `sha256(model + system + user)`
- [x] 2.7 Split credit exhaustion into 2 counters: `_credit_errors_main` (main+premium) and `_credit_errors_light`
- [x] 2.8 Route `_call_api()` to correct client+sdk_type based on model selection
- [x] 2.9 Add DeepSeek and Opus pricing to `PRICING` dict
- [x] 2.10 Log model name in debug output for cost transparency

## 3. Python — Config (config.py)

- [x] 3.1 Read `CLAUDE_BASE_URL_LIGHT`, `CLAUDE_API_KEY_LIGHT`, `CLAUDE_MODEL_PREMIUM` env vars into BuildConfig

## 4. Python — Runner (runner.py)

- [x] 4.1 Pass `base_url_light`, `api_key_light`, `model_premium` from config to ClaudeClient constructor

## 5. Python — P5 Build (p5_build.py)

- [x] 5.1 Add `use_premium = config.quality_tier == "premium"` flag
- [x] 5.2 Pass `use_premium_model=use_premium` to SKILL.md generation `claude.call()` calls
- [x] 5.3 Pass `use_premium_model=use_premium` to knowledge writer `claude.call()` calls

## 6. Python — P6 Optimize (p6_optimize.py)

- [x] 6.1 Add `use_premium = config.quality_tier == "premium"` flag
- [x] 6.2 Pass `use_premium_model=use_premium` to optimization `claude.call()` calls

## 7. TypeScript — DB Schema (lib/db-schema.ts)

- [x] 7.1 Add 3 `INSERT OR IGNORE` entries for new settings: `claude_base_url_light`, `claude_api_key_light`, `claude_model_premium`

## 8. TypeScript — Build Runner (lib/build-runner.ts)

- [x] 8.1 Extend `ApiCredentials` interface with `baseUrlLight`, `apiKeyLight`, `modelPremium`
- [x] 8.2 Read 3 new settings in `_resolveApiCredentials()`
- [x] 8.3 Pass as env vars in `_spawnPipeline()`: `CLAUDE_BASE_URL_LIGHT`, `CLAUDE_API_KEY_LIGHT`, `CLAUDE_MODEL_PREMIUM`
- [x] 8.4 Pass same env vars in `resumeAfterResolve()`

## 9. TypeScript — Settings UI (app/settings/page.tsx)

- [x] 9.1 Add "Light Model" section with base_url_light and api_key_light fields (below existing model_light)
- [x] 9.2 Add "Premium Model" section with model_premium field + helper text

## 10. Tests

- [x] 10.1 Update `MockClaudeClient` in conftest.py: accept new params, support `use_premium_model`
- [x] 10.2 Test: light separate provider creates separate client
- [x] 10.3 Test: premium model swap uses main client
- [x] 10.4 Test: backward compatible — empty fields = old behavior
- [x] 10.5 Test: cache key includes model name (different models → different keys)
- [x] 10.6 Run full test suite: `py -m pytest pipeline/tests/ -x`
- [x] 10.7 Run TypeScript build: `npm run build`
