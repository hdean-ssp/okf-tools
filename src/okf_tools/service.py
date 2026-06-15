"""Service layer: orchestrates multi-step workflows across modules.

Supports multi-bundle operation — commit/update/delete route to a target
bundle, while fetch/list aggregate across all configured bundles.
"""

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
from .config import BundleRef, OkfConfig, get_defaults, load_config
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


def commit_concept(config: OkfConfig, input_data: Dict[str, Any], bundle_name: Optional[str] = None) -> str:
    """Full commit workflow. Returns concept_id.

    Routes the write to the specified bundle, or the default bundle.
    """
    # Resolve target bundle
    bundle = config.get_writable_bundle(bundle_name)
    bundle_path = bundle.path

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

    # Check duplicates if requested (search across all bundles)
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
    _embed_and_index_for_bundle(config, bundle, concept)

    # Git add
    if config.auto_git_add:
        _git_add(bundle_path, file_path)

    return concept_id


def update_concept(config: OkfConfig, concept_id: str, updates: Dict[str, Any], bundle_name: Optional[str] = None) -> str:
    """Full update workflow. Returns concept_id.

    Routes the update to the specified bundle, or searches all bundles
    to find the concept.
    """
    bundle, file_path = _resolve_concept_in_bundles(config, concept_id, bundle_name)
    bundle_path = bundle.path

    # Verify writable
    if not bundle.writable:
        from .errors import ConfigError
        raise ConfigError("bundles", f"Bundle '{bundle.name}' is read-only")

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
    _embed_and_index_for_bundle(config, bundle, concept)

    # Git add
    if config.auto_git_add:
        _git_add(bundle_path, file_path)

    return concept_id


def delete_concept(config: OkfConfig, concept_id: str, bundle_name: Optional[str] = None) -> None:
    """Full delete workflow.

    Finds the concept in the specified bundle (or searches all bundles).
    """
    bundle, file_path = _resolve_concept_in_bundles(config, concept_id, bundle_name)
    bundle_path = bundle.path

    # Verify writable
    if not bundle.writable:
        from .errors import ConfigError
        raise ConfigError("bundles", f"Bundle '{bundle.name}' is read-only")

    # Remove file
    file_path.unlink()

    # Update index.md
    remove_from_index_file(file_path.parent, concept_id)

    # Remove from vector index and graph
    index, graph = _open_index_and_graph_for_bundle(bundle)
    try:
        index.delete(concept_id)
        graph.remove_concept(concept_id)
    finally:
        index.close()
        graph.close()

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
    bundle_name: Optional[str] = None,
) -> List[SearchResult]:
    """Semantic search workflow — aggregates across all bundles.

    If bundle_name is specified, searches only that bundle.
    Otherwise searches all configured bundles and merges results by score.
    """
    n = top_n or config.default_top_n
    t = threshold if threshold is not None else 0.0

    # Determine which bundles to search
    if bundle_name:
        bundle = config.get_bundle(bundle_name)
        if bundle is None:
            from .errors import ConfigError
            raise ConfigError(
                "bundles",
                f"Bundle '{bundle_name}' not found. "
                f"Available: {', '.join(b.name for b in config.bundles)}",
            )
        bundles_to_search = [bundle]
    else:
        bundles_to_search = config.bundles

    # Collect results from all bundles
    all_results: List[SearchResult] = []

    for bundle in bundles_to_search:
        if not bundle.index_db_path.exists():
            continue

        index = VectorIndex(bundle.index_db_path)
        try:
            if mode == "keyword":
                results = index.search_keyword(query, n * 3)
            else:
                query_embedding = embed_text(query, config.embedding_model)
                results = index.search(
                    query_embedding, n * 3, t, query=query, mode=mode
                )
        finally:
            index.close()

        # Tag each result with its source bundle
        for r in results:
            r.bundle = bundle.name
        all_results.extend(results)

    # Apply metadata filters (check against each bundle's index)
    if type_filter:
        all_results = [r for r in all_results if _matches_type_in_bundle(config, r) and
                       _result_type_matches(config, r, type_filter)]
    if tags_filter:
        all_results = [r for r in all_results if _matches_tags_in_bundle(config, r, tags_filter)]

    # Sort by score descending, deduplicate by concept_id (keep highest score)
    all_results.sort(key=lambda r: r.score, reverse=True)
    seen_ids: set = set()
    deduplicated: List[SearchResult] = []
    for r in all_results:
        key = f"{r.bundle}:{r.concept_id}"
        if key not in seen_ids:
            seen_ids.add(key)
            deduplicated.append(r)

    return deduplicated[:n]


