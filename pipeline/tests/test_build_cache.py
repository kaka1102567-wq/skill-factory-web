"""Tests for cross-build cache."""

import json
import os
import time

import pytest

from pipeline.core.build_cache import BuildCache, CacheStats


@pytest.fixture
def cache_dir(tmp_path):
    return str(tmp_path / "build_cache")


@pytest.fixture
def cache(cache_dir):
    return BuildCache(cache_dir=cache_dir, ttl_days=30)


class TestAtomsCache:
    def test_save_and_get(self, cache):
        atoms = [{"id": "atom_1", "title": "Test", "content": "Hello"}]
        cache.save_atoms("hash1", "sonnet", "v1", "standard", atoms)
        result = cache.get_atoms("hash1", "sonnet", "v1", "standard")
        assert result == atoms

    def test_miss_returns_none(self, cache):
        result = cache.get_atoms("nonexistent", "sonnet", "v1", "standard")
        assert result is None

    def test_different_model_is_miss(self, cache):
        atoms = [{"id": "atom_1"}]
        cache.save_atoms("hash1", "sonnet", "v1", "standard", atoms)
        result = cache.get_atoms("hash1", "deepseek", "v1", "standard")
        assert result is None

    def test_different_prompt_version_is_miss(self, cache):
        atoms = [{"id": "atom_1"}]
        cache.save_atoms("hash1", "sonnet", "v1", "standard", atoms)
        result = cache.get_atoms("hash1", "sonnet", "v2", "standard")
        assert result is None

    def test_different_tier_is_miss(self, cache):
        atoms = [{"id": "atom_1"}]
        cache.save_atoms("hash1", "sonnet", "v1", "standard", atoms)
        result = cache.get_atoms("hash1", "sonnet", "v1", "premium")
        assert result is None

    def test_ttl_expiry(self, cache_dir):
        cache = BuildCache(cache_dir=cache_dir, ttl_days=0)
        atoms = [{"id": "atom_1"}]
        cache.save_atoms("hash1", "sonnet", "v1", "standard", atoms)
        time.sleep(0.1)
        result = cache.get_atoms("hash1", "sonnet", "v1", "standard")
        assert result is None


class TestInventoryCache:
    def test_save_and_get(self, cache):
        inventory = {"topics": ["A", "B"], "coverage_matrix": {}}
        hashes = ["h1", "h2"]
        cache.save_inventory("facebook-ads", hashes, "sonnet", "standard", inventory)
        result = cache.get_inventory("facebook-ads", hashes, "sonnet", "standard")
        assert result == inventory

    def test_different_fileset_is_miss(self, cache):
        inventory = {"topics": ["A"]}
        cache.save_inventory("domain", ["h1", "h2"], "sonnet", "standard", inventory)
        result = cache.get_inventory("domain", ["h1", "h2", "h3"], "sonnet", "standard")
        assert result is None

    def test_hash_order_irrelevant(self, cache):
        inventory = {"topics": ["A"]}
        cache.save_inventory("domain", ["h2", "h1"], "sonnet", "standard", inventory)
        result = cache.get_inventory("domain", ["h1", "h2"], "sonnet", "standard")
        assert result == inventory


class TestEmbeddingsCache:
    def test_save_and_get(self, cache):
        vectors = [[0.1, 0.2], [0.3, 0.4]]
        cache.save_embeddings("texthash", "text-embedding-3-small", vectors)
        result = cache.get_embeddings("texthash", "text-embedding-3-small")
        assert result == vectors

    def test_different_model_is_miss(self, cache):
        vectors = [[0.1, 0.2]]
        cache.save_embeddings("texthash", "model-a", vectors)
        result = cache.get_embeddings("texthash", "model-b")
        assert result is None


class TestFileContentHash:
    def test_same_content_same_hash(self, tmp_path):
        f1 = tmp_path / "file_a.txt"
        f2 = tmp_path / "file_b.txt"
        f1.write_text("Hello World")
        f2.write_text("Hello World")
        assert BuildCache.file_content_hash(str(f1)) == BuildCache.file_content_hash(str(f2))

    def test_different_content_different_hash(self, tmp_path):
        f1 = tmp_path / "file1.txt"
        f2 = tmp_path / "file2.txt"
        f1.write_text("Hello")
        f2.write_text("World")
        assert BuildCache.file_content_hash(str(f1)) != BuildCache.file_content_hash(str(f2))


class TestGracefulDegradation:
    def test_corrupt_json_returns_none(self, cache, cache_dir):
        atoms_dir = os.path.join(cache_dir, "atoms")
        os.makedirs(atoms_dir, exist_ok=True)
        corrupt_file = os.path.join(atoms_dir, "abcd1234abcd1234.json")
        with open(corrupt_file, "w") as f:
            f.write("{invalid json")
        # Should not crash
        result = cache.get_atoms("doesnt_matter", "m", "v", "t")
        assert result is None or result is None  # Just verifies no exception

    def test_missing_dir_auto_creates(self, tmp_path):
        new_dir = str(tmp_path / "nonexistent" / "cache")
        cache = BuildCache(cache_dir=new_dir)
        assert os.path.isdir(os.path.join(new_dir, "atoms"))
        assert os.path.isdir(os.path.join(new_dir, "inventory"))
        assert os.path.isdir(os.path.join(new_dir, "embeddings"))


class TestCacheManagement:
    def test_stats(self, cache):
        cache.save_atoms("h1", "m", "v1", "s", [{"id": "1"}])
        cache.save_atoms("h2", "m", "v1", "s", [{"id": "2"}])
        cache.save_inventory("d", ["h1"], "m", "s", {"topics": []})
        stats = cache.get_stats()
        assert stats.atom_entries == 2
        assert stats.inventory_entries == 1
        assert stats.total_size_bytes > 0

    def test_clear_all(self, cache):
        cache.save_atoms("h1", "m", "v1", "s", [{"id": "1"}])
        cache.save_inventory("d", ["h1"], "m", "s", {})
        cleared = cache.clear()
        assert cleared >= 2
        assert cache.get_stats().atom_entries == 0

    def test_clear_older_than(self, cache_dir):
        cache = BuildCache(cache_dir=cache_dir)
        cache.save_atoms("h1", "m", "v1", "s", [{"id": "1"}])

        # Backdate the entry
        for f in (cache.cache_dir / "atoms").glob("*.json"):
            data = json.loads(f.read_text())
            data["metadata"]["timestamp"] = time.time() - 100 * 86400
            f.write_text(json.dumps(data))

        # Save a fresh entry
        cache.save_atoms("h2", "m", "v1", "s", [{"id": "2"}])

        cleared = cache.clear(older_than_days=30)
        assert cleared == 1
        assert cache.get_stats().atom_entries == 1
