# OKF Knowledge Tools — Agent Guide

You have access to `okf` — a CLI for managing OKF knowledge bundles. Bundles store learnings, patterns, decisions, and context as markdown files with semantic search.

## When to Use

**USE when:**
- The task involves project-specific knowledge (patterns, decisions, architecture, bugs)
- You need context about past decisions or established patterns before making changes
- You've learned something worth preserving for future sessions

**DO NOT USE when:**
- The user is asking a general programming question unrelated to this project
- The task is purely about external documentation or libraries
- The user explicitly says not to

## Workflow

1. **Before acting:** `okf fetch "<what I'm about to do>"` — check for existing knowledge
2. **During work:** Use what you find to inform decisions
3. **After learning:** `okf commit --check-duplicates --json '{"title": "...", "type": "...", "content": "...", "tags": [...]}'`

## Commands

| Command | When to Use |
|---------|-------------|
| `okf fetch "<query>"` | Before starting work. Uses hybrid search (keyword + semantic). |
| `okf show <concept-id>` | After fetch returns relevant results. Loads full content. |
| `okf list [--type X] [--tags Y]` | Browsing what's available. Use `--format brief` to scan. |
| `okf commit --check-duplicates --json '{...}'` | After discovering something worth persisting. Always use `--check-duplicates`. |
| `okf update <concept-id> --json '{...}'` | When existing knowledge needs correction. |
| `okf delete <concept-id>` | When a concept is obsolete. Rarely needed. |
| `okf reindex` | After external changes to .md files (manual edits, git pulls). |
| `okf stats` | Understanding bundle health. |

## Output Formats

- Commands output JSON when piped (default for agents) — parse it directly
- Use `okf --format json <command>` to force JSON output
- Use `okf --format brief list` for compact scanning (concept_id\ttitle per line)

## Concept Types

Use consistent type values: `Pattern`, `Decision`, `Bug Fix`, `API Endpoint`, `Architecture`, `Runbook`. Check existing types with `okf stats` before inventing new ones.

## Linking Concepts

Use standard markdown links in content to connect related concepts:

```markdown
Related: [Retry Pattern](retry-pattern.md)
```

## Tips

- Always use `--check-duplicates` when committing to avoid redundant entries
- Use `--dry-run` on commit to preview without writing
- Keep entries project-specific — don't commit general programming knowledge the LLM already knows
- Prefer updating existing concepts over creating near-duplicates
