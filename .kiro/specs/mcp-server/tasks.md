# Implementation Plan: MCP Server

## Overview

Add an MCP server module (`src/okf_tools/server.py`) that wraps the existing `service.py` functions as MCP tools using the FastMCP SDK. The server exposes 9 tools over stdio transport, maps domain errors to MCP error responses, and is launched via the `okf-mcp` entry point. Tests cover both example-based scenarios and property-based correctness.

## Tasks

- [x] 1. Add dependencies and entry point to pyproject.toml
  - [x] 1.1 Add `mcp>=1.0,<2.0` to project dependencies, add `hypothesis>=6.0` and `pytest-asyncio>=0.21` to dev dependencies, and add `okf-mcp = "okf_tools.server:main"` to `[project.scripts]`
    - Edit `pyproject.toml` to add the mcp runtime dependency, the two dev dependencies, and the new script entry point
    - _Requirements: 1.1, 1.2, 12.1_

- [x] 2. Implement MCP server core and tool handlers
  - [x] 2.1 Create `src/okf_tools/server.py` with FastMCP instance, startup logic, and `_require_bundle` helper
    - Create the module with `mcp = FastMCP("okf-tools")` at module level
    - Add module-level `_config: Optional[OkfConfig] = None`
    - Implement `main()` that parses `--bundle-path`, resolves config via `find_bundle_root`, configures stderr logging, and calls `mcp.run(transport="stdio")`
    - Implement `_require_bundle()` helper that raises an MCP error if `_config` is None
    - Implement `_handle_error(e: OkfError)` helper that maps domain errors to MCP error content strings
    - Validate `--bundle-path` exists and is a directory; exit with error if invalid
    - If no bundle is found and no `--bundle-path` given, start with `_config = None`
    - All logging to stderr, never stdout
    - _Requirements: 1.1, 1.2, 1.3, 12.1, 12.2, 12.3, 12.4, 11.4_

  - [x] 2.2 Implement `init_bundle` tool handler
    - Decorate with `@mcp.tool()`
    - Accept optional `path` parameter (defaults to cwd)
    - Validate path exists and is a directory
    - Call `service.init_bundle(Path(path))`
    - On success, update module `_config` by loading config from the new bundle, return JSON with absolute path
    - Catch `BundleAlreadyInitialisedError` and return `isError=true` response
    - This is the only tool that does NOT call `_require_bundle()`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 11.3_

  - [x] 2.3 Implement `commit_concept` tool handler
    - Decorate with `@mcp.tool()`
    - Accept `title`, `type`, `content` (required), `tags`, `path`, `check_duplicates` (optional, default true)
    - Call `_require_bundle()`
    - Build input dict and call `service.commit_concept(_config, input_data)`
    - Return JSON with `concept_id`
    - Catch `ValidationError` and return `isError=true` with all error messages
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 11.1_

  - [x] 2.4 Implement `update_concept` tool handler
    - Decorate with `@mcp.tool()`
    - Accept `concept_id` (required), optional `title`, `type`, `tags`, `content`
    - Call `_require_bundle()`
    - Validate at least one update field provided, return validation error if none
    - Build updates dict from non-None fields, call `service.update_concept(_config, concept_id, updates)`
    - Return JSON with `concept_id`
    - Catch `ConceptNotFoundError`, `ValidationError` and return appropriate `isError=true` responses
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 11.1, 11.2_

  - [x] 2.5 Implement `delete_concept` tool handler
    - Decorate with `@mcp.tool()`
    - Accept `concept_id` (required)
    - Call `_require_bundle()` and `service.delete_concept(_config, concept_id)`
    - Return JSON with deleted `concept_id`
    - Catch `ConceptNotFoundError` and return `isError=true`
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 11.2_

  - [x] 2.6 Implement `fetch_concepts` tool handler
    - Decorate with `@mcp.tool()`
    - Accept `query` (required), `top_n`, `threshold`, `type`, `tags`, `mode` (optional)
    - Call `_require_bundle()`
    - Validate query is not empty/whitespace-only, return validation error if so
    - Call `service.fetch_concepts(_config, query, top_n, threshold, type, tags, mode)`
    - Format results as JSON list with `concept_id`, `title`, `score`, `snippet` (truncated to 200 chars)
    - Return empty list without error when no index exists
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 11.1_

  - [x] 2.7 Implement `list_concepts` tool handler
    - Decorate with `@mcp.tool()`
    - Accept optional `type`, `tags`, `since`, `limit` (default 100), `path`
    - Call `_require_bundle()`
    - Call `service.list_concepts(_config, type, tags, since, limit, path)`
    - Format results as JSON list with `concept_id`, `title`, `type`, `tags` per entry
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

  - [x] 2.8 Implement `show_concept` tool handler
    - Decorate with `@mcp.tool()`
    - Accept `concept_id` (required)
    - Call `_require_bundle()` and `service.show_concept(_config, concept_id)`
    - Return JSON with `concept_id`, all frontmatter fields, and `body` (full markdown content)
    - Catch `ConceptNotFoundError` and return `isError=true`
    - _Requirements: 8.1, 8.2, 8.3, 11.2_

  - [x] 2.9 Implement `reindex` tool handler
    - Decorate with `@mcp.tool()`
    - Accept optional `full` (bool, default false)
    - Call `_require_bundle()` and `service.reindex(_config, full)`
    - Return JSON summary with `added`, `updated`, `removed`, `skipped`, `total_indexed`
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

  - [x] 2.10 Implement `get_stats` tool handler
    - Decorate with `@mcp.tool()`
    - Accept no parameters
    - Call `_require_bundle()` and `service.get_stats(_config)`
    - Return JSON with `concept_count`, `type_distribution`, `tag_distribution`, `last_reindex_timestamp`, `pending_reembedding_count`
    - _Requirements: 10.1, 10.2, 10.3, 10.4_

  - [x] 2.11 Add catch-all exception handler to all tool handlers
    - Wrap each handler body with a try/except that catches unexpected `Exception`
    - Log full traceback to stderr at ERROR level
    - Return generic "An internal error occurred" with `isError=true` — no stack trace, no file paths
    - _Requirements: 11.4_

