"""Profile-scoped executor for the Modelo 232 related-party statements."""

from __future__ import annotations

import asyncio
import secrets
from decimal import Decimal
from typing import Final
from uuid import UUID

from pydantic import BaseModel, ValidationError

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ...core.async_cleanup import await_cancellation_complete
from ...core.operations import OperationEffect
from ...core.time.clock import now
from ...domain.modelos.m232_related_party import Modelo232NoneStatement, Modelo232Operation, Modelo232TurnoverStatement
from ..aggregation.m232_related_party_repository import (
    Modelo232RelatedPartyRefusedError,
    Modelo232RelatedPartyRevisionConflictError,
    Modelo232RelatedPartyWritePorts,
    state_m232_none,
    state_m232_operation,
    state_m232_turnover,
    withdraw_m232_none,
    withdraw_m232_operation,
    withdraw_m232_turnover,
)
from ..operations.models import OperationRequest
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.public_scalar import PublicDecimal
from ..operations.refusal_evidence import OperationRefusalEvidence
from ..user_profile.access_errors import ProfileAccessRefusedError
from .contracts import (
    M232_RELATED_PARTY_LIST_OPERATION_DEFINITION_ID,
    M232_RELATED_PARTY_NONE_STATE_OPERATION_DEFINITION_ID,
    M232_RELATED_PARTY_NONE_WITHDRAW_OPERATION_DEFINITION_ID,
    M232_RELATED_PARTY_OPERATION_STATE_OPERATION_DEFINITION_ID,
    M232_RELATED_PARTY_OPERATION_WITHDRAW_OPERATION_DEFINITION_ID,
    M232_RELATED_PARTY_REFUSAL_CODE,
    M232_RELATED_PARTY_REVISION_REFUSAL_CODE,
    M232_RELATED_PARTY_TURNOVER_STATE_OPERATION_DEFINITION_ID,
    M232_RELATED_PARTY_TURNOVER_WITHDRAW_OPERATION_DEFINITION_ID,
    Modelo232RelatedPartyOperationId,
    Modelo232RelatedPartyOperationRefusalReason,
)
from .ports import Modelo232RelatedPartyPortsFactory
from .refusal_words import served_m232_related_party_refusal_words
from .requests import (
    Modelo232NoneStateRequest,
    Modelo232NoneWithdrawRequest,
    Modelo232OperationStateRequest,
    Modelo232OperationWithdrawRequest,
    Modelo232RelatedPartyListRequest,
    Modelo232RelatedPartyProfileRequest,
    Modelo232RelatedPartyWriteRequest,
    Modelo232TurnoverStateRequest,
    Modelo232TurnoverWithdrawRequest,
)
from .results import (
    Modelo232NoneStatementProjection,
    Modelo232OperationProjection,
    Modelo232RelatedPartyExecutionResult,
    Modelo232RelatedPartyRefusalProjection,
    Modelo232TurnoverStatementProjection,
    Modelo232YearProjection,
)
from .verdict import modelo_232_verdict

__all__ = ["M232_RELATED_PARTY_REQUEST_TYPES", "Modelo232RelatedPartyExecutor"]

M232_RELATED_PARTY_REQUEST_TYPES: Final[dict[str, type[Modelo232RelatedPartyProfileRequest]]] = {
    M232_RELATED_PARTY_LIST_OPERATION_DEFINITION_ID: Modelo232RelatedPartyListRequest,
    M232_RELATED_PARTY_OPERATION_STATE_OPERATION_DEFINITION_ID: Modelo232OperationStateRequest,
    M232_RELATED_PARTY_OPERATION_WITHDRAW_OPERATION_DEFINITION_ID: Modelo232OperationWithdrawRequest,
    M232_RELATED_PARTY_NONE_STATE_OPERATION_DEFINITION_ID: Modelo232NoneStateRequest,
    M232_RELATED_PARTY_NONE_WITHDRAW_OPERATION_DEFINITION_ID: Modelo232NoneWithdrawRequest,
    M232_RELATED_PARTY_TURNOVER_STATE_OPERATION_DEFINITION_ID: Modelo232TurnoverStateRequest,
    M232_RELATED_PARTY_TURNOVER_WITHDRAW_OPERATION_DEFINITION_ID: Modelo232TurnoverWithdrawRequest,
}
"""The one request class each definition admits."""

