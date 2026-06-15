# Agent Prompt: Build `okf-tools`

## Project Identity

**Name:** okf-tools  
**Tagline:** A companion CLI and library for working with OKF bundles — filling the gaps that the spec intentionally leaves open.  
**Repo location:** `/home/hdean/development/okf-tools` (fresh repo, create from scratch)  
**License:** Apache 2.0  
**Language:** Python 3.9+  
**Tone:** Professional casual. Written by a developer who's genuinely excited about making AI agent workflows better. Clear, opinionated where it matters, never corporate.

---

## What This Project Is

Google's Open Knowledge Format (OKF v0.1, published June 12 2026) is an open specification for representing knowledge as a directory of markdown files with YAML frontmatter. It defines how to structure, link, and version knowledge so both humans and AI agents can produce and consume it.

OKF deliberately leaves several things as non-goals:
- No search/query infrastructure
- No prescribed storage or serving
- No tooling requirements
- No taxonomy enforcement

**okf-tools fills those gaps.** It's a general-purpose companion toolkit that makes OKF bundles queryable, navigable, and agent-friendly — without coupling to any specific domain, codebase, or vendor.

---

## What OKF Is (Context for the Agent)

The full OKF v0.1 spec lives at: https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md

Key points:
- A **Knowledge Bundle** is a directory tree of `.md` files
- Each `.md` file is a **Concept** — YAML frontmatter + markdown body
- Only one field is required: `type` (a short string like "Bug Fix", "Pattern", "API Endpoint")
- Optional standard fields: `title`, `description`, `resource`, `tags` (YAML list), `timestamp` (ISO 8601)
- Producers can add any extra YAML keys they want
- Concepts link to each other via standard markdown links (absolute from bundle root with `/` or relative with `./`)
- `index.md` files provide progressive disclosure (directory listings)
- `log.md` files provide chronological change history
- Bundles live in git repos for versioning, diffs, blame, and collaboration
- OKF is NOT tied to any cloud, database, model provider, or agent framework

---

## What okf-tools Must Provide

### Core Capabilities

1. **Semantic Search over OKF bundles**
   - Embed all concept bodies using a local embedding model (fastembed, BAAI/bge-small-en-v1.5, 384 dimensions)
   - Store embeddings in a sidecar index (sqlite-vec) that is gitignored and rebuildable
   - Query: given natural language, return the top-N most relevant concepts by cosine similarity
   - The vector index is a **derived artifact** — the .md files are always the source of truth

2. **Concept Authoring (commit)**
   - Create new OKF-compliant concept files from structured input (JSON or individual args)
   - Auto-generate slug filenames from title
   - Place in appropriate subdirectory based on type or user specification
   - Auto-update the parent `index.md`
   - Optionally auto-run `git add`
   - Duplicate detection: embed proposed content and check for similar existing concepts

3. **Concept Management (update, delete, list)**
   - Update: edit frontmatter and/or body of an existing concept, re-embed
   - Delete: remove concept file, update index, remove from vector index
   - List: enumerate concepts with filtering by type, tags, path, or date

4. **Graph Traversal**
   - Parse all markdown links between concepts to build a link graph
   - Query: "what links to this concept?" (backlinks/cited-by)
   - Query: "what does this concept link to?" (outlinks/references)
   - Query: "show me the neighborhood" (concepts within N hops)
   - This enables agents to navigate the knowledge graph without loading everything into context

5. **Index Synchronisation**
   - Detect new/changed/deleted .md files since last index build
   - Incremental re-embedding (only changed files)
   - Full rebuild command for fresh clones or corruption recovery
   - File watcher mode (optional) for live development

6. **Progressive Disclosure for Agents**
   - A "summarise" command that returns just frontmatter (title, description, type, tags) for a set of concepts without the full body
   - Allows agents to scan what's available before choosing what to read in full
   - Respects the OKF `index.md` pattern — use existing index files when available

7. **Bundle Statistics**
   - Concept count, type distribution, tag distribution
   - Link graph density (average links per concept, orphan concepts)
   - Index freshness (last rebuild, concepts pending re-embed)
   - Bundle size on disk

8. **Bundle Validation & Linting**
   - Validate entire bundles for OKF compliance after the fact
   - Structural checks: every directory with concepts has an index.md, no orphaned entries
   - Link integrity: report broken internal markdown links proactively
   - Type consistency: detect near-duplicate type values (case, hyphenation, whitespace variants)
   - Configurable strictness: `strict` (requires title+description), `standard` (OKF minimum), `relaxed` (permissive)
   - CI-friendly output: JSON diagnostics with file, rule, severity, message
   - Integration with reindex via `--lint` flag
   - Per-rule and per-path filtering for targeted validation

### Modular Skills System

The tool must support **drop-in skill packs** — additional steering files and hooks that extend its behaviour for specific domains without modifying the core tool.

