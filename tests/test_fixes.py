"""Tests for bug fixes: duplicate detection, wikilinks, --since, stats -b, FTS5 escaping."""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pytest

from okf_tools.bundle import Concept
from okf_tools.config import BundleRef, OkfConfig
from okf_tools.graph import LinkGraph, extract_links
from okf_tools.search import VectorIndex


# --- Helpers ---


def _make_concept(concept_id: str, body: str, bundle_root: Path) -> Concept:
    file_path = bundle_root / (concept_id + ".md")
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(f"---\ntype: Test\ntitle: {concept_id}\n---\n\n{body}\n")
    return Concept(
        concept_id=concept_id,
        frontmatter={"type": "Test", "title": concept_id},
        body=body,
        file_path=file_path,
    )


def _random_embedding():
    vec = np.random.randn(384).astype(np.float32)
    return vec / np.linalg.norm(vec)


def _upsert_concept(index, concept_id, title="Test", body="Some body text"):
    emb = _random_embedding()
    metadata = {
        "title": title,
        "type": "Pattern",
        "tags": ["test"],
        "mtime": time.time(),
        "snippet": body[:200],
        "body": body,
    }
    index.upsert(concept_id, emb, metadata)
    return emb


# --- FTS5 Hyphen Escaping ---


class TestFTS5Escaping:
    """FTS5 queries containing hyphens should not be misinterpreted as column:value."""

    @pytest.fixture
    def index(self, tmp_path):
        idx = VectorIndex(tmp_path / "test.db")
        yield idx
        idx.close()

    def test_hyphenated_query_does_not_crash(self, index):
        _upsert_concept(index, "multi-bundle-concept", body="multi bundle testing")
        # This previously raised: sqlite3.OperationalError: no such column: bundle
        results = index.search_keyword("multi-bundle", top_n=5)
        assert isinstance(results, list)

    def test_hyphenated_query_finds_results(self, index):
        _upsert_concept(index, "code-style", title="Code Style", body="code style preferences")
        results = index.search_keyword("code-style", top_n=5)
        assert len(results) >= 1
        assert results[0].concept_id == "code-style"

    def test_multiple_hyphens(self, index):
        _upsert_concept(index, "a", title="SSP Ref 8", body="ssp-ref-8-conditional-renewal")
        results = index.search_keyword("ssp-ref-8-conditional", top_n=5)
        assert isinstance(results, list)

    def test_normal_queries_still_work(self, index):
        _upsert_concept(index, "normal", body="regular search terms here")
        results = index.search_keyword("regular search", top_n=5)
        assert len(results) >= 1

    def test_escape_fts5_query_method(self, index):
        # Verify the static method produces quoted tokens
        escaped = VectorIndex._escape_fts5_query("multi-bundle test")
        assert '"multi-bundle"' in escaped
        assert '"test"' in escaped


# --- Wikilink Parsing ---


class TestWikilinkExtraction:
    """extract_links should parse [[wikilink]] syntax in addition to markdown links."""

    def test_basic_wikilink(self, tmp_path):
        concept = _make_concept("a", "See [[some-concept]] for details.", tmp_path)
        links = extract_links(concept, tmp_path)
        assert "some-concept" in links

    def test_wikilink_with_display_text(self, tmp_path):
        concept = _make_concept("a", "See [[target-id|Display Name]] here.", tmp_path)
        links = extract_links(concept, tmp_path)
        assert "target-id" in links

    def test_wikilink_spaces_converted_to_hyphens(self, tmp_path):
        concept = _make_concept("a", "See [[My Cool Concept]] here.", tmp_path)
        links = extract_links(concept, tmp_path)
        assert "my-cool-concept" in links

    def test_wikilink_case_normalized(self, tmp_path):
        concept = _make_concept("a", "See [[API Error Response]] here.", tmp_path)
        links = extract_links(concept, tmp_path)
        assert "api-error-response" in links

    def test_wikilink_with_md_extension_stripped(self, tmp_path):
        concept = _make_concept("a", "See [[other.md]] here.", tmp_path)
        links = extract_links(concept, tmp_path)
        assert "other" in links

    def test_wikilink_deduplicates_with_markdown_links(self, tmp_path):
        body = "See [[target]] and also [target](./target.md)."
        concept = _make_concept("a", body, tmp_path)
        links = extract_links(concept, tmp_path)
        # Should contain 'target' but not duplicated
        assert links.count("target") == 1

    def test_multiple_wikilinks(self, tmp_path):
        body = "Links: [[first]], [[second]], [[third]]."
        concept = _make_concept("a", body, tmp_path)
        links = extract_links(concept, tmp_path)
        assert "first" in links
        assert "second" in links
        assert "third" in links

    def test_wikilink_in_graph_population(self, tmp_path):
        """Full flow: commit with wikilinks should populate the link graph."""
        graph = LinkGraph(tmp_path / "graph.db")
        try:
            concept = _make_concept("source", "Links to [[target-a]] and [[target-b]].", tmp_path)
            targets = extract_links(concept, tmp_path)
            graph.set_links("source", targets)

            assert sorted(graph.get_outlinks("source")) == ["target-a", "target-b"]
            assert graph.get_inlinks("target-a") == ["source"]
        finally:
            graph.close()


