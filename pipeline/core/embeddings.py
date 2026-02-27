"""Embedding API client with TF-IDF fallback for hybrid similarity matching."""

import hashlib
import logging
import math
import re
import time
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)


@dataclass
class EmbeddingResult:
    vectors: list[list[float]]
    model: str
    tokens_used: int
    from_cache: bool
    fallback_used: bool


def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Dot product / (norm_a * norm_b), clamped [0,1], zero-vector safe."""
    if not vec_a or not vec_b:
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return max(0.0, min(1.0, dot / (norm_a * norm_b)))


class EmbeddingClient:
    def __init__(
        self,
        api_key: str = "",
        model: str = "text-embedding-3-small",
        base_url: str = "https://api.openai.com/v1",
        cache_enabled: bool = True,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._cache_enabled = cache_enabled
        self._api_available = bool(api_key)
        self._cache: dict[str, list[float]] = {}
        self._total_tokens = 0

    # ── Public API ────────────────────────────────────────────────────────────

    def embed_texts(self, texts: list[str]) -> EmbeddingResult:
        """Embed texts: cache check → API batch → TF-IDF fallback on error."""
        if not texts:
            return EmbeddingResult(
                vectors=[], model=self._model, tokens_used=0,
                from_cache=False, fallback_used=False,
            )

        keys = [self._cache_key(t) for t in texts]

        # Collect cached
        result_map: dict[str, list[float]] = {}
        uncached_indices: list[int] = []
        for i, key in enumerate(keys):
            if self._cache_enabled and key in self._cache:
                result_map[key] = self._cache[key]
            else:
                uncached_indices.append(i)

        # Cache only applies when API is available (TF-IDF vectors are corpus-dependent)
        all_from_cache = not uncached_indices and self._api_available
        fallback_used = False
        tokens_used = 0

        if uncached_indices:
            uncached_texts = [texts[i] for i in uncached_indices]
            if self._api_available:
                try:
                    vecs, tokens_used = self._api_embed(uncached_texts)
                    fallback_used = False
                    # Only cache API vectors (corpus-independent)
                    for idx, vec in zip(uncached_indices, vecs):
                        key = keys[idx]
                        result_map[key] = vec
                        if self._cache_enabled:
                            self._cache[key] = vec
                except Exception as exc:
                    logger.warning("Embedding API failed (%s), using TF-IDF fallback", exc)
                    vecs = self._tfidf_fallback(uncached_texts)
                    fallback_used = True
                    # Do NOT cache TF-IDF vectors — corpus-dependent
                    for idx, vec in zip(uncached_indices, vecs):
                        result_map[keys[idx]] = vec
            else:
                vecs = self._tfidf_fallback(uncached_texts)
                fallback_used = True
                # Do NOT cache TF-IDF vectors — corpus-dependent
                for idx, vec in zip(uncached_indices, vecs):
                    result_map[keys[idx]] = vec

        self._total_tokens += tokens_used
        vectors = [result_map[k] for k in keys]
        return EmbeddingResult(
            vectors=vectors,
            model=self._model if not fallback_used else "tfidf-fallback",
            tokens_used=tokens_used,
            from_cache=all_from_cache,
            fallback_used=fallback_used,
        )

    def similarity(self, text_a: str, text_b: str) -> float:
        """Embed both texts, return cosine similarity."""
        result = self.embed_texts([text_a, text_b])
        if len(result.vectors) < 2:
            return 0.0
        return _cosine_similarity(result.vectors[0], result.vectors[1])

    def similarity_matrix(
        self, queries: list[str], corpus: list[str]
    ) -> list[list[float]]:
        """Embed all texts once, return pairwise cosine matrix[query][corpus]."""
        if not queries or not corpus:
            return []
        all_texts = queries + corpus
        result = self.embed_texts(all_texts)
        q_vecs = result.vectors[: len(queries)]
        c_vecs = result.vectors[len(queries):]
        return [
            [_cosine_similarity(qv, cv) for cv in c_vecs]
            for qv in q_vecs
        ]

    def get_stats(self) -> dict:
        return {
            "tokens_used": self._total_tokens,
            "cache_size": len(self._cache),
            "api_available": self._api_available,
        }

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _cache_key(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

    def _api_embed(self, texts: list[str]) -> tuple[list[list[float]], int]:
        """Call OpenAI-compatible embedding endpoint. Batches up to 100 texts."""
        all_vectors: list[list[float]] = []
        total_tokens = 0
        batch_size = 100

        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            vecs, tokens = self._call_api_with_retry(batch)
            all_vectors.extend(vecs)
            total_tokens += tokens

        return all_vectors, total_tokens

    def _call_api_with_retry(
        self, texts: list[str], retries: int = 2
    ) -> tuple[list[list[float]], int]:
        """POST /embeddings with exponential backoff on failure."""
        url = f"{self._base_url}/embeddings"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        body = {"model": self._model, "input": texts}

        last_exc: Exception = RuntimeError("No attempts made")
        for attempt in range(retries + 1):
            if attempt > 0:
                time.sleep(2 ** attempt)
            try:
                with httpx.Client(timeout=60.0) as client:
                    resp = client.post(url, headers=headers, json=body)
                    resp.raise_for_status()
                    data = resp.json()
                    vectors = [item["embedding"] for item in data["data"]]
                    tokens = data.get("usage", {}).get("total_tokens", 0)
                    return vectors, tokens
            except Exception as exc:
                last_exc = exc
                logger.debug("Embedding API attempt %d failed: %s", attempt + 1, exc)

        raise last_exc

    def _tfidf_fallback(self, texts: list[str]) -> list[list[float]]:
        """Compute TF-IDF vectors aligned to shared vocabulary."""
        if not texts:
            return []

        tokenized = [re.findall(r"\w+", t.lower()) for t in texts]

        # Build vocabulary
        vocab: dict[str, int] = {}
        for tokens in tokenized:
            for tok in tokens:
                if tok not in vocab:
                    vocab[tok] = len(vocab)

        if not vocab:
            return [[0.0] for _ in texts]

        n_docs = len(tokenized)
        vocab_size = len(vocab)

        # Document frequency per term
        df: dict[str, int] = {}
        for tokens in tokenized:
            for tok in set(tokens):
                df[tok] = df.get(tok, 0) + 1

        # Check whether any term has df < n_docs (non-trivial IDF)
        has_idf = any(df[tok] < n_docs for tok in vocab)

        vectors: list[list[float]] = []
        for tokens in tokenized:
            vec = [0.0] * vocab_size
            if not tokens:
                vectors.append(vec)
                continue
            tf: dict[str, float] = {}
            for tok in tokens:
                tf[tok] = tf.get(tok, 0) + 1
            for tok, count in tf.items():
                if has_idf:
                    idf = math.log(n_docs / df[tok]) if df[tok] < n_docs else 0.0
                    vec[vocab[tok]] = (count / len(tokens)) * idf
                else:
                    # All terms appear in every document (IDF = 0) — use raw TF
                    vec[vocab[tok]] = count / len(tokens)
            vectors.append(vec)

        return vectors

    def _keyword_similarity(self, text_a: str, text_b: str) -> float:
        """Jaccard similarity on keyword sets."""
        set_a = set(re.findall(r"\w+", text_a.lower()))
        set_b = set(re.findall(r"\w+", text_b.lower()))
        if not set_a and not set_b:
            return 1.0
        union = set_a | set_b
        if not union:
            return 0.0
        return len(set_a & set_b) / len(union)
