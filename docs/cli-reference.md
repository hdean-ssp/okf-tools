# CLI Reference

All commands use `okf` as the entry point. Global options go before the subcommand.

## Global Options

```
okf --format json|text|brief <command>
okf --bundle <name> <command>     # or: okf -b <name> <command>
okf --version
okf --help
```

- `--format`: Override output format. Default: `text` for TTY, `json` when piped.
- `--bundle` / `-b`: Target a specific named bundle. Applies to all subcommands. For write commands (commit, update, delete) this sets the write target. For read commands (fetch, list, show, links, stats) this limits scope to one bundle. Without `-b`, reads search all bundles and writes go to the default bundle.

---

## okf init

Initialise a new OKF bundle in the current directory.

```bash
okf init
okf init --register                    # Also add to ~/.config/okf/config.json
okf init --register --name team-kb     # Register with a custom name
```

Creates `.okf/config.json`, root `index.md`, and updates `.gitignore` if in a git repo.

**Options:**
| Flag | Description |
|------|-------------|
| `--register` | Register the new bundle in user-level config |
| `--name` | Name for the bundle (defaults to directory name) |

---

## okf commit

Create a new concept.

```bash
# Via flags
okf commit --title "Name" --type "Pattern" --content "Body text" --tags "a,b"

# Via JSON
okf commit --json '{"title": "Name", "type": "Pattern", "content": "Body", "tags": ["a"]}'

# Via file
okf commit --file concept.json

# With duplicate checking
okf commit --json '...' --check-duplicates
okf commit --json '...' --check-duplicates --force
```

**Options:**
| Flag | Description |
|------|-------------|
| `--title` | Concept title |
| `--type` | Concept type (required) |
| `--content` | Markdown body |
| `--tags` | Comma-separated tags |
| `--json` | JSON string with all fields |
| `--file` | Path to JSON file |
| `--path` | Target subdirectory |
| `--check-duplicates` | Warn if similar concepts exist |
| `--force` | Commit despite duplicates |

**Multi-bundle:**
```bash
okf -b team commit --json '...'       # Write to team bundle
okf -b personal commit --json '...'   # Write to personal bundle
okf commit --json '...'               # Write to the default bundle
```

---

## okf update \<concept-id\>

Update an existing concept.

```bash
okf update patterns/retry --title "New Title"
okf update patterns/retry --json '{"content": "Updated body"}'
```

Only specified fields are modified; others are preserved.

---

## okf delete \<concept-id\>

Remove a concept and clean up index/graph entries.

```bash
okf delete patterns/old-pattern
```

---

## okf list

List concepts with optional filters.

```bash
okf list
okf list --type "Pattern"
okf list --tags "reliability,performance"
okf list --since 2026-01-01
okf list --path patterns/
okf list --limit 10
```

Filters combine with AND logic.

---

## okf show \<concept-id\>

Display a concept's full content.

```bash
okf show patterns/retry-with-backoff
okf --format brief show patterns/retry-with-backoff  # frontmatter only
okf --format json show patterns/retry-with-backoff   # structured JSON
```

---

## okf fetch \<query\>

Search the bundle using hybrid (keyword + semantic), pure semantic, or pure keyword mode.

```bash
okf fetch "handling network failures"
okf fetch "auth patterns" --top-n 10 --threshold 0.3
okf fetch "database" --type "Pattern" --tags "performance"
okf fetch "retry" --mode keyword       # BM25 full-text only
okf fetch "resilience" --mode semantic  # Vector cosine only
```

**Options:**
| Flag | Description |
|------|-------------|
| `--top-n` | Max results (default: 5) |
| `--threshold` | Min similarity score (0.0–1.0) |
| `--type` | Filter by type |
| `--tags` | Filter by tags (comma-separated) |
| `--mode` | `hybrid` (default), `semantic`, or `keyword` |

**Search modes:**
- **hybrid** — merges BM25 keyword scores (40%) with vector cosine similarity (60%). Best for most queries.
- **semantic** — pure vector cosine similarity. Good for natural language queries where exact terms don't matter.
- **keyword** — pure BM25 full-text search via SQLite FTS5. Good for exact term lookups. Does not load the embedding model.

**Multi-bundle:** By default, searches all configured bundles and merges results by score. Each result includes a `bundle` field showing its source. Use `-b` to search a single bundle.

---

## okf links \<concept-id\>

Show link graph (inbound + outbound).

```bash
okf links patterns/retry
okf links patterns/retry --direction out
okf links patterns/retry --depth 2
```

**Options:**
| Flag | Description |
|------|-------------|
| `--direction` | `in`, `out`, or `both` (default: both) |
| `--depth` | BFS depth 1–10 (default: 1) |

---

## okf lint

Validate bundle for OKF compliance.

```bash
okf lint
okf lint --warn-only
okf lint --path patterns/
okf lint --rule frontmatter
okf --format json lint  # CI-friendly output
```

**Options:**
| Flag | Description |
|------|-------------|
| `--warn-only` | Always exit 0 |
| `--path` | Validate only this subdirectory |
| `--rule` | `frontmatter`, `structure`, `links`, or `types` |

**Exit codes:** 0 = clean (or `--warn-only`), 1 = errors found.

---

## okf reindex

Rebuild the vector index.

```bash
okf reindex          # Incremental (only changed files)
okf reindex --full   # Full rebuild from scratch
okf reindex --lint   # Validate during reindex
```

---

## okf stats

Bundle health metrics.

```bash
okf stats
```

Shows: concept count, type/tag distribution, link density, orphans, index freshness.

---

## okf skills

List installed skill packs.

```bash
okf skills
```
