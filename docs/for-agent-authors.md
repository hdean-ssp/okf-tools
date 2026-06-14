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

If results are relevant, use `okf show <concept-id>` to load full context.

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