Design:
- A skill pack is a directory containing one or more `.md` steering files and optionally `.kiro.hook` JSON files
- okf-tools ships a default skill: `core-knowledge.md` (general OKF usage rules for agents)
- Users add domain-specific skills by dropping them into a configurable directory (default: `.kiro/steering/` in the target project, or a `skills/` dir in the okf-tools install)
- The tool provides an `okf-skills` command to list installed skills and their descriptions
- Example skills that could be created (but are NOT part of this repo):
  - `genero-tools.md` — integrates structural codebase queries alongside knowledge fetches
  - `code-review.md` — guides agents to fetch patterns before reviewing PRs
  - `incident-response.md` — guides agents to fetch runbooks and past incidents

This means okf-tools is **domain-agnostic** by default but **domain-aware** when skills are installed.

---

## CLI Interface Design

Commands should be short, memorable, and consistent. Use `okf` as the single entry point with subcommands:

```
okf fetch <query>              # Semantic search (default top-5)
okf commit                     # Create a new concept (interactive or --json/--file)
okf update <concept-id>        # Update an existing concept
okf delete <concept-id>        # Delete a concept
okf list                       # List concepts (filterable)
okf show <concept-id>          # Display a concept's full content
okf links <concept-id>         # Show link graph (inbound + outbound)
okf reindex                    # Rebuild the vector index
okf lint                       # Validate bundle for OKF compliance
okf stats                      # Bundle statistics
okf skills                     # List installed skill packs
okf init                       # Initialise a new OKF bundle in cwd
```

Where `<concept-id>` is the file path within the bundle minus the `.md` extension (per the OKF spec definition of Concept ID).

### Output formats
All commands support `--format json|text|brief` for machine and human consumption. Default is `text` for interactive use, `json` when stdout is not a TTY (agent-friendly).

### Key flags
```
okf fetch <query> [--top-n N] [--threshold T] [--type TYPE] [--tags tag1,tag2]
okf commit --json '{...}' | --file path.json | --title "..." --content "..." --type "..." --tags "..."
okf commit --check-duplicates [--force]
okf list [--type TYPE] [--tags tag1,tag2] [--since YYYY-MM-DD] [--limit N] [--path subdir/]
okf links <concept-id> [--depth N] [--direction in|out|both]
okf reindex [--full] [--lint]
okf lint [--warn-only] [--path subdir/] [--rule frontmatter|structure|links|types]
```

---

## Configuration

Config file: `.okf/config.json` in the bundle root, or `~/.config/okf/config.json` for user-level defaults.

```json
{
  "bundle_path": ".",
  "index_path": ".okf/index",
  "embedding_model": "BAAI/bge-small-en-v1.5",
  "default_top_n": 5,
  "similarity_threshold": 1.0,
  "auto_git_add": true,
  "skills_paths": [".kiro/steering/", "~/.config/okf/skills/"],
  "validation_level": "standard"
}
```

The `.okf/` directory is the tool's workspace within a bundle — contains the vector index, config, and any derived data. It should be gitignored.

---

## Technical Architecture

```
okf-tools/
├── pyproject.toml
├── README.md
├── CONTRIBUTING.md
├── LICENSE
├── docs/
│   ├── getting-started.md
│   ├── cli-reference.md
│   ├── architecture.md
│   ├── skills.md
│   └── for-agent-authors.md
├── src/
│   └── okf_tools/
│       ├── __init__.py
│       ├── cli.py              # Click-based CLI (single `okf` entry point)
│       ├── bundle.py           # OKF bundle I/O: parse frontmatter, read/write concepts, manage index.md
│       ├── search.py           # Vector index: embed, store, query (fastembed + sqlite-vec)
│       ├── graph.py            # Link graph: parse md links, build adjacency, traversal queries
│       ├── service.py          # Orchestration: commit, fetch, update, delete workflows
│       ├── config.py           # Configuration loading and validation
│       ├── sync.py             # Index synchronisation and incremental rebuild
│       ├── validation.py      # Bundle-wide OKF compliance checking and linting
│       ├── skills.py           # Skill pack discovery and listing
│       └── errors.py           # Error hierarchy
├── skills/
│   └── core-knowledge.md      # Default steering: general OKF usage rules for agents
├── tests/
│   ├── __init__.py
│   ├── test_bundle.py
│   ├── test_search.py
│   ├── test_graph.py
│   ├── test_service.py
│   └── fixtures/
│       └── sample_bundle/      # A minimal OKF bundle for testing
└── .gitignore
```

### Dependencies

```
fastembed          # Local embeddings (ONNX, CPU-only, no API keys)
sqlite-vec         # Vector similarity search in SQLite
click              # CLI framework (cleaner than argparse for subcommands)
pyyaml             # YAML frontmatter parsing
python-frontmatter # Convenient frontmatter+body parsing for .md files
```

