# Writing Skill Packs

Skill packs extend okf-tools with domain-specific guidance for AI agents — without modifying the core tool.

## What's a Skill Pack?

A `.md` file with YAML frontmatter, placed in a configured skills directory. It provides steering instructions that agents read to understand how to use the knowledge bundle in a specific context.

## Creating a Skill

Create a file like `my-domain.md`:

```markdown
---
title: My Domain Integration
description: Guides agents to use domain-specific knowledge patterns
inclusion: auto
---

# My Domain Integration

Instructions for agents working in this domain...

## When to Fetch
- Before starting any task, search for relevant domain knowledge.

## When to Commit  
- After discovering domain-specific patterns or decisions.
```

## Installation

Drop the file into any configured skills path:

- `.kiro/steering/` (project-level, default)
- `~/.config/okf/skills/` (user-level, default)
- Any path listed in `skills_paths` in your config

No registration needed — okf-tools discovers skills on each invocation.

## Required Fields

Only YAML frontmatter is required. The file must have a `---` frontmatter block.

**Title resolution:** frontmatter `title` → first `# Heading` → filename stem.

## Discovery

```bash
okf skills
```

Lists all discovered skills with filename, title, and description.

## Built-in Skill

okf-tools ships with `core-knowledge.md` — general OKF usage rules covering when to fetch, commit, navigate, and lint. It's always included regardless of configured paths.

## Example Skills (not shipped)

- `code-review.md` — fetch patterns before reviewing PRs
- `incident-response.md` — fetch runbooks during incidents
- `onboarding.md` — guide new-joiners to relevant architecture decisions
