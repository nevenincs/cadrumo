"""CLI presentation handlers for the Modelo 232 related-party statements.

Each handler builds the exact-profile request, runs it through the profile
worker and presents the stored payload. A refused write raises its typed
boundary error; no line names a counterparty's identifier.
"""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

import typer
from pydantic import ValidationError

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
    Modelo232RelatedPartyWriteRequest,
    Modelo232TurnoverStateRequest,
    Modelo232TurnoverWithdrawRequest,
)
from ...application.operations.public_scalar import PublicDecimal
from ...core.i18n.render import tr
from ...domain.modelos.m232_related_party import (
    Modelo232Direction,
    Modelo232Exclusion,
    Modelo232OperationKind,
    Modelo232TurnoverSource,
)
from .common import active_bucket_id_or_refuse, bad, emit_envelope
from .decimal_parsing import parse_decimal_amount
from .m232_related_party_results import (
    Modelo232NoneStatementResult,
    Modelo232OperationResult,
    Modelo232StatedPayload,
    Modelo232TurnoverStatementResult,
)
from .operation_ledger_m232_related_party import (
    list_m232_related_party,
    none_statement_payload,
    operation_payload,
    submit_m232_related_party_write,
    turnover_statement_payload,
)

__all__ = [
    "m232_related_party_list",
    "m232_related_party_state_none",
    "m232_related_party_state_operation",
    "m232_related_party_state_turnover",
    "m232_related_party_withdraw_none",
    "m232_related_party_withdraw_operation",
    "m232_related_party_withdraw_turnover",
]


def _amount(raw: str, *, label: str) -> PublicDecimal:
    return PublicDecimal(decimal=str(parse_decimal_amount(raw, label=label, signed=False)))


def _request[RequestT: Modelo232RelatedPartyWriteRequest | Modelo232RelatedPartyListRequest](
    build: Callable[[UUID], RequestT],
) -> RequestT:
    try:
        return build(UUID(active_bucket_id_or_refuse()))
    except ValidationError:
        raise bad(tr("cli.app.ledger.operaciones_vinculadas.invalid_input")) from None


def _line(row: Modelo232StatedPayload, identity: str) -> str:
    return f"{row.ejercicio}\t{identity}\t{row.state}\tstated_at={row.stated_at}\trevision={row.revision_id}"


def _emit_operation(
    ctx: typer.Context, definition_id: str, request: Modelo232RelatedPartyWriteRequest, outcome: str
) -> None:
    projection = submit_m232_related_party_write(ctx, request, definition_id=definition_id, outcome=outcome)
    if projection.operation is None:
        raise bad(tr("cli.app.ledger.operaciones_vinculadas.invalid_input"))
    result = Modelo232OperationResult(
        bucket_id=str(request.profile_id), operation=operation_payload(projection.operation)
    )
    row = result.operation
    emit_envelope(
        ctx,
        command=definition_id,
        result=result,
        lines=(
            f"bucket\t{result.bucket_id}",
            f"{_line(row, row.operation_id)}\t{row.operation_kind}\t{row.amount_eur}",
        ),
    )


def _emit_none(
    ctx: typer.Context, definition_id: str, request: Modelo232RelatedPartyWriteRequest, outcome: str
) -> None:
    projection = submit_m232_related_party_write(ctx, request, definition_id=definition_id, outcome=outcome)
    if projection.none_statement is None:
        raise bad(tr("cli.app.ledger.operaciones_vinculadas.invalid_input"))
    result = Modelo232NoneStatementResult(
        bucket_id=str(request.profile_id), none_statement=none_statement_payload(projection.none_statement)
    )
    row = result.none_statement
    emit_envelope(
        ctx,
        command=definition_id,
        result=result,
        lines=(f"bucket\t{result.bucket_id}", _line(row, row.statement_id)),
    )


def _emit_turnover(
    ctx: typer.Context, definition_id: str, request: Modelo232RelatedPartyWriteRequest, outcome: str
) -> None:
    projection = submit_m232_related_party_write(ctx, request, definition_id=definition_id, outcome=outcome)
    if projection.turnover_statement is None:
        raise bad(tr("cli.app.ledger.operaciones_vinculadas.invalid_input"))
    result = Modelo232TurnoverStatementResult(
        bucket_id=str(request.profile_id),
        turnover_statement=turnover_statement_payload(projection.turnover_statement),
    )
    row = result.turnover_statement
    emit_envelope(
        ctx,
        command=definition_id,
        result=result,
        lines=(f"bucket\t{result.bucket_id}", f"{_line(row, row.statement_id)}\t{row.turnover_eur}\t{row.source}"),
    )


