# Implementation Plan: okf-tools

## Overview

Build the okf-tools CLI and library from scratch, implementing all 18 requirements. The build order ensures a working tool at each step: scaffold → parsing → authoring → search → navigation → validation → stats → skills → docs.

## Tasks

- [x] 1. Create project scaffold with pyproject.toml (name: okf-tools, python>=3.9, Apache 2.0), dependencies (click>=8.0,<9.0, fastembed>=0.3.0,<1.0, sqlite-vec>=0.1.0,<1.0, python-frontmatter>=1.0,<2.0, pyyaml>=6.0), dev deps (pytest), entry point `okf = "okf_tools.cli:okf"`, directory structure (src/okf_tools/, tests/, tests/fixtures/sample_bundle/, skills/, docs/), __init__.py with version, .gitignore, and LICENSE file
  Requirements: R1, R12

- [x] 2. Create errors module (src/okf_tools/errors.py) with error hierarchy: OkfError base, ConceptNotFoundError(concept_id), ValidationError(errors: list[str]), IndexCorruptionError, BundleAlreadyInitialisedError, ConfigError(path, reason), ParseError(path, reason)
  Requirements: R15

- [x] 3. Create config module (src/okf_tools/config.py) with OkfConfig dataclass, get_defaults() returning built-in defaults, load_config(bundle_root) loading and merging .okf/config.json → ~/.config/okf/config.json → defaults per-field, find_bundle_root(start_path) walking up directories, and ConfigError on invalid JSON
  Requirements: R12.1, R12.2, R12.3, R12.4, R12.5, R12.6

- [x] 4. Create bundle parser (src/okf_tools/bundle.py) with Concept dataclass (concept_id, frontmatter, body, file_path, properties for title/type/tags/timestamp), parse_concept(file_path, bundle_root) using python-frontmatter, format_concept(concept) producing ---YAML---\n\nbody\n, validate_frontmatter checking type required+non-empty, timestamp ISO 8601, tags is list of strings, and ParseError on invalid files
  Requirements: R17.1, R17.2, R17.3, R17.4, R17.5, R16.1, R16.2, R16.3, R16.4, R16.5, R16.6

- [x] 5. Implement bundle I/O functions: generate_slug(title) with lowercase/hyphens/60-char-word-boundary-truncation, resolve_unique_path(dir, slug) appending -2/-3 for collisions, walk_concepts(bundle_root) finding all .md excluding index.md/log.md, write_concept(concept, bundle_root) creating dirs and writing, update_index_file and remove_from_index_file managing directory index.md entries
  Requirements: R2.2, R2.3, R2.4, R2.7, R4.2, R5.1, R9.7

- [x] 6. Create search module (src/okf_tools/search.py) with VectorIndex class: init sqlite-vec DB with WAL mode, create sync_meta/concepts/vec_concepts tables, implement upsert/delete/search (cosine similarity with threshold and top-n)/get_all_concept_ids/get_sync_timestamp/set_sync_timestamp/concept_count/check_integrity. Add module-level get_embedder (lazy cached), embed_text, and embed_batch functions using fastembed
  Requirements: R7.1, R7.2, R7.3, R7.4, R7.5, R9.1, R9.6, R15.3

- [x] 7. Create graph module (src/okf_tools/graph.py) with LinkGraph class backed by SQLite links table: extract_links(concept, bundle_root) parsing [text](url) patterns for internal .md links, set_links/remove_concept/get_outlinks/get_inlinks, bfs_neighborhood(concept_id, depth, direction), get_orphans(all_concept_ids), get_stats(total_concepts)
  Requirements: R8.1, R8.2, R8.3, R8.4, R8.5, R8.6, R8.7, R8.8, R10.1

