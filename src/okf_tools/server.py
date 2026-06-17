"""MCP server exposing okf-tools service functions as MCP tools.

All diagnostic output goes to stderr (never stdout — that's the JSON-RPC channel).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import List, Optional

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from . import service
from .config import OkfConfig, find_bundle_root, load_config
from .errors import (
    BundleAlreadyInitialisedError,
    ConceptNotFoundError,
    OkfError,
    ValidationError,
)

mcp = FastMCP("okf-tools")

_config: Optional[OkfConfig] = None


def _require_bundle() -> OkfConfig:
    """Return the current config or raise a ToolError if no bundle is configured.

    Tool handlers that require a configured bundle call this before
    invoking service functions.
    """
    if _config is None:
        raise ToolError(
            "No bundle configured. Use init_bundle to create one, "
            "or restart the server with --bundle-path pointing to an existing bundle."
        )
    return _config


def _handle_error(e: OkfError) -> str:
    """Map domain errors to MCP error content strings.

    Returns a human-readable message suitable for returning to the MCP client.
    """
    if isinstance(e, ValidationError):
        return "\n".join(e.errors)
    elif isinstance(e, ConceptNotFoundError):
        return f"Concept not found: {e.concept_id}"
    elif isinstance(e, BundleAlreadyInitialisedError):
        return str(e)
    else:
        return "An internal error occurred"


@mcp.tool()
def commit_concept(
    title: str,
    type: str,
    content: str,
    tags: Optional[List[str]] = None,
    path: Optional[str] = None,
    check_duplicates: bool = True,
) -> str:
    """Commit a new concept to the knowledge bundle.

    Creates a concept file with the given title, type, and content.
    Optionally checks for duplicate concepts before committing.
    """
    try:
        config = _require_bundle()
        try:
            input_data = {
                "title": title,
                "type": type,
                "content": content,
                "check_duplicates": check_duplicates,
            }
            if tags is not None:
                input_data["tags"] = tags
            if path is not None:
                input_data["path"] = path
            concept_id = service.commit_concept(config, input_data)
            return json.dumps({"concept_id": concept_id})
        except ValidationError as e:
            raise ToolError(_handle_error(e))
    except ToolError:
        raise
    except Exception:
        logging.getLogger(__name__).error("Unexpected error in commit_concept", exc_info=True)
        raise ToolError("An internal error occurred")


@mcp.tool()
def init_bundle(path: str = ".") -> str:
    """Initialize a new OKF knowledge bundle at the specified path.

    Creates .okf/config.json, a root index.md, and updates .gitignore if in a git repo.
    This is the only tool that does not require a pre-configured bundle.
    """
    global _config

    try:
        resolved = Path(path).resolve()
        if not resolved.exists() or not resolved.is_dir():
            raise ToolError(
                f"Path '{path}' does not exist or is not a directory"
            )

        try:
            service.init_bundle(resolved)
        except BundleAlreadyInitialisedError as e:
            raise ToolError(str(e))

        _config = load_config(resolved)
        return json.dumps({"path": str(resolved)})
    except ToolError:
        raise
    except Exception:
        logging.getLogger(__name__).error("Unexpected error in init_bundle", exc_info=True)
        raise ToolError("An internal error occurred")


@mcp.tool()
def update_concept(
    concept_id: str,
    title: Optional[str] = None,
    type: Optional[str] = None,
    tags: Optional[List[str]] = None,
    content: Optional[str] = None,
) -> str:
    """Update an existing concept in the bundle.

    Applies only the provided fields to the concept, leaving unspecified fields unchanged.
    Re-embeds the content and updates the vector index.
    """
    try:
        config = _require_bundle()

        updates: dict = {}
        if title is not None:
            updates["title"] = title
        if type is not None:
            updates["type"] = type
        if tags is not None:
            updates["tags"] = tags
        if content is not None:
            updates["content"] = content

        if not updates:
            raise ToolError(
                "At least one update field must be provided (title, type, tags, or content)"
            )

        try:
            service.update_concept(config, concept_id, updates)
        except ConceptNotFoundError as e:
            raise ToolError(_handle_error(e))
        except ValidationError as e:
            raise ToolError(_handle_error(e))

        return json.dumps({"concept_id": concept_id})
    except ToolError:
        raise
    except Exception:
        logging.getLogger(__name__).error("Unexpected error in update_concept", exc_info=True)
        raise ToolError("An internal error occurred")


@mcp.tool()
def delete_concept(concept_id: str) -> str:
    """Delete a concept from the bundle by its concept_id."""
    try:
        config = _require_bundle()
        try:
            service.delete_concept(config, concept_id)
            return json.dumps({"concept_id": concept_id})
        except ConceptNotFoundError as e:
            raise ToolError(_handle_error(e))
    except ToolError:
        raise
    except Exception:
        logging.getLogger(__name__).error("Unexpected error in delete_concept", exc_info=True)
        raise ToolError("An internal error occurred")


@mcp.tool()
def show_concept(concept_id: str) -> str:
    """Show the full details of a concept by its concept_id.

    Returns all frontmatter fields and the complete markdown body.
    """
    try:
        config = _require_bundle()
        try:
            concept = service.show_concept(config, concept_id)
            result = {"concept_id": concept.concept_id, **concept.frontmatter, "body": concept.body}
            return json.dumps(result)
        except ConceptNotFoundError as e:
            raise ToolError(_handle_error(e))
    except ToolError:
        raise
    except Exception:
        logging.getLogger(__name__).error("Unexpected error in show_concept", exc_info=True)
        raise ToolError("An internal error occurred")


@mcp.tool()
def reindex(full: bool = False) -> str:
    """Rebuild the vector index for the knowledge bundle.

    Performs an incremental reindex by default (only processes changed files).
    Set full=True to discard the existing index and rebuild from scratch.

    Returns a JSON summary with counts of added, updated, removed, skipped concepts
    and the total number of indexed concepts.
    """
    try:
        config = _require_bundle()
        summary = service.reindex(config, full)
        return json.dumps(summary)
    except ToolError:
        raise
    except Exception:
        logging.getLogger(__name__).error("Unexpected error in reindex", exc_info=True)
        raise ToolError("An internal error occurred")


@mcp.tool()
def fetch_concepts(
    query: str,
    top_n: int = 5,
    threshold: float = 0.0,
    type: Optional[str] = None,
    tags: Optional[List[str]] = None,
    mode: str = "hybrid",
) -> str:
    """Search the knowledge bundle using natural language queries.

    Returns a ranked list of matching concepts with scores and snippets.
    Supports hybrid (semantic + keyword), keyword-only, or semantic-only modes.
    """
    try:
        config = _require_bundle()

        if not query.strip():
            raise ToolError("A non-empty query is required")

        results = service.fetch_concepts(
            config, query, top_n, threshold, type_filter=type, tags_filter=tags, mode=mode
        )

        formatted_results = [
            {
                "concept_id": r.concept_id,
                "title": r.title,
                "score": r.score,
                "snippet": r.snippet[:200],
            }
            for r in results
        ]

        return json.dumps({"results": formatted_results})
    except ToolError:
        raise
    except Exception:
        logging.getLogger(__name__).error("Unexpected error in fetch_concepts", exc_info=True)
        raise ToolError("An internal error occurred")


@mcp.tool()
def list_concepts(
    type: Optional[str] = None,
    tags: Optional[List[str]] = None,
    since: Optional[str] = None,
    limit: int = 100,
    path: Optional[str] = None,
) -> str:
    """List concepts in the knowledge bundle with optional filters.

    Returns a filtered, sorted list of concepts. Supports filtering by type,
    tags, modification date, and path prefix.
    """
    try:
        config = _require_bundle()
        concepts = service.list_concepts(
            config,
            type_filter=type,
            tags_filter=tags,
            since=since,
            limit=limit,
            path_filter=path,
        )
        formatted = [
            {
                "concept_id": c.concept_id,
                "title": c.title,
                "type": c.frontmatter.get("type", ""),
                "tags": c.tags,
            }
            for c in concepts
        ]
        return json.dumps({"concepts": formatted})
    except ToolError:
        raise
    except Exception:
        logging.getLogger(__name__).error("Unexpected error in list_concepts", exc_info=True)
        raise ToolError("An internal error occurred")


@mcp.tool()
def get_stats() -> str:
    """Return bundle health statistics.

    Returns concept count, type/tag distributions, last reindex timestamp,
    and the number of concepts pending re-embedding.
    """
    try:
        config = _require_bundle()
        stats = service.get_stats(config)
        return json.dumps(stats)
    except ToolError:
        raise
    except Exception:
        logging.getLogger(__name__).error("Unexpected error in get_stats", exc_info=True)
        raise ToolError("An internal error occurred")


def main() -> None:
    """Entry point for the okf-mcp server.

    Parses --bundle-path, resolves configuration, configures stderr logging,
    and starts the MCP server over stdio transport.
    """
    global _config

    parser = argparse.ArgumentParser(
        description="OKF Tools MCP Server",
        prog="okf-mcp",
    )
    parser.add_argument(
        "--bundle-path",
        type=str,
        default=None,
        help="Path to the OKF bundle root directory",
    )
    args = parser.parse_args()

    # Configure logging to stderr only (stdout is the JSON-RPC channel)
    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s: %(message)s",
        stream=sys.stderr,
    )

    # Resolve bundle configuration
    if args.bundle_path is not None:
        bundle_path = Path(args.bundle_path)
        if not bundle_path.exists() or not bundle_path.is_dir():
            print(
                f"Error: --bundle-path '{args.bundle_path}' does not exist "
                "or is not a directory.",
                file=sys.stderr,
            )
            sys.exit(1)
        _config = load_config(bundle_path.resolve())
    else:
        root = find_bundle_root()
        if root is not None:
            _config = load_config(root)
        # else: _config stays None — init_bundle can be called later

    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
