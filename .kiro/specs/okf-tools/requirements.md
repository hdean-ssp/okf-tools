# Requirements Document

## Introduction

okf-tools is a companion CLI and Python library for working with Google's Open Knowledge Format (OKF v0.1) bundles. It fills the gaps the OKF spec intentionally leaves open — semantic search, graph traversal, concept authoring, and agent-friendly progressive disclosure — while keeping markdown files as the sole source of truth. The tool targets both human developers and AI agents as first-class consumers.

## Glossary

- **Bundle**: A directory tree of `.md` files conforming to the OKF v0.1 specification, representing a collection of linked knowledge concepts
- **Concept**: A single `.md` file within a Bundle containing YAML frontmatter (with at least a `type` field) and a markdown body
- **Concept_ID**: The relative file path of a Concept within the Bundle, minus the `.md` extension
- **Frontmatter**: The YAML metadata block delimited by `---` at the top of a Concept file
- **Vector_Index**: A sqlite-vec sidecar database storing embeddings of Concept bodies for semantic search, gitignored and rebuildable from source files
- **Link_Graph**: An adjacency structure representing markdown links between Concepts within a Bundle
- **Skill_Pack**: A drop-in directory containing steering files (`.md`) and optional hook files that extend okf-tools behaviour for a specific domain
- **CLI**: The `okf` command-line interface, the single entry point for all okf-tools operations
- **Embedding**: A dense vector representation of text content, generated locally via fastembed using the BAAI/bge-small-en-v1.5 model (384 dimensions)
- **Sidecar**: A derived data store (the `.okf/` directory) that lives alongside the Bundle but is not part of it and can be regenerated
- **Index_File**: An `index.md` file within a Bundle directory that provides a listing of Concepts in that directory
- **Slug**: A URL-safe filename derived from a Concept title (lowercase, hyphens, max 60 characters)
- **Lint_Diagnostic**: A structured finding from bundle validation, containing file path, rule identifier, severity (error or warning), and a human-readable message
- **Validation_Level**: A configurable strictness setting (`strict`, `standard`, or `relaxed`) that controls which OKF compliance checks are enforced

## Requirements

### Requirement 1: Bundle Initialisation

**User Story:** As a developer, I want to initialise a new OKF bundle in any directory, so that I can start authoring and querying concepts immediately.

#### Acceptance Criteria

1. WHEN the user runs `okf init` in a directory, THE CLI SHALL create the `.okf/` directory and an `.okf/config.json` file containing these fields with default values: `bundle_path` (default: `"."`), `index_path` (default: `".okf/index"`), `embedding_model` (default: `"BAAI/bge-small-en-v1.5"`), `default_top_n` (default: `5`), `similarity_threshold` (default: `0.85`), `auto_git_add` (default: `true`), and `skills_paths` (default: `[".kiro/steering/", "~/.config/okf/skills/"]`), and exit with status code 0
2. WHEN the user runs `okf init` in a directory that does not contain a root `index.md` file, THE CLI SHALL create a root `index.md` file with a top-level heading matching the directory name and an empty Concept listing
3. IF the user runs `okf init` in a directory that already contains an `.okf/config.json`, THEN THE CLI SHALL report an error message indicating the bundle is already initialised and exit with a non-zero status code without modifying existing files
4. IF a `.git` directory exists in the target directory and a `.gitignore` file does not exist, THEN THE CLI SHALL create a `.gitignore` file containing the `.okf/index/` entry
5. IF a `.git` directory exists in the target directory and a `.gitignore` file exists but does not contain the `.okf/index/` entry, THEN THE CLI SHALL append the `.okf/index/` entry to the existing `.gitignore` file
6. IF no `.git` directory exists in the target directory, THEN THE CLI SHALL skip `.gitignore` modification

### Requirement 2: Concept Authoring (Commit)

**User Story:** As a developer or AI agent, I want to create new OKF-compliant concept files from structured input, so that knowledge is persisted in the bundle with correct formatting and metadata.

#### Acceptance Criteria

