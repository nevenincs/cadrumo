"""Reviewability gates for committed AEAT modelo registry TOML fragments."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

from .....core.directory_scan import scan_directory
from .....core.resources._boundary import bundled_path

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REGISTRY_ROOT = bundled_path("registry", "aeat", "modelos")
_REGISTRY_PACKAGE_ROOT = Path(__file__).parent.parent
_MAX_TOML_LINES = 1_500
_MAX_TOML_LINE_CHARS = 600
_MAX_BASELINE_TOML_LINES = 1_400
_MAX_BASELINE_TOML_LINE_CHARS = 520
#: Ceiling in REVIEWABLE CODE LINES -- blank lines, comments and docstrings
#: excluded. The metric changed from raw length after the raw form started
#: measuring the wrong thing: ``_validate_export_layout_coverage.py`` crossed its
#: ceiling at 1,201 lines of which 394 were code and 807 were the comment and
#: docstring blocks recording WHY each regex is spelled the way it is. Under the
#: raw metric the only ways to go green were to delete that reasoning or to split
#: a cohesive validator to beat a number, and this repository asks for exactly the
#: documentation the gate was punishing. Complexity is what has to stay
#: reviewable, so complexity is what is now counted.
#:
#: 200 is chosen to hold the gate at its current strictness rather than to
#: loosen it: it leaves thirteen modules needing a pinned entry, against the
#: twelve the raw ceiling pinned, so the mapping below stays a short register of
#: known-large validators rather than growing into a register of all fifty-one.
_MAX_NEW_VALIDATOR_MODULE_CODE_LINES = 200
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
_VALIDATOR_MODULE_CODE_LINE_BASELINES = {
    "_validate.py": 210,
    "_validate_dependency_sections.py": 292,
    "_validate_evidence.py": 275,
    "_validate_export_layout_coverage.py": 486,
    "_validate_exports.py": 337,
    "_validate_previous_filing_year_coverage.py": 273,
    "_validate_record_sections.py": 241,
    "_validate_references.py": 210,
    "_validate_relation_periods.py": 397,
    "_validate_relation_sources.py": 275,
    "_validate_revision_sections.py": 290,
    "_validate_surfaces.py": 312,
    "_validate_verification_predicates.py": 297,
}
# The workbook-parity backend used to be ratcheted here. It has since moved
# out of the product package, and its ratchet moved with it. The gate left
# behind pointed at a path that no longer existed, so it raised
# FileNotFoundError on every run rather than measuring anything.


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


def _reviewable_code_lines(path: Path) -> int:
    """Return a module's lines of CODE: no blanks, no comments, no docstrings.

    Docstring spans are taken from the parsed tree rather than by counting quote
    characters, so a triple-quoted string used as a VALUE -- a regex, a message
    template -- still counts as the code it is.
    """
    text = path.read_text(encoding="utf-8")
    documented: set[int] = set()
    for node in ast.walk(ast.parse(text, filename=str(path))):
        if not isinstance(node, ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            continue
        body = node.body
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
            and body[0].end_lineno is not None
        ):
            documented.update(range(body[0].lineno, body[0].end_lineno + 1))
    return sum(
        1
        for number, line in enumerate(text.splitlines(), start=1)
        if line.strip() and not line.strip().startswith("#") and number not in documented
    )


def test_registry_validator_modules_stay_below_complexity_baselines() -> None:
    # BOTH spellings are scanned. A validator promoted out of its underscore-
    # private name keeps every reason it had for being held to a ceiling, but a
    # pattern anchored on the underscore stops matching it, and the module drops
    # out of the gate silently -- worse than an unpinned ceiling, because it is
    # not measured at all rather than measured against a generous number.
    oversize: list[str] = []
    seen: set[str] = set()
    for pattern in ("_validate*.py", "validate*.py"):
        for path in scan_directory(_REGISTRY_PACKAGE_ROOT, pattern=pattern):
            if path.name in seen:
                continue
            seen.add(path.name)
            code_lines = _reviewable_code_lines(path)
            ceiling = _VALIDATOR_MODULE_CODE_LINE_BASELINES.get(path.name, _MAX_NEW_VALIDATOR_MODULE_CODE_LINES)
            if code_lines > ceiling:
                oversize.append(f"{path.name}: {code_lines} code lines exceeds {ceiling}")

    assert oversize == [], (
        "validator module(s) grew past their reviewable-code ceiling: "
        + "; ".join(oversize)
        + ". Shrink the module, or re-pin its entry in "
        "_VALIDATOR_MODULE_CODE_LINE_BASELINES as a reviewed decision. Comments "
        "and docstrings are NOT counted, so recording reasoning never trips this."
    )
