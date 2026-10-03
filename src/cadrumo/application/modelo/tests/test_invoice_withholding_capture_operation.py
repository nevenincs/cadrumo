"""Focused contract and custody tests for invoice withholding capture."""

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

from cadrumo.core.aggregation import BindingSourceKind, RetencionClave, RetencionScheme
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.governed_fact_scope import validating_governed_facts
from cadrumo.domain.calculations.registry.withholding_bindings import WithholdingObservation

from ...aggregation.invoice_retencion import (
    InvoiceRetencionProjectionDefect,
    InvoiceWithholdingCapture,
    InvoiceWithholdingDefectsError,
    InvoiceWithholdingEvidenceError,
    InvoiceWithholdingEvidenceRequest,
)
from ...aggregation.retenciones import RetencionObservation
from ...aggregation.service import PerModeloAggregationCommand, aggregate_per_modelo
from ...aggregation.withholding_filing_cadence import WithholdingFilerCadence
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
from ...user_profile.access_contracts import AccessAction, AccessDenialCode, Availability, OperationAccessRequest
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..invoice_withholding_capture_contracts import (
    MODELO_INVOICE_WITHHOLDING_CAPTURE_OPERATION_DEFINITION_ID,
    MODELO_INVOICE_WITHHOLDING_CAPTURE_REFUSAL_CODE,
    MODELO_INVOICE_WITHHOLDING_CAPTURE_REFUSAL_CODES,
    MODELO_INVOICE_WITHHOLDING_DEFECTS_REFUSAL_CODE,
    ModeloInvoiceWithholdingCapturePorts,
    ModeloInvoiceWithholdingCapturePortsFactory,
    ModeloInvoiceWithholdingCaptureProjection,
    ModeloInvoiceWithholdingCaptureReport,
    ModeloInvoiceWithholdingCaptureRequest,
)
from ..invoice_withholding_capture_execution import ModeloInvoiceWithholdingCaptureExecutor, _PreparedCapture
from ..invoice_withholding_capture_operation import (
    build_modelo_invoice_withholding_capture_definition,
    build_modelo_invoice_withholding_capture_registration,
    resolve_modelo_invoice_withholding_capture_access,
)
from ..invoice_withholding_capture_projection import project_modelo_invoice_withholding_capture_result
from ..invoice_withholding_capture_public import PublicInvoiceWithholdingEvidence
from .withholding_window_operation_test_support import WithholdingWindowServiceFixture

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("21212121-2121-4121-8121-212121212121")
_OTHER_PROFILE = UUID("33333333-3333-4333-8333-333333333333")
_OPERAND_REF = "e" * 64
_PERIOD = PublicPeriod(filing_year=2024, code="1T")
_SCOPE = WithholdingWindowScope(modelo="111", period=_PERIOD.to_period())
_BASELINE = WithholdingWindowBaseline(scope_token=_SCOPE.token, generation_id="a" * 64)


def _evidence() -> InvoiceWithholdingEvidenceRequest:
    return InvoiceWithholdingEvidenceRequest(
        invoice_id="b" * 64,
        income_kind=WithholdingIncomeKind.PROFESSIONAL,
        scheme=RetencionScheme("actividades_profesionales"),
        recipient_tax_status=WithholdingRecipientTaxStatus.RESIDENT,
        recipient_tax_regime=WithholdingRecipientTaxRegime.IRPF,
        allocation_id="allocation-1",
        allocated_base=Decimal("100.00"),
        allocated_withholding=Decimal("15.00"),
        allocated_settlement=Decimal("85.00"),
        idempotency_key="capture-1",
    )


def _command(*, modelo: str = "111", retenciones: tuple[RetencionObservation, ...] = ()) -> PerModeloAggregationCommand:
    return PerModeloAggregationCommand(
        modelo=modelo,
        period=_PERIOD.to_period(),
        retencion_observations=retenciones,
    )


def _request(*, profile_id: UUID = _PROFILE) -> OperationRequest[ModeloInvoiceWithholdingCaptureRequest]:
    return OperationRequest[ModeloInvoiceWithholdingCaptureRequest](
        definition_id=MODELO_INVOICE_WITHHOLDING_CAPTURE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(profile_id)),
        payload=ModeloInvoiceWithholdingCaptureRequest.from_inputs(
            profile_id=profile_id,
            command=_command(),
            evidence=_evidence(),
        ),
    )


