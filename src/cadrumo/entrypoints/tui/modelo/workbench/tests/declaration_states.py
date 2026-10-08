"""Put the synthetic declaration in the states the header and the journey must read.

A result in each direction the read model states, a deadline in each band, the
last check's findings on each attention level, and a declaration recorded as
filed: each built from the shared fixture by updating the read model's own
fields, so every state is one the application could hand the workbench.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from ......application.modelo.work_form_models import (
    ModeloFormDeadline,
    ModeloFormEditClosure,
    ModeloFormFiling,
    ModeloFormIssue,
    ModeloFormResult,
    ModeloFormResultDirection,
    ModeloWorkForm,
)
from ......core.result_disposition import ResultDisposition
from ......domain.deadlines.festivos import DeadlineHolidayCoverage
from ......domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationCompletenessStatus,
)

REFERENCE_DAY = date(2026, 4, 8)
"""The day the synthetic deadlines are counted from."""
RECORDED_AT = datetime(2026, 4, 15, 10, 0, tzinfo=UTC)
"""When the synthetic declaration is recorded as filed."""

_MESSAGE_KEY = "application.modelo.findings.oss_evidence_missing"
_LEGAL_REF = "ley-37-1992:art-99"


def with_result(
    form: ModeloWorkForm,
    direction: ModeloFormResultDirection,
    value: Decimal | None,
    *,
    disposition: ResultDisposition | None = None,
    election: bool = False,
    casilla_id: str = "19",
) -> ModeloWorkForm:
    """The form with a settlement box, its value and the direction the read model states."""
    result = ModeloFormResult(
        casilla_id=casilla_id,
        box=casilla_id,
        value=value,
        direction=direction,
        disposition=disposition,
        election_may_change=election,
    )
    return form.model_copy(update={"result": result})


def with_deadline(
    form: ModeloWorkForm,
    *,
    days_left: int | None = None,
    days_late: int | None = None,
    shifted_by: int = 0,
) -> ModeloWorkForm:
    """The form with a filing window closing ``days_left`` days after, or ``days_late`` days before, the reference."""
    if days_left is not None:
        closes = REFERENCE_DAY + timedelta(days=days_left)
    else:
        closes = REFERENCE_DAY - timedelta(days=days_late or 1)
    deadline = ModeloFormDeadline(
        closes_on=closes,
        nominal_closes_on=closes - timedelta(days=shifted_by),
        holiday_coverage=DeadlineHolidayCoverage.NATIONAL_AND_TERRITORY,
        reference_on=REFERENCE_DAY,
        days_remaining=days_left,
        days_overdue=None if days_left is not None else days_late or 1,
    )
    return form.model_copy(update={"deadline": deadline})


def _finding(severity: ModeloVerificationFindingSeverity, casilla_id: str | None) -> ModeloVerificationFinding:
    kind = (
        ModeloVerificationFindingKind.BLOCKING_RULE
        if severity is ModeloVerificationFindingSeverity.BLOCKING
        else ModeloVerificationFindingKind.RECONCILIATION_MISMATCH
    )
    return ModeloVerificationFinding(
        kind=kind,
        severity=severity,
        casilla_id=casilla_id,
        message_locale_key=_MESSAGE_KEY,
        legal_refs=(_LEGAL_REF,),
    )


def with_findings(
    form: ModeloWorkForm, *, blocking: tuple[str | None, ...] = (), worth_checking: tuple[str | None, ...] = ()
) -> ModeloWorkForm:
    """The form checked, with blocking findings and findings worth checking on the named boxes or on none."""
    issues = (
        *(
            ModeloFormIssue(finding=_finding(ModeloVerificationFindingSeverity.BLOCKING, box), box=box)
            for box in blocking
        ),
        *(
            ModeloFormIssue(finding=_finding(ModeloVerificationFindingSeverity.WARNING, box), box=box)
            for box in worth_checking
        ),
    )
    verdict = VerificationCompletenessStatus.BLOCKED if blocking else VerificationCompletenessStatus.COMPLETE
    return form.model_copy(update={"issues": issues, "verification": verdict})


def recorded_as_filed(form: ModeloWorkForm) -> ModeloWorkForm:
    """The form of a declaration recorded as filed: closed to editing, with when it was recorded."""
    return form.model_copy(
        update={
            "filing": ModeloFormFiling(recorded_at=RECORDED_AT),
            "edit_admitted": False,
            "edit_closure": ModeloFormEditClosure.RECORDED_AS_FILED,
        }
    )


__all__ = [
    "RECORDED_AT",
    "REFERENCE_DAY",
    "recorded_as_filed",
    "with_deadline",
    "with_findings",
    "with_result",
]
