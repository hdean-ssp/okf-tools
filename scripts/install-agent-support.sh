#!/usr/bin/env bash
# install-agent-support.sh
#
# Installs okf-tools steering files and hooks into a target workspace
# (or the user's global ~/.kiro directory if no workspace is specified).
#
# Usage:
#   ./scripts/install-agent-support.sh                  # Install to ~/.kiro (user-level)
#   ./scripts/install-agent-support.sh /path/to/project # Install to project/.kiro
#
# What gets installed:
#   - Steering file: okf-knowledge.md (instructs agents to use okf-tools)
#   - Hook: okf-prompt-fetch.json (runs okf fetch after each prompt)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Determine target directory
if [[ $# -ge 1 ]]; then
    TARGET="$(realpath "$1")/.kiro"
    echo "Installing to workspace: $1"
else
    TARGET="$HOME/.kiro"
    echo "Installing to user directory: $TARGET"
fi

STEERING_DIR="$TARGET/steering"
HOOKS_DIR="$TARGET/hooks"

mkdir -p "$STEERING_DIR" "$HOOKS_DIR"

# --- Install steering file ---

cat > "$STEERING_DIR/okf-knowledge.md" << 'STEERING'
---
inclusion: auto
description: Integrates okf-tools knowledge retrieval into agent workflows
---

# OKF Knowledge Integration

You have access to an OKF knowledge bundle via the `okf` CLI. Use it to persist and retrieve learnings across interactions.

## When to Fetch

- At the start of each interaction, run `okf fetch "<brief description of task>"` to check for relevant prior knowledge.
- Before architectural decisions, check for existing rationale.
- When encountering unfamiliar patterns, search first.

## When to Commit

- After discovering a significant bug fix, pattern, or decision.
- Always check for duplicates first: `okf commit --check-duplicates --json '{...}'`

## When to Navigate

- Use `okf links <concept-id>` to explore related concepts.
- Use `okf list --type "Pattern"` to browse available patterns.
- Use `okf show <concept-id>` to read a full concept before acting on it.

## When to Lint

- After bulk operations (multiple commits, imports, or restructuring), run `okf lint`.
- Treat lint errors as blockers — fix them before considering the task complete.

## Command Quick Reference

```
okf fetch "query"               # Semantic search
okf commit --json '{...}'       # Create concept
okf show <concept-id>           # Read full concept
okf links <concept-id>          # See connections
okf list [--type X] [--tags Y]  # Browse
okf lint                        # Validate compliance
okf stats                       # Bundle health
```
STEERING

echo "  ✓ Installed steering: $STEERING_DIR/okf-knowledge.md"

# --- Install post-prompt hook ---

cat > "$HOOKS_DIR/okf-prompt-fetch.json" << 'HOOK'
{
  "name": "OKF Knowledge Fetch",
  "version": "1.0.0",
  "description": "After each prompt, reminds the agent to check the OKF knowledge bundle for relevant context",
  "when": {
    "type": "promptSubmit"
  },
  "then": {
    "type": "askAgent",
    "prompt": "Before proceeding, check if there is relevant prior knowledge in the OKF bundle. Run `okf fetch \"<one-line summary of the user's request>\"` and review any results with score > 0.3. If relevant concepts exist, use `okf show <concept-id>` to load them. Then proceed with the task informed by that context."
  }
}
HOOK

echo "  ✓ Installed hook: $HOOKS_DIR/okf-prompt-fetch.json"

# --- Install post-task lint hook ---

cat > "$HOOKS_DIR/okf-post-task-lint.json" << 'HOOK'
{
  "name": "OKF Lint After Task",
  "version": "1.0.0",
  "description": "Runs okf lint after task completion to verify bundle compliance",
  "when": {
    "type": "postTaskExecution"
  },
  "then": {
    "type": "runCommand",
    "command": "okf lint --warn-only --format json"
  }
}
HOOK

echo "  ✓ Installed hook: $HOOKS_DIR/okf-post-task-lint.json"

# --- Summary ---

echo ""
echo "Done. Installed okf-tools agent support to: $TARGET"
echo ""
echo "Files installed:"
echo "  $STEERING_DIR/okf-knowledge.md     — steering for knowledge retrieval"
echo "  $HOOKS_DIR/okf-prompt-fetch.json   — fetch knowledge on each prompt"
echo "  $HOOKS_DIR/okf-post-task-lint.json — lint bundle after task completion"
echo ""
echo "Make sure 'okf' is on PATH (pip install okf-tools) and the target"
echo "workspace has an initialised bundle (okf init)."
