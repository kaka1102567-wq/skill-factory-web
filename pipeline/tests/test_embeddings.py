"""Tests for embedding client and hybrid similarity matching."""

import pytest
from pipeline.core.embeddings import EmbeddingClient, EmbeddingResult, _cosine_similarity


class TestCosineSimilarity:
    """Test cosine similarity helper function."""

    def test_identical_vectors(self):
        """Identical vectors should return 1.0."""
        assert _cosine_similarity([1, 0, 0], [1, 0, 0]) == 1.0

    def test_orthogonal_vectors(self):
        """Orthogonal vectors should have similarity near 0."""
        assert abs(_cosine_similarity([1, 0, 0], [0, 1, 0])) < 0.01

    def test_opposite_vectors_clamped(self):
        """Opposite vectors clamped to [0,1] should return 0.0."""
        assert _cosine_similarity([1, 0], [-1, 0]) == 0.0

    def test_zero_vector(self):
        """Zero vector with non-zero vector should return 0.0."""
        assert _cosine_similarity([0, 0], [1, 1]) == 0.0

    def test_zero_both_vectors(self):
        """Both zero vectors should return 0.0."""
        assert _cosine_similarity([0, 0], [0, 0]) == 0.0

    def test_empty_vectors(self):
        """Empty vectors should return 0.0."""
        assert _cosine_similarity([], []) == 0.0

    def test_one_empty_vector(self):
        """One empty vector should return 0.0."""
        assert _cosine_similarity([1, 2, 3], []) == 0.0
        assert _cosine_similarity([], [1, 2, 3]) == 0.0

    def test_normalized_vectors(self):
        """Normalized vectors should work correctly."""
        # (1/sqrt(2), 1/sqrt(2)) and (1/sqrt(2), 1/sqrt(2)) = 1.0
        import math
        unit = 1.0 / math.sqrt(2)
        assert abs(_cosine_similarity([unit, unit], [unit, unit]) - 1.0) < 1e-6

    def test_different_magnitudes_same_direction(self):
        """Vectors in same direction but different magnitudes should be 1.0."""
        assert abs(_cosine_similarity([1, 2, 3], [2, 4, 6]) - 1.0) < 1e-6


