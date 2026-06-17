"""Tests for okf_tools.server module — startup, helpers, and configuration."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from okf_tools.errors import (
    BundleAlreadyInitialisedError,
    ConceptNotFoundError,
    ConfigError,
    IndexCorruptionError,
    OkfError,
    ParseError,
    ValidationError,
)
from okf_tools.server import (
    _handle_error,
    _require_bundle,
    init_bundle,
    commit_concept,
    update_concept,
    delete_concept,
    fetch_concepts,
    list_concepts,
    show_concept,
    reindex,
    get_stats,
)


# ---------------------------------------------------------------------------
# Fixtures for tool handler tests (tasks 4.2–4.7)
# ---------------------------------------------------------------------------


@pytest.fixture
def configured_server(sample_config):
    """Patch server._config so tool handlers have a configured bundle."""
    with patch("okf_tools.server._config", sample_config):
        yield sample_config


@pytest.fixture(autouse=True)
def mock_embeddings():
    """Mock embed_text and VectorIndex to avoid real embedding calls."""
    with patch("okf_tools.service.embed_text") as mock_embed, \
         patch("okf_tools.service.VectorIndex") as mock_index_cls:
        # embed_text returns a fake embedding vector
        mock_embed.return_value = [0.1] * 384
        # VectorIndex mock with basic methods
        mock_index = mock_index_cls.return_value
        mock_index.search.return_value = []
        mock_index.get_sync_timestamp.return_value = None
        mock_index.concept_count.return_value = 0
        mock_index.close.return_value = None
        mock_index.upsert.return_value = None
        mock_index.delete.return_value = None
        yield {"embed_text": mock_embed, "VectorIndex": mock_index_cls, "index": mock_index}


class TestRequireBundle:
    """Tests for _require_bundle helper."""

    def test_raises_tool_error_when_config_is_none(self):
        """_require_bundle raises ToolError when no bundle is configured."""
        with patch("okf_tools.server._config", None):
            with pytest.raises(ToolError) as exc_info:
                _require_bundle()
            assert "No bundle configured" in str(exc_info.value)

    def test_returns_config_when_set(self, tmp_path):
        """_require_bundle returns the config when one is set."""
        from okf_tools.config import OkfConfig

        config = OkfConfig(
            bundle_path=tmp_path,
            index_path=Path(".okf/index"),
            embedding_model="test",
            default_top_n=5,
            similarity_threshold=0.85,
            auto_git_add=True,
        )
        with patch("okf_tools.server._config", config):
            result = _require_bundle()
            assert result is config


class TestHandleError:
    """Tests for _handle_error helper."""

    def test_validation_error_joins_messages(self):
        """ValidationError messages are joined with newlines."""
        err = ValidationError(["missing title", "missing type", "invalid tags"])
        result = _handle_error(err)
        assert result == "missing title\nmissing type\ninvalid tags"

    def test_validation_error_single_message(self):
        """Single validation error message is returned as-is."""
        err = ValidationError(["missing title"])
        result = _handle_error(err)
        assert result == "missing title"

    def test_concept_not_found_includes_id(self):
        """ConceptNotFoundError includes the concept_id."""
        err = ConceptNotFoundError("patterns/my-pattern")
        result = _handle_error(err)
        assert result == "Concept not found: patterns/my-pattern"

    def test_bundle_already_initialised(self):
        """BundleAlreadyInitialisedError returns its string representation."""
        err = BundleAlreadyInitialisedError()
        result = _handle_error(err)
        assert "already initialised" in result.lower() or "already initialized" in result.lower()

    def test_generic_okf_error_hides_details(self):
        """Unrecognized OkfError subclasses return a generic message."""
        err = OkfError("secret internal detail")
        result = _handle_error(err)
        assert result == "An internal error occurred"
        assert "secret" not in result

    def test_config_error_hides_path(self):
        """ConfigError does not expose internal paths."""
        err = ConfigError("/home/user/.okf/config.json", "bad json")
        result = _handle_error(err)
        assert result == "An internal error occurred"
        assert "/home" not in result

    def test_parse_error_hides_path(self):
        """ParseError does not expose internal paths."""
        err = ParseError("/home/user/bundle/concepts/test.md", "invalid yaml")
        result = _handle_error(err)
        assert result == "An internal error occurred"
        assert "/home" not in result

    def test_index_corruption_error_hides_path(self):
        """IndexCorruptionError does not expose internal paths."""
        err = IndexCorruptionError("/home/user/.okf/index/okf.db")
        result = _handle_error(err)
        assert result == "An internal error occurred"
        assert "/home" not in result


class TestMain:
    """Tests for main() entry point — argument parsing and config resolution."""

    def test_invalid_bundle_path_exits(self, capsys):
        """main() exits with error when --bundle-path doesn't exist."""
        with patch.object(sys, "argv", ["okf-mcp", "--bundle-path", "/nonexistent"]):
            with pytest.raises(SystemExit) as exc_info:
                from okf_tools import server
                server.main()
            assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "does not exist" in captured.err

    def test_invalid_bundle_path_file_not_dir(self, tmp_path, capsys):
        """main() exits with error when --bundle-path is a file, not a directory."""
        file_path = tmp_path / "not_a_dir.txt"
        file_path.write_text("hello")
        with patch.object(sys, "argv", ["okf-mcp", "--bundle-path", str(file_path)]):
            with pytest.raises(SystemExit) as exc_info:
                from okf_tools import server
                server.main()
            assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "not a directory" in captured.err

    def test_no_bundle_path_no_bundle_found_starts_with_none(self):
        """When no bundle found and no --bundle-path, _config is None."""
        import okf_tools.server as server_module

        with patch.object(sys, "argv", ["okf-mcp"]):
            with patch("okf_tools.server.find_bundle_root", return_value=None):
                with patch.object(server_module.mcp, "run"):
                    server_module.main()
                    assert server_module._config is None

    def test_bundle_path_arg_loads_config(self, tmp_path):
        """When --bundle-path is valid, config is loaded from that path."""
        import okf_tools.server as server_module

        # Create a minimal .okf/config.json
        okf_dir = tmp_path / ".okf"
        okf_dir.mkdir()
        (okf_dir / "config.json").write_text("{}")

        with patch.object(sys, "argv", ["okf-mcp", "--bundle-path", str(tmp_path)]):
            with patch.object(server_module.mcp, "run"):
                server_module.main()
                assert server_module._config is not None
                assert server_module._config.bundle_path == tmp_path.resolve()

    def test_auto_discover_bundle(self, tmp_path):
        """When no --bundle-path is given but a bundle exists, config is loaded."""
        import okf_tools.server as server_module

        with patch.object(sys, "argv", ["okf-mcp"]):
            with patch("okf_tools.server.find_bundle_root", return_value=tmp_path):
                with patch("okf_tools.server.load_config") as mock_load:
                    from okf_tools.config import OkfConfig

                    mock_load.return_value = OkfConfig(
                        bundle_path=tmp_path,
                        index_path=Path(".okf/index"),
                        embedding_model="test",
                        default_top_n=5,
                        similarity_threshold=0.85,
                        auto_git_add=True,
                    )
                    with patch.object(server_module.mcp, "run"):
                        server_module.main()
                        mock_load.assert_called_once_with(tmp_path)
                        assert server_module._config is not None


