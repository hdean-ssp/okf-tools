# Known Risks & Assumptions

## OKF Spec Stability

okf-tools targets [OKF v0.1](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md), a draft spec from Google Cloud Platform's knowledge-catalog repo.

**Risk:** The spec has limited adoption visibility. If Google abandons it or makes breaking changes, okf-tools' compliance story breaks.

**Our stance:**
- The OKF format is simple (markdown + YAML frontmatter with a `type` field). Even if the spec is abandoned, the file format remains useful.
- If the spec changes substantially, we'll either adapt or fork our format definition. The sidecar index is derived data — only the `.md` files matter.
- We track spec version in `okf --version` output so users know what they're targeting.

## Pre-1.0 Dependencies

| Dependency | Version range | What breaks if it changes |
|-----------|---------------|--------------------------|
| `fastembed` | `>=0.3.0,<1.0` | If embedding output dimensions change or model loading API changes, the entire vector index becomes invalid. Requires `okf reindex --full`. |
| `sqlite-vec` | `>=0.1.0,<1.0` | If the `vec0` virtual table syntax changes, the sidecar database can't be opened. Requires rebuilding the index. |

**Mitigation:**
- The sidecar index (`.okf/index/okf.db`) is always rebuildable from source `.md` files via `okf reindex --full`.
- Index version metadata (embedding model + dimensions) is stored in the database. On mismatch, the tool warns and suggests reindex.
- We pin to `<1.0` upper bounds to avoid surprise breaking changes, and will add migration paths when upgrading.

## Agent Behaviour Assumptions

okf-tools assumes agents will follow a fetch → work → commit workflow. In practice:

- Agents are unreliable at multi-step protocols without direct prompting
- Hooks nudge but don't enforce (the agent can still ignore them)
- Knowledge quality depends on the agent's judgment about what's worth committing

See [For Agent Authors > Limitations](for-agent-authors.md#limitations--known-issues) for mitigation strategies.

## Platform Compatibility

- **sqlite-vec** bundles a native extension. This can be fragile on ARM, older glibc, or non-standard Python builds.
- **First run** downloads ~30MB embedding model (BAAI/bge-small-en-v1.5) via fastembed. No network access needed after that.
- **Install script** only supports bash. Users on other shells need manual PATH configuration.
