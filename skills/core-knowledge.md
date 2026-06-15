---
title: OKF Knowledge Integration
description: General OKF usage rules for AI agents — fetch, commit, navigate, and lint
inclusion: auto
---

# OKF Knowledge Integration

You have access to OKF knowledge bundles via the `okf` CLI. Use it to persist and retrieve learnings across interactions. Multiple bundles can be configured (e.g. personal + shared team knowledge).

## Multi-Bundle Awareness

- `okf` can be configured with multiple named bundles (personal, team, project, etc.)
- By default, `okf fetch` searches ALL configured bundles — results include a `bundle` field
- By default, `okf commit` writes to the bundle marked `"default": true`
- Use `okf -b <name>` before the subcommand to target a specific bundle
- Shared team bundles allow knowledge to accumulate across all team members via git

### When to target a specific bundle

- Use `-b team` when committing knowledge that benefits the whole team
- Use `-b personal` for notes/context only relevant to you
- If unsure, commit to the default bundle (usually the team one)

## When to Fetch

- At the start of each interaction, run `okf fetch "<brief description of task>"` to check for relevant prior knowledge. Uses hybrid search (keyword + semantic) by default.
- Before architectural decisions, check for existing rationale.
- When encountering unfamiliar patterns, search first.
- Use `--mode keyword` for exact term lookups (faster, no model load).
- Use `--mode semantic` when the exact words don't matter but the meaning does.

## When to Commit

- After discovering a significant bug fix, pattern, or decision.
- Always check for duplicates first: `okf commit --check-duplicates --json '{...}'`
- Duplicate checks search across ALL bundles — avoids re-committing what a teammate already captured.

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
okf fetch "query"                  # Search ALL bundles (hybrid mode)
okf fetch "query" --mode keyword   # BM25 full-text only (fast, no model load)
okf fetch "query" --mode semantic  # Pure vector cosine similarity
okf -b team fetch "query"          # Search only team bundle
okf commit --json '{...}'          # Write to default bundle
okf -b personal commit --json '{...}'  # Write to personal bundle
okf show <concept-id>              # Read full concept
okf links <concept-id>             # See connections
okf list [--type X] [--tags Y]     # Browse all bundles
okf -b team list                   # Browse only team bundle
okf lint                           # Validate compliance
okf stats                          # Bundle health
```