- [x] 8. Create sync module (src/okf_tools/sync.py) with ChangeSet/SyncSummary dataclasses, detect_changes comparing filesystem mtimes vs indexed mtimes, incremental_reindex processing only changed files (parse → batch embed → upsert → update links → remove deleted → set timestamp), full_reindex dropping all data and rebuilding, handling embedding failures by skipping with report
  Requirements: R9.1, R9.2, R9.3, R9.4, R9.5, R9.6, R9.7, R9.8, R9.9, R9.10

- [x] 9. Create service module (src/okf_tools/service.py) implementing: init_bundle (create .okf/config.json + index.md + .gitignore), commit_concept (validate → slug → path → duplicates → write → index → embed → links → git add), update_concept (verify → merge → validate → write → re-embed → index update → git add), delete_concept (verify → remove file → index → vector → graph → git add), fetch_concepts, list_concepts with all filters, show_concept, get_links, reindex (with optional --lint integration), get_stats, list_skills, lint_bundle
  Requirements: R1, R2, R3, R4, R5, R6, R7, R8, R9, R10, R13, R18

- [x] 10. Create skills module (src/okf_tools/skills.py) with discover_skills scanning configured paths (skip missing dirs), parsing .md files for frontmatter, resolving title (frontmatter → first heading → filename), extracting description. Create skills/core-knowledge.md with default OKF steering content (including guidance to run okf lint after bulk operations). Always include bundled skill in results
  Requirements: R13.1, R13.2, R13.3, R13.4, R13.5, R13.6