def m232_related_party_state_operation(
    ctx: typer.Context,
    ejercicio: int,
    kind: Modelo232OperationKind,
    counterparty_name: str,
    counterparty_country: str,
    amount: str,
    counterparty_tax_id: str | None = None,
    tipo_vinculacion: str | None = None,
    tipo_operacion: str | None = None,
    metodo_valoracion: str | None = None,
    direction: Modelo232Direction | None = None,
    specific: bool = False,
    exclusion: Modelo232Exclusion | None = None,
    description: str | None = None,
    participation: str | None = None,
    parent_tax_id: str | None = None,
    parent_name: str | None = None,
    expected_guard_revision: str | None = None,
) -> None:
    """State one related-party or tax-haven operation of an ejercicio and present the stored row."""
    amount_eur = _amount(amount, label="--amount")
    participation_percent = None if participation is None else _amount(participation, label="--participation")
    request = _request(
        lambda profile_id: Modelo232OperationStateRequest(
            profile_id=profile_id,
            ejercicio=ejercicio,
            operation_kind=kind,
            counterparty_tax_id=counterparty_tax_id,
            counterparty_name=counterparty_name.strip(),
            counterparty_country=counterparty_country.strip(),
            tipo_vinculacion=tipo_vinculacion,
            tipo_operacion=tipo_operacion,
            valuation_method=metodo_valoracion,
            direction=direction,
            specific_operation=specific,
            amount_eur=amount_eur,
            exclusion=exclusion,
            description=description,
            participation_percent=participation_percent,
            parent_tax_id=parent_tax_id,
            parent_name=parent_name,
            expected_guard_revision_id=expected_guard_revision,
        )
    )
    _emit_operation(ctx, M232_RELATED_PARTY_OPERATION_STATE_OPERATION_DEFINITION_ID, request, "stated")


def m232_related_party_withdraw_operation(
    ctx: typer.Context, operation_id: str, ejercicio: int, expected_revision: str
) -> None:
    """Withdraw one stated operation, guarded by the revision a listing showed."""
    request = _request(
        lambda profile_id: Modelo232OperationWithdrawRequest(
            profile_id=profile_id,
            ejercicio=ejercicio,
            operation_id=operation_id,
            expected_revision_id=expected_revision,
        )
    )
    _emit_operation(ctx, M232_RELATED_PARTY_OPERATION_WITHDRAW_OPERATION_DEFINITION_ID, request, "withdrawn")


def m232_related_party_state_none(
    ctx: typer.Context, ejercicio: int, note: str, expected_guard_revision: str | None = None
) -> None:
    """State that an ejercicio had no related-party and no tax-haven operations."""
    request = _request(
        lambda profile_id: Modelo232NoneStateRequest(
            profile_id=profile_id,
            ejercicio=ejercicio,
            note=note.strip(),
            expected_guard_revision_id=expected_guard_revision,
        )
    )
    _emit_none(ctx, M232_RELATED_PARTY_NONE_STATE_OPERATION_DEFINITION_ID, request, "stated")


def m232_related_party_withdraw_none(ctx: typer.Context, ejercicio: int, expected_revision: str) -> None:
    """Withdraw the "none" statement of an ejercicio, guarded by the revision a listing showed."""
    request = _request(
        lambda profile_id: Modelo232NoneWithdrawRequest(
            profile_id=profile_id, ejercicio=ejercicio, expected_revision_id=expected_revision
        )
    )
    _emit_none(ctx, M232_RELATED_PARTY_NONE_WITHDRAW_OPERATION_DEFINITION_ID, request, "withdrawn")


def m232_related_party_state_turnover(
    ctx: typer.Context,
    ejercicio: int,
    cifra_negocios: str,
    source: Modelo232TurnoverSource,
    source_reference: str,
    expected_guard_revision: str | None = None,
) -> None:
    """State an ejercicio's cifra de negocios and where it was taken from."""
    turnover_eur = _amount(cifra_negocios, label="--cifra-negocios")
    request = _request(
        lambda profile_id: Modelo232TurnoverStateRequest(
            profile_id=profile_id,
            ejercicio=ejercicio,
            turnover_eur=turnover_eur,
            source=source,
            source_reference=source_reference.strip(),
            expected_guard_revision_id=expected_guard_revision,
        )
    )
    _emit_turnover(ctx, M232_RELATED_PARTY_TURNOVER_STATE_OPERATION_DEFINITION_ID, request, "stated")


def m232_related_party_withdraw_turnover(ctx: typer.Context, ejercicio: int, expected_revision: str) -> None:
    """Withdraw the turnover statement of an ejercicio, guarded by the revision a listing showed."""
    request = _request(
        lambda profile_id: Modelo232TurnoverWithdrawRequest(
            profile_id=profile_id, ejercicio=ejercicio, expected_revision_id=expected_revision
        )
    )
    _emit_turnover(ctx, M232_RELATED_PARTY_TURNOVER_WITHDRAW_OPERATION_DEFINITION_ID, request, "withdrawn")


def m232_related_party_list(ctx: typer.Context, ejercicio: int) -> None:
    """List everything stated for one ejercicio, with each revision and what the records decide."""
    request = _request(lambda profile_id: Modelo232RelatedPartyListRequest(profile_id=profile_id, ejercicio=ejercicio))
    result = list_m232_related_party(ctx, request)
    verdict = result.verdict
    emit_envelope(
        ctx,
        command=M232_RELATED_PARTY_LIST_OPERATION_DEFINITION_ID,
        result=result,
        lines=(
            f"bucket\t{result.bucket_id}",
            f"guard_revision\t{result.guard_revision_id}",
            *(f"operation\t{_line(row, row.operation_id)}\t{row.operation_kind}" for row in result.operations),
            *(f"none\t{_line(row, row.statement_id)}" for row in result.none_statements),
            *(f"turnover\t{_line(row, row.statement_id)}\t{row.turnover_eur}" for row in result.turnover_statements),
            *(() if verdict is None else (f"verdict\t{verdict.obligation}\t{verdict.obligation_label}",)),
        ),
    )
