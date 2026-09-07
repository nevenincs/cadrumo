"""Gate exact membership disjunctions whose broad needle subsumes a sibling."""

from __future__ import annotations

import locale
import tomllib
from pathlib import Path

import pytest

from ..._paths import REPO_ROOT
from ..subsuming_disjunctions import (
    scan_paths_for_subsuming_disjunctions,
    scan_subsuming_disjunctions,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_FIXTURE = Path("fixture.py")
_TEST_ROOTS = (REPO_ROOT / "src" / "cadrumo", REPO_ROOT / "dev")
_CASES = tomllib.loads(
    (Path(__file__).parent / "fixtures" / "subsuming_disjunction_cases.toml").read_text(encoding="utf-8")
)


def _case(name: str) -> str:
    """Return one named, non-collected Python specimen."""
    source = _CASES[name]["source"]
    assert isinstance(source, str)
    return source


def _test_modules() -> tuple[Path, ...]:
    """Return every test module, refusing either declared root collapsing."""
    by_root = {root: tuple(root.rglob("test_*.py")) for root in _TEST_ROOTS}
    starved = {root: len(paths) for root, paths in by_root.items() if len(paths) < 500}
    assert not starved, (
        "the subsuming-disjunction sweep reached fewer than 500 test modules in "
        f"a declared root; modules found per starved root: {starved}"
    )
    return tuple(path for paths in by_root.values() for path in paths)


def test_the_detector_catches_the_residual_rows_subsumption() -> None:
    """Positive control: reproduce the residual assertion that founded the gate."""
    findings = scan_subsuming_disjunctions(
        _FIXTURE,
        _case("residual_rows"),
    )

    assert len(findings) == 1, f"the planted rows subsumption produced {findings!r}"
    finding = findings[0]
    assert finding.broad_needle == "rows"
    assert finding.specific_needle == '"rows"'
    assert finding.haystack == "output"
    assert finding.path == _FIXTURE
    assert finding.lineno == 1


def test_path_sweep_reads_real_utf8_bytes_and_preserves_attribution(
    tmp_path: Path,
) -> None:
    """The real filesystem adapter owns UTF-8 decoding and source attribution."""
    fixture = tmp_path / "utf8_fixture.py"
    fixture.write_bytes(_case("utf8_accented").encode())
    previous_locale = locale.setlocale(locale.LC_CTYPE)
    try:
        locale.setlocale(locale.LC_CTYPE, "C")
        findings = scan_paths_for_subsuming_disjunctions((fixture,))
    finally:
        locale.setlocale(locale.LC_CTYPE, previous_locale)

    assert len(findings) == 1
    finding = findings[0]
    assert (finding.broad_needle, finding.specific_needle, finding.path, finding.lineno) == (
        "é",
        "café",
        fixture,
        1,
    )


@pytest.mark.parametrize(
    "case_name",
    [
        "preceding_conjunction",
        "preceding_unsupported_operand",
        "preceding_different_haystacks",
        "effectful_repeated_haystack",
    ],
)
def test_an_unrelated_earlier_assertion_does_not_end_the_sweep(case_name: str) -> None:
    """A rejected candidate cannot hide a later decidable instance."""
    source = _case(case_name) + _case("residual_rows")

    findings = scan_subsuming_disjunctions(_FIXTURE, source)

    assert len(findings) == 1
    assert findings[0].lineno == 2


@pytest.mark.parametrize(
    "case_name",
    [
        "distinct_needles",
        "different_haystacks",
        "effectful_repeated_haystack",
        "attribute_haystack",
        "unsupported_operand",
        "conjunction",
        "dynamic_needle",
    ],
)
def test_legitimate_or_mismatched_shapes_are_left_alone(case_name: str) -> None:
    """Only all-literal memberships on one haystack establish subsumption."""
    findings = scan_subsuming_disjunctions(_FIXTURE, _case(case_name))

    assert findings == (), f"the detector exceeded its closed AST claim: {findings!r}"


def test_no_subsuming_membership_disjunction_survives_in_the_real_tree() -> None:
    """Sweep every test module under both declared roots."""
    findings = scan_paths_for_subsuming_disjunctions(_test_modules())

    assert not findings, "broad membership operands subsume sibling claims:\n" + "\n".join(
        f"  {finding}" for finding in findings
    )
