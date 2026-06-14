"""Bundle-wide OKF compliance checking and linting."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

from .bundle import Concept, is_concept_file, validate_frontmatter, walk_concepts
from .config import OkfConfig
from .graph import extract_links


@dataclass
class LintDiagnostic:
    """A single validation finding."""

    file: str
    rule: str
    severity: str  # "error" or "warning"
    message: str


@dataclass
class LintReport:
    """Aggregated result of bundle validation."""

    diagnostics: List[LintDiagnostic] = field(default_factory=list)
    files_checked: int = 0
    errors: int = 0
    warnings: int = 0


def lint_bundle(
    bundle_root: Path,
    config: OkfConfig,
    path_filter: Optional[str] = None,
    rule_filter: Optional[str] = None,
) -> LintReport:
    """Run all applicable validation rules across the bundle."""
    concepts = walk_concepts(bundle_root)

    # Apply path filter
    if path_filter:
        filter_path = (bundle_root / path_filter).resolve()
        concepts = [
            c for c in concepts
            if c.file_path.resolve().is_relative_to(filter_path)
        ]

    report = LintReport(files_checked=len(concepts))
    level = config.validation_level

    # Run requested checks
    if not rule_filter or rule_filter == "frontmatter":
        for c in concepts:
            report.diagnostics.extend(validate_concept_full(c, level))

    if not rule_filter or rule_filter == "structure":
        report.diagnostics.extend(validate_structure(bundle_root, concepts))

    if not rule_filter or rule_filter == "links":
        report.diagnostics.extend(check_link_integrity(concepts, bundle_root))

    if not rule_filter or rule_filter == "types":
        report.diagnostics.extend(check_type_consistency(concepts))

    # Sort by file path
    report.diagnostics.sort(key=lambda d: (d.file, d.rule))
    report.errors = sum(1 for d in report.diagnostics if d.severity == "error")
    report.warnings = sum(1 for d in report.diagnostics if d.severity == "warning")

    return report


def validate_concept_full(concept: Concept, validation_level: str) -> List[LintDiagnostic]:
    """Validate a single concept against all frontmatter rules at given strictness."""
    diagnostics: List[LintDiagnostic] = []
    rel_path = concept.concept_id + ".md"
    fm = concept.frontmatter

    # Always: type required
    base_errors = validate_frontmatter(fm)
    for err in base_errors:
        severity = "error"
        if validation_level == "relaxed" and "type" not in err:
            severity = "warning"

        rule = _infer_rule(err)
        diagnostics.append(LintDiagnostic(
            file=rel_path, rule=rule, severity=severity, message=err
        ))

    # Strict: require title and description
    if validation_level == "strict":
        if not fm.get("title"):
            diagnostics.append(LintDiagnostic(
                file=rel_path,
                rule="frontmatter/title-required",
                severity="error",
                message="'title' field is required in strict mode",
            ))
        if not fm.get("description"):
            diagnostics.append(LintDiagnostic(
                file=rel_path,
                rule="frontmatter/description-required",
                severity="error",
                message="'description' field is required in strict mode",
            ))

    return diagnostics


def validate_structure(bundle_root: Path, concepts: List[Concept]) -> List[LintDiagnostic]:
    """Check structural conventions around index.md files."""
    diagnostics: List[LintDiagnostic] = []

    # Group concepts by directory
    dirs_with_concepts: Dict[Path, List[Concept]] = {}
    for c in concepts:
        parent = c.file_path.parent
        dirs_with_concepts.setdefault(parent, []).append(c)

    for directory, dir_concepts in dirs_with_concepts.items():
        index_path = directory / "index.md"
        rel_dir = str(directory.relative_to(bundle_root.resolve()))

        if not index_path.exists():
            diagnostics.append(LintDiagnostic(
                file=f"{rel_dir}/index.md",
                rule="structure/missing-index",
                severity="error",
                message=f"Directory '{rel_dir}' contains concepts but has no index.md",
            ))
            continue

        # Parse index.md entries
        content = index_path.read_text(encoding="utf-8")
        index_entries = _parse_index_entries(content)
        actual_files = {c.file_path.name for c in dir_concepts}

        # Check for orphaned entries (in index but not on disk)
        for entry_filename in index_entries:
            if entry_filename not in actual_files and not (directory / entry_filename).exists():
                diagnostics.append(LintDiagnostic(
                    file=f"{rel_dir}/index.md",
                    rule="structure/orphaned-entry",
                    severity="warning",
                    message=f"index.md references '{entry_filename}' which does not exist",
                ))

        # Check for missing entries (on disk but not in index)
        for concept in dir_concepts:
            if concept.file_path.name not in index_entries:
                diagnostics.append(LintDiagnostic(
                    file=concept.concept_id + ".md",
                    rule="structure/missing-entry",
                    severity="warning",
                    message=f"Concept not listed in {rel_dir}/index.md",
                ))

    return diagnostics


def check_link_integrity(concepts: List[Concept], bundle_root: Path) -> List[LintDiagnostic]:
    """Check that all internal markdown links resolve to existing concept files."""
    diagnostics: List[LintDiagnostic] = []
    existing_ids: Set[str] = {c.concept_id for c in concepts}

    for concept in concepts:
        targets = extract_links(concept, bundle_root)
        for target_id in targets:
            if target_id not in existing_ids:
                # Verify the file doesn't exist (it might be index.md or log.md)
                target_path = bundle_root / (target_id + ".md")
                if not target_path.exists():
                    diagnostics.append(LintDiagnostic(
                        file=concept.concept_id + ".md",
                        rule="links/broken-internal",
                        severity="error",
                        message=f"Broken link to '{target_id}' (file does not exist)",
                    ))

    return diagnostics


def check_type_consistency(concepts: List[Concept]) -> List[LintDiagnostic]:
    """Detect near-duplicate type values."""
    diagnostics: List[LintDiagnostic] = []

    # Group by normalized form
    groups: Dict[str, Dict[str, List[str]]] = {}  # normalized -> {original -> [files]}
    for c in concepts:
        type_val = c.frontmatter.get("type", "")
        if not type_val:
            continue
        normalized = _normalize_type(type_val)
        group = groups.setdefault(normalized, {})
        group.setdefault(type_val, []).append(c.concept_id + ".md")

    # Report clusters with multiple variants
    for normalized, variants in groups.items():
        if len(variants) > 1:
            variant_list = ", ".join(f"'{v}'" for v in sorted(variants.keys()))
            # Report on the first file of the least common variant
            for variant, files in sorted(variants.items(), key=lambda x: len(x[1])):
                for file_path in files:
                    diagnostics.append(LintDiagnostic(
                        file=file_path,
                        rule="types/near-duplicate",
                        severity="warning",
                        message=f"Type '{variant}' has near-duplicates: {variant_list}",
                    ))
                break  # Only report on the minority variant's files

    return diagnostics


# --- Helpers ---


def _normalize_type(type_val: str) -> str:
    """Normalize type for comparison: lowercase, remove hyphens and spaces."""
    return re.sub(r"[-\s]", "", type_val.lower())


def _infer_rule(error_msg: str) -> str:
    """Map a validate_frontmatter error message to a rule identifier."""
    if "type" in error_msg:
        return "frontmatter/type-required"
    if "timestamp" in error_msg:
        return "frontmatter/invalid-timestamp"
    if "tags" in error_msg:
        return "frontmatter/invalid-tags"
    return "frontmatter/unknown"


def _parse_index_entries(content: str) -> Set[str]:
    """Extract filenames from index.md link entries."""
    pattern = re.compile(r"\[.*?\]\(\./([^)]+)\)")
    return {match.group(1) for match in pattern.finditer(content)}
