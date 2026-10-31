"""Worker inventory advisories reach the shared CLI notice channel in both formats."""

from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import UUID

import pytest
import typer
from typer.core import TyperCommand

from cadrumo_client.commands.registered_operation_contracts import RegisteredOperationCompletion

from ....application.inventory.registered_projections import (
    InventoryLedgerProjection,
    InventoryListProjection,
    InventoryListRowProjection,
    inventory_advisories,
)
from ....application.inventory.registered_requests import InventoryRestoreRequest
from ....application.operations.public_scalar import PublicDecimal
from ....core.config import override_settings
from ....core.operations import OperationEffect
from ....domain.contribuyente.inventory.records import MovementKind, ValuationMethod
from .. import common
from .. import ledger_inventory_commands as commands
from .. import operation_ledger_inventory as bridge
from ..ledger_business_payloads import (
    InventoryCreateResult,
    InventoryInspectResult,
    InventoryLedgerChangeResult,
    InventoryListResult,
    InventoryMovementAddResult,
)
from ..operation_ledger_inventory import _ledger_payload_json

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = "5aa00000-0000-4000-8000-0000000000aa"
_CODE = "ledger.inventory.retired_book_leaves_year_unresolved"


def _ledger() -> InventoryLedgerProjection:
    return InventoryLedgerProjection(
        actividad_id="act-1",
        year=2026,
        valuation_method=ValuationMethod.FIFO,
        opening_stock=PublicDecimal(decimal="100.00"),
        opening_layers=(),
        closing_authority_fingerprints=None,
        period_movements=(),
        schema_version="3",
        advisories=inventory_advisories(year=2026, leaves_year_unresolved=True),
    )


def test_cli_payload_excludes_advisories_without_mutating_the_worker_projection() -> None:
    ledger = _ledger()
    payload = InventoryInspectResult.model_validate_json(_ledger_payload_json(ledger))
    assert ledger.advisories
    assert "advisories" not in payload.model_dump()
    assert payload.opening_stock == "100.00"


def test_inventory_list_bridge_separates_row_state_from_its_worker_advisories(monkeypatch: pytest.MonkeyPatch) -> None:
    ledger = _ledger()
    row = InventoryListRowProjection(
        actividad_id=ledger.actividad_id,
        year=ledger.year,
        valuation_method=ledger.valuation_method,
        opening_stock=ledger.opening_stock,
        movement_count=0,
        advisories=ledger.advisories,
    )
    completion = RegisteredOperationCompletion(
        operation_id="a" * 64,
        projection=InventoryListProjection(profile_id=UUID(_PROFILE), rows=(row,)),
        effect=OperationEffect.NONE,
    )
    monkeypatch.setattr(bridge, "_run", lambda *_args, **_kwargs: completion)
    monkeypatch.setattr(bridge, "require_active_bucket_id", lambda: _PROFILE)
    observed, payload = bridge.read_inventory_catalogue(typer.Context(TyperCommand("inventory")))
    assert observed.projection.rows[0].advisories == ledger.advisories
    assert "advisories" not in payload.rows[0].model_dump()


def test_a_ledger_without_worker_advisories_emits_no_warning() -> None:
    assert commands._inventory_notices(_ledger().model_copy(update={"advisories": ()})) == []


@pytest.mark.parametrize("format_name", ["json", "text"])
@pytest.mark.parametrize("operation", ["list", "create", "movement", "change", "inspect"])
def test_inventory_handlers_emit_the_worker_warning_with_activity_and_year(
    operation: str, format_name: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    ledger = _ledger()
    row = InventoryListRowProjection(
        actividad_id=ledger.actividad_id,
        year=ledger.year,
        valuation_method=ledger.valuation_method,
        opening_stock=ledger.opening_stock,
        movement_count=0,
        advisories=ledger.advisories,
    )
    completion = SimpleNamespace(projection=SimpleNamespace(ledger=ledger, rows=(row,)))
    payloads = {
        "list": InventoryListResult(
            bucket_id=_PROFILE,
            rows=[InventoryInspectResult.model_validate_json(_ledger_payload_json(ledger)).model_dump(mode="json")],
            count=1,
        ),
        "create": InventoryCreateResult.model_validate_json(_ledger_payload_json(ledger)),
        "movement": InventoryMovementAddResult.model_validate_json(_ledger_payload_json(ledger)),
        "change": InventoryLedgerChangeResult.model_validate_json(_ledger_payload_json(ledger, outcome="applied")),
        "inspect": InventoryInspectResult.model_validate_json(_ledger_payload_json(ledger)),
    }
    bridge = {
        "list": "read_inventory_catalogue",
        "create": "create_inventory_ledger",
        "movement": "add_inventory_movement",
        "change": "apply_inventory_ledger_change",
        "inspect": "inspect_inventory_ledger",
    }[operation]
    monkeypatch.setattr(commands, bridge, lambda *_args, **_kwargs: (completion, payloads[operation]))
    monkeypatch.setattr(commands, "_inventory_bucket_id", lambda: _PROFILE)
    monkeypatch.setattr(common, "active_profile_label", lambda: None)
    monkeypatch.setattr(common, "_is_metadata_invocation", lambda _ctx: False)
    monkeypatch.setattr(
        "cadrumo.application.operator_output.sandbox_notice.sandbox_notice_for_active_bucket", lambda: None
    )
    ctx = typer.Context(TyperCommand("inventory"), obj={"format": format_name})
    with override_settings(cadrumo_output_language="en"):
        if operation == "list":
            commands.inventory_list(ctx)
        elif operation == "create":
            commands.inventory_create(ctx, "act-1", 2026, "fifo", "100.00")
        elif operation == "movement":
            commands.inventory_movement_add(ctx, "act-1", 2026, "move-1", "2026-01-01", MovementKind.PURCHASE, "1")
        elif operation == "change":
            commands._emit_ledger_change(
                ctx,
                command="ledger.inventory.restore",
                request=InventoryRestoreRequest(
                    profile_id=UUID(_PROFILE), actividad_id="act-1", year=2026, correction_id="correction-1"
                ),
            )
        else:
            commands.inventory_inspect(ctx, "act-1", 2026)
    output = capsys.readouterr().out
    if format_name == "json":
        envelope = json.loads(output)
        assert envelope["status"] == "warning"
        assert "advisories" not in envelope["result"]
        if operation == "list":
            assert "advisories" not in envelope["result"]["rows"][0]
        (notice,) = envelope["notices"]
        assert notice["code"] == _CODE
        assert notice["severity"] == "warning"
        assert notice["context"] == {"actividad_id": "act-1", "year": "2026"}
        assert "2026" in notice["message"] and "%{" not in notice["message"]
    else:
        assert f"notice\t{_CODE}\t" in output
        assert "2026" in output
        assert "advisory\t" not in output
