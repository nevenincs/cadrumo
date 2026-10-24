"""The form names one next action, in the order the application's gates decide, and halts only on rules it cannot use.

Every form is a Modelo 210 built by the real builder over the published
registry; a row of the state table then states the one lifecycle fact it is
about. The file for the AEAT and recording the filing are offered only where
the export and filing gates would admit them: a verified calculation with
nothing that blocks filing, whichever calculation note the gates refuse on.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.modelos.calculation_revision import CalculationRevisionState
from ....domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationCompletenessStatus,
)
from ..calculation_notes import (
    CALCULATION_NOTE_ATTENTION,
    CHECK_REFUSED_REASONS,
    EXPORT_REFUSED_REASONS,
    GATE_REFUSED_REASONS,
)
from ..edit_admission import RESPONSIBLE_OWNER
from ..edit_models import ModeloEditDomainRefusalV1, ModeloEditRefusalCode, ModeloEditRefusedV1
from ..work_form_models import ModeloFormAttention, ModeloFormCalculationNote, ModeloFormExport, ModeloWorkForm
from ..work_form_next_step import (
    ModeloFormNextAction,
    ModeloFormNextStep,
    blocking_count,
    form_next_step,
    held_prerequisite_step,
    missing_count,
    registry_grade_refusal,
)
from .work_form_fixture import built_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_INCOME = "rendimientos_integros"
_KIND = "tipo_renta"
_HELD: dict[str, Decimal | str] = {_INCOME: Decimal("1200.00"), _KIND: "01"}
_CALCULATION = "c" * 64
_EXPORTED_AT = datetime(2026, 4, 2, tzinfo=UTC)
_FILE_ACTIONS = frozenset(
    {ModeloFormNextAction.EXPORT, ModeloFormNextAction.EXPORT_AGAIN, ModeloFormNextAction.RECORD_AFTER_FILE}
)


def _empty(operation: PinnedAuthorityOperation) -> ModeloWorkForm:
    """Nothing calculated and the required income box still to fill in."""
    return built_form(operation, "210", 2025, "0A", entered=frozenset())


def _entered(operation: PinnedAuthorityOperation) -> ModeloWorkForm:
    """The income and its kind entered by the filer, so nothing is missing or assumed."""
    return built_form(operation, "210", 2025, "0A", held=_HELD, entered=frozenset(_HELD))


def _calculated(form: ModeloWorkForm, **update: object) -> ModeloWorkForm:
    return form.model_copy(update={"calculation_revision_id": _CALCULATION, **update})


def _export(*, current: bool) -> ModeloFormExport:
    return ModeloFormExport(exported_at=_EXPORTED_AT, calculation_revision_id=_CALCULATION, current=current)


def _note(reason: str) -> ModeloFormCalculationNote:
    return ModeloFormCalculationNote(reason=reason, attention=CALCULATION_NOTE_ATTENTION[reason])


def _stale() -> ModeloVerificationFinding:
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.STALE_CALCULATION,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        message_locale_key="application.modelo.findings.ledger_snapshot_drift",
        legal_refs=("ley-58-2003:art-119",),
    )


def test_each_state_offers_the_one_action_its_facts_call_for(operation: PinnedAuthorityOperation) -> None:
    empty = _empty(operation)
    entered = _entered(operation)
    assumed = built_form(operation, "210", 2025, "0A", held=_HELD, entered=frozenset({_KIND}))
    verified = _calculated(entered, verification=VerificationCompletenessStatus.COMPLETE)
    stale = _calculated(built_form(operation, "210", 2025, "0A", entered=frozenset(), findings=(_stale(),)))
    filed = built_form(operation, "210", 2025, "0A", entered=frozenset(), lifecycle=CalculationRevisionState.PRESENTADO)
    check_note = sorted(CHECK_REFUSED_REASONS)[0]

    table = [
        (empty, False, False, ModeloFormNextAction.FILL, missing_count(empty)),
        (assumed, False, False, ModeloFormNextAction.CONFIRM, 1),
        (entered, False, False, ModeloFormNextAction.CALCULATE, 0),
        (stale, False, False, ModeloFormNextAction.RECALCULATE, 0),
        (_calculated(entered), False, False, ModeloFormNextAction.VERIFY, 0),
        # A note only the check can decide sends an unchecked calculation to the check, not to "resolve".
        (_calculated(entered, calculation_notes=(_note(check_note),)), False, False, ModeloFormNextAction.VERIFY, 0),
        (verified, True, False, ModeloFormNextAction.EXPORT, 0),
        (
            verified.model_copy(update={"last_export": _export(current=False)}),
            True,
            False,
            ModeloFormNextAction.EXPORT_AGAIN,
            0,
        ),
        (
            verified.model_copy(update={"last_export": _export(current=True)}),
            True,
            False,
            ModeloFormNextAction.RECORD_AFTER_FILE,
            0,
        ),
        (filed, True, True, ModeloFormNextAction.RECORDED, 0),
    ]
    for form, is_verified, is_filed, action, count in table:
        step = form_next_step(form, verified=is_verified, filed=is_filed)
        assert (step.action, step.count) == (action, count), (action, step, form.counts)

    assert missing_count(empty) > 0
    assert (
        form_next_step(
            verified.model_copy(update={"last_export": _export(current=True)}), verified=True, filed=False
        ).file_created_at
        == _EXPORTED_AT
    )
    recorded = form_next_step(filed, verified=True, filed=True)
    assert filed.filing is not None
    assert recorded.recorded_at == filed.filing.recorded_at


@pytest.mark.parametrize("reason", sorted(GATE_REFUSED_REASONS | EXPORT_REFUSED_REASONS))
def test_a_note_the_export_or_filing_gate_refuses_on_withholds_the_file_and_the_recording(
    operation: PinnedAuthorityOperation, reason: str
) -> None:
    """Whatever the check said, the form never offers what the gate would refuse."""
    verified = _calculated(
        _entered(operation),
        verification=VerificationCompletenessStatus.COMPLETE,
        last_export=_export(current=True),
        calculation_notes=(_note(reason),),
    )

    assert CALCULATION_NOTE_ATTENTION[reason] is ModeloFormAttention.BLOCKS
    assert blocking_count(verified) == 1
    step = form_next_step(verified, verified=True, filed=False)
    assert step.action is ModeloFormNextAction.RESOLVE
    assert step.count == 1


def test_an_unverified_calculation_is_never_offered_the_file(operation: PinnedAuthorityOperation) -> None:
    for verdict in VerificationCompletenessStatus:
        form = _calculated(_entered(operation), verification=verdict, last_export=_export(current=True))
        assert form_next_step(form, verified=False, filed=False).action not in _FILE_ACTIONS, verdict


def _refusal(code: ModeloEditRefusalCode, *facts: str) -> ModeloEditRefusedV1:
    return ModeloEditRefusedV1(
        refusal=ModeloEditDomainRefusalV1(
            code=code,
            facts=facts,
            responsible_owner=RESPONSIBLE_OWNER,
            reconsideration_condition="edit a modelo revision whose registry authority reaches calculation grade",
        )
    )


def test_only_rules_short_of_calculation_grade_halt_the_next_step() -> None:
    assert registry_grade_refusal(_refusal(ModeloEditRefusalCode.ADMISSION_DENIED, "registry_authority_grade"))
    assert not registry_grade_refusal(
        _refusal(ModeloEditRefusalCode.ADMISSION_DENIED, "current_calculation_revision_id")
    )
    assert not registry_grade_refusal(
        _refusal(ModeloEditRefusalCode.CALCULATION_HEAD_CONFLICT, "registry_authority_grade")
    )


def test_a_recorded_filing_leaves_its_receipt_to_add_until_it_is_verified(operation: PinnedAuthorityOperation) -> None:
    filed = built_form(operation, "210", 2025, "0A", entered=frozenset(), lifecycle=CalculationRevisionState.PRESENTADO)
    verified = _calculated(_entered(operation), verification=VerificationCompletenessStatus.COMPLETE)

    unverified = form_next_step(filed, verified=True, filed=True, receipt_confirmed=False)
    confirmed = form_next_step(filed, verified=True, filed=True, receipt_confirmed=True)
    unread = form_next_step(filed, verified=True, filed=True)

    assert (unverified.action, unverified.receipt_to_add) == (ModeloFormNextAction.RECORDED, True)
    assert (confirmed.action, confirmed.receipt_to_add) == (ModeloFormNextAction.RECORDED, False)
    assert (unread.action, unread.receipt_to_add) == (ModeloFormNextAction.RECORDED, False)
    # A declaration not recorded has no receipt to add, whatever the read said.
    open_step = form_next_step(verified, verified=True, filed=False, receipt_confirmed=False)
    assert open_step.action is ModeloFormNextAction.EXPORT and not open_step.receipt_to_add


def test_a_retained_prerequisite_makes_resolving_it_the_one_step_from_the_findings() -> None:
    for action in ModeloFormNextAction:
        held = held_prerequisite_step(ModeloFormNextStep(action=action, count=4, receipt_to_add=True))
        assert (held.action, held.count, held.findings_lead, held.receipt_to_add) == (
            ModeloFormNextAction.RESOLVE,
            1,
            True,
            False,
        ), action
