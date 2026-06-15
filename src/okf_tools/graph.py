"""Link graph: parse markdown links, build adjacency, and perform traversal."""

from __future__ import annotations

import re
import sqlite3
from collections import deque
from pathlib import Path
from typing import Dict, List, Set

from .bundle import Concept


# Pattern to match markdown links: [text](url)
_LINK_PATTERN = re.compile(r"\[(?:[^\]]*)\]\(([^)]+)\)")
# Pattern to match wikilinks: [[concept-id]] or [[concept-id|display text]]
_WIKILINK_PATTERN = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]")


def extract_links(concept: Concept, bundle_root: Path) -> List[str]:
    """Parse markdown links and wikilinks from body, resolve to concept_ids.

    Supports:
    - Markdown links: [text](path.md) — internal only (no http://)
    - Wikilinks: [[concept-id]] or [[concept-id|display text]]
    """
    links: List[str] = []
    concept_dir = concept.file_path.parent

    # Markdown-style links
    for match in _LINK_PATTERN.finditer(concept.body):
        url = match.group(1).strip()

        # Skip external URLs
        if url.startswith(("http://", "https://", "mailto:")):
            continue
        # Skip fragment-only anchors
        if url.startswith("#"):
            continue
        # Must end with .md to be a concept link
        if not url.endswith(".md"):
            continue

        # Strip any fragment
        url = url.split("#")[0]

        # Resolve path
        if url.startswith("/"):
            # Absolute from bundle root
            resolved = bundle_root / url.lstrip("/")
        else:
            # Relative to concept's directory
            resolved = (concept_dir / url).resolve()

        # Convert to concept_id
        try:
            rel = resolved.relative_to(bundle_root.resolve())
            concept_id = str(rel.with_suffix(""))
            links.append(concept_id)
        except ValueError:
            continue  # Outside bundle root

    # Wikilinks: [[concept-id]] or [[concept-id|display text]]
    for match in _WIKILINK_PATTERN.finditer(concept.body):
        target = match.group(1).strip()
        # Normalize: treat as concept_id directly (lowercase, hyphens)
        # If it looks like a path with .md, strip the extension
        if target.endswith(".md"):
            target = target[:-3]
        # Convert spaces to hyphens for slug matching
        target = target.replace(" ", "-").lower()
        if target and target not in links:
            links.append(target)

    return links


class LinkGraph:
    """Bidirectional link graph backed by SQLite."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._create_tables()

    def _create_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS links (
                source_id TEXT,
                target_id TEXT,
                PRIMARY KEY (source_id, target_id)
            );
            CREATE INDEX IF NOT EXISTS idx_links_target
                ON links(target_id);
        """)
        self._conn.commit()

    def set_links(self, source_id: str, target_ids: List[str]) -> None:
        """Replace all outlinks for a source concept."""
        self._conn.execute("DELETE FROM links WHERE source_id = ?", (source_id,))
        if target_ids:
            self._conn.executemany(
                "INSERT OR IGNORE INTO links (source_id, target_id) VALUES (?, ?)",
                [(source_id, t) for t in target_ids],
            )
        self._conn.commit()

    def remove_concept(self, concept_id: str) -> None:
        """Remove all links involving this concept (in + out)."""
        self._conn.execute("DELETE FROM links WHERE source_id = ?", (concept_id,))
        self._conn.execute("DELETE FROM links WHERE target_id = ?", (concept_id,))
        self._conn.commit()

    def get_outlinks(self, concept_id: str) -> List[str]:
        """Concepts this one links to."""
        rows = self._conn.execute(
            "SELECT target_id FROM links WHERE source_id = ?", (concept_id,)
        ).fetchall()
        return [row[0] for row in rows]

    def get_inlinks(self, concept_id: str) -> List[str]:
        """Concepts that link to this one."""
        rows = self._conn.execute(
            "SELECT source_id FROM links WHERE target_id = ?", (concept_id,)
        ).fetchall()
        return [row[0] for row in rows]

    def bfs_neighborhood(
        self, concept_id: str, depth: int, direction: str = "both"
    ) -> List[str]:
        """BFS traversal. direction: 'in', 'out', or 'both'."""
        visited: Set[str] = {concept_id}
        queue: deque = deque([(concept_id, 0)])
        result: List[str] = []

        while queue:
            current, current_depth = queue.popleft()
            if current_depth >= depth:
                continue

            neighbors: Set[str] = set()
            if direction in ("out", "both"):
                neighbors.update(self.get_outlinks(current))
            if direction in ("in", "both"):
                neighbors.update(self.get_inlinks(current))

            for neighbor in neighbors:
                if neighbor not in visited:
                    visited.add(neighbor)
                    result.append(neighbor)
                    queue.append((neighbor, current_depth + 1))

        return result

    def get_orphans(self, all_concept_ids: Set[str]) -> List[str]:
        """Concepts with no inbound or outbound links."""
        linked = set()
        rows = self._conn.execute("SELECT DISTINCT source_id FROM links").fetchall()
        linked.update(row[0] for row in rows)
        rows = self._conn.execute("SELECT DISTINCT target_id FROM links").fetchall()
        linked.update(row[0] for row in rows)
        return sorted(all_concept_ids - linked)

    def get_stats(self, total_concepts: int) -> Dict[str, float]:
        """Edge count and average links per concept."""
        row = self._conn.execute("SELECT COUNT(*) FROM links").fetchone()
        edge_count = row[0] if row else 0
        avg = round(edge_count / total_concepts, 1) if total_concepts > 0 else 0.0
        return {"edge_count": edge_count, "average_links_per_concept": avg}

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
