# Agent Hooks

These hook definitions nudge AI agents to use okf-tools as part of their workflow. They're IDE-agnostic JSON files — adapt them to your tool:

## Installation by IDE

**Kiro:** Copy hook JSON files to `.kiro/hooks/` in your workspace or `~/.kiro/hooks/` for global.

**Cursor:** Adapt the prompts into your `.cursorrules` file or project instructions.

**Other IDEs:** Use the hook definitions as templates. The key concepts:
- On each prompt/message, remind the agent to `okf fetch` relevant context
- After task completion, suggest the agent commits learnings

## Available Hooks

- `okf-prompt-fetch.json` — Reminds the agent about okf-tools on each prompt
