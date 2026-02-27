## Why

P3 dedup gửi mọi cặp atoms cho LLM so sánh — 106 atoms = hàng nghìn comparisons, tốn $0.43/build (Sonnet) hoặc $0.02 (DeepSeek). Embedding pre-filter giảm 70-80% LLM calls bằng cách loại nhanh cặp rõ ràng unique hoặc rõ ràng duplicate.

P4 verify dùng keyword matching — miss cross-language hoàn toàn. "Cách tối ưu chi phí quảng cáo" vs "How to reduce Facebook Ads spend" → 0 keyword match nhưng multilingual embedding → score ~0.85.

## What Changes

- Tạo module `pipeline/core/embeddings.py` — embedding API client (OpenAI-compatible) với fallback chain: API → TF-IDF → keyword matching
- P3 dedup: thêm embedding pre-filter trước LLM (≥0.85 auto-merge, <0.60 skip, 0.60-0.85 gửi LLM)
- P4 verify: thay keyword matching bằng embedding similarity (multilingual, giữ keyword fallback)
- P5 build: upgrade Confidence Map 2-level → 4-level (HIGH/MEDIUM/LOW/UNKNOWN) + conditional enrichment khi ≥3 sources
- TypeScript: thêm 3 embedding settings (model, api_key, base_url) vào DB schema, build-runner, settings UI
- Config/runner: đọc embedding env vars, tạo EmbeddingClient, truyền vào phases

## Capabilities

### New Capabilities
- `embedding-client`: Embedding API client module với OpenAI-compatible endpoint, in-memory cache, TF-IDF + keyword fallback chain
- `hybrid-dedup-filter`: Embedding pre-filter cho P3 dedup — phân loại nhanh duplicate/uncertain/unique trước khi gửi LLM
- `multilingual-verify`: Embedding-based verification cho P4 — thay keyword matching, hỗ trợ cross-language (Vietnamese ↔ English)

### Modified Capabilities
- `knowledge-atom-repr`: P5 Confidence Map upgrade 2-level → 4-level (HIGH/MEDIUM/LOW/UNKNOWN) dựa trên embedding scores từ P4

## Impact

- **Python pipeline**: Tạo 1 file mới (`embeddings.py`), sửa 6 files (types, config, runner, p3, p4, p5)
- **TypeScript web app**: Sửa 3 files (db-schema, build-runner, settings page)
- **Dependencies**: Dùng `httpx` (đã có) cho embedding API — KHÔNG thêm openai SDK
- **Backward compatible**: embedding_api_key trống → behavior y hệt trước Sprint 3
- **Function signatures**: giữ nguyên `run_pN(config, claude, cache, lookup, logger)` — truyền embedding_client qua config attribute