class TestInitBundle:
    """Tests for init_bundle tool handler."""

    def test_successful_init_creates_bundle(self, tmp_path):
        """init_bundle creates .okf/config.json and returns the path."""
        result = init_bundle(path=str(tmp_path))
        data = json.loads(result)
        assert data["path"] == str(tmp_path.resolve())
        assert (tmp_path / ".okf" / "config.json").exists()

    def test_init_existing_bundle_returns_error(self, tmp_bundle):
        """init_bundle on already-initialized bundle raises ToolError."""
        with pytest.raises(ToolError) as exc_info:
            init_bundle(path=str(tmp_bundle))
        assert "already initialised" in str(exc_info.value).lower() or "already initialized" in str(exc_info.value).lower()

    def test_init_invalid_path_returns_error(self):
        """init_bundle with nonexistent path raises ToolError."""
        with pytest.raises(ToolError) as exc_info:
            init_bundle(path="/nonexistent/path")
        assert "does not exist" in str(exc_info.value)


class TestUpdateConcept:
    """Tests for update_concept tool handler."""

    def test_update_applies_specified_fields(self, configured_server):
        """update_concept changes only the specified field."""
        # Create a concept first
        result = commit_concept(title="Original Title", type="pattern", content="Original body")
        data = json.loads(result)
        concept_id = data["concept_id"]

        # Update just the title
        update_result = update_concept(concept_id=concept_id, title="New Title")
        update_data = json.loads(update_result)
        assert update_data["concept_id"] == concept_id

        # Verify via show
        show_data = json.loads(show_concept(concept_id=concept_id))
        assert show_data["title"] == "New Title"
        assert show_data["type"] == "pattern"  # unchanged

    def test_update_no_fields_returns_error(self, configured_server):
        """update_concept with no update fields raises ToolError."""
        with pytest.raises(ToolError) as exc_info:
            update_concept(concept_id="some-concept")
        assert "at least one" in str(exc_info.value).lower()

    def test_update_nonexistent_concept_returns_error(self, configured_server):
        """update_concept on missing concept raises ToolError."""
        with pytest.raises(ToolError) as exc_info:
            update_concept(concept_id="nonexistent/concept", title="New")
        assert "not found" in str(exc_info.value).lower()