1. WHEN the user provides a title, content, and type via `okf commit`, THE CLI SHALL create a new `.md` file with valid YAML frontmatter and markdown body
2. WHEN the user provides a title, THE CLI SHALL generate a Slug filename (lowercase, hyphens replacing spaces, non-alphanumeric characters removed, maximum 60 characters, truncated at the last complete word within the limit)
3. IF a file already exists at the generated Slug path, THEN THE CLI SHALL append a numeric suffix (e.g., `-2`, `-3`) to produce a unique filename
4. WHEN a target directory is specified via `--path`, THE CLI SHALL place the Concept file in that subdirectory, creating it if it does not exist
5. WHEN no target directory is specified and a type-to-directory mapping exists in configuration, THE CLI SHALL place the Concept file in the mapped directory
6. WHEN no target directory is specified and no type-to-directory mapping exists for the given type, THE CLI SHALL place the Concept file in the Bundle root directory
7. WHEN a new Concept is created, THE CLI SHALL update the parent directory's Index_File to include the new Concept entry
8. WHEN `auto_git_add` is true in configuration, THE CLI SHALL run `git add` on the newly created Concept file
9. WHEN `--check-duplicates` is specified, THE CLI SHALL embed the proposed content, search the Vector_Index for similar concepts above the configured similarity_threshold, and warn the user before proceeding
10. WHEN `--check-duplicates` detects similar concepts and `--force` is not specified, THE CLI SHALL display the similar concepts with their Concept_IDs and similarity scores, and abort the commit
11. WHEN input is provided via `--json` or `--file`, THE CLI SHALL parse the structured input and extract title, content, type, and tags fields
12. IF required fields (title, content, type) are missing from input, THEN THE CLI SHALL report a validation error listing the missing fields and abort with a non-zero exit code
13. WHEN the commit completes successfully, THE CLI SHALL embed the new Concept body and add the Embedding to the Vector_Index
14. WHEN the commit completes successfully, THE CLI SHALL output the new Concept_ID

### Requirement 3: Concept Update

**User Story:** As a developer or AI agent, I want to update existing concepts, so that knowledge stays current as understanding evolves.

#### Acceptance Criteria

1. WHEN the user runs `okf update <concept-id>` with new field values provided via `--json`, `--file`, or individual flags (`--title`, `--content`, `--type`, `--tags`), THE CLI SHALL overwrite only the specified fields in the Concept file while preserving all unmodified frontmatter fields and body content
2. WHEN a Concept is updated, THE CLI SHALL re-embed the Concept body and update the Vector_Index entry
3. IF the specified Concept_ID does not correspond to an existing file, THEN THE CLI SHALL report an error with the invalid Concept_ID and exit with a non-zero status code
4. WHEN `auto_git_add` is true in configuration, THE CLI SHALL run `git add` on the updated Concept file
5. WHEN the update completes successfully, THE CLI SHALL output the Concept_ID of the updated Concept
6. WHEN a Concept's title is modified by an update, THE CLI SHALL update the corresponding entry in the parent directory's Index_File to reflect the new title

### Requirement 4: Concept Deletion

**User Story:** As a developer, I want to delete concepts that are no longer relevant, so that the bundle stays clean and search results remain accurate.

#### Acceptance Criteria

1. WHEN the user runs `okf delete <concept-id>`, THE CLI SHALL remove the Concept `.md` file from the filesystem
2. WHEN a Concept is deleted, THE CLI SHALL remove the Concept entry from the parent directory's Index_File
3. WHEN a Concept is deleted, THE CLI SHALL remove the Concept's Embedding from the Vector_Index
4. WHEN a Concept is deleted, THE CLI SHALL remove the Concept from the Link_Graph (both inbound and outbound edges)
5. IF the specified Concept_ID does not correspond to an existing file, THEN THE CLI SHALL report an error with the invalid Concept_ID and exit with a non-zero status code
6. WHEN `auto_git_add` is true in configuration, THE CLI SHALL run `git add` on the deletion (stage the file removal)

### Requirement 5: Concept Listing

**User Story:** As a developer or AI agent, I want to list concepts with filtering, so that I can browse the bundle contents without loading everything into context.

#### Acceptance Criteria

1. WHEN the user runs `okf list`, THE CLI SHALL enumerate all Concepts in the Bundle with their Concept_ID, title, and type, sorted alphabetically by Concept_ID
2. WHEN `--type` is specified, THE CLI SHALL include only Concepts whose frontmatter type matches the specified value (case-sensitive)
3. WHEN `--tags` is specified, THE CLI SHALL include only Concepts whose frontmatter tags contain at least one of the specified tags
4. WHEN `--since` is specified with an ISO 8601 date, THE CLI SHALL include only Concepts whose frontmatter timestamp is on or after the specified date; Concepts without a timestamp field SHALL be excluded from results when this filter is active
5. WHEN `--limit` is specified, THE CLI SHALL return at most the specified number of Concepts
6. WHEN `--path` is specified, THE CLI SHALL include only Concepts within the specified subdirectory (recursive)
7. WHEN multiple filter flags are provided together, THE CLI SHALL apply all filters using AND logic

