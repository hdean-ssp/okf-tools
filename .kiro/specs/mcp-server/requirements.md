# Requirements Document

## Introduction

This feature converts okf-tools from a CLI-only tool into an MCP (Model Context Protocol) server, exposing the existing service layer functions as MCP tools. This enables any MCP-compatible client (Kiro, Claude Desktop, etc.) to use okf-tools for semantic knowledge management without going through the CLI. The existing core modules (bundle.py, search.py, sync.py, config.py) are reused as-is; the MCP server is a thin transport layer wrapping the service functions.

## Glossary

- **MCP_Server**: The Model Context Protocol server process that exposes okf-tools service functions as MCP tools over stdio transport
- **MCP_Client**: Any MCP-compatible client application (Kiro, Claude Desktop, or other agents) that connects to the MCP_Server
- **Tool**: An MCP tool definition that maps to a single service layer function, including its name, description, and input schema
- **Bundle**: An OKF knowledge bundle — a directory of markdown files with YAML frontmatter and a sidecar vector index
- **Service_Layer**: The existing `service.py` module containing the orchestrated workflows (init, commit, fetch, etc.)
- **Transport**: The communication mechanism between MCP_Client and MCP_Server (stdio or SSE)
- **JSON_RPC**: The JSON-RPC 2.0 protocol used by MCP for request/response communication over the transport

## Requirements

### Requirement 1: MCP Server Initialization

**User Story:** As a developer, I want the MCP server to start and accept connections over stdio transport, so that MCP-compatible clients can discover and invoke okf-tools capabilities.

#### Acceptance Criteria

1. WHEN the MCP_Server process is started, THE MCP_Server SHALL accept JSON_RPC messages over stdin and write responses to stdout
2. WHEN the MCP_Server receives an `initialize` request, THE MCP_Server SHALL respond with server capabilities including the server name "okf-tools", a version string in semver format, and the list of available tool definitions (each with name, description, and JSON Schema input schema)
3. WHEN the MCP_Server starts, THE MCP_Server SHALL resolve the bundle path from the working directory using the existing config resolution logic (find_bundle_root)
4. IF the MCP_Server receives a malformed JSON_RPC message (invalid JSON or missing required JSON_RPC fields), THEN THE MCP_Server SHALL respond with a JSON_RPC error with code -32700 (parse error) or -32600 (invalid request)

### Requirement 2: Bundle Initialization Tool

**User Story:** As an MCP client, I want to initialize a new OKF bundle via the MCP interface, so that I can set up knowledge management in a new directory.

#### Acceptance Criteria

1. THE MCP_Server SHALL expose an `init_bundle` tool that accepts a `path` parameter (string, optional, defaults to current working directory)
2. WHEN the `init_bundle` tool is invoked with a valid path (an existing directory that is writable), THE MCP_Server SHALL create the `.okf/config.json` file, a root `index.md`, update `.gitignore` if a git repo, and return a success message with the absolute initialized path
3. IF the bundle is already initialized at the specified path (`.okf/config.json` exists), THEN THE MCP_Server SHALL return an error response indicating the bundle already exists
4. IF the path does not exist or is not a directory, THEN THE MCP_Server SHALL return a validation error indicating the path is invalid

### Requirement 3: Commit Concept Tool

**User Story:** As an MCP client, I want to create new knowledge concepts via the MCP interface, so that agents can persist learnings into the bundle.

#### Acceptance Criteria

1. THE MCP_Server SHALL expose a `commit_concept` tool that accepts `title` (string, required), `type` (string, required), `content` (string, required), `tags` (array of strings, optional), `path` (string, optional subdirectory within the bundle), and `check_duplicates` (boolean, optional, defaults to true) parameters
2. WHEN the `commit_concept` tool is invoked with valid parameters, THE MCP_Server SHALL create the concept file, update the directory index, embed the content, and return the generated concept_id as a string
3. IF required fields are missing from the input, THEN THE MCP_Server SHALL return a validation error listing each missing field
4. IF `check_duplicates` is true and concepts with similarity score above the configured threshold exist, THEN THE MCP_Server SHALL return an error listing up to 5 similar concepts with their concept_id, title, score, and snippet
5. IF no bundle is configured, THEN THE MCP_Server SHALL return an error indicating that a bundle must be initialized first

### Requirement 4: Update Concept Tool