class TestDeleteConcept:
    """Tests for delete_concept tool handler."""

    def test_delete_removes_concept(self, configured_server):
        """delete_concept removes the file and returns concept_id."""
        # Create a concept
        result = commit_concept(title="To Delete", type="pattern", content="Delete me")
        data = json.loads(result)
        concept_id = data["concept_id"]

        # Delete it
        delete_result = delete_concept(concept_id=concept_id)
        delete_data = json.loads(delete_result)
        assert delete_data["concept_id"] == concept_id

        # Verify it's gone
        with pytest.raises(ToolError):
            show_concept(concept_id=concept_id)

    def test_delete_nonexistent_returns_error(self, configured_server):
        """delete_concept on missing concept raises ToolError."""
        with pytest.raises(ToolError) as exc_info:
            delete_concept(concept_id="nonexistent/concept")
        assert "not found" in str(exc_info.value).lower()


class TestCommitConcept:
    """Tests for commit_concept tool handler."""

    def test_successful_commit_returns_concept_id(self, configured_server):
        """commit_concept returns JSON with a concept_id."""
        result = commit_concept(title="Test Pattern", type="pattern", content="Some content")
        data = json.loads(result)
        assert "concept_id" in data
        assert data["concept_id"]  # non-empty

    def test_commit_missing_required_fields_returns_error(self, configured_server):
        """commit_concept with empty title/content raises ToolError listing missing fields."""
        with pytest.raises(ToolError) as exc_info:
            commit_concept(title="", type="pattern", content="")
        error_msg = str(exc_info.value)
        assert "title" in error_msg.lower() or "content" in error_msg.lower()

    def test_commit_no_bundle_returns_error(self):
        """commit_concept when no bundle configured raises ToolError."""
        with patch("okf_tools.server._config", None):
            with pytest.raises(ToolError) as exc_info:
                commit_concept(title="Test", type="pattern", content="content")
            assert "No bundle configured" in str(exc_info.value)


class TestShowConcept:
    """Tests for show_concept tool handler."""

    def test_show_returns_full_concept_data(self, configured_server):
        """show_concept returns concept_id, frontmatter, and body."""
        # First commit a concept
        result = commit_concept(title="Show Test", type="pattern", content="Body content")
        data = json.loads(result)
        concept_id = data["concept_id"]

        # Now show it
        show_result = show_concept(concept_id=concept_id)
        show_data = json.loads(show_result)
        assert show_data["concept_id"] == concept_id
        assert show_data["title"] == "Show Test"
        assert show_data["type"] == "pattern"
        assert "body" in show_data
        assert "Body content" in show_data["body"]

    def test_show_nonexistent_concept_returns_error(self, configured_server):
        """show_concept with bad concept_id raises ToolError."""
        with pytest.raises(ToolError) as exc_info:
            show_concept(concept_id="nonexistent/concept")
        assert "not found" in str(exc_info.value).lower()


class TestFetchConcepts:
    """Tests for fetch_concepts tool handler."""

    def test_search_returns_correct_structure(self, configured_server, mock_embeddings):
        """fetch_concepts returns results with correct fields."""
        from okf_tools.search import SearchResult

        mock_results = [
            SearchResult(concept_id="test/concept", title="Test", score=0.95, snippet="A snippet"),
        ]
        with patch("okf_tools.server.service.fetch_concepts", return_value=mock_results):
            result = fetch_concepts(query="test query")
            data = json.loads(result)
            assert "results" in data
            assert len(data["results"]) == 1
            r = data["results"][0]
            assert r["concept_id"] == "test/concept"
            assert r["title"] == "Test"
            assert r["score"] == 0.95
            assert r["snippet"] == "A snippet"

    def test_whitespace_only_query_returns_error(self, configured_server):
        """fetch_concepts with whitespace-only query raises ToolError."""
        with pytest.raises(ToolError) as exc_info:
            fetch_concepts(query="   \t\n  ")
        assert "non-empty query" in str(exc_info.value).lower()

    def test_empty_query_returns_error(self, configured_server):
        """fetch_concepts with empty string query raises ToolError."""
        with pytest.raises(ToolError) as exc_info:
            fetch_concepts(query="")
        assert "non-empty query" in str(exc_info.value).lower()

    def test_search_no_index_returns_empty(self, configured_server):
        """fetch_concepts returns empty results when no index exists."""
        with patch("okf_tools.server.service.fetch_concepts", return_value=[]):
            result = fetch_concepts(query="test")
            data = json.loads(result)
            assert data["results"] == []

    def test_snippet_truncated_to_200_chars(self, configured_server):
        """fetch_concepts truncates snippets to 200 chars."""
        from okf_tools.search import SearchResult

        long_snippet = "x" * 500
        mock_results = [
            SearchResult(concept_id="test/long", title="Long", score=0.8, snippet=long_snippet),
        ]
        with patch("okf_tools.server.service.fetch_concepts", return_value=mock_results):
            result = fetch_concepts(query="test")
            data = json.loads(result)
            assert len(data["results"][0]["snippet"]) <= 200


