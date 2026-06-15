# okf-tools (ssp-full)

> **This is the extended branch.** For the minimal core tool (init → commit → fetch → reindex), see the [`main` branch](https://github.com/hdean-ssp/okf-tools/tree/main).

A companion CLI and library for working with [OKF](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md) bundles — filling the gaps that the spec intentionally leaves open.

**What it does:** Makes OKF knowledge bundles queryable, navigable, and agent-friendly via semantic search, link graph traversal, compliance linting, multi-bundle collaboration, and progressive disclosure.

> **OKF-compatible with extensions:** Bundles produced by okf-tools are valid OKF v0.1. The tool adds features on top (hybrid search, FTS indexing, link graph) that don't break spec compliance. See [Architecture > Extensions Beyond OKF](docs/architecture.md#extensions-beyond-okf) for details.

## Quick Start

Requires **Python 3.9+** and **bash**.

```bash
# Clone and install (one-time setup)
git clone https://github.com/hdean-ssp/okf-tools.git -b ssp-full
cd okf-tools
./scripts/install-agent-support.sh ~/my-project
source ~/.bashrc

# Now 'okf' is available globally — initialise a bundle
cd ~/my-project
okf init

# Create a concept
okf commit --check-duplicates --json '{
  "title": "Retry Pattern",
  "type": "Pattern",
  "content": "Use exponential backoff for transient failures.",
  "tags": ["reliability", "networking"]
}'

# Build the search index (first run downloads ~30MB embedding model)
okf reindex

# Search it
okf fetch "how to handle network failures"

# Validate compliance
okf lint
```

The install script:
1. Creates a persistent venv at `~/.local/share/okf-tools/.venv`
2. Installs okf-tools into it
3. Adds the venv's `bin/` to your PATH in `~/.bashrc` (so `okf` works in every new shell, including agent sessions)
4. Installs steering files and hooks to the target workspace (or `~/.kiro` if no path given)

> **Manual install alternative:** If you prefer to manage your own venv: `python3 -m venv .venv && source .venv/bin/activate && pip install -e .`

## Agent Integration (Steering + Hooks)

The install script handles everything — it installs the CLI globally and sets up agent support in one command:

```bash
./scripts/install-agent-support.sh /path/to/your/project
```

Or for user-level (applies to all workspaces):

```bash
./scripts/install-agent-support.sh
```

This installs:
- **`steering/okf-knowledge.md`** — comprehensive guide for agents: when to use/not use, all commands, workflow patterns
- **`hooks/okf-prompt-fetch.json`** — points agents to the steering file on each prompt
- **`hooks/okf-post-task-lint.json`** — lints the bundle after task completion

The `okf` command is on PATH permanently (via `~/.bashrc`), so agents can call it in any fresh shell session without activating a venv.

## What You Get

| Command | Purpose |
|---------|---------|
| `okf init` | Initialise a new OKF bundle |
| `okf commit` | Create a new concept |
| `okf fetch <query>` | Hybrid search (BM25 + semantic) |
| `okf show <id>` | Display a concept |
| `okf list` | Browse concepts (filterable) |
| `okf update <id>` | Modify a concept |
| `okf delete <id>` | Remove a concept |
| `okf links <id>` | Navigate the link graph |
| `okf lint` | Validate OKF compliance |
| `okf reindex` | Rebuild the vector index |
| `okf stats` | Bundle health metrics |
| `okf skills` | List installed skill packs |

All commands support `--format json|text|brief`. Output is JSON when piped (agent-friendly), text when interactive. `okf commit` also supports `--dry-run` to preview without writing.

## Key Design Decisions

- **Markdown files are the source of truth** — the vector index is a derived sidecar, gitignored and rebuildable
- **Multi-bundle architecture** — personal + shared team bundles. All writable, all searchable. Agents commit to the team bundle by default; knowledge accumulates collaboratively via git
- **Hybrid search** — combines BM25 keyword matching with vector semantic similarity (no external services). Searches across all configured bundles
- **Local embeddings** — fastembed + BAAI/bge-small-en-v1.5, no API keys needed
- **Incremental indexing** — only re-embeds changed files
- **Link graph** — parse markdown links between concepts for backlink/neighborhood queries
- **Compliance-first** — `okf lint` validates structure, links, types, and frontmatter
- **Extensible** — drop-in skill packs for domain-specific agent guidance

## Multi-Bundle (Personal + Team)

okf supports multiple named bundles. Typical setup:

```json
// ~/.config/okf/config.json
{
  "bundles": [
    {"name": "personal", "path": "~/personal/my-okf"},
    {"name": "team", "path": "/shared/team-okf", "default": true}
  ]
}
```

- `okf fetch` searches ALL bundles — results tagged with source
- `okf commit` writes to the default bundle (team)
- `okf -b personal commit ...` writes to personal
- Shared bundles sync between teammates via git push/pull

See [Getting Started](docs/getting-started.md#multi-bundle-setup) for full setup guide.

## Documentation

- [Getting Started](docs/getting-started.md)
- [CLI Reference](docs/cli-reference.md)
- [Architecture](docs/architecture.md)
- [Writing Skill Packs](docs/skills.md)
- [For Agent Authors](docs/for-agent-authors.md)
- [Known Risks](docs/risks.md)

## Development

```bash
git clone https://github.com/hdean-ssp/okf-tools.git -b ssp-full
cd okf-tools
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Branches

- **`main`** — minimal core tool (init, commit, fetch, show, reindex). Best starting point for most users.
- **`ssp-full`** (this branch) — extended version with multi-bundle, link graph, lint, skills, steering, hooks, and the install script. Used internally at SSP.

## License

Apache 2.0