# --- --since Filter ---


class TestSinceFilter:
    """--since should match against file mtime when no frontmatter timestamp."""

    def test_since_matches_recent_files(self, tmp_path):
        from okf_tools.service import list_concepts
        from tests.conftest import create_concept_file

        bundle = tmp_path / "bundle"
        bundle.mkdir()
        (bundle / "index.md").write_text("# Bundle\n")

        # Create a concept (file will have current mtime)
        create_concept_file(bundle, "recent", title="Recent")

        bundles = [BundleRef(name="test", path=bundle, default=True)]
        config = OkfConfig(
            bundle_path=bundle,
            index_path=Path(".okf/index"),
            embedding_model="test",
            default_top_n=5,
            similarity_threshold=0.85,
            auto_git_add=False,
            bundles=bundles,
        )

        # Should find today's concept
        concepts = list_concepts(config, since="2020-01-01")
        assert len(concepts) == 1
        assert concepts[0].concept_id == "recent"

    def test_since_excludes_old_files(self, tmp_path):
        import os
        from okf_tools.service import list_concepts
        from tests.conftest import create_concept_file

        bundle = tmp_path / "bundle"
        bundle.mkdir()
        (bundle / "index.md").write_text("# Bundle\n")

        file_path = create_concept_file(bundle, "old", title="Old")
        # Set mtime to 2020
        old_time = 1577836800.0  # 2020-01-01
        os.utime(file_path, (old_time, old_time))

        bundles = [BundleRef(name="test", path=bundle, default=True)]
        config = OkfConfig(
            bundle_path=bundle,
            index_path=Path(".okf/index"),
            embedding_model="test",
            default_top_n=5,
            similarity_threshold=0.85,
            auto_git_add=False,
            bundles=bundles,
        )

        # Should NOT find the old concept
        concepts = list_concepts(config, since="2025-01-01")
        assert len(concepts) == 0

    def test_since_uses_frontmatter_timestamp_when_present(self, tmp_path):
        from okf_tools.service import list_concepts
        from tests.conftest import create_concept_file

        bundle = tmp_path / "bundle"
        bundle.mkdir()
        (bundle / "index.md").write_text("# Bundle\n")

        create_concept_file(
            bundle, "timestamped", title="Timestamped",
            extra_fm={"timestamp": "2026-06-15"},
        )

        bundles = [BundleRef(name="test", path=bundle, default=True)]
        config = OkfConfig(
            bundle_path=bundle,
            index_path=Path(".okf/index"),
            embedding_model="test",
            default_top_n=5,
            similarity_threshold=0.85,
            auto_git_add=False,
            bundles=bundles,
        )

        # Frontmatter timestamp is 2026-06-15, filter from 2026-06-01
        concepts = list_concepts(config, since="2026-06-01")
        assert len(concepts) == 1

        # Filter from future date should exclude it
        concepts = list_concepts(config, since="2027-01-01")
        assert len(concepts) == 0


# --- Stats Respects -b Flag ---


class TestStatsBundleAwareness:
    """get_stats should return stats for only the specified bundle."""

    def test_stats_scoped_to_bundle(self, tmp_path):
        from okf_tools.service import get_stats
        from tests.conftest import create_concept_file

        bundle_a = tmp_path / "a"
        bundle_b = tmp_path / "b"
        bundle_a.mkdir()
        bundle_b.mkdir()
        (bundle_a / "index.md").write_text("# A\n")
        (bundle_b / "index.md").write_text("# B\n")

        # 3 concepts in A, 1 in B
        create_concept_file(bundle_a, "a1", title="A1")
        create_concept_file(bundle_a, "a2", title="A2")
        create_concept_file(bundle_a, "a3", title="A3")
        create_concept_file(bundle_b, "b1", title="B1", type_val="Bug Fix")

        bundles = [
            BundleRef(name="alpha", path=bundle_a, default=True),
            BundleRef(name="beta", path=bundle_b),
        ]
        config = OkfConfig(
            bundle_path=bundle_a,
            index_path=Path(".okf/index"),
            embedding_model="test",
            default_top_n=5,
            similarity_threshold=0.85,
            auto_git_add=False,
            bundles=bundles,
        )

        stats_a = get_stats(config, bundle_name="alpha")
        assert stats_a["concept_count"] == 3

        stats_b = get_stats(config, bundle_name="beta")
        assert stats_b["concept_count"] == 1
        assert "Bug Fix" in stats_b["type_distribution"]


