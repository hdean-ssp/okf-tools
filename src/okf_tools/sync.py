"""Index synchronisation: detect changes and drive incremental/full rebuilds."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

from .bundle import Concept, is_concept_file, parse_concept, walk_concepts
from .config import OkfConfig
from .errors import ParseError
from .graph import LinkGraph, extract_links
from .search import VectorIndex, embed_batch


@dataclass
class ChangeSet:
    """Files changed since last index sync."""

    added: List[Path] = field(default_factory=list)
    modified: List[Path] = field(default_factory=list)
    deleted: List[str] = field(default_factory=list)


@dataclass
class SyncSummary:
    """Result of a reindex operation."""

    added: int = 0
    updated: int = 0
    removed: int = 0
    total_indexed: int = 0
    skipped: List[str] = field(default_factory=list)


def detect_changes(bundle_root: Path, index: VectorIndex) -> ChangeSet:
    """Compare filesystem state to indexed state."""
    changes = ChangeSet()
    indexed_mtimes = index.get_all_mtimes()
    on_disk: Dict[str, Path] = {}

    # Walk filesystem
    for md_file in sorted(bundle_root.rglob("*.md")):
        if not is_concept_file(md_file):
            continue
        # Skip .okf/ sidecar
        try:
            md_file.relative_to(bundle_root / ".okf")
            continue
        except ValueError:
            pass

        rel = md_file.resolve().relative_to(bundle_root.resolve())
        concept_id = str(rel.with_suffix(""))
        on_disk[concept_id] = md_file

        mtime = md_file.stat().st_mtime
        if concept_id not in indexed_mtimes:
            changes.added.append(md_file)
        elif mtime > indexed_mtimes[concept_id]:
            changes.modified.append(md_file)

    # Detect deleted
    for concept_id in indexed_mtimes:
        if concept_id not in on_disk:
            changes.deleted.append(concept_id)

    return changes


def incremental_reindex(
    bundle_root: Path, index: VectorIndex, graph: LinkGraph, config: OkfConfig
) -> SyncSummary:
    """Process only changed files."""
    # Check model compatibility
    warning = index.check_model_compatibility(config.embedding_model)
    if warning:
        import sys
        print(f"warning: {warning}", file=sys.stderr)

    changes = detect_changes(bundle_root, index)
    summary = SyncSummary()

    # Process added + modified
    to_process = [(f, "added") for f in changes.added] + [
        (f, "modified") for f in changes.modified
    ]

    if to_process:
        concepts: List[Concept] = []
        for file_path, _ in to_process:
            try:
                concept = parse_concept(file_path, bundle_root)
                concepts.append(concept)
            except ParseError:
                summary.skipped.append(str(file_path))

        if concepts:
            texts = [c.body for c in concepts]
            try:
                embeddings = embed_batch(texts, config.embedding_model)
            except Exception:
                summary.skipped.extend(c.concept_id for c in concepts)
                concepts = []
                embeddings = []

            for concept, embedding in zip(concepts, embeddings):
                metadata = {
                    "title": concept.title,
                    "type": concept.type,
                    "tags": concept.tags,
                    "mtime": concept.file_path.stat().st_mtime,
                    "snippet": concept.body[:200],
                    "body": concept.body,
                }
                index.upsert(concept.concept_id, embedding, metadata)
                # Update graph
                targets = extract_links(concept, bundle_root)
                graph.set_links(concept.concept_id, targets)

    summary.added = len(changes.added) - len(
        [s for s in summary.skipped if any(str(f) == s for f in changes.added)]
    )
    summary.updated = len(changes.modified) - len(
        [s for s in summary.skipped if any(str(f) == s for f in changes.modified)]
    )

    # Remove deleted
    for concept_id in changes.deleted:
        index.delete(concept_id)
        graph.remove_concept(concept_id)
    summary.removed = len(changes.deleted)

    # Persist timestamp
    index.set_sync_timestamp(time.time())
    summary.total_indexed = index.concept_count()

    return summary


def full_reindex(
    bundle_root: Path, index: VectorIndex, graph: LinkGraph, config: OkfConfig
) -> SyncSummary:
    """Drop all index data and rebuild from scratch."""
    summary = SyncSummary()

    # Clear existing data
    index.clear()
    graph.clear()

    # Walk and process all concepts
    concepts = walk_concepts(bundle_root)

    if concepts:
        texts = [c.body for c in concepts]
        try:
            embeddings = embed_batch(texts, config.embedding_model)
        except Exception:
            summary.skipped = [c.concept_id for c in concepts]
            index.set_sync_timestamp(time.time())
            return summary

        for concept, embedding in zip(concepts, embeddings):
            metadata = {
                "title": concept.title,
                "type": concept.type,
                "tags": concept.tags,
                "mtime": concept.file_path.stat().st_mtime,
                "snippet": concept.body[:200],
                "body": concept.body,
            }
            index.upsert(concept.concept_id, embedding, metadata)
            targets = extract_links(concept, bundle_root)
            graph.set_links(concept.concept_id, targets)

    summary.added = len(concepts) - len(summary.skipped)
    index.set_sync_timestamp(time.time())
    index.set_model_info(config.embedding_model, 384)
    summary.total_indexed = index.concept_count()

    return summary
