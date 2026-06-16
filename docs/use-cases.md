# Developer Use Cases

Concrete examples of how okf-tools helps developers working with OKF knowledge bundles.

---

## Use Case 1: Find Relevant Concepts for a Natural-Language Question

**Scenario:** A developer is about to work on retry logic in a service they haven't touched before. They want to know if anyone has documented patterns, decisions, or gotchas related to retries in this codebase.

**Input:**

```bash
okf fetch "retry and error handling patterns"
```

**Expected Output (text mode):**

```
concept_id: patterns/retry-with-backoff
title: Retry with Exponential Backoff
score: 0.89
snippet: When network calls fail transiently, retry with doubling delays and jitter. Max 3 attempts...

concept_id: decisions/circuit-breaker-adoption
title: Circuit Breaker for External APIs
score: 0.76
snippet: After repeated timeout incidents in Q1, we adopted the circuit breaker pattern for all...

concept_id: bugs/timeout-cascade-fix
title: Timeout Cascade in Payment Service
score: 0.71
snippet: Root cause: unbounded retries without backoff caused cascading timeouts across...
```

**Expected Output (JSON mode, for agents):**

```json
[
  {
    "concept_id": "patterns/retry-with-backoff",
    "title": "Retry with Exponential Backoff",
    "score": 0.89,
    "snippet": "When network calls fail transiently, retry with doubling delays and jitter. Max 3 attempts..."
  },
  {
    "concept_id": "decisions/circuit-breaker-adoption",
    "title": "Circuit Breaker for External APIs",
    "score": 0.76,
    "snippet": "After repeated timeout incidents in Q1, we adopted the circuit breaker pattern for all..."
  }
]
```

**Why it's useful:** Instead of grepping source code or searching a wiki, the developer gets ranked, relevant knowledge in seconds. The hybrid search means both exact terminology ("retry") and semantic intent ("error handling patterns") contribute to ranking.

---

## Use Case 2: Understand an Unfamiliar Subsystem Quickly

**Scenario:** A new engineer is assigned to fix a bug in the "payment processing" area. They've never worked on this subsystem. They want a fast path to understanding its purpose, key flows, and known issues.

**Input:**

```bash
# Broad semantic query to find everything relevant
okf fetch "payment processing overview and key flows" --top-n 10

# Filter to architecture concepts only
okf fetch "payment" --type Architecture

# Filter to known bugs in this area
okf fetch "payment" --type "Bug Fix"
```

**Expected Output (architecture filter):**

```
concept_id: architecture/payment-pipeline
title: Payment Processing Pipeline
score: 0.92
snippet: Orders flow through: validation -> fraud check -> gateway charge -> ledger write -> notification...

concept_id: architecture/payment-gateway-integration
title: Payment Gateway Integration
score: 0.84
snippet: We use Stripe as primary, Adyen as fallback. Gateway selection happens in the router...
```

**Expected Output (bug fix filter):**

```
concept_id: bugs/double-charge-race-condition
title: Double Charge Race Condition
score: 0.88
snippet: Under high concurrency, two charges could be submitted for the same order. Fixed by adding...

concept_id: bugs/webhook-replay-idempotency
title: Webhook Replay Causing Duplicate Ledger Entries
score: 0.79
snippet: Stripe webhook retries were processed as new events. Added idempotency key check at...
```

**Why it's useful:** In 30 seconds, the engineer has: the high-level flow, integration details, and known failure modes — all from people who've worked on this area before. Compare this to hours of source reading, git blame archaeology, or waiting for a colleague to be available.

---

## Use Case 3: Agent-Assisted Discovery (Automated Workflow)

**Scenario:** An AI agent is about to refactor error handling across a service. Before making changes, it queries the bundle for context.

> *Agent guidance files* (in the `agent/` directory) instruct the agent on how to use okf-tools — what commands to run and when. These are IDE-agnostic and can be adapted to Kiro, Cursor, Windsurf, or any tool that supports agent configuration.

**Agent workflow:**

```bash
# 1. Agent fetches context before starting work
okf fetch "error handling patterns and conventions in this service"

# 2. Agent reviews results, loads the most relevant
okf show patterns/error-handling-conventions

# 3. Agent completes the refactoring work...

# 4. Agent commits what it learned (new pattern discovered during refactoring)
okf commit --check-duplicates --json '{
  "title": "Structured Error Codes Convention",
  "type": "Pattern",
  "content": "All service errors use the format ERR_{DOMAIN}_{CODE}. See [Error Handling Conventions](patterns/error-handling-conventions.md) for the base pattern. New codes must be registered in error-catalog.md.",
  "tags": ["errors", "conventions", "refactoring"]
}'
```

**Why it's useful:** The agent doesn't start from zero. It finds existing conventions, follows them, and persists new discoveries for the next session (human or agent). Knowledge accumulates across sessions rather than being rediscovered each time.

---

## Use Case 4: Quick Bundle Health Check

**Scenario:** A tech lead wants to understand how well the team bundle is being maintained — are concepts being committed, are there gaps in coverage?

**Input:**

```bash
okf stats
```

**Expected Output:**

```json
{
  "concept_count": 47,
  "type_distribution": {
    "Pattern": 12,
    "Decision": 9,
    "Architecture": 8,
    "Bug Fix": 11,
    "Runbook": 4,
    "API Endpoint": 3
  },
  "tag_distribution": {
    "reliability": 8,
    "payments": 7,
    "authentication": 5,
    "networking": 4
  },
  "last_reindex_timestamp": "2025-06-14T10:32:00",
  "pending_reembedding_count": 2
}
```

**Why it's useful:** At a glance, the lead can see coverage gaps (no "testing" concepts?), maintenance needs, and activity trends. This feeds into curation decisions and can be reported as a proof-point metric.

---

## Summary

| Use Case | Command | Time to Answer |
|----------|---------|---------------|
| Find relevant knowledge | `okf fetch "<question>"` | ~2 seconds |
| Understand a subsystem | `okf fetch "<area>" --type Architecture` | ~5 seconds |
| Agent pre-task context | `okf fetch` (automated) | ~2 seconds |
| Bundle health check | `okf stats` | ~1 second |

Compare these to the manual alternatives: searching wikis (minutes), asking colleagues (hours of context-switching), or reading source code (potentially hours for an unfamiliar area).
