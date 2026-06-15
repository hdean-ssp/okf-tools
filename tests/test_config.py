"""Tests for configuration loading and merging."""

import json
from pathlib import Path

import pytest

from okf_tools.config import get_defaults, load_config, find_bundle_root
from okf_tools.errors import ConfigError


class TestDefaults:
    def test_returns_all_fields(self):
        defaults = get_defaults()
        assert defaults["bundle_path"] == "."
        assert defaults["embedding_model"] == "BAAI/bge-small-en-v1.5"
        assert defaults["default_top_n"] == 5
        assert defaults["similarity_threshold"] == 0.85


class TestFindBundleRoot:
    def test_finds_root(self, tmp_path):
        (tmp_path / ".okf").mkdir()
        (tmp_path / ".okf" / "config.json").write_text("{}")
        nested = tmp_path / "a" / "b"
        nested.mkdir(parents=True)

        result = find_bundle_root(nested)
        assert result == tmp_path

    def test_returns_none_when_missing(self, tmp_path):
        result = find_bundle_root(tmp_path)
        assert result is None


class TestLoadConfig:
    def test_loads_bundle_config(self, tmp_path):
        okf_dir = tmp_path / ".okf"
        okf_dir.mkdir()
        config_data = {"default_top_n": 10}
        (okf_dir / "config.json").write_text(json.dumps(config_data))

        config = load_config(tmp_path)
        assert config.default_top_n == 10
        # Defaults still applied for unset fields
        assert config.embedding_model == "BAAI/bge-small-en-v1.5"

    def test_invalid_json_raises_config_error(self, tmp_path):
        okf_dir = tmp_path / ".okf"
        okf_dir.mkdir()
        (okf_dir / "config.json").write_text("not json {{{")

        with pytest.raises(ConfigError) as exc_info:
            load_config(tmp_path)
        assert "Invalid JSON" in str(exc_info.value)

    def test_defaults_when_no_config(self, tmp_path):
        # No .okf/ directory, no user config — should use pure defaults
        config = load_config(tmp_path)
        assert config.default_top_n == 5
        assert config.auto_git_add is True
