"""Contract tests for exact-profile IVA-wallet seed and override operations."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from cadrumo.core.iva_compensation_provenance import IvaCompensationStateProvenance
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from cadrumo.domain.iva_compensation.errors import IvaCompensationSeedConflictError
from cadrumo.domain.iva_compensation.reconciliation import IvaCompensationDecisionReason

from ...operations.access_resolution import OperationAccessContext
from ...operations.capabilities import OperationRequestStoragePolicy, OperationSensitiveInputPolicy
from ...operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from ...operations.owner import OperationExecutorContext
from ...operations.public_period import PublicPeriod
from ...operations.registry import OperationFrontendProjection, OperationPublicDefinitionRegistrationV1
from ...user_profile.access_contracts import AccessAction, AccessDenialCode, Availability
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..iva_wallet_override_operation import (
    MODELO_IVA_WALLET_OVERRIDE_OPERATION_DEFINITION_ID,
    ModeloIvaWalletOverrideExecutor,
    ModeloIvaWalletOverrideProjection,
    ModeloIvaWalletOverrideReport,
    ModeloIvaWalletOverrideRequest,
    build_modelo_iva_wallet_override_definition,
    build_modelo_iva_wallet_override_registration,
    project_modelo_iva_wallet_override_result,
    resolve_modelo_iva_wallet_override_access,
)
from ..iva_wallet_seed_operation import (
    MODELO_IVA_WALLET_SEED_OPERATION_DEFINITION_ID,
    ModeloIvaWalletSeedExecutor,
    ModeloIvaWalletSeedProjection,
    ModeloIvaWalletSeedReport,
    ModeloIvaWalletSeedRequest,
    build_modelo_iva_wallet_seed_definition,
    build_modelo_iva_wallet_seed_registration,
    project_modelo_iva_wallet_seed_result,
    resolve_modelo_iva_wallet_seed_access,
)
from ..iva_wallet_seed_ports import ModeloIvaWalletSeedPorts, ModeloIvaWalletSeedPortsFactory

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("21212121-2121-4121-8121-212121212121")
_OTHER_PROFILE = UUID("33333333-3333-4333-8333-333333333333")
_PERIOD = PublicPeriod(filing_year=2024, code="4T")
_AUTHORITY = object()


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


class _Authority:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.coordinates: list[tuple[str, int, str]] = []

    def snapshot(self, modelo: str, *, filing_year: int, period: str) -> None:
        self.coordinates.append((modelo, filing_year, period))
        if self.error is not None:
            raise self.error


class _Factory:
    def __init__(self, *, bucket_id: str | None = None) -> None:
        self.bucket_id = bucket_id
        self.requested: list[str] = []
        self.operations: list[object] = []

    def __call__(self, *, bucket_id: str, operation: object) -> ModeloIvaWalletSeedPorts:
        self.requested.append(bucket_id)
        self.operations.append(operation)
        selected = self.bucket_id if self.bucket_id is not None else bucket_id
        return cast(
            ModeloIvaWalletSeedPorts,
            cast(
                object,
                SimpleNamespace(
                    work_unit_repository=SimpleNamespace(bucket_id=selected),
                    calculation_repository=SimpleNamespace(bucket_id=selected),
                ),
            ),
        )


def _seed_request(*, profile_id: UUID = _PROFILE) -> OperationRequest[ModeloIvaWalletSeedRequest]:
    return OperationRequest[ModeloIvaWalletSeedRequest](
        definition_id=MODELO_IVA_WALLET_SEED_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(profile_id)),
        payload=ModeloIvaWalletSeedRequest(profile_id=profile_id, period=_PERIOD, amount="1200.50"),
    )


def _override_request(*, profile_id: UUID = _PROFILE) -> OperationRequest[ModeloIvaWalletOverrideRequest]:
    return OperationRequest[ModeloIvaWalletOverrideRequest](
        definition_id=MODELO_IVA_WALLET_OVERRIDE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(profile_id)),
        payload=ModeloIvaWalletOverrideRequest(
            profile_id=profile_id,
            period=_PERIOD,
            amount="1200.50",
            reason="operator asserts the prior balance",
            evidence_locator="local:m303-2023-filed-return",
        ),
    )


def _seed_registration():
    factory = cast(ModeloIvaWalletSeedPortsFactory, cast(object, lambda **_kwargs: None))
    definition = build_modelo_iva_wallet_seed_definition(factory)
    return definition, build_modelo_iva_wallet_seed_registration(definition)


def _override_registration():
    factory = cast(ModeloIvaWalletSeedPortsFactory, cast(object, lambda **_kwargs: None))
    definition = build_modelo_iva_wallet_override_definition(factory)
    return definition, build_modelo_iva_wallet_override_registration(definition)


def _executor_context(
    *,
    definition_id: str,
    events: _Events,
    operands: _Operands,
    authority: _Authority | object = _AUTHORITY,
) -> OperationExecutorContext:
    return cast(
        OperationExecutorContext,
        SimpleNamespace(
            identity=OperationIdentity(
                operation_id="a" * 64,
                definition_id=definition_id,
                subject_ref=profile_operation_subject(str(_PROFILE)),
            ),
            authority_operation=authority,
            cancellation=_Cancellation(),
            events=events,
            operands=operands,
        ),
    )


def _access_context(
    registration: OperationPublicDefinitionRegistrationV1, *, profile_id: UUID = _PROFILE
) -> OperationAccessContext:
    return OperationAccessContext(
        profile_id=profile_id,
        destination_id=uuid4(),
        action=AccessAction.SUBMIT,
        frontend=OperationFrontendProjection.CLI,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
    )


def _seed_state(*, amount: Decimal = Decimal("1200.50")) -> object:
    period = _PERIOD.to_period()
    return SimpleNamespace(
        period=period,
        filing_year=period.filing_year,
        taxpayer_nif="12345678Z",
        provenance=IvaCompensationStateProvenance.OPERATOR_SEED,
        available_end_amount=amount,
        status=None,
        registry_snapshot_ref=SimpleNamespace(
            modelo="303",
            modelo_year=period.filing_year,
            period=period.registry_token,
        ),
    )


def _override_decision(
    *,
    amount: Decimal = Decimal("1200.50"),
    authority: str = "taxpayer_override",
) -> object:
    return SimpleNamespace(
        target_year=_PERIOD.filing_year,
        target_period=_PERIOD.to_period(),
        taxpayer_nif="12345678Z",
        selected_authority=authority,
        selected_amount=amount,
        override_amount=amount,
        divergence="override",
        blocked=False,
        reason_identity=IvaCompensationDecisionReason.TAXPAYER_OVERRIDE,
        operator_explanation="operator asserts the prior balance",
    )


def test_seed_and_override_definitions_keep_confidential_inputs_and_closed_results() -> None:
    seed_definition, _seed_registration_value = _seed_registration()
    override_definition, _override_registration_value = _override_registration()

    assert seed_definition.capabilities.request_storage is OperationRequestStoragePolicy.SECURE_REFERENCE
    assert seed_definition.capabilities.sensitive_input is OperationSensitiveInputPolicy.SECURE_REFERENCE
    assert override_definition.capabilities.request_storage is OperationRequestStoragePolicy.SECURE_REFERENCE
    assert override_definition.capabilities.sensitive_input is OperationSensitiveInputPolicy.SECURE_REFERENCE
    assert set(ModeloIvaWalletSeedProjection.model_json_schema()["properties"]) == {
        "result_version",
        "profile_id",
        "period",
        "taxpayer_nif",
        "amount",
        "provenance",
        "register_status",
    }
    assert set(ModeloIvaWalletOverrideProjection.model_json_schema()["properties"]) == {
        "result_version",
        "profile_id",
        "period",
        "taxpayer_nif",
        "amount",
        "reason",
        "evidence_locator",
        "selected_authority",
        "divergence",
    }
    with pytest.raises(ValidationError):
        ModeloIvaWalletSeedRequest(profile_id=_PROFILE, period=_PERIOD, amount="1e3")
    with pytest.raises(ValidationError):
        ModeloIvaWalletOverrideRequest(
            profile_id=_PROFILE,
            period=_PERIOD,
            amount="1200.50",
            reason="operator asserts the prior balance",
            evidence_locator="x" * 501,
        )
    with pytest.raises(ValidationError):
        ModeloIvaWalletOverrideProjection(
            profile_id=_PROFILE,
            period=_PERIOD,
            taxpayer_nif="12345678Z",
            amount="1200.50",
            reason="operator asserts the prior balance",
            evidence_locator="local:m303-2023-filed-return",
            selected_authority="aeat_wallet",
            divergence="match",
        )


@pytest.mark.parametrize(
    ("request_factory", "registration_factory", "resolver"),
    [
        (_seed_request, _seed_registration, resolve_modelo_iva_wallet_seed_access),
        (_override_request, _override_registration, resolve_modelo_iva_wallet_override_access),
    ],
)
def test_access_is_exact_profile_period_scoped_and_requires_commit(
    request_factory,
    registration_factory,
    resolver,
) -> None:
    _definition, registered = registration_factory()
    operation_request = request_factory()
    resolved = resolver(cast(OperationRequest[BaseModel], operation_request), _access_context(registered))

    assert resolved.request.periods == frozenset({_PERIOD.to_period()})
    assert not resolved.request.period_independent
    assert AccessAction.COMMIT in resolved.policy.actions
    with pytest.raises(ProfileAccessRefusedError) as refused:
        resolver(
            cast(OperationRequest[BaseModel], operation_request),
            _access_context(registered, profile_id=_OTHER_PROFILE),
        )
    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH


def test_seed_executor_uses_pinned_authority_and_refuses_ungrounded_state(monkeypatch: pytest.MonkeyPatch) -> None:
    events = _Events()
    operands = _Operands()
    authority = _Authority()
    factory = _Factory()
    seen: list[dict[str, object]] = []
    monkeypatch.setattr(
        "cadrumo.application.modelo.iva_wallet_seed_operation.require_active_bucket_id", lambda: str(_PROFILE)
    )
    monkeypatch.setattr("cadrumo.application.operations.profile_guard.require_active_bucket_id", lambda: str(_PROFILE))

    def seed(**kwargs: object) -> object:
        seen.append(kwargs)
        return _seed_state()

    monkeypatch.setattr(
        "cadrumo.application.modelo.iva_wallet_seed_operation.seed_iva_compensation_period_for_bucket", seed
    )
    executor = ModeloIvaWalletSeedExecutor(cast(ModeloIvaWalletSeedPortsFactory, factory))
    context = _executor_context(
        definition_id=MODELO_IVA_WALLET_SEED_OPERATION_DEFINITION_ID,
        events=events,
        operands=operands,
        authority=authority,
    )

    result_ref = asyncio.run(executor.execute(_seed_request(), context))

    assert result_ref == "result-reference"
    assert authority.coordinates == [("303", 2024, "4T")]
    assert factory.requested == [str(_PROFILE)]
    assert factory.operations == [authority]
    assert seen[0]["bucket_id"] == str(_PROFILE)
    assert seen[0]["operation"] is authority
    assert events.effects == [OperationEffect.UNKNOWN, OperationEffect.UPDATED]
    assert events.phases == [
        f"{MODELO_IVA_WALLET_SEED_OPERATION_DEFINITION_ID}.commit",
        f"{MODELO_IVA_WALLET_SEED_OPERATION_DEFINITION_ID}.result",
    ]
    report = cast(ModeloIvaWalletSeedReport, operands.values[0])
    assert report.projection.amount == "1200.50"
    receipt = OperationTerminalReceipt(
        identity=OperationIdentity(
            operation_id="a" * 64,
            definition_id=MODELO_IVA_WALLET_SEED_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(_PROFILE)),
        ),
        revision=3,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.UPDATED,
        settled_at=datetime(2026, 9, 29, 10, 0, tzinfo=UTC),
        result_ref=result_ref,
    )
    assert project_modelo_iva_wallet_seed_result(report, receipt) == report.projection

    events = _Events()
    operands = _Operands()

    def ungrounded_seed(**_kwargs: object) -> object:
        return _seed_state(amount=Decimal("1200.51"))

    monkeypatch.setattr(
        "cadrumo.application.modelo.iva_wallet_seed_operation.seed_iva_compensation_period_for_bucket",
        ungrounded_seed,
    )
    with pytest.raises(ProfileAccessRefusedError):
        asyncio.run(
            ModeloIvaWalletSeedExecutor(cast(ModeloIvaWalletSeedPortsFactory, factory)).execute(
                _seed_request(),
                _executor_context(
                    definition_id=MODELO_IVA_WALLET_SEED_OPERATION_DEFINITION_ID,
                    events=events,
                    operands=operands,
                    authority=_Authority(),
                ),
            )
        )
    assert events.effects == [OperationEffect.UNKNOWN, OperationEffect.UPDATED]
    assert operands.values == []


def test_seed_authority_refusal_precedes_commit_and_duplicate_is_effect_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events = _Events()
    operands = _Operands()
    authority = _Authority(ValueError("unavailable published authority"))
    factory = _Factory()
    monkeypatch.setattr(
        "cadrumo.application.modelo.iva_wallet_seed_operation.require_active_bucket_id", lambda: str(_PROFILE)
    )
    monkeypatch.setattr("cadrumo.application.operations.profile_guard.require_active_bucket_id", lambda: str(_PROFILE))
    monkeypatch.setattr(
        "cadrumo.application.modelo.iva_wallet_seed_operation.seed_iva_compensation_period_for_bucket",
        lambda **_kwargs: pytest.fail("seed service must not run without pinned source authority"),
    )
    executor = ModeloIvaWalletSeedExecutor(cast(ModeloIvaWalletSeedPortsFactory, factory))
    with pytest.raises(ValueError, match="unavailable published authority"):
        asyncio.run(
            executor.execute(
                _seed_request(),
                _executor_context(
                    definition_id=MODELO_IVA_WALLET_SEED_OPERATION_DEFINITION_ID,
                    events=events,
                    operands=operands,
                    authority=authority,
                ),
            )
        )
    assert events.phases == []
    assert events.effects == []
    assert factory.requested == []

    events = _Events()
    monkeypatch.setattr(
        "cadrumo.application.modelo.iva_wallet_seed_operation.seed_iva_compensation_period_for_bucket",
        lambda **_kwargs: (_ for _ in ()).throw(
            IvaCompensationSeedConflictError(
                translated_message="application.calculations.iva_compensation.errors.seed_conflict"
            )
        ),
    )
    with pytest.raises(IvaCompensationSeedConflictError):
        asyncio.run(
            ModeloIvaWalletSeedExecutor(cast(ModeloIvaWalletSeedPortsFactory, factory)).execute(
                _seed_request(),
                _executor_context(
                    definition_id=MODELO_IVA_WALLET_SEED_OPERATION_DEFINITION_ID,
                    events=events,
                    operands=_Operands(),
                    authority=_Authority(),
                ),
            )
        )
    assert events.effects == [OperationEffect.UNKNOWN, OperationEffect.NONE]


def test_override_executor_uses_pinned_authority_and_refuses_ungrounded_decision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events = _Events()
    operands = _Operands()
    authority = _Authority()
    factory = _Factory()
    seen: list[dict[str, object]] = []
    monkeypatch.setattr(
        "cadrumo.application.modelo.iva_wallet_override_operation.require_active_bucket_id", lambda: str(_PROFILE)
    )
    monkeypatch.setattr("cadrumo.application.operations.profile_guard.require_active_bucket_id", lambda: str(_PROFILE))

    def record(**kwargs: object) -> object:
        seen.append(kwargs)
        return _override_decision()

    monkeypatch.setattr(
        "cadrumo.application.modelo.iva_wallet_override_operation.record_iva_compensation_override_for_bucket",
        record,
    )
    executor = ModeloIvaWalletOverrideExecutor(cast(ModeloIvaWalletSeedPortsFactory, factory))
    context = _executor_context(
        definition_id=MODELO_IVA_WALLET_OVERRIDE_OPERATION_DEFINITION_ID,
        events=events,
        operands=operands,
        authority=authority,
    )

    result_ref = asyncio.run(executor.execute(_override_request(), context))

    assert result_ref == "result-reference"
    assert authority.coordinates == [("303", 2024, "4T")]
    assert factory.requested == [str(_PROFILE)]
    assert factory.operations == [authority]
    assert seen[0]["bucket_id"] == str(_PROFILE)
    assert seen[0]["operation"] is authority
    assert events.effects == [OperationEffect.UNKNOWN, OperationEffect.UPDATED]
    assert events.phases == [
        f"{MODELO_IVA_WALLET_OVERRIDE_OPERATION_DEFINITION_ID}.commit",
        f"{MODELO_IVA_WALLET_OVERRIDE_OPERATION_DEFINITION_ID}.result",
    ]
    report = cast(ModeloIvaWalletOverrideReport, operands.values[0])
    assert report.projection.amount == "1200.50"
    receipt = OperationTerminalReceipt(
        identity=OperationIdentity(
            operation_id="a" * 64,
            definition_id=MODELO_IVA_WALLET_OVERRIDE_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(_PROFILE)),
        ),
        revision=3,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.UPDATED,
        settled_at=datetime(2026, 9, 29, 10, 0, tzinfo=UTC),
        result_ref=result_ref,
    )
    assert project_modelo_iva_wallet_override_result(report, receipt) == report.projection

    events = _Events()
    operands = _Operands()
    monkeypatch.setattr(
        "cadrumo.application.modelo.iva_wallet_override_operation.record_iva_compensation_override_for_bucket",
        lambda **_kwargs: _override_decision(authority="aeat_wallet"),
    )
    with pytest.raises(ProfileAccessRefusedError):
        asyncio.run(
            ModeloIvaWalletOverrideExecutor(cast(ModeloIvaWalletSeedPortsFactory, factory)).execute(
                _override_request(),
                _executor_context(
                    definition_id=MODELO_IVA_WALLET_OVERRIDE_OPERATION_DEFINITION_ID,
                    events=events,
                    operands=operands,
                    authority=_Authority(),
                ),
            )
        )
    assert events.effects == [OperationEffect.UNKNOWN, OperationEffect.UPDATED]
    assert operands.values == []
