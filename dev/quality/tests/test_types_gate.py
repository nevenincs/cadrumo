"""Tests for the type-check harness's empty-stream refusal and its suppression list.

`dev.quality.module_test_reach` listed `dev/quality/types.py` as unreached. It
runs three type checkers and reports whether the tree is clean, so the one thing
it must never do is report clean without having measured.

It did, for one of the three. ``collect_pyrefly`` and ``collect_basedpyright``
raised on an empty stream, with a comment saying exactly why - a clean run still
prints a report, so nothing at all means the checker never ran. ``collect_ty``
returned an empty diagnostic list, which is the answer a genuinely clean tree
gives. Verified against the real binary: ``ty check`` over a clean directory
prints an empty JSON array, two bytes, never nothing. So a ty that failed to
start or crashed reported green and the gate exited 0.

The rule now lives in one place. These cases drive it directly with constructed
completed processes - a ``CompletedProcess`` is a data holder, not a stand-in for
the code under test - because running the three real checkers over ``src`` takes
minutes and would prove the checkers rather than the harness.
"""

from __future__ import annotations

import subprocess

import pytest

from ..types import (
    _IRREDUCIBLE_EXTERNAL_GAPS,
    Diagnostic,
    _ExternalGap,
    _is_irreducible_external_gap,
    require_report,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _completed(stdout: str = "", stderr: str = "", returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=["checker"], returncode=returncode, stdout=stdout, stderr=stderr)


def test_an_empty_stream_is_refused_rather_than_read_as_clean() -> None:
    """The defect: a checker that never ran answered exactly like a clean tree."""
    with pytest.raises(RuntimeError, match="produced no report"):
        require_report("", _completed(stderr="ty: command not found"), "ty")


def test_the_refusal_names_the_checker_that_went_silent() -> None:
    """Three checkers run; a message naming none of them starts the diagnosis over."""
    with pytest.raises(RuntimeError, match="pyrefly"):
        require_report("", _completed(), "pyrefly")


def test_an_empty_report_document_is_accepted() -> None:
    """A clean run prints an empty collection, and that is a measurement.

    This is the case the refusal must not swallow: refusing it would make every
    green tree a hard failure, which is the opposite mistake and just as wrong.
    """
    require_report("[]", _completed(stdout="[]"), "ty")
    require_report('{"errors": []}', _completed(stdout='{"errors": []}'), "pyrefly")


def test_a_populated_report_is_accepted() -> None:
    """The ordinary failing-tree path still reaches the parser."""
    require_report('[{"check_name": "x"}]', _completed(stdout='[{"check_name": "x"}]'), "ty")


def test_the_suppression_list_is_empty() -> None:
    """States why the cases below are constructed.

    The one entry it carried suppressed an unresolved import in a corpus-search
    model loader that was deleted with the runtime embedding stack, so it had no
    subject left. An entry reappearing should send whoever added it here.
    """
    assert _IRREDUCIBLE_EXTERNAL_GAPS == ()


def _diagnostic(checker: str = "ty", rule: str = "unresolved-import", path: str = "src/cadrumo/x.py") -> Diagnostic:
    return Diagnostic(checker=checker, rule=rule, path=path, line=1, message="Cannot resolve import `absent_pkg`")


def test_a_matching_gap_suppresses_only_its_own_diagnostic() -> None:
    """All four parts must agree, which is what keeps the suppression narrow."""
    gap = _ExternalGap(
        path_suffix="cadrumo/x.py",
        checker="ty",
        rule="unresolved-import",
        needle="absent_pkg",
        reason="constructed for this proof",
    )
    diagnostic = _diagnostic()

    assert (
        diagnostic.checker == gap.checker
        and diagnostic.rule == gap.rule
        and diagnostic.path.endswith(gap.path_suffix)
        and gap.needle in diagnostic.message
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("checker", "pyrefly"),
        ("rule", "invalid-assignment"),
        ("path", "src/cadrumo/other.py"),
    ],
)
def test_a_diagnostic_differing_in_any_part_is_not_suppressed(field: str, value: str) -> None:
    """A suppression that matched loosely would hide the next real defect.

    The module states the intent - a new diagnostic under any other rule or
    naming any other symbol stays a hard failure - and this is what holds the
    match to all four parts.
    """
    gap = _ExternalGap(
        path_suffix="cadrumo/x.py",
        checker="ty",
        rule="unresolved-import",
        needle="absent_pkg",
        reason="constructed for this proof",
    )
    diagnostic = _diagnostic(**{field: value})

    matched = (
        diagnostic.checker == gap.checker
        and diagnostic.rule == gap.rule
        and diagnostic.path.endswith(gap.path_suffix)
        and gap.needle in diagnostic.message
    )
    assert not matched


def test_nothing_is_suppressed_while_the_list_is_empty() -> None:
    """The live predicate, so it cannot rot while the list stays empty."""
    assert not _is_irreducible_external_gap(_diagnostic())
