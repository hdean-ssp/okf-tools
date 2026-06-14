# Technical Design Document

## Overview

okf-tools is a Python CLI and library that makes OKF bundles queryable, navigable, and agent-friendly. The design follows a layered architecture: a thin CLI layer delegates to a service orchestration layer, which coordinates domain modules (bundle I/O, vector search, link graph). All derived state lives in a gitignored sidecar directory (`.okf/`), keeping the markdown files as the sole source of truth.

**Key architectural decisions:**
- Single `okf` CLI entry point using Click with subcommands
- Vector index is a derived sidecar artifact (sqlite-vec) — gitignored, rebuildable
- Concepts live as files — no database for primary data
- Incremental indexing via file mtime tracking
- Lazy model loading — embedding model only loads when needed
- Auto-detect TTY for output format (JSON for pipes/agents, text for humans)

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      CLI Layer (cli.py)                  │
│  Click-based entry point, output formatting, TTY detect │
└────────────────────────────┬────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────┐
│                  Service Layer (service.py)              │
│  Orchestrates workflows: commit, fetch, update, delete  │
└──┬──────────┬──────────┬──────────┬──────────┬──────────┘
   │          │          │          │          │
┌──▼────┐ ┌──▼─────┐ ┌──▼────┐ ┌──▼─────┐ ┌──▼────────┐
│bundle │ │search  │ │graph  │ │sync    │ │validation │
│.py    │ │.py     │ │.py    │ │.py     │ │.py        │
│       │ │        │ │       │ │        │ │           │
│Parse  │ │Embed+  │ │Link   │ │Increm. │ │Lint rules │
│R/W    │ │Query   │ │adj.   │ │rebuild │ │Structure  │
│Index  │ │sqlite  │ │BFS    │ │mtime   │ │Links/Types│
└───────┘ └────────┘ └───────┘ └────────┘ └───────────┘
   │          │          │          │          │
┌──▼──────────▼──────────▼──────────▼──────────▼──────────┐
│         Shared: config.py, errors.py, skills.py         │
└─────────────────────────────────────────────────────────┘
```

**Data flow summary:**
- CLI parses user input → calls service layer functions
- Service layer coordinates module calls (validate → write → embed → index → git)
- Bundle module owns file I/O and parsing
- Search module owns the vector database
- Graph module owns link parsing and traversal
- Sync module detects filesystem changes and drives incremental updates
- Validation module owns all compliance checks beyond basic frontmatter (structure, links, type consistency)
- Config module resolves settings from defaults → user → bundle levels

**Runtime file system layout:**
```
my-knowledge-bundle/           # The OKF bundle (git tracked)
├── index.md                   # Root concept listing
├── patterns/
│   ├── index.md
│   ├── retry-with-backoff.md
│   └── circuit-breaker.md
├── .okf/                      # Sidecar directory (gitignored)
│   ├── config.json            # Bundle-level configuration
│   └── index/
│       └── okf.db             # sqlite-vec database (embeddings + links + metadata)
└── .gitignore                 # Contains .okf/index/
```

## Data Models

```python
@dataclass
class Concept:
    """In-memory representation of an OKF concept file."""
    concept_id: str              # Relative path minus .md (e.g., "patterns/retry-with-backoff")
    frontmatter: dict[str, Any]  # All YAML fields (type is required, rest optional)
    body: str                    # Markdown content after frontmatter
    file_path: Path              # Absolute path to the .md file on disk

    @property
    def title(self) -> str | None:
        return self.frontmatter.get("title")

    @property
    def type(self) -> str:
        return self.frontmatter["type"]

    @property
    def tags(self) -> list[str]:
        return self.frontmatter.get("tags", [])

    @property
    def timestamp(self) -> str | None:
        return self.frontmatter.get("timestamp")


@dataclass
class OkfConfig:
    """Resolved configuration with defaults applied."""
    bundle_path: Path
    index_path: Path
    embedding_model: str
    default_top_n: int
    similarity_threshold: float
    auto_git_add: bool
    skills_paths: list[str]
    validation_level: str        # "strict", "standard", or "relaxed"


@dataclass
class SearchResult:
    """A single search result from semantic query."""
    concept_id: str
    title: str | None
    score: float          # Cosine similarity 0.0-1.0
    snippet: str          # First 200 chars of body


