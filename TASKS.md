# okf-tools Improvement Task List

Two-branch strategy with a shared goal: make okf-tools demonstrably useful as an OKF companion toolkit and a measurable AI proof point.

- **`main`** — Core tool (this branch). Focused on the essential loop: init → commit → fetch → reindex. Proves "local semantic search over markdown is useful" with minimal complexity.
- **`ssp-full`** — Extended version with multi-bundle support, link graph traversal, compliance linting, skills system, and Kiro-specific install script. Demonstrates the full agent-integrated workflow.

Both branches share the "Proof-Point & Usability" tasks (section below) — each implements them in its own context.

---

## `main` — Polish the full-featured version

Everything below happens on main. Ship what we have, but fix the rough edges.

### Documentation & Honesty

- [ ] **1. Fix similarity_threshold documentation mismatch**
  - Requirements doc says default is `1.0`, implementation uses `0.85` (correct)
  - Update requirements doc to match. Add rationale comment in config.py.
  - Files: `.kiro/specs/okf-tools/requirements.md`, `src/okf_tools/config.py`

- [ ] **2. Document wikilinks as a non-OKF extension**
  - `[[concept-id]]` isn't in the OKF spec. Be upfront about it.
  - Add "Extensions beyond OKF" section to architecture.md
  - Note in README that bundles are "OKF-compatible with tooling extensions"
  - Files: `docs/architecture.md`, `README.md`

- [ ] **3. Clarify scope: OKF tooling vs agent framework**
  - Table in architecture.md: core layer (init, commit, fetch, reindex, lint) vs integration layer (skills, steering, hooks, multi-bundle routing)
  - File: `docs/architecture.md`

- [ ] **4. Document agent reliability limitations**
  - Add "Limitations" section to for-agent-authors.md
  - Be honest: agents skip fetch, commit garbage, ignore lint. Hooks help but aren't guaranteed.
  - Add curation guidance: bundles need periodic human review
  - Files: `docs/for-agent-authors.md`, `docs/getting-started.md`

- [ ] **5. Add known risks documentation**
  - OKF spec is v0.1 draft — document our stance and migration strategy
  - Pre-1.0 deps (fastembed, sqlite-vec) — what breaks if they change
  - Add to README or new `docs/risks.md`

- [ ] **6. Make single-bundle the prominent getting-started path**
  - Show minimal "init and go" workflow first, multi-bundle as an advanced topic
  - Ensure `-b <name>` gives a helpful message when only one bundle exists
  - Files: `docs/getting-started.md`, `src/okf_tools/cli.py`

### Code Quality

- [ ] **7. Eliminate private attribute access in sync.py**
  - Add public `VectorIndex.clear()` and `LinkGraph.clear()` methods
  - Replace `index._conn.execute("DELETE FROM ...")` calls in `full_reindex()`
  - Files: `src/okf_tools/search.py`, `src/okf_tools/graph.py`, `src/okf_tools/sync.py`

- [ ] **8. Add index version metadata**
  - Store embedding model name + dimension in `sync_meta` table on reindex
  - On load, check stored model vs config — warn + suggest reindex on mismatch
  - File: `src/okf_tools/search.py`

- [ ] **9. Add `--dry-run` to `okf commit`**
  - Shows what would be written (title, type, tags, target bundle) without persisting
  - Useful for agents and humans alike
  - Files: `src/okf_tools/cli.py`, `src/okf_tools/service.py`

- [ ] **10. Improve duplicate detection feedback**
  - When `--check-duplicates` finds a near-match, show the existing concept title + snippet
  - Files: `src/okf_tools/service.py`, `src/okf_tools/cli.py`

- [ ] **11. Add spec version to `okf --version` output**
  - e.g. "okf-tools 0.1.0 (targeting OKF spec v0.1)"
  - Files: `src/okf_tools/cli.py`, `pyproject.toml`

### Install & Onboarding

- [ ] **12. Add first-run model download notice**
  - Warn about ~30MB download in install script output and getting-started.md
  - Files: `scripts/install-agent-support.sh`, `docs/getting-started.md`

---

## `core-only` — Minimal viable knowledge tool

Branch off main, then strip down. Proves the thesis: "local semantic search over markdown is useful" without the complexity. Includes IDE-agnostic agent guidance files at the repo root so users can drop them into any agentic IDE (Kiro, Cursor, Windsurf, etc.).

### What stays

- `okf init` — create a bundle
- `okf commit` — write a concept (with `--check-duplicates`)
- `okf fetch` — hybrid search (BM25 + vector)
- `okf show` — display a concept
- `okf reindex` — rebuild index
- `okf --version`
- Single bundle only (no `-b`, no bundles array in config)
- Incremental indexing via mtime
- Agent steering/hook files (at repo root, IDE-agnostic)

### What gets removed

- [ ] **13. Remove multi-bundle config system**
  - Strip `BundleRef`, `bundles` array, `-b` flag, bundle resolution logic
  - Config becomes: `bundle_path`, `index_path`, `embedding_model`, `default_top_n`, `similarity_threshold`
  - Files: `src/okf_tools/config.py`, `src/okf_tools/cli.py`

- [ ] **14. Remove skills system**
  - Delete `src/okf_tools/skills.py`
  - Remove `okf skills` command
  - Remove `skills_paths` from config
  - Files: `src/okf_tools/skills.py`, `src/okf_tools/cli.py`, `src/okf_tools/config.py`

