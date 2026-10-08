"""The IVA-wallet correction CLI submits and verifies its registered result."""

from __future__ import annotations

from typing import cast
from uuid import UUID

import pytest
import typer

from ....application.modelo.iva_wallet_correction_operation import (
    MODELO_IVA_WALLET_CORRECTION_OPERATION_DEFINITION_ID,
    ModeloIvaWalletCorrectionProjection,
    ModeloIvaWalletCorrectionRequest,
)
from ....application.operations.public_period import PublicPeriod
from ....application.runtime.contracts import RuntimeRefusalCode
from ....core.iva_compensation_provenance import IvaCompensationStateProvenance
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....core.period import Period
from .. import runtime_modelo_iva_wallet_correction as bridge
from .. import runtime_profile_operation as profile_operation
from ..errors import CliRefusedBoundaryError
from ..registered_operation_contracts import RegisteredOperationCompletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("21212121-2121-4121-8121-212121212121")
_OPERATION_ID = "b" * 64
_PERIOD = Period.from_year_and_code(2024, "4T")


def _projection() -> ModeloIvaWalletCorrectionProjection:
    return ModeloIvaWalletCorrectionProjection(
        profile_id=_PROFILE,
        period=PublicPeriod.from_period(_PERIOD),
        taxpayer_nif="12345678Z",
        previous_amount="500.00",
        amount="1200.50",
        provenance=IvaCompensationStateProvenance.OPERATOR_CORRECTION,
        register_status=None,
        reason="corrected opening balance",
    )


def _bind(
    monkeypatch: pytest.MonkeyPatch,
    projection: ModeloIvaWalletCorrectionProjection,
    *,
    effect: OperationEffect = OperationEffect.UPDATED,
    condition: OperationTerminalCondition = OperationTerminalCondition.SUCCEEDED,
    refusal_code: str | None = None,
) -> tuple[list[tuple[ModeloIvaWalletCorrectionRequest, dict[str, object]]], list[UUID]]:
    monkeypatch.setattr(bridge, "require_active_bucket_id", lambda: str(_PROFILE))
    bound_profiles: list[UUID] = []

    def require_client(_ctx: object, *, expected_profile_id: UUID):
        bound_profiles.append(expected_profile_id)
        return object()

    monkeypatch.setattr(bridge, "require_profile_client", require_client)
    submitted: list[tuple[ModeloIvaWalletCorrectionRequest, dict[str, object]]] = []

    def submit(_client: object, request: ModeloIvaWalletCorrectionRequest, **kwargs: object):
        submitted.append((request, kwargs))
        return RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=projection,
            effect=effect,
            terminal_condition=condition,
            refusal_code=refusal_code,
        )

    monkeypatch.setattr(profile_operation, "run_registered_operation", submit)
    return submitted, bound_profiles


def _read() -> bridge.ModeloIvaWalletCorrectionRead:
    return bridge.read_modelo_iva_wallet_correction_for_cli(
        cast(typer.Context, cast(object, None)),
        period=_PERIOD,
        amount="1200.50",
        reason="corrected opening balance",
    )


def test_bridge_submits_to_exact_profile_and_accepts_only_matching_updated_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    submitted, bound_profiles = _bind(monkeypatch, _projection())

    read = _read()

    assert read.completion.operation_id == _OPERATION_ID
    assert read.projection == _projection()
    assert bound_profiles == [_PROFILE]
    assert len(submitted) == 1
    request, options = submitted[0]
    assert request == ModeloIvaWalletCorrectionRequest(
        profile_id=_PROFILE,
        period=PublicPeriod.from_period(_PERIOD),
        amount="1200.50",
        reason="corrected opening balance",
    )
    assert options["definition_id"] == MODELO_IVA_WALLET_CORRECTION_OPERATION_DEFINITION_ID
    assert options["subject_ref"] == profile_operation_subject(str(_PROFILE))
    assert options["result_type"] is ModeloIvaWalletCorrectionProjection
    assert options["request_version"] == 1
    assert options["result_version"] == 1


@pytest.mark.parametrize(
    "mismatch", ["profile", "period", "amount", "reason", "provenance", "effect", "terminal", "refusal"]
)
def test_result_or_receipt_mismatch_refuses_with_operation_correlation(
    monkeypatch: pytest.MonkeyPatch,
    mismatch: str,
) -> None:
    projection = _projection()
    effect = OperationEffect.UPDATED
    condition = OperationTerminalCondition.SUCCEEDED
    refusal_code = None
    if mismatch == "profile":
        projection = projection.model_copy(update={"profile_id": UUID("33333333-3333-4333-8333-333333333333")})
    elif mismatch == "period":
        projection = projection.model_copy(update={"period": PublicPeriod(filing_year=2023, code="4T")})
    elif mismatch == "amount":
        projection = projection.model_copy(update={"amount": "1200.51"})
    elif mismatch == "reason":
        projection = projection.model_copy(update={"reason": "other reason"})
    elif mismatch == "provenance":
        projection = projection.model_copy(update={"provenance": IvaCompensationStateProvenance.OPERATOR_SEED})
    elif mismatch == "effect":
        effect = OperationEffect.NONE
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