def list_concepts(
    config: OkfConfig,
    type_filter: Optional[str] = None,
    tags_filter: Optional[List[str]] = None,
    since: Optional[str] = None,
    limit: Optional[int] = None,
    path_filter: Optional[str] = None,
    bundle_name: Optional[str] = None,
) -> List[Concept]:
    """Filtered concept listing — aggregates across bundles.

    If bundle_name is specified, lists only that bundle's concepts.
    """
    if bundle_name:
        bundle = config.get_bundle(bundle_name)
        if bundle is None:
            from .errors import ConfigError
            raise ConfigError(
                "bundles",
                f"Bundle '{bundle_name}' not found.",
            )
        bundles_to_list = [bundle]
    else:
        bundles_to_list = config.bundles

    all_concepts: List[Concept] = []
    for bundle in bundles_to_list:
        if not bundle.path.exists():
            continue
        concepts = walk_concepts(bundle.path)

        # Tag each concept with its source bundle
        for c in concepts:
            c.bundle = bundle.name

        if path_filter:
            filter_path = (bundle.path / path_filter).resolve()
            concepts = [c for c in concepts if c.file_path.is_relative_to(filter_path)]

        all_concepts.extend(concepts)

    if type_filter:
        all_concepts = [c for c in all_concepts if c.frontmatter.get("type") == type_filter]

    if tags_filter:
        all_concepts = [
            c for c in all_concepts
            if set(c.tags) & set(tags_filter)
        ]

    if since:
        all_concepts = [
            c for c in all_concepts
            if _concept_matches_since(c, since)
        ]

    # Sort by concept_id
    all_concepts.sort(key=lambda c: c.concept_id)

    if limit:
        all_concepts = all_concepts[:limit]

    return all_concepts


def show_concept(config: OkfConfig, concept_id: str) -> Concept:
    """Load and return a single concept. Searches all bundles."""
    _, file_path = _resolve_concept_in_bundles(config, concept_id)
    # Determine which bundle this is in to get the correct bundle_path
    for bundle in config.bundles:
        if file_path.is_relative_to(bundle.path):
            return parse_concept(file_path, bundle.path)
    # Fallback to legacy
    return parse_concept(file_path, config.bundle_path)


def get_links(
    config: OkfConfig, concept_id: str, direction: str = "both", depth: int = 1
) -> Dict[str, List[str]]:
    """Graph traversal. Returns inbound/outbound concept_ids."""
    bundle, _ = _resolve_concept_in_bundles(config, concept_id)

    _, graph = _open_index_and_graph_for_bundle(bundle)
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