def _definition_and_registration():
    factory = cast(ModeloInvoiceWithholdingCapturePortsFactory, cast(object, lambda **_kwargs: None))
    definition = build_modelo_invoice_withholding_capture_definition(factory)
    return definition, build_modelo_invoice_withholding_capture_registration(definition)


def test_definition_and_access_are_confidential_exact_profile_and_period_scoped() -> None:
    definition, registration = _definition_and_registration()
    request = _request()

    assert definition.capabilities.request_storage is OperationRequestStoragePolicy.SECURE_REFERENCE
    assert definition.capabilities.sensitive_input is OperationSensitiveInputPolicy.SECURE_REFERENCE
    assert definition.refusal_detail_codes == MODELO_INVOICE_WITHHOLDING_CAPTURE_REFUSAL_CODES
    assert (
        frozenset({MODELO_INVOICE_WITHHOLDING_CAPTURE_REFUSAL_CODE, MODELO_INVOICE_WITHHOLDING_DEFECTS_REFUSAL_CODE})
        == MODELO_INVOICE_WITHHOLDING_CAPTURE_REFUSAL_CODES
    )
    assert definition.permitted_frontends == frozenset(
        {
            OperationFrontendProjection.CLI,
            OperationFrontendProjection.TUI,
            OperationFrontendProjection.MCP,
        }
    )
    assert definition.capabilities.permitted_effects == frozenset(
        {OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.UNKNOWN}
    )
    context = OperationAccessContext(
        profile_id=_PROFILE,
        destination_id=uuid4(),
        action=AccessAction.SUBMIT,
        frontend=OperationFrontendProjection.CLI,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
    )

    resolved = resolve_modelo_invoice_withholding_capture_access(
        cast(OperationRequest[BaseModel], cast(object, request)), context
    )

    assert resolved.request.periods == frozenset()
    assert resolved.request.period_independent
    assert resolved.policy.requires_all_periods
    assert AccessAction.COMMIT in resolved.policy.actions
    narrow_request = OperationAccessRequest(
        profile_id=_PROFILE,
        definition_id=definition.definition_id,
        action=AccessAction.SUBMIT,
        frontend=OperationFrontendProjection.CLI,
        periods=frozenset({_PERIOD.to_period()}),
        period_independent=False,
        destination_id=context.destination_id,
    )
    with pytest.raises(ProfileAccessRefusedError) as narrow:
        resolve_modelo_invoice_withholding_capture_access(
            cast(OperationRequest[BaseModel], cast(object, request)),
            replace(context, admitted_request=narrow_request),
        )
    assert narrow.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE
    all_period_request = OperationAccessRequest(
        profile_id=_PROFILE,
        definition_id=definition.definition_id,
        action=AccessAction.SUBMIT,
        frontend=OperationFrontendProjection.CLI,
        periods=frozenset(),
        period_independent=True,
        destination_id=context.destination_id,
    )
    admitted = resolve_modelo_invoice_withholding_capture_access(
        cast(OperationRequest[BaseModel], cast(object, request)),
        replace(context, admitted_request=all_period_request),
    )
    assert admitted.request == all_period_request
    request_schema = next(
        binding.model_type.model_json_schema()
        for binding in registration.schema_bindings
        if binding.identity == registration.contract.request_schema
    )
    assert set(request_schema["properties"]) == {"profile_id", "command", "evidence"}
    representation = repr(request.payload)
    assert "b" * 64 not in representation
    assert "100.00" not in representation
    with pytest.raises(ProfileAccessRefusedError) as refused:
        resolve_modelo_invoice_withholding_capture_access(
            cast(OperationRequest[BaseModel], cast(object, request)),
            replace(context, profile_id=_OTHER_PROFILE),
        )
    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH


def test_request_rejects_modelo_123_and_caller_authored_retencion_rows() -> None:
    with pytest.raises(ValidationError):
        ModeloInvoiceWithholdingCaptureRequest.from_inputs(
            profile_id=_PROFILE,
            command=_command(modelo="123"),
            evidence=_evidence(),
        )