- [x] 11. Create validation module (src/okf_tools/validation.py) with lint_bundle() orchestrating all checks, validate_structure() checking index.md presence and entry consistency, check_link_integrity() reporting broken internal links, check_type_consistency() detecting near-duplicate types via normalization, validate_concept_full() applying configurable strictness levels. Define rule identifiers (frontmatter/*, structure/*, links/*, types/*). Support path and rule filtering
  Requirements: R18.1, R18.2, R18.3, R18.5, R18.6, R18.7, R18.8, R18.9, R18.10, R18.11, R18.12, R18.14, R18.15

- [x] 12. Create CLI module (src/okf_tools/cli.py) with Click group `okf` accepting --format json|text|brief with TTY auto-detection, shared output() helper routing to formatters, handle_error() writing to stderr. Implement all subcommands: init, commit, update, delete, list, show, fetch, links, reindex (with --lint flag), stats, skills, lint (with --warn-only, --path, --rule) — each catching OkfError and formatting appropriately. Brief format shows concept_id\ttitle per line. JSON format outputs valid JSON only to stdout. Lint JSON output structured per R18.5
  Requirements: R1, R2, R3, R4, R5, R6, R7, R8, R9, R10, R11, R13, R14, R15, R18

- [x] 13. Create test fixtures: tests/fixtures/sample_bundle/ with root index.md, .okf/config.json, 6-8 concept files across patterns/ and decisions/ subdirectories with various types/tags/timestamps/cross-links, one orphan, one bidirectional link pair, extra YAML fields. Include lint-specific fixtures: a directory missing index.md, a broken internal link, near-duplicate type values (e.g., "Bug Fix" and "bug-fix"). Create tests/conftest.py with shared fixtures (tmp bundle, initialized VectorIndex, sample config)
  Requirements: All

- [x] 14. Create unit tests: test_bundle.py (parse/format round-trip, slug edge cases, collision resolution, index.md ops, validation), test_search.py (index CRUD, search filtering, empty index, integrity), test_graph.py (link extraction patterns, BFS, orphans), test_sync.py (change detection, incremental/full reindex), test_config.py (defaults, merge precedence, invalid JSON, validation_level), test_skills.py (discovery, missing dirs, title fallback), test_validation.py (structural checks, link integrity, type consistency, validation levels, rule filtering, path filtering), test_service.py (commit→fetch, update→show, delete→list, lint integration), test_cli.py (format selection, TTY mock, error formatting, lint exit codes and --warn-only)
  Requirements: All

- [x] 15. Create documentation: README.md (description, quick start, badges), CONTRIBUTING.md (dev setup, tests, style), docs/getting-started.md (install → init → commit → fetch → lint), docs/cli-reference.md (all commands including okf lint with examples), docs/architecture.md (components including validation module, data flow, decisions), docs/skills.md (writing skill packs), docs/for-agent-authors.md (steering integration, hooks, JSON output, lint in CI workflows)
  Requirements: Documentation

## Task Dependency Graph

```json
{
  "waves": [
    [1],
    [2],
    [3, 4, 10],
    [5, 6, 7],
    [8],
    [9, 11],
    [12],
    [13],
    [14],
    [15]
  ]
}
```

- Wave 1: Project scaffold (no dependencies)
- Wave 2: Errors module (depends on scaffold)
- Wave 3: Config, Bundle Parser, Skills module (depend on errors, can run in parallel)
- Wave 4: Bundle I/O, Search, Graph modules (depend on bundle parser/errors, can run in parallel)
- Wave 5: Sync module (depends on search + graph + bundle I/O)
- Wave 6: Service module + Validation module (service depends on all domain modules; validation depends on bundle parser + graph, can run in parallel with service)
- Wave 7: CLI module (depends on service + validation)
- Wave 8: Test fixtures (depends on modules being defined)
- Wave 9: Unit tests (depends on fixtures)
- Wave 10: Documentation (depends on CLI being complete)

- [x] 16. Add multi-bundle support to config module: Add `BundleRef` dataclass (name, path, writable=True, default=False), extend `OkfConfig` with a `bundles: List[BundleRef]` field, parse `"bundles"` array from user-level and project-level configs. `writable` defaults to `true` (all bundles writable unless explicitly locked). `default` marks which bundle receives writes when `--bundle` is not specified. Maintain backward compatibility — if old-style single `bundle_path` is present and no `bundles` array exists, synthesise a single-entry bundles list. Resolution order: project-level bundles (from `.okf/config.json` in cwd ancestors) then user-level bundles (from `~/.config/okf/config.json`). Each bundle has its own `.okf/index/okf.db` sidecar at `<bundle_path>/.okf/index/`.
  Requirements: R12

- [x] 17. Add `--bundle / -b` CLI option to the `okf` group: Pass bundle name through context. For write commands (commit, update, delete), target the named bundle (must be writable) or the default bundle if unspecified. For read commands (fetch, list, show, links, stats), default to all bundles unless `--bundle` narrows scope. Add `bundle` field to SearchResult output.
  Requirements: R12, R7, R2, R3, R4

- [x] 18. Implement aggregated search across multiple bundles: `fetch_concepts` in service.py iterates all configured bundles, queries each bundle's VectorIndex, merges results by score (descending), tags each result with its source bundle name. Deduplicate by concept_id (prefer highest score if same concept in multiple bundles). Respect `--bundle` flag to search a single bundle.
  Requirements: R7

- [x] 19. Implement write routing for multi-bundle: `commit_concept`, `update_concept`, and `delete_concept` in service.py route to the target bundle. If `--bundle` is specified, use that bundle. Otherwise use the bundle marked `"default": true`. If no default is set, use the first bundle in the list. If a bundle is explicitly marked `"writable": false`, raise a clear error. Since `writable` defaults to `true`, all bundles accept writes unless explicitly locked.
  Requirements: R2, R3, R4

- [x] 20. Update `init_bundle` for multi-bundle awareness: When `okf init` is run in a directory, it creates the standard `.okf/config.json` but also offers to register the new bundle in `~/.config/okf/config.json` bundles array (if the user-level config exists). Add `--register` flag to auto-add.
  Requirements: R1

- [x] 21. Update steering file for multi-bundle: Update the installed steering file (`~/.kiro/steering/okf-knowledge.md` or equivalent) to document `--bundle / -b` flag usage, explain personal vs shared bundle patterns, provide examples of user-level config with multiple bundles, and update the command reference table to show bundle-targeting syntax.
  Requirements: Documentation

- [x] 22. Update `skills/core-knowledge.md`: Add multi-bundle guidance for agents — when to use `--bundle`, how shared knowledge accumulates, how to check which bundles are configured, and default write-target behaviour.
  Requirements: Documentation

- [x] 23. Update `docs/getting-started.md`: Add a "Multi-Bundle Setup" section covering initial setup with personal + shared bundles, user-level config creation, and first commit to a shared bundle.
  Requirements: Documentation

- [x] 24. Update `docs/cli-reference.md`: Document the new `--bundle / -b` global option on the `okf` group, show examples for commit/fetch/list with explicit bundle targeting, and document `okf init --register`.
  Requirements: Documentation

- [x] 25. Update `docs/architecture.md`: Add a "Multi-Bundle Architecture" section explaining bundle resolution order, per-bundle sidecar indexes, aggregated search, write routing, and the config merging model.
  Requirements: Documentation

- [x] 26. Update `docs/for-agent-authors.md`: Add guidance on agentic multi-bundle workflows — how agents should default to the team bundle for shared knowledge, when to use personal bundles, and how `--bundle` integrates with steering prompts.
  Requirements: Documentation

- [x] 27. Update `README.md`: Add multi-bundle to the feature list, update the quick-start example to show multi-bundle config, and mention shared team bundles as a primary use case.
  Requirements: Documentation

- [x] 28. Update `.kiro/OKF_TOOLS_AGENT_PROMPT.md`: Sync the agent prompt with multi-bundle CLI changes so that agents using this tool understand the `--bundle` flag and default write behaviour.
  Requirements: Documentation

- [x] 29. Update `scripts/install-agent-support.sh`: Ensure the install script sets up a user-level config with a bundles array (prompting for personal bundle path) and installs the updated steering file that documents multi-bundle usage.
  Requirements: Documentation

- [x] 30. Add tests for multi-bundle: test_config.py — verify bundles array parsing, backward compat with single bundle_path, resolution order, writable defaults to true; test_service.py — verify aggregated search merges results from multiple bundles, write routing targets default bundle, explicit --bundle override works; test_cli.py — verify --bundle flag passes through correctly, init --register adds to user config.
  Requirements: All

## Task Dependency Graph (Multi-Bundle Feature)

```json
{
  "waves": [
    [16],
    [17, 19],
    [18, 20],
    [21, 22, 23, 24, 25, 26, 27, 28, 29],
    [30]
  ]
}
```

- Wave 1: Config changes (foundation for everything else)
- Wave 2: CLI option + write routing (can be parallel — CLI just passes the flag, service routes writes)
- Wave 3: Aggregated search + init update (depend on config + CLI option)
- Wave 4: Documentation updates (all docs/steering/scripts can be done in parallel once implementation is settled)
- Wave 5: Tests (depends on all implementation + docs being finalised)

## Notes

- The fastembed model download (~30MB) happens on first use. CI should cache `~/.cache/fastembed/`.
- sqlite-vec requires the `sqlite_vec` Python package which bundles the native extension — no system-level SQLite compilation needed.
- All modules share the same `okf.db` SQLite file in `.okf/index/` — VectorIndex and LinkGraph connect to the same database path.
- Python 3.9 compatibility: avoid `match` statements, use `dict` instead of `dict[str, Any]` in runtime code (use `from __future__ import annotations` or string annotations for type hints).
- Multi-bundle: each bundle maintains its own sidecar index independently. All bundles are writable by default — `"writable": false` is an opt-in lock for reference bundles you don't want agents modifying. The shared team bundle is the ideal default write target for agentic use so knowledge is automatically shared. Shared bundles are synced between teammates via git (commit + push/pull).
- Example user-level config (`~/.config/okf/config.json`):
  ```json
  {
    "bundles": [
      {"name": "personal", "path": "~/personal/my-okf"},
      {"name": "team", "path": "/shared/team-okf", "default": true}
    ]
  }
  ```
