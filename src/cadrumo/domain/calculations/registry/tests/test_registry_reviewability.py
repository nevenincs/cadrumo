"""Reviewability gates for committed AEAT modelo registry TOML fragments."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from .....core import scan_directory
from .....core.resources import bundled_path

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REGISTRY_ROOT = bundled_path("registry", "aeat", "modelos")
_REGISTRY_PACKAGE_ROOT = Path(__file__).parent.parent
_MAX_TOML_LINES = 1_500
_MAX_TOML_LINE_CHARS = 600
_MAX_BASELINE_TOML_LINES = 1_400
_MAX_BASELINE_TOML_LINE_CHARS = 520
_MAX_NEW_VALIDATOR_MODULE_LINES = 300
# Per-module ceilings for the validators that already exceed the default above.
# A module earns an entry here only by crossing that default; everything else
# is held to it, so this mapping stays a list of known-large modules rather
# than a register of every validator.
#
# Each entry is pinned to the module's exact current length, because slack is
# this gate's failure mode. A ceiling sitting above actual is silent permission
# to grow into the gap, and the gap is invisible from the outside -- the gate
# goes on reporting "reviewable" about a budget nothing is defending. Pinning
# makes any addition red, which is the entire mechanism: growth becomes a
# decision rather than a default.
#
# The incentive runs against that by construction, since raising a number is a
# one-line edit while shrinking a validator is real work. So a raise is a
# reviewed decision, and its reasoning belongs in the commit that makes it --
# not accumulated here, where it becomes a changelog nobody reads and every
# future reader has to scroll past.
#
# Slack cuts the other way and is just as real: a module that shrinks and
# leaves its old ceiling standing hands back budget nobody is defending.
# Re-pin on the way DOWN too, not only on the way up.
_VALIDATOR_MODULE_LINE_BASELINES = {
    "_validate.py": 307,
    "_validate_cross_revision.py": 326,
    "_validate_dependency_sections.py": 382,
    "_validate_evidence.py": 415,
    "_validate_export_exemption.py": 383,
    "_validate_export_layout_coverage.py": 1063,
    "_validate_exports.py": 536,
    "_validate_previous_filing_year_coverage.py": 421,
    "_validate_record_sections.py": 324,
    "_validate_relation_periods.py": 589,
    "_validate_relation_sources.py": 422,
    "_validate_revision_sections.py": 323,
    "_validate_surfaces.py": 353,
    "_validate_verification_predicates.py": 335,
}
# The workbook-parity backend used to be ratcheted here. It now lives at
# dev/registry/parity/_workbook_parity.py, and its ratchet moved with it to
# dev/registry/tests/test_dev_module_reviewability.py. The gate left behind
# pointed at a path that no longer existed, so it raised FileNotFoundError
# on every run rather than measuring anything.


@dataclass(frozen=True)
class _TomlSize:
    path: Path
    line_count: int
    max_line_chars: int


def _toml_sizes() -> list[_TomlSize]:
    sizes: list[_TomlSize] = []
    for path in scan_directory(_REGISTRY_ROOT, pattern="*.toml", recursive=True):
        lines = path.read_text(encoding="utf-8").splitlines()
        sizes.append(
            _TomlSize(
                path=path.relative_to(_REGISTRY_ROOT),
                line_count=len(lines),
                max_line_chars=max((len(line) for line in lines), default=0),
            ),
        )
    return sizes


def _max_toml_lines(size: _TomlSize) -> int:
    return _MAX_TOML_LINES


def test_registry_toml_fragments_stay_reviewable() -> None:
    oversize = [
        size
        for size in _toml_sizes()
        if size.line_count > _max_toml_lines(size) or size.max_line_chars > _MAX_TOML_LINE_CHARS
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
    for path in scan_directory(_REGISTRY_PACKAGE_ROOT, pattern="_validate*.py"):
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        ceiling = _VALIDATOR_MODULE_LINE_BASELINES.get(path.name, _MAX_NEW_VALIDATOR_MODULE_LINES)
        if line_count > ceiling:
            oversize.append(f"{path.name}: {line_count} lines exceeds {ceiling}")

    assert oversize == []


