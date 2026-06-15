"""Configuration loading, merging, and validation.

Supports both legacy single-bundle configs and multi-bundle configs.
Multi-bundle allows a user to have personal + shared team bundles,
all searchable and writable by default.
"""

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
class BundleRef:
    """Reference to a single OKF bundle."""

    name: str
    path: Path
    writable: bool = True
    default: bool = False

    @property
    def index_db_path(self) -> Path:
        """Path to this bundle's sidecar index database."""
        return self.path / ".okf" / "index" / "okf.db"


@dataclass
class OkfConfig:
    """Resolved configuration with defaults applied.

    Supports multi-bundle operation. The legacy ``bundle_path`` field is
    preserved for backward compatibility — it points to the default bundle
    (or the first bundle when multiple are configured).
    """

    bundle_path: Path
    index_path: Path
    embedding_model: str
    default_top_n: int
    similarity_threshold: float
    auto_git_add: bool
    skills_paths: List[str] = field(default_factory=list)
    validation_level: str = "standard"
    bundles: List[BundleRef] = field(default_factory=list)

    # --- Multi-bundle helpers ---

    def get_bundle(self, name: str) -> Optional[BundleRef]:
        """Look up a bundle by name. Returns None if not found."""
        for b in self.bundles:
            if b.name == name:
                return b
        return None

    def get_default_bundle(self) -> Optional[BundleRef]:
        """Return the bundle marked as default, or the first bundle if none marked."""
        for b in self.bundles:
            if b.default:
                return b
        return self.bundles[0] if self.bundles else None

    def get_writable_bundle(self, name: Optional[str] = None) -> BundleRef:
        """Resolve the write-target bundle.

        If *name* is given, look it up and verify it's writable.
        Otherwise use the default bundle.
        Raises ConfigError if not found or not writable.
        """
        if name:
            bundle = self.get_bundle(name)
            if bundle is None:
                raise ConfigError(
                    "bundles",
                    f"Bundle '{name}' not found. "
                    f"Available: {', '.join(b.name for b in self.bundles)}",
                )
            if not bundle.writable:
                raise ConfigError(
                    "bundles",
                    f"Bundle '{name}' is read-only (writable: false)",
                )
            return bundle

        default = self.get_default_bundle()
        if default is None:
            raise ConfigError(
                "bundles",
                "No bundles configured. Run `okf init` or add bundles to "
                "~/.config/okf/config.json",
            )
        if not default.writable:
            raise ConfigError(
                "bundles",
                f"Default bundle '{default.name}' is read-only (writable: false)",
            )
        return default


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


def _resolve_path(path_str: str) -> Path:
    """Resolve a path string, expanding ~ to home directory."""
    return Path(path_str).expanduser().resolve()


def _parse_bundles(raw_bundles: List[Dict[str, Any]]) -> List[BundleRef]:
    """Parse a bundles array from config JSON into BundleRef objects."""
    bundles = []
    for entry in raw_bundles:
        if not isinstance(entry, dict) or "name" not in entry or "path" not in entry:
            continue
        bundles.append(BundleRef(
            name=entry["name"],
            path=_resolve_path(entry["path"]),
            writable=entry.get("writable", True),
            default=entry.get("default", False),
        ))
    return bundles


def load_config(bundle_root: Optional[Path] = None) -> OkfConfig:
    """Load config from bundle → user → defaults. Merge per-field.

    Multi-bundle resolution:
    1. Collect bundles from user-level config (~/.config/okf/config.json)
    2. Collect bundles from project-level config (.okf/config.json in cwd ancestors)
    3. Project-level bundles are prepended (higher priority for default resolution)
    4. If no bundles array exists anywhere, synthesise one from the legacy bundle_path

    The legacy ``bundle_path`` field on OkfConfig always points to the default
    bundle's path for backward compatibility with code that uses it directly.
    """
    merged = get_defaults()
    all_bundles: List[BundleRef] = []

    # User-level config
    user_config_path = Path.home() / ".config" / "okf" / "config.json"
    user_bundles: List[BundleRef] = []
    if user_config_path.exists():
        user_data = _read_json(user_config_path)
        # Extract bundles before merging scalar fields
        if "bundles" in user_data:
            user_bundles = _parse_bundles(user_data.pop("bundles"))
        merged.update({k: v for k, v in user_data.items() if v is not None})

    # Bundle-level (project) config — overrides user for scalar fields
    if bundle_root is None:
        bundle_root = find_bundle_root()

    project_bundles: List[BundleRef] = []
    if bundle_root:
        bundle_config_path = bundle_root / ".okf" / "config.json"
        if bundle_config_path.exists():
            bundle_data = _read_json(bundle_config_path)
            if "bundles" in bundle_data:
                project_bundles = _parse_bundles(bundle_data.pop("bundles"))
            merged.update({k: v for k, v in bundle_data.items() if v is not None})
        merged["bundle_path"] = str(bundle_root)

    # Merge bundles: project-level first, then user-level (deduplicate by name)
    seen_names: set = set()
    for b in project_bundles:
        if b.name not in seen_names:
            all_bundles.append(b)
            seen_names.add(b.name)
    for b in user_bundles:
        if b.name not in seen_names:
            all_bundles.append(b)
            seen_names.add(b.name)

    # Backward compatibility: if no bundles array found anywhere,
    # synthesise a single-bundle list from the legacy bundle_path
    if not all_bundles:
        legacy_path = Path(merged["bundle_path"]).expanduser().resolve()
        all_bundles.append(BundleRef(
            name=legacy_path.name or "default",
            path=legacy_path,
            writable=True,
            default=True,
        ))

    # Resolve bundle_path to point to the default bundle
    default_bundle = next((b for b in all_bundles if b.default), None)
    if default_bundle is None and all_bundles:
        default_bundle = all_bundles[0]
    resolved_bundle_path = default_bundle.path if default_bundle else Path(merged["bundle_path"]).resolve()

    return OkfConfig(
        bundle_path=resolved_bundle_path,
        index_path=Path(merged["index_path"]),
        embedding_model=merged["embedding_model"],
        default_top_n=int(merged["default_top_n"]),
        similarity_threshold=float(merged["similarity_threshold"]),
        auto_git_add=bool(merged["auto_git_add"]),
        skills_paths=list(merged["skills_paths"]),
        validation_level=merged["validation_level"],
        bundles=all_bundles,
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
