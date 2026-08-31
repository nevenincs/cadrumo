"""The tautology gate, and the proof that it can actually fire.

The repository sweep below currently returns zero findings, which is exactly
the situation where a gate is worth least and looks worth most: a scan that
matched nothing and a scan that cannot match anything produce identical
output. Every shape the scan claims to catch is therefore driven through it
with a fixture that MUST be reported, and every shape it must NOT catch is
driven through with a fixture that must come back clean. The sweep is the
last test here, not the first, because on its own it proves nothing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dev.quality.tautological_assertion_scan import (
    scan_paths_for_tautological_assertions,
    scan_tautological_assertions,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_ROOT = Path(__file__).resolve().parents[2]

_FIXTURE = Path("fixture.py")


def _reasons(source: str) -> tuple[str, ...]:
    """Scan one source string and return the reason for each finding."""
    return tuple(finding.reason for finding in scan_tautological_assertions(_FIXTURE, source))


@pytest.mark.parametrize(
    ("source", "expected_fragment"),
    [
        ("assert True", "true before any operand is read"),
        ("assert 1", "true before any operand is read"),
        ("assert 'text'", "true before any operand is read"),
        ("assert (left, right)", "true before any operand is read"),
        ("assert [candidate]", "true before any operand is read"),
        ("assert False", "can never pass"),
        ("assert 0", "can never pass"),
        ("assert []", "can never pass"),
        ("assert value or True", "cannot change the verdict"),
        ("assert value or 1", "cannot change the verdict"),
        ("assert value == value", "can never fail"),
        ("assert payload.total == payload.total", "can never fail"),
        ("assert value is value", "can never fail"),
        ("assert value >= value", "can never fail"),
        ("assert value != value", "can never pass"),
        ("assert value < value", "can never pass"),
        ("assert isinstance(value, object)", "holds for every value in the language"),
    ],
)
def test_the_scan_reports_each_shape_it_claims_to_catch(source: str, expected_fragment: str) -> None:
    """Every advertised shape produces a finding naming why it is decided."""
    reasons = _reasons(source)
    assert len(reasons) == 1, f"{source!r} produced {len(reasons)} findings, expected exactly one"
    assert expected_fragment in reasons[0], f"{source!r} was reported as: {reasons[0]}"


@pytest.mark.parametrize(
    "source",
    [
        "assert value",
        "assert value == other",
        "assert value or other",
        "assert value and True",
        "assert isinstance(value, int)",
        "assert not value",
        "assert value in collection",
        "assert len(value) == expected",
    ],
)
def test_the_scan_leaves_assertions_that_depend_on_their_operands(source: str) -> None:
    """An assertion whose verdict needs the operand is not this gate's business."""
    assert _reasons(source) == (), f"{source!r} was wrongly reported as tautological"


def test_two_calls_that_merely_look_identical_are_not_reflexive() -> None:
    """``next(it) == next(it)`` is two evaluations, not one operand twice.

    The single most likely false positive: comparing by unparsed source makes
    textually identical sides look reflexive, and for a call they are not --
    the two sides can legitimately differ. Flagging this would fire the gate
    on code doing real work, which is how a gate gets disabled.
    """
    assert _reasons("assert next(stream) == next(stream)") == ()
    assert _reasons("assert compute(x) != compute(x)") == ()


def test_a_finding_renders_as_an_openable_locator() -> None:
    """The report names the file and line, so a reader can go straight there."""
    findings = scan_tautological_assertions(_FIXTURE, "value = 1\nassert value or True\n")
    assert len(findings) == 1
    rendered = str(findings[0])
    assert rendered.startswith("fixture.py:2 "), rendered


def test_an_unparseable_module_is_skipped_rather_than_crashing_the_sweep() -> None:
    """A file being rewritten by another lane must not abort the whole scan.

    The tree is edited concurrently, so a sweep that raises on the first
    syntactically incomplete file reports nothing about the thousands that
    parsed -- a failure indistinguishable from a clean run.
    """
    assert scan_tautological_assertions(_FIXTURE, "def broken(:\n") == ()


def test_no_tautological_assertion_survives_in_the_repository() -> None:
    """The sweep itself. Meaningful only because the teeth above pass."""
    paths = tuple(path for root in ("src/cadrumo", "dev") for path in (_ROOT / root).rglob("*.py"))
    assert paths, "the sweep matched no modules at all, so it measured nothing"
    findings = scan_paths_for_tautological_assertions(paths)
    assert not findings, "assertions decided without their operands:\n" + "\n".join(
        f"  {finding}" for finding in findings
    )