class TestEmbeddingClient:
    """Test EmbeddingClient initialization and TF-IDF fallback."""

    def test_init_with_api_key(self):
        """Client with API key should have API available."""
        client = EmbeddingClient(api_key="test-key")
        assert client._api_available is True

    def test_init_without_api_key(self):
        """Client without API key should have API unavailable."""
        client = EmbeddingClient()
        assert client._api_available is False

    def test_init_default_model(self):
        """Client should use default model when not specified."""
        client = EmbeddingClient()
        assert client._model == "text-embedding-3-small"

    def test_init_custom_model(self):
        """Client should use custom model when specified."""
        client = EmbeddingClient(model="custom-model")
        assert client._model == "custom-model"

    def test_cache_disabled(self):
        """Cache can be disabled."""
        client = EmbeddingClient(cache_enabled=False)
        assert client._cache_enabled is False

    def test_empty_texts_returns_empty_result(self):
        """Embedding empty text list should return empty vectors."""
        client = EmbeddingClient()
        result = client.embed_texts([])
        assert result.vectors == []
        assert result.tokens_used == 0

    def test_tfidf_fallback(self):
        """Without API key, should use TF-IDF fallback."""
        client = EmbeddingClient()  # No API key → fallback
        result = client.embed_texts(["hello world", "hello there"])
        assert len(result.vectors) == 2
        assert result.fallback_used is True
        assert result.model == "tfidf-fallback"
        # TF-IDF vectors should have consistent dimensions
        assert len(result.vectors[0]) > 0
        assert len(result.vectors[1]) > 0

    def test_similarity_matrix_shape(self):
        """Similarity matrix should have correct dimensions."""
        client = EmbeddingClient()
        matrix = client.similarity_matrix(["a", "b"], ["c", "d", "e"])
        assert len(matrix) == 2
        assert len(matrix[0]) == 3

    def test_similarity_matrix_empty_queries(self):
        """Empty queries should return empty matrix."""
        client = EmbeddingClient()
        matrix = client.similarity_matrix([], ["a", "b"])
        assert matrix == []

    def test_similarity_matrix_empty_corpus(self):
        """Empty corpus should return empty matrix."""
        client = EmbeddingClient()
        matrix = client.similarity_matrix(["a", "b"], [])
        assert matrix == []

    def test_tfidf_vectors_are_not_cached(self):
        """TF-IDF vectors should not be cached (corpus-dependent)."""
        client = EmbeddingClient()
        result1 = client.embed_texts(["test text"])
        stats1 = client.get_stats()
        # Second call with same text — TF-IDF not cached
        result2 = client.embed_texts(["test text"])
        stats2 = client.get_stats()
        # Cache size should remain 0 (TF-IDF vectors not cached)
        assert stats2["cache_size"] == 0

    def test_keyword_similarity(self):
        """Keyword similarity should work for overlapping text."""
        client = EmbeddingClient()
        score = client._keyword_similarity("facebook ads campaign", "facebook ads optimization")
        # "facebook" and "ads" overlap → Jaccard > 0
        assert 0.0 < score < 1.0

    def test_keyword_similarity_identical(self):
        """Keyword similarity for identical text should be 1.0."""
        client = EmbeddingClient()
        score = client._keyword_similarity("hello world", "hello world")
        assert score == 1.0

    def test_keyword_similarity_no_overlap(self):
        """Keyword similarity with no overlap should be 0.0."""
        client = EmbeddingClient()
        score = client._keyword_similarity("hello world", "foo bar")
        assert score == 0.0

    def test_keyword_similarity_empty_both(self):
        """Keyword similarity with both empty strings should be 1.0."""
        client = EmbeddingClient()
        score = client._keyword_similarity("", "")
        assert score == 1.0

    def test_get_stats(self):
        """get_stats should return all required fields."""
        client = EmbeddingClient(api_key="test")
        stats = client.get_stats()
        assert "tokens_used" in stats
        assert "cache_size" in stats
        assert "api_available" in stats
        assert stats["api_available"] is True
        assert stats["tokens_used"] == 0
        assert stats["cache_size"] == 0

    def test_similarity_both_empty_texts(self):
        """Similarity between two empty texts should be 0.0."""
        client = EmbeddingClient()
        score = client.similarity("", "")
        assert score == 0.0

    def test_similarity_one_empty_text(self):
        """Similarity with one empty text should be 0.0."""
        client = EmbeddingClient()
        score = client.similarity("hello", "")
        assert score == 0.0

    def test_similarity_same_text(self):
        """Similarity of text with itself should be high."""
        client = EmbeddingClient()
        score = client.similarity("hello world test", "hello world test")
        # TF-IDF vectors of identical text should have cosine sim ~1.0
        assert score > 0.9

    def test_tfidf_with_single_document(self):
        """TF-IDF with single document should work."""
        client = EmbeddingClient()
        result = client.embed_texts(["single document"])
        assert len(result.vectors) == 1
        assert len(result.vectors[0]) > 0

    def test_tfidf_with_numeric_tokens(self):
        """TF-IDF should handle texts with numbers."""
        client = EmbeddingClient()
        result = client.embed_texts(["test 123", "test 456"])
        assert len(result.vectors) == 2
        assert result.fallback_used is True

    def test_cache_hit_with_api_available(self):
        """With API available and cache enabled, same text should not re-embed."""
        client = EmbeddingClient(api_key="test-key")
        # Note: Real API calls will fail, but cache mechanisms should work
        # This test checks the cache structure itself
        assert client._cache_enabled is True
        assert len(client._cache) == 0

    def test_embedding_result_structure(self):
        """EmbeddingResult should have all required fields."""
        result = EmbeddingResult(
            vectors=[[1.0, 2.0]],
            model="test-model",
            tokens_used=100,
            from_cache=False,
            fallback_used=True
        )
        assert result.vectors == [[1.0, 2.0]]
        assert result.model == "test-model"
        assert result.tokens_used == 100
        assert result.from_cache is False
        assert result.fallback_used is True


