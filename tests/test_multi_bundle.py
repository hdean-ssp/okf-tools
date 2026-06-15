"""Tests for multi-bundle configuration, write routing, and aggregated list."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from okf_tools.config import (
    BundleRef,
    OkfConfig,
    _parse_bundles,
    _resolve_path,
    load_config,
)
from okf_tools.errors import ConfigError


# --- BundleRef tests ---


class TestBundleRef:
    def test_defaults(self):
        b = BundleRef(name="test", path=Path("/tmp/test"))
        assert b.writable is True
        assert b.default is False

    def test_index_db_path(self):
        b = BundleRef(name="x", path=Path("/data/kb"))
        assert b.index_db_path == Path("/data/kb/.okf/index/okf.db")

    def test_explicit_writable_false(self):
        b = BundleRef(name="ref", path=Path("/ref"), writable=False)
        assert b.writable is False


# --- _parse_bundles tests ---


class TestParseBundles:
    def test_basic_parsing(self):
        raw = [
            {"name": "a", "path": "/tmp/a"},
            {"name": "b", "path": "~/b", "default": True},
            {"name": "c", "path": "/c", "writable": False},
        ]
        result = _parse_bundles(raw)
        assert len(result) == 3
        assert result[0].name == "a"
        assert result[0].writable is True
        assert result[0].default is False
        assert result[1].default is True
        assert result[2].writable is False

    def test_skips_invalid_entries(self):
        raw = [
            {"name": "good", "path": "/tmp"},
            {"name": "no_path"},  # Missing path
            {"path": "/no_name"},  # Missing name
            "not_a_dict",
        ]
        result = _parse_bundles(raw)
        assert len(result) == 1
        assert result[0].name == "good"

    def test_path_resolution(self):
        raw = [{"name": "home", "path": "~/test-bundle"}]
        result = _parse_bundles(raw)
        assert "~" not in str(result[0].path)
        assert result[0].path.is_absolute()


# --- OkfConfig multi-bundle helpers ---


class TestOkfConfigHelpers:
    @pytest.fixture
    def multi_config(self) -> OkfConfig:
        bundles = [
            BundleRef(name="personal", path=Path("/home/user/personal")),
            BundleRef(name="team", path=Path("/shared/team"), default=True),
            BundleRef(name="archive", path=Path("/archive"), writable=False),
        ]
        return OkfConfig(
            bundle_path=Path("/shared/team"),
            index_path=Path(".okf/index"),
            embedding_model="test",
            default_top_n=5,
            similarity_threshold=1.0,
            auto_git_add=False,
            bundles=bundles,
        )

    def test_get_bundle_by_name(self, multi_config):
        assert multi_config.get_bundle("personal").name == "personal"
        assert multi_config.get_bundle("team").name == "team"
        assert multi_config.get_bundle("nonexistent") is None

    def test_get_default_bundle(self, multi_config):
        assert multi_config.get_default_bundle().name == "team"

    def test_get_default_falls_back_to_first(self):
        bundles = [
            BundleRef(name="a", path=Path("/a")),
            BundleRef(name="b", path=Path("/b")),
        ]
        config = OkfConfig(
            bundle_path=Path("/a"),
            index_path=Path(".okf/index"),
            embedding_model="test",
            default_top_n=5,
            similarity_threshold=1.0,
            auto_git_add=False,
            bundles=bundles,
        )
        assert config.get_default_bundle().name == "a"

    def test_get_writable_bundle_default(self, multi_config):
        assert multi_config.get_writable_bundle().name == "team"

    def test_get_writable_bundle_by_name(self, multi_config):
        assert multi_config.get_writable_bundle("personal").name == "personal"

    def test_get_writable_bundle_raises_on_readonly(self, multi_config):
        with pytest.raises(ConfigError) as exc_info:
            multi_config.get_writable_bundle("archive")
        assert "read-only" in str(exc_info.value)

    def test_get_writable_bundle_raises_on_not_found(self, multi_config):
        with pytest.raises(ConfigError) as exc_info:
            multi_config.get_writable_bundle("nonexistent")
        assert "not found" in str(exc_info.value)

    def test_get_writable_bundle_raises_on_empty(self):
        config = OkfConfig(
            bundle_path=Path("/tmp"),
            index_path=Path(".okf/index"),
            embedding_model="test",
            default_top_n=5,
            similarity_threshold=1.0,
            auto_git_add=False,
            bundles=[],
        )
        with pytest.raises(ConfigError) as exc_info:
            config.get_writable_bundle()
        assert "No bundles configured" in str(exc_info.value)


# --- load_config with bundles ---


class TestLoadConfigMultiBundle:
    def test_user_level_bundles(self, tmp_path, monkeypatch):
        """User config with bundles array is parsed correctly."""
        user_config_dir = tmp_path / "user_config"
        user_config_dir.mkdir()
        user_config = user_config_dir / "config.json"
        user_config.write_text(json.dumps({
            "bundles": [
                {"name": "personal", "path": str(tmp_path / "personal")},
                {"name": "team", "path": str(tmp_path / "team"), "default": True},
            ]
        }))

        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        # Create the expected path structure
        (tmp_path / ".config" / "okf").mkdir(parents=True)
        (tmp_path / ".config" / "okf" / "config.json").write_text(json.dumps({
            "bundles": [
                {"name": "personal", "path": str(tmp_path / "personal")},
                {"name": "team", "path": str(tmp_path / "team"), "default": True},
            ]
        }))

        config = load_config(tmp_path)  # No .okf/config.json here
        assert len(config.bundles) >= 1

    def test_backward_compat_no_bundles(self, tmp_path, monkeypatch):
        """When no bundles array exists, synthesise from bundle_path."""
        # Ensure no user config interferes
        fake_home = tmp_path / "fakehome"
        fake_home.mkdir()
        monkeypatch.setattr(Path, "home", lambda: fake_home)

        okf_dir = tmp_path / ".okf"
        okf_dir.mkdir()
        (okf_dir / "config.json").write_text(json.dumps({
            "default_top_n": 10
        }))

        config = load_config(tmp_path)
        # Should have a synthetic bundle
        assert len(config.bundles) == 1
        assert config.bundles[0].path == tmp_path
        assert config.bundles[0].writable is True
        assert config.bundles[0].default is True

    def test_project_bundles_override_user(self, tmp_path, monkeypatch):
        """Project-level bundles take priority over user-level (by name)."""
        # Create user config
        user_home = tmp_path / "home"
        user_home.mkdir()
        (user_home / ".config" / "okf").mkdir(parents=True)
        (user_home / ".config" / "okf" / "config.json").write_text(json.dumps({
            "bundles": [
                {"name": "shared", "path": str(tmp_path / "user-shared")},
            ]
        }))
        monkeypatch.setattr(Path, "home", lambda: user_home)

        # Create project config with same bundle name
        project = tmp_path / "project"
        project.mkdir()
        (project / ".okf").mkdir()
        (project / ".okf" / "config.json").write_text(json.dumps({
            "bundles": [
                {"name": "shared", "path": str(tmp_path / "project-shared"), "default": True},
            ]
        }))

        config = load_config(project)
        # Project version should win (deduplicated by name)
        shared = config.get_bundle("shared")
        assert shared is not None
        assert "project-shared" in str(shared.path)


# --- Multi-bundle list_concepts ---


class TestMultiBundleList:
    def test_list_aggregates_across_bundles(self, tmp_path):
        """list_concepts returns concepts from all bundles."""
        from okf_tools.service import list_concepts
        from tests.conftest import create_concept_file

        # Create two bundle directories
        bundle_a = tmp_path / "bundle_a"
        bundle_b = tmp_path / "bundle_b"
        bundle_a.mkdir()
        bundle_b.mkdir()
        (bundle_a / "index.md").write_text("# A\n")
        (bundle_b / "index.md").write_text("# B\n")

        create_concept_file(bundle_a, "concept-a", title="Concept A")
        create_concept_file(bundle_b, "concept-b", title="Concept B")

        bundles = [
            BundleRef(name="a", path=bundle_a, default=True),
            BundleRef(name="b", path=bundle_b),
        ]
        config = OkfConfig(
            bundle_path=bundle_a,
            index_path=Path(".okf/index"),
            embedding_model="test",
            default_top_n=5,
            similarity_threshold=1.0,
            auto_git_add=False,
            bundles=bundles,
        )

        concepts = list_concepts(config)
        ids = [c.concept_id for c in concepts]
        assert "concept-a" in ids
        assert "concept-b" in ids

    def test_list_with_bundle_filter(self, tmp_path):
        """list_concepts with bundle_name only returns that bundle's concepts."""
        from okf_tools.service import list_concepts
        from tests.conftest import create_concept_file

        bundle_a = tmp_path / "bundle_a"
        bundle_b = tmp_path / "bundle_b"
        bundle_a.mkdir()
        bundle_b.mkdir()
        (bundle_a / "index.md").write_text("# A\n")
        (bundle_b / "index.md").write_text("# B\n")

        create_concept_file(bundle_a, "from-a", title="From A")
        create_concept_file(bundle_b, "from-b", title="From B")

        bundles = [
            BundleRef(name="a", path=bundle_a, default=True),
            BundleRef(name="b", path=bundle_b),
        ]
        config = OkfConfig(
            bundle_path=bundle_a,
            index_path=Path(".okf/index"),
            embedding_model="test",
            default_top_n=5,
            similarity_threshold=1.0,
            auto_git_add=False,
            bundles=bundles,
        )

        concepts = list_concepts(config, bundle_name="a")
        ids = [c.concept_id for c in concepts]
        assert "from-a" in ids
        assert "from-b" not in ids
