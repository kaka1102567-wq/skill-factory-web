## Why

Pipeline xử lý LẠI toàn bộ files mỗi lần build, kể cả khi input không đổi. Build 5 PDFs = $0.50; thêm 1 PDF mới → build lại 6 PDFs = $0.60, dù 5 PDFs cũ giữ nguyên. Cross-build cache cho phép skip files đã xử lý, tiết kiệm 60-80% chi phí API trên incremental builds.

## What Changes

- Thêm `BuildCache` module — persistent JSON cache cho atoms (P2) và inventory (P1)
- P2 extract: per-file cache lookup trước khi gọi Claude — cache hit = skip extraction
- P1 audit: inventory cache per domain+fileset — exact same inputs = skip audit
- Embedding cache cho P3 dedup phase
- Composite cache key: `file_content_hash + model + prompt_version + tier` — đảm bảo invalidation khi bất kỳ factor nào thay đổi
- Prompt version constants trong prompt files — bump version = auto-invalidate cache
- CLI commands: `cache-stats`, `cache-clear` (--all, --older-than N)
- Thread-safe atomic writes, 30-day TTL, graceful degradation (corrupt/missing cache = chạy bình thường)

## Capabilities

### New Capabilities
- `build-cache`: Cross-build persistent cache — atoms per file (P2), inventory per domain+fileset (P1), embeddings per text. JSON storage, TTL expiry, atomic writes, CLI management commands.

### Modified Capabilities
- `cache-key-safety`: Thêm prompt_version vào composite key components — cache key phải invalidate khi prompt template thay đổi.

## Impact

- **Python files**: 5 files (1 new module, 2 phase modifications, 1 CLI update, 1 test file)
- **Pipeline phases**: P1 audit, P2 extract — thêm cache check/save wrapper, giữ nguyên function signatures
- **Storage**: Thêm `data/cache/build_cache/` directory (atoms/, inventory/, embeddings/)
- **CLI**: 2 subcommands mới (cache-stats, cache-clear)
- **Dependencies**: Không thêm external dependency — chỉ dùng stdlib (hashlib, json, pathlib)
- **TypeScript/UI**: Không ảnh hưởng
