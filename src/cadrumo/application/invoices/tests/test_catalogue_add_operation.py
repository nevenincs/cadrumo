"""Registered invoice creation keeps its private input and canonical write contract."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, date, datetime
from types import SimpleNamespace
from typing import Never, cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from ....core.operations import (
    OperationEffect,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.authority_lease_support import private_authority_lease
from ....domain.iva.classification import InvoiceKind
from ...operations import profile_guard
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from ...operations.owner import OperationExecutorContext
from ...operations.public_scalar import PublicDecimal
from ...operations.refusal_evidence import OperationRefusalEvidence
from ...operations.registry import OperationFrontendProjection, OperationRegistry
from ...user_profile.access_contracts import AccessAction, AccessDenialCode, Availability
from ...user_profile.access_errors import ProfileAccessRefusedError
from .. import catalogue_add_operation as add_operation
from ..catalogue_add_contracts import (
    INVOICE_ADD_OPERATION_DEFINITION_ID,
    INVOICE_ADD_VALIDATION_REFUSAL_CODE,
    InvoiceAddExecutionResult,
    InvoiceAddLine,
    InvoiceAddRequest,
    project_invoice_add_result,
)
from ..catalogue_add_operation import (
    InvoiceAddExecutor,
    build_invoice_add_definition,
    build_invoice_add_registration,
)
from ..catalogue_creation_ports import CatalogueCreationPorts
from ..tests._catalogue_creation_fakes import in_memory_catalogue_creation_ports

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")


def _request(**overrides: object) -> InvoiceAddRequest:
    values: dict[str, object] = {
        "profile_id": _PROFILE,
        "kind": InvoiceKind.RECEIVED,
        "counterparty_name": "Synthetic supplier",
        "counterparty_tax_id": "A58818501",
        "counterparty_country": "ES",
        "invoice_number": "ADD-2026-001",
        "issued_at": date(2026, 4, 15),
        "taxable_base": PublicDecimal(decimal="100.00"),
        "iva_rate": PublicDecimal(decimal="21"),
        "currency": "EUR",
    }
    values.update(overrides)
    return InvoiceAddRequest.model_validate(values)


def test_request_json_roundtrip_keeps_decimal_meaning_and_refuses_incomplete_line_modes() -> None:
    request = _request(retention_amount=PublicDecimal(decimal="0.00"))

    assert InvoiceAddRequest.model_validate_json(request.model_dump_json()) == request
    assert request.retention_amount == PublicDecimal(decimal="0.00")

    with pytest.raises(ValidationError):
        _request(taxable_base=None, iva_rate=None)

    line = InvoiceAddLine(
        description="Service",
        quantity=PublicDecimal(decimal="1"),
        unit_price=PublicDecimal(decimal="100.00"),
        subtotal=PublicDecimal(decimal="100.00"),
        iva_rate="RATE_21",
        iva_amount=PublicDecimal(decimal="21.00"),
    )
    with pytest.raises(ValidationError):
        _request(lines=(line,))


@pytest.mark.parametrize(
    "overrides",
    (
        pytest.param(
            {
                "taxable_base": None,
                "iva_rate": None,
                "lines": (
                    InvoiceAddLine(
                        description="Service",
                        quantity=PublicDecimal(decimal="1"),
                        unit_price=PublicDecimal(decimal="100.00"),
                        subtotal=PublicDecimal(decimal="100.00"),
                        iva_rate="UNDECLARED_RATE",
                        iva_amount=PublicDecimal(decimal="21.00"),
                    ),
                ),
            },
            id="line-rate",
        ),
        pytest.param(
            {
                "taxable_base": None,
                "iva_rate": None,
                "lines": (
                    InvoiceAddLine(
                        description="Service",
                        quantity=PublicDecimal(decimal="1"),
                        unit_price=PublicDecimal(decimal="100.00"),
                        subtotal=PublicDecimal(decimal="100.00"),
                        iva_rate="RATE_21",
                        iva_amount=PublicDecimal(decimal="21.00"),
                        oss_rate_kind="UNDECLARED_KIND",
                    ),
                ),
            },
            id="line-oss-rate-kind",
        ),
        pytest.param({"iva_category": "UNDECLARED_CATEGORY"}, id="iva-category"),
        pytest.param({"invoice_class": "UNDECLARED_CLASS"}, id="invoice-class"),
    ),
)
def test_undeclared_registry_tokens_are_validation_refusals(overrides: dict[str, object], monkeypatch) -> None:
    monkeypatch.setattr(profile_guard, "require_active_bucket_id", lambda: str(_PROFILE))
    monkeypatch.setattr(add_operation, "require_active_bucket_id", lambda: str(_PROFILE))
    ports = in_memory_catalogue_creation_ports()

    def factory(*, bucket_id: str) -> CatalogueCreationPorts:
        assert bucket_id == str(_PROFILE)
        return ports

    with private_authority_lease() as authority_operation:
        context = _Context(authority_operation)
        request = OperationRequest[InvoiceAddRequest](
            definition_id=INVOICE_ADD_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(_PROFILE)),
            payload=_request(**overrides),
        )
        result = asyncio.run(InvoiceAddExecutor(factory).execute(request, context))

    assert isinstance(result, OperationRefusalEvidence)
    assert result.refusal_code == INVOICE_ADD_VALIDATION_REFUSAL_CODE
    assert context.events.effects == []
    assert context.operands.value is not None
    assert context.operands.value.result.outcome == "validation_error"
    assert context.operands.value.result.validation_code == "invalid_invoice"
    assert len(ports.invoice_repository.load()) == 0


def test_executor_refuses_foreign_active_profile_before_phase_or_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    request = OperationRequest[InvoiceAddRequest](
        definition_id=INVOICE_ADD_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=_request(),
    )
    events = _Events()
    context = cast(
        OperationExecutorContext,
        SimpleNamespace(
            identity=OperationIdentity(
                operation_id="a" * 64,
                definition_id=request.definition_id,
                subject_ref=request.subject_ref,
            ),
            events=events,
        ),
    )
    monkeypatch.setattr(profile_guard, "require_active_bucket_id", lambda: str(uuid4()))
    factory_calls: list[str] = []

    def unused_factory(*, bucket_id: str) -> CatalogueCreationPorts:
        factory_calls.append(bucket_id)
        pytest.fail("foreign active profile reached invoice creation ports")

    with pytest.raises(ProfileAccessRefusedError) as refused:
        asyncio.run(InvoiceAddExecutor(unused_factory).execute(request, context))

    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH
    assert events.phases == events.effects == []
    assert factory_calls == []


def test_registration_requires_profile_scoped_commit_and_secure_request_storage() -> None:
    def unused_factory(*, bucket_id: str) -> CatalogueCreationPorts:
        raise AssertionError(f"registration composed profile ports for {bucket_id}")

    definition = build_invoice_add_definition(unused_factory)
    registration = build_invoice_add_registration(definition)
    registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
    request = OperationRequest[InvoiceAddRequest](
        definition_id=INVOICE_ADD_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=_request(),
    )
    context = OperationAccessContext(
        profile_id=_PROFILE,
        destination_id=uuid4(),
        action=AccessAction.SUBMIT,
        frontend=OperationFrontendProjection.CLI,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
    )

    access_request = OperationRequest[BaseModel](
        definition_id=request.definition_id, subject_ref=request.subject_ref, payload=request.payload
    )
    access = resolve_operation_access(registry=registry, request=access_request, context=context)

    assert access.policy.actions >= {AccessAction.SUBMIT, AccessAction.COMMIT}
    assert definition.capabilities.request_storage.value == "secure_reference"
    assert definition.capabilities.sensitive_input.value == "secure_reference"
    assert definition.permitted_frontends == frozenset(
        {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI, OperationFrontendProjection.MCP}
    )


class _Events:
    def __init__(self) -> None:
        self.effects: list[OperationEffect] = []
        self.phases: list[str] = []

    async def phase(self, phase_code: str) -> None:
        self.phases.append(phase_code)

    async def effect(self, effect: OperationEffect) -> None:
        self.effects.append(effect)

    async def progress(self, **_kwargs: object) -> None:
        raise AssertionError("invoice creation does not publish progress")

    async def log(self, **_kwargs: object) -> None:
        raise AssertionError("invoice creation does not publish logs")

    async def notice(self, notice_code: str, *, display_code: str | None = None) -> None:
        raise AssertionError("invoice creation does not publish notices")

    async def diagnostic(self, diagnostic_ref: str) -> None:
        raise AssertionError("invoice creation does not publish diagnostics")


class _Cancellation:
    def __init__(self) -> None:
        self.inside_irreversible_section = False

    @property
    def cancellation_requested(self) -> bool:
        return False

    async def acknowledge_cancellation(self) -> None:
        raise AssertionError("these executions are never cancelled")

    @asynccontextmanager
    async def irreversible_section(self):
        self.inside_irreversible_section = True
        try:
            yield
        finally:
            self.inside_irreversible_section = False


class _Operands:
    def __init__(self, cancellation: _Cancellation, events: _Events) -> None:
        self._cancellation = cancellation
        self._events = events
        self.value: InvoiceAddExecutionResult | None = None

    async def put(self, operand: BaseModel, *, written_at: datetime) -> str:
        assert isinstance(operand, InvoiceAddExecutionResult)
        assert self._cancellation.inside_irreversible_section
        assert not self._events.effects or self._events.effects[-1] in {
            OperationEffect.UPDATED,
            OperationEffect.NONE,
        }
        self.value = operand
        return "d" * 64

    async def resolve[OperandT: BaseModel](self, reference: str, operand_type: type[OperandT]) -> OperandT:
        raise AssertionError("invoice creation does not resolve prior operands")


class _Context:
    def __init__(self, authority_operation: PinnedAuthorityOperation) -> None:
        self.identity = OperationIdentity(
            operation_id="c" * 64,
            definition_id=INVOICE_ADD_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(_PROFILE)),
        )
        self.authority_operation = authority_operation
        self.events = _Events()
        self.cancellation = _Cancellation()
        self.operands = _Operands(self.cancellation, self.events)

    @property
    def revision(self) -> int:
        return 1

    @property
    def deadlines(self) -> Never:
        raise AssertionError("invoice creation does not consume deadlines")

    @property
    def ephemeral_secret(self) -> Never:
        raise AssertionError("invoice creation does not consume secrets")

    @property
    def financial_operand(self) -> Never:
        raise AssertionError("invoice creation does not consume financial submissions")

    @property
    def cleanup(self) -> Never:
        raise AssertionError("invoice creation does not acquire resources")

    @property
    def interactions(self) -> Never:
        raise AssertionError("invoice creation does not publish interactions")


def test_executor_uses_canonical_builder_and_writer_with_commit_fenced_publication(monkeypatch) -> None:
    monkeypatch.setattr(profile_guard, "require_active_bucket_id", lambda: str(_PROFILE))
    monkeypatch.setattr(add_operation, "require_active_bucket_id", lambda: str(_PROFILE))
    ports = in_memory_catalogue_creation_ports()
    events = _Events()
    cancellation = _Cancellation()
    original_commit = ports.audit_commit

    class _ObservedCommit:
        def mutate_with_event(self, mutation, event, *, attempts: int = 4):
            assert cancellation.inside_irreversible_section
            assert events.effects == [OperationEffect.UNKNOWN]
            return original_commit.mutate_with_event(mutation, event, attempts=attempts)

    ports = replace(ports, audit_commit=_ObservedCommit())
    factory_calls: list[str] = []

    def factory(*, bucket_id: str) -> CatalogueCreationPorts:
        factory_calls.append(bucket_id)
        return ports

    with private_authority_lease() as authority_operation:
        context = _Context(authority_operation)
        context.events = events
        context.cancellation = cancellation
        context.operands = _Operands(cancellation, events)
        request = OperationRequest[InvoiceAddRequest](
            definition_id=INVOICE_ADD_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(_PROFILE)),
            payload=_request(),
        )
        result_ref = asyncio.run(InvoiceAddExecutor(factory).execute(request, context))

    execution_result = context.operands.value
    assert result_ref == "d" * 64
    assert factory_calls == [str(_PROFILE)]
    assert context.events.phases == [INVOICE_ADD_OPERATION_DEFINITION_ID]
    assert context.events.effects == [OperationEffect.UNKNOWN, OperationEffect.UPDATED]
    assert execution_result is not None
    result = execution_result.result
    assert result.outcome == "created"
    assert result.profile_id == _PROFILE
    assert result.invoice is not None
    assert result.invoice.bucket_id == str(_PROFILE)
    assert result.invoice.invoice_number == "ADD-2026-001"
    assert len(result.bucket_event_ids) == 1
    assert result.euro_value_pending is False
    assert result.simplificada_tax_id_advisory_required is False
    assert len(ports.invoice_repository.load()) == 1


def test_duplicate_is_a_typed_refusal_with_secure_detail_and_no_second_write(monkeypatch) -> None:
    monkeypatch.setattr(profile_guard, "require_active_bucket_id", lambda: str(_PROFILE))
    monkeypatch.setattr(add_operation, "require_active_bucket_id", lambda: str(_PROFILE))
    ports = in_memory_catalogue_creation_ports()

    def factory(*, bucket_id: str) -> CatalogueCreationPorts:
        assert bucket_id == str(_PROFILE)
        return ports

    with private_authority_lease() as authority_operation:
        executor = InvoiceAddExecutor(factory)
        successful_context = _Context(authority_operation)
        success_ref = asyncio.run(
            executor.execute(
                OperationRequest[InvoiceAddRequest](
                    definition_id=INVOICE_ADD_OPERATION_DEFINITION_ID,
                    subject_ref=profile_operation_subject(str(_PROFILE)),
                    payload=_request(),
                ),
                successful_context,
            )
        )

        duplicate_context = _Context(authority_operation)
        duplicate_refusal = asyncio.run(
            executor.execute(
                OperationRequest[InvoiceAddRequest](
                    definition_id=INVOICE_ADD_OPERATION_DEFINITION_ID,
                    subject_ref=profile_operation_subject(str(_PROFILE)),
                    payload=_request(),
                ),
                duplicate_context,
            )
        )

    assert success_ref == "d" * 64
    assert isinstance(duplicate_refusal, OperationRefusalEvidence)
    assert duplicate_refusal.refusal_code == INVOICE_ADD_VALIDATION_REFUSAL_CODE
    assert duplicate_refusal.detail_ref == "d" * 64
    assert duplicate_context.events.effects == [OperationEffect.UNKNOWN, OperationEffect.NONE]
    assert duplicate_context.operands.value is not None
    result = duplicate_context.operands.value.result
    assert result.outcome == "validation_error"
    assert result.profile_id == _PROFILE
    assert result.invoice is None
    assert result.invoice_id is not None
    assert result.validation_code == "duplicate_invoice"
    assert len(ports.invoice_repository.load()) == 1

    receipt = OperationTerminalReceipt(
        identity=duplicate_context.identity,
        revision=1,
        condition=OperationTerminalCondition.REFUSED,
        effect=OperationEffect.NONE,
        settled_at=datetime.now(UTC),
        refusal_ref=INVOICE_ADD_VALIDATION_REFUSAL_CODE,
        refusal_detail_ref="d" * 64,
    )
    assert project_invoice_add_result(duplicate_context.operands.value, receipt) == result


def test_invalid_invoice_is_a_typed_refusal_with_no_effect_or_write(monkeypatch) -> None:
    monkeypatch.setattr(profile_guard, "require_active_bucket_id", lambda: str(_PROFILE))
    monkeypatch.setattr(add_operation, "require_active_bucket_id", lambda: str(_PROFILE))
    ports = in_memory_catalogue_creation_ports()

    def factory(*, bucket_id: str) -> CatalogueCreationPorts:
        assert bucket_id == str(_PROFILE)
        return ports

    with private_authority_lease() as authority_operation:
        context = _Context(authority_operation)
        refusal = asyncio.run(
            InvoiceAddExecutor(factory).execute(
                OperationRequest[InvoiceAddRequest](
                    definition_id=INVOICE_ADD_OPERATION_DEFINITION_ID,
                    subject_ref=profile_operation_subject(str(_PROFILE)),
                    payload=_request(retention_rate=PublicDecimal(decimal="0.15")),
                ),
                context,
            )
        )

    assert isinstance(refusal, OperationRefusalEvidence)
    assert refusal.refusal_code == INVOICE_ADD_VALIDATION_REFUSAL_CODE
    assert context.events.effects == []
    assert context.operands.value is not None
    result = context.operands.value.result
    assert result.outcome == "validation_error"
    assert result.profile_id == _PROFILE
    assert result.invoice is None
    assert result.invoice_id is None
    assert result.validation_code == "invalid_invoice"
    assert len(ports.invoice_repository.load()) == 0

    receipt = OperationTerminalReceipt(
        identity=context.identity,
        revision=1,
        condition=OperationTerminalCondition.REFUSED,
        effect=OperationEffect.NONE,
        settled_at=datetime.now(UTC),
        refusal_ref=INVOICE_ADD_VALIDATION_REFUSAL_CODE,
        refusal_detail_ref=refusal.detail_ref,
    )
    assert project_invoice_add_result(context.operands.value, receipt) == result


def _execute_add(
    payload: InvoiceAddRequest, monkeypatch: pytest.MonkeyPatch
) -> tuple[_Context, CatalogueCreationPorts]:
    monkeypatch.setattr(profile_guard, "require_active_bucket_id", lambda: str(_PROFILE))
    monkeypatch.setattr(add_operation, "require_active_bucket_id", lambda: str(_PROFILE))
    ports = in_memory_catalogue_creation_ports()

    def factory(*, bucket_id: str) -> CatalogueCreationPorts:
        assert bucket_id == str(_PROFILE)
        return ports

    with private_authority_lease() as authority_operation:
        context = _Context(authority_operation)
        asyncio.run(
            InvoiceAddExecutor(factory).execute(
                OperationRequest[InvoiceAddRequest](
                    definition_id=INVOICE_ADD_OPERATION_DEFINITION_ID,
                    subject_ref=profile_operation_subject(str(_PROFILE)),
                    payload=payload,
                ),
                context,
            )
        )
    return context, ports


def test_an_issued_business_premises_lease_reaches_the_stored_invoice(monkeypatch: pytest.MonkeyPatch) -> None:
    """The one add operation every frontend submits carries the lessor's lease facts into the aggregate."""
    context, ports = _execute_add(
        _request(
            kind=InvoiceKind.ISSUED,
            arrendamiento_local_negocio=True,
            situacion_inmueble="1",
            referencia_catastral="9872023VH5797S0001WX",
        ),
        monkeypatch,
    )

    assert context.operands.value is not None
    assert context.operands.value.result.outcome == "created"
    (stored,) = ports.invoice_repository.load().values()
    assert stored.arrendamiento_local_negocio is True
    assert stored.situacion_inmueble == "1"
    assert stored.referencia_catastral == "9872023VH5797S0001WX"


def test_a_lease_on_a_received_invoice_is_an_invalid_invoice_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    context, ports = _execute_add(
        _request(kind=InvoiceKind.RECEIVED, arrendamiento_local_negocio=True, situacion_inmueble="3"),
        monkeypatch,
    )

    assert context.operands.value is not None
    assert context.operands.value.result.validation_code == "invalid_invoice"
    assert len(ports.invoice_repository.load()) == 0


def test_the_request_refuses_a_situacion_outside_the_record_design() -> None:
    with pytest.raises(ValidationError):
        _request(kind=InvoiceKind.ISSUED, arrendamiento_local_negocio=True, situacion_inmueble="5")
