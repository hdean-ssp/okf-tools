"""Tests for the graph module: link extraction and traversal."""

from pathlib import Path

import pytest

from okf_tools.bundle import Concept
from okf_tools.graph import LinkGraph, extract_links


@pytest.fixture
def graph(tmp_path):
    db_path = tmp_path / "test.db"
    g = LinkGraph(db_path)
    yield g
    g.close()


def _make_concept(concept_id: str, body: str, bundle_root: Path) -> Concept:
    file_path = bundle_root / (concept_id + ".md")
    file_path.parent.mkdir(parents=True, exist_ok=True)
    return Concept(
        concept_id=concept_id,
        frontmatter={"type": "Test"},
        body=body,
        file_path=file_path,
    )


class TestExtractLinks:
    def test_relative_link(self, tmp_path):
        concept = _make_concept("a", "See [B](./b.md) here.", tmp_path)
        links = extract_links(concept, tmp_path)
        assert links == ["b"]

    def test_absolute_link(self, tmp_path):
        concept = _make_concept("sub/a", "See [X](/other/x.md).", tmp_path)
        links = extract_links(concept, tmp_path)
        assert links == ["other/x"]

    def test_external_url_excluded(self, tmp_path):
        concept = _make_concept("a", "See [Docs](https://example.com/page.md).", tmp_path)
        links = extract_links(concept, tmp_path)
        assert links == []

    def test_fragment_only_excluded(self, tmp_path):
        concept = _make_concept("a", "See [Section](#heading).", tmp_path)
        links = extract_links(concept, tmp_path)
        assert links == []

    def test_non_md_excluded(self, tmp_path):
        concept = _make_concept("a", "See [Image](./pic.png).", tmp_path)
        links = extract_links(concept, tmp_path)
        assert links == []

    def test_multiple_links(self, tmp_path):
        body = "Links: [A](./a.md), [B](./b.md), and [ext](https://x.com)."
        concept = _make_concept("root", body, tmp_path)
        links = extract_links(concept, tmp_path)
        assert sorted(links) == ["a", "b"]

    def test_nested_relative_link(self, tmp_path):
        concept = _make_concept("sub/a", "See [sibling](./b.md).", tmp_path)
        links = extract_links(concept, tmp_path)
        assert links == ["sub/b"]


class TestLinkGraph:
    def test_set_and_get_outlinks(self, graph):
        graph.set_links("a", ["b", "c"])
        assert sorted(graph.get_outlinks("a")) == ["b", "c"]

    def test_get_inlinks(self, graph):
        graph.set_links("a", ["b"])
        graph.set_links("c", ["b"])
        assert sorted(graph.get_inlinks("b")) == ["a", "c"]

    def test_remove_concept(self, graph):
        graph.set_links("a", ["b"])
        graph.set_links("b", ["a"])
        graph.remove_concept("a")
        assert graph.get_outlinks("a") == []
        assert graph.get_inlinks("a") == []

    def test_bfs_both(self, graph):
        graph.set_links("a", ["b"])
        graph.set_links("b", ["c"])
        neighbors = graph.bfs_neighborhood("a", depth=2, direction="both")
        assert "b" in neighbors
        assert "c" in neighbors

    def test_bfs_direction_out(self, graph):
        graph.set_links("a", ["b"])
        graph.set_links("c", ["a"])  # c points to a
        neighbors = graph.bfs_neighborhood("a", depth=2, direction="out")
        assert "b" in neighbors
        assert "c" not in neighbors

    def test_orphans(self, graph):
        graph.set_links("a", ["b"])
        all_ids = {"a", "b", "c"}
        orphans = graph.get_orphans(all_ids)
        assert orphans == ["c"]

    def test_stats(self, graph):
        graph.set_links("a", ["b", "c"])
        graph.set_links("b", ["c"])
        stats = graph.get_stats(3)
        assert stats["edge_count"] == 3
        assert stats["average_links_per_concept"] == 1.0
