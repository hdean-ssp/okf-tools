"""Click-based CLI: single `okf` entry point with subcommands.

Core-only: init, commit, fetch, show, list, update, delete, reindex, stats.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Optional

import click

from . import __version__, OKF_SPEC_VERSION
from .config import load_config
from .errors import OkfError


# --- Output helpers ---


def _detect_format(explicit: Optional[str]) -> str:
    """Determine output format: explicit > TTY detection."""
    if explicit:
        return explicit
    return "text" if sys.stdout.isatty() else "json"


def _output(ctx: click.Context, data: Any) -> None:
    """Output data in the active format."""
    fmt = ctx.obj["format"]
    if fmt == "json":
        click.echo(json.dumps(data, indent=2, default=str))
    elif fmt == "brief" and isinstance(data, list):
        if not data:
            click.echo("No matching concepts.", err=True)
            return
        for item in data:
            if isinstance(item, dict):
                click.echo(f"{item.get('concept_id', '')}\t{item.get('title', '')}")
            else:
                click.echo(str(item))
    else:
        # Text format
        if isinstance(data, dict):
            _print_dict(data)
        elif isinstance(data, list):
            if not data:
                click.echo("No matching concepts.", err=True)
                return
            for item in data:
                if isinstance(item, dict):
                    _print_dict(item)
                    click.echo()
                else:
                    click.echo(str(item))
        else:
            click.echo(str(data))


def _print_dict(d: dict) -> None:
    """Pretty-print a dict in text mode."""
    for key, value in d.items():
        if isinstance(value, dict):
            click.echo(f"{key}:")
            for k, v in value.items():
                click.echo(f"  {k}: {v}")
        elif isinstance(value, list) and len(value) > 3:
            click.echo(f"{key}: [{len(value)} items]")
        else:
            click.echo(f"{key}: {value}")


def _handle_error(ctx: click.Context, message: str, exit_code: int = 1) -> None:
    """Write error to stderr in appropriate format."""
    fmt = ctx.obj.get("format", "text")
    if fmt == "json":
        click.echo(
            json.dumps({"error": message, "exit_code": exit_code}), err=True
        )
    else:
        click.echo(f"error: {message}", err=True)
    ctx.exit(exit_code)


# --- Main group ---


@click.group()
@click.option(
    "--format", "fmt",
    type=click.Choice(["json", "text", "brief"]),
    default=None,
    help="Output format (default: text for TTY, json for pipes)",
)
@click.version_option(
    version=__version__,
    prog_name="okf-tools",
    message="%(prog)s %(version)s (targeting OKF spec v" + OKF_SPEC_VERSION + ")",
)
@click.pass_context
def okf(ctx: click.Context, fmt: Optional[str]) -> None:
    """OKF bundle tools — search, author, and navigate knowledge."""
    ctx.ensure_object(dict)
    ctx.obj["format"] = _detect_format(fmt)


# --- Commands ---


@okf.command()
@click.pass_context
def init(ctx: click.Context) -> None:
    """Initialise a new OKF bundle in the current directory."""
    from .service import init_bundle

    try:
        path = Path.cwd()
        init_bundle(path)
        _output(ctx, {"status": "ok", "message": "Bundle initialised"})
    except OkfError as e:
        _handle_error(ctx, str(e))


@okf.command()
@click.argument("query")
@click.option("--top-n", type=int, help="Number of results (default: 5)")
@click.option("--threshold", type=float, help="Minimum similarity score")
@click.option("--type", "type_filter", help="Filter by concept type")
@click.option("--tags", help="Filter by tags (comma-separated)")
@click.option(
    "--mode",
    type=click.Choice(["hybrid", "semantic", "keyword"]),
    default="hybrid",
    help="Search mode (default: hybrid)",
)
@click.option("--format", "local_format", type=click.Choice(["json", "text", "brief"]),
              default=None, help="Output format (overrides global --format)")
@click.pass_context
def fetch(
    ctx: click.Context,
    query: str,
    top_n: Optional[int],
    threshold: Optional[float],
    type_filter: Optional[str],
    tags: Optional[str],
    mode: str,
    local_format: Optional[str],
) -> None:
    """Semantic search over the knowledge bundle."""
    from .service import fetch_concepts

    if local_format:
        ctx.obj["format"] = local_format

    if not query.strip():
        _handle_error(ctx, "A non-empty query is required", exit_code=2)
        return

    try:
        config = load_config()
        tags_list = [t.strip() for t in tags.split(",")] if tags else None
        results = fetch_concepts(
            config, query, top_n, threshold, type_filter, tags_list, mode=mode,
        )
        data = [
            {
                "concept_id": r.concept_id,
                "title": r.title,
                "score": r.score,
                "snippet": r.snippet,
            }
            for r in results
        ]
        _output(ctx, data)
    except OkfError as e:
        _handle_error(ctx, str(e))


@okf.command()
@click.option("--title", help="Concept title")
@click.option("--content", help="Concept body content")
@click.option("--type", "concept_type", help="Concept type (required)")
@click.option("--tags", help="Tags (comma-separated)")
@click.option("--json", "json_input", help="JSON input with all fields")
@click.option("--file", "file_input", type=click.Path(exists=True), help="JSON file input")
@click.option("--path", "target_path", help="Target subdirectory")
@click.option("--check-duplicates", is_flag=True, help="Check for similar concepts")
@click.option("--force", is_flag=True, help="Force commit even if duplicates found")
@click.option("--dry-run", is_flag=True, help="Show what would be committed without writing")
@click.pass_context
def commit(ctx: click.Context, **kwargs) -> None:
    """Create a new concept in the bundle."""
    from .service import commit_concept

    try:
        config = load_config()
        input_data = _parse_commit_input(kwargs)

        # Dry run: show what would happen without persisting
        if kwargs.get("dry_run"):
            _output(ctx, {
                "dry_run": True,
                "title": input_data.get("title"),
                "type": input_data.get("type"),
                "tags": input_data.get("tags", []),
                "target_path": input_data.get("path", "(bundle root)"),
                "content_length": len(input_data.get("content", "")),
            })
            return

        concept_id = commit_concept(config, input_data)
        _output(ctx, {"concept_id": concept_id})
    except OkfError as e:
        _handle_error(ctx, str(e))


@okf.command()
@click.argument("concept_id")
@click.option("--title", help="New title")
@click.option("--content", help="New body content")
@click.option("--type", "concept_type", help="New type")
@click.option("--tags", help="New tags (comma-separated)")
@click.option("--json", "json_input", help="JSON with fields to update")
@click.option("--file", "file_input", type=click.Path(exists=True), help="JSON file")
@click.pass_context
def update(ctx: click.Context, concept_id: str, **kwargs) -> None:
    """Update an existing concept."""
    from .service import update_concept

    try:
        config = load_config()
        updates = _parse_update_input(kwargs)
        result_id = update_concept(config, concept_id, updates)
        _output(ctx, {"concept_id": result_id})
    except OkfError as e:
        _handle_error(ctx, str(e))


@okf.command()
@click.argument("concept_id")
@click.pass_context
def delete(ctx: click.Context, concept_id: str) -> None:
    """Delete a concept from the bundle."""
    from .service import delete_concept

    try:
        config = load_config()
        delete_concept(config, concept_id)
        _output(ctx, {"status": "ok", "concept_id": concept_id})
    except OkfError as e:
        _handle_error(ctx, str(e))


@okf.command("list")
@click.option("--type", "type_filter", help="Filter by type")
@click.option("--tags", help="Filter by tags (comma-separated)")
@click.option("--since", help="Filter by timestamp (ISO 8601 date)")
@click.option("--limit", type=int, help="Maximum results")
@click.option("--path", "path_filter", help="Filter by subdirectory")
@click.option("--format", "local_format", type=click.Choice(["json", "text", "brief"]),
              default=None, help="Output format (overrides global --format)")
@click.pass_context
def list_cmd(ctx: click.Context, type_filter, tags, since, limit, path_filter, local_format) -> None:
    """List concepts in the bundle."""
    from .service import list_concepts

    if local_format:
        ctx.obj["format"] = local_format

    try:
        config = load_config()
        tags_list = [t.strip() for t in tags.split(",")] if tags else None
        concepts = list_concepts(config, type_filter, tags_list, since, limit, path_filter)
        data = [
            {"concept_id": c.concept_id, "title": c.title, "type": c.type}
            for c in concepts
        ]
        _output(ctx, data)
    except OkfError as e:
        _handle_error(ctx, str(e))


@okf.command()
@click.argument("concept_id")
@click.pass_context
def show(ctx: click.Context, concept_id: str) -> None:
    """Display a concept's full content."""
    from .service import show_concept

    try:
        config = load_config()
        concept = show_concept(config, concept_id)

        fmt = ctx.obj["format"]
        if fmt == "json":
            data = {
                "concept_id": concept.concept_id,
                "frontmatter": concept.frontmatter,
                "body": concept.body,
            }
            click.echo(json.dumps(data, indent=2, default=str))
        elif fmt == "brief":
            # Progressive disclosure: frontmatter only
            for key in ("title", "description", "type", "tags"):
                val = concept.frontmatter.get(key)
                if val is not None:
                    click.echo(f"{key}: {val}")
        else:
            click.echo(f"# {concept.title or concept.concept_id}\n")
            click.echo(f"type: {concept.type}")
            if concept.tags:
                click.echo(f"tags: {', '.join(concept.tags)}")
            click.echo(f"\n{concept.body}")
    except OkfError as e:
        _handle_error(ctx, str(e))


