"""Read what a profile's records already say through the exact-profile registered operation."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

import typer

from cadrumo_client.commands.profile_binding import require_profile_client
from cadrumo_client.commands.registered_operation import run_registered_operation
from cadrumo_client.commands.registered_operation_errors import invalid_completion_error

from ...application.ledger.known_values_operation import (
    LEDGER_KNOWN_VALUES_OPERATION_DEFINITION_ID,
    KnownText,
    LedgerKnownValuesProjection,
    LedgerKnownValuesRequest,
)
from ...core.bucket_pointer import require_active_bucket_id
from ...core.ledger_known_values import LedgerKnownValueKind
from ...core.operations import OperationEffect, profile_operation_subject
from .common import emit_envelope


def read_ledger_known_values_for_cli(
    ctx: typer.Context,
    *,
    kinds: tuple[LedgerKnownValueKind, ...],
) -> LedgerKnownValuesProjection:
    """Submit the kinds and correlate the returned profile and no-effect receipt."""
    client = require_profile_client(ctx, expected_profile_id=UUID(require_active_bucket_id()))
    completed = run_registered_operation(
        client,
        LedgerKnownValuesRequest(profile_id=client.profile_id, kinds=kinds),
        definition_id=LEDGER_KNOWN_VALUES_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=LedgerKnownValuesProjection,
        request_version=1,
        result_version=1,
        timeout=60,
    )
    result = completed.projection
    if result.profile_id != client.profile_id or completed.effect is not OperationEffect.NONE:
        raise invalid_completion_error(completed)
    return result


def _text_lines(kind: LedgerKnownValueKind, rows: tuple[KnownText, ...]) -> list[str]:
    return [f"{kind.value}\t{row.text}\t{row.uses}\t{row.last_used.isoformat()}" for row in rows]


def ledger_known_values(ctx: typer.Context, kinds: Sequence[LedgerKnownValueKind] = ()) -> None:
    """List the values of the named kinds, or of all of them, most recent first."""
    from .ledger_results import LedgerKnownCounterpartyPayload, LedgerKnownTextPayload, LedgerKnownValuesResult

    projection = read_ledger_known_values_for_cli(ctx, kinds=tuple(kinds) or tuple(LedgerKnownValueKind))
    sections = (
        (LedgerKnownValueKind.DESCRIPTION, projection.descriptions),
        (LedgerKnownValueKind.GROUP_LABEL, projection.group_labels),
        (LedgerKnownValueKind.M210_PAYER, projection.m210_payers),
        (LedgerKnownValueKind.M210_ASSET, projection.m210_assets),
        (LedgerKnownValueKind.ASSET_REFERENCE, projection.asset_references),
    )
    lines = [
        *(
            "\t".join(
                (
                    LedgerKnownValueKind.COUNTERPARTY.value,
                    row.name,
                    row.tax_id or "-",
                    row.country or "-",
                    str(row.uses),
                    row.last_used.isoformat(),
                )
            )
            for row in projection.counterparties
        ),
        *(line for kind, rows in sections for line in _text_lines(kind, rows)),
        *(f"truncated\t{kind.value}" for kind in projection.truncated),
    ]

    def texts(rows: tuple[KnownText, ...]) -> list[LedgerKnownTextPayload]:
        return [
            LedgerKnownTextPayload(
                text=row.text,
                uses=row.uses,
                last_used=row.last_used.isoformat(),
                counterparty=row.counterparty,
            )
            for row in rows
        ]

    emit_envelope(
        ctx,
        command="ledger.known-values",
        result=LedgerKnownValuesResult(
            bucket_id=str(projection.profile_id),
            counterparties=[
                LedgerKnownCounterpartyPayload(
                    name=row.name,
                    tax_id=row.tax_id,
                    country=row.country,
                    identification_state=row.identification_state,
                    uses=row.uses,
                    last_used=row.last_used.isoformat(),
                )
                for row in projection.counterparties
            ],
            descriptions=texts(projection.descriptions),
            group_labels=texts(projection.group_labels),
            m210_payers=texts(projection.m210_payers),
            m210_assets=texts(projection.m210_assets),
            asset_references=texts(projection.asset_references),
            truncated=[kind.value for kind in projection.truncated],
        ),
        lines=lines,
    )
