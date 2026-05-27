"""Reviewability gates for committed AEAT registry TOML fragments."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from aeat.core.resources import bundled_path

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_REGISTRY_ROOT = bundled_path("registry", "aeat")
_REGISTRY_PACKAGE_ROOT = Path(__file__).parent
_MAX_TOML_LINES = 5_000
_MAX_TOML_LINE_CHARS = 1_200
_MAX_NEW_VALIDATOR_MODULE_LINES = 300
_VALIDATOR_MODULE_LINE_BASELINES = {
    "_validate.py": 204,
    "_validate_references.py": 312,
    "_validate_revision_sections.py": 252,
    "_validate_semantic_roles.py": 243,
    "_validate_record_sections.py": 238,
    "_validate_revision_identity.py": 228,
    "_validate_relation_periods.py": 198,
    "_validate_semantic_role_axes.py": 188,
    "_validate_dependency_sections.py": 182,
}


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
            )
        )
    return sizes


def test_registry_toml_fragments_stay_reviewable() -> None:
    oversize = [
        size
        for size in _toml_sizes()
        if size.line_count > _MAX_TOML_LINES or size.max_line_chars > _MAX_TOML_LINE_CHARS
    ]

    assert oversize == [], "\n".join(
        f"{size.path}: {size.line_count} lines, longest line {size.max_line_chars} chars"
        for size in oversize[:20]
    )


def test_registry_reviewability_baseline_remains_well_below_hard_cap() -> None:
    sizes = _toml_sizes()
    largest = max(sizes, key=lambda size: size.line_count)
    widest = max(sizes, key=lambda size: size.max_line_chars)

    assert largest.line_count < 3_500, (
        f"largest registry TOML grew beyond review baseline: {largest.path} "
        f"has {largest.line_count} lines"
    )
    assert widest.max_line_chars < 1_000, (
        f"widest registry TOML row grew beyond review baseline: {widest.path} "
        f"has a {widest.max_line_chars}-char line"
    )


def test_registry_validator_modules_stay_below_p05_reviewability_baseline() -> None:
    oversize: list[str] = []
    for path in sorted(_REGISTRY_PACKAGE_ROOT.glob("_validate*.py")):
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        ceiling = _VALIDATOR_MODULE_LINE_BASELINES.get(path.name, _MAX_NEW_VALIDATOR_MODULE_LINES)
        if line_count > ceiling:
            oversize.append(f"{path.name}: {line_count} lines exceeds {ceiling}")

    assert oversize == []
