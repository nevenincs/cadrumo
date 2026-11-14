"""A grounded row held only by the edition's authority grade is ``grade-held``: never green, apart from ``fail``.

The classifier reads the blocking findings of the verify reason the runner wrote; a calculation mismatch, another
blocking finding or an ungrounded row keeps its own verdict, so the verdict cannot hide a real defect.
"""

from __future__ import annotations

import pytest

from ..render import summary_line
from ..rows import GREEN, PlannedRow, Stage, TableRow, Verdict

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_GRADE = "blocking_rule - registry_authority_grade_insufficient"
_EXPORT = "export: modelo.export refused REFUSED_MODELO_REVISION_NOT_SEALED :: not sealed"


def _row(
    reason: str,
    *,
    calculate: Stage = Stage.PASSED,
    verify: Stage = Stage.INCOMPLETE,
    export: Stage = Stage.REFUSED,
    grounding: str = "verified",
) -> TableRow:
    plan = PlannedRow(
        persona="persona",
        modelo="200",
        year=2024,
        period="0A",
        horizon=2025,
        has_values=True,
        grounding=grounding,
        sources=("ley:art-1",),
    )
    return TableRow.from_plan(plan, calculate, verify=verify, export=export, figures=(("0001", "1"),), reason=reason)


def test_a_grounded_row_blocked_only_by_the_authority_grade_is_grade_held_and_never_green() -> None:
    row = _row(f"verify: blocked; 6 findings; blocking: {_GRADE} | {_EXPORT}")

    assert row.verdict is Verdict.GRADE_HELD
    assert row.verdict not in GREEN
    assert "grade-held 1" in summary_line([row])
    assert "fail 0" in summary_line([row])


def test_another_blocking_finding_beside_the_grade_keeps_the_row_fail() -> None:
    row = _row(f"verify: blocked; 7 findings; blocking: {_GRADE}, blocking_rule - source_incomplete | {_EXPORT}")

    assert row.verdict is Verdict.FAIL


def test_a_blocking_finding_other_than_the_grade_is_fail() -> None:
    row = _row(f"verify: blocked; 1 findings; blocking: blocking_rule - source_incomplete | {_EXPORT}")

    assert row.verdict is Verdict.FAIL


def test_a_calculation_mismatch_is_still_fail_whatever_the_verify_reason_says() -> None:
    row = _row(f"verify: blocked; 6 findings; blocking: {_GRADE} | {_EXPORT}", calculate=Stage.MISMATCH)

    assert row.verdict is Verdict.FAIL


def test_a_verify_that_did_not_block_or_an_export_that_ran_is_not_grade_held() -> None:
    reason = f"verify: blocked; 6 findings; blocking: {_GRADE} | {_EXPORT}"

    assert _row(reason, verify=Stage.PASSED, export=Stage.REFUSED).verdict is Verdict.FAIL
    assert _row(reason, export=Stage.MISMATCH).verdict is Verdict.FAIL


def test_a_reason_without_a_blocking_list_is_fail_and_an_ungrounded_row_stays_unverified() -> None:
    assert _row("verify: incomplete").verdict is Verdict.FAIL
    assert _row(f"blocking: {_GRADE}", grounding="unverified").verdict is Verdict.UNVERIFIED