Dev dependencies:
```
pytest
```

### Key Design Decisions

1. **Single `okf` command** — not multiple `okf-fetch`, `okf-commit` binaries. Subcommands under one entry point.
2. **Vector index is a sidecar** — gitignored, rebuildable, never the source of truth. The .md files ARE the data.
3. **Incremental indexing** — track file mtimes, only re-embed what changed. Full rebuild available as fallback.
4. **No database for concepts** — concepts live as files. The only database is the vector index for search.
5. **python-frontmatter for parsing** — handles the `---` delimited YAML + body pattern cleanly.
6. **Click for CLI** — gives us subcommands, help text, type validation, and shell completion for free.
7. **Auto-detect TTY** — output JSON when piped (agent use), text when interactive (human use).
8. **Concept ID = relative file path minus .md** — per OKF spec. This is the universal identifier.

---

## Behavioural Requirements

### Commit workflow
1. Validate input (title, content, type are required; tags recommended)
2. Generate filename slug from title (lowercase, hyphens, max 60 chars)
3. Determine target directory (from type mapping in config, or explicit `--path`)
4. Check for duplicates if `--check-duplicates` flag set (embed content, search, warn if similar)
5. Write the .md file with proper frontmatter
6. Update the parent directory's `index.md` (add entry)
7. Embed the new content and add to vector index
8. If `auto_git_add` is true, run `git add <file>`
9. Output the concept ID

### Fetch workflow
1. Load/verify vector index is current (rebuild if stale)
2. Embed the query text
3. Search the index with cosine similarity
4. Filter results by optional type/tag constraints
5. Return results with: concept ID, title, score, snippet (first ~200 chars of body)
6. Agents can then `okf show <id>` to read the full concept

### Graph traversal
1. On reindex, also scan all .md files for markdown links to other concepts
2. Build an in-memory adjacency list (or persist in the sidecar DB)
3. `okf links <id>` returns both inbound (who links here) and outbound (what this links to)
4. `--depth N` does BFS to show the neighborhood

### Index sync
1. Walk the bundle directory, collect all .md files (excluding index.md, log.md)
2. Compare file paths + mtimes against the index metadata
3. For new/modified files: re-parse frontmatter, re-embed body, update index
4. For deleted files: remove from index
5. Persist last-sync timestamp

### Lint workflow
1. Walk the bundle, parse all concept files
2. Run frontmatter validation on each concept (respecting validation_level)
3. Check structural conventions (index.md presence, entry consistency)
4. Check link integrity (all internal links resolve to existing files)
5. Check type consistency (detect near-duplicate type values)
6. Aggregate diagnostics with file, rule, severity, message
7. Output results in the active format (JSON for CI, text for humans)
8. Exit 0 if clean or --warn-only, exit 1 if errors found

---

## Documentation Requirements

The project needs clear, human-friendly docs:

1. **README.md** — what it is, why it exists, quick start (install + first query), link to full docs
2. **CONTRIBUTING.md** — how to set up dev environment, run tests, code style, PR guidelines
3. **docs/getting-started.md** — install, init a bundle, commit your first concept, search it
4. **docs/cli-reference.md** — every command with examples
5. **docs/architecture.md** — how the pieces fit together, data flow, design decisions
6. **docs/skills.md** — how to write and install skill packs
7. **docs/for-agent-authors.md** — how to integrate okf-tools into agent steering files and hooks

All docs written in the same professional casual tone. Concise, practical, code examples over paragraphs of explanation.

---

## Sample Skill Pack (ships with the tool)

`skills/core-knowledge.md`:
```markdown
---
inclusion: auto
---

# OKF Knowledge Integration

You have access to an OKF knowledge bundle via the `okf` CLI. Use it to persist and retrieve learnings across interactions.

## When to Fetch
- At the start of each interaction, run `okf fetch "<brief description of task>"` to check for relevant prior knowledge.
- Before architectural decisions, check for existing rationale.
- When encountering unfamiliar patterns, search first.

## When to Commit
- After discovering a significant bug fix, pattern, or decision.
- Always check for duplicates first: `okf commit --check-duplicates --json '{...}'`

## When to Navigate
- Use `okf links <concept-id>` to explore related concepts.
- Use `okf list --type "Pattern"` to browse available patterns.
- Use `okf show <concept-id>` to read a full concept before acting on it.

## When to Lint
- After bulk operations (multiple commits, imports, or restructuring), run `okf lint` to verify bundle integrity.
- Before completing a task that modified the knowledge bundle, run `okf lint --path <affected-dir>` on changed directories.
- Treat lint errors as blockers — fix them before considering the task complete.

## Command Quick Reference
```
okf fetch "query"               # Semantic search
okf commit --json '{...}'       # Create concept
okf show <concept-id>           # Read full concept
okf links <concept-id>          # See connections
okf list [--type X] [--tags Y]  # Browse
okf lint                        # Validate compliance
okf stats                       # Bundle health
```
```

