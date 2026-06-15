"""Click-based CLI: single `okf` entry point with subcommands."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Optional

import click

from . import __version__
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
        for item in data:
            if isinstance(item, dict):
                click.echo(f"{item.get('concept_id', '')}\t{item.get('title', '')}")
            else:
                click.echo(str(item))
    else:
        # Text format — handle different data shapes
        if isinstance(data, dict):
            _print_dict(data)
        elif isinstance(data, list):
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
@click.option(
    "--bundle", "-b", "bundle_name",
    default=None,
    help="Target a specific bundle by name (for multi-bundle setups)",
)
@click.version_option(version=__version__)
@click.pass_context
def okf(ctx: click.Context, fmt: Optional[str], bundle_name: Optional[str]) -> None:
    """OKF bundle tools — search, author, and navigate knowledge."""
    ctx.ensure_object(dict)
    ctx.obj["format"] = _detect_format(fmt)
    ctx.obj["bundle_name"] = bundle_name


# --- Commands ---


@okf.command()
@click.option("--register", is_flag=True, help="Also register this bundle in ~/.config/okf/config.json")
@click.option("--name", "bundle_name_opt", default=None, help="Name for the bundle (defaults to directory name)")
@click.pass_context
def init(ctx: click.Context, register: bool, bundle_name_opt: Optional[str]) -> None:
    """Initialise a new OKF bundle in the current directory."""
    from .service import init_bundle

    try:
        path = Path.cwd()
        init_bundle(path)

        if register:
            _register_bundle_in_user_config(path, bundle_name_opt)

        _output(ctx, {"status": "ok", "message": "Bundle initialised"})
    except OkfError as e:
        _handle_error(ctx, str(e))


def _register_bundle_in_user_config(bundle_path: Path, name: Optional[str] = None) -> None:
    """Add a bundle entry to the user-level config at ~/.config/okf/config.json."""
    import json as _json

    user_config_path = Path.home() / ".config" / "okf" / "config.json"
    user_config_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing or create new
    if user_config_path.exists():
        text = user_config_path.read_text(encoding="utf-8")
        data = _json.loads(text)
    else:
        data = {}

    # Ensure bundles array exists
    if "bundles" not in data:
        data["bundles"] = []

    bundle_name = name or bundle_path.name
    path_str = str(bundle_path)

    # Check if already registered
    for entry in data["bundles"]:
        if entry.get("name") == bundle_name:
            return  # Already registered, no-op

    # Add the new bundle
    new_entry = {"name": bundle_name, "path": path_str}
    # If this is the first bundle, make it default
    if not data["bundles"]:
        new_entry["default"] = True
    data["bundles"].append(new_entry)

    user_config_path.write_text(
        _json.dumps(data, indent=2) + "\n", encoding="utf-8"
    )


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
@click.pass_context
def fetch(
    ctx: click.Context,
    query: str,
    top_n: Optional[int],
    threshold: Optional[float],
    type_filter: Optional[str],
    tags: Optional[str],
    mode: str,
) -> None:
    """Semantic search over the knowledge bundle."""
    from .service import fetch_concepts

    if not query.strip():
        _handle_error(ctx, "A non-empty query is required", exit_code=2)
        return

    try:
        config = load_config()
        tags_list = [t.strip() for t in tags.split(",")] if tags else None
        bundle_name = ctx.obj.get("bundle_name")
        results = fetch_concepts(
            config, query, top_n, threshold, type_filter, tags_list,
            mode=mode, bundle_name=bundle_name,
        )
        data = [
            {
                "concept_id": r.concept_id,
                "title": r.title,
                "score": r.score,
                "snippet": r.snippet,
                **({"bundle": r.bundle} if r.bundle else {}),
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
@click.pass_context
def commit(ctx: click.Context, **kwargs) -> None:
    """Create a new concept in the bundle."""
    from .service import commit_concept

    try:
        config = load_config()
        input_data = _parse_commit_input(kwargs)
        bundle_name = ctx.obj.get("bundle_name")
        concept_id = commit_concept(config, input_data, bundle_name=bundle_name)
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
        bundle_name = ctx.obj.get("bundle_name")
        result_id = update_concept(config, concept_id, updates, bundle_name=bundle_name)
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
        bundle_name = ctx.obj.get("bundle_name")
        delete_concept(config, concept_id, bundle_name=bundle_name)
        _output(ctx, {"status": "ok", "concept_id": concept_id})
    except OkfError as e:
        _handle_error(ctx, str(e))


@okf.command("list")
@click.option("--type", "type_filter", help="Filter by type")
@click.option("--tags", help="Filter by tags (comma-separated)")
@click.option("--since", help="Filter by timestamp (ISO 8601 date)")
@click.option("--limit", type=int, help="Maximum results")
@click.option("--path", "path_filter", help="Filter by subdirectory")
@click.pass_context
def list_cmd(ctx: click.Context, type_filter, tags, since, limit, path_filter) -> None:
    """List concepts in the bundle."""
    from .service import list_concepts

    try:
        config = load_config()
        tags_list = [t.strip() for t in tags.split(",")] if tags else None
        bundle_name = ctx.obj.get("bundle_name")
        concepts = list_concepts(
            config, type_filter, tags_list, since, limit, path_filter,
            bundle_name=bundle_name,
        )
        data = [
            {"concept_id": c.concept_id, "title": c.title, "type": c.type, "bundle": c.bundle}
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

        # Determine source bundle name
        bundle_label = None
        for bundle in config.bundles:
            if concept.file_path.is_relative_to(bundle.path):
                bundle_label = bundle.name
                break

        fmt = ctx.obj["format"]
        if fmt == "json":
            data = {
                "concept_id": concept.concept_id,
                "frontmatter": concept.frontmatter,
                "body": concept.body,
                "bundle": bundle_label,
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
            if bundle_label:
                click.echo(f"bundle: {bundle_label}")
            click.echo(f"\n{concept.body}")
    except OkfError as e:
        _handle_error(ctx, str(e))


@okf.command()
@click.argument("concept_id")
@click.option("--direction", type=click.Choice(["in", "out", "both"]), default="both")
@click.option("--depth", type=int, default=1, help="BFS depth (1-10)")
@click.pass_context
def links(ctx: click.Context, concept_id: str, direction: str, depth: int) -> None:
    """Show link graph for a concept."""
    from .service import get_links

    try:
        config = load_config()
        depth = max(1, min(10, depth))
        result = get_links(config, concept_id, direction, depth)
        _output(ctx, result)
    except OkfError as e:
        _handle_error(ctx, str(e))


@okf.command()
@click.option("--full", is_flag=True, help="Full rebuild (discard existing index)")
@click.option("--lint", "run_lint", is_flag=True, help="Validate bundle during reindex")
@click.pass_context
def reindex(ctx: click.Context, full: bool, run_lint: bool) -> None:
    """Rebuild the vector index."""
    from .service import reindex as do_reindex

    try:
        config = load_config()
        bundle_name = ctx.obj.get("bundle_name")
        result = do_reindex(config, full=full, lint=run_lint, bundle_name=bundle_name)
        _output(ctx, result)

        # Non-zero exit if lint found errors
        if run_lint and result.get("lint", {}).get("errors", 0) > 0:
            ctx.exit(1)
    except OkfError as e:
        _handle_error(ctx, str(e))


@okf.command()
@click.pass_context
def stats(ctx: click.Context) -> None:
    """Show bundle health statistics."""
    from .service import get_stats

    try:
        config = load_config()
        bundle_name = ctx.obj.get("bundle_name")
        result = get_stats(config, bundle_name=bundle_name)
        _output(ctx, result)
    except OkfError as e:
        _handle_error(ctx, str(e))


@okf.command()
@click.pass_context
def skills(ctx: click.Context) -> None:
    """List installed skill packs."""
    from .service import list_skills

    try:
        config = load_config()
        skill_list = list_skills(config)
        data = [
            {"filename": s.filename, "title": s.title, "description": s.description}
            for s in skill_list
        ]
        _output(ctx, data)
    except OkfError as e:
        _handle_error(ctx, str(e))


@okf.command()
@click.option("--warn-only", is_flag=True, help="Always exit 0 regardless of findings")
@click.option("--path", "path_filter", help="Validate only this subdirectory")
@click.option(
    "--rule",
    type=click.Choice(["frontmatter", "structure", "links", "types"]),
    help="Run only this rule category",
)
@click.pass_context
def lint(
    ctx: click.Context,
    warn_only: bool,
    path_filter: Optional[str],
    rule: Optional[str],
) -> None:
    """Validate bundle for OKF compliance."""
    from .service import lint_bundle

    try:
        config = load_config()
        report = lint_bundle(config, path_filter, rule)

        fmt = ctx.obj["format"]
        if fmt == "json":
            data = {
                "files_checked": report.files_checked,
                "errors": report.errors,
                "warnings": report.warnings,
                "diagnostics": [
                    {"file": d.file, "rule": d.rule, "severity": d.severity, "message": d.message}
                    for d in report.diagnostics
                ],
            }
            click.echo(json.dumps(data, indent=2))
        else:
            if not report.diagnostics:
                click.echo(f"✓ Bundle clean ({report.files_checked} files checked)")
            else:
                for d in report.diagnostics:
                    icon = "✗" if d.severity == "error" else "⚠"
                    click.echo(f"{icon} {d.file}: [{d.rule}] {d.message}")
                click.echo(
                    f"\n{report.errors} error(s), {report.warnings} warning(s) "
                    f"in {report.files_checked} files"
                )

        if not warn_only and report.errors > 0:
            ctx.exit(1)
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

    # Warn about unrecognized fields in JSON input
    _KNOWN_COMMIT_FIELDS = {
        "title", "content", "type", "tags", "timestamp", "description",
        "path", "check_duplicates", "force",
    }
    unknown = set(data.keys()) - _KNOWN_COMMIT_FIELDS
    if unknown:
        import sys
        print(
            f"warning: unrecognized fields ignored: {', '.join(sorted(unknown))}",
            file=sys.stderr,
        )

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
