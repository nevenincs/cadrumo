"""IVA wallet pull routes through the exact-profile registered capture."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from uuid import UUID

import pytest
import typer

from ....application.live.iva_wallet_capture_operation import (
    IVA_WALLET_CAPTURE_DEFINITION_ID,
    IvaWalletCapturePublicResultV1,
    IvaWalletCaptureRequest,
)
from ....application.runtime.contracts import RuntimeRefusalCode
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....core.period import Period
from .. import _app_live as handler
from .. import runtime_iva_wallet_capture as bridge
from .._app_live_iva_wallet_payloads import IvaWalletPullResult
from ..errors import CliRefusedBoundaryError
from ..registered_operation_contracts import RegisteredOperationCompletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OPERATION_ID = "a" * 64
_PERIOD = Period.from_year_and_code(2025, "1T")
_CAPTURED_AT = datetime(2025, 2, 3, 4, 5, tzinfo=UTC)


def _projection() -> IvaWalletCapturePublicResultV1:
    return IvaWalletCapturePublicResultV1(
        taxpayer_ref="taxpayer-ref",
        target_year=2025,
        target_period="1T",
        observation_path="iva/wallet/2025/1T.json",
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


def _bind(
    monkeypatch: pytest.MonkeyPatch,
    projection: IvaWalletCapturePublicResultV1,
    *,
    effect: OperationEffect = OperationEffect.UPDATED,
    condition: OperationTerminalCondition = OperationTerminalCondition.SUCCEEDED,
    refusal_code: str | None = None,
) -> tuple[list[tuple[IvaWalletCaptureRequest, dict[str, object]]], list[UUID]]:
    monkeypatch.setattr(bridge, "require_active_bucket_id", lambda: str(_PROFILE))
    bound_profiles: list[UUID] = []

    def require_client(_ctx: object, *, expected_profile_id: UUID):
        bound_profiles.append(expected_profile_id)
        return object()

    monkeypatch.setattr(bridge, "require_profile_client", require_client)
    submitted: list[tuple[IvaWalletCaptureRequest, dict[str, object]]] = []

    def submit(_client: object, request: IvaWalletCaptureRequest, **kwargs: object):
        submitted.append((request, kwargs))
        return RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=projection,
            effect=effect,
            terminal_condition=condition,
            refusal_code=refusal_code,
        )

    monkeypatch.setattr(bridge, "run_registered_operation", submit)
    return submitted, bound_profiles


def _read() -> bridge.IvaWalletCaptureRead:
    return bridge.read_iva_wallet_capture_for_cli(
        cast(typer.Context, cast(object, None)),
        target_year=2025,
        target_period=_PERIOD,
        taxpayer_nif="X1234567L",
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
        target_year=2025,
        target_period="1T",
        taxpayer_nif="X1234567L",
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
        projection = projection.model_copy(update={"target_year": 2024})
    elif mismatch == "period":
        projection = projection.model_copy(update={"target_period": "2T"})
    elif mismatch == "effect":
        effect = OperationEffect.NONE
    elif mismatch == "terminal":
        condition = OperationTerminalCondition.REFUSED
    elif mismatch == "refusal":
        refusal_code = RuntimeRefusalCode.UNAVAILABLE.value
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
    assert error.value.context["reason"] == RuntimeRefusalCode.INVALID_FRAME.value


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
        year=2025,
        period="1T",
        taxpayer_nif="X1234567L",
    )

    assert len(envelopes) == 1
    envelope = envelopes[0]
    assert envelope["command"] == "app.live.iva_wallet.pull"
    result = cast(IvaWalletPullResult, envelope["result"])
    assert result.target_year == 2025
    assert result.target_period == _PERIOD
    assert result.taxpayer_ref == "taxpayer-ref"
    assert result.observation_path == "iva/wallet/2025/1T.json"
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
    assert "target_year=2025" in lines
    assert "target_period=2025 1T" in lines
    assert "row_count=3" in lines
    assert "captured_at=2025-02-03T04:05:00+00:00" in lines