- [x] 3. Checkpoint - Verify server module
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Example-based tests
  - [x] 4.1 Create `tests/test_server.py` with test infrastructure
    - Import server module and tool handler functions
    - Set up fixtures that configure `server._config` with `sample_config` from conftest
    - Mock `service` functions (embed_text, VectorIndex) to avoid real embedding calls
    - Use `pytest-asyncio` for async test support
    - _Requirements: 1.2, 12.1_

  - [x] 4.2 Write tests for server startup and bundle path resolution
    - Test `main()` with `--bundle-path` pointing to a valid tmp_bundle
    - Test `main()` with `--bundle-path` pointing to nonexistent path (expect exit with error)
    - Test startup without arguments resolves bundle from cwd (mock `find_bundle_root`)
    - Test startup with no bundle found sets `_config = None`
    - _Requirements: 12.1, 12.2, 12.3, 12.4_

  - [x] 4.3 Write tests for `init_bundle` handler
    - Test successful init creates bundle and returns path
    - Test init on existing bundle returns error
    - Test init with invalid path returns validation error
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [x] 4.4 Write tests for `commit_concept` and `show_concept` handlers
    - Test successful commit returns concept_id
    - Test commit with missing required fields returns validation error listing fields
    - Test commit when no bundle configured returns bundle-not-configured error
    - Test show returns full concept data
    - Test show with nonexistent concept_id returns not-found error
    - _Requirements: 3.1, 3.2, 3.3, 3.5, 8.1, 8.2, 8.3_

  - [x] 4.5 Write tests for `update_concept` and `delete_concept` handlers
    - Test update applies only specified fields
    - Test update with no fields returns validation error
    - Test update on nonexistent concept returns not-found error
    - Test delete removes concept and returns concept_id
    - Test delete on nonexistent concept returns not-found error
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 5.1, 5.2, 5.3_

  - [x] 4.6 Write tests for `fetch_concepts` handler
    - Test search returns results with correct structure
    - Test whitespace-only query returns validation error
    - Test search with no index returns empty list
    - Test type and tags filters narrow results
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [x] 4.7 Write tests for `list_concepts`, `reindex`, and `get_stats` handlers
    - Test list returns sorted results with correct fields
    - Test list with filters
    - Test reindex returns summary with correct integer fields
    - Test get_stats returns correct structure
    - Test get_stats with no bundle returns error
    - _Requirements: 7.1, 7.2, 7.3, 9.1, 9.2, 10.1, 10.2, 10.3_

