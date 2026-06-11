"""Reviewability gates for committed AEAT modelo registry TOML fragments."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from .....core.resources import bundled_path

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REGISTRY_ROOT = bundled_path("registry", "aeat", "modelos")
_REGISTRY_PACKAGE_ROOT = Path(__file__).parent.parent
_MAX_TOML_LINES = 1_500
_MAX_TOML_LINE_CHARS = 600
_MAX_BASELINE_TOML_LINES = 1_100
_MAX_BASELINE_TOML_LINE_CHARS = 520
_MAX_NEW_VALIDATOR_MODULE_LINES = 300
_VALIDATOR_MODULE_LINE_BASELINES = {
    "_validate_cross_revision.py": 424,
    "_validate_references.py": 312,
    "_validate_revision_sections.py": 299,
    "_validate_semantic_roles.py": 243,
    "_validate_record_sections.py": 240,
    "_validate_revision_identity.py": 228,
    "_validate.py": 210,
    "_validate_relation_periods.py": 209,
    "_validate_semantic_role_axes.py": 188,
    "_validate_dependency_sections.py": 182,
}
_WORKBOOK_PARITY_MODULE_LINE_BASELINE = 1_336


@dataclass(frozen=True)
class _TomlSize:
    path: Path
    line_count: int
    max_line_chars: int


def _toml_sizes() -> list[_TomlSize]:
    sizes: list[_TomlSize] = []
    for path in sorted(_REGISTRY_ROOT.rglob("*.toml")):
        lines = path.read_text(encoding="utf-8").splitlines()
        sizes.append(
            _TomlSize(
                path=path.relative_to(_REGISTRY_ROOT),
                line_count=len(lines),
                max_line_chars=max((len(line) for line in lines), default=0),
            ),
        )
    return sizes


def test_registry_toml_fragments_stay_reviewable() -> None:
    oversize = [
        size
        for size in _toml_sizes()
        if size.line_count > _MAX_TOML_LINES or size.max_line_chars > _MAX_TOML_LINE_CHARS
    ]

    assert oversize == [], "\n".join(
        f"{size.path}: {size.line_count} lines, longest line {size.max_line_chars} chars" for size in oversize[:20]
    )


def test_registry_reviewability_baseline_remains_well_below_hard_cap() -> None:
    sizes = _toml_sizes()
    largest = max(sizes, key=lambda size: size.line_count)
    widest = max(sizes, key=lambda size: size.max_line_chars)

    assert largest.line_count < _MAX_BASELINE_TOML_LINES, (
        f"largest registry TOML grew beyond review baseline: {largest.path} has {largest.line_count} lines"
    )
    assert widest.max_line_chars < _MAX_BASELINE_TOML_LINE_CHARS, (
        f"widest registry TOML row grew beyond review baseline: {widest.path} has a {widest.max_line_chars}-char line"
    )


def test_registry_validator_modules_stay_below_complexity_baselines() -> None:
    oversize: list[str] = []
    for path in sorted(_REGISTRY_PACKAGE_ROOT.glob("_validate*.py")):
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        ceiling = _VALIDATOR_MODULE_LINE_BASELINES.get(path.name, _MAX_NEW_VALIDATOR_MODULE_LINES)
        if line_count > ceiling:
            oversize.append(f"{path.name}: {line_count} lines exceeds {ceiling}")

    assert oversize == []


def test_registry_workbook_parity_module_does_not_grow_past_reviewed_baseline() -> None:
    path = _REGISTRY_PACKAGE_ROOT / "_workbook_parity.py"
    line_count = len(path.read_text(encoding="utf-8").splitlines())

    assert line_count <= _WORKBOOK_PARITY_MODULE_LINE_BASELINE, (
        f"{path.name}: {line_count} lines exceeds reviewed baseline {_WORKBOOK_PARITY_MODULE_LINE_BASELINE}"
    )
