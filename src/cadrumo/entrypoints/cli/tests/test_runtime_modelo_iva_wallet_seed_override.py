"""CLI bridge contracts for exact-profile IVA-wallet seed and override operations."""

from __future__ import annotations

from typing import cast
from uuid import UUID

import pytest
import typer

from ....application.modelo.iva_wallet_override_operation import (
    MODELO_IVA_WALLET_OVERRIDE_OPERATION_DEFINITION_ID,
    ModeloIvaWalletOverrideProjection,
    ModeloIvaWalletOverrideRequest,
)
from ....application.modelo.iva_wallet_seed_operation import (
    MODELO_IVA_WALLET_SEED_OPERATION_DEFINITION_ID,
    ModeloIvaWalletSeedProjection,
    ModeloIvaWalletSeedRequest,
)
from ....application.operations.public_period import PublicPeriod
from ....application.runtime.contracts import RuntimeRefusalCode
from ....core.iva_compensation_provenance import IvaCompensationStateProvenance
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....core.period import Period
from .. import runtime_modelo_iva_wallet_override as override_bridge
from .. import runtime_modelo_iva_wallet_seed as seed_bridge
from ..errors import CliRefusedBoundaryError
from ..runtime_registered_operation import RegisteredOperationCompletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("21212121-2121-4121-8121-212121212121")
_OPERATION_ID = "b" * 64
_PERIOD = Period.from_year_and_code(2024, "4T")


def _seed_projection() -> ModeloIvaWalletSeedProjection:
    return ModeloIvaWalletSeedProjection(
        profile_id=_PROFILE,
        period=PublicPeriod.from_period(_PERIOD),
        taxpayer_nif="12345678Z",
        amount="1200.50",
        provenance=IvaCompensationStateProvenance.OPERATOR_SEED,
        register_status=None,
    )


def _override_projection() -> ModeloIvaWalletOverrideProjection:
    return ModeloIvaWalletOverrideProjection(
        profile_id=_PROFILE,
        period=PublicPeriod.from_period(_PERIOD),
        taxpayer_nif="12345678Z",
        amount="1200.50",
        reason="operator asserts the prior balance",
        evidence_locator="local:m303-2023-filed-return",
        selected_authority="taxpayer_override",
        divergence="override",
    )


def _bind(
    monkeypatch: pytest.MonkeyPatch,
    bridge: object,
    projection: ModeloIvaWalletSeedProjection | ModeloIvaWalletOverrideProjection,
    *,
    effect: OperationEffect = OperationEffect.UPDATED,
    condition: OperationTerminalCondition = OperationTerminalCondition.SUCCEEDED,
    refusal_code: str | None = None,
):
    monkeypatch.setattr(bridge, "require_active_bucket_id", lambda: str(_PROFILE))
    bound_profiles: list[UUID] = []

    def require_client(_ctx: object, *, expected_profile_id: UUID):
        bound_profiles.append(expected_profile_id)
        return object()

    monkeypatch.setattr(bridge, "require_profile_client", require_client)
    submitted: list[tuple[object, dict[str, object]]] = []

    def submit(_client: object, request: object, **kwargs: object):
        submitted.append((request, cast(dict[str, object], kwargs)))
        return RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=projection,
            effect=effect,
            terminal_condition=condition,
            refusal_code=refusal_code,
        )

    monkeypatch.setattr(bridge, "run_registered_operation", submit)
    return submitted, bound_profiles


def _seed_read() -> seed_bridge.ModeloIvaWalletSeedRead:
    return seed_bridge.read_modelo_iva_wallet_seed_for_cli(
        cast(typer.Context, cast(object, None)),
        period=_PERIOD,
        amount="1200.50",
    )


def _override_read() -> override_bridge.ModeloIvaWalletOverrideRead:
    return override_bridge.read_modelo_iva_wallet_override_for_cli(
        cast(typer.Context, cast(object, None)),
        period=_PERIOD,
        amount="1200.50",
        reason="operator asserts the prior balance",
        evidence_locator="local:m303-2023-filed-return",
    )


def test_seed_bridge_submits_to_exact_profile_and_accepts_only_matching_updated_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    submitted, bound_profiles = _bind(monkeypatch, seed_bridge, _seed_projection())

    read = _seed_read()

    assert read.completion.operation_id == _OPERATION_ID
    assert read.projection == _seed_projection()
    assert bound_profiles == [_PROFILE]
    assert len(submitted) == 1
    request, options = submitted[0]
    assert request == ModeloIvaWalletSeedRequest(
        profile_id=_PROFILE,
        period=PublicPeriod.from_period(_PERIOD),
        amount="1200.50",
    )
    assert options["definition_id"] == MODELO_IVA_WALLET_SEED_OPERATION_DEFINITION_ID
    assert options["subject_ref"] == profile_operation_subject(str(_PROFILE))
    assert options["result_type"] is ModeloIvaWalletSeedProjection
    assert options["request_version"] == 1
    assert options["result_version"] == 1


