"""IVA wallet pull routes through the exact-profile registered capture."""

from __future__ import annotations

from datetime import UTC, datetime
from functools import partial
from typing import cast
from uuid import UUID

import pytest
import typer

from cadrumo_client.commands.errors import CliRefusedBoundaryError
from cadrumo_client.commands.registered_operation_contracts import RegisteredOperationCompletion
from cadrumo_client.contracts.contracts import RefusalCode

from ....application.live.iva_wallet_capture_operation import (
    IVA_WALLET_CAPTURE_DEFINITION_ID,
    IvaWalletCapturePublicResultV1,
    IvaWalletCaptureRequest,
)
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....core.period import Period
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from .. import app_live_iva_commands as handler
from .. import operation_iva_wallet_capture as bridge
from ..app_live_iva_wallet_results import IvaWalletPullResult
from .operation_bridge_support import bind_profile_submission

_YEAR = filing_year_envelope().horizon


pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OPERATION_ID = "a" * 64
_PERIOD = Period.from_year_and_code(_YEAR, "1T")
_CAPTURED_AT = datetime(_YEAR, 2, 3, 4, 5, tzinfo=UTC)


def _projection() -> IvaWalletCapturePublicResultV1:
    return IvaWalletCapturePublicResultV1(
        taxpayer_ref="taxpayer-ref",
        target_year=_YEAR,
        target_period="1T",
        observation_path=f"iva/wallet/{_YEAR}/1T.json",
        decision_key="wallet-decision-key",
        row_count=3,
        total_pending="120.00",
        selected_authority="aeat",
        selected_amount="120.00",
        local_recurrence_amount="100.00",
        divergence="divergent",
        blocked=True,
        captured_at=_CAPTURED_AT,
    )


_bind = partial(
    bind_profile_submission,
    bridge=bridge,
    operation_id=_OPERATION_ID,
    profile_id=_PROFILE,
    effect=OperationEffect.UPDATED,
)


def _read() -> bridge.IvaWalletCaptureRead:
    return bridge.read_iva_wallet_capture_for_cli(
        cast(typer.Context, cast(object, None)),
        target_year=_YEAR,
        target_period=_PERIOD,
        taxpayer_nif="X0001500M",
    )


def test_registered_wallet_capture_uses_exact_profile_and_period_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    submitted, bound_profiles = _bind(monkeypatch, _projection())

    read = _read()

    assert read.completion.operation_id == _OPERATION_ID
    assert read.projection == _projection()
    assert bound_profiles == [_PROFILE]
    assert len(submitted) == 1
    request, options = submitted[0]
    assert request == IvaWalletCaptureRequest(
        profile_id=_PROFILE,
        target_year=_YEAR,
        target_period="1T",
        taxpayer_nif="X0001500M",
    )
    assert options["definition_id"] == IVA_WALLET_CAPTURE_DEFINITION_ID
    assert options["subject_ref"] == profile_operation_subject(str(_PROFILE))
    assert options["result_type"] is IvaWalletCapturePublicResultV1
    assert options["request_version"] == 1
    assert options["result_version"] == 1


@pytest.mark.parametrize("mismatch", ["year", "period", "effect", "terminal", "refusal"])
def test_mismatched_period_or_receipt_refuses_with_correlated_operation(
    monkeypatch: pytest.MonkeyPatch,
    mismatch: str,
) -> None:
    projection = _projection()
    effect = OperationEffect.UPDATED
    condition = OperationTerminalCondition.SUCCEEDED
    refusal_code = None
    if mismatch == "year":
        projection = projection.model_copy(update={"target_year": _YEAR - 1})
    elif mismatch == "period":
        projection = projection.model_copy(update={"target_period": "2T"})
    elif mismatch == "effect":
        effect = OperationEffect.NONE
    elif mismatch == "terminal":
        condition = OperationTerminalCondition.REFUSED
    elif mismatch == "refusal":
        refusal_code = RefusalCode.UNAVAILABLE.value
    _bind(
        monkeypatch,
        projection,
        effect=effect,
        condition=condition,
        refusal_code=refusal_code,
    )

    with pytest.raises(CliRefusedBoundaryError) as error:
        _read()

    assert error.value.context is not None
    assert error.value.context["operation_id"] == _OPERATION_ID
    assert error.value.context["reason"] == RefusalCode.INVALID_FRAME.value


def test_wallet_pull_command_emits_existing_payload_and_text_from_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    projection = _projection()
    completion = RegisteredOperationCompletion(
        operation_id=_OPERATION_ID,
        projection=projection,
        effect=OperationEffect.UPDATED,
    )
    read = bridge.IvaWalletCaptureRead(completion=completion, projection=projection)
    monkeypatch.setattr(handler, "emit_live_auth_preflight", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(bridge, "read_iva_wallet_capture_for_cli", lambda *_args, **_kwargs: read)
    envelopes: list[dict[str, object]] = []
    monkeypatch.setattr(handler, "emit_envelope", lambda *_args, **kwargs: envelopes.append(kwargs))

    handler.iva_wallet_pull_cmd(
        cast(typer.Context, cast(object, None)),
        year=_YEAR,
        period="1T",
        taxpayer_nif="X0001500M",
    )

    assert len(envelopes) == 1
    envelope = envelopes[0]
    assert envelope["command"] == "app.live.iva_wallet.pull"
    result = cast(IvaWalletPullResult, envelope["result"])
    assert result.target_year == _YEAR
    assert result.target_period == _PERIOD
    assert result.taxpayer_ref == "taxpayer-ref"
    assert result.observation_path == f"iva/wallet/{_YEAR}/1T.json"
    assert result.decision_key == "wallet-decision-key"
    assert result.row_count == 3
    assert result.total_pending == "120.00"
    assert result.selected_authority == "aeat"
    assert result.selected_amount == "120.00"
    assert result.local_recurrence_amount == "100.00"
    assert result.divergence == "divergent"
    assert result.blocked is True
    assert result.captured_at == _CAPTURED_AT.isoformat()
    lines = envelope["lines"]
    assert isinstance(lines, tuple)
    assert f"target_year={_YEAR}" in lines
    assert f"target_period={_YEAR} 1T" in lines
    assert "row_count=3" in lines
    assert f"captured_at={datetime(_YEAR, 2, 3, 4, 5, tzinfo=UTC).isoformat()}" in lines
