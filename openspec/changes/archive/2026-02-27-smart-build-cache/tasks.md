## 1. Core Cache Module

- [x] 1.1 Create `pipeline/core/build_cache.py` — BuildCache class with atoms/inventory/embeddings cache, JSON storage, atomic writes, TTL expiry, graceful degradation, CacheStats, file_content_hash, clear/get_stats management
- [x] 1.2 Add `PROMPT_VERSION` constants to `pipeline/prompts/p1_audit_prompts.py` and `pipeline/prompts/p2_extract_prompts.py`

## 2. Phase Integration

- [x] 2.1 Integrate cache into `pipeline/phases/p2_extract.py` — add per-file cache check/save around Stream A transcript extraction loop. Group chunks by source file, check cache before processing, save atoms after extraction. Only cache Stream A (not gap-fill B or code C)
- [x] 2.2 Integrate cache into `pipeline/phases/p1_audit.py` — add inventory cache check at start (domain + sorted file hashes + model + tier), save inventory after successful audit

## 3. CLI Commands

- [x] 3.1 Add `cache-stats` and `cache-clear` subcommands to `pipeline/cli.py` — JSON output, --all and --older-than flags

## 4. Tests

- [x] 4.1 Create `pipeline/tests/test_build_cache.py` — atoms cache (save/get, miss, model/prompt/tier differentiation, TTL expiry), inventory cache (save/get, fileset change miss, hash order irrelevance), file content hash, graceful degradation (corrupt JSON, auto-create dirs), cache management (stats, clear all, clear by age)
- [x] 4.2 Run full test suite and verify all tests pass including new cache tests