_OPERATION_IDS: Final[dict[str, Modelo232RelatedPartyOperationId]] = {
    M232_RELATED_PARTY_LIST_OPERATION_DEFINITION_ID: "list",
    M232_RELATED_PARTY_OPERATION_STATE_OPERATION_DEFINITION_ID: "state_operation",
    M232_RELATED_PARTY_OPERATION_WITHDRAW_OPERATION_DEFINITION_ID: "withdraw_operation",
    M232_RELATED_PARTY_NONE_STATE_OPERATION_DEFINITION_ID: "state_none",
    M232_RELATED_PARTY_NONE_WITHDRAW_OPERATION_DEFINITION_ID: "withdraw_none",
    M232_RELATED_PARTY_TURNOVER_STATE_OPERATION_DEFINITION_ID: "state_turnover",
    M232_RELATED_PARTY_TURNOVER_WITHDRAW_OPERATION_DEFINITION_ID: "withdraw_turnover",
}

type _Stated = Modelo232OperationProjection | Modelo232NoneStatementProjection | Modelo232TurnoverStatementProjection


def _row_id() -> str:
    """A random identity that names a row without naming its counterparty."""
    return secrets.token_hex(16)


def _decimal(amount: PublicDecimal | None) -> Decimal | None:
    return None if amount is None else Decimal(amount.decimal)


def _build_operation(request: Modelo232OperationStateRequest) -> Modelo232Operation | None:
    """Build the operation the write path will judge, or ``None`` when its fields form no operation of its kind."""
    try:
        return Modelo232Operation(
            operation_id=_row_id(),
            ejercicio=request.ejercicio,
            operation_kind=request.operation_kind,
            counterparty_tax_id=request.counterparty_tax_id,
            counterparty_name=request.counterparty_name,
            counterparty_country=request.counterparty_country,
            tipo_vinculacion=request.tipo_vinculacion,
            tipo_operacion=request.tipo_operacion,
            valuation_method=request.valuation_method,
            direction=request.direction,
            specific_operation=request.specific_operation,
            amount_eur=Decimal(request.amount_eur.decimal),
            exclusion=request.exclusion,
            description=request.description,
            participation_percent=_decimal(request.participation_percent),
            parent_tax_id=request.parent_tax_id,
            parent_name=request.parent_name,
            stated_at=now(),
        )
    except ValidationError:
        return None


def _state_operation(
    request: Modelo232OperationStateRequest, ports: Modelo232RelatedPartyWritePorts
) -> _Stated | Modelo232RelatedPartyOperationRefusalReason:
    operation = _build_operation(request)
    if operation is None:
        return "validation"
    revision_id = state_m232_operation(
        operation, ports=ports, expected_guard_revision_id=request.expected_guard_revision_id
    )
    return Modelo232OperationProjection.from_operation(operation, revision_id=revision_id)


def _state_none(
    request: Modelo232NoneStateRequest, ports: Modelo232RelatedPartyWritePorts
) -> _Stated | Modelo232RelatedPartyOperationRefusalReason:
    try:
        statement = Modelo232NoneStatement(
            statement_id=_row_id(), ejercicio=request.ejercicio, note=request.note, stated_at=now()
        )
    except ValidationError:
        return "validation"
    revision_id = state_m232_none(statement, ports=ports, expected_guard_revision_id=request.expected_guard_revision_id)
    return Modelo232NoneStatementProjection.from_statement(statement, revision_id=revision_id)