def reindex(
    config: OkfConfig,
    full: bool = False,
    lint: bool = False,
    bundle_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Index rebuild. Returns summary dict, optionally with lint results.

    If bundle_name is specified, reindexes only that bundle.
    Otherwise reindexes the default bundle.
    """
    if bundle_name:
        bundle = config.get_bundle(bundle_name)
        if bundle is None:
            from .errors import ConfigError
            raise ConfigError(
                "bundles",
                f"Bundle '{bundle_name}' not found. "
                f"Available: {', '.join(b.name for b in config.bundles)}",
            )
        index, graph = _open_index_and_graph_for_bundle(bundle)
        bundle_path = bundle.path
    else:
        index, graph = _open_index_and_graph(config)
        bundle_path = config.bundle_path

    try:
        if full or index.get_sync_timestamp() is None:
            summary = full_reindex(bundle_path, index, graph, config)
        else:
            summary = incremental_reindex(bundle_path, index, graph, config)
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
        lint_report = _lint_bundle(bundle_path, config)
        result["lint"] = {
            "errors": lint_report.errors,
            "warnings": lint_report.warnings,
            "diagnostics": [
                {"file": d.file, "rule": d.rule, "severity": d.severity, "message": d.message}
                for d in lint_report.diagnostics
            ],
        }

    return result


def get_stats(config: OkfConfig, bundle_name: Optional[str] = None) -> Dict[str, Any]:
    """Bundle health statistics.

    If bundle_name is specified, shows stats for that bundle only.
    Otherwise shows stats for the default bundle.
    """
    if bundle_name:
        bundle = config.get_bundle(bundle_name)
        if bundle is None:
            from .errors import ConfigError
            raise ConfigError(
                "bundles",
                f"Bundle '{bundle_name}' not found. "
                f"Available: {', '.join(b.name for b in config.bundles)}",
            )
        bundle_path = bundle.path
    else:
        bundle_path = config.bundle_path

    concepts = walk_concepts(bundle_path)
    concept_ids = {c.concept_id for c in concepts}

    # Type and tag distributions
    type_dist: Dict[str, int] = {}
    tag_dist: Dict[str, int] = {}
    for c in concepts:
        t = c.frontmatter.get("type", "")
        type_dist[t] = type_dist.get(t, 0) + 1
        for tag in c.tags:
            tag_dist[tag] = tag_dist.get(tag, 0) + 1

    # Open the correct bundle's index/graph
    if bundle_name:
        index, graph = _open_index_and_graph_for_bundle(
            config.get_bundle(bundle_name)
        )
    else:
        index, graph = _open_index_and_graph(config)

    try:
        graph_stats = graph.get_stats(len(concepts))
        orphans = graph.get_orphans(concept_ids)
        last_sync = index.get_sync_timestamp()
        indexed_count = index.concept_count()
    finally:
        index.close()
        graph.close()

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
    """Resolve concept_id to file path in the default bundle.

    Raises ConceptNotFoundError if missing. Legacy helper for backward compat.
    """
    file_path = config.bundle_path / (concept_id + ".md")
    if not file_path.exists():
        raise ConceptNotFoundError(concept_id)
    return file_path


def _resolve_concept_in_bundles(
    config: OkfConfig, concept_id: str, bundle_name: Optional[str] = None
) -> "tuple[BundleRef, Path]":
    """Find a concept across bundles. Returns (bundle, file_path).

    If bundle_name is specified, look only in that bundle.
    Otherwise search all bundles in order.
    """
    if bundle_name:
        bundle = config.get_bundle(bundle_name)
        if bundle is None:
            from .errors import ConfigError
            raise ConfigError(
                "bundles",
                f"Bundle '{bundle_name}' not found.",
            )
        file_path = bundle.path / (concept_id + ".md")
        if not file_path.exists():
            raise ConceptNotFoundError(concept_id)
        return bundle, file_path

    # Search all bundles
    for bundle in config.bundles:
        file_path = bundle.path / (concept_id + ".md")
        if file_path.exists():
            return bundle, file_path

    raise ConceptNotFoundError(concept_id)


def _open_index_and_graph(config: OkfConfig):
    """Open the sidecar database for the default bundle. Legacy helper."""
    db_path = config.bundle_path / config.index_path / "okf.db"
    index = VectorIndex(db_path)
    graph = LinkGraph(db_path)
    return index, graph


def _open_index_and_graph_for_bundle(bundle: BundleRef):
    """Open the sidecar database for a specific bundle."""
    db_path = bundle.index_db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    index = VectorIndex(db_path)
    graph = LinkGraph(db_path)
    return index, graph


def _embed_and_index(config: OkfConfig, concept: Concept) -> None:
    """Embed concept body and upsert into the default bundle's index.

    Legacy helper — delegates to _embed_and_index_for_bundle.
    """
    default_bundle = config.get_default_bundle()
    if default_bundle:
        _embed_and_index_for_bundle(config, default_bundle, concept)


def _embed_and_index_for_bundle(config: OkfConfig, bundle: BundleRef, concept: Concept) -> None:
    """Embed concept body and upsert into a specific bundle's index + graph."""
    index, graph = _open_index_and_graph_for_bundle(bundle)
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
        targets = extract_links(concept, bundle.path)
        graph.set_links(concept.concept_id, targets)
    finally:
        index.close()
        graph.close()


def _concept_matches_since(concept: Concept, since: str) -> None:
    """Check if a concept was created/modified on or after the given date.

    Uses frontmatter timestamp if available, otherwise falls back to file mtime.
    """
    from datetime import datetime

    # Parse the since date
    try:
        since_dt = datetime.strptime(since, "%Y-%m-%d")
    except ValueError:
        try:
            since_dt = datetime.fromisoformat(since)
        except ValueError:
            return False

    # Check frontmatter timestamp first
    if concept.timestamp:
        ts_str = concept.timestamp
        if isinstance(ts_str, datetime):
            return ts_str >= since_dt
        try:
            concept_dt = datetime.strptime(ts_str, "%Y-%m-%d")
            return concept_dt >= since_dt
        except ValueError:
            try:
                concept_dt = datetime.fromisoformat(ts_str)
                return concept_dt >= since_dt
            except ValueError:
                pass

    # Fall back to file modification time
    if concept.file_path and concept.file_path.exists():
        mtime = concept.file_path.stat().st_mtime
        file_dt = datetime.fromtimestamp(mtime)
        return file_dt >= since_dt

    return False


def _check_duplicates(config: OkfConfig, content: str, force: bool) -> None:
    """Check for similar existing concepts across all bundles.

    Raises ValidationError if found and not forced.
    """
    embedding = embed_text(content, config.embedding_model)
    all_dups: List[str] = []

    for bundle in config.bundles:
        if not bundle.index_db_path.exists():
            continue
        index = VectorIndex(bundle.index_db_path)
        try:
            results = index.search(embedding, 5, config.similarity_threshold)
            for r in results:
                all_dups.append(f"{bundle.name}:{r.concept_id} (score={r.score})")
        finally:
            index.close()

    if all_dups and not force:
        raise ValidationError([f"Similar concepts found: {'; '.join(all_dups)}"])


def _result_type_matches(config: OkfConfig, result: SearchResult, type_filter: str) -> bool:
    """Check if a search result's concept matches a type filter."""
    if not result.bundle:
        return False
    bundle = config.get_bundle(result.bundle)
    if not bundle:
        return False
    index = VectorIndex(bundle.index_db_path)
    try:
        meta = index.get_metadata(result.concept_id)
        return meta is not None and meta.get("type") == type_filter
    finally:
        index.close()


def _matches_type_in_bundle(config: OkfConfig, result: SearchResult) -> bool:
    """Verify a result's bundle exists (used as pre-filter)."""
    return result.bundle is not None and config.get_bundle(result.bundle) is not None


def _matches_tags_in_bundle(config: OkfConfig, result: SearchResult, tags_filter: List[str]) -> bool:
    """Check if a search result's concept matches tags filter."""
    if not result.bundle:
        return False
    bundle = config.get_bundle(result.bundle)
    if not bundle:
        return False
    index = VectorIndex(bundle.index_db_path)
    try:
        meta = index.get_metadata(result.concept_id)
        if meta is None:
            return False
        concept_tags = meta.get("tags", [])
        return bool(set(concept_tags) & set(tags_filter))
    finally:
        index.close()


def _matches_type(config: OkfConfig, concept_id: str, type_filter: str) -> bool:
    """Check if a concept matches a type filter. Legacy helper."""
    index, _ = _open_index_and_graph(config)
    try:
        meta = index.get_metadata(concept_id)
        return meta is not None and meta.get("type") == type_filter
    finally:
        index.close()


def _matches_tags(config: OkfConfig, concept_id: str, tags_filter: List[str]) -> bool:
    """Check if a concept matches a tags filter. Legacy helper."""
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
