# okf-tools — AI Proof Point Summary

## Problem Addressed

Engineers working on large, unfamiliar codebases spend significant time discovering context that already exists somewhere — in docs, past decisions, architecture notes, or colleagues' heads. This knowledge is scattered, unsearchable, and rarely persisted in a structured way.

When an AI agent assists a developer, it starts fresh each session with no project-specific memory. Useful discoveries are lost between sessions.

## Approach

okf-tools provides a local, queryable knowledge layer over OKF markdown bundles.

[OKF (Open Knowledge Format)](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md) is a vendor-neutral specification published by Google Cloud Platform for representing knowledge as markdown files with YAML frontmatter. It is intentionally minimal — defining structure but not prescribing tooling, storage, or query infrastructure. okf-tools fills those intentional gaps.

- **Source of truth:** Plain markdown files with YAML frontmatter (OKF v0.1 format). Human-readable, git-tracked, fully portable.
- **Derived search index:** Local embeddings (BAAI/bge-small-en-v1.5) + BM25 full-text search in a SQLite sidecar database. No external services, no API keys. Index is always rebuildable from the markdown files.
- **Hybrid retrieval:** Combines semantic similarity with keyword matching to surface relevant concepts from natural-language queries.
- **Agent integration:** JSON output, steering files, and IDE hooks allow AI agents to fetch context before acting and commit learnings after discovering something useful.

The tool fills gaps the OKF spec intentionally leaves open: search, navigation, link traversal, compliance validation, and agent-friendly access patterns.

## Outputs Produced

| Output | Format | Consumer |
|--------|--------|----------|
| Search results (ranked, with snippets) | JSON / text | Developers, AI agents |
| Concept detail views | Markdown / JSON | Developers, AI agents |
| Link graph traversals | JSON | Developers exploring relationships |
| Lint/compliance reports | JSON / text | CI pipelines, developers |
| Bundle health statistics | JSON | Team leads, onboarding docs |
| Structured markdown concepts | `.md` files | Anyone with a text editor |

All outputs are reviewable by humans and parseable by machines.

## Workflows Improved

| Workflow | Without okf-tools | With okf-tools |
|----------|-------------------|----------------|
| Understanding an unfamiliar module | Read source, grep for docs, ask a colleague | `okf fetch "what does module X do"` → ranked relevant concepts |
| Triaging an issue in unknown code | Trace code paths, read git blame, context-switch | `okf fetch "error in payment flow"` → prior bug fixes, related patterns |
| New engineer onboarding | Scattered wikis, tribal knowledge, slow ramp-up | Query the team bundle for architecture decisions, key flows, gotchas |
| Preserving discoveries | Knowledge lost between sessions/engineers | `okf commit` persists learnings as searchable, linked concepts |
| Agent context loading | Agent starts fresh each session | Agent runs `okf fetch` at session start, builds on prior knowledge |

## How Impact Should Be Measured

Metrics to track (before/after introducing okf-tools into a workflow):

| Metric | How to measure | Baseline |
|--------|---------------|----------|
| Time to understand a module | Self-reported time from "starting to investigate" to "confident I understand the purpose, key flows, and dependencies" | Capture before first use |
| Time to triage an issue | Clock time from "assigned" to "root cause identified or escalation decision made" | Capture from recent tickets |
| Onboarding ramp-up | Days until a new engineer submits their first meaningful PR in an unfamiliar area | Capture from recent hires |
| Agent context hit rate | Percentage of `okf fetch` calls that return results the agent actually uses (measured by subsequent `okf show` calls) | 0% (no bundle exists yet) |
| Knowledge reuse rate | How often committed concepts are fetched by someone other than the original author | Track via access logs or git blame |

See `docs/metrics.md` for the capture template and reporting format.

### What Constitutes a Meaningful Result

A credible proof point would demonstrate ≥30% reduction in at least one time-based metric (time to understand, time to triage) across 2-3 paired observations (same task type, with and without the tool). Small sample sizes are acceptable for an initial proof point if the effect size is clear and observations are well-documented.

## Current Status

- Core CLI: functional (init, commit, fetch, show, list, update, delete, reindex, lint, links, stats, skills)
- Local hybrid search: working (BM25 + vector, no external services)
- Multi-bundle support: working (personal + team bundles, aggregated search)
- Agent integration: steering files + hooks installed via script
- Validation: bundle-wide lint with structured reporting

## What Makes This an AI Proof Point

1. **AI-assisted knowledge extraction** — agents commit project-specific knowledge during normal development work, building a searchable corpus over time.
2. **AI-assisted retrieval** — agents query the bundle before acting, reducing redundant discovery and improving decision quality.
3. **Measurable developer workflow improvement** — the metrics above can demonstrate concrete time savings in understanding, triaging, and onboarding.
4. **Reusable by the team** — outputs are plain markdown, searchable via CLI, and consumable by any tool or agent that reads text.
5. **Low-friction adoption** — single install command, works locally, no infrastructure dependencies.

## Limitations & Honest Assessment

- **Bundle quality depends on what's committed.** If agents or developers commit low-value, generic knowledge, the bundle becomes noisy. Periodic human curation is required.
- **Agent behaviour is imperfect.** Agents may skip `okf fetch`, commit duplicates, or ignore lint. Hooks nudge but don't guarantee compliance.
- **Metrics require manual capture today.** Until `okf metrics log` is implemented, observations must be recorded manually in YAML. This is workable for small teams but doesn't scale automatically.
- **OKF spec is v0.1 draft.** If the upstream spec changes significantly, okf-tools may need to adapt. The mitigation is simple: the markdown files remain valid regardless of spec evolution, and the sidecar is rebuildable.
- **Sample size for proof point will be small.** Initial measurements will likely be 2-5 paired observations. This is sufficient to demonstrate a signal but not to claim statistical certainty.
