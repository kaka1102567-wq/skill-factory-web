## 1. Core Embedding Module

- [x] 1.1 Create `pipeline/core/embeddings.py` — EmbeddingClient class with `__init__`, `embed_texts`, `similarity`, `similarity_matrix`, `get_stats` methods
- [x] 1.2 Implement OpenAI-compatible API call via httpx (POST /embeddings, batch max 100, 2 retries with backoff)
- [x] 1.3 Implement in-memory cache (sha256 key, check/store per text)
- [x] 1.4 Implement `_tfidf_fallback` (tokenize → vocabulary → TF-IDF vectors)
- [x] 1.5 Implement `_keyword_similarity` (Jaccard similarity on tokenized keywords)
- [x] 1.6 Implement `_cosine_similarity` module-level function (clamped 0-1, zero-vector safe)

## 2. Config & Integration

- [x] 2.1 Add 3 embedding fields to `BuildConfig` in `pipeline/core/types.py` (embedding_api_key, embedding_model, embedding_base_url)
- [x] 2.2 Read 3 embedding env vars in `pipeline/core/config.py`
- [x] 2.3 Create EmbeddingClient in `pipeline/orchestrator/runner.py` and attach to config as `config.embedding_client`

## 3. P3 Hybrid Dedup

- [x] 3.1 Read and understand current P3 dedup flow (cross-source, per-category, batch logic)
- [x] 3.2 Add embedding pre-filter to cross-source dedup: compute similarity matrix, classify pairs into auto-merge/uncertain/unique
- [x] 3.3 Implement auto-merge for ≥0.85 pairs (keep higher confidence atom)
- [x] 3.4 Send only 0.60-0.85 uncertain pairs to existing LLM dedup logic
- [x] 3.5 Add fallback path: no embedding → existing LLM-only dedup unchanged
- [x] 3.6 Log embedding filter stats via PipelineLogger

## 4. P4 Multilingual Verify

- [x] 4.1 Read and understand current P4 verify flow (keyword matching, sampling)
- [x] 4.2 Add embedding-based verification: compute similarity against baseline refs, classify verified/partial/expert_insight
- [x] 4.3 Write score into verification_note format `"Verified (score X.XX) against ref.md"`
- [x] 4.4 Add fallback path: no embedding → existing keyword matching unchanged

## 5. P5 Confidence Map + Enrichment

- [x] 5.1 Upgrade `_generate_confidence_map()` from 2-level to 4-level (HIGH/MEDIUM/LOW based on parsed scores)
- [x] 5.2 Add `_extract_verification_score()` helper to parse score from verification_note
- [x] 5.3 Implement `_enrich_atoms_multi_source()` — conditional enrichment when ≥3 source files, cluster by embedding similarity >0.80

## 6. TypeScript Web App

- [x] 6.1 Add 3 embedding settings to `lib/db-schema.ts` default settings
- [x] 6.2 Pass 3 embedding env vars in `lib/build-runner.ts`
- [x] 6.3 Add Embedding Model section to `app/settings/page.tsx` UI

## 7. Tests

- [x] 7.1 Create `pipeline/tests/test_embeddings.py` — unit tests for EmbeddingClient (cosine, cache, fallback, matrix)
- [x] 7.2 Add P5 Confidence Map tests (4-level with scores, backward compatible without scores)
- [x] 7.3 Update `pipeline/tests/test_phases.py` — P3 hybrid dedup tests (with/without embedding), P4 multilingual verify tests
- [x] 7.4 Run `python -m pytest tests/ -x -v` and fix failures
- [x] 7.5 Run `npm run build` and fix TypeScript errors
