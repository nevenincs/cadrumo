"""Contract tests for exact-profile IVA wallet balance enrollment."""

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

from cadrumo.core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from cadrumo.domain.calculations.registry.governed_fact_scope import governed_facts_in_scope
from cadrumo.domain.iva_compensation.balance import IvaWalletBalanceReport

from ...operations.access_resolution import OperationAccessContext
from ...operations.capabilities import OperationRequestStoragePolicy
from ...operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from ...operations.owner import OperationExecutorContext
from ...operations.registry import OperationFrontendProjection
from ...user_profile.access_contracts import AccessAction, AccessDenialCode, Availability
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..iva_wallet_balance_operation import (
    MODELO_IVA_WALLET_BALANCE_OPERATION_DEFINITION_ID,
    ModeloIvaWalletBalanceExecutor,
    ModeloIvaWalletBalanceOperationReport,
    ModeloIvaWalletBalanceProjection,
    ModeloIvaWalletBalanceRequest,
    build_modelo_iva_wallet_balance_definition,
    build_modelo_iva_wallet_balance_registration,
    project_modelo_iva_wallet_balance_result,
    resolve_modelo_iva_wallet_balance_access,
)
from ..iva_wallet_seed_ports import ModeloIvaWalletSeedPortsFactory

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("21212121-2121-4121-8121-212121212121")
_OTHER_PROFILE = UUID("33333333-3333-4333-8333-333333333333")
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
        return "balance-reference"


class _Factory:
    def __init__(self, repository: object, *, selected_bucket: str | None = None) -> None:
        self.repository = repository
        self.selected_bucket = selected_bucket
        self.requested: list[str] = []
        self.operations: list[object] = []

    def __call__(self, *, bucket_id: str, operation: object) -> object:
        self.requested.append(bucket_id)
        self.operations.append(operation)
        selected = self.selected_bucket if self.selected_bucket is not None else bucket_id
        return SimpleNamespace(
            work_unit_repository=SimpleNamespace(bucket_id=selected),
            calculation_repository=SimpleNamespace(bucket_id=selected),
            iva_compensation_history_repository=self.repository,
        )


def _request(*, profile_id: UUID = _PROFILE, year: int = 2024):
    return OperationRequest[ModeloIvaWalletBalanceRequest](
        definition_id=MODELO_IVA_WALLET_BALANCE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(profile_id)),
        payload=ModeloIvaWalletBalanceRequest(profile_id=profile_id, as_of_year=year),
    )


def _definition_and_registration():
    factory = cast(ModeloIvaWalletSeedPortsFactory, cast(object, lambda **_kwargs: None))
    definition = build_modelo_iva_wallet_balance_definition(factory)
    return definition, build_modelo_iva_wallet_balance_registration(definition)


def test_operation_has_credential_free_request_and_closed_result() -> None:
    definition, _registration = _definition_and_registration()

    assert definition.capabilities.request_storage is OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL
    assert definition.capabilities.permitted_effects == frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN})
    assert set(ModeloIvaWalletBalanceProjection.model_json_schema()["properties"]) == {
        "result_version",
        "profile_id",
        "as_of_year",
        "total_balance",
        "active_balance",
        "expired_balance",
        "lot_count",
        "next_expiry_year",
        "unallocated_applied_amount",
    }
    with pytest.raises(ValidationError):
        ModeloIvaWalletBalanceProjection(
            profile_id=_PROFILE,
            as_of_year=2024,
            total_balance="-1",
            active_balance="0",
            expired_balance="0",
            lot_count=0,
            next_expiry_year=None,
            unallocated_applied_amount="0",
        )


