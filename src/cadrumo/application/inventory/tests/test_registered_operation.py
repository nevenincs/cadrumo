"""Inventory registered operations redact evidence and settle refusals truthfully."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import cast
from uuid import UUID

import pytest
from pydantic import BaseModel, ValidationError

from ....core.config import override_settings
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....domain.contribuyente.inventory.records import (
    InventoryAcquisitionCompleteness,
    InventoryAcquisitionCost,
    InventoryAcquisitionEvidence,
    InventoryAcquisitionEvidenceKind,
    InventoryLedger,
    MovementRecord,
    ValuationMethod,
)
from ....domain.filing_evidence import FilingEvidenceReference
from ...operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from ...operations.owner import OperationExecutorContext
from ...operations.public_scalar import PublicDecimal
from ...operations.refusal_evidence import OperationRefusalEvidence
from ...user_profile.access_contracts import AccessDenialCode
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..errors import InventoryServiceInputError
from ..ports import InventoryServicePorts
from ..registered_operation import (
    INVENTORY_CREATE_OPERATION_DEFINITION_ID,
    INVENTORY_VALIDATION_REFUSAL_CODE,
    InventoryAcquisitionCostRequest,
    InventoryClosingAuthorityRecordInput,
    InventoryCreateRequest,
    InventoryOperationExecutionResult,
    InventoryOperationExecutor,
    InventoryOperationRefusalDetail,
    build_inventory_closing_authority_record_definition,
    build_inventory_closing_authority_record_registration,
    build_inventory_create_definition,
    build_inventory_create_registration,
    build_inventory_list_definition,
    build_inventory_list_registration,
    build_inventory_movement_add_definition,
    build_inventory_movement_add_registration,
    build_inventory_valuation_preview_definition,
    build_inventory_valuation_preview_registration,
    project_inventory_create_result,
)
from ..service import InventoryLedgerResult
from .registered_operation_conformance_support import build_inventory_conformance_closing_authority_record

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000bb")


def _ledger_with_private_evidence() -> InventoryLedger:
    evidence = (
        InventoryAcquisitionEvidence(
            reference=FilingEvidenceReference(reference="invoice-private-reference"),
            evidence_kind=InventoryAcquisitionEvidenceKind.PURCHASE_INVOICE,
            content_digest="a" * 64,
        ),
        InventoryAcquisitionEvidence(
            reference=FilingEvidenceReference(reference="cost-private-reference"),
            evidence_kind=InventoryAcquisitionEvidenceKind.ATTRIBUTABLE_COST_REVIEW,
            content_digest="b" * 64,
        ),
        InventoryAcquisitionEvidence(
            reference=FilingEvidenceReference(reference="iva-private-reference"),
            evidence_kind=InventoryAcquisitionEvidenceKind.IVA_RECOVERABILITY_REVIEW,
            content_digest="c" * 64,
        ),
    )
    acquisition = InventoryAcquisitionCost(
        consideration_excluding_iva=Decimal("55.00"),
        consideration_iva_amount=Decimal("11.55"),
        consideration_deductible_iva_ratio=Decimal("1.00"),
        attributable_cost_components=(),
        evidence=evidence,
        completeness=InventoryAcquisitionCompleteness(
            consideration_evidence=FilingEvidenceReference(reference="invoice-private-reference"),
            attributable_cost_review_evidence=FilingEvidenceReference(reference="cost-private-reference"),
            iva_recoverability_review_evidence=FilingEvidenceReference(reference="iva-private-reference"),
        ),
        directly_attributable_cost_total=Decimal("0.00"),
        nonrecoverable_iva_included=Decimal("0.00"),
        recoverable_iva_excluded=Decimal("11.55"),
        total_acquisition_cost=Decimal("55.00"),
    )
    movement = MovementRecord.from_purchase_acquisition(
        movement_id="purchase-1",
        movement_date=date(2026, 3, 15),
        sku="widget",
        quantity=Decimal("5"),
        acquisition_cost=acquisition,
    )
    return InventoryLedger(
        actividad_id="act-1",
        year=2026,
        valuation_method=ValuationMethod.FIFO,
        opening_stock=Decimal("100.00"),
        closing_authority_record=None,
        period_movements=(movement,),
    )


def test_acquisition_cost_request_round_trips_the_existing_canonical_record() -> None:
    movement = _ledger_with_private_evidence().period_movements[0]
    acquisition = movement.acquisition_cost

    assert acquisition is not None
    assert InventoryAcquisitionCostRequest.from_domain(acquisition).to_domain() == acquisition


def test_closing_authority_request_round_trips_the_existing_canonical_record() -> None:
    request = build_inventory_conformance_closing_authority_record("inventory-closing-seed")

    assert InventoryClosingAuthorityRecordInput.from_domain(request.to_domain()) == request


def _receipt(
    *,
    condition: OperationTerminalCondition,
    effect: OperationEffect,
    result_ref: str | None = None,
    refusal_ref: str | None = None,
    refusal_detail_ref: str | None = None,
) -> OperationTerminalReceipt:
    return OperationTerminalReceipt(
        identity=OperationIdentity(
            operation_id="c" * 64,
            definition_id=INVENTORY_CREATE_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(_PROFILE)),
        ),
        revision=1,
        condition=condition,
        effect=effect,
        settled_at=datetime.now(UTC),
        result_ref=result_ref,
        refusal_ref=refusal_ref,
        refusal_detail_ref=refusal_detail_ref,
    )


def test_create_projection_redacts_purchase_evidence_and_preserves_full_public_facts() -> None:
    ledger = _ledger_with_private_evidence()
    result = InventoryOperationExecutionResult(
        operation_id="create",
        outcome="success",
        profile_id=_PROFILE,
        ledger_result=InventoryLedgerResult(ledger=ledger, bucket_event_ids=("evt-1",)),
    )

    projection = project_inventory_create_result(
        result,
        _receipt(condition=OperationTerminalCondition.SUCCEEDED, effect=OperationEffect.UPDATED, result_ref="d" * 64),
    )

    assert projection.outcome == "created"
    assert projection.ledger is not None
    assert projection.ledger.period_movements[0].acquisition_cost is not None
    assert projection.ledger.period_movements[0].acquisition_cost.evidence_count == 3
    assert projection.ledger.period_movements[0].acquisition_cost.total_acquisition_cost == PublicDecimal(
        decimal="55.00",
    )
    rendered = projection.model_dump_json()
    for private_value in (
        "invoice-private-reference",
        "cost-private-reference",
        "iva-private-reference",
        "a" * 64,
        "b" * 64,
        "c" * 64,
    ):
        assert private_value not in rendered


def test_create_projection_accepts_only_receipt_correlated_typed_refusal() -> None:
    refusal = InventoryOperationRefusalDetail(
        code=INVENTORY_VALIDATION_REFUSAL_CODE,
        reason="inventory_validation",
        actividad_id="act-1",
        year=2026,
    )
    private_result = InventoryOperationExecutionResult(
        operation_id="create",
        outcome="refused",
        profile_id=_PROFILE,
        refusal=refusal,
    )

    projection = project_inventory_create_result(
        private_result,
        _receipt(
            condition=OperationTerminalCondition.REFUSED,
            effect=OperationEffect.NONE,
            refusal_ref=refusal.code,
            refusal_detail_ref="e" * 64,
        ),
    )

    assert projection.outcome == "refused"
    assert projection.refusal is not None
    assert projection.refusal.reason == "inventory_validation"
    with pytest.raises(ValueError, match="contradicts its terminal receipt"):
        project_inventory_create_result(
            private_result,
            _receipt(
                condition=OperationTerminalCondition.REFUSED,
                effect=OperationEffect.UPDATED,
                refusal_ref=refusal.code,
                refusal_detail_ref="e" * 64,
            ),
        )


def test_inventory_registry_binds_all_five_closed_secure_request_and_result_schemas() -> None:
    def ports_factory(*, bucket_id: str):
        raise AssertionError(f"ports should be bound only inside the profile worker: {bucket_id}")

    definitions = (
        build_inventory_list_definition(ports_factory),
        build_inventory_create_definition(ports_factory),
        build_inventory_movement_add_definition(ports_factory),
        build_inventory_valuation_preview_definition(ports_factory),
        build_inventory_closing_authority_record_definition(ports_factory),
    )
    registrations = (
        build_inventory_list_registration(definitions[0]),
        build_inventory_create_registration(definitions[1]),
        build_inventory_movement_add_registration(definitions[2]),
        build_inventory_valuation_preview_registration(definitions[3]),
        build_inventory_closing_authority_record_registration(definitions[4]),
    )

    assert tuple(item.definition_id for item in definitions) == (
        "ledger.inventory.list",
        "ledger.inventory.create",
        "ledger.inventory.movement.add",
        "ledger.inventory.valuation.preview",
        "ledger.inventory.closing-authority.record",
    )
    assert all(item.capabilities.request_storage.value == "secure_reference" for item in definitions)
    assert all(item.capabilities.sensitive_input.value == "secure_reference" for item in definitions)
    assert all(item.result_projector is not None for item in registrations)


class _Events:
    def __init__(self) -> None:
        self.effects: list[OperationEffect] = []
        self.phases: list[str] = []

    async def phase(self, phase: str) -> None:
        self.phases.append(phase)

    async def effect(self, effect: OperationEffect) -> None:
        self.effects.append(effect)


class _Cancellation:
    def __init__(self) -> None:
        self.inside = False

    @asynccontextmanager
    async def irreversible_section(self):
        self.inside = True
        try:
            yield
        finally:
            self.inside = False


class _Operands:
    def __init__(self, cancellation: _Cancellation) -> None:
        self.cancellation = cancellation
        self.value: BaseModel | None = None

    async def put(self, value: BaseModel, *, written_at):
        del written_at
        assert self.cancellation.inside
        self.value = value
        return "d" * 64


class _Context:
    def __init__(self) -> None:
        self.identity = OperationIdentity(
            operation_id="c" * 64,
            definition_id=INVENTORY_CREATE_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(_PROFILE)),
        )
        self.events = _Events()
        self.cancellation = _Cancellation()
        self.operands = _Operands(self.cancellation)


@pytest.mark.parametrize(
    ("mismatch", "request_definition_id"),
    [
        ("request_subject", INVENTORY_CREATE_OPERATION_DEFINITION_ID),
        ("context_definition", INVENTORY_CREATE_OPERATION_DEFINITION_ID),
        ("context_subject", INVENTORY_CREATE_OPERATION_DEFINITION_ID),
        ("active_profile", INVENTORY_CREATE_OPERATION_DEFINITION_ID),
        ("expected_definition", "ledger.inventory.other"),
    ],
)
def test_profile_mismatch_refuses_before_phase_or_service_factory(
    mismatch: str,
    request_definition_id: str,
) -> None:
    request_subject = (
        profile_operation_subject(str(_OTHER_PROFILE))
        if mismatch == "request_subject"
        else profile_operation_subject(str(_PROFILE))
    )
    request = OperationRequest[BaseModel](
        definition_id=request_definition_id,
        subject_ref=request_subject,
        payload=InventoryCreateRequest(
            profile_id=_PROFILE,
            actividad_id="act-1",
            year=2026,
            valuation_method="fifo",
        ),
    )
    context = _Context()
    if mismatch == "context_definition":
        context.identity = OperationIdentity(
            operation_id="c" * 64,
            definition_id="ledger.inventory.other",
            subject_ref=profile_operation_subject(str(_PROFILE)),
        )
    elif mismatch == "expected_definition":
        context.identity = OperationIdentity(
            operation_id="c" * 64,
            definition_id=request_definition_id,
            subject_ref=profile_operation_subject(str(_PROFILE)),
        )
    elif mismatch == "context_subject":
        context.identity = OperationIdentity(
            operation_id="c" * 64,
            definition_id=INVENTORY_CREATE_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(_OTHER_PROFILE)),
        )

    factory_bucket_ids: list[str] = []

    def unused_factory(*, bucket_id: str) -> InventoryServicePorts:
        factory_bucket_ids.append(bucket_id)
        raise AssertionError("profile mismatch must be refused before service construction")

    executor = InventoryOperationExecutor(
        unused_factory,
        definition_id=INVENTORY_CREATE_OPERATION_DEFINITION_ID,
    )
    active_profile = (
        None
        if mismatch == "expected_definition"
        else str(_OTHER_PROFILE)
        if mismatch == "active_profile"
        else str(_PROFILE)
    )

    with override_settings(cadrumo_active_profile=active_profile), pytest.raises(ProfileAccessRefusedError) as refused:
        asyncio.run(executor.execute(request, cast(OperationExecutorContext, context)))

    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH
    assert context.events.phases == []
    assert context.events.effects == []
    assert factory_bucket_ids == []


def test_unclassified_validation_error_keeps_mutation_effect_unknown() -> None:
    with pytest.raises(ValidationError) as captured:
        InventoryCreateRequest(
            profile_id=_PROFILE,
            actividad_id="act-1",
            year="not-a-year",
            valuation_method="fifo",
        )
    error = captured.value

    def work_after_possible_write() -> None:
        raise error

    context = _Context()

    def unused_factory(*, bucket_id: str) -> InventoryServicePorts:
        raise AssertionError(f"the fake mutation does not resolve inventory ports: {bucket_id}")

    executor = InventoryOperationExecutor(unused_factory, definition_id="ledger.inventory.create")
    request = InventoryCreateRequest(
        profile_id=_PROFILE,
        actividad_id="act-1",
        year=2026,
        valuation_method="fifo",
    )

    with pytest.raises(ValidationError):
        asyncio.run(
            executor._mutate(
                cast(OperationExecutorContext, context),
                operation_id="create",
                profile_id=_PROFILE,
                request=request,
                work=work_after_possible_write,
            )
        )

    assert context.events.effects == [OperationEffect.UNKNOWN]
    assert context.operands.value is None


def test_only_known_service_input_validation_settles_as_none_effect_refusal() -> None:
    context = _Context()

    def unused_factory(*, bucket_id: str) -> InventoryServicePorts:
        raise AssertionError(f"the fake mutation does not resolve inventory ports: {bucket_id}")

    executor = InventoryOperationExecutor(unused_factory, definition_id="ledger.inventory.create")
    request = InventoryCreateRequest(
        profile_id=_PROFILE,
        actividad_id="act-1",
        year=2026,
        valuation_method="fifo",
    )

    result = asyncio.run(
        executor._mutate(
            cast(OperationExecutorContext, context),
            operation_id="create",
            profile_id=_PROFILE,
            request=request,
            work=lambda: (_ for _ in ()).throw(
                InventoryServiceInputError(
                    translated_message="errors.refused.refused_profile_inventory_validation",
                    context={},
                )
            ),
        )
    )

    assert isinstance(result, OperationRefusalEvidence)
    assert result.refusal_code == INVENTORY_VALIDATION_REFUSAL_CODE
    assert context.events.effects == [OperationEffect.UNKNOWN, OperationEffect.NONE]
    assert isinstance(context.operands.value, InventoryOperationExecutionResult)
