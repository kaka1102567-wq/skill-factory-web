## Context

Pipeline hiện có response-level cache trong `claude_client.py` (key = model+system+user hash) — cache từng lần gọi Claude API. Tuy nhiên, không có cross-build cache ở mức phase output: P1 inventory và P2 atoms phải tính lại toàn bộ mỗi lần build, kể cả khi input files không đổi.

P2 loop (`p2_extract.py:76-130`) iterate qua `all_chunks` từ tất cả transcripts — không có file-level granularity để skip files đã xử lý. P1 audit tất cả transcripts cùng lúc, output 1 inventory cho toàn domain.

BuildConfig có đủ fields cần thiết: `domain`, `quality_tier`, `claude_model`, `transcript_paths`, `output_dir`. Prompt files chưa có version constants.

## Goals / Non-Goals

**Goals:**
- Skip P2 extraction cho files đã xử lý (same content + model + prompt + tier)
- Skip P1 audit khi exact same file set + domain + model + tier
- Cache embeddings để tránh re-compute P3 vectors
- CLI commands để inspect và clear cache
- Graceful degradation — cache failure không break pipeline

**Non-Goals:**
- Partial inventory cache (thêm 1 file = full P1 re-audit) — quá phức tạp cho lợi ích nhỏ
- Cache P3 dedup results (phụ thuộc vào atom set thay đổi liên tục)
- Cache Stream B gap-fill hoặc Stream C code atoms (phụ thuộc inventory từ P1)
- Distributed cache / Redis — chỉ local JSON files
- Cache invalidation UI trong TypeScript frontend

## Decisions

### D1: Cache granularity — Per-file atoms (P2) + per-domain-fileset inventory (P1)

**Rationale:** P2 chunk loop không có file boundary — cần restructure để track atoms per source file. P1 inventory phụ thuộc vào toàn bộ file set nên cache key phải include sorted file hashes.

**Alternative considered:** Per-chunk cache — rejected vì chunk boundaries có thể thay đổi khi chunking algorithm thay đổi, gây cache miss không cần thiết.

### D2: Cache key = `hash(content + model + prompt_version + tier)`

**Rationale:** Bất kỳ factor nào thay đổi đều cần re-process. Content hash (không filename) = rename-safe. Prompt version constant mới trong prompt files — bump version = auto-invalidate.

**Alternative considered:** Include timestamp — rejected vì mục đích là cache across builds, timestamp sẽ luôn miss.

### D3: JSON file storage trong `data/cache/build_cache/`

**Rationale:** Tách biệt với existing Claude response cache (`data/cache/claude/`). JSON human-readable cho debugging. Atomic write via .tmp → rename.

**Alternative considered:** SQLite — rejected vì overhead không cần thiết cho <1000 entries, JSON đủ performant.

### D4: Không sửa function signatures — cache logic bên trong phase functions

**Rationale:** `run_pN(config, claude, cache, lookup, logger)` signature đã stable. BuildCache tạo inline từ config paths, không cần thêm parameter.

### D5: Helper `_get_build_cache(config)` trong mỗi phase file

**Rationale:** Module-level helper, return `BuildCache | None`. Cache dir derive từ `config.seekers_cache_dir` (đã có pattern `data/cache/`) + `/build_cache/`. Graceful — return None nếu tạo thất bại.

### D6: P2 cần group chunks by source file để cache per-file

**Rationale:** Current loop flat-iterates `all_chunks`. Cần wrap thêm outer loop per transcript file: check cache → nếu miss, extract all chunks of that file → save atoms per file. Giữ inner chunk loop unchanged.

## Risks / Trade-offs

- **[Stale cache]** Prompt thay đổi nhưng quên bump version → stale atoms. → Mitigation: Document version bump rule. Cache TTL 30 ngày là safety net.
- **[Disk growth]** Nhiều builds tích lũy cache files. → Mitigation: TTL auto-expire + `cache-clear --older-than N` CLI.
- **[P1 cache miss rate cao]** Thêm/bớt 1 file = full P1 re-audit. → Accepted trade-off: P1 cost thấp hơn P2 nhiều, và partial inventory cache quá phức tạp.
- **[Atomic write on Windows]** `Path.replace()` trên Windows có thể fail nếu target locked. → Mitigation: try/except, graceful degradation.
- **[P2 restructure risk]** Grouping chunks by file thay đổi loop structure. → Mitigation: Keep inner chunk processing identical, chỉ wrap outer file loop.