### Requirement 6: Concept Display

**User Story:** As a developer or AI agent, I want to view the full content of a specific concept, so that I can read its complete knowledge entry.

#### Acceptance Criteria

1. WHEN the user runs `okf show <concept-id>`, THE CLI SHALL display the full frontmatter and markdown body of the specified Concept
2. WHEN output format is JSON, THE CLI SHALL output a JSON object with `concept_id`, `frontmatter` (as a nested object), and `body` (as a string) fields
3. IF the specified Concept_ID does not correspond to an existing file, THEN THE CLI SHALL report an error with the invalid Concept_ID and exit with a non-zero status code

### Requirement 7: Semantic Search

**User Story:** As a developer or AI agent, I want to search the bundle using natural language queries, so that I can find relevant concepts without knowing exact titles or paths.

#### Acceptance Criteria

1. WHEN the user runs `okf fetch <query>` with a non-empty query string, THE CLI SHALL embed the query text using the configured Embedding model
2. WHEN the query is embedded, THE CLI SHALL search the Vector_Index using cosine similarity and return results ordered by descending similarity score, limited to the top-N count
3. THE CLI SHALL include in each search result: the Concept_ID, title, similarity score (as a decimal between 0.0 and 1.0), and a snippet of the first 200 characters of the body
4. WHEN `--top-n` is specified with a value between 1 and 100, THE CLI SHALL return at most the specified number of results (default: 5)
5. WHEN `--threshold` is specified with a value between 0.0 and 1.0, THE CLI SHALL exclude results with a similarity score below the specified value
6. WHEN `--type` is specified, THE CLI SHALL filter results to only Concepts matching the specified type; WHEN multiple filter flags are provided together, THE CLI SHALL apply all filters using AND logic
7. WHEN `--tags` is specified, THE CLI SHALL filter results to only Concepts containing at least one of the specified tags
8. IF the Vector_Index does not exist or is empty, THEN THE CLI SHALL report that no index exists and suggest running `okf reindex`
9. IF the query string is empty or contains only whitespace, THEN THE CLI SHALL report a validation error indicating that a non-empty query is required and exit with a non-zero status code
10. IF the search returns zero matching results after applying all filters and threshold, THEN THE CLI SHALL output an empty result set with no error

### Requirement 8: Link Graph Traversal

**User Story:** As a developer or AI agent, I want to query the link relationships between concepts, so that I can navigate the knowledge graph and discover related information without loading the entire bundle.

#### Acceptance Criteria

1. WHEN the user runs `okf links <concept-id>`, THE CLI SHALL display both inbound links (Concepts that link to the target) and outbound links (Concepts that the target links to), showing the Concept_ID, title, and link direction for each entry
2. WHEN `--direction in` is specified, THE CLI SHALL display only inbound links
3. WHEN `--direction out` is specified, THE CLI SHALL display only outbound links
4. WHEN `--depth N` is specified with N between 2 and 10 inclusive, THE CLI SHALL perform breadth-first traversal and display all Concepts within N hops of the target
5. WHEN `--depth` is not specified, THE CLI SHALL default to depth 1 (direct links only)
6. IF the specified Concept_ID does not correspond to an existing file, THEN THE CLI SHALL report an error and exit with a non-zero status code
7. THE CLI SHALL parse standard markdown links (both absolute from bundle root with `/` and relative with `./`) to build the Link_Graph, excluding external URLs and fragment-only anchors
8. IF a markdown link references a path that does not correspond to an existing Concept file in the Bundle, THEN THE CLI SHALL exclude that link from the displayed results

### Requirement 9: Index Synchronisation

**User Story:** As a developer, I want the vector index to stay current with the bundle contents efficiently, so that search results are accurate without expensive full rebuilds.

#### Acceptance Criteria