class TestListConcepts:
    """Tests for list_concepts tool handler."""

    def test_list_returns_correct_structure(self, configured_server):
        """list_concepts returns concepts with correct fields."""
        # Create a few concepts
        commit_concept(title="First", type="pattern", content="Content A")
        commit_concept(title="Second", type="decision", content="Content B")

        result = list_concepts()
        data = json.loads(result)
        assert "concepts" in data
        assert len(data["concepts"]) == 2
        for c in data["concepts"]:
            assert "concept_id" in c
            assert "title" in c
            assert "type" in c
            assert "tags" in c

    def test_list_sorted_by_concept_id(self, configured_server):
        """list_concepts returns results sorted alphabetically by concept_id."""
        commit_concept(title="Zebra", type="pattern", content="Z content")
        commit_concept(title="Alpha", type="pattern", content="A content")

        result = list_concepts()
        data = json.loads(result)
        ids = [c["concept_id"] for c in data["concepts"]]
        assert ids == sorted(ids)

    def test_list_with_type_filter(self, configured_server):
        """list_concepts with type filter returns only matching concepts."""
        commit_concept(title="Pattern One", type="pattern", content="P content")
        commit_concept(title="Decision One", type="decision", content="D content")

        result = list_concepts(type="pattern")
        data = json.loads(result)
        for c in data["concepts"]:
            assert c["type"] == "pattern"


class TestReindex:
    """Tests for reindex tool handler."""

    def test_reindex_returns_summary(self, configured_server, mock_embeddings):
        """reindex returns JSON with correct integer fields."""
        mock_summary = {"added": 3, "updated": 1, "removed": 0, "skipped": 0, "total_indexed": 4}
        with patch("okf_tools.server.service.reindex", return_value=mock_summary):
            result = reindex()
            data = json.loads(result)
            assert data["added"] == 3
            assert data["updated"] == 1
            assert data["removed"] == 0
            assert data["skipped"] == 0
            assert data["total_indexed"] == 4

    def test_reindex_full(self, configured_server, mock_embeddings):
        """reindex with full=True calls service with full=True."""
        mock_summary = {"added": 10, "updated": 0, "removed": 0, "skipped": 0, "total_indexed": 10}
        with patch("okf_tools.server.service.reindex", return_value=mock_summary) as mock_svc:
            result = reindex(full=True)
            mock_svc.assert_called_once()
            args = mock_svc.call_args
            assert args[0][1] is True  # full=True


class TestGetStats:
    """Tests for get_stats tool handler."""

    def test_get_stats_returns_correct_structure(self, configured_server, mock_embeddings):
        """get_stats returns JSON with correct structure."""
        mock_stats = {
            "concept_count": 5,
            "type_distribution": {"pattern": 3, "decision": 2},
            "tag_distribution": {"python": 4, "design": 1},
            "last_reindex_timestamp": "2024-01-15T10:30:00",
            "pending_reembedding_count": 2,
        }
        with patch("okf_tools.server.service.get_stats", return_value=mock_stats):
            result = get_stats()
            data = json.loads(result)
            assert data["concept_count"] == 5
            assert data["type_distribution"] == {"pattern": 3, "decision": 2}
            assert data["tag_distribution"] == {"python": 4, "design": 1}
            assert data["last_reindex_timestamp"] == "2024-01-15T10:30:00"
            assert data["pending_reembedding_count"] == 2

    def test_get_stats_no_bundle_returns_error(self):
        """get_stats with no bundle configured raises ToolError."""
        with patch("okf_tools.server._config", None):
            with pytest.raises(ToolError) as exc_info:
                get_stats()
            assert "No bundle configured" in str(exc_info.value)
