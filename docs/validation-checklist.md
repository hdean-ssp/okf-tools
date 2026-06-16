# Usability Validation Checklist

A lightweight checklist to confirm another engineer can use okf-tools without prior project context.

## Prerequisites

- Python 3.9+
- bash shell
- ~100MB free disk space (for venv + embedding model on first run)

## Validation Steps

Have an engineer who has **not** used okf-tools before work through the following. Record pass/fail and time taken.

---

### 1. Install (target: < 5 minutes)

```bash
git clone https://github.com/hdean-ssp/okf-tools.git
cd okf-tools
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

**Pass criteria:** `okf --version` prints version info without errors.

| Result | Time | Notes |
|--------|------|-------|
| ☐ Pass / ☐ Fail | ___ min | |

---

### 2. Create a Bundle (target: < 2 minutes)

```bash
mkdir /tmp/test-bundle && cd /tmp/test-bundle
okf init
```

> **Note:** Remain in `/tmp/test-bundle` for all subsequent steps in this checklist.

**Pass criteria:** `.okf/config.json` and `index.md` exist in the directory.

| Result | Time | Notes |
|--------|------|-------|
| ☐ Pass / ☐ Fail | ___ min | |

---

### 3. Commit a Concept (target: < 2 minutes)

```bash
okf commit --json '{
  "title": "Database Connection Pooling",
  "type": "Pattern",
  "content": "Use connection pooling for PostgreSQL. Default pool size is 10. Increase for write-heavy services. Each service owns its own pool — no shared connections across service boundaries.",
  "tags": ["database", "performance", "postgres"]
}'
```

**Pass criteria:** Command exits 0, prints a concept_id in output.

| Result | Time | Notes |
|--------|------|-------|
| ☐ Pass / ☐ Fail | ___ min | |

---

### 4. Build the Index (target: < 3 minutes first run, < 10 seconds subsequent)

```bash
okf reindex
```

**Pass criteria:** Command exits 0, reports at least 1 concept indexed. (First run downloads the embedding model — this is expected.)

| Result | Time | Notes |
|--------|------|-------|
| ☐ Pass / ☐ Fail | ___ min | |

---

### 5. Query the Bundle (target: < 10 seconds)

```bash
okf fetch "how to configure database connections"
```

**Pass criteria:** Returns at least one result with a non-zero score. The result should clearly relate to the concept committed in step 3.

| Result | Time | Notes |
|--------|------|-------|
| ☐ Pass / ☐ Fail | ___ sec | |

---

### 6. Understand the Result Without Prior Context (target: pass/fail)

After seeing the search results, can the engineer:

- [ ] Identify what the concept is about from the title and snippet alone?
- [ ] Understand the format (concept_id, title, score, snippet)?
- [ ] Know how to load the full concept (`okf show <concept_id>`)?

**Pass criteria:** All three checked.

| Result | Notes |
|--------|-------|
| ☐ Pass / ☐ Fail | |

---

### 7. View Full Concept (target: < 10 seconds)

```bash
okf show <concept_id from step 3>
```

**Pass criteria:** Displays the full concept with title, type, tags, and body content.

| Result | Time | Notes |
|--------|------|-------|
| ☐ Pass / ☐ Fail | ___ sec | |

---

### 8. List Concepts (target: < 10 seconds)

```bash
okf list
```

**Pass criteria:** Shows at least the one concept committed in step 3.

| Result | Time | Notes |
|--------|------|-------|
| ☐ Pass / ☐ Fail | ___ sec | |

---

## Summary

| Step | Description | Pass? |
|------|-------------|-------|
| 1 | Install | ☐ |
| 2 | Create bundle | ☐ |
| 3 | Commit concept | ☐ |
| 4 | Build index | ☐ |
| 5 | Query bundle | ☐ |
| 6 | Understand result | ☐ |
| 7 | View full concept | ☐ |
| 8 | List concepts | ☐ |

**Total time:** ___ minutes

**Overall assessment:** ☐ Usable without prior context / ☐ Needs improvement

**Friction points noted:**

(Record any confusion, unclear error messages, or unexpected behaviour here)

---

## Notes for Evaluators

- Steps 1-5 constitute the minimum viable workflow: install → create → commit → index → query.
- If any of steps 1-5 fail, the tool has a blocking usability issue.
- Steps 6-8 validate comprehension and discoverability.
- Time targets are loose guides, not hard requirements. The point is to identify friction, not enforce speed.
- Run this on a machine that has NOT been used for okf-tools development (no cached models, no pre-existing config).
