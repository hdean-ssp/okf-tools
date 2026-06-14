"""Configuration loading, merging, and validation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .errors import ConfigError


DEFAULTS: Dict[str, Any] = {
    "bundle_path": ".",
    "index_path": ".okf/index",
    "embedding_model": "BAAI/bge-small-en-v1.5",
    "default_top_n": 5,
    "similarity_threshold": 1.0,
    "auto_git_add": True,
    "skills_paths": [".kiro/steering/", "~/.config/okf/skills/"],
    "validation_level": "standard",
}


@dataclass
class OkfConfig:
    """Resolved configuration with defaults applied."""

    bundle_path: Path
    index_path: Path
    embedding_model: str
    default_top_n: int
    similarity_threshold: float
    auto_git_add: bool
    skills_paths: List[str] = field(default_factory=list)
    validation_level: str = "standard"


def get_defaults() -> Dict[str, Any]:
    """Return built-in default configuration values."""
    return dict(DEFAULTS)


def find_bundle_root(start_path: Optional[Path] = None) -> Optional[Path]:
    """Walk up directories to find .okf/config.json. Returns None if not found."""
    path = (start_path or Path.cwd()).resolve()
    for directory in [path, *path.parents]:
        if (directory / ".okf" / "config.json").exists():
            return directory
    return None


def load_config(bundle_root: Optional[Path] = None) -> OkfConfig:
    """Load config from bundle → user → defaults. Merge per-field."""
    merged = get_defaults()

    # User-level config
    user_config_path = Path.home() / ".config" / "okf" / "config.json"
    if user_config_path.exists():
        user_data = _read_json(user_config_path)
        merged.update({k: v for k, v in user_data.items() if v is not None})

    # Bundle-level config (overrides user)
    if bundle_root is None:
        bundle_root = find_bundle_root()

    if bundle_root:
        bundle_config_path = bundle_root / ".okf" / "config.json"
        if bundle_config_path.exists():
            bundle_data = _read_json(bundle_config_path)
            merged.update({k: v for k, v in bundle_data.items() if v is not None})
        merged["bundle_path"] = str(bundle_root)

    return OkfConfig(
        bundle_path=Path(merged["bundle_path"]).resolve(),
        index_path=Path(merged["index_path"]),
        embedding_model=merged["embedding_model"],
        default_top_n=int(merged["default_top_n"]),
        similarity_threshold=float(merged["similarity_threshold"]),
        auto_git_add=bool(merged["auto_git_add"]),
        skills_paths=list(merged["skills_paths"]),
        validation_level=merged["validation_level"],
    )


def _read_json(path: Path) -> Dict[str, Any]:
    """Read and parse a JSON config file. Raises ConfigError on failure."""
    try:
        text = path.read_text(encoding="utf-8")
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ConfigError(str(path), f"Invalid JSON: {e}")
    except OSError as e:
        raise ConfigError(str(path), str(e))
