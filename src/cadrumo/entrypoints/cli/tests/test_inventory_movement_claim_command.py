"""The ledger-row statement command submits its request and renders a refusal through the served catalogue."""

from __future__ import annotations

import json
from uuid import UUID

import pytest
import typer
from typer.core import TyperCommand

from cadrumo_client.commands.errors import CliRefusedBoundaryError
from cadrumo_client.commands.registered_operation_contracts import RegisteredOperationCompletion

from ....application.inventory.registered_projections import (
    InventoryLedgerChangeProjection,
    InventoryLedgerProjection,
    InventoryRefusalProjection,
)
from ....application.inventory.registered_requests import (
    INVENTORY_MOVEMENT_CLAIM_OPERATION_DEFINITION_ID,
    InventoryMovementClaimRequest,
)
from ....application.operations.public_scalar import PublicDecimal
from ....core.config import override_settings
from ....core.i18n.render import tr
from ....core.operations import OperationEffect, OperationTerminalCondition
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.contribuyente.inventory.corrections import inventory_refusal_key
from ....domain.contribuyente.inventory.records import PurchaseLedgerRow, ValuationMethod
from .. import common
from .. import ledger_inventory_commands as commands
from .. import operation_ledger_inventory as bridge

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = "5aa00000-0000-4000-8000-0000000000aa"
_YEAR = filing_year_envelope().horizon
_TRANSACTION = "ab" * 32


def _ledger() -> InventoryLedgerProjection:
    return InventoryLedgerProjection(
        actividad_id="act-1",
        year=_YEAR,
        valuation_method=ValuationMethod.FIFO,
        opening_stock=PublicDecimal(decimal="100.00"),
        opening_layers=(),
        closing_authority_fingerprints=None,
        period_movements=(),
        schema_version="3",
        advisories=(),
    )


def _quiet(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(commands, "active_bucket_id_or_refuse", lambda: _PROFILE)
    monkeypatch.setattr(common, "active_profile_label", lambda: None)
    monkeypatch.setattr(common, "common_is_metadata_invocation", lambda _ctx: False)
    monkeypatch.setattr(
        "cadrumo.application.operator_output.sandbox_notice.sandbox_notice_for_active_bucket", lambda: None
    )


def test_the_claim_command_submits_the_statement_and_prints_the_applied_result(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _quiet(monkeypatch)
    seen: list[tuple[str, InventoryMovementClaimRequest]] = []

    def run(_ctx: object, request: InventoryMovementClaimRequest, *, definition_id: str, **_kwargs: object):
        seen.append((definition_id, request))
        projection = InventoryLedgerChangeProjection(
            outcome="applied", profile_id=UUID(_PROFILE), ledger=_ledger(), bucket_event_ids=("e" * 32,)
        )
        return RegisteredOperationCompletion(
            operation_id="a" * 64, projection=projection, effect=OperationEffect.UPDATED
        )

    monkeypatch.setattr(bridge, "run", run)
    ctx = typer.Context(TyperCommand("claim"), obj={"format": "json"})

    with override_settings(cadrumo_output_language="en"):
        commands.inventory_movement_claim(
            ctx, "act-1", _YEAR, "claim-1", "BUY-1", PurchaseLedgerRow.CLAIMED, _TRANSACTION
        )

    ((definition_id, request),) = seen
    assert definition_id == INVENTORY_MOVEMENT_CLAIM_OPERATION_DEFINITION_ID
    assert request.movement_id == "BUY-1"
    assert request.ledger_row is PurchaseLedgerRow.CLAIMED
    assert request.claimed_transaction_id == _TRANSACTION
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["command"] == "ledger.inventory.movement.claim"
    assert envelope["result"]["outcome"] == "applied"


def test_a_refused_claim_surfaces_as_the_catalogue_sentence_of_its_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    _quiet(monkeypatch)
    reason = "claimed_transaction_amount_mismatch"

    def run(_ctx: object, _request: object, **_kwargs: object):
        refusal = InventoryRefusalProjection(
            code="REFUSED_INVENTORY_SERVICE_INPUT",
            reason=reason,
            actividad_id="act-1",
            year=_YEAR,
            movement_id="BUY-1",
            reason_key=inventory_refusal_key(reason),
        )
        return RegisteredOperationCompletion(
            operation_id="a" * 64,
            projection=InventoryLedgerChangeProjection(outcome="refused", profile_id=UUID(_PROFILE), refusal=refusal),
            effect=OperationEffect.NONE,
            terminal_condition=OperationTerminalCondition.REFUSED,
            refusal_code="REFUSED_INVENTORY_SERVICE_INPUT",
        )

    monkeypatch.setattr(bridge, "run", run)
    ctx = typer.Context(TyperCommand("claim"), obj={"format": "json"})

    with (
        override_settings(cadrumo_output_language="en"),
        pytest.raises(CliRefusedBoundaryError) as refused,
    ):
        commands.inventory_movement_claim(
            ctx, "act-1", _YEAR, "claim-1", "BUY-1", PurchaseLedgerRow.CLAIMED, _TRANSACTION
        )

    assert refused.value.translated_message == inventory_refusal_key(reason)
    assert refused.value.context is not None
    assert refused.value.context["movement_id"] == "BUY-1"


@pytest.mark.parametrize(
    ("ledger_row", "transaction_id"),
    [
        (PurchaseLedgerRow.CLAIMED, None),
        (PurchaseLedgerRow.NONE, _TRANSACTION),
        (PurchaseLedgerRow.UNSTATED, _TRANSACTION),
    ],
)
def test_a_transaction_is_named_exactly_when_the_purchase_claims_one(
    monkeypatch: pytest.MonkeyPatch, ledger_row: PurchaseLedgerRow, transaction_id: str | None
) -> None:
    _quiet(monkeypatch)
    ctx = typer.Context(TyperCommand("claim"), obj={"format": "json"})

    with override_settings(cadrumo_output_language="en"), pytest.raises(typer.BadParameter) as refused:
        commands.inventory_movement_claim(ctx, "act-1", _YEAR, "claim-1", "BUY-1", ledger_row, transaction_id)

    with override_settings(cadrumo_output_language="en"):
        expected = tr("cli.app.ledger.inventory.claim_transaction_mismatch")
    assert str(refused.value.message) == expected
    assert "%{" not in expected
