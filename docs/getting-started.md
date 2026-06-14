# Getting Started

## Installation

```bash
pip install okf-tools
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

Returns concepts ranked by semantic similarity.

## Validate Compliance

```bash
okf lint
```

Checks:
- Frontmatter validity (type required, timestamps ISO 8601, tags are lists)
- Structural completeness (directories have index.md)
- Link integrity (no broken internal links)
- Type consistency (no near-duplicate type values)

## Next Steps

- Run `okf list` to browse concepts
- Run `okf links <concept-id>` to explore relationships
- Run `okf stats` to see bundle health
- See [CLI Reference](cli-reference.md) for all commands
