# OKF Knowledge Tools — Agent Guide

You have access to okf-tools via MCP — a set of tools for managing OKF knowledge bundles. Bundles store learnings, patterns, decisions, and context as markdown files with semantic search.

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

1. **Before acting:** Use `fetch_concepts` with a relevant query — check for existing knowledge
2. **During work:** Use what you find to inform decisions
3. **After learning:** Use `commit_concept` to persist the discovery

## MCP Tools

| Tool | When to Use |
|------|-------------|
| `fetch_concepts` | Before starting work. Searches with natural language (hybrid keyword + semantic). Params: `query`, optional `top_n`, `threshold`, `type`, `tags`, `mode`. |
| `show_concept` | After fetch returns relevant results. Gets full content. Params: `concept_id`. |
| `list_concepts` | Browsing what's available. Params: optional `type`, `tags`, `since`, `limit`, `path`. |
| `commit_concept` | After discovering something worth persisting. Params: `title`, `type`, `content`, optional `tags`, `path`, `check_duplicates`. |
| `update_concept` | When existing knowledge needs correction. Params: `concept_id`, plus optional `title`, `type`, `tags`, `content`. |
| `delete_concept` | When a concept is obsolete. Rarely needed. Params: `concept_id`. |
| `reindex` | After external changes to .md files (manual edits, git pulls). Params: optional `full`. |
| `get_stats` | Understanding bundle health. No params. |
| `init_bundle` | Creating a new bundle. Params: optional `path`. |

## Response Formats

All tools return JSON strings. Parse the result to extract data:

- `fetch_concepts` → `{"results": [{"concept_id": "...", "title": "...", "score": 0.87, "snippet": "..."}]}`
- `show_concept` → `{"concept_id": "...", "title": "...", "type": "...", "tags": [...], "body": "..."}`
- `list_concepts` → `{"concepts": [{"concept_id": "...", "title": "...", "type": "...", "tags": [...]}]}`
- `commit_concept` → `{"concept_id": "..."}`
- `get_stats` → `{"concept_count": N, "type_distribution": {...}, ...}`

## Concept Types

Use consistent type values: `Pattern`, `Decision`, `Bug Fix`, `API Endpoint`, `Architecture`, `Runbook`. Check existing types with `get_stats` before inventing new ones.

## Tips

- Always use `check_duplicates: true` (the default) when committing to avoid redundant entries
- Keep entries project-specific — don't commit general programming knowledge the LLM already knows
- Prefer updating existing concepts over creating near-duplicates
- Use `fetch_concepts` before every significant task to check for prior art
- The bundle is shared across the team — be thoughtful about what you commit