def _state_turnover(
    request: Modelo232TurnoverStateRequest, ports: Modelo232RelatedPartyWritePorts
) -> _Stated | Modelo232RelatedPartyOperationRefusalReason:
    try:
        statement = Modelo232TurnoverStatement(
            statement_id=_row_id(),
            ejercicio=request.ejercicio,
            turnover_eur=Decimal(request.turnover_eur.decimal),
            source=request.source,
            source_reference=request.source_reference,
            stated_at=now(),
        )
    except ValidationError:
        return "validation"
    revision_id = state_m232_turnover(
        statement, ports=ports, expected_guard_revision_id=request.expected_guard_revision_id
    )
    return Modelo232TurnoverStatementProjection.from_statement(statement, revision_id=revision_id)


def _write(
    request: Modelo232RelatedPartyWriteRequest, ports: Modelo232RelatedPartyWritePorts
) -> _Stated | Modelo232RelatedPartyOperationRefusalReason:
    """Store the statement or withdrawal, or name why the write path refused it before anything was stored."""
    try:
        if isinstance(request, Modelo232OperationStateRequest):
            return _state_operation(request, ports)
        if isinstance(request, Modelo232NoneStateRequest):
            return _state_none(request, ports)
        if isinstance(request, Modelo232TurnoverStateRequest):
            return _state_turnover(request, ports)
        if isinstance(request, Modelo232OperationWithdrawRequest):
            operation, revision_id = withdraw_m232_operation(
                (request.ejercicio, request.operation_id),
                at=now(),
                ports=ports,
                expected_revision_id=request.expected_revision_id,
            )
            return Modelo232OperationProjection.from_operation(operation, revision_id=revision_id)
        if isinstance(request, Modelo232NoneWithdrawRequest):
            none_statement, revision_id = withdraw_m232_none(
                request.ejercicio, at=now(), ports=ports, expected_revision_id=request.expected_revision_id
            )
            return Modelo232NoneStatementProjection.from_statement(none_statement, revision_id=revision_id)
        if isinstance(request, Modelo232TurnoverWithdrawRequest):
            turnover, revision_id = withdraw_m232_turnover(
                request.ejercicio, at=now(), ports=ports, expected_revision_id=request.expected_revision_id
            )
            return Modelo232TurnoverStatementProjection.from_statement(turnover, revision_id=revision_id)
    except Modelo232RelatedPartyRefusedError as exc:
        return exc.reason
    except Modelo232RelatedPartyRevisionConflictError:
        return "stale_revision"
    raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)


def _succeeded(
    operation_id: Modelo232RelatedPartyOperationId,
    request: Modelo232RelatedPartyWriteRequest,
    stated: _Stated,
) -> Modelo232RelatedPartyExecutionResult:
    return Modelo232RelatedPartyExecutionResult(
        operation_id=operation_id,
        outcome="success",
        profile_id=request.profile_id,
        ejercicio=request.ejercicio,
        operation=stated if isinstance(stated, Modelo232OperationProjection) else None,
        none_statement=stated if isinstance(stated, Modelo232NoneStatementProjection) else None,
        turnover_statement=stated if isinstance(stated, Modelo232TurnoverStatementProjection) else None,
    )