@dataclass
class LinkEntry:
    """A single link relationship between concepts."""
    source_id: str
    target_id: str


@dataclass
class ChangeSet:
    """Files changed since last index sync."""
    added: list[Path]
    modified: list[Path]
    deleted: list[str]   # concept_ids


@dataclass
class SyncSummary:
    """Result of a reindex operation."""
    added: int
    updated: int
    removed: int
    total_indexed: int
    skipped: list[str]   # Files that failed embedding


@dataclass
class SkillPack:
    """A discovered skill pack."""
    filename: str
    title: str
    description: str
    file_path: Path


@dataclass
class LintDiagnostic:
    """A single validation finding."""
    file: str              # Relative path within bundle
    rule: str              # Rule identifier (e.g., "frontmatter/type-required")
    severity: str          # "error" or "warning"
    message: str           # Human-readable description


@dataclass
class LintReport:
    """Aggregated result of bundle validation."""
    diagnostics: list[LintDiagnostic]
    files_checked: int
    errors: int
    warnings: int
```

## Components and Interfaces

### Component 1: Bundle Module (`src/okf_tools/bundle.py`)

**Responsibility:** Parse and write OKF concept files, manage index.md files, generate slugs, walk the bundle directory tree, validate frontmatter.

**Interface:**

```python
def parse_concept(file_path: Path, bundle_root: Path) -> Concept:
    """Parse a .md file into a Concept dataclass.
    Raises ParseError if file lacks valid frontmatter."""

def format_concept(concept: Concept) -> str:
    """Serialize a Concept to .md content: --- frontmatter --- \\n\\n body\\n"""

def write_concept(concept: Concept, bundle_root: Path) -> Path:
    """Write concept to disk, creating directories as needed. Returns file path."""

def generate_slug(title: str) -> str:
    """Create URL-safe filename: lowercase, hyphens, max 60 chars, word boundary truncation."""

def resolve_unique_path(directory: Path, slug: str) -> Path:
    """If slug.md exists, append -2, -3 etc. Returns a unique .md path."""

def update_index_file(directory: Path, concept_id: str, title: str) -> None:
    """Add or update an entry in the directory's index.md. Creates index.md if missing."""

def remove_from_index_file(directory: Path, concept_id: str) -> None:
    """Remove an entry from the directory's index.md."""

def walk_concepts(bundle_root: Path) -> list[Concept]:
    """Find and parse all .md files (excluding index.md, log.md)."""

def validate_frontmatter(frontmatter: dict) -> list[str]:
    """Validate OKF compliance. Returns list of error messages (empty = valid)."""
```

**Slug generation algorithm:**
1. Lowercase the title
2. Replace whitespace sequences with single hyphens
3. Remove all characters that are not alphanumeric or hyphens
4. Collapse consecutive hyphens into one
5. Strip leading/trailing hyphens
6. If longer than 60 characters, truncate at the last hyphen boundary within 60 chars
7. If a file exists at the path, append `-2`, `-3`, etc. until unique

### Component 2: Search Module (`src/okf_tools/search.py`)

**Responsibility:** Manage the sqlite-vec vector index, embed text via fastembed, perform cosine similarity queries.

**Interface:**

```python
class VectorIndex:
    """Manages the sqlite-vec sidecar database."""

    def __init__(self, db_path: Path):
        """Open or create the database. Enables WAL mode."""

    def upsert(self, concept_id: str, embedding: np.ndarray, metadata: dict) -> None:
        """Add or update a concept's embedding and metadata."""

    def delete(self, concept_id: str) -> None:
        """Remove a concept from the index."""

    def search(self, query_embedding: np.ndarray, top_n: int, threshold: float) -> list[SearchResult]:
        """Cosine similarity search. Returns results above threshold."""

    def get_metadata(self, concept_id: str) -> dict | None:
        """Get stored metadata for a concept (mtime, type, tags, snippet)."""

    def get_all_concept_ids(self) -> set[str]:
        """Return all indexed concept IDs."""

    def get_sync_timestamp(self) -> float | None:
        """Get last sync timestamp from metadata table."""

    def set_sync_timestamp(self, ts: float) -> None:
        """Persist sync timestamp."""

    def check_integrity(self) -> bool:
        """Verify database is openable and passes integrity_check."""

    def concept_count(self) -> int:
        """Number of indexed concepts."""


