# CLI Reference

All commands support `--format json|text|brief`. Output is JSON when piped, text when interactive.

## okf init

Initialise a new OKF bundle in the current directory.

```bash
okf init
```

Creates `.okf/config.json`, root `index.md`, and updates `.gitignore`.

## okf commit

Create a new concept.

```bash
okf commit --json '{
  "title": "My Concept",
  "type": "Pattern",
  "content": "Description...",
  "tags": ["tag1", "tag2"]
}'
```

Options:
- `--title`, `--content`, `--type`, `--tags` — individual field flags
- `--json` — JSON string with all fields
- `--file` — path to JSON file
- `--path` — target subdirectory
- `--check-duplicates` — warn if similar concepts exist (recommended)
- `--force` — commit even if duplicates found
- `--dry-run` — show what would be committed without writing

**Linking:** Use standard markdown links (`[Display Text](concept-id.md)`) in content to connect concepts.

## okf fetch \<query\>

Search the bundle using natural language.

```bash
okf fetch "how to handle network failures"
okf fetch "retry" --mode keyword
okf fetch "resilience" --mode semantic --top-n 10
```

Options:
- `--top-n` — number of results (default: 5)
- `--threshold` — minimum similarity score (0.0-1.0)
- `--type` — filter by concept type
- `--tags` — filter by tags (comma-separated)
- `--mode` — `hybrid` (default), `semantic`, or `keyword`

## okf show \<concept-id\>

Display a concept's full content.

```bash
okf show retry-pattern
okf --format brief show retry-pattern  # frontmatter only
```

## okf list

List concepts with optional filtering.

```bash
okf list
okf list --type "Pattern" --tags "reliability"
okf list --since 2025-01-01 --limit 10
okf --format brief list
```

Options:
- `--type` — filter by type
- `--tags` — filter by tags (comma-separated)
- `--since` — filter by date (ISO 8601)
- `--limit` — max results
- `--path` — filter by subdirectory

## okf update \<concept-id\>

Update an existing concept's fields.

```bash
okf update retry-pattern --content "Updated description..."
okf update retry-pattern --json '{"tags": ["new-tag"]}'
```

## okf delete \<concept-id\>

Remove a concept.

```bash
okf delete old-concept
```

## okf reindex

Rebuild the vector index.

```bash
okf reindex        # incremental (only changed files)
okf reindex --full # full rebuild from scratch
```

## okf stats

Show bundle statistics.

```bash
okf stats
```

Returns: concept count, type/tag distributions, last reindex time, pending re-embedding count.