@pytest.mark.parametrize(
    "mismatch", ["profile", "period", "amount", "provenance", "status", "effect", "terminal", "refusal"]
)
def test_seed_result_or_receipt_mismatch_refuses_with_operation_correlation(
    monkeypatch: pytest.MonkeyPatch,
    mismatch: str,
) -> None:
    projection = _seed_projection()
    effect = OperationEffect.UPDATED
    condition = OperationTerminalCondition.SUCCEEDED
    refusal_code = None
    if mismatch == "profile":
        projection = projection.model_copy(update={"profile_id": UUID("33333333-3333-4333-8333-333333333333")})
    elif mismatch == "period":
        projection = projection.model_copy(update={"period": PublicPeriod(filing_year=2023, code="4T")})
    elif mismatch == "amount":
        projection = projection.model_copy(update={"amount": "1200.51"})
    elif mismatch == "provenance":
        projection = projection.model_copy(update={"provenance": IvaCompensationStateProvenance.OPERATOR_CORRECTION})
    elif mismatch == "status":
        projection = projection.model_copy(update={"register_status": "presentado"})
    elif mismatch == "effect":
        effect = OperationEffect.NONE
    elif mismatch == "terminal":
        condition = OperationTerminalCondition.REFUSED
    elif mismatch == "refusal":
        refusal_code = RuntimeRefusalCode.UNAVAILABLE.value
    _bind(monkeypatch, seed_bridge, projection, effect=effect, condition=condition, refusal_code=refusal_code)

    with pytest.raises(CliRefusedBoundaryError) as refused:
        _seed_read()

    assert refused.value.context is not None
    assert refused.value.context["operation_id"] == _OPERATION_ID
    assert refused.value.context["reason"] == RuntimeRefusalCode.INVALID_FRAME.value


def test_override_bridge_submits_to_exact_profile_and_accepts_matching_updated_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    submitted, bound_profiles = _bind(monkeypatch, override_bridge, _override_projection())

    read = _override_read()

    assert read.completion.operation_id == _OPERATION_ID
    assert read.projection == _override_projection()
    assert bound_profiles == [_PROFILE]
    assert len(submitted) == 1
    request, options = submitted[0]
    assert request == ModeloIvaWalletOverrideRequest(
        profile_id=_PROFILE,
        period=PublicPeriod.from_period(_PERIOD),
        amount="1200.50",
        reason="operator asserts the prior balance",
        evidence_locator="local:m303-2023-filed-return",
    )
    assert options["definition_id"] == MODELO_IVA_WALLET_OVERRIDE_OPERATION_DEFINITION_ID
    assert options["subject_ref"] == profile_operation_subject(str(_PROFILE))
    assert options["result_type"] is ModeloIvaWalletOverrideProjection
    assert options["request_version"] == 1
    assert options["result_version"] == 1


@pytest.mark.parametrize(
    "mismatch", ["profile", "period", "amount", "reason", "locator", "authority", "divergence", "effect", "terminal"]
)
def test_override_result_or_receipt_mismatch_refuses_with_operation_correlation(
    monkeypatch: pytest.MonkeyPatch,
    mismatch: str,
) -> None:
    projection = _override_projection()
    effect = OperationEffect.UPDATED
    condition = OperationTerminalCondition.SUCCEEDED
    if mismatch == "profile":
        projection = projection.model_copy(update={"profile_id": UUID("33333333-3333-4333-8333-333333333333")})
    elif mismatch == "period":
        projection = projection.model_copy(update={"period": PublicPeriod(filing_year=2023, code="4T")})
    elif mismatch == "amount":
        projection = projection.model_copy(update={"amount": "1200.51"})
    elif mismatch == "reason":
        projection = projection.model_copy(update={"reason": "other reason"})
    elif mismatch == "locator":
        projection = projection.model_copy(update={"evidence_locator": "other locator"})
    elif mismatch == "authority":
        projection = projection.model_copy(update={"selected_authority": "aeat_wallet"})
    elif mismatch == "divergence":
        projection = projection.model_copy(update={"divergence": "match"})
    elif mismatch == "effect":
        effect = OperationEffect.NONE
    elif mismatch == "terminal":
        condition = OperationTerminalCondition.REFUSED
    _bind(monkeypatch, override_bridge, projection, effect=effect, condition=condition)

    with pytest.raises(CliRefusedBoundaryError) as refused:
        _override_read()

    assert refused.value.context is not None
    assert refused.value.context["operation_id"] == _OPERATION_ID
    assert refused.value.context["reason"] == RuntimeRefusalCode.INVALID_FRAME.value
