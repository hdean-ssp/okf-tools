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

# --- Step 3: Ensure user-level config exists ---

USER_CONFIG_DIR="$HOME/.config/okf"
USER_CONFIG="$USER_CONFIG_DIR/config.json"

if [[ -f "$USER_CONFIG" ]]; then
    echo "✓ User config already exists at $USER_CONFIG"
else
    mkdir -p "$USER_CONFIG_DIR"
    cat > "$USER_CONFIG" << 'CONFIG'
{
  "bundles": []
}
CONFIG
    echo "  ✓ Created user config at $USER_CONFIG"
    echo "    Add bundles with: okf init --register --name <name>"
fi

# --- Step 4: Determine steering/hooks target directory ---

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

You have access to `okf` — a CLI for managing OKF knowledge bundles. Bundles store learnings, patterns, decisions, and context as linked markdown files with semantic search.

## Multi-Bundle Setup

okf supports multiple named bundles. Common setup:
- **personal** — your own learnings, per-user, private
- **team** — shared knowledge across teammates, synced via git

Configuration lives at `~/.config/okf/config.json`:
```json
{
  "bundles": [
    {"name": "personal", "path": "~/my-okf", "default": true},
    {"name": "team", "path": "~/team-okf"}
  ]
}
```

**Your active bundles:**
- **personal** (default write target) — individual learnings, preferences, workflow
- **team** — shared codebase knowledge, synced via git

When committing, consider whether the knowledge is personal or team-relevant. Use `-b team` for the latter.

### Bundle Targeting

Use `-b <name>` (before the subcommand) to target a specific bundle:
```
okf -b personal commit --json '{...}'    # Write to personal bundle
okf -b team fetch "query"                # Search only team bundle
okf fetch "query"                        # Searches ALL bundles (default)
okf commit --json '{...}'                # Writes to the default bundle
```

## When to Use okf-tools

**USE when:**
- The task involves project-specific knowledge (patterns, decisions, architecture, bugs)
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
| `okf fetch "<query>"` | Before starting work that might have prior context. Uses hybrid search (keyword + semantic) by default. Searches all bundles unless `-b` is used. |
| `okf show <concept-id>` | After fetch returns relevant results. Loads the full concept body into your context. |
| `okf list [--type X] [--tags Y]` | When browsing what's available. Use `--format brief` to scan without loading full content. |
| `okf links <concept-id> [--depth N]` | When exploring related concepts. Shows what links to/from a concept. |

### Author & Modify

| Command | When to Use |
|---------|-------------|
| `okf commit --check-duplicates --json '{...}'` | After discovering a significant pattern, decision, or bug fix worth persisting. Always use `--check-duplicates`. Writes to default bundle. |
| `okf -b <name> commit --json '{...}'` | Write to a specific bundle (e.g. personal vs team). |
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

## Bundle Routing

When committing new knowledge, route to the correct bundle:

| Knowledge type | Bundle | Command |
|---------------|--------|---------|
| Personal preferences, workflow, editor config, learning notes | personal | `okf commit --check-duplicates --json '{...}'` |
| Codebase patterns, bug fixes, architecture decisions, team conventions | team | `okf -b team commit --check-duplicates --json '{...}'` |

**Rule of thumb:** If it would help a teammate, put it in `team`. If it's only about you, put it in `personal`.

## Output Formats

- Commands output JSON when piped (default for agents) — parse it directly
- Use `okf --format json <command>` to force JSON output
- `--format` is also available per-command on `list` and `fetch`: `okf list --format brief`
- Use `okf --format brief list` for compact scanning (concept_id\ttitle per line)
- Fetch results include a `bundle` field showing which bundle each result came from
- When filters produce zero results, "No matching concepts." is printed to stderr

## Concept Types to Use

Use consistent type values. Common types: `Pattern`, `Decision`, `Bug Fix`, `API Endpoint`, `Architecture`, `Runbook`. Check existing types with `okf stats` before inventing new ones.
STEERING

echo "  ✓ Installed steering: $STEERING_DIR/okf-knowledge.md"

# --- Install post-prompt hook ---

cat > "$HOOKS_DIR/okf-prompt-fetch.json" << 'HOOK'
{
  "name": "OKF Knowledge Awareness",
  "version": "1.1.0",
  "description": "Points the agent to the okf-knowledge steering file after each prompt so it knows the knowledge tools are available",
  "when": {
    "type": "promptSubmit"
  },
  "then": {
    "type": "askAgent",
    "prompt": "You have access to okf-tools for managing project knowledge across two bundles: 'personal' (your preferences and workflow) and 'team' (shared codebase knowledge). Refer to the okf-knowledge.md steering file for full command reference and bundle routing guidance. If this task relates to the codebase or project-specific knowledge, run `okf fetch` with a relevant query before proceeding (this searches both bundles by default). When committing new knowledge, decide whether it belongs in personal (default) or team (`okf -b team commit`)."
  }
}
HOOK

echo "  ✓ Installed hook: $HOOKS_DIR/okf-prompt-fetch.json"

# --- Install post-task lint hook ---

cat > "$HOOKS_DIR/okf-post-task-lint.json" << 'HOOK'
{
  "name": "OKF Lint After Task",
  "version": "1.1.0",
  "description": "Runs okf lint on both personal and team bundles after task completion to verify compliance",
  "when": {
    "type": "postTaskExecution"
  },
  "then": {
    "type": "runCommand",
    "command": "okf lint --warn-only --format json && okf -b team lint --warn-only --format json"
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
echo "Config:"
echo "  $USER_CONFIG — add bundles here or use 'okf init --register'"
echo ""
echo "Steering + Hooks:"
echo "  $STEERING_DIR/okf-knowledge.md     — full command reference and usage guidance"
echo "  $HOOKS_DIR/okf-prompt-fetch.json   — points agent to steering on each prompt"
echo "  $HOOKS_DIR/okf-post-task-lint.json — lint bundle after task completion"
echo ""
echo "⚠  First run note:"
echo "  The first command that uses search (okf fetch, okf commit, okf reindex)"
echo "  will download the embedding model (~30MB, BAAI/bge-small-en-v1.5)."
echo "  This is a one-time download. No network access needed after that."
echo ""
echo "Next steps:"
echo "  1. Create a knowledge bundle: mkdir ~/my-knowledge && cd ~/my-knowledge && okf init --register --name personal"
echo "  2. Or clone a shared team bundle and register it: okf init --register --name team"
