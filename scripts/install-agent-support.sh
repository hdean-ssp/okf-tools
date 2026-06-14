#!/usr/bin/env bash
# install-agent-support.sh
#
# Installs okf-tools (into a persistent venv with PATH export) plus
# steering files and hooks for agentic work.
#
# Usage:
#   ./scripts/install-agent-support.sh                  # Install to ~/.kiro (user-level)
#   ./scripts/install-agent-support.sh /path/to/project # Install to project/.kiro
#
# What gets installed:
#   1. okf-tools venv at ~/.local/share/okf-tools/.venv (if not already present)
#   2. PATH entry in ~/.bashrc so `okf` is available in all shells
#   3. Steering file: okf-knowledge.md (full agent guide)
#   4. Hook: okf-prompt-fetch.json (points agent to steering on each prompt)
#   5. Hook: okf-post-task-lint.json (lints after task completion)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

OKF_INSTALL_DIR="$HOME/.local/share/okf-tools"
OKF_VENV="$OKF_INSTALL_DIR/.venv"
OKF_BIN="$OKF_VENV/bin"

# --- Step 1: Install okf-tools into a persistent venv ---

if [[ -x "$OKF_BIN/okf" ]]; then
    echo "✓ okf-tools already installed at $OKF_BIN/okf"
else
    echo "Installing okf-tools to $OKF_INSTALL_DIR..."
    mkdir -p "$OKF_INSTALL_DIR"
    python3 -m venv "$OKF_VENV"
    "$OKF_BIN/pip" install --quiet --upgrade pip
    "$OKF_BIN/pip" install --quiet "$REPO_ROOT"
    echo "  ✓ Installed okf-tools to $OKF_BIN/okf"
fi

# --- Step 2: Ensure PATH includes the venv bin ---

PATH_LINE="export PATH=\"$OKF_BIN:\$PATH\""
BASHRC="$HOME/.bashrc"

if grep -qF "$OKF_BIN" "$BASHRC" 2>/dev/null; then
    echo "✓ PATH already configured in $BASHRC"
else
    echo "" >> "$BASHRC"
    echo "# okf-tools CLI" >> "$BASHRC"
    echo "$PATH_LINE" >> "$BASHRC"
    echo "  ✓ Added $OKF_BIN to PATH in $BASHRC"
fi

# Make available in current session too
export PATH="$OKF_BIN:$PATH"

# Verify
if command -v okf &>/dev/null; then
    echo "  ✓ 'okf' command available ($(okf --version))"
else
    echo "  ⚠ 'okf' not found in current PATH — start a new shell or run: source ~/.bashrc"
fi

# --- Step 3: Determine steering/hooks target directory ---

if [[ $# -ge 1 ]]; then
    TARGET="$(realpath "$1")/.kiro"
    echo ""
    echo "Installing steering + hooks to workspace: $1"
else
    TARGET="$HOME/.kiro"
    echo ""
    echo "Installing steering + hooks to user directory: $TARGET"
fi

STEERING_DIR="$TARGET/steering"
HOOKS_DIR="$TARGET/hooks"

mkdir -p "$STEERING_DIR" "$HOOKS_DIR"

# --- Install steering file ---

cat > "$STEERING_DIR/okf-knowledge.md" << 'STEERING'
---
inclusion: auto
description: Comprehensive guide for AI agents on using okf-tools to manage knowledge
---

# OKF Knowledge Tools

You have access to `okf` — a CLI for managing an OKF knowledge bundle in this workspace. The bundle stores learnings, patterns, decisions, and context as linked markdown files with semantic search.

## When to Use okf-tools

**USE when:**
- The task involves this codebase or project-specific knowledge (patterns, decisions, architecture, bugs)
- You need context about past decisions or established patterns before making changes
- You've learned something worth preserving for future sessions
- You're doing bulk operations on concept files and need to verify integrity

**DO NOT USE when:**
- The user is asking a general programming question unrelated to this project
- The task is purely about external documentation or libraries
- The user explicitly says not to

## Available Commands

### Search & Retrieve

| Command | When to Use |
|---------|-------------|
| `okf fetch "<query>"` | Before starting work that might have prior context. Searches semantically — describe what you're looking for in natural language. |
| `okf show <concept-id>` | After fetch returns relevant results. Loads the full concept body into your context. |
| `okf list [--type X] [--tags Y]` | When browsing what's available. Use `--format brief` to scan without loading full content. |
| `okf links <concept-id> [--depth N]` | When exploring related concepts. Shows what links to/from a concept. |

### Author & Modify

| Command | When to Use |
|---------|-------------|
| `okf commit --check-duplicates --json '{...}'` | After discovering a significant pattern, decision, or bug fix worth persisting. Always use `--check-duplicates`. |
| `okf update <concept-id> --json '{...}'` | When existing knowledge needs correction or expansion. |
| `okf delete <concept-id>` | When a concept is obsolete or incorrect. Rarely needed. |

### Validate & Maintain

| Command | When to Use |
|---------|-------------|
| `okf lint` | After bulk operations (multiple commits, restructuring). Treat errors as blockers. |
| `okf lint --path <dir>` | After modifying concepts in a specific directory. |
| `okf reindex` | After external changes to .md files (manual edits, git pulls). Usually unnecessary — commit/update handle indexing automatically. |
| `okf stats` | When you need to understand bundle health or structure. |

### Discovery

| Command | When to Use |
|---------|-------------|
| `okf skills` | To see what domain-specific guidance is available. |

## Workflow Pattern

1. **Before acting:** `okf fetch "<what I'm about to do>"` — check for existing knowledge
2. **During work:** Use what you find to inform decisions
3. **After learning:** `okf commit --check-duplicates --json '{"title": "...", "type": "...", "content": "...", "tags": [...]}'`
4. **After bulk changes:** `okf lint` — verify compliance

## Output Formats

- Commands output JSON when piped (default for agents) — parse it directly
- Use `okf --format json <command>` to force JSON output
- Use `okf --format brief list` for compact scanning (concept_id\ttitle per line)

## Concept Types to Use

Use consistent type values. Common types: `Pattern`, `Decision`, `Bug Fix`, `API Endpoint`, `Architecture`, `Runbook`. Check existing types with `okf stats` before inventing new ones.
STEERING

echo "  ✓ Installed steering: $STEERING_DIR/okf-knowledge.md"

# --- Install post-prompt hook ---

cat > "$HOOKS_DIR/okf-prompt-fetch.json" << 'HOOK'
{
  "name": "OKF Knowledge Awareness",
  "version": "1.0.0",
  "description": "Points the agent to the okf-knowledge steering file after each prompt so it knows the knowledge tools are available",
  "when": {
    "type": "promptSubmit"
  },
  "then": {
    "type": "askAgent",
    "prompt": "You have access to okf-tools for managing project knowledge. Refer to the okf-knowledge.md steering file for full command reference and usage guidance. If this task relates to the codebase or project-specific knowledge, consider running `okf fetch` with a relevant query before proceeding."
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
echo "Done. okf-tools agent support fully installed."
echo ""
echo "CLI:"
echo "  $OKF_BIN/okf (also on PATH via ~/.bashrc)"
echo ""
echo "Steering + Hooks:"
echo "  $STEERING_DIR/okf-knowledge.md     — full command reference and usage guidance"
echo "  $HOOKS_DIR/okf-prompt-fetch.json   — points agent to steering on each prompt"
echo "  $HOOKS_DIR/okf-post-task-lint.json — lint bundle after task completion"
echo ""
echo "Next: run 'okf init' in your project to initialise a knowledge bundle."
