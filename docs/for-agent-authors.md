# For Agent Authors

How to integrate okf-tools into AI agent workflows via steering files and hooks.

## JSON Output

When stdout is not a TTY (typical for agent invocations), okf-tools outputs JSON by default. You can also force it:

```bash
okf --format json fetch "query"
okf --format json list --type "Pattern"
okf --format json show concept-id
okf --format json lint
```

All JSON output is valid, parseable, and contains no decorative text.

## Recommended Agent Workflow

### 1. Fetch before acting

```bash
okf fetch "brief description of current task"
```

Uses hybrid search by default (keyword + semantic). For exact term lookups use `--mode keyword`. If results are relevant, use `okf show <concept-id>` to load full context.

### 2. Commit after learning

```bash
okf commit --check-duplicates --json '{
  "title": "What I Learned",
  "type": "Pattern",
  "content": "Detailed description...",
  "tags": ["relevant", "tags"]
}'
```

Always use `--check-duplicates` to avoid redundant entries.

### 3. Lint after bulk changes

```bash
okf lint --format json
```

Exit code 1 means errors exist — the agent should fix them before completing the task.

## Steering File Integration

Add a skill pack to `.kiro/steering/` that instructs your agent:

```markdown
---
inclusion: auto
---

# Knowledge Integration

- Before each task: `okf fetch "<task summary>"`
- After significant discoveries: `okf commit --check-duplicates --json '...'`
- After bulk operations: `okf lint`
- When exploring: `okf links <concept-id> --depth 2`
```

## Hook Integration

Create a hook that runs lint after task completion:

```json
{
  "name": "Lint After Task",
  "version": "1.0.0",
  "when": { "type": "postTaskExecution" },
  "then": {
    "type": "runCommand",
    "command": "okf lint --warn-only"
  }
}
```

Or fetch knowledge before each prompt:

```json
{
  "name": "Fetch Before Prompt",
  "version": "1.0.0",
  "when": { "type": "promptSubmit" },
  "then": {
    "type": "askAgent",
    "prompt": "Run `okf fetch` with a summary of the user's request and review any relevant results before proceeding."
  }
}
```

## Progressive Disclosure

Use brief format to scan what's available without loading full content:

```bash
okf --format brief list              # concept_id<TAB>title per line
okf --format brief show <id>         # frontmatter only, no body
```

Then selectively load full concepts:

```bash
okf --format json show <id>          # full frontmatter + body
```

## Error Handling

Errors are written to stderr as JSON when format is json:

```json
{"error": "Concept not found: nonexistent/path", "exit_code": 1}
```

Check exit codes: 0 = success, 1 = error, 2 = usage error.

## Multi-Bundle Agentic Workflows

When multiple bundles are configured (personal + team), agents should:

### Default to the team bundle for shared knowledge

Knowledge that benefits the team — bug fixes, patterns, architectural decisions — should go to the team/shared bundle. If the shared bundle is configured as `"default": true`, this happens automatically:

```bash
okf commit --check-duplicates --json '{...}'  # Goes to default (team) bundle
```

### Use personal bundle for scratch/private notes

```bash
okf -b personal commit --json '{
  "title": "My Notes on X",
  "type": "Note",
  "content": "...",
  "tags": ["personal"]
}'
```

### Search results include source bundle

When fetching, results include a `bundle` field:

```json
[
  {"concept_id": "retry-pattern", "title": "...", "score": 0.87, "bundle": "team"},
  {"concept_id": "my-notes", "title": "...", "score": 0.72, "bundle": "personal"}
]
```

### Duplicate checking spans all bundles

`--check-duplicates` searches across ALL configured bundles. If a teammate already committed a similar concept to the team bundle, the agent will be warned before duplicating it.

### Steering file example for multi-bundle

```markdown
---
inclusion: auto
---

# Knowledge Integration (Multi-Bundle)

- Before each task: `okf fetch "<task summary>"` (searches all bundles)
- After shared discoveries: `okf commit --check-duplicates --json '...'` (default = team)
- After personal notes: `okf -b personal commit --json '...'`
- After bulk changes: `okf lint`
```
