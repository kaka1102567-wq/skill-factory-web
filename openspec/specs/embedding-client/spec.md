# embedding-client Specification

## Purpose
Provides a unified embedding client that abstracts OpenAI-compatible embedding APIs with built-in caching, fallback chains (TF-IDF → keyword similarity), and similarity computation utilities. Enables hybrid embedding-based document deduplication and multilingual verification across the pipeline.

## Requirements

### Requirement: OpenAI-compatible embedding API client
The EmbeddingClient SHALL call any OpenAI-compatible embedding endpoint via `httpx` raw HTTP (NOT openai SDK). It SHALL accept `api_key`, `model`, `base_url` as constructor params. Default: `text-embedding-3-small` at `https://api.openai.com/v1`.

#### Scenario: Embed texts via API
- **WHEN** `embed_texts(["text1", "text2"])` is called with valid API key
- **THEN** system POSTs to `{base_url}/embeddings` with `{"model": model, "input": texts}`
- **AND** returns `EmbeddingResult` with vectors in same order as input, `tokens_used` from response

#### Scenario: Batch limit
- **WHEN** more than 100 texts are passed
- **THEN** system batches into chunks of 100 and concatenates results

### Requirement: In-memory cache per build
The EmbeddingClient SHALL cache embeddings keyed by `sha256(text)[:16]`. Cache is in-memory only (not persistent). Same text across P3/P4/P5 phases SHALL return cached vector without API call.

#### Scenario: Cache hit
- **WHEN** `embed_texts(["already cached text"])` is called
- **THEN** system returns cached vector without API call
- **AND** `EmbeddingResult.from_cache` is True

#### Scenario: Mixed cache/uncached
- **WHEN** some texts are cached and some are not
- **THEN** system calls API only for uncached texts and merges results

### Requirement: Fallback chain API to TF-IDF to keyword
When API is unavailable (no key or API error), the client SHALL fall back to TF-IDF vectorization. If TF-IDF fails, SHALL fall back to keyword (Jaccard) similarity. Pipeline SHALL NOT crash regardless of embedding availability.

#### Scenario: No API key
- **WHEN** `EmbeddingClient(api_key="")` is created
- **THEN** `_api_available` is False
- **AND** `embed_texts()` uses TF-IDF fallback
- **AND** `EmbeddingResult.fallback_used` is `"tfidf"`

#### Scenario: API error triggers fallback
- **WHEN** API returns non-200 status or network error
- **THEN** system retries twice with exponential backoff
- **AND** if still failing, falls back to TF-IDF

#### Scenario: Keyword similarity last resort
- **WHEN** `_keyword_similarity(text_a, text_b)` is called
- **THEN** system computes Jaccard similarity on tokenized keywords

### Requirement: Similarity matrix computation
The client SHALL provide `similarity_matrix(queries, corpus)` that embeds all texts once and computes pairwise cosine similarity.

#### Scenario: Matrix dimensions
- **WHEN** `similarity_matrix(["a","b"], ["c","d","e"])` is called
- **THEN** result is 2x3 matrix where `result[i][j]` = cosine similarity of query i vs corpus j

### Requirement: Cosine similarity clamped 0 to 1
`_cosine_similarity()` SHALL return values clamped to [0.0, 1.0]. Zero vectors SHALL return 0.0 without division error.

#### Scenario: Identical vectors
- **WHEN** two identical vectors are compared
- **THEN** score is 1.0

#### Scenario: Zero vector
- **WHEN** one vector is all zeros
- **THEN** score is 0.0 (no ZeroDivisionError)

#### Scenario: Opposite vectors
- **WHEN** vectors point in opposite directions
- **THEN** score is clamped to 0.0

### Requirement: Independent embedding config
Embedding config (api_key, model, base_url) SHALL be independent from main LLM provider config. DeepSeek light model has no embedding API; Voyage needs separate key. Three separate fields in BuildConfig, db-schema, and settings UI.

#### Scenario: Different providers
- **WHEN** main LLM uses DeepSeek and embedding uses OpenAI
- **THEN** both work independently with their own API keys