def test_request_typed_operands_round_trip_canonically() -> None:
    payload = _request().payload
    evidence_schema = PublicInvoiceWithholdingEvidence.model_json_schema()
    definitions = evidence_schema["$defs"]
    for name in (
        "WithholdingIncomeKind",
        "WithholdingRecipientTaxStatus",
        "WithholdingRecipientTaxRegime",
        "WithholdingMutationMode",
    ):
        assert definitions[name]["enum"]
    evidence = payload.evidence.model_dump(mode="json")
    evidence["income_kind"] = "unrecognized_kind"
    with pytest.raises(ValidationError):
        PublicInvoiceWithholdingEvidence.model_validate(evidence)
    with pytest.raises(ValidationError):
        ModeloInvoiceWithholdingCaptureRequest.model_validate(
            {
                "profile_id": str(_PROFILE),
                "command": {"modelo": "111", "period": {"filing_year": 2024, "code": "bad"}},
                "evidence": payload.evidence.model_dump(mode="json"),
            }
        )
    assert payload.command.to_domain() == _command()
    assert payload.evidence.to_domain() == _evidence()
    row = RetencionObservation(
        source_kind=BindingSourceKind.PAYABLE_INVOICE,
        source_object_id="invoice-source",
        perceptor_nif="12345678Z",
        perceptor_name="Sensitive name",
        scheme=RetencionScheme("actividades_profesionales"),
        taxable_base=Decimal("100.00"),
        retencion_amount=Decimal("15.00"),
        accrued_on="2024-01-15",
    )
    with pytest.raises(ValueError, match="caller-authored observations"):
        ModeloInvoiceWithholdingCaptureRequest.from_inputs(
            profile_id=_PROFILE,
            command=_command(retenciones=(row,)),
            evidence=_evidence(),
        )


