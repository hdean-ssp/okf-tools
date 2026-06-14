---
inclusion: auto
---

# OKF Compliance Standards

When working on this project (okf-tools), enforce OKF compliance as a first-class concern.

## Rules

1. **Always validate OKF compliance** when creating or modifying concept files — ensure `type` is present and non-empty, `timestamp` is ISO 8601 if used, and `tags` is a YAML list of strings.

2. **Run `okf lint` as a verification step** after any bulk operation that touches multiple concept files (commits, imports, restructuring, or automated generation).

3. **Use strict mode during development** — set `"validation_level": "strict"` in `.okf/config.json` to catch missing `title` and `description` fields early.

4. **Treat lint errors as blockers** — do not consider a task complete if `okf lint` reports errors. Warnings can be deferred but should be tracked.

5. **Validate link integrity** after renaming or moving concept files. Run `okf lint --rule links` to catch broken internal references.

6. **Maintain type consistency** — before introducing a new type value, run `okf lint --rule types` to check for near-duplicate existing values. Prefer an existing canonical form over creating a variant.

7. **Ensure structural completeness** — every directory containing concept `.md` files must have an `index.md`. After creating new directories, verify with `okf lint --rule structure`.

## Integration with CI

For automated pipelines, use:
```bash
okf lint --format json
```

This outputs machine-readable diagnostics suitable for CI reporting tools. Exit code 1 indicates errors were found.
