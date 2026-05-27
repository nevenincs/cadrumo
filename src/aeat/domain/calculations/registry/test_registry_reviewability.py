"""Reviewability gates for committed AEAT registry TOML fragments."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from aeat.core.resources import bundled_path

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_REGISTRY_ROOT = bundled_path("registry", "aeat")
_MAX_TOML_LINES = 5_000
_MAX_TOML_LINE_CHARS = 1_200


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
