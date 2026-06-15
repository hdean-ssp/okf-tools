"""Shared pytest fixtures for okf-tools tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from okf_tools.config import OkfConfig


@pytest.fixture
def tmp_bundle(tmp_path: Path) -> Path:
    """Create a minimal OKF bundle in a temp directory."""
    # Create .okf/config.json
    okf_dir = tmp_path / ".okf"
    okf_dir.mkdir()
    config = {
        "bundle_path": ".",
        "index_path": ".okf/index",
        "embedding_model": "BAAI/bge-small-en-v1.5",
        "default_top_n": 5,
        "similarity_threshold": 0.85,
        "auto_git_add": False,
    }
    (okf_dir / "config.json").write_text(json.dumps(config), encoding="utf-8")

    # Create root index.md
    (tmp_path / "index.md").write_text("# Test Bundle\n", encoding="utf-8")

    return tmp_path


@pytest.fixture
def sample_config(tmp_bundle: Path) -> OkfConfig:
    """Return an OkfConfig pointing to the tmp_bundle."""
    return OkfConfig(
        bundle_path=tmp_bundle,
        index_path=Path(".okf/index"),
        embedding_model="BAAI/bge-small-en-v1.5",
        default_top_n=5,
        similarity_threshold=0.85,
        auto_git_add=False,
    )


def create_concept_file(
    bundle_root: Path,
    concept_id: str,
    type_val: str = "Pattern",
    title: str = "Test Concept",
    body: str = "Some content here.",
    tags: list = None,
    extra_fm: dict = None,
) -> Path:
    """Helper to create a concept .md file in the bundle."""
    file_path = bundle_root / (concept_id + ".md")
    file_path.parent.mkdir(parents=True, exist_ok=True)

    fm_lines = [f"type: {type_val}", f"title: {title}"]
    if tags:
        fm_lines.append(f"tags: {json.dumps(tags)}")
    if extra_fm:
        for k, v in extra_fm.items():
            fm_lines.append(f"{k}: {v}")

    content = "---\n" + "\n".join(fm_lines) + "\n---\n\n" + body + "\n"
    file_path.write_text(content, encoding="utf-8")
    return file_path
