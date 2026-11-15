"""A return whose check did not pass carries the blocking findings the workbench's issues list showed, and only then.

The ids come from the issues the form holds; the line is read back through the persona table's own parser, and the
grader's export matching consumes them.
"""

from __future__ import annotations

import json

import pytest

from cadrumo.application.modelo.work_form_findings import ModeloFormIssue
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from cadrumo.entrypoints.tui.modelo.workbench.tests.workbench_driver import blocking_finding_ids

from ...persona_table.frontend import GRADE_HELD_FINDING, NOT_REACHED, parity, parse_result
from ...persona_table.rows import PlannedRow, Stage, TableRow
from ..intake import INCOMPLETE, PilotRow

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_ENVELOPE = filing_year_envelope()
_NOT_SEALED = "REFUSED_MODELO_REVISION_NOT_SEALED"
_FIGURES = (("0505", "1200.5"),)
_GRADE_KEY = f"application.modelo.findings.{GRADE_HELD_FINDING}"
_OTHER_KEY = "application.modelo.findings.oss_evidence_missing"


def _issue(key: str, severity: ModeloVerificationFindingSeverity) -> ModeloFormIssue:
    return ModeloFormIssue(
        finding=ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.BLOCKING_RULE
            if severity is ModeloVerificationFindingSeverity.BLOCKING
            else ModeloVerificationFindingKind.ADVISORY,
            severity=severity,
            message_locale_key=key,
            legal_refs=("ley-37-1992:art-99",),
        )
    )


def _blocked(*findings: str) -> PilotRow:
    """A return whose check did not pass and whose form served no export door."""
    return PilotRow(
        persona="p",
        modelo="303",
        year=_ENVELOPE.floor,
        period="1T",
        calculate="pass",
        verify=INCOMPLETE,
        export=NOT_REACHED,
        export_served=False,
        figures=dict(_FIGURES),
        blocking_findings=findings,
    )


def _table_row() -> TableRow:
    plan = PlannedRow(
        persona="p",
        modelo="303",
        year=_ENVELOPE.floor,
        period="1T",
        horizon=_ENVELOPE.horizon,
        has_values=True,
        grounding="verified",
        sources=("ley:art-1",),
    )
    return TableRow.from_plan(
        plan,
        Stage.PASSED,
        verify=Stage.INCOMPLETE,
        export=Stage.REFUSED,
        figures=_FIGURES,
        reason=f"verify: blocked; 1 findings | export: modelo.export refused {_NOT_SEALED} :: not verified",
    )


def test_the_ids_are_the_blocking_findings_each_once_in_the_order_the_issues_show() -> None:
    blocking = ModeloVerificationFindingSeverity.BLOCKING
    warning = ModeloVerificationFindingSeverity.WARNING
    issues = [
        _issue(_GRADE_KEY, blocking),
        _issue(_OTHER_KEY, warning),
        _issue("application.modelo.findings.cross_period_dependency_unclean", blocking),
        _issue(_GRADE_KEY, blocking),
    ]

    assert blocking_finding_ids(issues) == (GRADE_HELD_FINDING, "cross_period_dependency_unclean")
    assert blocking_finding_ids([_issue(_OTHER_KEY, warning)]) == ()
    assert blocking_finding_ids([]) == ()


def test_a_row_with_blocking_findings_writes_them_and_the_grader_reads_them_back() -> None:
    row = _blocked(GRADE_HELD_FINDING, "cross_period_dependency_unclean")

    document = row.document(tree="t", log="")
    result = parse_result(row.line(tree="t", log=""))

    assert document["blocking_findings"] == [GRADE_HELD_FINDING, "cross_period_dependency_unclean"]
    assert result.blocking_findings == (GRADE_HELD_FINDING, "cross_period_dependency_unclean")
    assert row.result().blocking_findings == result.blocking_findings


def test_a_row_without_findings_omits_the_field() -> None:
    row = _blocked()

    assert "blocking_findings" not in row.document(tree="t", log="")
    assert "blocking_findings" not in json.loads(row.line(tree="t", log=""))
    assert row.result().blocking_findings == ()


def test_a_withheld_export_door_blocked_on_the_grade_finding_matches_the_unsealed_refusal() -> None:
    held = parity(_table_row(), "tui", _blocked(GRADE_HELD_FINDING).result())

    assert held.outcome == "matched"
    assert held.causes == ()
    assert held.gated_stages == (f"export unavailable (refused | not served) {_NOT_SEALED}",)


@pytest.mark.parametrize("findings", [(), ("cross_period_dependency_unclean",)])
def test_the_same_row_without_the_grade_finding_still_differs(findings: tuple[str, ...]) -> None:
    other = parity(_table_row(), "tui", _blocked(*findings).result())

    assert (other.outcome, other.gated_stages) == ("differs", ())
    assert "export tui not-reached, table refused" in other.causes
