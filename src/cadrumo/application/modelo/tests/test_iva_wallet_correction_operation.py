"""Contract tests for exact-profile IVA wallet correction enrollment."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Never, cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from cadrumo.core.iva_compensation_provenance import IvaCompensationStateProvenance
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.schema_references import RegistrySnapshotRef
from cadrumo.domain.iva_compensation.carry_forward import IvaCompensationPeriodState
from cadrumo.domain.modelos.calculation_revision import CalculationRevisionCatalogue
from cadrumo.domain.modelos.work_unit import WorkUnitCatalogue

from ...calculations.observations_repository import CalculationObservationPorts
from ...ledger.tests.unused_repository_ports import ProfileOnlyCatalogueRepository, UnusedBucketEventRepository
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
from .advisory_diagnostic_repositories import EmptyObservationRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("21212121-2121-4121-8121-212121212121")
_OTHER_PROFILE = UUID("33333333-3333-4333-8333-333333333333")
_PERIOD = PublicPeriod(filing_year=2024, code="4T")
_AUTHORITY = object()


class _History:
    def __init__(self, prior: IvaCompensationPeriodState) -> None:
        self.prior = prior

    def load_period(self, period: Period) -> IvaCompensationPeriodState:
        assert period == self.prior.period
        return self.prior

    def list_periods(self) -> tuple[IvaCompensationPeriodState, ...]:
        return (self.prior,)

    def save_period(self, state: IvaCompensationPeriodState) -> None:
        raise AssertionError("the correction seam owns history writes in this test")

    def to_secure_object_write(self, payload: IvaCompensationPeriodState, **_kwargs: object) -> Never:
        raise AssertionError("the correction seam owns secure writes in this test")

    @property
    def secure_object_repository(self) -> Never:
        raise AssertionError("the correction seam owns storage in this test")


class _UnusedWalletDecisionRepository:
    def load_decision(self, taxpayer_nif: str, target_period: Period) -> Never:
        raise AssertionError("the correction seam does not read wallet decisions")

    def list_decisions(self) -> Never:
        raise AssertionError("the correction seam does not list wallet decisions")

    def load_decision_history(self, taxpayer_nif: str, target_period: Period) -> Never:
        raise AssertionError("the correction seam does not read wallet history")

    def save_decision(self, decision: object) -> Never:
        raise AssertionError("the correction seam owns wallet decision writes")

    @property
    def secure_object_repository(self) -> Never:
        raise AssertionError("the correction seam owns wallet storage")


def _history_state(
    amount: Decimal, *, provenance: IvaCompensationStateProvenance = IvaCompensationStateProvenance.OPERATOR_SEED
) -> IvaCompensationPeriodState:
    return IvaCompensationPeriodState(
        taxpayer_nif="12345678Z",
        filing_year=_PERIOD.filing_year,
        period=_PERIOD.to_period(),
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo="303", revision_id="synthetic-revision", modelo_year=_PERIOD.filing_year, period=_PERIOD.code
        ),
        provenance=provenance,
        presented_at=datetime(2026, 9, 29, 10, 0, tzinfo=UTC),
        generated_amount=Decimal("0"),
        available_end_amount=amount,
        source_observation_key="synthetic-correction-history",
    )


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
        return ModeloIvaWalletSeedPorts(
            work_unit_repository=ProfileOnlyCatalogueRepository[WorkUnitCatalogue](selected),
            calculation_repository=ProfileOnlyCatalogueRepository[CalculationRevisionCatalogue](selected),
            bucket_event_repository=UnusedBucketEventRepository(),
            calculation_observation_ports=CalculationObservationPorts(
                observation_repository=EmptyObservationRepository(),
                iva_wallet_decision_repository=_UnusedWalletDecisionRepository(),
            ),
            iva_compensation_history_repository=self.history,
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
    typed_request = _request()
    request = OperationRequest[BaseModel](
        definition_id=typed_request.definition_id,
        subject_ref=typed_request.subject_ref,
        payload=typed_request.payload,
    )
    context = OperationAccessContext(
        profile_id=_PROFILE,
        destination_id=uuid4(),
        action=AccessAction.SUBMIT,
        frontend=OperationFrontendProjection.CLI,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
    )

    resolved = resolve_modelo_iva_wallet_correction_access(request, context)

    assert resolved.request.periods == frozenset({_PERIOD.to_period()})
    assert not resolved.request.period_independent
    assert AccessAction.COMMIT in resolved.policy.actions
    with pytest.raises(ProfileAccessRefusedError) as refused:
        resolve_modelo_iva_wallet_correction_access(
            request,
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


@pytest.mark.usefixtures("operation")
def test_executor_uses_exact_bucket_pinned_authority_and_commit_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prior = _history_state(Decimal("500.00"))
    state = _history_state(Decimal("1200.50"), provenance=IvaCompensationStateProvenance.OPERATOR_CORRECTION)
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


@pytest.mark.usefixtures("operation")
def test_known_seed_refusal_is_settled_with_no_effect(monkeypatch: pytest.MonkeyPatch) -> None:
    events = _Events()
    operands = _Operands()
    factory = _Factory(history=_History(_history_state(Decimal("500.00"))))
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
