# okf-tools

A companion CLI and library for working with [OKF](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md) bundles — filling the gaps that the spec intentionally leaves open.

**What it does:** Makes OKF knowledge bundles queryable, navigable, and agent-friendly via semantic search, link graph traversal, compliance linting, and progressive disclosure.

## Quick Start

```bash
pip install okf-tools

# Initialise a bundle
cd my-knowledge-repo
okf init

# Create a concept
okf commit --title "Retry Pattern" --type "Pattern" --content "Use exponential backoff for transient failures." --tags "reliability,networking"

# Search it
okf fetch "how to handle network failures"

# Validate compliance
okf lint
```

## What You Get

| Command | Purpose |
|---------|---------|
| `okf init` | Initialise a new OKF bundle |
| `okf commit` | Create a new concept |
| `okf fetch <query>` | Semantic search |
| `okf show <id>` | Display a concept |
| `okf list` | Browse concepts (filterable) |
| `okf update <id>` | Modify a concept |
| `okf delete <id>` | Remove a concept |
| `okf links <id>` | Navigate the link graph |
| `okf lint` | Validate OKF compliance |
| `okf reindex` | Rebuild the vector index |
| `okf stats` | Bundle health metrics |
| `okf skills` | List installed skill packs |

All commands support `--format json|text|brief`. Output is JSON when piped (agent-friendly), text when interactive.

## Key Design Decisions

- **Markdown files are the source of truth** — the vector index is a derived sidecar, gitignored and rebuildable
- **Local embeddings** — fastembed + BAAI/bge-small-en-v1.5, no API keys needed
- **Incremental indexing** — only re-embeds changed files
- **Link graph** — parse markdown links between concepts for backlink/neighborhood queries
- **Compliance-first** — `okf lint` validates structure, links, types, and frontmatter
- **Extensible** — drop-in skill packs for domain-specific agent guidance

## Documentation

- [Getting Started](docs/getting-started.md)
- [CLI Reference](docs/cli-reference.md)
- [Architecture](docs/architecture.md)
- [Writing Skill Packs](docs/skills.md)
- [For Agent Authors](docs/for-agent-authors.md)

## Development

```bash
git clone <repo-url>
cd okf-tools
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## License

Apache 2.0
