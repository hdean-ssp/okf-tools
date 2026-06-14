"""Tests for bundle module: parsing, formatting, slugs, validation."""

from pathlib import Path

import pytest

from okf_tools.bundle import (
    Concept,
    format_concept,
    generate_slug,
    is_concept_file,
    parse_concept,
    remove_from_index_file,
    resolve_unique_path,
    update_index_file,
    validate_frontmatter,
)
from okf_tools.errors import ParseError


class TestParseAndFormat:
    def test_round_trip(self, tmp_path):
        content = "---\ntype: Pattern\ntitle: Test\ntags:\n- one\n- two\n---\n\nBody text.\n"
        f = tmp_path / "test.md"
        f.write_text(content)

        concept = parse_concept(f, tmp_path)
        assert concept.concept_id == "test"
        assert concept.type == "Pattern"
        assert concept.title == "Test"
        assert concept.tags == ["one", "two"]
        assert "Body text." in concept.body

        # Round-trip
        output = format_concept(concept)
        f2 = tmp_path / "test2.md"
        f2.write_text(output)
        concept2 = parse_concept(f2, tmp_path)
        assert concept2.frontmatter == concept.frontmatter
        assert concept2.body.strip() == concept.body.strip()

    def test_extra_yaml_keys_preserved(self, tmp_path):
        content = "---\ntype: Bug Fix\ncustom_key: hello\nanother: 42\n---\n\nBody.\n"
        f = tmp_path / "extra.md"
        f.write_text(content)

        concept = parse_concept(f, tmp_path)
        assert concept.frontmatter["custom_key"] == "hello"
        assert concept.frontmatter["another"] == 42

        output = format_concept(concept)
        assert "custom_key: hello" in output
        assert "another: 42" in output

    def test_parse_error_no_frontmatter(self, tmp_path):
        f = tmp_path / "bad.md"
        f.write_text("Just plain text, no frontmatter.")
        with pytest.raises(ParseError):
            parse_concept(f, tmp_path)

    def test_concept_id_from_nested_path(self, tmp_path):
        nested = tmp_path / "a" / "b"
        nested.mkdir(parents=True)
        f = nested / "deep.md"
        f.write_text("---\ntype: Test\n---\n\nDeep.\n")

        concept = parse_concept(f, tmp_path)
        assert concept.concept_id == "a/b/deep"


class TestValidation:
    def test_valid_frontmatter(self):
        fm = {"type": "Pattern", "tags": ["a", "b"], "timestamp": "2026-01-15"}
        assert validate_frontmatter(fm) == []

    def test_missing_type(self):
        errors = validate_frontmatter({})
        assert any("type" in e for e in errors)

    def test_empty_type(self):
        errors = validate_frontmatter({"type": ""})
        assert any("type" in e for e in errors)

    def test_invalid_timestamp(self):
        errors = validate_frontmatter({"type": "X", "timestamp": "not-a-date"})
        assert any("timestamp" in e for e in errors)

    def test_invalid_tags_not_list(self):
        errors = validate_frontmatter({"type": "X", "tags": "single-string"})
        assert any("tags" in e for e in errors)

    def test_invalid_tags_not_strings(self):
        errors = validate_frontmatter({"type": "X", "tags": [1, 2, 3]})
        assert any("tags" in e for e in errors)


class TestSlug:
    def test_basic(self):
        assert generate_slug("Hello World") == "hello-world"

    def test_special_chars(self):
        assert generate_slug("What's up? (Really!)") == "whats-up-really"

    def test_long_title_truncates(self):
        title = "this is a very long title that should be truncated at a word boundary"
        slug = generate_slug(title)
        assert len(slug) <= 60
        assert not slug.endswith("-")

    def test_consecutive_hyphens(self):
        assert generate_slug("a - - b") == "a-b"

    def test_empty_string(self):
        assert generate_slug("") == ""

    def test_unicode_removed(self):
        slug = generate_slug("café résumé")
        assert slug == "caf-rsum"  # non-ascii letters removed


class TestResolveUniquePath:
    def test_no_collision(self, tmp_path):
        path = resolve_unique_path(tmp_path, "new-file")
        assert path == tmp_path / "new-file.md"

    def test_collision_appends_suffix(self, tmp_path):
        (tmp_path / "existing.md").write_text("x")
        path = resolve_unique_path(tmp_path, "existing")
        assert path == tmp_path / "existing-2.md"

    def test_multiple_collisions(self, tmp_path):
        (tmp_path / "file.md").write_text("x")
        (tmp_path / "file-2.md").write_text("x")
        path = resolve_unique_path(tmp_path, "file")
        assert path == tmp_path / "file-3.md"


class TestIndexFile:
    def test_create_new_index(self, tmp_path):
        update_index_file(tmp_path, "my-concept", "My Concept")
        content = (tmp_path / "index.md").read_text()
        assert "- [My Concept](./my-concept.md)" in content

    def test_update_existing_entry(self, tmp_path):
        (tmp_path / "index.md").write_text(
            "# Dir\n\n- [Old Title](./my-concept.md)\n"
        )
        update_index_file(tmp_path, "my-concept", "New Title")
        content = (tmp_path / "index.md").read_text()
        assert "New Title" in content
        assert "Old Title" not in content

    def test_remove_entry(self, tmp_path):
        (tmp_path / "index.md").write_text(
            "# Dir\n\n- [A](./a.md)\n- [B](./b.md)\n"
        )
        remove_from_index_file(tmp_path, "a")
        content = (tmp_path / "index.md").read_text()
        assert "a.md" not in content
        assert "b.md" in content


class TestIsConceptFile:
    def test_concept_file(self, tmp_path):
        assert is_concept_file(tmp_path / "pattern.md")

    def test_index_excluded(self, tmp_path):
        assert not is_concept_file(tmp_path / "index.md")

    def test_log_excluded(self, tmp_path):
        assert not is_concept_file(tmp_path / "log.md")

    def test_non_md_excluded(self, tmp_path):
        assert not is_concept_file(tmp_path / "readme.txt")