def get_embedder(model_name: str) -> TextEmbedding:
    """Lazily initialize and cache the fastembed model."""

def embed_text(text: str, model_name: str) -> np.ndarray:
    """Embed a single text string. Returns 384-dim vector."""

def embed_batch(texts: list[str], model_name: str) -> list[np.ndarray]:
    """Batch embed for reindex efficiency."""
```

**Database schema:**

```sql
CREATE TABLE IF NOT EXISTS sync_meta (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS concepts (
    concept_id TEXT PRIMARY KEY,
    title TEXT,
    type TEXT,
    tags TEXT,          -- JSON array as string
    mtime REAL,
    snippet TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS vec_concepts USING vec0(
    concept_id TEXT PRIMARY KEY,
    embedding FLOAT[384]
);
```

### Component 3: Graph Module (`src/okf_tools/graph.py`)

**Responsibility:** Parse markdown links from concept bodies, persist link relationships, perform BFS traversal.

**Interface:**

```python
class LinkGraph:
    """Bidirectional link graph backed by SQLite."""

    def __init__(self, db_path: Path):
        """Open the links table in the sidecar database."""

    def set_links(self, source_id: str, target_ids: list[str]) -> None:
        """Replace all outlinks for a source concept."""

    def remove_concept(self, concept_id: str) -> None:
        """Remove all links involving this concept (in + out)."""

    def get_outlinks(self, concept_id: str) -> list[str]:
        """Concepts this one links to."""

    def get_inlinks(self, concept_id: str) -> list[str]:
        """Concepts that link to this one."""

    def bfs_neighborhood(self, concept_id: str, depth: int, direction: str) -> list[str]:
        """BFS traversal. direction: 'in', 'out', or 'both'."""

    def get_orphans(self, all_concept_ids: set[str]) -> list[str]:
        """Concepts with no inbound or outbound links."""

    def get_stats(self, total_concepts: int) -> dict:
        """Edge count, average links per concept."""


def extract_links(concept: Concept, bundle_root: Path) -> list[str]:
    """Parse markdown links from body, resolve to concept_ids.
    Excludes external URLs, fragment-only anchors, and non-.md targets."""
```

**Link parsing rules:**
- Match markdown link pattern: `[text](url)`
- Internal if URL starts with `/` or `./` and ends with `.md`
- Resolve relative paths against source concept's directory
- Absolute paths relative to bundle root
- Strip `.md` to get concept_id
- Exclude: http/https URLs, `#`-only anchors, non-.md references

**SQL schema (in same `okf.db`):**
```sql
CREATE TABLE IF NOT EXISTS links (
    source_id TEXT,
    target_id TEXT,
    PRIMARY KEY (source_id, target_id)
);
CREATE INDEX IF NOT EXISTS idx_links_target ON links(target_id);
```

### Component 4: Sync Module (`src/okf_tools/sync.py`)

**Responsibility:** Detect filesystem changes, drive incremental re-embedding, coordinate full rebuilds.

**Interface:**

```python
def detect_changes(bundle_root: Path, index: VectorIndex) -> ChangeSet:
    """Compare filesystem state to indexed state. Returns added/modified/deleted."""

def incremental_reindex(
    bundle_root: Path, index: VectorIndex, graph: LinkGraph, config: OkfConfig
) -> SyncSummary:
    """Process only changed files. Re-embed, update index + graph."""

def full_reindex(
    bundle_root: Path, index: VectorIndex, graph: LinkGraph, config: OkfConfig
) -> SyncSummary:
    """Drop all index data and rebuild from scratch."""

def is_concept_file(path: Path) -> bool:
    """True if .md file but not index.md or log.md."""
```

**Incremental sync algorithm:**
1. Walk bundle, collect all concept files
2. Get all indexed concept_ids + mtimes from VectorIndex
3. Classify: added (new on disk), modified (mtime > stored), deleted (in index, not on disk)
4. Parse + batch embed added/modified files
5. Upsert embeddings + metadata for added/modified
6. Remove deleted from index + graph
7. Update link graph for added/modified (extract_links → set_links)
8. Persist sync timestamp
9. If `--lint` flag is active, run `lint_bundle()` and append diagnostics to output
10. Report summary (or skip list for failures)

### Component 5: Service Module (`src/okf_tools/service.py`)

**Responsibility:** Orchestrate multi-step workflows that coordinate across modules.

**Interface:**

```python
def init_bundle(path: Path) -> None:
    """Create .okf/config.json, root index.md, update .gitignore."""

def commit_concept(config: OkfConfig, input_data: dict) -> str:
    """Full commit workflow. Returns concept_id."""

def update_concept(config: OkfConfig, concept_id: str, updates: dict) -> str:
    """Full update workflow. Returns concept_id."""

def delete_concept(config: OkfConfig, concept_id: str) -> None:
    """Full delete workflow."""

def fetch_concepts(
    config: OkfConfig, query: str, top_n: int, threshold: float,
    type_filter: str | None, tags_filter: list[str] | None
) -> list[SearchResult]:
    """Semantic search workflow."""

def list_concepts(
    config: OkfConfig, type_filter: str | None, tags_filter: list[str] | None,
    since: str | None, limit: int | None, path_filter: str | None
) -> list[Concept]:
    """Filtered concept listing."""

def show_concept(config: OkfConfig, concept_id: str) -> Concept:
    """Load and return a single concept."""

def get_links(
    config: OkfConfig, concept_id: str, direction: str, depth: int
) -> dict:
    """Graph traversal. Returns {'inbound': [...], 'outbound': [...]}."""

def reindex(config: OkfConfig, full: bool) -> SyncSummary:
    """Index rebuild (incremental or full)."""

def get_stats(config: OkfConfig) -> dict:
    """Bundle health statistics."""

def list_skills(config: OkfConfig) -> list[SkillPack]:
    """Discover and return all skill packs."""

def lint_bundle(
    config: OkfConfig, path_filter: str | None, rule_filter: str | None
) -> LintReport:
    """Run bundle validation. Delegates to validation module."""
```

### Component 6: Config Module (`src/okf_tools/config.py`)

**Interface:**

```python
def load_config(bundle_root: Path | None = None) -> OkfConfig:
    """Load config from bundle → user → defaults. Merge per-field."""

def get_defaults() -> dict:
    """Return built-in default configuration values."""

def find_bundle_root(start_path: Path) -> Path | None:
    """Walk up directories to find .okf/config.json. Returns None if not found."""
```

**Resolution order:** defaults → `~/.config/okf/config.json` → `.okf/config.json` (each level overrides per-field).

**Default for `validation_level`:** `"standard"`. Valid values: `"strict"`, `"standard"`, `"relaxed"`.

### Component 7: Skills Module (`src/okf_tools/skills.py`)

**Interface:**

```python
def discover_skills(skills_paths: list[str], bundled_skill_path: Path) -> list[SkillPack]:
    """Scan all configured paths + bundled skill. Return discovered skills."""

def parse_skill_metadata(file_path: Path) -> SkillPack | None:
    """Extract title/description from a skill .md file. Returns None if no frontmatter."""
```

### Component 8: Validation Module (`src/okf_tools/validation.py`)

**Responsibility:** Perform bundle-wide OKF compliance checks including structural validation, link integrity, type consistency, and configurable strictness enforcement. Reuses `validate_frontmatter()` from bundle.py for per-concept checks but extends with cross-cutting concerns.

**Interface:**

```python
def lint_bundle(
    bundle_root: Path, config: OkfConfig,
    path_filter: str | None = None, rule_filter: str | None = None
) -> LintReport:
    """Run all applicable validation rules across the bundle.
    Respects validation_level from config. Returns aggregated report."""

def validate_structure(bundle_root: Path, concepts: list[Concept]) -> list[LintDiagnostic]:
    """Check structural conventions:
    - Every directory with concepts has an index.md
    - Every index.md entry points to an existing file
    - No orphaned entries in index.md"""

def check_link_integrity(concepts: list[Concept], bundle_root: Path) -> list[LintDiagnostic]:
    """Check that all internal markdown links resolve to existing concept files.
    Reports broken links as errors."""

def check_type_consistency(concepts: list[Concept]) -> list[LintDiagnostic]:
    """Detect near-duplicate type values (case-insensitive collisions,
    hyphenation variants, whitespace differences). Reports as warnings."""

def validate_concept_full(
    concept: Concept, validation_level: str
) -> list[LintDiagnostic]:
    """Validate a single concept against all frontmatter rules at the given strictness.
    - strict: type + title + description required
    - standard: type required, validate timestamp/tags if present
    - relaxed: only type required, other violations downgraded to warnings"""
```

**Rule identifiers:**
| Rule ID | Category | Severity | Description |
|---------|----------|----------|-------------|
| `frontmatter/type-required` | frontmatter | error | Missing or empty `type` field |
| `frontmatter/title-required` | frontmatter | error (strict only) | Missing `title` in strict mode |
| `frontmatter/description-required` | frontmatter | error (strict only) | Missing `description` in strict mode |
| `frontmatter/invalid-timestamp` | frontmatter | error/warning | Non-ISO 8601 timestamp |
| `frontmatter/invalid-tags` | frontmatter | error/warning | `tags` is not a list of strings |
| `structure/missing-index` | structure | error | Directory with concepts lacks index.md |
| `structure/orphaned-entry` | structure | warning | index.md entry points to non-existent file |
| `structure/missing-entry` | structure | warning | Concept exists but is not listed in index.md |
| `links/broken-internal` | links | error | Internal link target does not exist |
| `types/near-duplicate` | types | warning | Type values differ only by case/hyphen/space |

**Type consistency detection algorithm:**
1. Collect all distinct `type` values across the bundle
2. Normalize each: lowercase, replace hyphens and spaces with empty string
3. Group original values by their normalized form
4. Any group with more than one distinct original value is a near-duplicate cluster
5. Report each cluster as a warning listing all variants and their file locations

### Component 9: CLI Module (`src/okf_tools/cli.py`)

**Interface:** Click group `okf` with subcommands: `init`, `fetch`, `commit`, `update`, `delete`, `list`, `show`, `links`, `reindex`, `stats`, `skills`, `lint`.

**Output formatting:** All commands call a shared `output()` helper that routes to JSON, text, or brief formatters.

**Error handling:** All commands catch `OkfError` subclasses and route through `handle_error()` which formats to stderr per the active format.

**Lint command specifics:**
```python
@okf.command()
@click.option("--warn-only", is_flag=True, help="Always exit 0 regardless of findings")
@click.option("--path", "path_filter", help="Validate only concepts in this subdirectory")
@click.option("--rule", "rule_filter", type=click.Choice(["frontmatter", "structure", "links", "types"]))
def lint(warn_only, path_filter, rule_filter): ...
```

### Component 10: Errors Module (`src/okf_tools/errors.py`)

```python
class OkfError(Exception): ...
class ConceptNotFoundError(OkfError): ...
class ValidationError(OkfError): ...
class IndexCorruptionError(OkfError): ...
class BundleAlreadyInitialisedError(OkfError): ...
class ConfigError(OkfError): ...
class ParseError(OkfError): ...
```

## Correctness Properties

### Property 1: Source of Truth Invariant

The `.md` files on disk are always authoritative. The vector index and link graph are derived and can be fully reconstructed via `okf reindex --full`. No operation ever modifies the sidecar without first succeeding on the filesystem.

**Validates: Requirements 9.1, 9.2**

### Property 2: Round-trip Fidelity

`parse_concept(format_concept(parse_concept(file)))` produces identical frontmatter key-value pairs and identical body string for all valid concept files. Extra YAML keys beyond the OKF standard fields are preserved through parse and format operations.

**Validates: Requirements 17.3, 17.4**

### Property 3: Index Consistency After Mutations

Every commit, update, and delete operation updates both the filesystem AND the sidecar index (vector + links). If a write succeeds but indexing fails, the file is still written (source of truth preserved) and a subsequent `okf reindex` will bring the sidecar back into sync.

**Validates: Requirements 2.13, 3.2, 4.3**

### Property 4: Slug Uniqueness

The `resolve_unique_path` function guarantees no two concepts share a filename in the same directory by appending incrementing numeric suffixes (`-2`, `-3`, etc.) until a unique path is found.

**Validates: Requirements 2.2, 2.3**

### Property 5: Incremental Sync Completeness

After `okf reindex` completes successfully, the set of concept_ids in the vector index equals the set of concept `.md` files on disk (minus index.md and log.md). No stale entries remain, no files are missing from the index.

**Validates: Requirements 9.4, 9.5, 9.7**

### Property 6: Graph Accuracy

The link graph reflects only links to existing concepts within the bundle. External URLs (http/https), broken internal links (paths that don't resolve to files), and fragment-only anchors are excluded from the graph.

**Validates: Requirements 8.7, 8.8**

### Property 7: Config Precedence

Bundle-level config fields always override user-level fields, which always override built-in defaults. Merge is per-field — no field is silently dropped when a higher-priority config file is present.

**Validates: Requirements 12.1, 12.6**

### Property 8: Lint Completeness

After `okf lint` completes with zero errors at a given `validation_level`, the bundle is guaranteed to satisfy all OKF compliance rules for that level: every concept has valid frontmatter, every directory with concepts has an index.md, all internal links resolve, and no type inconsistencies exist at error severity. A bundle that passes lint at `strict` level also passes at `standard` and `relaxed`.

**Validates: Requirements 18.1, 18.2, 18.6, 18.7, 18.8, 18.9, 18.10, 18.11, 18.12**

## Error Handling

**Error propagation pattern:**
1. Domain modules raise typed exceptions from `errors.py`
2. Service layer may catch and wrap errors (e.g., filesystem errors → ConceptNotFoundError)
3. CLI layer catches all `OkfError` subclasses at the command boundary
4. CLI routes errors through `handle_error()` which formats for the active output mode

**Error categories and exit codes:**
| Error Type | Exit Code | Example |
|-----------|-----------|---------|
| Usage / missing arguments | 2 | `okf fetch` (no query) |
| Concept not found | 1 | `okf show nonexistent/path` |
| Validation failure | 1 | Missing `type` field |
| Lint errors found | 1 | `okf lint` finds broken links |
| Lint with --warn-only | 0 | Findings reported but exit clean |
| Filesystem failure | 1 | Permission denied |
| Index corruption | 1 | Corrupted SQLite file |
| Config parse failure | 1 | Malformed JSON |

**Resilience during reindex:**
- If embedding fails for a specific file, skip it, continue others, report at end
- If the database is corrupted, suggest `okf reindex --full`
- Non-existent skills_paths are silently skipped

## Testing Strategy

**Unit tests (per module):**
- `test_bundle.py`: parse/format round-trip, slug generation (edge cases: long titles, special chars, collisions), index.md update/remove, validate_frontmatter
- `test_search.py`: VectorIndex CRUD operations, search with threshold/top-n, integrity check
- `test_graph.py`: link extraction (various markdown patterns), BFS traversal, orphan detection
- `test_sync.py`: change detection (added/modified/deleted), incremental vs full reindex
- `test_service.py`: end-to-end workflows (commit → fetch finds it, delete → fetch doesn't)
- `test_config.py`: merge precedence, invalid JSON handling, defaults
- `test_skills.py`: discovery with missing dirs, frontmatter parsing, title resolution fallback
- `test_validation.py`: structural checks (missing index.md, orphaned entries), link integrity (broken links detected), type consistency (near-duplicate detection), validation levels (strict requires title+description, relaxed downgrades to warnings), rule filtering
- `test_cli.py`: output format selection, TTY detection, error formatting, lint command exit codes

**Test fixtures:**
- `tests/fixtures/sample_bundle/`: A minimal OKF bundle with 5-10 concepts across 2 directories, cross-linked, with various frontmatter combinations.

**Integration approach:**
- Tests that need the vector index use a temporary directory with a fresh sqlite-vec database
- Tests that need embeddings use fastembed with the real model (small enough for CI)
- No mocks for the embedding model — tests validate real embedding + search behaviour

## Dependency Details

| Package | Version Constraint | Purpose |
|---------|-------------------|---------|
| `click` | `>=8.0,<9.0` | CLI framework with subcommands and auto-completion |
| `fastembed` | `>=0.3.0,<1.0` | Local ONNX-based text embeddings (BAAI/bge-small-en-v1.5) |
| `sqlite-vec` | `>=0.1.0,<1.0` | Vector similarity extension for SQLite |
| `python-frontmatter` | `>=1.0,<2.0` | Parse YAML frontmatter + markdown body |
| `pyyaml` | `>=6.0` | YAML serialization (transitive, pinned for safety) |

## Packaging

```toml
[project.scripts]
okf = "okf_tools.cli:okf"
```

The bundled `core-knowledge.md` skill is included as package data via `importlib.resources` for reliable access regardless of install method.