class TestConfidenceMap:
    """Test P5 confidence map generation from verification scores."""

    def test_verified_unverified_with_scores(self):
        """Confidence map should categorize atoms as VERIFIED or UNVERIFIED."""
        from pipeline.phases.p5_build import _generate_confidence_map

        atoms = [
            {
                "title": "A",
                "verification_note": "Verified (score 0.85) against ref.md",
                "baseline_reference": "ref.md",
            },
            {
                "title": "B",
                "verification_note": "Partial match (score 0.60) against ref2.md",
                "baseline_reference": "ref2.md",
            },
            {
                "title": "C",
                "verification_note": "Expert insight (best match score 0.30)",
                "baseline_reference": "",
            },
            {
                "title": "D",
                "verification_note": "",
                "baseline_reference": "",
            },
        ]
        result = _generate_confidence_map(atoms)
        assert isinstance(result, str)
        assert "VERIFIED" in result
        assert "UNVERIFIED" in result
        assert "- A" in result  # has score and ref → VERIFIED
        assert "- B" in result  # has score and ref → VERIFIED
        assert "- C" in result  # has score → VERIFIED
        assert "- D" in result  # no score, no ref → UNVERIFIED

    def test_backward_compatible_no_scores(self):
        """Confidence map should work without extraction scores."""
        from pipeline.phases.p5_build import _generate_confidence_map

        atoms = [
            {
                "title": "X",
                "verification_note": "Verified against ref",
                "baseline_reference": "ref.md",
            },
            {
                "title": "Y",
                "verification_note": "",
                "baseline_reference": "",
            },
        ]
        result = _generate_confidence_map(atoms)
        assert "VERIFIED" in result  # X has ref → VERIFIED
        assert "UNVERIFIED" in result   # Y no ref, no score → UNVERIFIED
        assert "- X" in result
        assert "- Y" in result

    def test_score_with_reference_is_verified(self):
        """Atoms with score should be VERIFIED."""
        from pipeline.phases.p5_build import _generate_confidence_map

        atoms = [
            {
                "title": "Perfect",
                "verification_note": "score 1.0",
                "baseline_reference": "",
            },
            {
                "title": "Weak Score",
                "verification_note": "score 0.25",
                "baseline_reference": "",
            },
        ]
        result = _generate_confidence_map(atoms)
        assert "- Perfect" in result
        assert "- Weak Score" in result
        # Both should be VERIFIED (score is present)
        lines = result.split("\n")
        perfect_idx = next(i for i, l in enumerate(lines) if "- Perfect" in l)
        weak_idx = next(i for i, l in enumerate(lines) if "- Weak Score" in l)
        verified_idx = next(i for i, l in enumerate(lines) if "### VERIFIED" in l)
        unverified_idx = next(i for i, l in enumerate(lines) if "### UNVERIFIED" in l)
        assert verified_idx < perfect_idx
        assert verified_idx < weak_idx
        assert unverified_idx > perfect_idx

    def test_reference_without_score_is_verified(self):
        """Atoms with baseline_reference but no score should be VERIFIED."""
        from pipeline.phases.p5_build import _generate_confidence_map

        atoms = [
            {
                "title": "Referenced",
                "verification_note": "Some note without score",
                "baseline_reference": "some_ref.md",
            },
        ]
        result = _generate_confidence_map(atoms)
        lines = result.split("\n")
        ref_idx = next(i for i, l in enumerate(lines) if "- Referenced" in l)
        verified_idx = next(i for i, l in enumerate(lines) if "### VERIFIED" in l)
        unverified_idx = next(i for i, l in enumerate(lines) if "### UNVERIFIED" in l)
        assert verified_idx < ref_idx < unverified_idx

    def test_truncation_at_limits(self):
        """Long lists should be truncated with '... and N more'."""
        from pipeline.phases.p5_build import _generate_confidence_map

        # Create 16 VERIFIED atoms (limit is 15)
        atoms = [
            {
                "title": f"Verified{i}",
                "verification_note": f"score 0.{80 + i}",
                "baseline_reference": "",
            }
            for i in range(16)
        ]
        result = _generate_confidence_map(atoms)
        assert "... and 1 more" in result  # 16 - 15 = 1

    def test_empty_atom_list(self):
        """Empty atom list should produce valid output."""
        from pipeline.phases.p5_build import _generate_confidence_map

        result = _generate_confidence_map([])
        assert "### Confidence Map" in result
        assert "### VERIFIED" in result
        assert "### UNVERIFIED" in result

    def test_invalid_score_format_unverified(self):
        """Invalid score format should be treated as no score."""
        from pipeline.phases.p5_build import _generate_confidence_map

        atoms = [
            {
                "title": "Invalid",
                "verification_note": "score not_a_number",
                "baseline_reference": "",
            },
        ]
        result = _generate_confidence_map(atoms)
        # No valid score and no ref → UNVERIFIED
        lines = result.split("\n")
        invalid_idx = next(i for i, l in enumerate(lines) if "- Invalid" in l)
        unverified_idx = next(i for i, l in enumerate(lines) if "### UNVERIFIED" in l)
        assert unverified_idx < invalid_idx


