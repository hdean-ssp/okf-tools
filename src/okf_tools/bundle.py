"""OKF bundle I/O: parse, write, validate concepts and manage index files."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import frontmatter

from .errors import ParseError


@dataclass
class Concept:
    """In-memory representation of an OKF concept file."""

    concept_id: str
    frontmatter: Dict[str, Any]
    body: str
    file_path: Path

    @property
    def title(self) -> Optional[str]:
        return self.frontmatter.get("title")

    @property
    def type(self) -> str:
        return self.frontmatter["type"]

    @property
    def tags(self) -> List[str]:
        return self.frontmatter.get("tags", [])

    @property
    def timestamp(self) -> Optional[str]:
        return self.frontmatter.get("timestamp")


# --- Parsing ---


def parse_concept(file_path: Path, bundle_root: Path) -> Concept:
    """Parse a .md file into a Concept. Raises ParseError on failure."""
    try:
        post = frontmatter.load(str(file_path))
    except Exception as e:
        raise ParseError(str(file_path), f"Failed to parse frontmatter: {e}")

    if not post.metadata:
        raise ParseError(str(file_path), "No YAML frontmatter found")

    rel = file_path.resolve().relative_to(bundle_root.resolve())
    concept_id = str(rel.with_suffix(""))

    return Concept(
        concept_id=concept_id,
        frontmatter=dict(post.metadata),
        body=post.content,
        file_path=file_path.resolve(),
    )


def format_concept(concept: Concept) -> str:
    """Serialize a Concept to .md file content."""
    post = frontmatter.Post(content=concept.body, **concept.frontmatter)
    return frontmatter.dumps(post) + "\n"


# --- Validation ---


def validate_frontmatter(fm: Dict[str, Any]) -> List[str]:
    """Validate OKF compliance. Returns list of error messages (empty = valid)."""
    errors: List[str] = []

    # type is required and must be non-empty string
    type_val = fm.get("type")
    if not type_val or not isinstance(type_val, str) or not type_val.strip():
        errors.append("'type' field is required and must be a non-empty string")

    # timestamp must be ISO 8601 if present
    ts = fm.get("timestamp")
    if ts is not None:
        if not _is_iso8601(ts):
            errors.append(f"'timestamp' must be ISO 8601 format, got: {ts}")

    # tags must be a list of strings if present
    tags = fm.get("tags")
    if tags is not None:
        if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
            errors.append("'tags' must be a list of strings")

    return errors


def _is_iso8601(value: Any) -> bool:
    """Check if a value is a valid ISO 8601 date/datetime string."""
    if isinstance(value, datetime):
        return True
    if not isinstance(value, str):
        return False
    # Try common ISO 8601 patterns
    for fmt in (
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S.%f%z",
    ):
        try:
            datetime.strptime(value, fmt)
            return True
        except ValueError:
            continue
    return False


# --- Slug Generation ---


def generate_slug(title: str) -> str:
    """Create URL-safe filename from title: lowercase, hyphens, max 60 chars."""
    slug = title.lower()
    slug = re.sub(r"\s+", "-", slug)
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    slug = re.sub(r"-{2,}", "-", slug)
    slug = slug.strip("-")

    if len(slug) > 60:
        # Truncate at last hyphen boundary within 60 chars
        truncated = slug[:60]
        last_hyphen = truncated.rfind("-")
        if last_hyphen > 0:
            slug = truncated[:last_hyphen]
        else:
            slug = truncated

    return slug


def resolve_unique_path(directory: Path, slug: str) -> Path:
    """If slug.md exists, append -2, -3 etc. Returns a unique .md path."""
    candidate = directory / f"{slug}.md"
    if not candidate.exists():
        return candidate

    counter = 2
    while True:
        candidate = directory / f"{slug}-{counter}.md"
        if not candidate.exists():
            return candidate
        counter += 1


# --- Bundle Walking ---


def walk_concepts(bundle_root: Path) -> List[Concept]:
    """Find and parse all concept .md files (excluding index.md, log.md)."""
    concepts: List[Concept] = []
    for md_file in sorted(bundle_root.rglob("*.md")):
        if not is_concept_file(md_file):
            continue
        # Skip files inside .okf/ sidecar
        try:
            md_file.relative_to(bundle_root / ".okf")
            continue
        except ValueError:
            pass
        try:
            concept = parse_concept(md_file, bundle_root)
            concepts.append(concept)
        except ParseError:
            continue  # Skip unparseable files during walk
    return concepts


def is_concept_file(path: Path) -> bool:
    """True if .md file but not index.md or log.md."""
    return path.suffix == ".md" and path.name not in ("index.md", "log.md")


# --- Index File Management ---


def update_index_file(directory: Path, concept_id: str, title: str) -> None:
    """Add or update an entry in the directory's index.md."""
    index_path = directory / "index.md"
    filename = Path(concept_id).name + ".md"
    entry = f"- [{title}](./{filename})"

    if index_path.exists():
        content = index_path.read_text(encoding="utf-8")
        # Check if entry for this file already exists
        pattern = re.compile(rf"- \[.*\]\(\./{ re.escape(filename) }\)")
        if pattern.search(content):
            # Update existing entry
            content = pattern.sub(entry, content)
        else:
            # Append new entry
            content = content.rstrip("\n") + "\n" + entry + "\n"
        index_path.write_text(content, encoding="utf-8")
    else:
        # Create new index.md
        heading = directory.name or "Knowledge Bundle"
        content = f"# {heading}\n\n{entry}\n"
        index_path.write_text(content, encoding="utf-8")


def remove_from_index_file(directory: Path, concept_id: str) -> None:
    """Remove an entry from the directory's index.md."""
    index_path = directory / "index.md"
    if not index_path.exists():
        return

    filename = Path(concept_id).name + ".md"
    pattern = re.compile(rf"- \[.*\]\(\./{ re.escape(filename) }\)\n?")
    content = index_path.read_text(encoding="utf-8")
    content = pattern.sub("", content)
    index_path.write_text(content, encoding="utf-8")


# --- Write ---


def write_concept(concept: Concept, bundle_root: Path) -> Path:
    """Write concept to disk, creating directories as needed. Returns file path."""
    file_path = bundle_root / (concept.concept_id + ".md")
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(format_concept(concept), encoding="utf-8")
    return file_path
