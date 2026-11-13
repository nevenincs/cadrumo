"""Modelo 232 related-party statements through the real supervisor matrix."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from ...application.aggregation.m232_related_party_repository import (
    state_m232_none,
    state_m232_operation,
    state_m232_turnover,
)
from ...application.m232_related_party.contracts import (
    M232_RELATED_PARTY_LIST_OPERATION_DEFINITION_ID,
    M232_RELATED_PARTY_NONE_STATE_OPERATION_DEFINITION_ID,
    M232_RELATED_PARTY_NONE_WITHDRAW_OPERATION_DEFINITION_ID,
    M232_RELATED_PARTY_OPERATION_STATE_OPERATION_DEFINITION_ID,
    M232_RELATED_PARTY_OPERATION_WITHDRAW_OPERATION_DEFINITION_ID,
    M232_RELATED_PARTY_TURNOVER_STATE_OPERATION_DEFINITION_ID,
    M232_RELATED_PARTY_TURNOVER_WITHDRAW_OPERATION_DEFINITION_ID,
)
from ...application.m232_related_party.requests import (
    Modelo232NoneStateRequest,
    Modelo232NoneWithdrawRequest,
    Modelo232OperationStateRequest,
    Modelo232OperationWithdrawRequest,
    Modelo232RelatedPartyListRequest,
    Modelo232TurnoverStateRequest,
    Modelo232TurnoverWithdrawRequest,
)
from ...application.m232_related_party.results import (
    Modelo232RelatedPartyListProjection,
    Modelo232RelatedPartyMutationProjection,
)
from ...application.operations.public_scalar import PublicDecimal
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.modelos.m232_related_party import (
    Modelo232Direction,
    Modelo232NoneStatement,
    Modelo232Operation,
    Modelo232OperationKind,
    Modelo232StatementState,
    Modelo232TurnoverSource,
    Modelo232TurnoverStatement,
)
from ..m232_related_party_composition import build_m232_related_party_ports
from .conformance_family_contract import (
    ConformanceFamily,
    ConformanceFamilyContext,
    ConformanceOutcome,
    ConformancePreparation,
    RegisteredExecutorConformanceCase,
)

_NAME = "Synthetic Related Holding"
_NOTE = "No related-party or tax-haven operations in the ejercicio."
_REFERENCE = "Synthetic annual accounts, page 7."
_OPERATION_ID = "0123456789abcdef0123456789abcdef"
_STATEMENT_ID = "fedcba9876543210fedcba9876543210"


def _prepare(context: ConformanceFamilyContext) -> ConformancePreparation:
    definition_id = context.definition.definition_id
    subject = profile_operation_subject(str(context.profile_id))
    ports = build_m232_related_party_ports(profile_id=context.profile_id, operation=context.operation)
    ejercicio = context.operation.supported_filing_years().years[-1]
    at = datetime(ejercicio, 4, 2, 9, 0, tzinfo=UTC)

    def verify_written(kind: str, state: Modelo232StatementState):
        def verify(outcome: ConformanceOutcome) -> None:
            result = outcome.resolve_result(Modelo232RelatedPartyMutationProjection)
            assert result.outcome == ("stated" if state is Modelo232StatementState.ACTIVE else "withdrawn")
            assert result.profile_id == context.profile_id
            assert result.refusal is None
            view = ports.store.read_year(ejercicio)
            stored = {"operation": view.operations, "none": view.nones, "turnover": view.turnovers}[kind]
            (row, revision_id) = stored[0]
            assert row.state is state
            payload = result.payload
            assert payload is not None
            assert payload.revision_id == revision_id
            assert payload.state is state

        return verify

    if definition_id == M232_RELATED_PARTY_OPERATION_STATE_OPERATION_DEFINITION_ID:
        return ConformancePreparation(
            subject,
            Modelo232OperationStateRequest(
                profile_id=context.profile_id,
                ejercicio=ejercicio,
                operation_kind=Modelo232OperationKind.TAX_HAVEN_OPERATION,
                counterparty_name=_NAME,
                counterparty_country="KY",
                amount_eur=PublicDecimal(decimal="1500.00"),
                description="Synthetic service fee",
            ),
            verify=verify_written("operation", Modelo232StatementState.ACTIVE),
        )
    if definition_id == M232_RELATED_PARTY_OPERATION_WITHDRAW_OPERATION_DEFINITION_ID:
        revision_id = state_m232_operation(
            Modelo232Operation(
                operation_id=_OPERATION_ID,
                ejercicio=ejercicio,
                operation_kind=Modelo232OperationKind.RELATED_PARTY,
                counterparty_tax_id="B99999991",
                counterparty_name=_NAME,
                counterparty_country="ES",
                tipo_vinculacion="D",
                tipo_operacion="06",
                valuation_method="1A",
                direction=Modelo232Direction.PAGO,
                amount_eur=Decimal("1000.00"),
                stated_at=at,
            ),
            ports=ports,
        )
        return ConformancePreparation(
            subject,
            Modelo232OperationWithdrawRequest(
                profile_id=context.profile_id,
                ejercicio=ejercicio,
                operation_id=_OPERATION_ID,
                expected_revision_id=revision_id,
            ),
            verify=verify_written("operation", Modelo232StatementState.WITHDRAWN),
        )
    if definition_id == M232_RELATED_PARTY_NONE_STATE_OPERATION_DEFINITION_ID:
        return ConformancePreparation(
            subject,
            Modelo232NoneStateRequest(profile_id=context.profile_id, ejercicio=ejercicio, note=_NOTE),
            verify=verify_written("none", Modelo232StatementState.ACTIVE),
        )
    if definition_id == M232_RELATED_PARTY_NONE_WITHDRAW_OPERATION_DEFINITION_ID:
        revision_id = state_m232_none(
            Modelo232NoneStatement(statement_id=_STATEMENT_ID, ejercicio=ejercicio, note=_NOTE, stated_at=at),
            ports=ports,
        )
        return ConformancePreparation(
            subject,
            Modelo232NoneWithdrawRequest(
                profile_id=context.profile_id, ejercicio=ejercicio, expected_revision_id=revision_id
            ),
            verify=verify_written("none", Modelo232StatementState.WITHDRAWN),
        )
    if definition_id == M232_RELATED_PARTY_TURNOVER_STATE_OPERATION_DEFINITION_ID:
        return ConformancePreparation(
            subject,
            Modelo232TurnoverStateRequest(
                profile_id=context.profile_id,
                ejercicio=ejercicio,
                turnover_eur=PublicDecimal(decimal="987654.32"),
                source=Modelo232TurnoverSource.ANNUAL_ACCOUNTS,
                source_reference=_REFERENCE,
            ),
            verify=verify_written("turnover", Modelo232StatementState.ACTIVE),
        )
    if definition_id == M232_RELATED_PARTY_TURNOVER_WITHDRAW_OPERATION_DEFINITION_ID:
        revision_id = state_m232_turnover(
            Modelo232TurnoverStatement(
                statement_id=_STATEMENT_ID,
                ejercicio=ejercicio,
                turnover_eur=Decimal("987654.32"),
                source=Modelo232TurnoverSource.ANNUAL_ACCOUNTS,
                source_reference=_REFERENCE,
                stated_at=at,
            ),
            ports=ports,
        )
        return ConformancePreparation(
            subject,
            Modelo232TurnoverWithdrawRequest(
                profile_id=context.profile_id, ejercicio=ejercicio, expected_revision_id=revision_id
            ),
            verify=verify_written("turnover", Modelo232StatementState.WITHDRAWN),
        )
    if definition_id == M232_RELATED_PARTY_LIST_OPERATION_DEFINITION_ID:
        revision_id = state_m232_none(
            Modelo232NoneStatement(statement_id=_STATEMENT_ID, ejercicio=ejercicio, note=_NOTE, stated_at=at),
            ports=ports,
        )

        def verify_list(outcome: ConformanceOutcome) -> None:
            result = outcome.resolve_result(Modelo232RelatedPartyListProjection)
            assert result.profile_id == context.profile_id
            assert result.ejercicio == ejercicio
            (row,) = result.year.none_statements
            assert row.note == _NOTE
            assert row.revision_id == revision_id
            assert result.year.guard_revision_id == ports.store.read_year(ejercicio).guard_revision_id
            assert result.year.operations == ()

        return ConformancePreparation(
            subject,
            Modelo232RelatedPartyListRequest(profile_id=context.profile_id, ejercicio=ejercicio),
            verify=verify_list,
        )
    raise AssertionError(f"unsupported Modelo 232 related-party conformance definition: {definition_id}")


def _case(definition_id: str, effect: OperationEffect) -> RegisteredExecutorConformanceCase:
    return RegisteredExecutorConformanceCase(definition_id, OperationTerminalCondition.SUCCEEDED, effect)


M232_RELATED_PARTY_CONFORMANCE_FAMILY = ConformanceFamily(
    cases=(
        _case(M232_RELATED_PARTY_OPERATION_STATE_OPERATION_DEFINITION_ID, OperationEffect.UPDATED),
        _case(M232_RELATED_PARTY_OPERATION_WITHDRAW_OPERATION_DEFINITION_ID, OperationEffect.UPDATED),
        _case(M232_RELATED_PARTY_NONE_STATE_OPERATION_DEFINITION_ID, OperationEffect.UPDATED),
        _case(M232_RELATED_PARTY_NONE_WITHDRAW_OPERATION_DEFINITION_ID, OperationEffect.UPDATED),
        _case(M232_RELATED_PARTY_TURNOVER_STATE_OPERATION_DEFINITION_ID, OperationEffect.UPDATED),
        _case(M232_RELATED_PARTY_TURNOVER_WITHDRAW_OPERATION_DEFINITION_ID, OperationEffect.UPDATED),
        _case(M232_RELATED_PARTY_LIST_OPERATION_DEFINITION_ID, OperationEffect.NONE),
    ),
    prepare=_prepare,
)