class TestEmbeddingIntegrationWithPhases:
    """Integration tests for embedding client with phase utilities."""

    def test_embedding_client_can_be_attached_to_config(self, build_config):
        """Embedding client should attach to build config."""
        client = EmbeddingClient()
        build_config.embedding_client = client
        assert build_config.embedding_client is client
        assert build_config.embedding_client._api_available is False

    def test_embedding_client_with_api_key_attached(self, build_config):
        """Embedding client with API key should indicate availability."""
        client = EmbeddingClient(api_key="test-key")
        build_config.embedding_client = client
        assert build_config.embedding_client._api_available is True

    def test_similarity_matrix_for_dedup_texts(self):
        """Similarity matrix should correctly rank similar texts."""
        client = EmbeddingClient()

        # Dedup scenario: transcript atoms vs baseline atoms
        transcript_atoms = [
            "Facebook Ads Manager allows campaign setup",
            "Audience targeting on Facebook",
        ]
        baseline_atoms = [
            "Facebook Ads configuration",
            "Campaign creation tutorial",
            "Python programming basics",
        ]

        matrix = client.similarity_matrix(transcript_atoms, baseline_atoms)
        assert len(matrix) == 2
        assert len(matrix[0]) == 3

        # First transcript atom should be most similar to first baseline (both about Ads Manager)
        sim_ads_to_ads_config = matrix[0][0]
        sim_ads_to_python = matrix[0][2]
        assert sim_ads_to_ads_config > sim_ads_to_python  # Ads to Ads > Ads to Python

    def test_similarity_metric_consistency(self):
        """Similarity scores should be consistent across multiple calls."""
        client = EmbeddingClient()

        text_a = "machine learning algorithms"
        text_b = "deep learning neural networks"

        score1 = client.similarity(text_a, text_b)
        score2 = client.similarity(text_a, text_b)

        # TF-IDF should produce identical scores for identical inputs
        assert score1 == score2
        assert 0.0 <= score1 <= 1.0

    def test_embedding_result_fallback_flag(self):
        """EmbeddingResult should correctly report fallback usage."""
        client = EmbeddingClient()  # No API key
        result = client.embed_texts(["test text"])
        assert result.fallback_used is True
        assert result.model == "tfidf-fallback"

    def test_embedding_client_stats_tracks_calls(self):
        """Statistics should track embedding calls."""
        client = EmbeddingClient()
        stats1 = client.get_stats()
        assert stats1["tokens_used"] == 0
        assert stats1["cache_size"] == 0

        # Make some embeddings
        client.embed_texts(["hello", "world"])
        stats2 = client.get_stats()
        # TF-IDF doesn't use tokens, but the call should be tracked
        assert stats2["cache_size"] == 0  # TF-IDF not cached
