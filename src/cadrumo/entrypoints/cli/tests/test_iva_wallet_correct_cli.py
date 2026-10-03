"""CLI surface tests for the registered IVA wallet correction verb."""

from __future__ import annotations

from typing import cast
from uuid import UUID

import pytest
import typer

from cadrumo.application.operations.public_period import PublicPeriod
from cadrumo.core.iva_compensation_provenance import IvaCompensationStateProvenance
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition
from cadrumo.core.period import Period

from .. import _modelo_iva_wallet_cli as handler
from .. import runtime_modelo_iva_wallet_correction as bridge
from .._modelo_payloads_m036 import IvaWalletCorrectResult
from ..runtime_registered_operation import RegisteredOperationCompletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("21212121-2121-4121-8121-212121212121")
_OPERATION_ID = "a" * 64
_PERIOD = Period.from_year_and_code(2024, "4T")


def _projection() -> bridge.ModeloIvaWalletCorrectionProjection:
    return bridge.ModeloIvaWalletCorrectionProjection(
        profile_id=_PROFILE,
        period=PublicPeriod.from_period(_PERIOD),
        taxpayer_nif="12345678Z",
        previous_amount="500.00",
        amount="1200.50",
        provenance=IvaCompensationStateProvenance.OPERATOR_CORRECTION,
        register_status=None,
        reason="typo in opening balance",
    )


def _read() -> bridge.ModeloIvaWalletCorrectionRead:
    projection = _projection()
    completion = RegisteredOperationCompletion(
        operation_id=_OPERATION_ID,
        projection=projection,
        effect=OperationEffect.UPDATED,
        terminal_condition=OperationTerminalCondition.SUCCEEDED,
    )
    return bridge.ModeloIvaWalletCorrectionRead(completion=completion, projection=projection)


def test_correct_command_requires_confirmation_before_submission(monkeypatch: pytest.MonkeyPatch) -> None:
    submitted: list[bool] = []
    monkeypatch.setattr(
        handler, "read_modelo_iva_wallet_correction_for_cli", lambda *_args, **_kwargs: submitted.append(True)
    )

    with pytest.raises(typer.BadParameter):
        handler.iva_wallet_correct_cmd(
            cast(typer.Context, cast(object, None)),
            filing_year=2024,
            period="4T",
            amount="1200.50",
            reason="fix",
            confirm=False,
        )

    assert submitted == []


def test_correct_command_emits_the_registered_projection_without_local_reads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    submissions: list[dict[str, object]] = []
    envelopes: list[dict[str, object]] = []

    def read(*_args: object, **kwargs: object) -> bridge.ModeloIvaWalletCorrectionRead:
        submissions.append(kwargs)
        return _read()

    monkeypatch.setattr(handler, "read_modelo_iva_wallet_correction_for_cli", read)
    monkeypatch.setattr(handler, "emit_envelope", lambda *_args, **kwargs: envelopes.append(kwargs))

    handler.iva_wallet_correct_cmd(
        cast(typer.Context, cast(object, None)),
        filing_year=2024,
        period="4T",
        amount="1200.50",
        reason="  typo in opening balance  ",
        confirm=True,
    )

    assert submissions == [{"period": _PERIOD, "amount": "1200.50", "reason": "typo in opening balance"}]
    assert len(envelopes) == 1
    envelope = envelopes[0]
    assert envelope["command"] == "modelo.iva_wallet.correct"
    result = cast(IvaWalletCorrectResult, envelope["result"])
    assert result.filing_year == 2024
    assert result.period == _PERIOD
    assert result.taxpayer_nif == "12345678Z"
    assert result.previous_amount == "500.00"
    assert result.amount == "1200.50"
    assert result.provenance is IvaCompensationStateProvenance.OPERATOR_CORRECTION
    assert result.register_status is None
    assert result.reason == "typo in opening balance"
    assert envelope["lines"] == [
        "operation\tmodelo.iva-wallet.correct",
        "filing_year\t2024",
        "period\t4T",
        "taxpayer_nif\t12345678Z",
        "previous_amount\t500.00",
        "amount\t1200.50",
        "provenance\toperator_correction",
        "register_status\t",
        "reason\ttypo in opening balance",
    ]


@pytest.mark.parametrize("amount", ["1e3", "NaN", "1.234"])
def test_correct_command_rejects_noncanonical_amount_before_submission(
    monkeypatch: pytest.MonkeyPatch,
    amount: str,
) -> None:
    submitted: list[bool] = []
    monkeypatch.setattr(
        handler, "read_modelo_iva_wallet_correction_for_cli", lambda *_args, **_kwargs: submitted.append(True)
    )

    with pytest.raises(typer.BadParameter):
        handler.iva_wallet_correct_cmd(
            cast(typer.Context, cast(object, None)),
            filing_year=2024,
            period="4T",
            amount=amount,
            reason="test",
            confirm=True,
        )

    assert submitted == []