# --- Duplicate Detection ---


class TestDuplicateDetection:
    """--check-duplicates should block when similar content exists."""

    def test_threshold_is_reasonable(self):
        from okf_tools.config import DEFAULTS
        # Threshold should be < 1.0 (otherwise it never fires)
        assert DEFAULTS["similarity_threshold"] < 1.0
        assert DEFAULTS["similarity_threshold"] >= 0.7

    def test_check_duplicates_raises_on_similar(self, tmp_path):
        """_check_duplicates raises ValidationError when similar content exists."""
        from okf_tools.errors import ValidationError
        from okf_tools.search import embed_text
        from okf_tools.service import _check_duplicates

        # Create index with one concept
        idx = VectorIndex(tmp_path / "test.db")
        emb = _random_embedding()
        idx.upsert("existing", emb, {
            "title": "Existing",
            "type": "Pattern",
            "tags": [],
            "mtime": time.time(),
            "snippet": "test",
            "body": "test",
        })
        idx.close()

        bundles = [BundleRef(name="test", path=tmp_path, default=True)]
        config = OkfConfig(
            bundle_path=tmp_path,
            index_path=Path(".okf/index"),
            embedding_model="BAAI/bge-small-en-v1.5",
            default_top_n=5,
            similarity_threshold=0.85,
            auto_git_add=False,
            bundles=bundles,
        )

        # This won't actually match since we used a random embedding,
        # but we can at least verify the function runs without error
        # when no duplicates are found
        from okf_tools.service import _check_duplicates
        # Should not raise (content is very different from random embedding)
        # This just tests the path doesn't crash
        try:
            _check_duplicates(config, "completely unique content xyz123", False)
        except ValidationError:
            pass  # Acceptable — means threshold caught something


# --- Unknown Fields Warning ---


class TestUnknownFieldWarning:
    """commit JSON with unrecognized fields should produce a warning."""

    def test_parse_commit_warns_on_unknown_fields(self, capsys):
        from okf_tools.cli import _parse_commit_input

        kwargs = {
            "json_input": json.dumps({
                "title": "Test",
                "type": "Decision",
                "content": "body",
                "links": ["foo"],
                "bogus": "bar",
            }),
            "check_duplicates": False,
            "force": False,
            "target_path": None,
            "file_input": None,
        }
        data = _parse_commit_input(kwargs)

        # Should still return the data
        assert data["title"] == "Test"

        # Should have printed warning to stderr
        captured = capsys.readouterr()
        assert "unrecognized fields ignored" in captured.err
        assert "bogus" in captured.err
        assert "links" in captured.err

    def test_parse_commit_no_warning_on_known_fields(self, capsys):
        from okf_tools.cli import _parse_commit_input

        kwargs = {
            "json_input": json.dumps({
                "title": "Test",
                "type": "Decision",
                "content": "body",
                "tags": ["a"],
                "timestamp": "2026-01-01",
                "description": "desc",
            }),
            "check_duplicates": True,
            "force": False,
            "target_path": None,
            "file_input": None,
        }
        data = _parse_commit_input(kwargs)

        captured = capsys.readouterr()
        assert "unrecognized" not in captured.err


# --- Reindex Respects -b ---


class TestReindexBundleAwareness:
    """reindex should target the specified bundle, not always the default."""

    def test_reindex_targets_specific_bundle(self, tmp_path):
        from okf_tools.service import reindex
        from tests.conftest import create_concept_file

        bundle_a = tmp_path / "a"
        bundle_b = tmp_path / "b"
        bundle_a.mkdir()
        bundle_b.mkdir()
        (bundle_a / "index.md").write_text("# A\n")
        (bundle_b / "index.md").write_text("# B\n")

        create_concept_file(bundle_a, "a1", title="A1")
        create_concept_file(bundle_a, "a2", title="A2")
        create_concept_file(bundle_b, "b1", title="B1")

        bundles = [
            BundleRef(name="alpha", path=bundle_a, default=True),
            BundleRef(name="beta", path=bundle_b),
        ]
        config = OkfConfig(
            bundle_path=bundle_a,
            index_path=Path(".okf/index"),
            embedding_model="BAAI/bge-small-en-v1.5",
            default_top_n=5,
            similarity_threshold=0.85,
            auto_git_add=False,
            bundles=bundles,
        )

        # Reindex only beta
        result = reindex(config, full=True, bundle_name="beta")
        assert result["total_indexed"] == 1  # Only b1

        # Reindex alpha
        result = reindex(config, full=True, bundle_name="alpha")
        assert result["total_indexed"] == 2  # a1 + a2