1. WHEN the user runs `okf reindex` and a synchronisation timestamp from a prior index build exists, THE CLI SHALL perform an incremental re-embedding of only new and modified Concept files since that timestamp and add or update their Embeddings in the Vector_Index
2. WHEN `--full` is specified, THE CLI SHALL discard the existing Vector_Index and rebuild it from all Concept files in the Bundle
3. WHEN the user runs `okf reindex` and no prior synchronisation timestamp exists, THE CLI SHALL perform a full rebuild equivalent to `--full`
4. WHEN performing incremental reindex, THE CLI SHALL detect new files, modified files (by comparing file modification times), and deleted files
5. WHEN deleted files are detected during reindex, THE CLI SHALL remove their Embeddings from the Vector_Index
6. WHEN reindex completes, THE CLI SHALL persist the synchronisation timestamp for use in subsequent incremental operations
7. THE CLI SHALL exclude `index.md` and `log.md` files from embedding during reindex
8. WHEN reindex completes successfully, THE CLI SHALL output a summary indicating the number of files added, updated, removed, and the total number of indexed Concepts
9. IF embedding fails for one or more Concept files during reindex, THEN THE CLI SHALL skip the failing files, continue processing remaining files, report the skipped file paths, and exit with a non-zero status code
10. WHEN the reindex of a Bundle with fewer than 1000 Concepts completes incrementally, THE CLI SHALL finish within 1 second for up to 50 changed files (excluding embedding computation time)

### Requirement 10: Bundle Statistics

**User Story:** As a developer or AI agent, I want to view bundle health metrics, so that I can understand the structure and freshness of the knowledge base.

#### Acceptance Criteria

1. WHEN the user runs `okf stats`, THE CLI SHALL display: total Concept count, type distribution (count per distinct type value), tag distribution (count per distinct tag value), average links per Concept rounded to one decimal place, orphan Concept count (Concepts with no inbound and no outbound links), last reindex timestamp in ISO 8601 format, and count of Concepts pending re-embedding
2. IF output format is JSON, THEN THE CLI SHALL structure all statistics as a single JSON object with fields: `concept_count`, `type_distribution`, `tag_distribution`, `average_links_per_concept`, `orphan_count`, `last_reindex_timestamp`, and `pending_reembedding_count`
3. IF the Vector_Index does not exist when `okf stats` is run, THEN THE CLI SHALL report the last reindex timestamp as null and pending re-embedding count as equal to the total Concept count
4. IF the Bundle contains no Concepts, THEN THE CLI SHALL display all counts as zero, distributions as empty, average links as 0.0, and last reindex timestamp as null

### Requirement 11: Output Format Control

**User Story:** As a developer or AI agent, I want consistent output formatting, so that humans get readable text and agents get parseable JSON without extra configuration.

#### Acceptance Criteria

1. THE CLI SHALL support `--format json|text|brief` on all commands that produce output
2. WHEN stdout is connected to a TTY and no `--format` is specified, THE CLI SHALL default to `text` format
3. WHEN stdout is not connected to a TTY and no `--format` is specified, THE CLI SHALL default to `json` format
4. WHEN `json` format is active, THE CLI SHALL output valid JSON to stdout with no extra decorative text, and SHALL direct any warnings or progress messages to stderr only
5. WHEN `brief` format is active, THE CLI SHALL output only Concept_IDs and titles separated by a tab character, one entry per line
6. IF an invalid value is provided to `--format`, THEN THE CLI SHALL report an error listing the valid options (json, text, brief) and exit with a non-zero status code

### Requirement 12: Configuration Management

**User Story:** As a developer, I want flexible configuration with sensible defaults, so that the tool works out of the box but can be customised per-bundle or per-user.

#### Acceptance Criteria

1. THE CLI SHALL load configuration from `.okf/config.json` in the Bundle root when present, and Bundle-level settings SHALL take precedence over user-level settings on a per-field basis
2. IF no Bundle-level configuration file exists, THEN THE CLI SHALL load configuration from `~/.config/okf/config.json`
3. IF no configuration file exists at either location, THEN THE CLI SHALL use the following built-in default values: `bundle_path` = `.`, `index_path` = `.okf/index`, `embedding_model` = `BAAI/bge-small-en-v1.5`, `default_top_n` = `5`, `similarity_threshold` = `0.85`, `auto_git_add` = `true`, `skills_paths` = `[".kiro/steering/", "~/.config/okf/skills/"]`, `validation_level` = `standard`
4. THE CLI SHALL support these configuration fields: `bundle_path` (string, directory path), `index_path` (string, directory path), `embedding_model` (string, model identifier), `default_top_n` (integer, 1 to 100), `similarity_threshold` (float, 0.0 to 1.0), `auto_git_add` (boolean), `skills_paths` (list of strings, each a directory path), and `validation_level` (string, one of `strict`, `standard`, or `relaxed`, default `standard`)
5. IF a configuration file contains invalid JSON, THEN THE CLI SHALL report an error indicating the file path and the nature of the parse failure, and exit with a non-zero status code
6. IF both Bundle-level and user-level configuration files exist, THEN THE CLI SHALL merge them by applying Bundle-level field values over user-level field values, with unset Bundle-level fields falling back to user-level values

