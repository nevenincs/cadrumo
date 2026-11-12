"""Reconciliation and Modelo 145 refusals state their door and are worded in every locale.

Each refusal is raised by the owning code from a real trigger, then read through
the reader the operation error detail uses and through the message resolver the
renderer uses.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....core.errors.error_codes import resolve_error_message
from ....core.operator_action_enums import NoRecoveryOutcome
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope, open_ended_revision
from ...cli_exception_preconditions import nested_terminal_precondition_verdict
from ...operator_actions.models import PreconditionVerdict
from ..m145_communication_period import M145CommunicationPeriod
from ..m145_communication_records import (
    M145CommunicationCreateCommand,
    M145CommunicationRecord,
    M145CommunicationRecordState,
    M145CommunicationRecordTransitionError,
    M145CommunicationRecordValidationError,
    create_m145_communication_record,
    mark_m145_communication_record_locally_completed,
)
from ..m145_communication_records_ports import M145CommunicationRecordsPorts
from ..reconcile_casilla import CasillaDivergence, CasillaDivergenceKind
from ..reconciliation import (
    ModeloReconciliationBytesCommand,
    ReconciliationDeclaracionSourceUnsupportedError,
    prepare_modelo_reconcile_bytes,
)
from ..reconciliation_comparison import _casilla_divergence_diff
from ..reconciliation_records import ModeloReconciliationEvidenceKind

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_LOCALES = ("en", "es", "ca", "hu")
_YEAR = filing_year_envelope().horizon
_BUCKET = "b" * 32


def _verdict(error: BaseException) -> PreconditionVerdict:
    verdict = nested_terminal_precondition_verdict(error)
    assert verdict is not None
    return verdict


def _outcome(error: BaseException) -> NoRecoveryOutcome:
    verdict = _verdict(error)
    assert verdict.action is None
    assert verdict.no_recovery_outcome is not None
    return verdict.no_recovery_outcome


def _served_in_every_locale(error: BaseException) -> dict[str, str]:
    served = {locale: resolve_error_message(error, locale=locale) for locale in _LOCALES}
    key = getattr(error, "translated_message", None)
    assert isinstance(key, str)
    for locale, text in served.items():
        assert text and text != key, locale
        assert "%{" not in text, locale
    assert len(set(served.values())) == len(_LOCALES)
    return served


class _RecordFixedRepository:
    """A record repository that resolves one stored record."""

    def __init__(self, record: M145CommunicationRecord) -> None:
        self._record = record

    def exists(self, communication_record_id: str) -> bool:
        raise AssertionError(communication_record_id)

    def load(self, communication_record_id: str) -> M145CommunicationRecord:
        raise AssertionError(communication_record_id)

    def resolve(self, communication_record_id: str) -> M145CommunicationRecord:
        assert communication_record_id == self._record.communication_record_id
        return self._record

    def save_with_secure_object_writes(self, record: M145CommunicationRecord, extra_writes: tuple[object, ...]) -> None:
        raise AssertionError(record.communication_record_id, extra_writes)


def test_a_record_not_yet_delivered_cannot_be_completed_and_says_which_state_it_holds() -> None:
    record = M145CommunicationRecord(
        communication_record_id="a" * 64,
        bucket_id=_BUCKET,
        communication_year=_YEAR,
        period_token=M145CommunicationPeriod.COMMUNICATION,
        revision_id=str(open_ended_revision("145").id),
        state=M145CommunicationRecordState.CREATED,
        field_values={"perceptor.nif": "12345678Z"},
        legal_refs=("rd-439-2007:art-88",),
        source_refs=("aeat-modelo-145-form",),
        created_at=datetime(_YEAR, 5, 8, 10, 15, tzinfo=UTC),
    )
    ports = M145CommunicationRecordsPorts(
        record_repository=_RecordFixedRepository(record),
        bucket_event_repository=_Untouched(),
    )
    with (
        bundled_indexed_authority().operation() as operation,
        pytest.raises(M145CommunicationRecordTransitionError) as raised,
    ):
        mark_m145_communication_record_locally_completed(
            record.communication_record_id, bucket_id=_BUCKET, ports=ports, operation=operation
        )

    assert _outcome(raised.value) is NoRecoveryOutcome.OPERATOR_DECISION
    served = _served_in_every_locale(raised.value)
    assert all("created" in text for text in served.values())


class _Untouched:
    """An event history the refused request never reaches."""

    def __getattr__(self, name: str) -> object:
        raise AssertionError(name)


def test_an_undeclared_communication_casilla_is_worded_with_its_count() -> None:
    command = M145CommunicationCreateCommand(communication_year=_YEAR, field_values={"not.a.declared.casilla": "x"})
    ports = M145CommunicationRecordsPorts(record_repository=_Untouched(), bucket_event_repository=_Untouched())
    with (
        bundled_indexed_authority().operation() as operation,
        pytest.raises(M145CommunicationRecordValidationError) as raised,
    ):
        create_m145_communication_record(command, bucket_id=_BUCKET, ports=ports, operation=operation)

    assert _outcome(raised.value) is NoRecoveryOutcome.OPERATOR_DECISION
    served = _served_in_every_locale(raised.value)
    assert all("1" in text for text in served.values())


def test_a_declaration_source_no_modelo_enrolls_is_the_operators_decision_in_every_locale() -> None:
    command = ModeloReconciliationBytesCommand(
        work_unit_id="c" * 64,
        source_kind=ModeloReconciliationEvidenceKind.DECLARATION,
        source_bytes=b"%PDF",
        source_ref="secure-source:example",
    )
    with (
        bundled_indexed_authority().operation() as operation,
        pytest.raises(ReconciliationDeclaracionSourceUnsupportedError) as raised,
    ):
        prepare_modelo_reconcile_bytes(command, operation=operation)

    assert _outcome(raised.value) is NoRecoveryOutcome.OPERATOR_DECISION
    assert _verdict(raised.value).failed_condition_id == "modelo.reconciliation.declaration_source.enrolled"
    _served_in_every_locale(raised.value)


def test_a_difference_in_an_undeclared_box_is_terminal_and_names_the_box() -> None:
    divergence = CasillaDivergence(
        casilla_id="undeclared.box",
        kind=CasillaDivergenceKind.VALUE_MISMATCH,
        computed_value=Decimal("1"),
        filed_value=Decimal("2"),
        delta=Decimal("1"),
    )
    with pytest.raises(ReconciliationDeclaracionSourceUnsupportedError) as raised:
        _casilla_divergence_diff(divergence, revision_casillas={})

    assert _outcome(raised.value) is NoRecoveryOutcome.TERMINAL
    served = _served_in_every_locale(raised.value)
    assert all("undeclared.box" in text for text in served.values())
