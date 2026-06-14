"""Skill pack discovery and listing."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import frontmatter


@dataclass
class SkillPack:
    """A discovered skill pack."""

    filename: str
    title: str
    description: str
    file_path: Path


def discover_skills(skills_paths: List[str], bundled_skill_path: Path) -> List[SkillPack]:
    """Scan all configured paths + bundled skill. Return discovered skills."""
    skills: List[SkillPack] = []
    seen_filenames: set = set()

    # Always include the bundled core skill
    if bundled_skill_path.exists():
        skill = parse_skill_metadata(bundled_skill_path)
        if skill:
            skills.append(skill)
            seen_filenames.add(skill.filename)

    # Scan configured paths
    for path_str in skills_paths:
        path = Path(path_str).expanduser()
        if not path.is_dir():
            continue
        for md_file in sorted(path.glob("*.md")):
            if md_file.name in seen_filenames:
                continue
            skill = parse_skill_metadata(md_file)
            if skill:
                skills.append(skill)
                seen_filenames.add(skill.filename)

    return skills


def parse_skill_metadata(file_path: Path) -> Optional[SkillPack]:
    """Extract title/description from a skill .md file. Returns None if no frontmatter."""
    try:
        post = frontmatter.load(str(file_path))
    except Exception:
        return None

    if not post.metadata:
        return None

    # Resolve title: frontmatter → first heading → filename stem
    title = post.metadata.get("title")
    if not title:
        heading_match = re.search(r"^#\s+(.+)$", post.content, re.MULTILINE)
        title = heading_match.group(1) if heading_match else file_path.stem

    description = post.metadata.get("description", "")

    return SkillPack(
        filename=file_path.name,
        title=title,
        description=description,
        file_path=file_path,
    )