**User Story:** As an MCP client, I want to update existing concepts via the MCP interface, so that agents can correct or extend knowledge.

#### Acceptance Criteria

1. THE MCP_Server SHALL expose an `update_concept` tool that accepts `concept_id` (string, required) and optional update fields: `title` (string), `type` (string), `tags` (array of strings), and `content` (string)
2. WHEN the `update_concept` tool is invoked with a valid concept_id and at least one update field, THE MCP_Server SHALL apply only the provided fields to the existing concept (leaving unspecified fields unchanged), re-embed the content, update the vector index, and return the concept_id
3. IF the specified concept_id does not exist, THEN THE MCP_Server SHALL return an error indicating the concept was not found
4. IF no update fields are provided in the invocation, THEN THE MCP_Server SHALL return a validation error indicating that at least one update field must be supplied
5. IF the updated frontmatter fails validation, THEN THE MCP_Server SHALL return a validation error listing the invalid fields without modifying the existing concept

### Requirement 5: Delete Concept Tool

**User Story:** As an MCP client, I want to remove obsolete concepts via the MCP interface, so that agents can maintain bundle quality.

#### Acceptance Criteria

1. THE MCP_Server SHALL expose a `delete_concept` tool that accepts `concept_id` (string, required)
2. WHEN the `delete_concept` tool is invoked with a valid concept_id, THE MCP_Server SHALL remove the concept file, remove the entry from the directory index, remove the entry from the vector index, and return a success response containing the deleted concept_id
3. IF the specified concept_id does not exist, THEN THE MCP_Server SHALL return an error indicating the concept was not found
4. IF the concept file is removed but the vector index removal fails, THEN THE MCP_Server SHALL still return a success response and leave the stale vector index entry for cleanup during the next reindex

### Requirement 6: Fetch Concepts Tool (Semantic Search)

**User Story:** As an MCP client, I want to search the knowledge bundle using natural language queries, so that agents can retrieve relevant context before acting.

#### Acceptance Criteria

1. THE MCP_Server SHALL expose a `fetch_concepts` tool that accepts `query` (string, required, minimum 1 non-whitespace character), `top_n` (integer, optional, range 1 to 100, defaults to 5), `threshold` (float, optional, range 0.0 to 1.0, defaults to 0.0), `type` (string, optional), `tags` (array of strings, optional), and `mode` (string, optional, one of "hybrid", "keyword", "semantic", defaults to "hybrid") parameters
2. WHEN the `fetch_concepts` tool is invoked with a query, THE MCP_Server SHALL perform search using the specified `mode` and return a list of at most `top_n` results, each containing concept_id, title, score (float between 0.0 and 1.0), and snippet (up to 200 characters of concept body)
3. WHEN no index database exists (bundle not yet indexed), THE MCP_Server SHALL return an empty result list without error
4. IF `type` or `tags` filters are provided, THEN THE MCP_Server SHALL return only results whose metadata matches the specified type exactly or shares at least one tag with the provided tags list
5. IF the `query` parameter is empty or contains only whitespace, THEN THE MCP_Server SHALL return a validation error indicating that a non-empty query is required

### Requirement 7: List Concepts Tool

**User Story:** As an MCP client, I want to browse all concepts in the bundle with optional filters, so that agents can discover available knowledge.

#### Acceptance Criteria

1. THE MCP_Server SHALL expose a `list_concepts` tool that accepts optional filter parameters: `type` (string), `tags` (array of strings), `since` (string, ISO 8601 date format YYYY-MM-DD), `limit` (integer, range 1 to 1000, defaults to 100), and `path` (string, subdirectory within the bundle)
2. WHEN the `list_concepts` tool is invoked, THE MCP_Server SHALL return a list of concepts sorted by concept_id alphabetically, each containing concept_id, title, type, and tags
3. WHEN filter parameters are provided, THE MCP_Server SHALL apply all filters (type matches exactly, tags matches any overlap, since filters by modification date, path filters by directory prefix) before returning results
4. WHEN the `tags` filter is provided, THE MCP_Server SHALL return concepts that have at least one tag in common with the provided tags list (OR semantics)

### Requirement 8: Show Concept Tool

**User Story:** As an MCP client, I want to retrieve the full content of a specific concept, so that agents can read detailed knowledge after a search result.

#### Acceptance Criteria