### Requirement 13: Skills System

**User Story:** As a developer, I want to extend okf-tools with domain-specific skill packs, so that agents can receive specialised guidance without modifying the core tool.

#### Acceptance Criteria

1. WHEN the user runs `okf skills`, THE CLI SHALL list all discovered Skill_Packs from the configured skills_paths directories
2. THE CLI SHALL discover Skill_Packs by scanning each directory in skills_paths for `.md` files that contain valid YAML frontmatter, silently skipping any `.md` files that lack a `---` delimited frontmatter block
3. THE CLI SHALL display for each discovered Skill_Pack: its filename, title (resolved from the frontmatter `title` field first, then the first markdown heading if no frontmatter title exists, then the filename without extension as a final fallback), and description (from the frontmatter `description` field if present, or empty if absent)
4. THE CLI SHALL ship with a default `core-knowledge.md` skill that provides general OKF usage rules for agents and SHALL include this skill in discovery results regardless of user-configured skills_paths
5. WHEN a new Skill_Pack is added to a configured skills_path directory, THE CLI SHALL discover it on the next invocation of `okf skills` without requiring any registration step
6. IF a configured skills_path directory does not exist on the filesystem, THEN THE CLI SHALL skip that path without reporting an error and continue scanning remaining paths

### Requirement 14: Progressive Disclosure for Agents

**User Story:** As an AI agent, I want to scan concept summaries before reading full content, so that I can make informed decisions about which concepts to load into context.

#### Acceptance Criteria

1. WHEN the user runs `okf list` with `--format brief`, THE CLI SHALL output only Concept_ID and title for each Concept
2. WHEN the user runs `okf show <concept-id>` with `--format brief`, THE CLI SHALL output only the frontmatter fields (title, description, type, tags) without the markdown body; missing frontmatter fields SHALL be omitted from the output rather than displayed as null
3. WHEN an Index_File exists in a directory and is used by `okf list`, THE CLI SHALL use the Index_File contents for listing rather than scanning individual files in that directory; however if the Index_File is stale (newer .md files exist in the directory), THE CLI SHALL fall back to scanning individual files

### Requirement 15: Error Handling

**User Story:** As a developer or AI agent, I want clear and consistent error reporting, so that I can diagnose and resolve issues without ambiguity.

#### Acceptance Criteria

1. IF a required subcommand argument is missing, THEN THE CLI SHALL print a usage hint showing the expected command syntax to stderr and exit with status code 2
2. IF a file system operation fails (read, write, delete), THEN THE CLI SHALL print to stderr the specific file path and the OS-reported error reason (e.g., permission denied, file not found), and exit with status code 1
3. IF the Vector_Index cannot be opened as a valid SQLite database or fails an integrity check query, THEN THE CLI SHALL print an error message to stderr indicating index corruption, suggest running `okf reindex --full` to rebuild, and exit with status code 1
4. WHEN output format is JSON, THE CLI SHALL write errors to stderr as a JSON object containing an `error` field with the error message string and an `exit_code` field with the numeric exit code
5. WHILE output format is text or brief, THE CLI SHALL write all error messages to stderr prefixed with the string "error:" followed by the descriptive message

### Requirement 16: Concept Frontmatter Validation

**User Story:** As a developer, I want the tool to enforce OKF compliance on authored concepts, so that all concepts in the bundle conform to the specification.

#### Acceptance Criteria

1. WHEN creating or updating a Concept, THE CLI SHALL validate that the frontmatter contains a `type` field with a non-empty string value
2. IF the `type` field is missing or empty in provided input, THEN THE CLI SHALL report a validation error indicating the `type` field is required and abort the operation with a non-zero exit code
3. WHEN a `timestamp` field is present in frontmatter, THE CLI SHALL validate that it conforms to ISO 8601 format (date, datetime, or datetime with timezone offset)
4. IF the `timestamp` field is present but does not conform to ISO 8601 format, THEN THE CLI SHALL report a validation error identifying the invalid timestamp value and abort the operation with a non-zero exit code
5. WHEN a `tags` field is present in frontmatter, THE CLI SHALL validate that it is a YAML list of strings
6. IF the `tags` field is present but is not a YAML list of strings, THEN THE CLI SHALL report a validation error identifying the invalid tags value and abort the operation with a non-zero exit code

