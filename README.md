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

## MCP Server

okf-tools includes an MCP (Model Context Protocol) server, letting any MCP-compatible client (Kiro, Claude Desktop, etc.) use your knowledge bundle directly.

### Quick Start — MCP Server

```bash
# Start the server (from within your bundle directory)
okf-mcp

# Or point to a specific bundle
okf-mcp --bundle-path ~/my-knowledge
```

The server communicates over stdio (JSON-RPC). You don't run it manually for normal use — instead, configure your MCP client to launch it.

### Client Configuration

**Team/Shared Deployment** (recommended — see [Team Setup Guide](docs/team-setup.md)):

Create `~/.kiro/settings/mcp.json` on the server:

```json
{
  "mcpServers": {
    "okf-tools": {
      "command": "/home/electra/trunk/m3/castle_sdx/etc/okf-tools/.venv/bin/okf-mcp",
      "args": [
        "--bundle-path",
        "/home/electra/trunk/m3/castle_sdx/etc/team-okf"
      ],
      "autoApprove": [
        "commit_concept", "delete_concept", "fetch_concepts",
        "get_stats", "init_bundle", "list_concepts",
        "reindex", "show_concept", "update_concept"
      ]
    }
  }
}
```

**Kiro via Remote-SSH** (generic setup — Kiro connects to server, MCP runs locally on server):

```json
{
  "mcpServers": {
    "okf-tools": {
      "command": "/path/to/okf-tools/.venv/bin/okf-mcp",
      "args": ["--bundle-path", "/path/to/your/bundle"]
    }
  }
}
```

**Local setup** (Kiro and bundle on same machine):

```json
{
  "mcpServers": {
    "okf-tools": {
      "command": "okf-mcp",
      "args": ["--bundle-path", "/path/to/your/bundle"]
    }
  }
}
```

See [MCP Setup Guide](docs/mcp-setup.md) for individual installation or [Team Setup Guide](docs/team-setup.md) for onboarding to the shared deployment.

### Available Tools

| Tool | Description |
|------|-------------|
| `init_bundle` | Create a new bundle at a given path |
| `commit_concept` | Add a new concept (title, type, content, tags) |
| `update_concept` | Modify fields on an existing concept |
| `delete_concept` | Remove a concept |
| `fetch_concepts` | Semantic/hybrid search with natural language |
| `list_concepts` | Browse concepts with filters (type, tags, date, path) |
| `show_concept` | Get full content of a concept |
| `reindex` | Rebuild the vector search index |
| `get_stats` | Bundle health statistics |

### Notes

- The server starts without a bundle configured — use `init_bundle` to create one, or pass `--bundle-path`
- All tools except `init_bundle` require a configured bundle
- Errors are returned as structured MCP tool errors (no stack traces exposed)
- All logging goes to stderr (stdout is the JSON-RPC channel)

## Agent Integration

The MCP server handles agent integration directly — no hooks or CLI wrappers needed.

- `agent/AGENT.md` — agent usage guide (when to use, MCP tools reference, workflow pattern)

Agents access the knowledge bundle through MCP tools (`fetch_concepts`, `commit_concept`, etc.) rather than shelling out to CLI commands.

## Documentation

- [Team Setup Guide](docs/team-setup.md) — onboarding for the shared deployment
- [MCP Setup Guide](docs/mcp-setup.md) — individual installation and troubleshooting
- [Getting Started](docs/getting-started.md) — CLI quick start
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

Dev dependencies include `pytest`, `hypothesis` (property-based testing), and `pytest-asyncio`.

## Branches

- **`main`** — core CLI tool. Focused on the essential loop: init → commit → fetch → reindex.
- **`mcp`** — adds the MCP server (`okf-mcp`) for use with Kiro, Claude Desktop, and other MCP clients.
- **`ssp-full`** — extended version with multi-bundle support, link graph traversal, compliance linting, skills system, and Kiro-specific install script.

## License

Apache 2.0
