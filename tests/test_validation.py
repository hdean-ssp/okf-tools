"""Tests for the validation/linting module."""

from pathlib import Path

import pytest

from okf_tools.config import OkfConfig
from okf_tools.validation import (
    check_link_integrity,
    check_type_consistency,
    lint_bundle,
    validate_concept_full,
    validate_structure,
)
from tests.conftest import create_concept_file


@pytest.fixture
def config(tmp_bundle):
    return OkfConfig(
        bundle_path=tmp_bundle,
        index_path=Path(".okf/index"),
        embedding_model="BAAI/bge-small-en-v1.5",
        default_top_n=5,
        similarity_threshold=1.0,
        auto_git_add=False,
        skills_paths=[],
        validation_level="standard",
    )


class TestValidateStructure:
    def test_missing_index(self, tmp_bundle):
        subdir = tmp_bundle / "patterns"
        subdir.mkdir()
        create_concept_file(tmp_bundle, "patterns/test", title="Test")
        from okf_tools.bundle import walk_concepts

        concepts = walk_concepts(tmp_bundle)
        diags = validate_structure(tmp_bundle, concepts)
        assert any(d.rule == "structure/missing-index" for d in diags)

    def test_orphaned_entry(self, tmp_bundle):
        subdir = tmp_bundle / "patterns"
        subdir.mkdir()
        create_concept_file(tmp_bundle, "patterns/real", title="Real")
        (subdir / "index.md").write_text(
            "# Patterns\n\n- [Real](./real.md)\n- [Ghost](./ghost.md)\n"
        )
        from okf_tools.bundle import walk_concepts

        concepts = walk_concepts(tmp_bundle)
        diags = validate_structure(tmp_bundle, concepts)
        assert any(d.rule == "structure/orphaned-entry" for d in diags)

    def test_clean_structure(self, tmp_bundle):
        subdir = tmp_bundle / "patterns"
        subdir.mkdir()
        create_concept_file(tmp_bundle, "patterns/one", title="One")
        (subdir / "index.md").write_text("# Patterns\n\n- [One](./one.md)\n")
        from okf_tools.bundle import walk_concepts

        concepts = walk_concepts(tmp_bundle)
        diags = validate_structure(tmp_bundle, concepts)
        assert len(diags) == 0


class TestLinkIntegrity:
    def test_broken_link(self, tmp_bundle):
        create_concept_file(
            tmp_bundle,
            "a",
            body="See [missing](./nonexistent.md) for details.",
        )
        from okf_tools.bundle import walk_concepts

        concepts = walk_concepts(tmp_bundle)
        diags = check_link_integrity(concepts, tmp_bundle)
        assert any(d.rule == "links/broken-internal" for d in diags)
        assert "nonexistent" in diags[0].message

    def test_valid_link(self, tmp_bundle):
        create_concept_file(tmp_bundle, "a", body="See [B](./b.md).")
        create_concept_file(tmp_bundle, "b", body="Content.")
        from okf_tools.bundle import walk_concepts

        concepts = walk_concepts(tmp_bundle)
        diags = check_link_integrity(concepts, tmp_bundle)
        assert len(diags) == 0


class TestTypeConsistency:
    def test_near_duplicates(self, tmp_bundle):
        create_concept_file(tmp_bundle, "a", type_val="Bug Fix")
        create_concept_file(tmp_bundle, "b", type_val="bug-fix")
        create_concept_file(tmp_bundle, "c", type_val="bugfix")
        from okf_tools.bundle import walk_concepts

        concepts = walk_concepts(tmp_bundle)
        diags = check_type_consistency(concepts)
        assert any(d.rule == "types/near-duplicate" for d in diags)

    def test_no_duplicates(self, tmp_bundle):
        create_concept_file(tmp_bundle, "a", type_val="Pattern")
        create_concept_file(tmp_bundle, "b", type_val="Decision")
        from okf_tools.bundle import walk_concepts

        concepts = walk_concepts(tmp_bundle)
        diags = check_type_consistency(concepts)
        assert len(diags) == 0


class TestValidationLevels:
    def test_strict_requires_title_and_description(self, tmp_bundle):
        create_concept_file(tmp_bundle, "bare", type_val="Pattern", title="")
        from okf_tools.bundle import parse_concept

        concept = parse_concept(tmp_bundle / "bare.md", tmp_bundle)
        diags = validate_concept_full(concept, "strict")
        rules = {d.rule for d in diags}
        assert "frontmatter/title-required" in rules
        assert "frontmatter/description-required" in rules

    def test_standard_accepts_no_title(self, tmp_bundle):
        create_concept_file(tmp_bundle, "notitle", type_val="Pattern", title="")
        from okf_tools.bundle import parse_concept

        concept = parse_concept(tmp_bundle / "notitle.md", tmp_bundle)
        diags = validate_concept_full(concept, "standard")
        rules = {d.rule for d in diags}
        assert "frontmatter/title-required" not in rules

    def test_relaxed_downgrades_to_warnings(self, tmp_bundle):
        # Create a concept with invalid tags
        f = tmp_bundle / "badtags.md"
        f.write_text("---\ntype: X\ntags: not-a-list\n---\n\nBody.\n")
        from okf_tools.bundle import parse_concept

        concept = parse_concept(f, tmp_bundle)
        diags = validate_concept_full(concept, "relaxed")
        assert all(d.severity == "warning" for d in diags)


class TestLintBundle:
    def test_clean_bundle(self, tmp_bundle, config):
        report = lint_bundle(tmp_bundle, config)
        assert report.errors == 0
        assert report.warnings == 0

    def test_rule_filter(self, tmp_bundle, config):
        create_concept_file(tmp_bundle, "a", body="See [ghost](./ghost.md).")
        # Only run link checks
        report = lint_bundle(tmp_bundle, config, rule_filter="links")
        assert all(d.rule.startswith("links/") for d in report.diagnostics)

    def test_path_filter(self, tmp_bundle, config):
        subdir = tmp_bundle / "sub"
        subdir.mkdir()
        create_concept_file(tmp_bundle, "sub/a", type_val="Pattern")
        create_concept_file(tmp_bundle, "root-concept", type_val="Pattern")
        report = lint_bundle(tmp_bundle, config, path_filter="sub")
        # Should only check 1 file (sub/a), not root-concept
        assert report.files_checked == 1