def test_access_is_bound_to_exact_profile_and_whole_history() -> None:
    _definition, registration = _definition_and_registration()
    request = _request(year=2028)
    context = OperationAccessContext(
        profile_id=_PROFILE,
        destination_id=uuid4(),
        action=AccessAction.SUBMIT,
        frontend=OperationFrontendProjection.CLI,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
    )

    resolved = resolve_modelo_iva_wallet_balance_access(cast(OperationRequest[BaseModel], request), context)

    assert resolved.request.periods == frozenset()
    assert resolved.request.period_independent
    assert resolved.policy.allow_period_independent
    with pytest.raises(ProfileAccessRefusedError) as refused:
        resolve_modelo_iva_wallet_balance_access(
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
                definition_id=MODELO_IVA_WALLET_BALANCE_OPERATION_DEFINITION_ID,
                subject_ref=profile_operation_subject(str(_PROFILE)),
            ),
            authority_operation=_AUTHORITY,
            cancellation=_Cancellation(),
            events=events,
            operands=operands,
        ),
    )


def test_executor_reads_exact_profile_and_year_inside_pinned_fact_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events = _Events()
    operands = _Operands()
    repository = object()
    factory = _Factory(repository)
    seen: list[tuple[int, object, object]] = []
    monkeypatch.setattr(
        "cadrumo.application.modelo.iva_wallet_balance_operation.require_active_bucket_id",
        lambda: str(_PROFILE),
    )
    monkeypatch.setattr("cadrumo.application.operations.profile_guard.require_active_bucket_id", lambda: str(_PROFILE))

    def query(*, as_of_year: int, repository: object, operation: object) -> IvaWalletBalanceReport:
        assert operation is _AUTHORITY
        assert governed_facts_in_scope() is _AUTHORITY
        seen.append((as_of_year, repository, operation))
        return IvaWalletBalanceReport(
            as_of_year=as_of_year,
            total_balance=Decimal("500.00"),
            active_balance=Decimal("500.00"),
            expired_balance=Decimal("0.00"),
            lot_count=1,
            next_expiry_year=2028,
            unallocated_applied_amount=Decimal("0.00"),
        )

    monkeypatch.setattr("cadrumo.application.modelo.iva_wallet_balance_operation.query_iva_wallet_balance", query)
    executor = ModeloIvaWalletBalanceExecutor(cast(ModeloIvaWalletSeedPortsFactory, factory))

    result_ref = asyncio.run(executor.execute(_request(year=2024), _executor_context(events, operands)))

    assert result_ref == "balance-reference"
    assert factory.requested == [str(_PROFILE)]
    assert factory.operations == [_AUTHORITY]
    assert seen == [(2024, repository, _AUTHORITY)]
    assert events.phases == [f"{MODELO_IVA_WALLET_BALANCE_OPERATION_DEFINITION_ID}.read"]
    assert events.effects == [OperationEffect.NONE]
    report = cast(ModeloIvaWalletBalanceOperationReport, operands.values[0])
    projection = report.projection
    assert projection.profile_id == _PROFILE
    assert projection.as_of_year == 2024
    assert projection.total_balance == "500.00"
    assert projection.next_expiry_year == 2028

    receipt = OperationTerminalReceipt(
        identity=OperationIdentity(
            operation_id="a" * 64,
            definition_id=MODELO_IVA_WALLET_BALANCE_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(_PROFILE)),
        ),
        revision=3,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.NONE,
        settled_at=datetime(2026, 9, 29, 10, 0, tzinfo=UTC),
        result_ref=result_ref,
    )
    assert project_modelo_iva_wallet_balance_result(report, receipt) == projection


def test_executor_refuses_a_factory_bundle_for_another_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    events = _Events()
    operands = _Operands()
    factory = _Factory(object(), selected_bucket=str(_OTHER_PROFILE))
    monkeypatch.setattr(
        "cadrumo.application.modelo.iva_wallet_balance_operation.require_active_bucket_id",
        lambda: str(_PROFILE),
    )
    monkeypatch.setattr("cadrumo.application.operations.profile_guard.require_active_bucket_id", lambda: str(_PROFILE))
    executor = ModeloIvaWalletBalanceExecutor(cast(ModeloIvaWalletSeedPortsFactory, factory))

    with pytest.raises(ProfileAccessRefusedError) as refused:
        asyncio.run(executor.execute(_request(), _executor_context(events, operands)))

    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH
    assert factory.operations == [_AUTHORITY]
    assert events.effects == []
    assert operands.values == []
