"""Contract tests for exact-profile non-invoice aggregate operations."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from cadrumo.core.aggregation import (
    AggregationCaptureKind,
    BindingSourceKind,
    ForeignAssetClass,
    RetencionClave,
    RetencionScheme,
)
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.withholding_bindings import WithholdingObservation
from cadrumo.domain.transactions.models import TransactionCatalogue

from ...aggregation.counterpart import CounterpartObservation
from ...aggregation.foreign_assets import ForeignAssetIngestObservation
from ...aggregation.ledger_payment_withholding import LedgerPaymentWithholdingEvidenceRequest
from ...aggregation.retenciones import RetencionObservation
from ...aggregation.service import PerModeloAggregationCommand, PerModeloAggregationContributor, aggregate_per_modelo
from ...aggregation.tests.withholding_filer_profile_support import withholding_filer_cadence
from ...aggregation.withholding_observation_service import (
    WithholdingObservationMutationError,
    WithholdingWindowBaseline,
    WithholdingWindowScope,
)
from ...aggregation.withholding_recognition import (
    WithholdingIncomeKind,
    WithholdingRecipientTaxRegime,
    WithholdingRecipientTaxStatus,
)
from ...operations.access_resolution import OperationAccessContext
from ...operations.capabilities import OperationRequestStoragePolicy, OperationSensitiveInputPolicy
from ...operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from ...operations.owner import OperationExecutorContext
from ...operations.public_period import PublicPeriod
from ...operations.refusal_evidence import OperationRefusalEvidence
from ...operations.registry import OperationFrontendProjection
from ...user_profile.access_contracts import AccessAction, AccessDenialCode, Availability
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..aggregate_operation import (
    MODELO_AGGREGATE_OPERATION_DEFINITION_ID,
    MODELO_AGGREGATE_UNSUPPORTED_MODELO_REFUSAL_CODE,
    ModeloAggregateExecutor,
    ModeloAggregateOperationPorts,
    ModeloAggregateOperationPortsFactory,
    ModeloAggregateOperationRequest,
    ModeloAggregateProjection,
    ModeloAggregateReport,
    build_modelo_aggregate_operation_definition,
    build_modelo_aggregate_operation_registration,
    project_modelo_aggregate_result,
    resolve_modelo_aggregate_access,
)
from ..aggregate_public import PublicModeloAggregateCommand
from .withholding_window_operation_test_support import WithholdingWindowServiceFixture

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("21212121-2121-4121-8121-212121212121")
_OTHER_PROFILE = UUID("33333333-3333-4333-8333-333333333333")
_PERIOD = Period.from_year_and_code(2025, "1T")
_RESULT_REF = "e" * 64
_SCOPE = WithholdingWindowScope(modelo="111", period=_PERIOD)
_BASELINE = WithholdingWindowBaseline(scope_token=_SCOPE.token, generation_id="a" * 64)


def _command(*, modelo: str = "111", period: Period = _PERIOD) -> PerModeloAggregationCommand:
    return PerModeloAggregationCommand(modelo=modelo, period=period)


def _capital_capture_request() -> LedgerPaymentWithholdingEvidenceRequest:
    return LedgerPaymentWithholdingEvidenceRequest(
        transaction_id="1" * 64,
        income_kind=WithholdingIncomeKind.ORDINARY_MOVABLE_CAPITAL,
        scheme=RetencionScheme("intereses"),
        recipient_tax_status=WithholdingRecipientTaxStatus.RESIDENT,
        recipient_tax_regime=WithholdingRecipientTaxRegime.IRPF,
        payment_event_id="payment-2025-02",
        allocation_id="allocation-1",
        gross_base=Decimal("100.00"),
        withholding_amount=Decimal("19.00"),
        net_settlement=Decimal("81.00"),
        idempotency_key="capture-1",
        perceptor_nif="11111111H",
        perceptor_name="Annual detail subject",
        exigibility_event_id="exigible-2025-01",
        exigibility_occurred_on=date(2025, 1, 10),
    )


def _request(
    *,
    command: PerModeloAggregationCommand | None = None,
    profile_id: UUID = _PROFILE,
    ledger_payment: LedgerPaymentWithholdingEvidenceRequest | None = None,
) -> OperationRequest[ModeloAggregateOperationRequest]:
    return OperationRequest[ModeloAggregateOperationRequest](
        definition_id=MODELO_AGGREGATE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(profile_id)),
        payload=ModeloAggregateOperationRequest.from_inputs(
            profile_id=profile_id,
            command=command or _command(),
            ledger_payment=ledger_payment,
        ),
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
        return _RESULT_REF


class _TransactionRepository:
    def __init__(self, *, profile_id: UUID = _PROFILE) -> None:
        self.bucket_id = str(profile_id)
        self.revisions: list[str | None] = []
        self.catalogue = TransactionCatalogue()

    def load_revision(self) -> str | None:
        return self.revisions.pop(0) if self.revisions else "b" * 64

    def load_by_ids(self, transaction_ids: tuple[str, ...]) -> TransactionCatalogue:
        return self.catalogue


class _RetencionRepository:
    def __init__(self, observations: tuple[RetencionObservation, ...] = ()) -> None:
        self.observations = observations
        self.loads: list[tuple[str, Period]] = []

    def load_observations(self, modelo: str, period: Period) -> tuple[RetencionObservation, ...]:
        self.loads.append((modelo, period))
        return self.observations

    def replace_observations(
        self,
        *,
        modelo: str,
        filing_year: int,
        period: Period,
        observations: Sequence[RetencionObservation],
        source_kind: AggregationCaptureKind,
        captured_at: datetime | None = None,
        source_metadata: Mapping[str, str] | None = None,
    ) -> None:
        raise AssertionError("the aggregate read must not replace observations")

    def load_annual_source_observations(self, source_modelo: str, filing_year: int) -> tuple[RetencionObservation, ...]:
        raise AssertionError("the periodic aggregate must not read annual observations")

    def load_source_observations_through_year(
        self, source_modelo: str, last_filing_year: int
    ) -> tuple[RetencionObservation, ...]:
        raise AssertionError("the periodic aggregate must not read historical observations")


class _PercepcionRepository:
    def __init__(self, annual: tuple[WithholdingObservation, ...] = ()) -> None:
        self.annual = annual
        self.annual_loads: list[tuple[str, int]] = []

    def load_observations(self, modelo: str, period: Period) -> tuple[WithholdingObservation, ...]:
        raise AssertionError("an annual summary composes its periodic windows, not a window of its own")

    def load_annual_source_observations(
        self, source_modelo: str, filing_year: int
    ) -> tuple[WithholdingObservation, ...]:
        self.annual_loads.append((source_modelo, filing_year))
        return self.annual

    def replace_observations(
        self,
        *,
        modelo: str,
        filing_year: int,
        period: Period,
        observations: Sequence[WithholdingObservation],
        source_kind: AggregationCaptureKind,
        captured_at: datetime | None = None,
        source_metadata: Mapping[str, str] | None = None,
    ) -> None:
        raise AssertionError("the aggregate read must not replace observations")


class _WindowService(WithholdingWindowServiceFixture):
    def __init__(self, *, generation: int = 0, observations: tuple[RetencionObservation, ...] = ()) -> None:
        super().__init__(baseline=_BASELINE, generation=generation, observations=observations)


def _ports(
    *,
    observations: tuple[RetencionObservation, ...] = (),
    window_service: _WindowService | None = None,
    transaction_repository: _TransactionRepository | None = None,
    percepciones: _PercepcionRepository | None = None,
) -> ModeloAggregateOperationPorts:
    return ModeloAggregateOperationPorts(
        profile_id=str(_PROFILE),
        transaction_catalogue_repository=transaction_repository or _TransactionRepository(),
        retencion_observation_repository=_RetencionRepository(observations),
        percepcion_observation_repository=percepciones or _PercepcionRepository(),
        withholding_observation_service=window_service or _WindowService(observations=observations),
    )


def _executor_context(
    events: _Events, operands: _Operands, *, authority_operation: PinnedAuthorityOperation | None = None
) -> OperationExecutorContext:
    return cast(
        OperationExecutorContext,
        SimpleNamespace(
            identity=OperationIdentity(
                operation_id="d" * 64,
                definition_id=MODELO_AGGREGATE_OPERATION_DEFINITION_ID,
                subject_ref=profile_operation_subject(str(_PROFILE)),
            ),
            authority_operation=authority_operation,
            cancellation=_Cancellation(),
            events=events,
            operands=operands,
        ),
    )


def _terminal_receipt(
    *,
    effect: OperationEffect,
    refused: bool = False,
    refusal_code: str = MODELO_AGGREGATE_UNSUPPORTED_MODELO_REFUSAL_CODE,
) -> OperationTerminalReceipt:
    identity = OperationIdentity(
        operation_id="d" * 64,
        definition_id=MODELO_AGGREGATE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
    )
    if refused:
        return OperationTerminalReceipt(
            identity=identity,
            revision=2,
            condition=OperationTerminalCondition.REFUSED,
            effect=OperationEffect.NONE,
            settled_at=datetime.now(UTC),
            refusal_ref=refusal_code,
            refusal_detail_ref="f" * 64,
        )
    return OperationTerminalReceipt(
        identity=identity,
        revision=2,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=effect,
        settled_at=datetime.now(UTC),
        result_ref=_RESULT_REF,
    )


def test_definition_and_access_are_profile_and_period_scoped() -> None:
    factory = cast(ModeloAggregateOperationPortsFactory, cast(object, lambda **_kwargs: None))
    definition = build_modelo_aggregate_operation_definition(factory)
    registration = build_modelo_aggregate_operation_registration(definition)
    request = _request()

    assert definition.capabilities.request_storage is OperationRequestStoragePolicy.SECURE_REFERENCE
    assert definition.capabilities.sensitive_input is OperationSensitiveInputPolicy.SECURE_REFERENCE
    assert definition.permitted_frontends == frozenset(
        {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI, OperationFrontendProjection.MCP}
    )
    context = OperationAccessContext(
        profile_id=_PROFILE,
        destination_id=uuid4(),
        action=AccessAction.SUBMIT,
        frontend=OperationFrontendProjection.CLI,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
    )

    resolved = resolve_modelo_aggregate_access(cast(OperationRequest[BaseModel], cast(object, request)), context)
    assert resolved.request.periods == frozenset({_PERIOD})
    assert not resolved.request.period_independent
    assert not resolved.policy.requires_all_periods
    assert AccessAction.COMMIT not in resolved.policy.actions

    capture_request = _request(command=_command(modelo="123"), ledger_payment=_capital_capture_request())
    capture_resolved = resolve_modelo_aggregate_access(
        cast(OperationRequest[BaseModel], cast(object, capture_request)),
        context,
    )
    assert capture_resolved.request.periods == frozenset()
    assert capture_resolved.request.period_independent
    assert capture_resolved.policy.requires_all_periods
    assert AccessAction.COMMIT in capture_resolved.policy.actions

    with pytest.raises(ProfileAccessRefusedError) as refused:
        resolve_modelo_aggregate_access(
            cast(OperationRequest[BaseModel], cast(object, request)),
            replace(context, profile_id=_OTHER_PROFILE),
        )
    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH


def test_request_rejects_caller_retenciones_and_mixed_capture_before_execution() -> None:
    observation = RetencionObservation(
        source_kind=BindingSourceKind.LEDGER_TRANSACTION,
        source_object_id="transaction-1",
        perceptor_nif="11111111H",
        perceptor_name="Private subject",
        scheme=RetencionScheme("actividades_profesionales"),
        taxable_base=Decimal("100.00"),
        retencion_amount=Decimal("15.00"),
        accrued_on="2025-01-15",
    )
    with pytest.raises(ValueError, match="read from storage"):
        ModeloAggregateOperationRequest.from_inputs(
            profile_id=_PROFILE,
            command=_command().model_copy(update={"retencion_observations": (observation,)}),
        )

    with pytest.raises(ValidationError, match="only for Modelos 111 and 123"):
        ModeloAggregateOperationRequest.from_inputs(
            profile_id=_PROFILE,
            command=_command(modelo="115"),
            ledger_payment=_capital_capture_request(),
        )


def test_public_command_round_trips_each_supported_observation_family() -> None:
    counterpart = CounterpartObservation(
        source_kind=BindingSourceKind.PAYABLE_INVOICE,
        source_object_id="invoice-1",
        counterparty_nif="FR12345678901",
        counterparty_name="Counterpart",
        counterparty_country="FR",
        operation_kind="E",
        operation_period="1T",
        taxable_base=Decimal("200.10"),
        invoice_total=Decimal("242.12"),
        accrued_on="2025-02-10",
    )
    foreign_asset = ForeignAssetIngestObservation(
        source_kind=BindingSourceKind.PURCHASE_INVOICE_EVIDENCE,
        source_object_id="evidence-1",
        asset_class=ForeignAssetClass.ACCOUNT,
        asset_external_id="bank-account-1",
        country="FR",
        issuer_or_institution="Bank",
        valuation_eur=Decimal("50000.50"),
        acquisition_date="2024-06-30",
        held_at_year_end=True,
    )
    command = PerModeloAggregationCommand(
        modelo="347",
        period=_PERIOD,
        counterpart_observations=(counterpart,),
        foreign_asset_observations=(foreign_asset,),
    )

    public_command = PublicModeloAggregateCommand.from_domain(command)

    assert public_command.to_domain() == command


def test_regular_aggregate_reads_profile_rows_and_publishes_no_evidence(
    monkeypatch: pytest.MonkeyPatch,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    events = _Events()
    operands = _Operands()
    retenciones = _RetencionRepository()
    window_service = _WindowService()
    transaction_repository = _TransactionRepository()
    ports = ModeloAggregateOperationPorts(
        profile_id=str(_PROFILE),
        transaction_catalogue_repository=transaction_repository,
        retencion_observation_repository=retenciones,
        percepcion_observation_repository=_PercepcionRepository(),
        withholding_observation_service=window_service,
    )
    executor = ModeloAggregateExecutor(cast(ModeloAggregateOperationPortsFactory, cast(object, lambda **_kw: ports)))
    request = _request()
    context = _executor_context(events, operands, authority_operation=authority_operation)
    monkeypatch.setattr(
        "cadrumo.application.modelo.aggregate_operation.require_active_bucket_id",
        lambda: str(_PROFILE),
    )
    monkeypatch.setattr("cadrumo.application.operations.profile_guard.require_active_bucket_id", lambda: str(_PROFILE))

    result_ref = asyncio.run(executor.execute(request, context))

    assert result_ref == _RESULT_REF
    assert retenciones.loads == []
    assert window_service.reads == [_SCOPE]
    assert events.effects == [OperationEffect.NONE]
    report = operands.values[0]
    assert isinstance(report, ModeloAggregateReport)
    projection = project_modelo_aggregate_result(report, _terminal_receipt(effect=OperationEffect.NONE))
    assert isinstance(projection, ModeloAggregateProjection)
    assert projection.outcome == "aggregated"
    assert projection.provider is PerModeloAggregationContributor.RETENCIONES
    assert projection.observation_count == 0
    assert projection.period == PublicPeriod.from_period(_PERIOD)
    assert projection.withholding_window is not None
    assert projection.clave_breakdown == ()
    assert projection.absent_source_families == ()
    assert projection.calculation_revision_id is None
    serialized = projection.model_dump(mode="json")
    assert not {"perceptor_nif", "perceptor_name", "taxable_base", "retencion_amount", "observations"} & set(serialized)


_ANNUAL_PERIOD = Period.from_year_and_code(2025, "0A")


def _percepcion(source_id: str, nif: str, clave: str) -> WithholdingObservation:
    return WithholdingObservation(
        source_id=source_id,
        perceptor_tax_id=nif,
        transaction_date=date(2025, 2, 1),
        clave=RetencionClave.from_registry(clave),
        percibido_dinerario=Decimal("1000.00"),
        retencion_practicada=Decimal("150.00"),
        incapacity_cash_perception=Decimal("0"),
        incapacity_cash_withholding=Decimal("0"),
        incapacity_kind_value=Decimal("0"),
        incapacity_kind_ingreso_a_cuenta=Decimal("0"),
        incapacity_kind_repercutido=Decimal("0"),
        foral_retention_estatal=Decimal("0"),
        foral_retention_navarra=Decimal("0"),
        foral_retention_araba=Decimal("0"),
        foral_retention_gipuzkoa=Decimal("0"),
        foral_retention_bizkaia=Decimal("0"),
        base_retenciones=Decimal("1000.00"),
    )


def _run_annual_190(
    monkeypatch: pytest.MonkeyPatch,
    authority_operation: PinnedAuthorityOperation,
    percepciones: _PercepcionRepository,
) -> tuple[ModeloAggregateProjection, _Events]:
    events = _Events()
    operands = _Operands()
    window_service = _WindowService()
    ports = _ports(window_service=window_service, percepciones=percepciones)
    executor = ModeloAggregateExecutor(cast(ModeloAggregateOperationPortsFactory, cast(object, lambda **_kw: ports)))
    context = _executor_context(events, operands, authority_operation=authority_operation)
    monkeypatch.setattr(
        "cadrumo.application.modelo.aggregate_operation.require_active_bucket_id", lambda: str(_PROFILE)
    )
    monkeypatch.setattr("cadrumo.application.operations.profile_guard.require_active_bucket_id", lambda: str(_PROFILE))
    # The bucket's stored profile is outside this unit; resolve an ordinary filer canonically instead.
    monkeypatch.setattr(
        "cadrumo.application.modelo.aggregate_operation.load_bucket_withholding_filer_cadence",
        lambda *, bucket_id, filing_year, operation: withholding_filer_cadence(operation, filing_year=filing_year),
    )

    asyncio.run(executor.execute(_request(command=_command(modelo="190", period=_ANNUAL_PERIOD)), context))

    report = operands.values[0]
    assert isinstance(report, ModeloAggregateReport)
    projection = project_modelo_aggregate_result(report, _terminal_receipt(effect=OperationEffect.NONE))
    assert isinstance(projection, ModeloAggregateProjection)
    assert window_service.reads == []
    return projection, events


def test_annual_summary_projects_the_per_clave_rows_its_calculation_reads(
    monkeypatch: pytest.MonkeyPatch,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Modelo 190 composes the year's Modelo 111 detail and reports it per clave without perceptor identities."""
    percepciones = _PercepcionRepository(
        (
            _percepcion("row-1", "11111111H", "A"),
            _percepcion("row-2", "22222222J", "A"),
            _percepcion("row-3", "33333333P", "G"),
        )
    )

    projection, events = _run_annual_190(monkeypatch, authority_operation, percepciones)

    assert percepciones.annual_loads == [("111", 2025)]
    assert events.effects == [OperationEffect.NONE]
    assert projection.outcome == "aggregated"
    assert projection.absent_source_families == ()
    assert projection.calculation_revision_id is not None
    assert [
        (row.clave, row.percepcion_count, row.percibido_total.decimal, row.retencion_total.decimal)
        for row in projection.clave_breakdown or ()
    ] == [("A", 2, "2000.00", "300.00"), ("G", 1, "1000.00", "150.00")]
    serialized = projection.model_dump_json()
    assert "11111111H" not in serialized
    assert "row-1" not in serialized


