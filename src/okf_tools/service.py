"""Service layer: orchestrates multi-step workflows across modules."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from .bundle import (
    Concept,
    format_concept,
    generate_slug,
    parse_concept,
    remove_from_index_file,
    resolve_unique_path,
    update_index_file,
    validate_frontmatter,
    walk_concepts,
    write_concept,
)
from .config import OkfConfig, get_defaults, load_config
from .errors import (
    BundleAlreadyInitialisedError,
    ConceptNotFoundError,
    ValidationError,
)
from .graph import LinkGraph, extract_links
from .search import SearchResult, VectorIndex, embed_text
from .skills import SkillPack, discover_skills
from .sync import SyncSummary, full_reindex, incremental_reindex
from .validation import LintReport, lint_bundle as _lint_bundle


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
    target_dir = config.bundle_path
    if input_data.get("path"):
        target_dir = config.bundle_path / input_data["path"]
        target_dir.mkdir(parents=True, exist_ok=True)

    # Generate slug and resolve unique path
    slug = generate_slug(input_data["title"])
    file_path = resolve_unique_path(target_dir, slug)
    rel_path = file_path.relative_to(config.bundle_path)
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
    write_concept(concept, config.bundle_path)

    # Update index.md
    update_index_file(file_path.parent, concept_id, input_data["title"])

    # Embed and index
    _embed_and_index(config, concept)

    # Git add
    if config.auto_git_add:
        _git_add(config.bundle_path, file_path)

    return concept_id


def update_concept(config: OkfConfig, concept_id: str, updates: Dict[str, Any]) -> str:
    """Full update workflow. Returns concept_id."""
    file_path = _resolve_concept_path(config, concept_id)
    concept = parse_concept(file_path, config.bundle_path)

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
    write_concept(concept, config.bundle_path)

    # Update index if title changed
    if concept.title != old_title and concept.title:
        update_index_file(file_path.parent, concept_id, concept.title)

    # Re-embed
    _embed_and_index(config, concept)

    # Git add
    if config.auto_git_add:
        _git_add(config.bundle_path, file_path)

    return concept_id


def delete_concept(config: OkfConfig, concept_id: str) -> None:
    """Full delete workflow."""
    file_path = _resolve_concept_path(config, concept_id)

    # Remove file
    file_path.unlink()

    # Update index.md
    remove_from_index_file(file_path.parent, concept_id)

    # Remove from vector index and graph
    index, graph = _open_index_and_graph(config)
    try:
        index.delete(concept_id)
        graph.remove_concept(concept_id)
    finally:
        index.close()
        graph.close()

    # Git add deletion
    if config.auto_git_add:
        _git_add(config.bundle_path, file_path)


def fetch_concepts(
    config: OkfConfig,
    query: str,
    top_n: Optional[int] = None,
    threshold: Optional[float] = None,
    type_filter: Optional[str] = None,
    tags_filter: Optional[List[str]] = None,
) -> List[SearchResult]:
    """Semantic search workflow."""
    index, _ = _open_index_and_graph(config)
    try:
        query_embedding = embed_text(query, config.embedding_model)
        n = top_n or config.default_top_n
        t = threshold if threshold is not None else 0.0
        results = index.search(query_embedding, n * 3, t)  # Over-fetch for filtering
    finally:
        index.close()

    # Apply metadata filters
    if type_filter:
        results = [r for r in results if _matches_type(config, r.concept_id, type_filter)]
    if tags_filter:
        results = [r for r in results if _matches_tags(config, r.concept_id, tags_filter)]

    return results[: (top_n or config.default_top_n)]


def list_concepts(
    config: OkfConfig,
    type_filter: Optional[str] = None,
    tags_filter: Optional[List[str]] = None,
    since: Optional[str] = None,
    limit: Optional[int] = None,
    path_filter: Optional[str] = None,
) -> List[Concept]:
    """Filtered concept listing."""
    concepts = walk_concepts(config.bundle_path)

    if path_filter:
        filter_path = (config.bundle_path / path_filter).resolve()
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
            if c.timestamp and c.timestamp >= since
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


def get_links(
    config: OkfConfig, concept_id: str, direction: str = "both", depth: int = 1
) -> Dict[str, List[str]]:
    """Graph traversal. Returns inbound/outbound concept_ids."""
    _resolve_concept_path(config, concept_id)  # Verify exists

    _, graph = _open_index_and_graph(config)
    try:
        if depth > 1:
            neighbors = graph.bfs_neighborhood(concept_id, depth, direction)
            return {"neighborhood": neighbors}

        result: Dict[str, List[str]] = {}
        if direction in ("in", "both"):
            result["inbound"] = graph.get_inlinks(concept_id)
        if direction in ("out", "both"):
            result["outbound"] = graph.get_outlinks(concept_id)
        return result
    finally:
        graph.close()


def reindex(config: OkfConfig, full: bool = False, lint: bool = False) -> Dict[str, Any]:
    """Index rebuild. Returns summary dict, optionally with lint results."""
    index, graph = _open_index_and_graph(config)
    try:
        if full or index.get_sync_timestamp() is None:
            summary = full_reindex(config.bundle_path, index, graph, config)
        else:
            summary = incremental_reindex(config.bundle_path, index, graph, config)
    finally:
        index.close()
        graph.close()

    result: Dict[str, Any] = {
        "added": summary.added,
        "updated": summary.updated,
        "removed": summary.removed,
        "total_indexed": summary.total_indexed,
        "skipped": summary.skipped,
    }

    if lint:
        lint_report = _lint_bundle(config.bundle_path, config)
        result["lint"] = {
            "errors": lint_report.errors,
            "warnings": lint_report.warnings,
            "diagnostics": [
                {"file": d.file, "rule": d.rule, "severity": d.severity, "message": d.message}
                for d in lint_report.diagnostics
            ],
        }

    return result


def get_stats(config: OkfConfig) -> Dict[str, Any]:
    """Bundle health statistics."""
    concepts = walk_concepts(config.bundle_path)
    concept_ids = {c.concept_id for c in concepts}

    # Type and tag distributions
    type_dist: Dict[str, int] = {}
    tag_dist: Dict[str, int] = {}
    for c in concepts:
        t = c.frontmatter.get("type", "")
        type_dist[t] = type_dist.get(t, 0) + 1
        for tag in c.tags:
            tag_dist[tag] = tag_dist.get(tag, 0) + 1

    # Graph stats
    _, graph = _open_index_and_graph(config)
    try:
        graph_stats = graph.get_stats(len(concepts))
        orphans = graph.get_orphans(concept_ids)
    finally:
        graph.close()

    # Index metadata
    index, _ = _open_index_and_graph(config)
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
        "average_links_per_concept": graph_stats["average_links_per_concept"],
        "orphan_count": len(orphans),
        "last_reindex_timestamp": last_sync,
        "pending_reembedding_count": max(0, pending),
    }


def list_skills(config: OkfConfig) -> List[SkillPack]:
    """Discover and return all skill packs."""
    # Bundled skill is shipped with the package
    bundled = Path(__file__).parent.parent.parent / "skills" / "core-knowledge.md"
    return discover_skills(config.skills_paths, bundled)


def lint_bundle(
    config: OkfConfig,
    path_filter: Optional[str] = None,
    rule_filter: Optional[str] = None,
) -> LintReport:
    """Run bundle validation."""
    return _lint_bundle(config.bundle_path, config, path_filter, rule_filter)


# --- Private helpers ---


def _resolve_concept_path(config: OkfConfig, concept_id: str) -> Path:
    """Resolve concept_id to file path, raising ConceptNotFoundError if missing."""
    file_path = config.bundle_path / (concept_id + ".md")
    if not file_path.exists():
        raise ConceptNotFoundError(concept_id)
    return file_path


def _open_index_and_graph(config: OkfConfig):
    """Open the sidecar database for both vector index and graph."""
    db_path = config.bundle_path / config.index_path / "okf.db"
    index = VectorIndex(db_path)
    graph = LinkGraph(db_path)
    return index, graph


def _embed_and_index(config: OkfConfig, concept: Concept) -> None:
    """Embed concept body and upsert into vector index + graph."""
    index, graph = _open_index_and_graph(config)
    try:
        embedding = embed_text(concept.body, config.embedding_model)
        metadata = {
            "title": concept.title,
            "type": concept.type,
            "tags": concept.tags,
            "mtime": concept.file_path.stat().st_mtime,
            "snippet": concept.body[:200],
        }
        index.upsert(concept.concept_id, embedding, metadata)
        targets = extract_links(concept, config.bundle_path)
        graph.set_links(concept.concept_id, targets)
    finally:
        index.close()
        graph.close()


def _check_duplicates(config: OkfConfig, content: str, force: bool) -> None:
    """Check for similar existing concepts. Raises ValidationError if found and not forced."""
    index, _ = _open_index_and_graph(config)
    try:
        embedding = embed_text(content, config.embedding_model)
        results = index.search(embedding, 5, config.similarity_threshold)
    finally:
        index.close()

    if results and not force:
        dups = "; ".join(f"{r.concept_id} (score={r.score})" for r in results)
        raise ValidationError([f"Similar concepts found: {dups}"])


def _matches_type(config: OkfConfig, concept_id: str, type_filter: str) -> bool:
    """Check if a concept matches a type filter."""
    index, _ = _open_index_and_graph(config)
    try:
        meta = index.get_metadata(concept_id)
        return meta is not None and meta.get("type") == type_filter
    finally:
        index.close()


def _matches_tags(config: OkfConfig, concept_id: str, tags_filter: List[str]) -> bool:
    """Check if a concept matches a tags filter."""
    index, _ = _open_index_and_graph(config)
    try:
        meta = index.get_metadata(concept_id)
        if meta is None:
            return False
        concept_tags = meta.get("tags", [])
        return bool(set(concept_tags) & set(tags_filter))
    finally:
        index.close()


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