@okf.command()
@click.option("--full", is_flag=True, help="Full rebuild (discard existing index)")
@click.pass_context
def reindex(ctx: click.Context, full: bool) -> None:
    """Rebuild the vector index."""
    from .service import reindex as do_reindex

    try:
        config = load_config()
        result = do_reindex(config, full=full)
        _output(ctx, result)
    except OkfError as e:
        _handle_error(ctx, str(e))


@okf.command()
@click.pass_context
def stats(ctx: click.Context) -> None:
    """Show bundle health statistics."""
    from .service import get_stats

    try:
        config = load_config()
        result = get_stats(config)
        _output(ctx, result)
    except OkfError as e:
        _handle_error(ctx, str(e))


# --- Input parsing helpers ---


def _parse_commit_input(kwargs: dict) -> dict:
    """Parse commit command input from flags or JSON."""
    if kwargs.get("json_input"):
        data = json.loads(kwargs["json_input"])
    elif kwargs.get("file_input"):
        with open(kwargs["file_input"]) as f:
            data = json.load(f)
    else:
        data = {}
        if kwargs.get("title"):
            data["title"] = kwargs["title"]
        if kwargs.get("content"):
            data["content"] = kwargs["content"]
        if kwargs.get("concept_type"):
            data["type"] = kwargs["concept_type"]
        if kwargs.get("tags"):
            data["tags"] = [t.strip() for t in kwargs["tags"].split(",")]

    if kwargs.get("target_path"):
        data["path"] = kwargs["target_path"]
    if kwargs.get("check_duplicates"):
        data["check_duplicates"] = True
    if kwargs.get("force"):
        data["force"] = True

    return data


def _parse_update_input(kwargs: dict) -> dict:
    """Parse update command input from flags or JSON."""
    if kwargs.get("json_input"):
        return json.loads(kwargs["json_input"])
    if kwargs.get("file_input"):
        with open(kwargs["file_input"]) as f:
            return json.load(f)

    updates = {}
    if kwargs.get("title"):
        updates["title"] = kwargs["title"]
    if kwargs.get("content"):
        updates["content"] = kwargs["content"]
    if kwargs.get("concept_type"):
        updates["type"] = kwargs["concept_type"]
    if kwargs.get("tags"):
        updates["tags"] = [t.strip() for t in kwargs["tags"].split(",")]
    return updates
