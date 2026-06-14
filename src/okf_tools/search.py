"""Vector index: embed, store, and query concepts using fastembed + sqlite-vec."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import numpy as np

from .errors import IndexCorruptionError


@dataclass
class SearchResult:
    """A single search result from semantic query."""

    concept_id: str
    title: Optional[str]
    score: float
    snippet: str


# --- Embedding (lazy-loaded) ---

_embedder_cache: Dict[str, Any] = {}


def get_embedder(model_name: str) -> Any:
    """Lazily initialize and cache the fastembed TextEmbedding model."""
    if model_name not in _embedder_cache:
        from fastembed import TextEmbedding

        _embedder_cache[model_name] = TextEmbedding(model_name=model_name)
    return _embedder_cache[model_name]


def embed_text(text: str, model_name: str) -> np.ndarray:
    """Embed a single text string. Returns 384-dim vector."""
    embedder = get_embedder(model_name)
    results = list(embedder.embed([text]))
    return np.array(results[0], dtype=np.float32)


def embed_batch(texts: List[str], model_name: str) -> List[np.ndarray]:
    """Batch embed for reindex efficiency."""
    if not texts:
        return []
    embedder = get_embedder(model_name)
    results = list(embedder.embed(texts))
    return [np.array(r, dtype=np.float32) for r in results]


# --- Vector Index ---


class VectorIndex:
    """Manages the sqlite-vec sidecar database."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._load_extension()
        self._create_tables()

    def _load_extension(self) -> None:
        """Load the sqlite-vec extension."""
        import sqlite_vec

        self._conn.enable_load_extension(True)
        sqlite_vec.load(self._conn)
        self._conn.enable_load_extension(False)

    def _create_tables(self) -> None:
        """Create required tables if they don't exist."""
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS sync_meta (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            CREATE TABLE IF NOT EXISTS concepts (
                concept_id TEXT PRIMARY KEY,
                title TEXT,
                type TEXT,
                tags TEXT,
                mtime REAL,
                snippet TEXT
            );
        """)
        # Create vector virtual table
        self._conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS vec_concepts USING vec0(
                concept_id TEXT PRIMARY KEY,
                embedding FLOAT[384]
            )
        """)
        self._conn.commit()

    def upsert(self, concept_id: str, embedding: np.ndarray, metadata: Dict[str, Any]) -> None:
        """Add or update a concept's embedding and metadata."""
        # Upsert metadata
        self._conn.execute(
            """INSERT OR REPLACE INTO concepts
               (concept_id, title, type, tags, mtime, snippet)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                concept_id,
                metadata.get("title"),
                metadata.get("type"),
                json.dumps(metadata.get("tags", [])),
                metadata.get("mtime"),
                metadata.get("snippet"),
            ),
        )
        # Upsert embedding
        self._conn.execute(
            "DELETE FROM vec_concepts WHERE concept_id = ?", (concept_id,)
        )
        self._conn.execute(
            "INSERT INTO vec_concepts (concept_id, embedding) VALUES (?, ?)",
            (concept_id, embedding.tobytes()),
        )
        self._conn.commit()

    def delete(self, concept_id: str) -> None:
        """Remove a concept from the index."""
        self._conn.execute("DELETE FROM concepts WHERE concept_id = ?", (concept_id,))
        self._conn.execute("DELETE FROM vec_concepts WHERE concept_id = ?", (concept_id,))
        self._conn.commit()

    def search(
        self, query_embedding: np.ndarray, top_n: int, threshold: float
    ) -> List[SearchResult]:
        """Cosine similarity search. Returns results above threshold."""
        rows = self._conn.execute(
            """
            SELECT v.concept_id, v.distance, c.title, c.snippet
            FROM vec_concepts v
            JOIN concepts c ON v.concept_id = c.concept_id
            WHERE v.embedding MATCH ?
                AND k = ?
            ORDER BY v.distance
            """,
            (query_embedding.tobytes(), top_n),
        ).fetchall()

        results = []
        for concept_id, distance, title, snippet in rows:
            # sqlite-vec returns cosine distance; similarity = 1 - distance
            score = 1.0 - distance
            if score >= threshold:
                results.append(SearchResult(
                    concept_id=concept_id,
                    title=title,
                    score=round(score, 4),
                    snippet=snippet or "",
                ))
        return results

    def get_metadata(self, concept_id: str) -> Optional[Dict[str, Any]]:
        """Get stored metadata for a concept."""
        row = self._conn.execute(
            "SELECT title, type, tags, mtime, snippet FROM concepts WHERE concept_id = ?",
            (concept_id,),
        ).fetchone()
        if not row:
            return None
        return {
            "title": row[0],
            "type": row[1],
            "tags": json.loads(row[2]) if row[2] else [],
            "mtime": row[3],
            "snippet": row[4],
        }

    def get_all_concept_ids(self) -> Set[str]:
        """Return all indexed concept IDs."""
        rows = self._conn.execute("SELECT concept_id FROM concepts").fetchall()
        return {row[0] for row in rows}

    def get_all_mtimes(self) -> Dict[str, float]:
        """Return concept_id -> mtime mapping for all indexed concepts."""
        rows = self._conn.execute("SELECT concept_id, mtime FROM concepts").fetchall()
        return {row[0]: row[1] for row in rows}

    def get_sync_timestamp(self) -> Optional[float]:
        """Get last sync timestamp."""
        row = self._conn.execute(
            "SELECT value FROM sync_meta WHERE key = 'last_sync'"
        ).fetchone()
        return float(row[0]) if row else None

    def set_sync_timestamp(self, ts: float) -> None:
        """Persist sync timestamp."""
        self._conn.execute(
            "INSERT OR REPLACE INTO sync_meta (key, value) VALUES ('last_sync', ?)",
            (str(ts),),
        )
        self._conn.commit()

    def concept_count(self) -> int:
        """Number of indexed concepts."""
        row = self._conn.execute("SELECT COUNT(*) FROM concepts").fetchone()
        return row[0] if row else 0

    def check_integrity(self) -> bool:
        """Verify database is openable and passes integrity_check."""
        try:
            result = self._conn.execute("PRAGMA integrity_check").fetchone()
            return result[0] == "ok"
        except Exception:
            return False

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
