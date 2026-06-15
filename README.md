# okf-tools

Local semantic search over [OKF](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md) knowledge bundles. No API keys, no cloud services.

Write markdown files with YAML frontmatter → okf-tools makes them queryable via hybrid search (BM25 keyword + vector cosine similarity).

## Quick Start

```bash
# Install
pip install -e .

# Create a bundle
mkdir my-knowledge && cd my-knowledge
git init && okf init

# Add a concept
okf commit --check-duplicates --json '{
  "title": "Retry Pattern",
  "type": "Pattern",
  "content": "Use exponential backoff with jitter for transient failures.",
  "tags": ["reliability", "networking"]
}'

# Build search index
okf reindex

# Search
okf fetch "how to handle network failures"
```

## Commands

| Command | Purpose |
|---------|---------|
| `okf init` | Initialise a new bundle |
| `okf commit` | Create a concept |
| `okf fetch <query>` | Hybrid search (BM25 + semantic) |
| `okf show <id>` | Display a concept |
| `okf list` | Browse concepts (filterable) |
| `okf update <id>` | Modify a concept |
| `okf delete <id>` | Remove a concept |
| `okf reindex` | Rebuild the vector index |
| `okf stats` | Bundle statistics |

All commands support `--format json|text|brief`. Output is JSON when piped (agent-friendly), text when interactive.

## How It Works

- **Markdown files are the source of truth** — the vector index is a derived sidecar, gitignored and rebuildable
- **Hybrid search** — combines BM25 keyword matching with vector semantic similarity. No external services.
- **Local embeddings** — fastembed + BAAI/bge-small-en-v1.5 (384 dimensions), no API keys
- **Incremental indexing** — only re-embeds changed files (mtime comparison)

## Agent Integration

The `agent/` directory contains IDE-agnostic guidance files for AI agents:

- `agent/AGENT.md` — full usage guide (when to use, commands, workflow pattern)
- `agent/hooks/` — hook definitions adaptable to Kiro, Cursor, Windsurf, etc.

See `agent/hooks/README.md` for setup instructions per IDE.

## Documentation

- [Getting Started](docs/getting-started.md)
- [CLI Reference](docs/cli-reference.md)

## Development

```bash
git clone https://github.com/hdean-ssp/okf-tools.git
cd okf-tools
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## License

Apache 2.0
