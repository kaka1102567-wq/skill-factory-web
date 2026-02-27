# Tester Agent Memory

## Project: skill-factory-web

### Test Infrastructure
- **Test Framework:** pytest with fixtures in `pipeline/tests/conftest.py`
- **Key Fixtures:** `mock_claude`, `build_config`, `logger`, `seekers_cache`, `seekers_lookup`
- **Mock Client:** `MockClaudeClient` supports LLM response simulation for all pipeline phases (P0-P6)
- **Test Pattern:** Phase functions called directly with mock client, output files validated via JSON reads

### ClaudeClient Multi-Provider Support (Feb 2025)
- **New Params:** `base_url_light`, `api_key_light`, `model_premium`
- **Client Routing:** Light provider gets separate OpenAI client when `base_url_light` provided; otherwise uses main_client
- **Premium Model:** Stored as string field, uses main_client (no separate client instance)
- **Cache Key:** Now includes model name via `sha256(model + system + user)` to avoid cross-model collisions
- **Credit Tracking:** Separate counters `_credit_errors_main` and `_credit_errors_light`
- **Test Coverage:** 4 unit tests verify light separation, premium swap, backward compatibility, cache key inclusion

### Test Results Summary
- **Full Suite:** 363 tests, 0 failures, 53.99s execution
- **TypeScript Build:** Clean compile, no errors
- **Backward Compatibility:** All existing tests continue to pass

### Files Modified
1. `pipeline/tests/conftest.py` — MockClaudeClient enhanced with multi-provider params
2. `pipeline/tests/test_phases.py` — Added TestClaudeClientMultiProvider with 4 new unit tests
3. `openspec/changes/multi-provider-opus-tier/tasks.md` — Tasks 10.1-10.7 marked complete
