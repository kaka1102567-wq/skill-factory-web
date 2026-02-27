## Context

Pipeline hiện tại: P3 dedup gửi mọi atom pairs cho LLM → O(n²) API calls. P4 verify dùng keyword matching → miss cross-language. P5 Confidence Map chỉ 2-level (có/không baseline reference).

Sprint 1 đã thêm multi-provider LLM (light/premium). Sprint 3 thêm embedding layer độc lập — pre-filter trước LLM, không thay thế LLM.

Constraints:
- Function signatures `run_pN(config, claude, cache, lookup, logger)` KHÔNG được sửa
- KHÔNG thêm `openai` SDK — dùng `httpx` raw HTTP
- Embedding config independent: 3 fields riêng (model, api_key, base_url)
- Backward compatible: no API key → behavior y hệt trước

## Goals / Non-Goals

**Goals:**
- Giảm 70-80% LLM calls ở P3 bằng embedding pre-filter
- Multilingual verification ở P4 (Vietnamese ↔ English)
- Confidence Map 4-level dựa trên embedding scores thực
- Fallback chain: API → TF-IDF → keyword (never crash)

**Non-Goals:**
- Persistent embedding cache (Sprint 4)
- Thay thế LLM cho contradiction/outdated detection
- Vector database hoặc external storage
- Batch processing optimization (giữ nguyên logic hiện tại)

## Decisions

### D1: Truyền EmbeddingClient qua config attribute

**Choice**: Attach `embedding_client` attribute lên BuildConfig instance sau khi tạo, không sửa `__init__` signature.

**Rationale**: Runner tạo EmbeddingClient → gán `config.embedding_client = client` → phases truy cập `config.embedding_client`. Giữ nguyên function signatures. Đơn giản nhất, không hack.

**Alternative rejected**: Module-level factory/global — tạo coupling, khó test.

### D2: OpenAI-compatible API via httpx

**Choice**: Raw HTTP calls với `httpx` (đã có trong requirements).

**Rationale**: Embedding API chỉ cần 1 endpoint (`POST /embeddings`). Thêm SDK cho 1 endpoint = overkill.

### D3: TF-IDF fallback khi no API key

**Choice**: In-memory TF-IDF (tokenize → vocabulary → TF-IDF vectors) → cosine similarity.

**Rationale**: Tốt hơn keyword matching, không cần API, đủ cho basic similarity. Keyword matching là last-resort khi TF-IDF fail.

### D4: Thresholds cố định (không configurable)

**Choice**: P3: ≥0.85 auto-merge, 0.60-0.85 LLM, <0.60 skip. P4: ≥0.70 verified, 0.50-0.70 partial, <0.50 expert.

**Rationale**: Thresholds từ empirical testing. Configurable = complexity không cần thiết ở giai đoạn này. Có thể thêm sau nếu cần.

### D5: In-memory cache per build, shared across phases

**Choice**: EmbeddingClient giữ `_cache: dict[str, list[float]]` — tính ở P3, reuse ở P4/P5 vì cùng instance.

**Rationale**: Atoms text không đổi giữa phases. Cache tránh duplicate API calls. Persistent cache = Sprint 4.

## Risks / Trade-offs

- **[Risk] Auto-merge false positives**: Cosine ≥0.85 nhưng không phải duplicate (e.g., "CPC $0.50" vs "CPC $1.20" = outdated) → **Mitigation**: Chỉ auto-merge DUPLICATE, CONTRADICTION/OUTDATED vẫn qua LLM. Threshold 0.85 là conservative.
- **[Risk] Embedding API downtime**: OpenAI API unavailable → **Mitigation**: Fallback chain TF-IDF → keyword. Pipeline không crash.
- **[Risk] TF-IDF quality thấp**: Fallback TF-IDF kém hơn real embeddings → **Mitigation**: Acceptable degradation — vẫn tốt hơn keyword-only. Log warning rõ ràng.
- **[Trade-off] Memory usage**: Cache tất cả embeddings in-memory per build → OK cho ~100-200 atoms, mỗi vector ~6KB. Total ~1MB max.
