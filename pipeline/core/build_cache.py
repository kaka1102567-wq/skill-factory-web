"""Cross-build cache for atoms and inventory.

Caches:
- P2 atoms per file: key = hash(file_content + model + prompt_version + tier)
- P1 inventory per domain: key = hash(domain + sorted(file_hashes) + model + tier)
- Embeddings per text: key = hash(text + embedding_model)

Storage: JSON files in data/cache/build_cache/
TTL: 30 days (configurable)
Thread-safe: file locking for writes via atomic rename
"""

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path


DEFAULT_TTL_DAYS = 30


@dataclass
class CacheStats:
    """Cache usage statistics."""
    atom_entries: int
    inventory_entries: int
    embedding_entries: int
    total_size_bytes: int
    oldest_entry_age_days: float
    newest_entry_age_days: float


class BuildCache:
    """Cross-build persistent cache with JSON storage and TTL expiry.

    Directory structure:
    cache_dir/
    ├── atoms/          # P2 atoms per file
    ├── inventory/      # P1 inventory per domain+fileset
    └── embeddings/     # Embedding vectors per text set
    """

    def __init__(self, cache_dir: str = "data/cache/build_cache",
                 ttl_days: int = DEFAULT_TTL_DAYS):
        self.cache_dir = Path(cache_dir)
        self.ttl_seconds = ttl_days * 86400
        self._ensure_dirs()

    def _ensure_dirs(self):
        """Create cache subdirectories if they don't exist."""
        for subdir in ("atoms", "inventory", "embeddings"):
            (self.cache_dir / subdir).mkdir(parents=True, exist_ok=True)

    # ── Atoms cache (P2) ──

    def get_atoms(self, file_hash: str, model: str,
                  prompt_version: str, tier: str) -> list[dict] | None:
        """Get cached atoms for a file. Returns None on miss/expired."""
        key = self._atoms_key(file_hash, model, prompt_version, tier)
        return self._read_cache("atoms", key, "atoms")

    def save_atoms(self, file_hash: str, model: str,
                   prompt_version: str, tier: str, atoms: list[dict]):
        """Save extracted atoms for a file."""
        key = self._atoms_key(file_hash, model, prompt_version, tier)
        self._write_cache("atoms", key, {
            "atoms": atoms,
            "metadata": {
                "file_hash": file_hash, "model": model,
                "prompt_version": prompt_version, "tier": tier,
                "timestamp": time.time(), "atoms_count": len(atoms),
            },
        })

    def _atoms_key(self, file_hash: str, model: str,
                   prompt_version: str, tier: str) -> str:
        raw = f"{file_hash}:{model}:{prompt_version}:{tier}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    # ── Inventory cache (P1) ──

    def get_inventory(self, domain: str, file_hashes: list[str],
                      model: str, tier: str) -> dict | None:
        """Get cached inventory. Only valid for EXACT same file set."""
        key = self._inventory_key(domain, file_hashes, model, tier)
        return self._read_cache("inventory", key, "inventory")

    def save_inventory(self, domain: str, file_hashes: list[str],
                       model: str, tier: str, inventory: dict):
        """Save audit inventory for a domain + file set."""
        key = self._inventory_key(domain, file_hashes, model, tier)
        self._write_cache("inventory", key, {
            "inventory": inventory,
            "metadata": {
                "domain": domain, "file_hashes": sorted(file_hashes),
                "model": model, "tier": tier, "timestamp": time.time(),
            },
        })

    def _inventory_key(self, domain: str, file_hashes: list[str],
                       model: str, tier: str) -> str:
        sorted_hashes = ":".join(sorted(file_hashes))
        raw = f"{domain}:{sorted_hashes}:{model}:{tier}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    # ── Embeddings cache ──

    def get_embeddings(self, text_hash: str,
                       embedding_model: str) -> list[list[float]] | None:
        """Get cached embedding vectors."""
        key = self._embedding_key(text_hash, embedding_model)
        return self._read_cache("embeddings", key, "vectors")

    def save_embeddings(self, text_hash: str, embedding_model: str,
                        vectors: list[list[float]]):
        """Save embedding vectors."""
        key = self._embedding_key(text_hash, embedding_model)
        self._write_cache("embeddings", key, {
            "vectors": vectors,
            "metadata": {
                "text_hash": text_hash,
                "embedding_model": embedding_model,
                "timestamp": time.time(),
            },
        })

    def _embedding_key(self, text_hash: str, embedding_model: str) -> str:
        raw = f"{text_hash}:{embedding_model}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    # ── File hash ──

    @staticmethod
    def file_content_hash(filepath: str) -> str:
        """SHA256 hash of file content (truncated 16 hex). Rename-safe."""
        with open(filepath, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()[:16]

    # ── Cache I/O ──

    def _read_cache(self, subdir: str, key: str, data_field: str):
        """Read cache entry. Returns None if miss/expired/corrupt."""
        path = self.cache_dir / subdir / f"{key}.json"
        try:
            if not path.exists():
                return None
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # TTL check
            timestamp = data.get("metadata", {}).get("timestamp", 0)
            if time.time() - timestamp > self.ttl_seconds:
                path.unlink(missing_ok=True)
                return None
            return data.get(data_field)
        except (json.JSONDecodeError, OSError, KeyError):
            path.unlink(missing_ok=True)
            return None

    def _write_cache(self, subdir: str, key: str, data: dict):
        """Write cache entry. Thread-safe via atomic rename."""
        path = self.cache_dir / subdir / f"{key}.json"
        tmp_path = path.with_suffix(".tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=True, indent=2)
            tmp_path.replace(path)
        except OSError:
            tmp_path.unlink(missing_ok=True)

    # ── Management ──

    def get_stats(self) -> CacheStats:
        """Get cache usage statistics."""
        atom_count = len(list((self.cache_dir / "atoms").glob("*.json")))
        inv_count = len(list((self.cache_dir / "inventory").glob("*.json")))
        emb_count = len(list((self.cache_dir / "embeddings").glob("*.json")))
        total_size = sum(
            f.stat().st_size for f in self.cache_dir.rglob("*.json")
        )
        ages = []
        for f in self.cache_dir.rglob("*.json"):
            try:
                data = json.loads(f.read_text())
                ts = data.get("metadata", {}).get("timestamp", 0)
                if ts:
                    ages.append((time.time() - ts) / 86400)
            except (json.JSONDecodeError, OSError):
                pass

        return CacheStats(
            atom_entries=atom_count,
            inventory_entries=inv_count,
            embedding_entries=emb_count,
            total_size_bytes=total_size,
            oldest_entry_age_days=max(ages) if ages else 0,
            newest_entry_age_days=min(ages) if ages else 0,
        )

    def clear(self, older_than_days: int | None = None) -> int:
        """Clear cache entries. None = all, N = older than N days."""
        cutoff = (
            time.time() - (older_than_days * 86400)
            if older_than_days else float("inf")
        )
        cleared = 0
        for f in self.cache_dir.rglob("*.json"):
            try:
                if older_than_days is None:
                    f.unlink()
                    cleared += 1
                else:
                    data = json.loads(f.read_text())
                    ts = data.get("metadata", {}).get("timestamp", 0)
                    if ts and ts < cutoff:
                        f.unlink()
                        cleared += 1
            except (json.JSONDecodeError, OSError):
                f.unlink(missing_ok=True)
                cleared += 1
        return cleared
