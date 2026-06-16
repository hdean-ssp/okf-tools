# Metrics & Impact Measurement

A lightweight framework for capturing before/after measurements when using okf-tools in developer workflows.

## Purpose

To demonstrate concrete, measurable impact, we need:
1. A baseline (how long things take *without* the tool)
2. A measurement after adoption (how long things take *with* the tool)
3. A consistent format for recording and reporting these values

This document provides the capture template and reporting structure. It does **not** invent numbers — all values should come from real observations.

---

## Metrics to Track

### 1. Time to Understand a Module

**What it measures:** How long it takes a developer to go from "I've never seen this code" to "I can explain what it does, its key flows, and its dependencies."

**How to capture:**
- Record the start time when the developer begins investigating
- Record the end time when they can articulate the module's purpose and key interactions
- Note whether okf-tools was used during the investigation

**Capture template:**

```yaml
metric: time_to_understand
module: "<module or subsystem name>"
engineer: "<name or ID>"
date: "<YYYY-MM-DD>"
okf_used: <true|false>
start_time: "<HH:MM>"
end_time: "<HH:MM>"
duration_minutes: <number>
confidence: "<low|medium|high>"  # self-assessed understanding quality
notes: "<optional context>"
```

### 2. Time to Triage an Issue

**What it measures:** How long from "issue assigned" to "root cause identified or escalation decision made."

**How to capture:**
- Use ticket timestamps (assigned → status change to "root cause identified")
- Note whether the developer queried the knowledge bundle during triage

**Capture template:**

```yaml
metric: time_to_triage
issue_id: "<ticket ID>"
engineer: "<name or ID>"
date: "<YYYY-MM-DD>"
okf_used: <true|false>
assigned_time: "<ISO 8601>"
resolved_time: "<ISO 8601>"
duration_minutes: <number>
okf_queries: <number>        # how many fetch calls made
relevant_results: <number>   # how many results were actually useful
notes: "<optional context>"
```

### 3. Onboarding Ramp-Up Time

**What it measures:** Days from a new engineer joining the team to their first meaningful contribution in an unfamiliar area.

**How to capture:**
- Record start date (first day on the team/project)
- Record the date of first merged PR that touches non-trivial logic
- Note whether okf-tools was available during onboarding

**Capture template:**

```yaml
metric: onboarding_ramp_up
engineer: "<name or ID>"
start_date: "<YYYY-MM-DD>"
first_meaningful_pr_date: "<YYYY-MM-DD>"
days_elapsed: <number>
okf_available: <true|false>
bundle_queries_during_onboarding: <number>
notes: "<optional context>"
```

### 4. Agent Context Hit Rate

**What it measures:** How often `okf fetch` returns results that the agent actually uses (follows up with `okf show` or references in its output).

**How to capture:**
- Log agent sessions where `okf fetch` is called
- Track whether a subsequent `okf show` call occurs for any returned concept
- Calculate: `(sessions with show after fetch) / (sessions with fetch)` × 100

**Capture template:**

```yaml
metric: agent_context_hit_rate
period: "<YYYY-MM-DD to YYYY-MM-DD>"
total_fetch_calls: <number>
fetch_with_followup_show: <number>
hit_rate_percent: <number>
notes: "<optional context>"
```

### 5. Knowledge Reuse Rate

**What it measures:** How often committed concepts are fetched by someone other than the original author.

**How to capture:**
- Compare git blame (who authored the concept file) with fetch logs (who queried it)
- Calculate: `(concepts fetched by non-author) / (total concepts fetched)` × 100

**Capture template:**

```yaml
metric: knowledge_reuse_rate
period: "<YYYY-MM-DD to YYYY-MM-DD>"
total_concepts_fetched: <number>
fetched_by_non_author: <number>
reuse_rate_percent: <number>
notes: "<optional context>"
```

---

## Reporting Format

Collect metric entries in a YAML file at the bundle or project level:

```
metrics/
├── observations.yaml    # raw observations (append-only)
└── summary.md           # periodic summary (human-written)
```

### observations.yaml (example)

```yaml
observations:
  - metric: time_to_understand
    module: "payment-gateway"
    engineer: "engineer-a"
    date: "2025-06-10"
    okf_used: false
    duration_minutes: 95
    confidence: medium
    notes: "Baseline — no bundle existed yet"

  - metric: time_to_understand
    module: "payment-gateway"
    engineer: "engineer-b"
    date: "2025-06-20"
    okf_used: true
    duration_minutes: 35
    confidence: high
    notes: "Used okf fetch to find architecture + bug fix concepts"

  - metric: time_to_triage
    issue_id: "PROJ-412"
    engineer: "engineer-a"
    date: "2025-06-15"
    okf_used: true
    assigned_time: "2025-06-15T09:00:00"
    resolved_time: "2025-06-15T09:25:00"
    duration_minutes: 25
    okf_queries: 3
    relevant_results: 2
    notes: "Found prior bug fix concept that described same root cause pattern"
```

### summary.md (example structure)

```markdown
# Metrics Summary — June 2025

## Time to Understand
| Module | Without okf | With okf | Improvement |
|--------|-------------|----------|-------------|
| payment-gateway | 95 min | 35 min | 63% reduction |

## Time to Triage
| Period | Avg without okf | Avg with okf | Improvement |
|--------|-----------------|--------------|-------------|
| June 1-15 | (no data yet) | 25 min | baseline |

## Notes
- Sample size is small; more observations needed before drawing conclusions.
- "With okf" means the developer actively used `okf fetch` during the workflow.
```

---

## Guidelines

1. **Don't fabricate data.** Only record real observations. Use "no data" or "baseline pending" where measurements haven't been taken.
2. **Small samples are fine.** Even 2-3 paired observations (same task, with/without) are useful for a proof point. State the sample size.
3. **Self-reported is acceptable.** For time-to-understand, self-reporting is the practical approach. Note confidence level.
4. **Capture context.** The `notes` field matters — it explains why a measurement might be unusually high or low.
5. **Update periodically.** Revisit `summary.md` weekly or biweekly during the proof-point period. After that, monthly is sufficient.

---

## Integration with okf-tools (Future)

Tasks for potential future implementation (tracked in TASKS.md):

- `okf metrics log` — append an observation to `metrics/observations.yaml` via CLI
- `okf metrics summary` — generate a summary table from collected observations
- `okf metrics export` — output observations as JSON for external reporting

These are optional conveniences — the YAML file can be edited manually or by any tool.
