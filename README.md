# okf-tools

Local semantic search over [OKF](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md) knowledge bundles. No API keys, no cloud services.

**Why it exists:** Engineers waste hours rediscovering knowledge that already exists — scattered across wikis, Slack, git history, and colleagues' heads. OKF defines a vendor-neutral format (published by Google Cloud Platform) for persisting that knowledge as markdown; okf-tools makes it queryable and useful in practice. OKF defines the format; okf-tools provides the tooling layer.

Write markdown files with YAML frontmatter → okf-tools makes them queryable via hybrid search (BM25 keyword + vector cosine similarity).

## Quick Start

```bash
# Install (requires Python 3.9+)
git clone https://github.com/hdean-ssp/okf-tools.git
cd okf-tools
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

# Create a bundle
mkdir ~/my-knowledge && cd ~/my-knowledge
git init && okf init

# Add a concept
okf commit --check-duplicates --json '{
  "title": "Retry Pattern",
  "type": "Pattern",
  "content": "Use exponential backoff with jitter for transient failures.",
  "tags": ["reliability", "networking"]
}'

# Build search index (first run downloads ~30MB embedding model)
# Note: first run takes ~30 seconds to download the model. Subsequent runs are instant.
okf reindex

# Search
okf fetch "how to handle network failures"
```

## What Next?

After completing the Quick Start above:

- `okf fetch "your question"` — search your bundle with natural language
- `okf list` — browse all concepts
- `okf show <concept-id>` — view full concept content
- `okf stats` — check bundle health
- See [Use Cases & Examples](docs/use-cases.md) for real-world workflows
- See [Getting Started](docs/getting-started.md) for the full guide

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
- [Use Cases & Examples](docs/use-cases.md)
- [Metrics & Impact Measurement](docs/metrics.md)
- [Validation Checklist](docs/validation-checklist.md)
- [Proof Point Summary](PROOF_POINT.md)

## Development

```bash
git clone https://github.com/hdean-ssp/okf-tools.git
cd okf-tools
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Branches

- **`main`** — core tool (this branch). Focused on the essential loop: init → commit → fetch → reindex.
- **`ssp-full`** — extended version with multi-bundle support, link graph traversal, compliance linting, skills system, and Kiro-specific install script.

## License

Apache 2.0