def test_annual_summary_without_stored_rows_names_the_absent_family_instead_of_a_zero(
    monkeypatch: pytest.MonkeyPatch,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """An empty composition is reported as missing data, not as a proven zero."""
    percepciones = _PercepcionRepository()

    projection, _events = _run_annual_190(monkeypatch, authority_operation, percepciones)

    assert percepciones.annual_loads == [("111", 2025)]
    assert projection.clave_breakdown == ()
    assert projection.absent_source_families == (BindingSourceKind.WITHHOLDING,)
    assert projection.calculation_revision_id is not None


def _snapshot_observation() -> RetencionObservation:
    return RetencionObservation(
        source_kind=BindingSourceKind.LEDGER_TRANSACTION,
        source_object_id="1" * 64,
        perceptor_nif="11111111H",
        perceptor_name="Synthetic recipient",
        scheme=RetencionScheme("actividades_profesionales"),
        taxable_base=Decimal("100.00"),
        retencion_amount=Decimal("15.00"),
        accrued_on="2025-01-15",
    )


def test_read_aggregate_retains_rows_and_generation_from_prepared_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    events = _Events()
    operands = _Operands()
    service = _WindowService(generation=1, observations=(_snapshot_observation(),))
    ports = _ports(window_service=service)
    executor = ModeloAggregateExecutor(
        cast(ModeloAggregateOperationPortsFactory, cast(object, lambda **_kwargs: ports))
    )
    context = _executor_context(events, operands, authority_operation=authority_operation)
    monkeypatch.setattr(
        "cadrumo.application.modelo.aggregate_operation.require_active_bucket_id", lambda: str(_PROFILE)
    )
    monkeypatch.setattr("cadrumo.application.operations.profile_guard.require_active_bucket_id", lambda: str(_PROFILE))

    def aggregate_then_advance(command: PerModeloAggregationCommand, *, operation: PinnedAuthorityOperation):
        result = aggregate_per_modelo(command, operation=operation)
        service.generation = 2
        service.observations = ()
        service.baseline = WithholdingWindowBaseline(scope_token=_SCOPE.token, generation_id="f" * 64)
        return result

    monkeypatch.setattr("cadrumo.application.modelo.aggregate_operation.aggregate_per_modelo", aggregate_then_advance)

    asyncio.run(executor.execute(_request(), context))

    report = operands.values[0]
    assert isinstance(report, ModeloAggregateReport)
    assert report.projection.observation_count == 1
    assert report.projection.withholding_window is not None
    assert report.projection.withholding_window.generation == 1
    assert report.projection.withholding_window.baseline.generation_id == _BASELINE.generation_id
    assert service.generation == 2
    assert service.reads == [_SCOPE]
    assert service.audit_reads == [(_SCOPE, _BASELINE.generation_id)]


@pytest.mark.parametrize(
    ("replayed", "expected_effect"),
    ((False, OperationEffect.UPDATED), (True, OperationEffect.NONE)),
)
def test_ledger_capture_reports_updated_or_replay_without_releasing_rows(
    monkeypatch: pytest.MonkeyPatch,
    authority_operation: PinnedAuthorityOperation,
    replayed: bool,
    expected_effect: OperationEffect,
) -> None:
    events = _Events()
    operands = _Operands()
    window_service = _WindowService(generation=2, observations=(_snapshot_observation(),))
    ports = _ports(window_service=window_service)
    executor = ModeloAggregateExecutor(
        cast(ModeloAggregateOperationPortsFactory, cast(object, lambda **_kwargs: ports))
    )
    request = _request(command=_command(), ledger_payment=_capital_capture_request())
    context = _executor_context(events, operands, authority_operation=authority_operation)
    prepared = SimpleNamespace(
        ports=ports,
        aggregate_command=_command(),
        preflight_result=SimpleNamespace(provider=PerModeloAggregationContributor.RETENCIONES),
        capture=SimpleNamespace(command=object(), scope=_SCOPE, catalogue_read_revision_id="b" * 64),
        cadence=object(),
        calculation_rows=None,
    )
    monkeypatch.setattr(
        "cadrumo.application.modelo.aggregate_operation.require_active_bucket_id",
        lambda: str(_PROFILE),
    )
    monkeypatch.setattr("cadrumo.application.operations.profile_guard.require_active_bucket_id", lambda: str(_PROFILE))
    monkeypatch.setattr(executor, "_prepare", lambda *_args: prepared)

    def aggregate_then_advance(command: PerModeloAggregationCommand, *, operation: PinnedAuthorityOperation):
        result = aggregate_per_modelo(command, operation=operation)
        window_service.generation = 3
        window_service.observations = ()
        window_service.baseline = WithholdingWindowBaseline(scope_token=_SCOPE.token, generation_id="f" * 64)
        return result

    monkeypatch.setattr("cadrumo.application.modelo.aggregate_operation.aggregate_per_modelo", aggregate_then_advance)

    class _Producer:
        def __init__(self, *, service: object) -> None:
            self.service = service

        def capture(self, _command: object, *, cadence: object, source_catalogue_revision_id: str):
            assert cadence is prepared.cadence
            assert source_catalogue_revision_id == prepared.capture.catalogue_read_revision_id
            return SimpleNamespace(scope=_SCOPE, mutation=SimpleNamespace(replayed=replayed))

    monkeypatch.setattr("cadrumo.application.modelo.aggregate_operation.WithholdingProducer", _Producer)

    result_ref = asyncio.run(executor.execute(request, context))

    assert result_ref == _RESULT_REF
    assert events.effects == [OperationEffect.UNKNOWN, expected_effect]
    assert window_service.reads == [_SCOPE]
    report = operands.values[0]
    assert isinstance(report, ModeloAggregateReport)
    projection = project_modelo_aggregate_result(report, _terminal_receipt(effect=expected_effect))
    assert isinstance(projection, ModeloAggregateProjection)
    assert projection.observation_count == 1
    assert projection.withholding_window is not None
    assert projection.withholding_window.generation == 2
    assert projection.withholding_window.baseline.generation_id == _BASELINE.generation_id
    assert window_service.generation == 3
    assert window_service.audit_reads == [(_SCOPE, _BASELINE.generation_id)]
    assert projection.withholding_window.generation_audit is not None
    assert not {"perceptor_nif", "perceptor_name", "transaction_id", "entries"} & set(
        projection.model_dump(mode="json")
    )


@pytest.mark.parametrize(
    "refusal_code",
    ("storage_delivery_ambiguous", "source_revision_changed", "source_revision_unavailable"),
)
def test_ledger_source_conflict_refuses_and_ambiguous_write_keeps_effect_unknown(
    monkeypatch: pytest.MonkeyPatch,
    refusal_code: str,
) -> None:
    events = _Events()
    operands = _Operands()
    ports = _ports()
    executor = ModeloAggregateExecutor(
        cast(ModeloAggregateOperationPortsFactory, cast(object, lambda **_kwargs: ports))
    )
    request = _request(command=_command(), ledger_payment=_capital_capture_request())
    context = _executor_context(events, operands)
    prepared = SimpleNamespace(
        ports=ports,
        aggregate_command=_command(),
        preflight_result=SimpleNamespace(provider=PerModeloAggregationContributor.RETENCIONES),
        capture=SimpleNamespace(command=object(), scope=_SCOPE, catalogue_read_revision_id="b" * 64),
        cadence=object(),
        calculation_rows=None,
    )
    monkeypatch.setattr(
        "cadrumo.application.modelo.aggregate_operation.require_active_bucket_id",
        lambda: str(_PROFILE),
    )
    monkeypatch.setattr("cadrumo.application.operations.profile_guard.require_active_bucket_id", lambda: str(_PROFILE))
    monkeypatch.setattr(executor, "_prepare", lambda *_args: prepared)

    class _Producer:
        def __init__(self, *, service: object) -> None:
            self.service = service

        def capture(self, _command: object, *, cadence: object, source_catalogue_revision_id: str):
            del cadence
            assert source_catalogue_revision_id == prepared.capture.catalogue_read_revision_id
            raise WithholdingObservationMutationError(refusal_code)

    monkeypatch.setattr("cadrumo.application.modelo.aggregate_operation.WithholdingProducer", _Producer)

    if refusal_code == "source_revision_changed":
        result = asyncio.run(executor.execute(request, context))
        assert isinstance(result, OperationRefusalEvidence)
        assert result.refusal_code == "REFUSED_LEDGER_PAYMENT_WITHHOLDING_EVIDENCE"
        assert events.effects == [OperationEffect.UNKNOWN, OperationEffect.NONE]
        report = operands.values[0]
        assert isinstance(report, ModeloAggregateReport)
        projection = project_modelo_aggregate_result(
            report,
            _terminal_receipt(effect=OperationEffect.NONE, refused=True, refusal_code=result.refusal_code),
        )
        assert isinstance(projection, ModeloAggregateProjection)
        assert projection.refusal_reason == "source_revision_changed"
        assert isinstance(ports.withholding_observation_service, _WindowService)
        assert ports.withholding_observation_service.reads == []
    else:
        with pytest.raises(WithholdingObservationMutationError):
            asyncio.run(executor.execute(request, context))

        assert events.effects == [OperationEffect.UNKNOWN]
        assert operands.values == []


def test_catalogue_revision_change_before_commit_refuses_without_producer_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events = _Events()
    operands = _Operands()
    transaction_repository = _TransactionRepository()
    transaction_repository.revisions = ["f" * 64]
    ports = _ports(transaction_repository=transaction_repository)
    executor = ModeloAggregateExecutor(
        cast(ModeloAggregateOperationPortsFactory, cast(object, lambda **_kwargs: ports))
    )
    request = _request(command=_command(), ledger_payment=_capital_capture_request())
    context = _executor_context(events, operands)
    prepared = SimpleNamespace(
        ports=ports,
        aggregate_command=_command(),
        preflight_result=SimpleNamespace(provider=PerModeloAggregationContributor.RETENCIONES),
        capture=SimpleNamespace(
            command=object(),
            scope=_SCOPE,
            catalogue_read_revision_id="b" * 64,
        ),
        cadence=object(),
        calculation_rows=None,
    )
    monkeypatch.setattr(
        "cadrumo.application.modelo.aggregate_operation.require_active_bucket_id",
        lambda: str(_PROFILE),
    )
    monkeypatch.setattr("cadrumo.application.operations.profile_guard.require_active_bucket_id", lambda: str(_PROFILE))
    monkeypatch.setattr(executor, "_prepare", lambda *_args: prepared)

    result = asyncio.run(executor.execute(request, context))

    assert isinstance(result, OperationRefusalEvidence)
    assert result.refusal_code == "REFUSED_LEDGER_PAYMENT_WITHHOLDING_EVIDENCE"
    assert events.effects == [OperationEffect.NONE]
    assert len(operands.values) == 1
    report = operands.values[0]
    assert isinstance(report, ModeloAggregateReport)
    assert report.projection.outcome == "refused"
    assert report.projection.refusal_reason == "transaction_catalogue_revision_changed"


def test_canonically_invalid_public_ledger_operands_refuse_before_capture(
    monkeypatch: pytest.MonkeyPatch,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    events = _Events()
    operands = _Operands()
    repository = _TransactionRepository()
    repository.revisions = ["b" * 64]
    ports = _ports(transaction_repository=repository)
    executor = ModeloAggregateExecutor(
        cast(ModeloAggregateOperationPortsFactory, cast(object, lambda **_kwargs: ports))
    )
    request = _request(ledger_payment=_capital_capture_request())
    public_payload = request.payload.model_dump(mode="python")
    public_payload["ledger_payment"]["income_kind"] = WithholdingIncomeKind.PROFESSIONAL
    request = request.model_copy(update={"payload": ModeloAggregateOperationRequest.model_validate(public_payload)})
    context = _executor_context(events, operands, authority_operation=authority_operation)
    monkeypatch.setattr(
        "cadrumo.application.modelo.aggregate_operation.require_active_bucket_id", lambda: str(_PROFILE)
    )
    monkeypatch.setattr("cadrumo.application.operations.profile_guard.require_active_bucket_id", lambda: str(_PROFILE))

    result = asyncio.run(executor.execute(request, context))

    assert isinstance(result, OperationRefusalEvidence)
    assert result.refusal_code == "REFUSED_LEDGER_PAYMENT_WITHHOLDING_EVIDENCE"
    assert events.effects == [OperationEffect.NONE]
    assert repository.revisions == ["b" * 64]
    report = operands.values[0]
    assert isinstance(report, ModeloAggregateReport)
    projection = project_modelo_aggregate_result(
        report,
        _terminal_receipt(effect=OperationEffect.NONE, refused=True, refusal_code=result.refusal_code),
    )
    assert isinstance(projection, ModeloAggregateProjection)
    assert projection.refusal_reason == "invalid_evidence"
