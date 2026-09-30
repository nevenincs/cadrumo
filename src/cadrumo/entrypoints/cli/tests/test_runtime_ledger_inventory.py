"""Inventory CLI bridge correlates worker receipts and keeps refusals explicit."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID

import pytest
import typer
from pydantic import BaseModel

from ....application.inventory.registered_operation import (
    INVENTORY_CREATE_OPERATION_DEFINITION_ID,
    INVENTORY_VALIDATION_REFUSAL_CODE,
    InventoryCreateProjection,
    InventoryCreateRequest,
    InventoryLedgerProjection,
    InventoryRefusalProjection,
)
from ....application.operations.public_scalar import PublicDecimal
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....domain.contribuyente.inventory.records import ValuationMethod
from .. import runtime_ledger_inventory as bridge
from ..errors import CliRefusedBoundaryError
from ..runtime_registered_operation import RegisteredOperationCompletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OPERATION_ID = "a" * 64


def _ctx() -> typer.Context:
    return cast(typer.Context, cast(object, None))


def _projection() -> InventoryCreateProjection:
    ledger = InventoryLedgerProjection(
        actividad_id="act-1",
        year=2026,
        valuation_method=ValuationMethod.FIFO,
        opening_stock=PublicDecimal(decimal="100.00"),
        opening_layers=(),
        closing_authority_fingerprints=None,
        period_movements=(),
        schema_version="3",
        bucket_event_ids=("e" * 64,),
    )
    return InventoryCreateProjection(
        outcome="created",
        profile_id=_PROFILE,
        ledger=ledger,
        bucket_event_ids=("e" * 64,),
    )


def _bind(
    monkeypatch: pytest.MonkeyPatch,
    *,
    completion: RegisteredOperationCompletion[Any],
    request: InventoryCreateRequest,
) -> list[BaseModel]:
    submitted: list[BaseModel] = []
    client = SimpleNamespace(profile_id=_PROFILE)
    monkeypatch.setattr(bridge, "require_profile_client", lambda *_args, **_kwargs: client)

    def submit(_client: object, payload: BaseModel, **kwargs: object):
        submitted.append(payload)
        assert payload is request
        assert kwargs["definition_id"] == INVENTORY_CREATE_OPERATION_DEFINITION_ID
        assert kwargs["subject_ref"] == profile_operation_subject(str(_PROFILE))
        assert kwargs["result_type"] is InventoryCreateProjection
        assert kwargs["request_version"] == kwargs["result_version"] == 1
        assert kwargs["timeout"] == 120
        assert kwargs["allow_refusal_detail"] is True
        return completion

    monkeypatch.setattr(bridge, "run_registered_operation", submit)
    return submitted


def _request() -> InventoryCreateRequest:
    return InventoryCreateRequest(
        profile_id=_PROFILE,
        actividad_id="act-1",
        year=2026,
        valuation_method="fifo",
        opening_stock=PublicDecimal(decimal="100.00"),
    )


def test_create_bridge_submits_captured_profile_request_and_legacy_result_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request()
    completion = RegisteredOperationCompletion(
        operation_id=_OPERATION_ID,
        projection=_projection(),
        effect=OperationEffect.UPDATED,
    )
    submitted = _bind(monkeypatch, completion=completion, request=request)
    monkeypatch.setattr(
        bridge,
        "require_active_bucket_id",
        lambda: pytest.fail("create must use the request's captured profile"),
    )

    observed, payload = bridge.create_inventory_ledger(_ctx(), request=request)

    assert submitted == [request]
    assert observed is completion
    assert payload.actividad_id == "act-1"
    assert payload.opening_stock == "100.00"
    assert payload.bucket_event_ids == ["e" * 64]


def test_create_bridge_preserves_registered_validation_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    request = _request()
    refusal = InventoryRefusalProjection(
        code=INVENTORY_VALIDATION_REFUSAL_CODE,
        reason="inventory_validation",
        actividad_id="act-1",
        year=2026,
        valuation_method="lifo",
    )
    completion = RegisteredOperationCompletion(
        operation_id=_OPERATION_ID,
        projection=InventoryCreateProjection(outcome="refused", profile_id=_PROFILE, refusal=refusal),
        effect=OperationEffect.NONE,
        terminal_condition=OperationTerminalCondition.REFUSED,
        refusal_code=INVENTORY_VALIDATION_REFUSAL_CODE,
    )
    _bind(monkeypatch, completion=completion, request=request)

    with pytest.raises(CliRefusedBoundaryError) as caught:
        bridge.create_inventory_ledger(_ctx(), request=request)

    assert caught.value.translated_message == "errors.refused.refused_profile_inventory_validation"
    assert caught.value.context == {
        "operation_id": _OPERATION_ID,
        "terminal_condition": "refused",
        "effect": "none",
        "refusal_code": INVENTORY_VALIDATION_REFUSAL_CODE,
        "reason": "inventory_validation",
        "actividad_id": "act-1",
        "year": "2026",
        "valuation_method": "lifo",
    }