- [x] 5. Checkpoint - Ensure all example tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Property-based tests
  - [x] 6.1 Create `tests/test_server_properties.py` with hypothesis strategies and shared fixtures
    - Define strategies for valid concept titles (non-empty strings, printable)
    - Define strategies for valid types (non-empty strings from known set)
    - Define strategies for valid content (non-empty strings)
    - Define strategies for valid tags (lists of non-empty strings)
    - Set up fixtures with mocked embedding layer and in-memory bundle
    - **Property 1: Commit-then-show round-trip preserves data**
    - **Validates: Requirements 3.2, 8.2**

  - [x] 6.2 Write property test for missing required fields enumeration
    - Generate all non-empty proper subsets of {title, type, content} to omit
    - Assert the validation error lists exactly those missing fields
    - **Property 2: Missing required fields are enumerated in validation error**
    - **Validates: Requirements 3.3**

  - [x] 6.3 Write property test for update applying only provided fields
    - Generate a random existing concept and a random non-empty subset of update fields
    - Assert only specified fields change; all others remain at prior values
    - **Property 3: Update applies only provided fields**
    - **Validates: Requirements 4.2**

  - [x] 6.4 Write property test for invalid updates being rejected without modification
    - Generate updates that produce invalid frontmatter (empty type, non-list tags, etc.)
    - Assert validation error is returned and concept file remains unchanged
    - **Property 4: Invalid updates are rejected without modifying the concept**
    - **Validates: Requirements 4.5**

  - [x] 6.5 Write property test for delete removes concept
    - Generate a concept, delete it, assert file no longer exists and response contains concept_id
    - **Property 5: Delete removes concept and returns concept_id**
    - **Validates: Requirements 5.2**

  - [x] 6.6 Write property test for search result structure
    - Generate random queries against a pre-populated bundle
    - Assert each result has non-empty concept_id, title string, score in [0.0, 1.0], snippet ≤ 200 chars
    - **Property 6: Search results have valid structure**
    - **Validates: Requirements 6.2**

  - [x] 6.7 Write property test for whitespace-only query rejection
    - Generate strings composed entirely of whitespace (spaces, tabs, newlines)
    - Assert validation error is returned for each
    - **Property 7: Whitespace-only queries are rejected**
    - **Validates: Requirements 6.5**

  - [x] 6.8 Write property test for list results sorted and structurally complete
    - Generate a bundle with multiple concepts, call list_concepts
    - Assert results are sorted by concept_id and each has concept_id, title, type, tags
    - **Property 8: List results are sorted and structurally complete**
    - **Validates: Requirements 7.2**

  - [x] 6.9 Write property test for stats response structure
    - Generate bundles with varying concept counts
    - Assert get_stats returns correct types: concept_count ≥ 0, distributions are dicts with int values, pending ≥ 0
    - **Property 9: Stats response has correct structure and types**
    - **Validates: Requirements 10.2**

  - [x] 6.10 Write property test for domain error mapping
    - Generate ValidationErrors with N messages and ConceptNotFoundErrors with random IDs
    - Assert all N messages appear in MCP error response; assert concept_id appears for not-found
    - **Property 10: Domain errors map to MCP error responses with full context**
    - **Validates: Requirements 11.1, 11.2**

  - [x] 6.11 Write property test for unexpected error sanitization
    - Generate exceptions with tracebacks, file paths, and class names
    - Assert MCP response contains none of those internal details
    - **Property 11: Unexpected errors do not expose internal details**
    - **Validates: Requirements 11.4**

  - [x] 6.12 Write property test for non-init tools require configured bundle
    - For each tool (except init_bundle), invoke with _config = None
    - Assert error response indicates no bundle is configured
    - **Property 12: Non-init tools require a configured bundle**
    - **Validates: Requirements 12.5**

- [x] 7. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific scenarios and edge cases
- The existing `conftest.py` fixtures (`tmp_bundle`, `sample_config`, `create_concept_file`) are reused
- All embedding calls are mocked in tests to avoid heavy model downloads
- The `mcp` SDK handles JSON-RPC protocol details (parse errors, invalid requests) automatically

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["2.1"] },
    { "id": 2, "tasks": ["2.2", "2.3", "2.4", "2.5", "2.6", "2.7", "2.8", "2.9", "2.10"] },
    { "id": 3, "tasks": ["2.11"] },
    { "id": 4, "tasks": ["4.1"] },
    { "id": 5, "tasks": ["4.2", "4.3", "4.4", "4.5", "4.6", "4.7"] },
    { "id": 6, "tasks": ["6.1"] },
    { "id": 7, "tasks": ["6.2", "6.3", "6.4", "6.5", "6.6", "6.7", "6.8", "6.9", "6.10", "6.11", "6.12"] }
  ]
}
```
