"""The registered Modelo 232 related-party operations run against the real composed ports, store and authority.

Only the operation host's event and operand plumbing is a minimal stand-in. The
retained result is what the CLI bridge reads back, so its outcome, effect and
refusal code are asserted here. All identifiers, names, notes and amounts are
synthetic; the years come from the registry's support envelope.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
from pydantic import BaseModel

from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.m232_related_party.contracts import (
    M232_RELATED_PARTY_LIST_OPERATION_DEFINITION_ID,
    M232_RELATED_PARTY_NONE_STATE_OPERATION_DEFINITION_ID,
    M232_RELATED_PARTY_NONE_WITHDRAW_OPERATION_DEFINITION_ID,
    M232_RELATED_PARTY_OPERATION_STATE_OPERATION_DEFINITION_ID,
    M232_RELATED_PARTY_OPERATION_WITHDRAW_OPERATION_DEFINITION_ID,
    M232_RELATED_PARTY_REFUSAL_CODE,
    M232_RELATED_PARTY_REVISION_REFUSAL_CODE,
    M232_RELATED_PARTY_TURNOVER_STATE_OPERATION_DEFINITION_ID,
    M232_RELATED_PARTY_TURNOVER_WITHDRAW_OPERATION_DEFINITION_ID,
)
from cadrumo.application.m232_related_party.executor import Modelo232RelatedPartyExecutor
from cadrumo.application.m232_related_party.requests import (
    Modelo232NoneStateRequest,
    Modelo232NoneWithdrawRequest,
    Modelo232OperationStateRequest,
    Modelo232OperationWithdrawRequest,
    Modelo232RelatedPartyListRequest,
    Modelo232TurnoverStateRequest,
    Modelo232TurnoverWithdrawRequest,
)
from cadrumo.application.m232_related_party.results import Modelo232RelatedPartyExecutionResult, Modelo232YearProjection
from cadrumo.application.operations.models import OperationIdentity, OperationRequest
from cadrumo.application.operations.owner import OperationExecutorContext
from cadrumo.application.operations.public_scalar import PublicDecimal
from cadrumo.application.operations.refusal_evidence import OperationRefusalEvidence
from cadrumo.application.tests.operation_host_fakes import RecordingEvents
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.core.config import override_settings
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.i18n.render import tr
from cadrumo.core.operations import OperationEffect, profile_operation_subject
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.domain.modelos.m232_obligation import Modelo232Basis, Modelo232Ground, Modelo232Obligation
from cadrumo.domain.modelos.m232_related_party import (
    Modelo232Direction,
    Modelo232OperationKind,
    Modelo232StatementState,
    Modelo232TurnoverSource,
)
from cadrumo.entrypoints.m232_related_party_composition import build_m232_related_party_ports

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("operation")]

_PROFILE = "7c2d9e4f-1a3b-4c5d-8e6f-0a1b2c3d4e5f"
_EJERCICIO = filing_year_envelope().horizon
_NAME = "Synthetic Related Holding"
_TAX_ID = "B99999991"
_NOTE = "Synthetic note: the partners confirmed no group dealings."
_REFERENCE = "Synthetic ref: accounts filed with the registry, page 7."
_STALE = "f" * 64


class _Cancellation:
    def __init__(self) -> None:
        self.inside = False

    @asynccontextmanager
    async def irreversible_section(self):
        self.inside = True
        try:
            yield
        finally:
            self.inside = False


class _Operands:
    def __init__(self, cancellation: _Cancellation, *, writes: bool) -> None:
        self._cancellation = cancellation
        self._writes = writes
        self.value: BaseModel | None = None

    async def put(self, value: BaseModel, *, written_at: object) -> str:
        del written_at
        assert self._cancellation.inside == self._writes
        self.value = value
        return "d" * 64


class _Context:
    def __init__(self, authority_operation: PinnedAuthorityOperation, definition_id: str) -> None:
        self.identity = OperationIdentity(
            operation_id="c" * 64,
            definition_id=definition_id,
            subject_ref=profile_operation_subject(_PROFILE),
        )
        self.authority_operation = authority_operation
        self.events = RecordingEvents()
        self.cancellation = _Cancellation()
        self.operands = _Operands(
            self.cancellation, writes=definition_id != M232_RELATED_PARTY_LIST_OPERATION_DEFINITION_ID
        )


type _Run = tuple[str | OperationRefusalEvidence, Modelo232RelatedPartyExecutionResult, list[OperationEffect]]


def _run(authority_operation: PinnedAuthorityOperation, definition_id: str, payload: BaseModel) -> _Run:
    context = _Context(authority_operation, definition_id)
    request = OperationRequest(
        definition_id=definition_id, subject_ref=profile_operation_subject(_PROFILE), payload=payload
    )
    executor = Modelo232RelatedPartyExecutor(build_m232_related_party_ports, definition_id=definition_id)
    outcome = asyncio.run(executor.execute(request, cast(OperationExecutorContext, context)))
    retained = context.operands.value
    assert isinstance(retained, Modelo232RelatedPartyExecutionResult)
    return outcome, retained, context.events.effects


def _state_operation(
    authority_operation: PinnedAuthorityOperation,
    *,
    ejercicio: int = _EJERCICIO,
    amount: str = "312345.67",
    guard: str | None = None,
    **overrides: object,
) -> _Run:
    fields: dict[str, object] = {
        "profile_id": UUID(_PROFILE),
        "ejercicio": ejercicio,
        "operation_kind": Modelo232OperationKind.RELATED_PARTY,
        "counterparty_tax_id": _TAX_ID,
        "counterparty_name": _NAME,
        "counterparty_country": "DE",
        "tipo_vinculacion": "D",
        "tipo_operacion": "06",
        "valuation_method": "1A",
        "direction": Modelo232Direction.PAGO,
        "amount_eur": PublicDecimal(decimal=amount),
        "expected_guard_revision_id": guard,
    }
    fields.update(overrides)
    return _run(
        authority_operation,
        M232_RELATED_PARTY_OPERATION_STATE_OPERATION_DEFINITION_ID,
        Modelo232OperationStateRequest.model_validate(fields),
    )


def _withdraw_operation(authority_operation: PinnedAuthorityOperation, operation_id: str, expected: str) -> _Run:
    return _run(
        authority_operation,
        M232_RELATED_PARTY_OPERATION_WITHDRAW_OPERATION_DEFINITION_ID,
        Modelo232OperationWithdrawRequest(
            profile_id=UUID(_PROFILE), ejercicio=_EJERCICIO, operation_id=operation_id, expected_revision_id=expected
        ),
    )


def _state_none(authority_operation: PinnedAuthorityOperation) -> _Run:
    return _run(
        authority_operation,
        M232_RELATED_PARTY_NONE_STATE_OPERATION_DEFINITION_ID,
        Modelo232NoneStateRequest(profile_id=UUID(_PROFILE), ejercicio=_EJERCICIO, note=_NOTE),
    )


def _withdraw_none(authority_operation: PinnedAuthorityOperation, expected: str) -> _Run:
    return _run(
        authority_operation,
        M232_RELATED_PARTY_NONE_WITHDRAW_OPERATION_DEFINITION_ID,
        Modelo232NoneWithdrawRequest(profile_id=UUID(_PROFILE), ejercicio=_EJERCICIO, expected_revision_id=expected),
    )


def _state_turnover(authority_operation: PinnedAuthorityOperation, amount: str = "987654.32") -> _Run:
    return _run(
        authority_operation,
        M232_RELATED_PARTY_TURNOVER_STATE_OPERATION_DEFINITION_ID,
        Modelo232TurnoverStateRequest(
            profile_id=UUID(_PROFILE),
            ejercicio=_EJERCICIO,
            turnover_eur=PublicDecimal(decimal=amount),
            source=Modelo232TurnoverSource.ANNUAL_ACCOUNTS,
            source_reference=_REFERENCE,
        ),
    )


def _withdraw_turnover(authority_operation: PinnedAuthorityOperation, expected: str) -> _Run:
    return _run(
        authority_operation,
        M232_RELATED_PARTY_TURNOVER_WITHDRAW_OPERATION_DEFINITION_ID,
        Modelo232TurnoverWithdrawRequest(
            profile_id=UUID(_PROFILE), ejercicio=_EJERCICIO, expected_revision_id=expected
        ),
    )


def _list(authority_operation: PinnedAuthorityOperation, ejercicio: int = _EJERCICIO) -> Modelo232YearProjection:
    outcome, listed, effects = _run(
        authority_operation,
        M232_RELATED_PARTY_LIST_OPERATION_DEFINITION_ID,
        Modelo232RelatedPartyListRequest(profile_id=UUID(_PROFILE), ejercicio=ejercicio),
    )
    assert not isinstance(outcome, OperationRefusalEvidence)
    assert effects == [OperationEffect.NONE]
    assert listed.outcome == "success"
    assert listed.year is not None
    return listed.year


def _refusal(run: _Run) -> tuple[str, str]:
    outcome, result, effects = run
    assert isinstance(outcome, OperationRefusalEvidence)
    assert effects == [OperationEffect.UNKNOWN, OperationEffect.NONE]
    assert result.outcome == "refused"
    assert result.refusal is not None
    assert result.refusal.code == outcome.refusal_code
    return result.refusal.reason, outcome.refusal_code


def test_an_operation_is_stated_listed_with_its_verdict_and_withdrawn(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE):
        # An empty year lists as empty: success, no change, and the records decide nothing yet.
        empty = _list(operation)
        assert (empty.operations, empty.none_statements, empty.turnover_statements) == ((), (), ())
        assert empty.verdict is not None
        assert empty.verdict.basis is Modelo232Basis.NOTHING_STATED
        assert empty.verdict.obligation is Modelo232Obligation.UNDECIDED

        outcome, stated, effects = _state_operation(operation, guard=empty.guard_revision_id)
        assert not isinstance(outcome, OperationRefusalEvidence)
        assert effects == [OperationEffect.UNKNOWN, OperationEffect.UPDATED]
        assert stated.outcome == "success"
        assert stated.operation is not None
        assert stated.operation.state is Modelo232StatementState.ACTIVE
        assert stated.operation.counterparty_name == _NAME
        assert _TAX_ID not in stated.model_dump_json()

        listed = _list(operation)
        (row,) = listed.operations
        assert row.operation_id == stated.operation.operation_id
        assert row.revision_id == stated.operation.revision_id
        assert row.amount_eur.decimal == "312345.67"
        assert listed.guard_revision_id != empty.guard_revision_id
        # The amount with one related party passes the registry's art. 2.1.a threshold.
        verdict = listed.verdict
        assert verdict is not None
        assert verdict.basis is Modelo232Basis.OPERATIONS_STATED
        assert verdict.obligation is Modelo232Obligation.OWED
        assert verdict.obligation_label == tr("aggregation.modelo_232_related_party.obligation.owed")
        grounds = {ground.ground: ground for ground in verdict.grounds}
        assert grounds[Modelo232Ground.SAME_RELATED_PARTY].state.value == "met"
        assert _TAX_ID not in listed.model_dump_json()

        stale = _withdraw_operation(operation, row.operation_id, _STALE)
        assert _refusal(stale) == ("stale_revision", M232_RELATED_PARTY_REVISION_REFUSAL_CODE)

        _, withdrawn, _ = _withdraw_operation(operation, row.operation_id, row.revision_id)
        assert withdrawn.operation is not None
        assert withdrawn.operation.state is Modelo232StatementState.WITHDRAWN
        assert withdrawn.operation.revision_id != row.revision_id

        again = _withdraw_operation(operation, row.operation_id, withdrawn.operation.revision_id)
        assert _refusal(again) == ("not_stated", M232_RELATED_PARTY_REFUSAL_CODE)

        # The withdrawn operation stays listed, and with nothing in force the records decide nothing.
        after = _list(operation)
        (kept,) = after.operations
        assert kept.state is Modelo232StatementState.WITHDRAWN
        assert after.verdict is not None
        assert after.verdict.basis is Modelo232Basis.NOTHING_STATED
        assert _list(operation, _EJERCICIO - 1).operations == ()


def test_a_write_against_a_moved_guard_is_refused(tmp_path: Path, operation: PinnedAuthorityOperation) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE):
        guard = _list(operation).guard_revision_id
        _state_turnover(operation)
        moved = _state_operation(operation, guard=guard)
        assert _refusal(moved) == ("stale_revision", M232_RELATED_PARTY_REVISION_REFUSAL_CODE)
        assert _list(operation).operations == ()


def test_the_none_statement_and_an_operation_cannot_stand_together(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE):
        _, none, _ = _state_none(operation)
        assert none.none_statement is not None
        assert none.none_statement.note == _NOTE
        assert _refusal(_state_operation(operation)) == ("none_stated", M232_RELATED_PARTY_REFUSAL_CODE)
        assert _refusal(_state_none(operation)) == ("already_stated", M232_RELATED_PARTY_REFUSAL_CODE)

        listed = _list(operation)
        assert listed.verdict is not None
        assert listed.verdict.basis is Modelo232Basis.NONE_STATED
        assert listed.verdict.obligation is Modelo232Obligation.NOT_OWED

        # Withdrawing the statement returns the year to undecided and admits an operation.
        (statement,) = listed.none_statements
        _, withdrawn, _ = _withdraw_none(operation, statement.revision_id)
        assert withdrawn.none_statement is not None
        assert withdrawn.none_statement.state is Modelo232StatementState.WITHDRAWN
        _, stated, _ = _state_operation(operation)
        assert stated.operation is not None
        assert _refusal(_state_none(operation)) == ("operations_present", M232_RELATED_PARTY_REFUSAL_CODE)


def test_the_turnover_is_stated_listed_and_withdrawn(tmp_path: Path, operation: PinnedAuthorityOperation) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE):
        _, stated, _ = _state_turnover(operation)
        assert stated.turnover_statement is not None
        assert _refusal(_state_turnover(operation)) == ("already_stated", M232_RELATED_PARTY_REFUSAL_CODE)

        (row,) = _list(operation).turnover_statements
        assert row.turnover_eur.decimal == "987654.32"
        assert row.source is Modelo232TurnoverSource.ANNUAL_ACCOUNTS
        assert row.source_label == tr("filing.applicability.records_turnover_source.annual_accounts")
        assert _refusal(_withdraw_turnover(operation, _STALE)) == (
            "stale_revision",
            M232_RELATED_PARTY_REVISION_REFUSAL_CODE,
        )
        _, withdrawn, _ = _withdraw_turnover(operation, row.revision_id)
        assert withdrawn.turnover_statement is not None
        assert withdrawn.turnover_statement.state is Modelo232StatementState.WITHDRAWN


def test_unsupported_years_unknown_codes_and_incoherent_fields_are_refused(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    floor = min(filing_year_envelope().years)
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE):
        assert _refusal(_state_operation(operation, ejercicio=floor - 1)) == (
            "ejercicio_unsupported",
            M232_RELATED_PARTY_REFUSAL_CODE,
        )
        assert _list(operation, floor - 1).verdict is None
        assert _refusal(_state_operation(operation, tipo_operacion="ZZ")) == (
            "code_unknown",
            M232_RELATED_PARTY_REFUSAL_CODE,
        )
        # A tax-haven operation states no relationship type, so these fields form no statement of its kind.
        assert _refusal(_state_operation(operation, operation_kind=Modelo232OperationKind.TAX_HAVEN_OPERATION)) == (
            "validation",
            M232_RELATED_PARTY_REFUSAL_CODE,
        )
        assert _list(operation).operations == ()


def test_the_composed_ports_refuse_a_profile_other_than_the_active_one(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE), pytest.raises(ProfileAccessRefusedError):
        build_m232_related_party_ports(profile_id=UUID("22222222-2222-4222-8222-222222222222"), operation=operation)


@pytest.mark.parametrize("language", list(OutputLanguage))
def test_each_refusal_serves_its_own_sentence_in_the_workers_language(
    tmp_path: Path, operation: PinnedAuthorityOperation, language: OutputLanguage
) -> None:
    with (
        override_settings(cadrumo_output_language=language.value),
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE),
    ):
        _state_none(operation)
        refused = {
            "already_stated": _state_none(operation)[1],
            "none_stated": _state_operation(operation)[1],
            "stale_revision": _withdraw_turnover(operation, _STALE)[1],
        }
    for reason, result in refused.items():
        assert result.refusal is not None
        assert result.refusal.reason == reason
        words = result.refusal.refusal_words
        assert words == tr(f"aggregation.modelo_232_related_party.served.{reason}", locale=language.value)
        assert result.refusal.refusal_words_language is language
        assert _NAME not in words
        assert _NOTE not in words