### Requirement 17: Parse and Print Concepts

**User Story:** As a developer, I want reliable parsing and serialisation of concept files, so that programmatic operations preserve file integrity.

#### Acceptance Criteria

1. THE Bundle_Parser SHALL parse any valid Concept file into a structured representation containing separate frontmatter (as a dictionary) and body (as a string) components
2. THE Bundle_Parser SHALL format a structured Concept representation back into a valid `.md` file with `---` delimited YAML frontmatter followed by a single blank line followed by the markdown body, ending with a trailing newline
3. THE Bundle_Parser SHALL ensure that parsing a valid Concept file, formatting the result, then parsing again produces a structured representation with identical frontmatter key-value pairs and identical body string (round-trip property)
4. WHEN a Concept file contains extra YAML keys beyond the OKF standard fields (type, title, description, resource, tags, timestamp), THE Bundle_Parser SHALL preserve those keys and their values through parse and format operations
5. IF a file does not contain valid `---` delimited YAML frontmatter or contains unparseable YAML, THEN THE Bundle_Parser SHALL raise a parse error indicating the file path and the nature of the malformation

### Requirement 18: Bundle Validation & Linting

**User Story:** As a developer or AI agent, I want to validate an entire OKF bundle for compliance, structural integrity, and consistency, so that I can catch and fix issues that per-file validation during commit/update cannot detect.

#### Acceptance Criteria

1. WHEN the user runs `okf lint`, THE CLI SHALL validate all Concept files in the Bundle against OKF compliance rules and output a list of Lint_Diagnostics
2. WHEN validation finds zero issues, THE CLI SHALL exit with status code 0 and output a success message confirming the bundle is clean
3. WHEN validation finds one or more errors, THE CLI SHALL exit with status code 1 and output all Lint_Diagnostics sorted by file path
4. WHEN `--warn-only` is specified, THE CLI SHALL output all Lint_Diagnostics but always exit with status code 0 regardless of findings
5. WHEN output format is JSON, THE CLI SHALL structure each Lint_Diagnostic as a JSON object with fields: `file` (relative path), `rule` (string identifier, e.g., `frontmatter/type-required`), `severity` (`error` or `warning`), and `message` (human-readable description)
6. THE CLI SHALL perform structural validation: every directory containing one or more Concept files SHALL have an `index.md` file; every entry in an `index.md` SHALL correspond to an existing `.md` file in that directory; no orphaned entries in `index.md` that point to non-existent files
7. THE CLI SHALL perform link integrity validation: every internal markdown link in a Concept body SHALL resolve to an existing Concept file in the Bundle; broken links SHALL be reported as Lint_Diagnostics with severity `error`
8. THE CLI SHALL perform type consistency validation: WHEN two or more distinct type values in the Bundle differ only by case, hyphenation, or whitespace (e.g., "Bug Fix", "bug-fix", "bugfix"), THE CLI SHALL report a Lint_Diagnostic with severity `warning` identifying the near-duplicate type values and the Concept files using each variant
9. THE CLI SHALL perform frontmatter validation on every Concept file: validate `type` is present and non-empty, `timestamp` conforms to ISO 8601 if present, `tags` is a list of strings if present — applying the same rules as Requirement 16 but retroactively across the entire Bundle
10. WHEN `validation_level` is set to `strict` in configuration, THE CLI SHALL additionally require that every Concept has non-empty `title` and `description` fields, reporting missing fields as errors
11. WHEN `validation_level` is set to `relaxed` in configuration, THE CLI SHALL downgrade all frontmatter field violations (except missing `type`) from errors to warnings
12. WHEN `validation_level` is set to `standard` (the default) or is absent from configuration, THE CLI SHALL enforce the OKF v0.1 minimum: `type` required, other standard fields validated if present
13. WHEN `okf reindex --lint` is specified, THE CLI SHALL perform full bundle validation as part of the reindex operation and include Lint_Diagnostics in the reindex output; validation failures SHALL NOT prevent reindexing from completing but SHALL cause a non-zero exit code
14. WHEN `--path` is specified with `okf lint`, THE CLI SHALL validate only Concept files within the specified subdirectory (recursive)
15. WHEN `--rule` is specified with `okf lint`, THE CLI SHALL run only the specified validation rule category (one of: `frontmatter`, `structure`, `links`, `types`)