1. THE MCP_Server SHALL expose a `show_concept` tool that accepts `concept_id` (string, required)
2. WHEN the `show_concept` tool is invoked with a valid concept_id, THE MCP_Server SHALL return the full concept including concept_id, frontmatter fields (title, type, tags, description, timestamp, and any additional frontmatter keys), and the complete body content as markdown text
3. IF the specified concept_id does not exist, THEN THE MCP_Server SHALL return an error indicating the concept was not found

### Requirement 9: Reindex Tool

**User Story:** As an MCP client, I want to rebuild the search index, so that agents can ensure search results reflect the current state of the bundle.

#### Acceptance Criteria

1. THE MCP_Server SHALL expose a `reindex` tool that accepts `full` (boolean, optional, defaults to false)
2. WHEN the `reindex` tool is invoked with `full` set to false, THE MCP_Server SHALL perform incremental reindexing (processing only concepts added, modified, or deleted since the last reindex) and return a summary containing integer counts of added, updated, removed, skipped, and total indexed concepts
3. WHEN the `reindex` tool is invoked with `full` set to true, THE MCP_Server SHALL clear the existing index, re-embed all concepts in the bundle, and return a summary containing integer counts of added, updated, removed, skipped, and total indexed concepts
4. IF `full` is false and no previous reindex has been completed (no sync timestamp exists), THEN THE MCP_Server SHALL perform a full reindex automatically
5. IF one or more concept files fail to parse during reindexing, THEN THE MCP_Server SHALL skip the unparseable files, include them in the skipped count, and continue reindexing the remaining concepts

### Requirement 10: Get Stats Tool

**User Story:** As an MCP client, I want to check bundle health and statistics, so that agents can understand the state of the knowledge base.

#### Acceptance Criteria

1. THE MCP_Server SHALL expose a `get_stats` tool that accepts no parameters
2. WHEN the `get_stats` tool is invoked, THE MCP_Server SHALL return bundle statistics including concept_count (integer), type_distribution (object mapping type names to counts), tag_distribution (object mapping tag names to counts), last_reindex_timestamp (string or null), and pending_reembedding_count (integer >= 0)
3. IF no bundle is configured, THEN THE MCP_Server SHALL return an error indicating that no bundle is available
4. IF the index has not been built yet, THEN THE MCP_Server SHALL return stats with last_reindex_timestamp as null and pending_reembedding_count equal to the total concept count

### Requirement 11: Error Handling

**User Story:** As an MCP client, I want clear, structured error responses when operations fail, so that agents can handle failures gracefully.

#### Acceptance Criteria

1. IF a tool invocation raises a ValidationError, THEN THE MCP_Server SHALL return a tool result with `isError` set to true and content containing each validation error message as text
2. IF a tool invocation raises a ConceptNotFoundError, THEN THE MCP_Server SHALL return a tool result with `isError` set to true and content stating the concept was not found, including the requested concept_id
3. IF a tool invocation raises a BundleAlreadyInitialisedError, THEN THE MCP_Server SHALL return a tool result with `isError` set to true and content indicating the bundle is already initialized at the target path
4. IF an unexpected error occurs during tool execution, THEN THE MCP_Server SHALL return a tool result with `isError` set to true and content containing a descriptive error message without exposing internal stack traces or file paths to the client

### Requirement 12: Bundle Path Configuration

**User Story:** As a developer, I want to configure which bundle the MCP server operates on, so that I can use it with different knowledge bases.

#### Acceptance Criteria

1. WHEN the MCP_Server starts without a `--bundle-path` command-line argument, THE MCP_Server SHALL resolve the bundle by calling find_bundle_root from the current working directory, which walks up the directory tree looking for a `.okf/config.json` file
2. WHEN the MCP_Server starts with a `--bundle-path` command-line argument, THE MCP_Server SHALL use the specified path as the bundle root, overriding any bundle that would be found via find_bundle_root
3. IF the `--bundle-path` argument specifies a path that does not exist or is not a directory, THEN THE MCP_Server SHALL fail to start and report an error indicating the path is invalid
4. IF no bundle is found at startup (neither via `--bundle-path` nor find_bundle_root), THEN THE MCP_Server SHALL start successfully and allow `init_bundle` to be called
5. IF no bundle is configured and a tool other than `init_bundle` is invoked, THEN THE MCP_Server SHALL return an error response indicating that no bundle is configured
