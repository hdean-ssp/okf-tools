# Getting Started

## Installation

```bash
git clone https://github.com/hdean-ssp/okf-tools.git
cd okf-tools
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Initialise a Bundle

```bash
mkdir my-knowledge && cd my-knowledge
git init
okf init
```

This creates:
- `.okf/config.json` — configuration with sensible defaults
- `index.md` — root concept listing
- `.gitignore` entry for `.okf/index/`

## Commit Your First Concept

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

> **First run:** The embedding model (~30MB, BAAI/bge-small-en-v1.5) downloads automatically on first use. One-time only.

## Search

```bash
okf fetch "handling transient failures"
```

Returns concepts ranked by combined keyword + semantic relevance.

Other modes:
```bash
okf fetch "retry" --mode keyword     # BM25 full-text only
okf fetch "resilience" --mode semantic  # Pure vector cosine
```

## Next Steps

- `okf list` — browse concepts
- `okf show <concept-id>` — read full content
- `okf stats` — bundle health
- See [CLI Reference](cli-reference.md) for all commands
- See [agent/AGENT.md](../agent/AGENT.md) for AI agent integration
