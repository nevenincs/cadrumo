"""Contract tests for exact-profile IVA wallet correction enrollment."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from cadrumo.core.iva_compensation_provenance import IvaCompensationStateProvenance
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject

from ...operations.access_resolution import OperationAccessContext
from ...operations.capabilities import OperationRequestStoragePolicy, OperationSensitiveInputPolicy
from ...operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from ...operations.owner import OperationExecutorContext
from ...operations.public_period import PublicPeriod
from ...operations.registry import OperationFrontendProjection
from ...user_profile.access_contracts import AccessAction, AccessDenialCode, Availability
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..iva_wallet_correction_operation import (
    MODELO_IVA_WALLET_CORRECTION_OPERATION_DEFINITION_ID,
    ModeloIvaWalletCorrectionExecutor,
    ModeloIvaWalletCorrectionProjection,
    ModeloIvaWalletCorrectionReport,
    ModeloIvaWalletCorrectionRequest,
    build_modelo_iva_wallet_correction_definition,
    build_modelo_iva_wallet_correction_registration,
    project_modelo_iva_wallet_correction_result,
    resolve_modelo_iva_wallet_correction_access,
)
from ..iva_wallet_seed import ModeloIvaWalletCorrectionNoRecordError
from ..iva_wallet_seed_ports import ModeloIvaWalletSeedPorts, ModeloIvaWalletSeedPortsFactory

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("21212121-2121-4121-8121-212121212121")
_OTHER_PROFILE = UUID("33333333-3333-4333-8333-333333333333")
_PERIOD = PublicPeriod(filing_year=2024, code="4T")
_AUTHORITY = object()


class _History:
    def __init__(self, prior: object) -> None:
        self.prior = prior

    def load_period(self, _period: object) -> object:
        return self.prior


class _Events:
    def __init__(self) -> None:
        self.phases: list[str] = []
        self.effects: list[OperationEffect] = []

    async def phase(self, value: str) -> None:
        self.phases.append(value)

    async def effect(self, value: OperationEffect) -> None:
        self.effects.append(value)


class _Cancellation:
    @asynccontextmanager
    async def irreversible_section(self):
        yield


class _Operands:
    def __init__(self) -> None:
        self.values: list[BaseModel] = []

    async def put(self, value: BaseModel, *, written_at: datetime) -> str:
        assert written_at.tzinfo is not None
        self.values.append(value)
        return "result-reference"


class _Factory:
    def __init__(self, *, history: _History, bucket_id: str | None = None) -> None:
        self.history = history
        self.bucket_id = bucket_id
        self.requested: list[str] = []

    def __call__(self, *, bucket_id: str) -> ModeloIvaWalletSeedPorts:
        self.requested.append(bucket_id)
        selected = self.bucket_id if self.bucket_id is not None else bucket_id
        return cast(
            ModeloIvaWalletSeedPorts,
            SimpleNamespace(
                work_unit_repository=SimpleNamespace(bucket_id=selected),
                calculation_repository=SimpleNamespace(bucket_id=selected),
                iva_compensation_history_repository=self.history,
            ),
        )


def _request(*, profile_id: UUID = _PROFILE) -> OperationRequest[ModeloIvaWalletCorrectionRequest]:
    return OperationRequest[ModeloIvaWalletCorrectionRequest](
        definition_id=MODELO_IVA_WALLET_CORRECTION_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(profile_id)),
        payload=ModeloIvaWalletCorrectionRequest(
            profile_id=profile_id,
            period=_PERIOD,
            amount="1200.50",
            reason="corrected opening balance",
        ),
    )


def _definition_and_registration():
    factory = cast(ModeloIvaWalletSeedPortsFactory, cast(object, lambda **_kwargs: None))
    definition = build_modelo_iva_wallet_correction_definition(factory)
    return definition, build_modelo_iva_wallet_correction_registration(definition)


def test_operation_keeps_request_confidential_and_public_result_closed() -> None:
    definition, _registration = _definition_and_registration()

    assert definition.capabilities.request_storage is OperationRequestStoragePolicy.SECURE_REFERENCE
    assert definition.capabilities.sensitive_input is OperationSensitiveInputPolicy.SECURE_REFERENCE
    assert definition.capabilities.permitted_effects == frozenset(
        {OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.UNKNOWN}
    )
    schema = ModeloIvaWalletCorrectionProjection.model_json_schema()
    assert set(schema["properties"]) == {
        "result_version",
        "profile_id",
        "period",
        "taxpayer_nif",
        "previous_amount",
        "amount",
        "provenance",
        "register_status",
        "reason",
    }
    with pytest.raises(ValidationError):
        ModeloIvaWalletCorrectionRequest(
            profile_id=_PROFILE,
            period=_PERIOD,
            amount="1e3",
            reason="unsupported amount spelling",
        )


def test_access_is_exact_profile_period_scoped_and_requires_commit() -> None:
    _definition, registration = _definition_and_registration()
    request = _request()
    context = OperationAccessContext(
        profile_id=_PROFILE,
        destination_id=uuid4(),
        action=AccessAction.SUBMIT,
        frontend=OperationFrontendProjection.CLI,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
    )

    resolved = resolve_modelo_iva_wallet_correction_access(cast(OperationRequest[BaseModel], request), context)

    assert resolved.request.periods == frozenset({_PERIOD.to_period()})
    assert not resolved.request.period_independent
    assert AccessAction.COMMIT in resolved.policy.actions
    with pytest.raises(ProfileAccessRefusedError) as refused:
        resolve_modelo_iva_wallet_correction_access(
            cast(OperationRequest[BaseModel], request),
            replace(context, profile_id=_OTHER_PROFILE),
        )
    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH


def _executor_context(events: _Events, operands: _Operands) -> OperationExecutorContext:
    return cast(
        OperationExecutorContext,
        SimpleNamespace(
            identity=OperationIdentity(
                operation_id="a" * 64,
                definition_id=MODELO_IVA_WALLET_CORRECTION_OPERATION_DEFINITION_ID,
                subject_ref=profile_operation_subject(str(_PROFILE)),
            ),
            authority_operation=_AUTHORITY,
            cancellation=_Cancellation(),
            events=events,
            operands=operands,
        ),
    )


def test_executor_uses_exact_bucket_pinned_authority_and_commit_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    period = _PERIOD.to_period()
    prior = SimpleNamespace(period=period, available_end_amount=Decimal("500.00"))
    state = SimpleNamespace(
        period=period,
        taxpayer_nif="12345678Z",
        provenance=IvaCompensationStateProvenance.OPERATOR_CORRECTION,
        available_end_amount=Decimal("1200.50"),
        status=None,
    )
    events = _Events()
    operands = _Operands()
    factory = _Factory(history=_History(prior))
    seen: list[dict[str, object]] = []

    monkeypatch.setattr(
        "cadrumo.application.modelo.iva_wallet_correction_operation.require_active_bucket_id", lambda: str(_PROFILE)
    )

    def correct(**kwargs: object):
        seen.append(kwargs)
        return state

    monkeypatch.setattr(
        "cadrumo.application.modelo.iva_wallet_correction_operation.correct_iva_compensation_period_for_bucket",
        correct,
    )
    executor = ModeloIvaWalletCorrectionExecutor(cast(ModeloIvaWalletSeedPortsFactory, factory))

    result_ref = asyncio.run(executor.execute(_request(), _executor_context(events, operands)))

    assert result_ref == "result-reference"
    assert factory.requested == [str(_PROFILE)]
    assert seen[0]["bucket_id"] == str(_PROFILE)
    assert seen[0]["operation"] is _AUTHORITY
    assert events.effects == [OperationEffect.UNKNOWN, OperationEffect.UPDATED]
    assert events.phases == [
        f"{MODELO_IVA_WALLET_CORRECTION_OPERATION_DEFINITION_ID}.commit",
        f"{MODELO_IVA_WALLET_CORRECTION_OPERATION_DEFINITION_ID}.result",
    ]
    report = operands.values[0]
    projection = cast(ModeloIvaWalletCorrectionReport, report).projection
    assert projection.previous_amount == "500.00"
    assert projection.amount == "1200.50"
    assert projection.reason == "corrected opening balance"

    receipt = OperationTerminalReceipt(
        identity=OperationIdentity(
            operation_id="a" * 64,
            definition_id=MODELO_IVA_WALLET_CORRECTION_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(_PROFILE)),
        ),
        revision=3,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.UPDATED,
        settled_at=datetime(2026, 9, 29, 10, 0, tzinfo=UTC),
        result_ref=result_ref,
    )
    assert project_modelo_iva_wallet_correction_result(report, receipt) == projection


def test_known_seed_refusal_is_settled_with_no_effect(monkeypatch: pytest.MonkeyPatch) -> None:
    period = _PERIOD.to_period()
    events = _Events()
    operands = _Operands()
    factory = _Factory(history=_History(SimpleNamespace(period=period, available_end_amount=Decimal("500.00"))))
    monkeypatch.setattr(
        "cadrumo.application.modelo.iva_wallet_correction_operation.require_active_bucket_id", lambda: str(_PROFILE)
    )

    def refuse(**_kwargs: object):
        raise ModeloIvaWalletCorrectionNoRecordError(
            translated_message="application.modelo.iva_wallet.correct_no_record"
        )

    monkeypatch.setattr(
        "cadrumo.application.modelo.iva_wallet_correction_operation.correct_iva_compensation_period_for_bucket",
        refuse,
    )
    executor = ModeloIvaWalletCorrectionExecutor(cast(ModeloIvaWalletSeedPortsFactory, factory))

    with pytest.raises(ModeloIvaWalletCorrectionNoRecordError):
        asyncio.run(executor.execute(_request(), _executor_context(events, operands)))

    assert events.effects == [OperationEffect.UNKNOWN, OperationEffect.NONE]
    assert operands.values == []
