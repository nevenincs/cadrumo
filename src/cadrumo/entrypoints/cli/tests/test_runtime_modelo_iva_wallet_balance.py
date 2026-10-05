"""The IVA wallet balance CLI bridge verifies its registered result and receipt."""

from __future__ import annotations

from typing import cast
from uuid import UUID

import pytest
import typer

from ....application.modelo.iva_wallet_balance_operation import (
    MODELO_IVA_WALLET_BALANCE_OPERATION_DEFINITION_ID,
    ModeloIvaWalletBalanceProjection,
    ModeloIvaWalletBalanceRequest,
)
from ....application.runtime.contracts import RuntimeRefusalCode
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .. import runtime_modelo_iva_wallet_balance as bridge
from ..errors import CliRefusedBoundaryError
from ..registered_operation_contracts import RegisteredOperationCompletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("21212121-2121-4121-8121-212121212121")
_OPERATION_ID = "b" * 64


def _projection() -> ModeloIvaWalletBalanceProjection:
    return ModeloIvaWalletBalanceProjection(
        profile_id=_PROFILE,
        as_of_year=2024,
        total_balance="500.00",
        active_balance="500.00",
        expired_balance="0.00",
        lot_count=1,
        next_expiry_year=2028,
        unallocated_applied_amount="0.00",
    )


def _bind(
    monkeypatch: pytest.MonkeyPatch,
    projection: ModeloIvaWalletBalanceProjection,
    *,
    effect: OperationEffect = OperationEffect.NONE,
    condition: OperationTerminalCondition = OperationTerminalCondition.SUCCEEDED,
    refusal_code: str | None = None,
) -> tuple[list[tuple[ModeloIvaWalletBalanceRequest, dict[str, object]]], list[UUID]]:
    monkeypatch.setattr(bridge, "require_active_bucket_id", lambda: str(_PROFILE))
    bound_profiles: list[UUID] = []

    def require_client(_ctx: object, *, expected_profile_id: UUID):
        bound_profiles.append(expected_profile_id)
        return object()

    monkeypatch.setattr(bridge, "require_profile_client", require_client)
    submitted: list[tuple[ModeloIvaWalletBalanceRequest, dict[str, object]]] = []

    def submit(_client: object, request: ModeloIvaWalletBalanceRequest, **kwargs: object):
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


def _read() -> bridge.ModeloIvaWalletBalanceRead:
    return bridge.read_modelo_iva_wallet_balance_for_cli(
        cast(typer.Context, cast(object, None)),
        as_of_year=2024,
    )


def test_bridge_submits_exact_profile_and_year_and_accepts_only_none_effect_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    submitted, bound_profiles = _bind(monkeypatch, _projection())

    read = _read()

    assert read.completion.operation_id == _OPERATION_ID
    assert read.projection == _projection()
    assert bound_profiles == [_PROFILE]
    assert len(submitted) == 1
    request, options = submitted[0]
    assert request == ModeloIvaWalletBalanceRequest(profile_id=_PROFILE, as_of_year=2024)
    assert options["definition_id"] == MODELO_IVA_WALLET_BALANCE_OPERATION_DEFINITION_ID
    assert options["subject_ref"] == profile_operation_subject(str(_PROFILE))
    assert options["result_type"] is ModeloIvaWalletBalanceProjection
    assert options["request_version"] == 1
    assert options["result_version"] == 1


@pytest.mark.parametrize("mismatch", ["profile", "year", "effect", "terminal", "refusal"])
def test_result_or_receipt_mismatch_refuses_with_operation_correlation(
    monkeypatch: pytest.MonkeyPatch,
    mismatch: str,
) -> None:
    projection = _projection()
    effect = OperationEffect.NONE
    condition = OperationTerminalCondition.SUCCEEDED
    refusal_code = None
    if mismatch == "profile":
        projection = projection.model_copy(update={"profile_id": UUID("33333333-3333-4333-8333-333333333333")})
    elif mismatch == "year":
        projection = projection.model_copy(update={"as_of_year": 2025})
    elif mismatch == "effect":
        effect = OperationEffect.UPDATED
    elif mismatch == "terminal":
        condition = OperationTerminalCondition.REFUSED
    elif mismatch == "refusal":
        refusal_code = RuntimeRefusalCode.UNAVAILABLE.value
    _bind(monkeypatch, projection, effect=effect, condition=condition, refusal_code=refusal_code)

    with pytest.raises(CliRefusedBoundaryError) as refused:
        _read()

    assert refused.value.context is not None
    assert refused.value.context["operation_id"] == _OPERATION_ID
    assert refused.value.context["reason"] == RuntimeRefusalCode.INVALID_FRAME.value