- [ ] **15. Remove link graph and `okf links` command**
  - Delete `src/okf_tools/graph.py`
  - Remove graph-related code from sync.py
  - Remove `okf links` from CLI
  - Files: `src/okf_tools/graph.py`, `src/okf_tools/sync.py`, `src/okf_tools/cli.py`

- [ ] **16. Remove `okf lint` and validation module**
  - Delete `src/okf_tools/validation.py`
  - Remove `okf lint` command, `validation_level` config
  - Files: `src/okf_tools/validation.py`, `src/okf_tools/cli.py`, `src/okf_tools/config.py`

- [ ] **17. Remove install script, move agent files to repo root**
  - Delete `scripts/install-agent-support.sh`
  - Move steering content to `agent/AGENT.md` at repo root — a single markdown file with full usage guide (replaces the Kiro-specific steering file)
  - Move hook definitions to `agent/hooks/` as plain JSON files with a README explaining how to wire them into your IDE (Kiro: copy to `.kiro/hooks/`, Cursor: adapt to `.cursorrules`, etc.)
  - Keep `auto_git_add` as a simple config flag
  - Files: new `agent/` directory, remove `scripts/`, `.kiro/steering/`, `.kiro/hooks/`

- [ ] **18. Simplify docs for core-only**
  - README: what it does, install (`pip install`), quick start (init → commit → fetch), and a section pointing to `agent/` for IDE integration
  - CLI reference: just the 5 commands
  - No architecture doc, no agent-authors doc, no skills docs
  - Files: `README.md`, `docs/`

- [ ] **19. Verify core-only tests pass independently**
  - Keep test_bundle.py, test_config.py, test_search.py
  - Remove test_graph.py, test_validation.py, test_multi_bundle.py, test_fixes.py (if lint-related)
  - Run pytest, ensure green
  - Files: `tests/`

---

## Proof-Point & Usability — Both Branches

Tasks below apply to both `main` and `ssp-full`. Each branch addresses them in its own context (core vs full-featured).

### Use Cases & Examples

- [ ] **20. Add sample bundle with realistic data**
  - Create `examples/sample-bundle/` with 5-8 concepts spanning Architecture, Pattern, Bug Fix, and Decision types
  - Include internal markdown links between concepts
  - Provide a README in the examples dir showing the expected fetch/show output
  - Files: `examples/sample-bundle/`, `examples/README.md`

- [ ] **21. Add `okf export` command for structured markdown output**
  - Export a concept (or set of concepts) as standalone markdown suitable for sharing outside the tool
  - Support: single concept by ID, or batch by type/tag filter
  - Output includes frontmatter, body, and resolved links
  - Files: `src/okf_tools/cli.py`, `src/okf_tools/service.py`

- [ ] **22. Add `--explain` flag to `okf fetch` results**
  - When set, each result includes a short note on why it matched (keyword hit, semantic similarity, or both)
  - Helps developers trust and understand search results
  - Files: `src/okf_tools/search.py`, `src/okf_tools/cli.py`

### Metrics & Measurement

- [ ] **23. Add `okf metrics log` command**
  - Appends a structured observation to `metrics/observations.yaml` (or a configured path)
  - Accepts `--metric`, `--value`, `--notes` and/or `--json` input
  - Creates the metrics directory if it doesn't exist
  - Files: `src/okf_tools/cli.py`, `src/okf_tools/service.py`

- [ ] **24. Add `okf metrics summary` command**
  - Reads `metrics/observations.yaml` and prints a grouped summary table
  - Groups by metric type, shows count, average, and min/max
  - Output in text or JSON
  - Files: `src/okf_tools/cli.py`, `src/okf_tools/service.py`

- [ ] **25. Track fetch usage in sidecar (access_count, last_accessed)**
  - When `okf fetch` returns results, increment `access_count` and update `last_accessed` for each returned concept
  - Useful for knowledge reuse metrics and identifying stale concepts
  - Stored in the sidecar database (derived, rebuildable)
  - Files: `src/okf_tools/search.py`, `src/okf_tools/service.py`

### Reusable Artefact Generation

- [ ] **26. Add `okf summary` command for subsystem overviews**
  - Given a path filter or tag, generate a markdown summary combining related concepts
  - Output: title, purpose (from Architecture concepts), key patterns, known issues (from Bug Fix concepts)
  - Useful for producing onboarding docs or architecture reviews from the bundle
  - Files: `src/okf_tools/cli.py`, `src/okf_tools/service.py`

### Usability

- [ ] **27. Add `okf quickstart` interactive command**
  - A guided walkthrough: init → commit a sample concept → reindex → fetch
  - Prints explanations at each step, suitable for first-time users
  - Can be run non-interactively with `--yes` for scripting/demos
  - Files: `src/okf_tools/cli.py`

- [ ] **28. Improve error messages for common failures**
  - No bundle found → suggest `okf init`
  - No index exists → suggest `okf reindex`
  - Empty fetch results → suggest broader query or `okf list` to see what exists
  - Files: `src/okf_tools/cli.py`, `src/okf_tools/service.py`, `src/okf_tools/errors.py`

---

## Parking Lot (future, either branch)

- [ ] `okf doctor` — environment health check (Python, deps, model, PATH)
- [ ] `okf prune` — surface stale/unused concepts for cleanup
- [ ] Embedding model hot-swap with automatic reindex
- [ ] WASM sqlite-vec for broader platform support
- [ ] Evaluate OKF spec adoption; fork format definition if abandoned
