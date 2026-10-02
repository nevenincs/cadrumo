"""CLI surface tests for the registered IVA-wallet balance read."""

from __future__ import annotations

from typing import cast
from uuid import UUID

import pytest
import typer

from ....core.operations import OperationEffect, OperationTerminalCondition
from .. import _modelo_iva_wallet_cli as handler
from .. import runtime_modelo_iva_wallet_balance as bridge
from .._modelo_iva_wallet_payloads import IvaWalletBalanceResult
from ..runtime_registered_operation import RegisteredOperationCompletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("21212121-2121-4121-8121-212121212121")
_OPERATION_ID = "a" * 64


def _read() -> bridge.ModeloIvaWalletBalanceRead:
    projection = bridge.ModeloIvaWalletBalanceProjection(
        profile_id=_PROFILE,
        as_of_year=2028,
        total_balance="300.00",
        active_balance="200.00",
        expired_balance="100.00",
        lot_count=2,
        next_expiry_year=2029,
        unallocated_applied_amount="0.00",
    )
    completion = RegisteredOperationCompletion(
        operation_id=_OPERATION_ID,
        projection=projection,
        effect=OperationEffect.NONE,
        terminal_condition=OperationTerminalCondition.SUCCEEDED,
    )
    return bridge.ModeloIvaWalletBalanceRead(completion=completion, projection=projection)


def test_balance_command_emits_the_registered_projection_without_local_reads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    submissions: list[dict[str, object]] = []
    envelopes: list[dict[str, object]] = []

    def read(*_args: object, **kwargs: object) -> bridge.ModeloIvaWalletBalanceRead:
        submissions.append(kwargs)
        return _read()

    monkeypatch.setattr(handler, "read_modelo_iva_wallet_balance_for_cli", read)
    monkeypatch.setattr(handler, "emit_envelope", lambda *_args, **kwargs: envelopes.append(kwargs))

    handler.iva_wallet_balance_cmd(cast(typer.Context, cast(object, None)), as_of_year=2028)

    assert submissions == [{"as_of_year": 2028}]
    assert len(envelopes) == 1
    envelope = envelopes[0]
    assert envelope["command"] == "modelo.iva_wallet.balance"
    result = cast(IvaWalletBalanceResult, envelope["result"])
    assert result.as_of_year == 2028
    assert result.total_balance == "300.00"
    assert result.active_balance == "200.00"
    assert result.expired_balance == "100.00"
    assert result.lot_count == 2
    assert result.next_expiry_year == 2029
    assert result.unallocated_applied_amount == "0.00"
    assert envelope["lines"] == [
        "operation\tmodelo.iva-wallet.balance",
        "as_of_year\t2028",
        "total_balance\t300.00",
        "active_balance\t200.00",
        "expired_balance\t100.00",
        "lot_count\t2",
        "next_expiry_year\t2029",
        "unallocated_applied_amount\t0.00",
    ]
