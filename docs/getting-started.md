# Getting Started

## Installation

```bash
git clone https://github.com/hdean-ssp/okf-tools.git
cd okf-tools
./scripts/install-agent-support.sh ~/my-project
source ~/.bashrc
```

This installs `okf` globally (via a persistent venv at `~/.local/share/okf-tools/`) and sets up steering + hooks in your workspace.

> **Manual alternative:** `python3 -m venv .venv && source .venv/bin/activate && pip install -e .`

## Initialise a Bundle

```bash
mkdir my-knowledge && cd my-knowledge
git init
okf init
```

This creates:
- `.okf/config.json` — configuration with sensible defaults
- `index.md` — root concept listing
- `.gitignore` entry for `.okf/index/` (the vector database)

## Commit Your First Concept

```bash
okf commit \
  --title "Retry with Exponential Backoff" \
  --type "Pattern" \
  --content "When network calls fail transiently, retry with doubling delays and jitter." \
  --tags "reliability,networking"
```

Or via JSON (better for agents):

```bash
okf commit --json '{
  "title": "Retry with Exponential Backoff",
  "type": "Pattern",
  "content": "When network calls fail transiently, retry with doubling delays and jitter.",
  "tags": ["reliability", "networking"]
}'
```

## Build the Search Index

```bash
okf reindex
```

This embeds all concepts using a local model (no API keys needed) and stores vectors in `.okf/index/okf.db`.

## Search

```bash
okf fetch "handling transient failures"
```

Returns concepts ranked by combined keyword + semantic relevance (hybrid mode, default).

Other modes:
```bash
okf fetch "retry" --mode keyword     # BM25 full-text only (fast, no model load)
okf fetch "resilience" --mode semantic  # Pure vector cosine similarity
```

## Validate Compliance

```bash
okf lint
```

Checks:
- Frontmatter validity (type required, timestamps ISO 8601, tags are lists)
- Structural completeness (directories have index.md)
- Link integrity (no broken internal links)
- Type consistency (no near-duplicate type values)

## Multi-Bundle Setup

okf supports multiple named bundles — e.g. a personal bundle and a shared team bundle. This lets agents and developers accumulate knowledge collaboratively.

### 1. Create your personal bundle

```bash
mkdir -p ~/personal/my-okf && cd ~/personal/my-okf
git init
okf init --register --name personal
```

The `--register` flag adds it to your user-level config at `~/.config/okf/config.json`.

### 2. Add a shared team bundle

Clone your team's knowledge repo and register it:

```bash
git clone git@github.com:your-org/team-knowledge.git /shared/team-okf
cd /shared/team-okf
okf init --register --name team
```

### 3. Set the default write target

Edit `~/.config/okf/config.json`:

```json
{
  "bundles": [
    {"name": "personal", "path": "~/personal/my-okf"},
    {"name": "team", "path": "/shared/team-okf", "default": true}
  ]
}
```

Now `okf commit` writes to the team bundle by default, and `okf fetch` searches both.

### 4. Target a specific bundle

```bash
okf -b personal commit --json '{...}'   # Write to personal
okf -b team fetch "query"               # Search only team
okf fetch "query"                       # Searches all bundles
```

## Next Steps

- Run `okf list` to browse concepts
- Run `okf links <concept-id>` to explore relationships
- Run `okf stats` to see bundle health
- See [CLI Reference](cli-reference.md) for all commands
