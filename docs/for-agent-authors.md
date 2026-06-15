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

The `--format` option is also available per-command on `list` and `fetch`:

```bash
okf list --format brief        # Works (no need for global position)
okf fetch "query" --format json
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
  "content": "Detailed description... Link to related: [Other Concept](other-concept.md)",
  "tags": ["relevant", "tags"]
}'
```

Always use `--check-duplicates` to avoid redundant entries. This will **block the commit** (exit code 1) if semantically similar content already exists in any bundle (threshold: 0.85 cosine similarity). Use `--force` to override.

Use standard markdown links (`[Display Text](concept-id.md)`) in content to create graph edges between concepts.

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

## Limitations & Known Issues

### Agent Reliability

okf-tools is designed for agent use, but current LLM agents are imperfect consumers:

- **Agents may skip `okf fetch`** — even with a promptSubmit hook nudging them, agents sometimes proceed without checking existing knowledge. The hook improves consistency but doesn't guarantee it.
- **Low-quality commits** — agents may commit trivially obvious knowledge ("use try/catch for error handling") that pollutes the bundle. The `--check-duplicates` flag catches exact semantic overlap but not low-value content.
- **Lint ignored** — agents may complete a task without running `okf lint`, leaving broken links or missing index entries. The postTaskExecution hook helps but isn't enforced.
- **Inconsistent bundle routing** — in multi-bundle setups, agents may commit personal-grade knowledge to the team bundle or vice versa.

### Mitigation

- **Human curation is required.** Periodically review recent commits: `okf list --since <date>`. Delete low-value entries with `okf delete`.
- **Hooks help but aren't sufficient.** Treat them as nudges, not guarantees. The real safeguard is reviewing what got committed before pushing a shared bundle.
- **Start with a single bundle.** Multi-bundle adds routing complexity that agents handle inconsistently. Add a second bundle only after the single-bundle workflow proves useful.

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