---

## What NOT to Build

- No web UI or server component — this is a CLI/library tool
- No proprietary cloud integration — it works with plain files and git
- No domain-specific logic — that goes in skill packs
- No schema registry or type enforcement beyond OKF's own rules
- No replacement for git — versioning, collaboration, and audit all happen through git
- No direct competitor to Google's enrichment agent — that's a producer; we're a consumer/query tool

---

## Prior Art (what we learned from AKR)

The existing Agent Knowledge Repository (`/home/hdean/development/agent-knowledge-repository/`) demonstrated:

**What worked well:**
- CLI interface for agents (JSON in, JSON out)
- Semantic search via fastembed + sqlite-vec — fast, local, no API keys
- Duplicate detection before commits
- Steering files driving automatic knowledge fetch/commit by agents
- Integration alongside structural query tools (genero-tools) via a tiered workflow

**What to improve:**
- Binary SQLite storage → OKF markdown files (human-readable, git-friendly)
- Custom audit trail → git history (more powerful, zero maintenance)
- Flat artifact list → graph of linked concepts (richer relationships)
- Multiple CLI binaries (akr-fetch, akr-commit, etc.) → single `okf` command with subcommands
- No progressive disclosure → index.md + summarise command
- Monolithic design → modular skills for domain-specific extensions
- argparse → Click (better UX, auto-completion, cleaner code)

---

## Success Criteria

The tool is done when:

1. A fresh user can `pip install okf-tools`, run `okf init`, commit a concept, and search for it in under 2 minutes
2. An AI agent can use `okf fetch` and `okf commit` via steering files with zero human intervention
3. The vector index rebuilds incrementally in under 1 second for bundles with <1000 concepts
4. The link graph is queryable and helps agents navigate without loading the entire bundle into context
5. A domain-specific skill pack can be dropped in without modifying any okf-tools code
6. All documentation is clear enough that a contributor can submit a PR without asking questions about setup
7. The tool adds zero runtime dependencies for anyone who just wants to *read* the OKF bundle manually — it only adds value through search and graph traversal

---

## Implementation Order

Build in this sequence for a working tool at each step:

1. **Project scaffold** — pyproject.toml, directory structure, basic CLI shell with Click
2. **Bundle parsing** — read .md files, parse frontmatter, represent concepts in memory
3. **Commit command** — create new concept files, generate slugs, update index.md
4. **Vector index** — embed concepts, store in sqlite-vec sidecar, incremental sync
5. **Fetch command** — semantic search over the index
6. **Show/list commands** — browse and display concepts
7. **Graph module** — parse links, build adjacency, backlinks query
8. **Links command** — expose graph traversal via CLI
9. **Validation module** — lint command, structural checks, link integrity, type consistency
10. **Stats command** — bundle health metrics
11. **Skills system** — discovery and listing of installed skill packs
12. **Documentation** — README, getting-started, cli-reference, contributing
13. **Tests** — unit tests for each module with a fixture bundle

---

## Environment Notes

- OS: Linux
- Python: 3.9+ (must work without 3.13-only features)
- Shell: bash
- The developer uses Kiro IDE with steering files and hooks
- Other tools in the ecosystem that will pair with okf-tools (via skill packs, not hard coupling):
  - genero-tools — structural codebase analysis for Genero/4GL
  - System documentation files — business logic docs stored as markdown
  - These integrations are NOT part of okf-tools itself — they're skill pack examples

---

## Multi-Bundle Architecture

okf-tools supports multiple named bundles configured at `~/.config/okf/config.json`:

```json
{
  "bundles": [
    {"name": "personal", "path": "~/personal/my-okf"},
    {"name": "team", "path": "/shared/team-okf", "default": true}
  ]
}
```

### Key behaviours:

- **All bundles are writable by default.** `"writable": false` is an opt-in lock for reference bundles.
- **`okf fetch` searches ALL bundles** and merges results by score. Each result has a `bundle` field.
- **`okf commit` writes to the default bundle** unless `--bundle / -b` is specified.
- **`okf -b <name>` targets a specific bundle** for any command (placed before the subcommand).
- **`okf init --register --name <name>`** initialises a bundle and adds it to user config.
- **Duplicate checking spans all bundles** — avoids redundant commits across personal/team.
- **Each bundle has its own sidecar index** at `<bundle_path>/.okf/index/okf.db`.
- **Shared bundles sync via git** — commit/push/pull like any repo. The index is gitignored.

### Config resolution:

1. Project-level bundles (from `.okf/config.json` in cwd ancestors) — highest priority
2. User-level bundles (from `~/.config/okf/config.json`)
3. Legacy single-bundle fallback (backward compat with old `bundle_path` field)
