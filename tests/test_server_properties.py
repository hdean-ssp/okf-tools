"""Property-based tests for okf_tools.server module.

Uses Hypothesis to verify correctness properties across many random inputs.
Validates: Requirements 3.2, 8.2
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from hypothesis import given, HealthCheck, settings, strategies as st

from okf_tools.config import OkfConfig
from okf_tools.search import SearchResult
from okf_tools.server import commit_concept, fetch_concepts, init_bundle, show_concept, update_concept

# ---------------------------------------------------------------------------
# Hypothesis strategies for valid concept fields
# ---------------------------------------------------------------------------

valid_titles = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "S", "Z")),
    min_size=1,
    max_size=100,
).filter(lambda s: s.strip() and any(c.isascii() and c.isalnum() for c in s))

valid_types = st.sampled_from(["pattern", "decision", "principle", "reference", "note"])

valid_content = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "S", "Z")),
    min_size=1,
    max_size=1000,
).filter(lambda s: s.strip())

valid_tags = st.lists(
    st.text(
        alphabet=st.characters(whitelist_categories=("L", "N")),
        min_size=1,
        max_size=30,
    ).filter(lambda s: s.strip()),
    min_size=0,
    max_size=5,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def mock_embeddings_pbt():
    """Mock embed_text and VectorIndex to avoid real embedding calls."""
    with patch("okf_tools.service.embed_text") as mock_embed, \
         patch("okf_tools.service.VectorIndex") as mock_index_cls:
        mock_embed.return_value = [0.1] * 384
        mock_index = mock_index_cls.return_value
        mock_index.search.return_value = []
        mock_index.get_sync_timestamp.return_value = None
        mock_index.concept_count.return_value = 0
        mock_index.close.return_value = None
        mock_index.upsert.return_value = None
        mock_index.delete.return_value = None
        yield


@pytest.fixture
def pbt_config(tmp_path):
    """Create a fresh bundle and return a configured server for PBT."""
    # Initialize a fresh bundle
    init_bundle(path=str(tmp_path))

    config = OkfConfig(
        bundle_path=tmp_path,
        index_path=Path(".okf/index"),
        embedding_model="test",
        default_top_n=5,
        similarity_threshold=0.85,
        auto_git_add=False,
    )
    with patch("okf_tools.server._config", config):
        yield config


# ---------------------------------------------------------------------------
# Property 1: Commit-then-show round-trip preserves data
# Validates: Requirements 3.2, 8.2
# ---------------------------------------------------------------------------


@given(title=valid_titles, type_val=valid_types, content=valid_content, tags=valid_tags)
@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_commit_then_show_round_trip(title, type_val, content, tags, pbt_config):
    """Property 1: Commit-then-show round-trip preserves data.

    **Validates: Requirements 3.2, 8.2**

    For any valid combination of title, type, content, and tags,
    committing a concept and then showing it returns the original data.
    """
    result = commit_concept(title=title, type=type_val, content=content, tags=tags)
    data = json.loads(result)
    concept_id = data["concept_id"]

    show_result = show_concept(concept_id=concept_id)
    show_data = json.loads(show_result)

    assert show_data["title"] == title
    assert show_data["type"] == type_val
    assert content.strip() in show_data["body"]
    if tags:
        assert show_data["tags"] == tags


# ---------------------------------------------------------------------------
# Property 2: Missing required fields are enumerated in validation error
# Validates: Requirements 3.3
# ---------------------------------------------------------------------------


@given(fields_to_omit=st.sets(st.sampled_from(["title", "content"]), min_size=1))
@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_missing_required_fields_enumerated(fields_to_omit, pbt_config):
    """Property 2: Missing required fields are enumerated in validation error.

    **Validates: Requirements 3.3**

    For any non-empty subset of required fields {title, content} that is omitted
    (set to empty string), the validation error lists exactly those missing fields.
    """
    from mcp.server.fastmcp.exceptions import ToolError
    from okf_tools.server import commit_concept

    kwargs = {
        "title": "Valid Title",
        "type": "pattern",
        "content": "Valid content",
    }
    # Set the fields to omit to empty string (which triggers "missing" validation)
    for field in fields_to_omit:
        kwargs[field] = ""

    with pytest.raises(ToolError) as exc_info:
        commit_concept(**kwargs)

    error_msg = str(exc_info.value).lower()
    for field in fields_to_omit:
        assert field in error_msg, f"Expected '{field}' in error message: {error_msg}"


# ---------------------------------------------------------------------------
# Property 5: Delete removes concept and returns concept_id
# Validates: Requirements 5.2
# ---------------------------------------------------------------------------


@given(title=valid_titles, type_val=valid_types, content=valid_content)
@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_delete_removes_concept(title, type_val, content, pbt_config):
    """Property 5: Delete removes concept and returns concept_id.

    **Validates: Requirements 5.2**

    For any concept that exists in the bundle, invoking delete_concept
    returns the concept_id and the concept file no longer exists.
    """
    from mcp.server.fastmcp.exceptions import ToolError
    from okf_tools.server import commit_concept, delete_concept, show_concept

    # Create a concept
    result = commit_concept(title=title, type=type_val, content=content)
    data = json.loads(result)
    concept_id = data["concept_id"]

    # Delete it
    delete_result = delete_concept(concept_id=concept_id)
    delete_data = json.loads(delete_result)

    # Assert response contains concept_id
    assert delete_data["concept_id"] == concept_id

    # Assert concept no longer exists
    with pytest.raises(ToolError) as exc_info:
        show_concept(concept_id=concept_id)
    assert "not found" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# Property 3: Update applies only provided fields
# Validates: Requirements 4.2
# ---------------------------------------------------------------------------


@given(
    new_title=valid_titles,
    new_content=valid_content,
    update_fields=st.sets(st.sampled_from(["title", "content"]), min_size=1),
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_update_applies_only_provided_fields(new_title, new_content, update_fields, pbt_config):
    """Property 3: Update applies only provided fields.

    **Validates: Requirements 4.2**

    For any existing concept and any non-empty subset of update fields,
    only the specified fields change; all others remain at prior values.
    """
    from okf_tools.server import commit_concept, update_concept, show_concept

    # Create a concept with known values
    result = commit_concept(title="Original Title", type="pattern", content="Original content")
    data = json.loads(result)
    concept_id = data["concept_id"]

    # Get the original state
    original = json.loads(show_concept(concept_id=concept_id))

    # Build update kwargs
    update_kwargs = {"concept_id": concept_id}
    if "title" in update_fields:
        update_kwargs["title"] = new_title
    if "content" in update_fields:
        update_kwargs["content"] = new_content

    update_concept(**update_kwargs)

    # Get the updated state
    updated = json.loads(show_concept(concept_id=concept_id))

    # Verify only updated fields changed
    if "title" in update_fields:
        assert updated["title"] == new_title
    else:
        assert updated["title"] == original["title"]

    if "content" in update_fields:
        assert new_content.strip() in updated["body"]
    else:
        assert updated["body"] == original["body"]

    # Type should never change (we never update it)
    assert updated["type"] == original["type"]


# ---------------------------------------------------------------------------
# Property 6: Search results have valid structure
# Validates: Requirements 6.2
# ---------------------------------------------------------------------------


@given(
    query=st.text(min_size=1, max_size=50).filter(lambda s: s.strip()),
    score=st.floats(min_value=0.0, max_value=1.0),
    snippet_len=st.integers(min_value=0, max_value=500),
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_search_results_have_valid_structure(query, score, snippet_len, pbt_config):
    """Property 6: Search results have valid structure.

    **Validates: Requirements 6.2**

    For any search query that returns results, each result has
    non-empty concept_id, title string, score in [0.0, 1.0],
    and snippet with length ≤ 200 characters.
    """
    # Create mock results with the generated parameters
    snippet = "x" * snippet_len
    mock_results = [
        SearchResult(concept_id="test/concept", title="Test Title", score=score, snippet=snippet),
    ]

    with patch("okf_tools.server.service.fetch_concepts", return_value=mock_results):
        result = fetch_concepts(query=query)
        data = json.loads(result)

        for r in data["results"]:
            assert r["concept_id"]  # non-empty
            assert isinstance(r["title"], str)
            assert 0.0 <= r["score"] <= 1.0
            assert len(r["snippet"]) <= 200


# ---------------------------------------------------------------------------
# Property 4: Invalid updates are rejected without modifying the concept
# Validates: Requirements 4.5
# ---------------------------------------------------------------------------


@given(invalid_type=st.text(max_size=0))
@settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_invalid_updates_rejected_without_modification(invalid_type, pbt_config):
    """Property 4: Invalid updates are rejected without modifying the concept.

    **Validates: Requirements 4.5**

    For any update that would produce invalid frontmatter (empty type),
    a validation error is returned and the concept remains unchanged.
    """
    from mcp.server.fastmcp.exceptions import ToolError
    from okf_tools.server import commit_concept, update_concept, show_concept

    # Create a concept
    result = commit_concept(title="Test Concept", type="pattern", content="Test content")
    data = json.loads(result)
    concept_id = data["concept_id"]

    # Get original state
    original = json.loads(show_concept(concept_id=concept_id))

    # Try to update with invalid type (empty string)
    with pytest.raises(ToolError):
        update_concept(concept_id=concept_id, type=invalid_type)

    # Verify concept is unchanged
    current = json.loads(show_concept(concept_id=concept_id))
    assert current["title"] == original["title"]
    assert current["type"] == original["type"]
    assert current["body"] == original["body"]


# ---------------------------------------------------------------------------
# Property 7: Whitespace-only queries are rejected
# Validates: Requirements 6.5
# ---------------------------------------------------------------------------


@given(whitespace_query=st.text(
    alphabet=st.sampled_from([" ", "\t", "\n", "\r", "\v", "\f"]),
    min_size=1, max_size=50
))
@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_whitespace_only_queries_rejected(whitespace_query, pbt_config):
    """Property 7: Whitespace-only queries are rejected.
    
    **Validates: Requirements 6.5**
    
    For any string composed entirely of whitespace characters,
    invoking fetch_concepts raises a validation error.
    """
    from mcp.server.fastmcp.exceptions import ToolError
    from okf_tools.server import fetch_concepts
    
    with pytest.raises(ToolError) as exc_info:
        fetch_concepts(query=whitespace_query)
    assert "non-empty query" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# Property 8: List results are sorted and structurally complete
# Validates: Requirements 7.2
# ---------------------------------------------------------------------------


@given(
    num_concepts=st.integers(min_value=1, max_value=5),
    type_val=valid_types,
)
@settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_list_results_sorted_and_complete(num_concepts, type_val, pbt_config):
    """Property 8: List results are sorted and structurally complete.
    
    **Validates: Requirements 7.2**
    
    For any bundle with concepts, list_concepts returns results
    sorted by concept_id with each entry containing concept_id, title, type, tags.
    """
    from okf_tools.server import commit_concept, list_concepts
    
    # Create multiple concepts
    for i in range(num_concepts):
        commit_concept(title=f"Concept {i}", type=type_val, content=f"Content for concept {i}")
    
    result = list_concepts()
    data = json.loads(result)
    
    concepts = data["concepts"]
    assert len(concepts) >= num_concepts
    
    # Check structure
    for c in concepts:
        assert "concept_id" in c and c["concept_id"]
        assert "title" in c
        assert "type" in c
        assert "tags" in c and isinstance(c["tags"], list)
    
    # Check sorted by concept_id
    ids = [c["concept_id"] for c in concepts]
    assert ids == sorted(ids)


# ---------------------------------------------------------------------------
# Property 10: Domain errors map to MCP error responses with full context
# Validates: Requirements 11.1, 11.2
# ---------------------------------------------------------------------------


@given(
    error_messages=st.lists(st.text(min_size=1, max_size=50).filter(lambda s: s.strip()), min_size=1, max_size=5),
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_validation_error_maps_all_messages(error_messages, pbt_config):
    """Property 10a: ValidationError maps all messages to MCP error response.
    
    **Validates: Requirements 11.1**
    """
    from okf_tools.server import _handle_error
    from okf_tools.errors import ValidationError
    
    err = ValidationError(error_messages)
    result = _handle_error(err)
    
    for msg in error_messages:
        assert msg in result


@given(
    concept_id=st.text(
        alphabet=st.characters(whitelist_categories=("L", "N", "P")),
        min_size=1, max_size=50
    ).filter(lambda s: s.strip()),
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_concept_not_found_maps_id(concept_id, pbt_config):
    """Property 10b: ConceptNotFoundError maps concept_id to MCP error response.
    
    **Validates: Requirements 11.2**
    """
    from okf_tools.server import _handle_error
    from okf_tools.errors import ConceptNotFoundError
    
    err = ConceptNotFoundError(concept_id)
    result = _handle_error(err)
    
    assert concept_id in result


# ---------------------------------------------------------------------------
# Property 11: Unexpected errors do not expose internal details
# Validates: Requirements 11.4
# ---------------------------------------------------------------------------


@given(
    error_msg=st.text(min_size=1, max_size=100).filter(lambda s: s.strip()),
    file_path=st.text(
        alphabet=st.characters(whitelist_categories=("L", "N", "P")),
        min_size=5, max_size=50
    ).map(lambda s: f"/home/user/{s}.py"),
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_unexpected_errors_hide_internal_details(error_msg, file_path, pbt_config):
    """Property 11: Unexpected errors do not expose internal details.
    
    **Validates: Requirements 11.4**
    
    For any unexpected exception, the MCP error response does not contain
    Python traceback text, absolute file paths, or class names.
    """
    from mcp.server.fastmcp.exceptions import ToolError
    from okf_tools.server import get_stats
    
    # Mock service.get_stats to raise an unexpected exception
    class CustomInternalError(Exception):
        pass
    
    exc = CustomInternalError(f"{error_msg} in {file_path}")
    
    with patch("okf_tools.server.service.get_stats", side_effect=exc):
        with pytest.raises(ToolError) as exc_info:
            get_stats()
        
        error_response = str(exc_info.value)
        # Should not contain the internal error message
        assert error_msg not in error_response
        # Should not contain file paths
        assert file_path not in error_response
        assert "/home/" not in error_response
        # Should not contain class name
        assert "CustomInternalError" not in error_response
        # Should contain generic message
        assert "internal error" in error_response.lower()


# ---------------------------------------------------------------------------
# Property 9: Stats response has correct structure and types
# Validates: Requirements 10.2
# ---------------------------------------------------------------------------


@given(
    concept_count=st.integers(min_value=0, max_value=100),
    num_types=st.integers(min_value=1, max_value=5),
    num_tags=st.integers(min_value=0, max_value=10),
    pending=st.integers(min_value=0, max_value=50),
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_stats_response_has_correct_structure(concept_count, num_types, num_tags, pending, pbt_config):
    """Property 9: Stats response has correct structure and types.
    
    **Validates: Requirements 10.2**
    
    For any configured bundle, get_stats returns an object with
    concept_count (int >= 0), type_distribution (dict with int values),
    tag_distribution (dict with int values), last_reindex_timestamp (str or null),
    and pending_reembedding_count (int >= 0).
    """
    from okf_tools.server import get_stats
    
    # Build mock stats
    type_dist = {f"type_{i}": i + 1 for i in range(num_types)}
    tag_dist = {f"tag_{i}": i + 1 for i in range(num_tags)}
    mock_stats = {
        "concept_count": concept_count,
        "type_distribution": type_dist,
        "tag_distribution": tag_dist,
        "last_reindex_timestamp": None,
        "pending_reembedding_count": pending,
    }
    
    with patch("okf_tools.server.service.get_stats", return_value=mock_stats):
        result = get_stats()
        data = json.loads(result)
        
        assert isinstance(data["concept_count"], int) and data["concept_count"] >= 0
        assert isinstance(data["type_distribution"], dict)
        for v in data["type_distribution"].values():
            assert isinstance(v, int)
        assert isinstance(data["tag_distribution"], dict)
        for v in data["tag_distribution"].values():
            assert isinstance(v, int)
        assert data["last_reindex_timestamp"] is None or isinstance(data["last_reindex_timestamp"], str)
        assert isinstance(data["pending_reembedding_count"], int) and data["pending_reembedding_count"] >= 0


# ---------------------------------------------------------------------------
# Property 12: Non-init tools require a configured bundle
# Validates: Requirements 12.5
# ---------------------------------------------------------------------------


@given(tool_idx=st.integers(min_value=0, max_value=7))
@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_non_init_tools_require_configured_bundle(tool_idx, pbt_config):
    """Property 12: Non-init tools require a configured bundle.
    
    **Validates: Requirements 12.5**
    
    For each tool except init_bundle, invoking it when no bundle
    is configured returns an error indicating no bundle is configured.
    """
    from mcp.server.fastmcp.exceptions import ToolError
    from okf_tools.server import (
        commit_concept, update_concept, delete_concept,
        fetch_concepts, list_concepts, show_concept, reindex, get_stats,
    )
    
    tools_and_kwargs = [
        (commit_concept, {"title": "T", "type": "p", "content": "c"}),
        (update_concept, {"concept_id": "test", "title": "New"}),
        (delete_concept, {"concept_id": "test"}),
        (fetch_concepts, {"query": "test"}),
        (list_concepts, {}),
        (show_concept, {"concept_id": "test"}),
        (reindex, {}),
        (get_stats, {}),
    ]
    
    tool_fn, kwargs = tools_and_kwargs[tool_idx]
    
    with patch("okf_tools.server._config", None):
        with pytest.raises(ToolError) as exc_info:
            tool_fn(**kwargs)
        assert "no bundle configured" in str(exc_info.value).lower()
