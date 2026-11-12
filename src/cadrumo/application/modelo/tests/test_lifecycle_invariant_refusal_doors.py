"""Invariant, profile-binding, communication, filing-evidence and reconciliation refusals open the door of their cause.

Each refusal is raised by the owning code from a real trigger, and read through
the reader the operation error detail uses.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ....core.errors.hierarchy import InternalInvariantError
from ....core.operator_action_enums import NoRecoveryOutcome
from ....core.period import Period
from ....core.secure_object_write import SecureObjectWrite
from ....domain.buckets.event import BucketEventHistoryCatalogue
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.binding_value_contract import BindingValueChannel
from ....domain.calculations.registry.tests.authored_editions import (
    filing_year_envelope,
    newest_authored_edition,
)
from ...aggregation.ledger_payment_withholding import LedgerPaymentWithholdingEvidenceError
from ...cli_exception_preconditions import nested_terminal_precondition_verdict
from ...operator_actions.models import PreconditionVerdict
from ..action_errors import M303FilingEvidenceError
from ..m145_communication_records import (
    M145CommunicationCreateCommand,
    M145CommunicationRecord,
    M145CommunicationRecordValidationError,
    create_m145_communication_record,
)
from ..m145_communication_records_ports import M145CommunicationRecordsPorts
from ..m303_ordinary_filing_evidence_authoring import OrdinaryM303FilingEvidenceRequest
from ..profile_binding import _decimal_value, _reject_channel_declaration_conflict
from ..profile_derived_facts import ProfileBindingResolutionError, inject_derived_state_attribution_facts
from ..reconciliation import ReconciliationEvidenceInvalidError
from ..work_form_errors import ModeloWorkFormLayoutError
from ..workspace import modelo_workspace_recovery_action

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _verdict(error: BaseException) -> PreconditionVerdict:
    verdict = nested_terminal_precondition_verdict(error)
    assert verdict is not None
    return verdict


def _outcome(verdict: PreconditionVerdict) -> NoRecoveryOutcome:
    assert verdict.action is None
    assert verdict.no_recovery_outcome is not None
    return verdict.no_recovery_outcome


def test_a_broken_invariant_is_terminal() -> None:
    with pytest.raises(InternalInvariantError) as raised:
        modelo_workspace_recovery_action("operator.not.a.declared.action", work_unit_id=None)

    verdict = _verdict(raised.value)

    assert _outcome(verdict) is NoRecoveryOutcome.TERMINAL
    assert verdict.evidence[0].values["invariant"] == "workspace.recovery_action_declared"


def test_a_layout_that_misses_a_casilla_is_terminal_at_class_level() -> None:
    assert _outcome(_verdict(ModeloWorkFormLayoutError("layout misses a casilla"))) is NoRecoveryOutcome.TERMINAL


def test_a_profile_fact_the_binding_refuses_is_the_operators_decision() -> None:
    with pytest.raises(ProfileBindingResolutionError) as raised:
        _decimal_value("irpf.example", "not a number")

    assert _outcome(_verdict(raised.value)) is NoRecoveryOutcome.OPERATOR_DECISION


def test_a_binding_contract_the_registry_contradicts_is_terminal() -> None:
    with pytest.raises(ProfileBindingResolutionError) as raised:
        _reject_channel_declaration_conflict(
            "irpf.example",
            declared_channel=BindingValueChannel.TEXT,
            is_date_channel=True,
            is_enum_channel=False,
        )

    assert _outcome(_verdict(raised.value)) is NoRecoveryOutcome.TERMINAL


def test_an_absent_jurisdiction_scope_opens_the_profile_questions() -> None:
    with bundled_indexed_authority().operation() as operation, pytest.raises(ProfileBindingResolutionError) as raised:
        inject_derived_state_attribution_facts({}, operation=operation)

    verdict = _verdict(raised.value)

    assert verdict.action is not None
    assert verdict.action.action_id == "operator.profile.edit"
    assert verdict.evidence[0].values["missing_fields"] == "tax_residence.jurisdiction_scope"


class _UntouchedRecords:
    """A record repository the refused request never reaches."""

    def exists(self, communication_record_id: str) -> bool:
        raise AssertionError(communication_record_id)

    def load(self, communication_record_id: str) -> M145CommunicationRecord:
        raise AssertionError(communication_record_id)

    def resolve(self, communication_record_id: str) -> M145CommunicationRecord:
        raise AssertionError(communication_record_id)

    def save_with_secure_object_writes(
        self, record: M145CommunicationRecord, extra_writes: tuple[SecureObjectWrite, ...]
    ) -> None:
        raise AssertionError(record.communication_record_id, extra_writes)


class _UntouchedEvents:
    """An event history the refused request never reaches."""

    def exists(self) -> bool:
        raise AssertionError("event history")

    def load(self) -> BucketEventHistoryCatalogue:
        raise AssertionError("event history")

    def save(self, catalogue: BucketEventHistoryCatalogue) -> None:
        raise AssertionError(catalogue)

    def to_secure_object_write(
        self, catalogue: BucketEventHistoryCatalogue, *, expected_revision_id: str | None = None
    ) -> SecureObjectWrite:
        raise AssertionError(catalogue, expected_revision_id)


def test_an_undeclared_communication_casilla_is_the_operators_decision() -> None:
    command = M145CommunicationCreateCommand(
        communication_year=filing_year_envelope().horizon,
        field_values={"not.a.declared.casilla": "x"},
    )
    ports = M145CommunicationRecordsPorts(
        record_repository=_UntouchedRecords(), bucket_event_repository=_UntouchedEvents()
    )
    with (
        bundled_indexed_authority().operation() as operation,
        pytest.raises(M145CommunicationRecordValidationError) as raised,
    ):
        create_m145_communication_record(command, bucket_id="b" * 32, ports=ports, operation=operation)

    assert _outcome(_verdict(raised.value)) is NoRecoveryOutcome.OPERATOR_DECISION


def test_a_period_that_disagrees_with_the_filing_year_opens_the_period_mismatch_door() -> None:
    year = newest_authored_edition("303")
    other_year = Period.from_year_and_code(year - 1, "1T")
    with pytest.raises((M303FilingEvidenceError, ValidationError)) as raised:
        OrdinaryM303FilingEvidenceRequest(
            filing_year=year,
            period=other_year,
            joint_return_elected=False,
            exonerado_390_applicability_reference=None,
        )

    verdict = _verdict(raised.value)

    assert _outcome(verdict) is NoRecoveryOutcome.OPERATOR_DECISION
    assert verdict.failed_condition_id == "modelo.work.calculate.m303_filing_evidence.valid"


def test_unusable_reconciliation_evidence_is_the_operators_decision_at_class_level() -> None:
    error = ReconciliationEvidenceInvalidError("captured declaration has no numeric comparison fields")

    assert _outcome(_verdict(error)) is NoRecoveryOutcome.OPERATOR_DECISION


def test_a_refused_ledger_payment_evidence_is_the_operators_decision_at_class_level() -> None:
    verdict = _verdict(LedgerPaymentWithholdingEvidenceError("ledger_payment_period_mismatch"))

    assert _outcome(verdict) is NoRecoveryOutcome.OPERATOR_DECISION
    assert verdict.evidence[0].values["refusal"] == "ledger_payment_period_mismatch"
