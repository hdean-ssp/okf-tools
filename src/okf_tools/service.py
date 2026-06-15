"""Service layer: orchestrates multi-step workflows across modules.

Core-only: single bundle, no graph, no lint, no skills.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from .bundle import (
    Concept,
    generate_slug,
    parse_concept,
    remove_from_index_file,
    resolve_unique_path,
    update_index_file,
    validate_frontmatter,
    walk_concepts,
    write_concept,
)
from .config import OkfConfig, get_defaults
from .errors import (
    BundleAlreadyInitialisedError,
    ConceptNotFoundError,
    ValidationError,
)
from .search import SearchResult, VectorIndex, embed_text
from .sync import SyncSummary, full_reindex, incremental_reindex


def init_bundle(path: Path) -> None:
    """Create .okf/config.json, root index.md, update .gitignore."""
    okf_dir = path / ".okf"
    config_path = okf_dir / "config.json"

    if config_path.exists():
        raise BundleAlreadyInitialisedError()

    # Create .okf/ and config
    okf_dir.mkdir(parents=True, exist_ok=True)
    defaults = get_defaults()
    config_path.write_text(
        json.dumps(defaults, indent=2) + "\n", encoding="utf-8"
    )

    # Create root index.md if missing
    index_path = path / "index.md"
    if not index_path.exists():
        heading = path.resolve().name
        index_path.write_text(f"# {heading}\n", encoding="utf-8")

    # Update .gitignore if git repo
    if (path / ".git").is_dir():
        gitignore = path / ".gitignore"
        entry = ".okf/index/"
        if gitignore.exists():
            content = gitignore.read_text(encoding="utf-8")
            if entry not in content:
                if not content.endswith("\n"):
                    content += "\n"
                content += entry + "\n"
                gitignore.write_text(content, encoding="utf-8")
        else:
            gitignore.write_text(entry + "\n", encoding="utf-8")


def commit_concept(config: OkfConfig, input_data: Dict[str, Any]) -> str:
    """Full commit workflow. Returns concept_id."""
    bundle_path = config.bundle_path

    # Validate required fields
    missing = [f for f in ("title", "content", "type") if not input_data.get(f)]
    if missing:
        raise ValidationError([f"Missing required field: {f}" for f in missing])

    # Build frontmatter
    fm: Dict[str, Any] = {"type": input_data["type"]}
    if input_data.get("title"):
        fm["title"] = input_data["title"]
    if input_data.get("tags"):
        fm["tags"] = input_data["tags"]
    if input_data.get("timestamp"):
        fm["timestamp"] = input_data["timestamp"]
    if input_data.get("description"):
        fm["description"] = input_data["description"]

    # Validate frontmatter
    errors = validate_frontmatter(fm)
    if errors:
        raise ValidationError(errors)

    # Determine target directory
    target_dir = bundle_path
    if input_data.get("path"):
        target_dir = bundle_path / input_data["path"]
        target_dir.mkdir(parents=True, exist_ok=True)

    # Generate slug and resolve unique path
    slug = generate_slug(input_data["title"])
    file_path = resolve_unique_path(target_dir, slug)
    rel_path = file_path.relative_to(bundle_path)
    concept_id = str(rel_path.with_suffix(""))

    # Check duplicates if requested
    if input_data.get("check_duplicates"):
        _check_duplicates(config, input_data["content"], input_data.get("force", False))

    # Create concept
    concept = Concept(
        concept_id=concept_id,
        frontmatter=fm,
        body=input_data["content"],
        file_path=file_path,
    )

    # Write file
    write_concept(concept, bundle_path)

    # Update index.md
    update_index_file(file_path.parent, concept_id, input_data["title"])

    # Embed and index
    _embed_and_index(config, concept)

    # Git add
    if config.auto_git_add:
        _git_add(bundle_path, file_path)

    return concept_id


def update_concept(config: OkfConfig, concept_id: str, updates: Dict[str, Any]) -> str:
    """Full update workflow. Returns concept_id."""
    bundle_path = config.bundle_path
    file_path = _resolve_concept_path(config, concept_id)
    concept = parse_concept(file_path, bundle_path)

    # Merge updates
    old_title = concept.title
    if "title" in updates:
        concept.frontmatter["title"] = updates["title"]
    if "type" in updates:
        concept.frontmatter["type"] = updates["type"]
    if "tags" in updates:
        concept.frontmatter["tags"] = updates["tags"]
    if "content" in updates:
        concept.body = updates["content"]

    # Validate
    errors = validate_frontmatter(concept.frontmatter)
    if errors:
        raise ValidationError(errors)

    # Write
    write_concept(concept, bundle_path)

    # Update index if title changed
    if concept.title != old_title and concept.title:
        update_index_file(file_path.parent, concept_id, concept.title)

    # Re-embed
    _embed_and_index(config, concept)

    # Git add
    if config.auto_git_add:
        _git_add(bundle_path, file_path)

    return concept_id


def delete_concept(config: OkfConfig, concept_id: str) -> None:
    """Full delete workflow."""
    bundle_path = config.bundle_path
    file_path = _resolve_concept_path(config, concept_id)

    # Remove file
    file_path.unlink()

    # Update index.md
    remove_from_index_file(file_path.parent, concept_id)

    # Remove from vector index
    index = VectorIndex(config.index_db_path)
    try:
        index.delete(concept_id)
    finally:
        index.close()

    # Git add deletion
    if config.auto_git_add:
        _git_add(bundle_path, file_path)


def fetch_concepts(
    config: OkfConfig,
    query: str,
    top_n: Optional[int] = None,
    threshold: Optional[float] = None,
    type_filter: Optional[str] = None,
    tags_filter: Optional[List[str]] = None,
    mode: str = "hybrid",
) -> List[SearchResult]:
    """Semantic search workflow."""
    n = top_n or config.default_top_n
    t = threshold if threshold is not None else 0.0

    if not config.index_db_path.exists():
        return []

    index = VectorIndex(config.index_db_path)
    try:
        if mode == "keyword":
            results = index.search_keyword(query, n * 3)
        else:
            query_embedding = embed_text(query, config.embedding_model)
            results = index.search(
                query_embedding, n * 3, t, query=query, mode=mode
            )

        # Apply metadata filters
        if type_filter:
            results = [
                r for r in results
                if _matches_type(index, r.concept_id, type_filter)
            ]
        if tags_filter:
            results = [
                r for r in results
                if _matches_tags(index, r.concept_id, tags_filter)
            ]
    finally:
        index.close()

    return results[:n]


def list_concepts(
    config: OkfConfig,
    type_filter: Optional[str] = None,
    tags_filter: Optional[List[str]] = None,
    since: Optional[str] = None,
    limit: Optional[int] = None,
    path_filter: Optional[str] = None,
) -> List[Concept]:
    """Filtered concept listing."""
    bundle_path = config.bundle_path
    concepts = walk_concepts(bundle_path)

    if path_filter:
        filter_path = (bundle_path / path_filter).resolve()
        concepts = [c for c in concepts if c.file_path.is_relative_to(filter_path)]

    if type_filter:
        concepts = [c for c in concepts if c.frontmatter.get("type") == type_filter]

    if tags_filter:
        concepts = [
            c for c in concepts
            if set(c.tags) & set(tags_filter)
        ]

    if since:
        concepts = [
            c for c in concepts
            if _concept_matches_since(c, since)
        ]

    # Sort by concept_id
    concepts.sort(key=lambda c: c.concept_id)

    if limit:
        concepts = concepts[:limit]

    return concepts


def show_concept(config: OkfConfig, concept_id: str) -> Concept:
    """Load and return a single concept."""
    file_path = _resolve_concept_path(config, concept_id)
    return parse_concept(file_path, config.bundle_path)


def reindex(config: OkfConfig, full: bool = False) -> Dict[str, Any]:
    """Index rebuild. Returns summary dict."""
    index = VectorIndex(config.index_db_path)
    try:
        if full or index.get_sync_timestamp() is None:
            summary = full_reindex(config.bundle_path, index, config)
        else:
            summary = incremental_reindex(config.bundle_path, index, config)
    finally:
        index.close()

    return {
        "added": summary.added,
        "updated": summary.updated,
        "removed": summary.removed,
        "total_indexed": summary.total_indexed,
        "skipped": summary.skipped,
    }


def get_stats(config: OkfConfig) -> Dict[str, Any]:
    """Bundle health statistics."""
    bundle_path = config.bundle_path
    concepts = walk_concepts(bundle_path)

    # Type and tag distributions
    type_dist: Dict[str, int] = {}
    tag_dist: Dict[str, int] = {}
    for c in concepts:
        t = c.frontmatter.get("type", "")
        type_dist[t] = type_dist.get(t, 0) + 1
        for tag in c.tags:
            tag_dist[tag] = tag_dist.get(tag, 0) + 1

    index = VectorIndex(config.index_db_path)
    try:
        last_sync = index.get_sync_timestamp()
        indexed_count = index.concept_count()
    finally:
        index.close()

    pending = len(concepts) - indexed_count

    return {
        "concept_count": len(concepts),
        "type_distribution": type_dist,
        "tag_distribution": tag_dist,
        "last_reindex_timestamp": last_sync,
        "pending_reembedding_count": max(0, pending),
    }


# --- Private helpers ---


def _resolve_concept_path(config: OkfConfig, concept_id: str) -> Path:
    """Resolve concept_id to file path. Raises ConceptNotFoundError if missing."""
    file_path = config.bundle_path / (concept_id + ".md")
    if not file_path.exists():
        raise ConceptNotFoundError(concept_id)
    return file_path


def _embed_and_index(config: OkfConfig, concept: Concept) -> None:
    """Embed concept body and upsert into the index."""
    index = VectorIndex(config.index_db_path)
    try:
        embedding = embed_text(concept.body, config.embedding_model)
        metadata = {
            "title": concept.title,
            "type": concept.type,
            "tags": concept.tags,
            "mtime": concept.file_path.stat().st_mtime,
            "snippet": concept.body[:200],
            "body": concept.body,
        }
        index.upsert(concept.concept_id, embedding, metadata)
    finally:
        index.close()


def _concept_matches_since(concept: Concept, since: str) -> bool:
    """Check if a concept was created/modified on or after the given date."""
    from datetime import date, datetime

    try:
        since_dt = datetime.strptime(since, "%Y-%m-%d")
    except ValueError:
        try:
            since_dt = datetime.fromisoformat(since)
        except ValueError:
            return False

    since_date = since_dt.date()

    if concept.timestamp:
        ts_val = concept.timestamp
        if isinstance(ts_val, datetime):
            return ts_val.date() >= since_date
        if isinstance(ts_val, date):
            return ts_val >= since_date
        if isinstance(ts_val, str):
            try:
                concept_dt = datetime.strptime(ts_val, "%Y-%m-%d")
                return concept_dt.date() >= since_date
            except ValueError:
                try:
                    concept_dt = datetime.fromisoformat(ts_val)
                    return concept_dt.date() >= since_date
                except ValueError:
                    pass

    if concept.file_path and concept.file_path.exists():
        mtime = concept.file_path.stat().st_mtime
        file_date = datetime.fromtimestamp(mtime).date()
        return file_date >= since_date

    return False


def _check_duplicates(config: OkfConfig, content: str, force: bool) -> None:
    """Check for similar existing concepts.

    Raises ValidationError if found and not forced.
    """
    if not config.index_db_path.exists():
        return

    embedding = embed_text(content, config.embedding_model)
    index = VectorIndex(config.index_db_path)
    try:
        results = index.search(embedding, 5, config.similarity_threshold)
        if results and not force:
            dup_list = "\n  ".join(
                f"{r.concept_id} \"{r.title}\" (score={r.score}) — {r.snippet[:80]}..."
                for r in results
            )
            raise ValidationError([
                f"Similar concepts already exist:\n  {dup_list}\n"
                f"Use --force to commit anyway."
            ])
    finally:
        index.close()


def _matches_type(index: VectorIndex, concept_id: str, type_filter: str) -> bool:
    """Check if a concept matches a type filter."""
    meta = index.get_metadata(concept_id)
    return meta is not None and meta.get("type") == type_filter


def _matches_tags(index: VectorIndex, concept_id: str, tags_filter: List[str]) -> bool:
    """Check if a concept matches a tags filter."""
    meta = index.get_metadata(concept_id)
    if meta is None:
        return False
    concept_tags = meta.get("tags", [])
    return bool(set(concept_tags) & set(tags_filter))


def _git_add(bundle_root: Path, file_path: Path) -> None:
    """Run git add on a file. Silently fails if not in a git repo."""
    try:
        subprocess.run(
            ["git", "add", str(file_path)],
            cwd=str(bundle_root),
            capture_output=True,
            timeout=5,
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
