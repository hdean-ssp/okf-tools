# Architecture

## Overview

okf-tools is a layered Python application:

```
CLI (cli.py) → Service (service.py) → Domain Modules
```

The CLI is a thin Click shell. The service layer orchestrates workflows. Domain modules own their data and logic.

## Components

okf-tools has two distinct layers. The core layer implements OKF operations; the integration layer adds agent/IDE workflow support.

### Layer Separation

| Layer | Modules | Purpose |
|-------|---------|---------|
| **Core (OKF tooling)** | `bundle.py`, `search.py`, `graph.py`, `sync.py`, `validation.py`, `config.py` | Parse, write, search, lint, and index OKF-compliant markdown files |
| **Integration (agent framework)** | `skills.py`, `cli.py` (hooks/steering support), install script | Multi-bundle routing, skill discovery, steering files, IDE hooks, progressive disclosure |

The core layer has no opinions about agents or IDEs. It works with files, embeddings, and a link graph. The integration layer wraps it with conventions for how agents should use the core.

### Module Detail

| Module | Responsibility |
|--------|---------------|
| `cli.py` | Click commands, output formatting, TTY detection |
| `service.py` | Workflow orchestration (commit, fetch, lint, etc.) |
| `bundle.py` | Parse/write OKF files, validate frontmatter, manage index.md |
| `search.py` | Hybrid search: vector index (sqlite-vec) + FTS5 keyword index, embeddings (fastembed) |
| `graph.py` | Link parsing (markdown links), adjacency storage, BFS traversal |
| `sync.py` | Change detection, incremental/full reindexing |
| `validation.py` | Bundle-wide compliance checks (lint) |
| `config.py` | Configuration loading and merging |
| `skills.py` | Skill pack discovery |
| `errors.py` | Typed exception hierarchy |

## Data Flow

### Commit

```
Input → validate → generate slug → write .md → update index.md → embed → upsert vector → update graph → git add
```

### Fetch (Search)

```
Query → [hybrid mode] → BM25 keyword search (FTS5) + embed query → vector cosine search → normalize scores → merge (60% semantic + 40% keyword) → filter by type/tags → return results
```

Modes: `hybrid` (default), `semantic` (vector only), `keyword` (BM25 only).

### Lint

```
Walk bundle → validate each concept's frontmatter → check structure (index.md) → check link integrity → check type consistency → report
```

### Reindex

```
Detect changes (mtime comparison) → parse changed files → batch embed → upsert vectors → rebuild links → persist timestamp
```

## Storage

**Source of truth:** `.md` files on disk (git-tracked).

**Derived sidecar:** `.okf/index/okf.db` — a SQLite database containing:
- `concepts` table (metadata for filtering)
- `vec_concepts` virtual table (384-dim embeddings via sqlite-vec)
- `fts_concepts` virtual table (FTS5 full-text index for BM25 keyword search)
- `links` table (concept-to-concept edges)
- `sync_meta` table (last sync timestamp)

The sidecar is gitignored. Run `okf reindex --full` to rebuild from scratch.

## Configuration Precedence

1. Built-in defaults (always present)
2. User config (`~/.config/okf/config.json`) overrides defaults
3. Bundle config (`.okf/config.json`) overrides user config

Merge is per-field — partial configs work fine.

## Design Decisions

1. **Files as data** — no database for concepts. Git provides versioning, blame, and collaboration.
2. **Hybrid search** — BM25 keyword matching catches exact terms; vector cosine catches semantic meaning. Combined by default (60/40 weighting), with pure modes available via `--mode`.
3. **Lazy model loading** — the embedding model only loads when a command needs it (fetch in semantic/hybrid mode, commit, reindex). List, show, lint, stats, and keyword-only fetch never touch it.
4. **Single SQLite file** — vector index + FTS index + link graph share one database for simplicity.
5. **Compliance as infrastructure** — lint isn't an afterthought; it's woven into reindex, steering files, and the default skill pack.
6. **Multi-bundle by design** — supports personal + shared team bundles. Each bundle is independent (own sidecar index), but the tool aggregates search across all and routes writes to the appropriate one.

## Extensions Beyond OKF

okf-tools is OKF v0.1 compatible but extends the spec in several ways. These extensions are additive — a pure OKF reader can still parse the files — but they enable features not covered by the spec.

| Extension | What it adds | OKF spec says |
|-----------|-------------|---------------|
| Wikilink parsing (fallback) | `[[concept-id]]` in body text is parsed as a graph edge — not promoted but handled gracefully if agents produce it | Spec only recognises standard markdown links (`[text](url.md)`) |
| FTS5 keyword index | Body text stored in sidecar for full-text keyword search | Spec says nothing about search |
| Sidecar database | `.okf/index/okf.db` stores embeddings, FTS, graph edges, sync metadata | Spec defines the `.okf/` directory but not its contents beyond config |
| Type consistency linting | Warns on near-duplicate types (e.g. "Bug Fix" vs "bug-fix") | Spec requires `type` field but doesn't constrain values |

**Note:** The graph module parses wikilinks as a fallback if they appear in content, but the recommended and spec-compliant way to link concepts is standard markdown links: `[Display Text](concept-id.md)`. Guides and steering files direct agents toward this syntax.

## Multi-Bundle Architecture

### Bundle Resolution

```
User config (~/.config/okf/config.json)
  └── bundles: [{name, path, writable?, default?}, ...]

Project config (.okf/config.json in cwd ancestors)
  └── bundles: [{name, path, writable?, default?}, ...]

Resolution: project bundles first, then user bundles (deduplicated by name)
```

### Per-Bundle Sidecar

Each bundle maintains its own sidecar index independently:

```
~/personal/my-okf/
├── index.md
├── concepts...
└── .okf/
    ├── config.json
    └── index/okf.db     ← this bundle's vector + FTS + graph

/shared/team-okf/
├── index.md
├── concepts...
└── .okf/
    ├── config.json
    └── index/okf.db     ← this bundle's vector + FTS + graph
```

### Aggregated Search

`okf fetch` queries each bundle's index in turn, collects results, tags them with the source bundle name, and merges by score descending. The output `bundle` field on each result tells the consumer where it came from.

### Write Routing

Write commands (commit, update, delete) target:
1. The bundle specified by `--bundle / -b` if provided
2. The bundle marked `"default": true` in config
3. The first bundle in the list if no default is set

All bundles are writable by default. Setting `"writable": false` is an opt-in lock for reference bundles.

### Sharing via Git

Shared team bundles are regular git repos. Team members:
1. Clone the bundle repo
2. Register it in their user config (`okf init --register`)
3. Commit knowledge (`okf commit`)
4. Push/pull to sync with teammates

The `.okf/index/` sidecar is gitignored — each user rebuilds their own local index via `okf reindex`.