class Modelo232RelatedPartyExecutor:
    """Run the Modelo 232 statement write path and listing under exact-profile worker custody."""

    def __init__(self, ports_factory: Modelo232RelatedPartyPortsFactory, *, definition_id: str) -> None:
        """Bind the capability factory and the exact public operation id."""
        self._ports_factory = ports_factory
        self._definition_id = definition_id

    async def execute(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> str | OperationRefusalEvidence:
        """Run one listing, statement or withdrawal and retain its receipt-correlated outcome."""
        payload = self._validate_request(request, context)
        await context.events.phase(self._definition_id)
        operation_id = _OPERATION_IDS[self._definition_id]
        if isinstance(payload, Modelo232RelatedPartyListRequest):
            return await self._list(context, payload)
        if not isinstance(payload, Modelo232RelatedPartyWriteRequest):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)

        async def commit() -> str | OperationRefusalEvidence:
            async with context.cancellation.irreversible_section():
                await context.events.effect(OperationEffect.UNKNOWN)

                def work() -> _Stated | Modelo232RelatedPartyOperationRefusalReason:
                    return _write(payload, self._ports(context, payload.profile_id))

                stated = await asyncio.to_thread(work)
                if isinstance(stated, str):
                    return await self._persist_refusal(context, payload, operation_id, stated)
                reference = await context.operands.put(_succeeded(operation_id, payload, stated), written_at=now())
                await context.events.effect(OperationEffect.UPDATED)
                return reference

        return await await_cancellation_complete(commit(), task_name=f"m232-related-party-{operation_id}")

    def _validate_request(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> Modelo232RelatedPartyProfileRequest:
        request_type = M232_RELATED_PARTY_REQUEST_TYPES.get(self._definition_id)
        payload = request.payload
        if request_type is None or type(payload) is not request_type:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        if not isinstance(payload, Modelo232RelatedPartyProfileRequest):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        if request.definition_id != self._definition_id:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)
        return payload

    def _ports(self, context: OperationExecutorContext, profile_id: UUID) -> Modelo232RelatedPartyWritePorts:
        return self._ports_factory(profile_id=profile_id, operation=context.authority_operation)

    async def _list(self, context: OperationExecutorContext, request: Modelo232RelatedPartyListRequest) -> str:
        async def read() -> str:
            def work() -> Modelo232YearProjection:
                ports = self._ports(context, request.profile_id)
                view = ports.store.read_year(request.ejercicio)
                return Modelo232YearProjection(
                    guard_revision_id=view.guard_revision_id,
                    operations=tuple(
                        Modelo232OperationProjection.from_operation(operation, revision_id=revision_id)
                        for operation, revision_id in view.operations
                    ),
                    none_statements=tuple(
                        Modelo232NoneStatementProjection.from_statement(statement, revision_id=revision_id)
                        for statement, revision_id in view.nones
                    ),
                    turnover_statements=tuple(
                        Modelo232TurnoverStatementProjection.from_statement(statement, revision_id=revision_id)
                        for statement, revision_id in view.turnovers
                    ),
                    verdict=modelo_232_verdict(ports.store, request.ejercicio, operation=context.authority_operation),
                )

            year = await asyncio.to_thread(work)
            result = Modelo232RelatedPartyExecutionResult(
                operation_id="list",
                outcome="success",
                profile_id=request.profile_id,
                ejercicio=request.ejercicio,
                year=year,
            )
            reference = await context.operands.put(result, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return reference

        return await await_cancellation_complete(read(), task_name="m232-related-party-list")

    async def _persist_refusal(
        self,
        context: OperationExecutorContext,
        request: Modelo232RelatedPartyWriteRequest,
        operation_id: Modelo232RelatedPartyOperationId,
        reason: Modelo232RelatedPartyOperationRefusalReason,
    ) -> OperationRefusalEvidence:
        code = (
            M232_RELATED_PARTY_REVISION_REFUSAL_CODE if reason == "stale_revision" else M232_RELATED_PARTY_REFUSAL_CODE
        )
        words, language = served_m232_related_party_refusal_words(reason, error_code=code)
        refusal = Modelo232RelatedPartyRefusalProjection.model_validate(
            {
                "code": code,
                "reason": reason,
                "ejercicio": request.ejercicio,
                "refusal_words": words,
                "refusal_words_language": language,
            },
        )
        result = Modelo232RelatedPartyExecutionResult(
            operation_id=operation_id,
            outcome="refused",
            profile_id=request.profile_id,
            ejercicio=request.ejercicio,
            refusal=refusal,
        )
        detail_ref = await context.operands.put(result, written_at=now())
        await context.events.effect(OperationEffect.NONE)
        return OperationRefusalEvidence(refusal_code=code, detail_ref=detail_ref)