def test_typed_annual_detail_preserves_all_canonical_fields_under_pinned_authority(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    with validating_governed_facts(authority_operation):
        detail = WithholdingObservation(
            source_id="invoice-source",
            perceptor_tax_id="11111111H",
            transaction_date=datetime(2024, 6, 1, tzinfo=UTC).date(),
            clave=RetencionClave.from_registry("G"),
            percibido_dinerario=Decimal("1000"),
            retencion_practicada=Decimal("190"),
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
            base_retenciones=Decimal("0"),
        )
        evidence = _evidence().model_copy(update={"modelo_190_detail": detail})
        public = PublicInvoiceWithholdingEvidence.from_domain(evidence)
        assert public.to_domain() == evidence
        assert public.modelo_190_detail is not None
        assert set(type(public.modelo_190_detail).model_fields) == set(WithholdingObservation.model_fields)


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
        return _OPERAND_REF


def _executor_context(
    events: _Events, operands: _Operands, *, authority_operation: PinnedAuthorityOperation | None = None
) -> OperationExecutorContext:
    return cast(
        OperationExecutorContext,
        SimpleNamespace(
            identity=OperationIdentity(
                operation_id="c" * 64,
                definition_id=MODELO_INVOICE_WITHHOLDING_CAPTURE_OPERATION_DEFINITION_ID,
                subject_ref=profile_operation_subject(str(_PROFILE)),
            ),
            authority_operation=authority_operation,
            cancellation=_Cancellation(),
            events=events,
            operands=operands,
        ),
    )


class _WithholdingService(WithholdingWindowServiceFixture):
    def __init__(self) -> None:
        observations = (
            RetencionObservation(
                source_kind=BindingSourceKind.PAYABLE_INVOICE,
                source_object_id="b" * 64,
                perceptor_nif="11111111H",
                perceptor_name="Synthetic recipient",
                scheme=RetencionScheme("actividades_profesionales"),
                taxable_base=Decimal("100.00"),
                retencion_amount=Decimal("15.00"),
                accrued_on="2024-01-15",
            ),
        )

        super().__init__(baseline=_BASELINE, generation=1, observations=observations, include_audit=False)


def _prepared() -> _PreparedCapture:
    service = _WithholdingService()
    ports = SimpleNamespace(
        profile_id=str(_PROFILE),
        invoice_catalogue_repository=SimpleNamespace(bucket_id=str(_PROFILE)),
        retencion_observation_repository=SimpleNamespace(load_observations=lambda _modelo, _period: ()),
        withholding_observation_service=service,
    )
    capture = SimpleNamespace(command=object(), scope=_SCOPE, catalogue_read_revision_id="b" * 64)
    return _PreparedCapture(
        ports=cast(ModeloInvoiceWithholdingCapturePorts, cast(object, ports)),
        cadence=cast(WithholdingFilerCadence, object()),
        capture=cast(InvoiceWithholdingCapture, cast(object, capture)),
        aggregate_command=_command(),
    )


def _terminal_receipt(
    *,
    effect: OperationEffect,
    refused: bool = False,
    refusal_ref: str = MODELO_INVOICE_WITHHOLDING_CAPTURE_REFUSAL_CODE,
) -> OperationTerminalReceipt:
    identity = OperationIdentity(
        operation_id="c" * 64,
        definition_id=MODELO_INVOICE_WITHHOLDING_CAPTURE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
    )
    if refused:
        return OperationTerminalReceipt(
            identity=identity,
            revision=2,
            condition=OperationTerminalCondition.REFUSED,
            effect=OperationEffect.NONE,
            settled_at=datetime.now(UTC),
            refusal_ref=refusal_ref,
            refusal_detail_ref="d" * 64,
        )
    return OperationTerminalReceipt(
        identity=identity,
        revision=2,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=effect,
        settled_at=datetime.now(UTC),
        result_ref=_OPERAND_REF,
    )


@pytest.mark.parametrize(
    ("replayed", "expected_effect"),
    ((True, OperationEffect.NONE), (False, OperationEffect.UPDATED)),
)
def test_executor_effect_matches_replay_and_publishes_only_safe_result(
    monkeypatch: pytest.MonkeyPatch,
    authority_operation: PinnedAuthorityOperation,
    replayed: bool,
    expected_effect: OperationEffect,
) -> None:
    events = _Events()
    operands = _Operands()
    executor = ModeloInvoiceWithholdingCaptureExecutor(
        cast(ModeloInvoiceWithholdingCapturePortsFactory, cast(object, lambda **_kwargs: None))
    )
    prepared = _prepared()
    service = prepared.ports.withholding_observation_service
    assert isinstance(service, _WithholdingService)
    context = _executor_context(events, operands, authority_operation=authority_operation)
    monkeypatch.setattr(
        "cadrumo.application.modelo.invoice_withholding_capture_execution.require_active_bucket_id",
        lambda: str(_PROFILE),
    )
    monkeypatch.setattr("cadrumo.application.operations.profile_guard.require_active_bucket_id", lambda: str(_PROFILE))
    monkeypatch.setattr(executor, "_prepare", lambda *_args: prepared)

    def aggregate_then_advance(command: PerModeloAggregationCommand, *, operation: PinnedAuthorityOperation):
        result = aggregate_per_modelo(command, operation=operation)
        service.generation = 2
        service.observations = ()
        service.baseline = WithholdingWindowBaseline(scope_token=_SCOPE.token, generation_id="f" * 64)
        return result

    monkeypatch.setattr(
        "cadrumo.application.modelo.invoice_withholding_capture_execution.aggregate_per_modelo",
        aggregate_then_advance,
    )

    class _Producer:
        def __init__(self, *, service: object) -> None:
            self.service = service

        def capture(self, _command: object, *, cadence: object, source_catalogue_revision_id: str):
            del cadence
            assert source_catalogue_revision_id == prepared.capture.catalogue_read_revision_id
            return SimpleNamespace(scope=_SCOPE, mutation=SimpleNamespace(replayed=replayed))

    monkeypatch.setattr(
        "cadrumo.application.modelo.invoice_withholding_capture_execution.WithholdingProducer",
        _Producer,
    )

    result_ref = asyncio.run(executor.execute(_request(), context))

    assert result_ref == _OPERAND_REF
    assert events.effects == [OperationEffect.UNKNOWN, expected_effect]
    report = operands.values[0]
    assert isinstance(report, ModeloInvoiceWithholdingCaptureReport)
    projected = project_modelo_invoice_withholding_capture_result(
        report,
        _terminal_receipt(effect=expected_effect),
    )
    assert isinstance(projected, ModeloInvoiceWithholdingCaptureProjection)
    assert projected.outcome == "captured"
    assert projected.observation_count == 1
    assert projected.withholding_window is not None
    assert projected.withholding_window.generation == 1
    assert projected.withholding_window.baseline.generation_id == _BASELINE.generation_id
    assert service.generation == 2
    assert service.reads == [_SCOPE]
    assert service.audit_reads == [(_SCOPE, _BASELINE.generation_id)]
    assert not {"perceptor_nif", "perceptor_name", "retencion_amount", "entries"} & set(
        projected.model_dump(mode="json")
    )


def test_prewrite_refusal_is_bounded_and_stored_as_secure_result_detail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events = _Events()
    operands = _Operands()
    executor = ModeloInvoiceWithholdingCaptureExecutor(
        cast(ModeloInvoiceWithholdingCapturePortsFactory, cast(object, lambda **_kwargs: None))
    )
    monkeypatch.setattr(
        "cadrumo.application.modelo.invoice_withholding_capture_execution.require_active_bucket_id",
        lambda: str(_PROFILE),
    )
    monkeypatch.setattr("cadrumo.application.operations.profile_guard.require_active_bucket_id", lambda: str(_PROFILE))

    def refuse_before_commit(*_args: object) -> _PreparedCapture:
        raise InvoiceWithholdingEvidenceError("not_a_retenedor_liability")

    monkeypatch.setattr(executor, "_prepare", refuse_before_commit)

    result = asyncio.run(executor.execute(_request(), _executor_context(events, operands)))

    assert isinstance(result, OperationRefusalEvidence)
    assert result.refusal_code == MODELO_INVOICE_WITHHOLDING_CAPTURE_REFUSAL_CODE
    assert events.effects == [OperationEffect.NONE]
    report = operands.values[0]
    assert isinstance(report, ModeloInvoiceWithholdingCaptureReport)
    projection = project_modelo_invoice_withholding_capture_result(
        report,
        _terminal_receipt(effect=OperationEffect.NONE, refused=True),
    )
    assert isinstance(projection, ModeloInvoiceWithholdingCaptureProjection)
    assert projection.outcome == "refused"
    assert isinstance(projection, ModeloInvoiceWithholdingCaptureProjection)
    assert projection.refusal_reason == "not_a_retenedor_liability"
    assert set(projection.model_dump(mode="json")) == {
        "outcome",
        "profile_id",
        "modelo",
        "period",
        "provider",
        "observation_count",
        "source_kinds",
        "result_row_count",
        "withholding_window",
        "refusal_reason",
        "refusal_defects",
    }
    assert projection.refusal_defects is None


def test_invoice_retencion_defects_refuse_naming_every_defect_under_their_own_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every defect travels as a stable token under the defects code, never as a flattened generic reason."""
    events = _Events()
    operands = _Operands()
    executor = ModeloInvoiceWithholdingCaptureExecutor(
        cast(ModeloInvoiceWithholdingCapturePortsFactory, cast(object, lambda **_kwargs: None))
    )
    monkeypatch.setattr(
        "cadrumo.application.modelo.invoice_withholding_capture_execution.require_active_bucket_id",
        lambda: str(_PROFILE),
    )
    monkeypatch.setattr("cadrumo.application.operations.profile_guard.require_active_bucket_id", lambda: str(_PROFILE))
    defects = (
        InvoiceRetencionProjectionDefect.NOT_A_RETENEDOR_LIABILITY,
        InvoiceRetencionProjectionDefect.NO_RETENCION_DECLARED,
    )

    def refuse_with_defects(*_args: object) -> _PreparedCapture:
        raise InvoiceWithholdingDefectsError(defects)

    monkeypatch.setattr(executor, "_prepare", refuse_with_defects)

    result = asyncio.run(executor.execute(_request(), _executor_context(events, operands)))

    assert isinstance(result, OperationRefusalEvidence)
    assert result.refusal_code == MODELO_INVOICE_WITHHOLDING_DEFECTS_REFUSAL_CODE
    assert events.effects == [OperationEffect.NONE]
    report = operands.values[0]
    assert isinstance(report, ModeloInvoiceWithholdingCaptureReport)
    assert not report.local_write_performed
    projection = project_modelo_invoice_withholding_capture_result(
        report,
        _terminal_receipt(
            effect=OperationEffect.NONE, refused=True, refusal_ref=MODELO_INVOICE_WITHHOLDING_DEFECTS_REFUSAL_CODE
        ),
    )
    assert isinstance(projection, ModeloInvoiceWithholdingCaptureProjection)
    assert projection.refusal_defects == defects
    assert projection.refusal_code == MODELO_INVOICE_WITHHOLDING_DEFECTS_REFUSAL_CODE
    assert projection.model_dump(mode="json")["refusal_defects"] == [defect.value for defect in defects]

    with pytest.raises(ValueError, match="contradicts its terminal receipt"):
        project_modelo_invoice_withholding_capture_result(
            report,
            _terminal_receipt(effect=OperationEffect.NONE, refused=True),
        )


def test_refused_projection_refuses_repeated_or_captured_defects() -> None:
    defect = InvoiceRetencionProjectionDefect.NO_RETENCION_DECLARED
    with pytest.raises(ValidationError, match="repeats an invoice withholding defect"):
        ModeloInvoiceWithholdingCaptureProjection(
            outcome="refused",
            profile_id=_PROFILE,
            modelo="111",
            period=_PERIOD,
            refusal_reason="invoice_withholding_defects",
            refusal_defects=(defect, defect),
        )
    with pytest.raises(ValidationError):
        ModeloInvoiceWithholdingCaptureProjection(
            outcome="refused",
            profile_id=_PROFILE,
            modelo="111",
            period=_PERIOD,
            refusal_reason="invoice_withholding_defects",
            refusal_defects=(),
        )


@pytest.mark.parametrize(
    "refusal_code", ("persistence_failure", "source_revision_changed", "source_revision_unavailable")
)
def test_invoice_source_conflict_refuses_and_ambiguous_mutation_keeps_effect_unknown(
    monkeypatch: pytest.MonkeyPatch,
    refusal_code: str,
) -> None:
    events = _Events()
    operands = _Operands()
    executor = ModeloInvoiceWithholdingCaptureExecutor(
        cast(ModeloInvoiceWithholdingCapturePortsFactory, cast(object, lambda **_kwargs: None))
    )
    monkeypatch.setattr(
        "cadrumo.application.modelo.invoice_withholding_capture_execution.require_active_bucket_id",
        lambda: str(_PROFILE),
    )
    monkeypatch.setattr("cadrumo.application.operations.profile_guard.require_active_bucket_id", lambda: str(_PROFILE))
    prepared = _prepared()
    monkeypatch.setattr(executor, "_prepare", lambda *_args: prepared)

    class _Producer:
        def __init__(self, *, service: object) -> None:
            self.service = service

        def capture(self, _command: object, *, cadence: object, source_catalogue_revision_id: str):
            del cadence
            assert source_catalogue_revision_id == prepared.capture.catalogue_read_revision_id
            raise WithholdingObservationMutationError(refusal_code)

    monkeypatch.setattr(
        "cadrumo.application.modelo.invoice_withholding_capture_execution.WithholdingProducer",
        _Producer,
    )

    if refusal_code == "source_revision_changed":
        result = asyncio.run(executor.execute(_request(), _executor_context(events, operands)))
        assert isinstance(result, OperationRefusalEvidence)
        assert result.refusal_code == MODELO_INVOICE_WITHHOLDING_CAPTURE_REFUSAL_CODE
        assert events.effects == [OperationEffect.UNKNOWN, OperationEffect.NONE]
        report = operands.values[0]
        assert isinstance(report, ModeloInvoiceWithholdingCaptureReport)
        projection = project_modelo_invoice_withholding_capture_result(
            report,
            _terminal_receipt(effect=OperationEffect.NONE, refused=True),
        )
        assert isinstance(projection, ModeloInvoiceWithholdingCaptureProjection)
        assert projection.refusal_reason == "source_revision_changed"
        assert isinstance(prepared.ports.withholding_observation_service, _WithholdingService)
        assert prepared.ports.withholding_observation_service.reads == []
    else:
        with pytest.raises(WithholdingObservationMutationError):
            asyncio.run(executor.execute(_request(), _executor_context(events, operands)))

        assert events.effects == [OperationEffect.UNKNOWN]
        assert operands.values == []
