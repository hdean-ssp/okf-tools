---
title: OKF Knowledge Integration
description: General OKF usage rules for AI agents — fetch, commit, navigate, and lint
inclusion: auto
---

# OKF Knowledge Integration

You have access to an OKF knowledge bundle via the `okf` CLI. Use it to persist and retrieve learnings across interactions.

## When to Fetch

- At the start of each interaction, run `okf fetch "<brief description of task>"` to check for relevant prior knowledge. Uses hybrid search (keyword + semantic) by default.
- Before architectural decisions, check for existing rationale.
- When encountering unfamiliar patterns, search first.
- Use `--mode keyword` for exact term lookups (faster, no model load).
- Use `--mode semantic` when the exact words don't matter but the meaning does.

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
okf fetch "query"               # Hybrid search (keyword + semantic, default)
okf fetch "query" --mode keyword   # BM25 full-text only (fast, no model load)
okf fetch "query" --mode semantic  # Pure vector cosine similarity
okf commit --json '{...}'       # Create concept
okf show <concept-id>           # Read full concept
okf links <concept-id>          # See connections
okf list [--type X] [--tags Y]  # Browse
okf lint                        # Validate compliance
okf stats                       # Bundle health
```
