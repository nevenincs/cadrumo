"""Real encrypted-store fixtures for the inventory registered-operation matrix."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from ....application.operations.public_scalar import PublicDecimal
from ....core.operations import OperationEffect
from ....core.time.clock import now
from ....domain.contribuyente.inventory.closing_foundations import (
    InventoryClosingAuthority,
    InventoryClosingDecisionEvidence,
    InventoryClosingDecisionEvidenceRole,
    PriorClosingContinuityEvidence,
    fingerprint_prior_authoritative_closing,
)
from ....domain.contribuyente.inventory.records import (
    InventoryCorrectionReason,
    InventoryLedger,
    InventoryRetirementReason,
    MovementKind,
)
from ....domain.filing_evidence import FilingEvidenceReference
from ..ports import InventoryServicePortsFactory
from ..registered_requests import (
    INVENTORY_CLOSING_AUTHORITY_RECORD_OPERATION_DEFINITION_ID,
    INVENTORY_CORRECT_OPERATION_DEFINITION_ID,
    INVENTORY_CREATE_OPERATION_DEFINITION_ID,
    INVENTORY_DESCRIBE_OPERATION_DEFINITION_ID,
    INVENTORY_INSPECT_OPERATION_DEFINITION_ID,
    INVENTORY_LIST_OPERATION_DEFINITION_ID,
    INVENTORY_MOVEMENT_ADD_OPERATION_DEFINITION_ID,
    INVENTORY_MOVEMENT_CORRECT_OPERATION_DEFINITION_ID,
    INVENTORY_MOVEMENT_REVERSE_OPERATION_DEFINITION_ID,
    INVENTORY_RESTORE_OPERATION_DEFINITION_ID,
    INVENTORY_RETIRE_OPERATION_DEFINITION_ID,
    INVENTORY_VALUATION_PREVIEW_OPERATION_DEFINITION_ID,
    InventoryClosingAuthorityDecisionRequest,
    InventoryClosingAuthorityRecordInput,
    InventoryClosingAuthorityRecordRequest,
    InventoryCorrectRequest,
    InventoryCreateRequest,
    InventoryDescribeRequest,
    InventoryInspectRequest,
    InventoryListRequest,
    InventoryMovementAddRequest,
    InventoryMovementCorrectRequest,
    InventoryMovementReverseRequest,
    InventoryPriorClosingLinkRequest,
    InventoryRestoreRequest,
    InventoryRetireRequest,
    InventoryValuationPreviewRequest,
)
from ..registered_specs import INVENTORY_LEDGER_CHANGE_REQUEST_TYPES
from ..service import InventoryMovementCommand, InventoryService


@dataclass(frozen=True, slots=True)
class InventoryOperationConformanceCase:
    """Canonical seed facts and one correctly typed public operation request."""

    request: BaseModel
    actividad_id: str
    year: int
    expected_effect: OperationEffect


def prepare_inventory_operation_conformance_case(
    definition_id: str,
    profile_id: UUID,
    *,
    ports_factory: InventoryServicePortsFactory,
) -> InventoryOperationConformanceCase:
    """Seed the encrypted canonical inventory store and build the typed case request.

    The caller supplies the same real ``build_inventory_service_ports`` factory
    used by production composition. Mutations happen through ``InventoryService``
    so the conformance harness tests the registered worker boundary, not a fake
    repository or result projector.
    """
    bucket_id = str(profile_id)
    service = InventoryService(ports=ports_factory(bucket_id=bucket_id))

    if definition_id == INVENTORY_INSPECT_OPERATION_DEFINITION_ID or definition_id in (
        INVENTORY_LEDGER_CHANGE_REQUEST_TYPES
    ):
        return _prepare_ledger_change_case(definition_id, profile_id, service=service, bucket_id=bucket_id)

    if definition_id == INVENTORY_LIST_OPERATION_DEFINITION_ID:
        actividad_id = "inventory-list-seed"
        service.create(
            bucket_id=bucket_id,
            actividad_id=actividad_id,
            year=2026,
            valuation_method="fifo",
            opening_stock=Decimal("0"),
            actor="conformance-seed",
        )
        return InventoryOperationConformanceCase(
            request=InventoryListRequest(profile_id=profile_id),
            actividad_id=actividad_id,
            year=2026,
            expected_effect=OperationEffect.NONE,
        )

    if definition_id == INVENTORY_CREATE_OPERATION_DEFINITION_ID:
        actividad_id = "inventory-create-op"
        return InventoryOperationConformanceCase(
            request=InventoryCreateRequest(
                profile_id=profile_id,
                actividad_id=actividad_id,
                year=2026,
                valuation_method="fifo",
                opening_stock=PublicDecimal(decimal="0.00"),
            ),
            actividad_id=actividad_id,
            year=2026,
            expected_effect=OperationEffect.UPDATED,
        )

    if definition_id == INVENTORY_MOVEMENT_ADD_OPERATION_DEFINITION_ID:
        actividad_id = "inventory-movement-seed"
        service.create(
            bucket_id=bucket_id,
            actividad_id=actividad_id,
            year=2026,
            valuation_method="fifo",
            opening_stock=Decimal("100.00"),
            actor="conformance-seed",
        )
        return InventoryOperationConformanceCase(
            request=InventoryMovementAddRequest(
                profile_id=profile_id,
                actividad_id=actividad_id,
                year=2026,
                movement_id="inventory-cogs-1",
                movement_date=date(2026, 3, 15),
                kind=MovementKind.COGS,
                quantity=PublicDecimal(decimal="1"),
            ),
            actividad_id=actividad_id,
            year=2026,
            expected_effect=OperationEffect.UPDATED,
        )

    if definition_id == INVENTORY_VALUATION_PREVIEW_OPERATION_DEFINITION_ID:
        actividad_id = "inventory-valuation-seed"
        service.create(
            bucket_id=bucket_id,
            actividad_id=actividad_id,
            year=2026,
            valuation_method="fifo",
            opening_stock=Decimal("100.00"),
            actor="conformance-seed",
        )
        return InventoryOperationConformanceCase(
            request=InventoryValuationPreviewRequest(
                profile_id=profile_id,
                actividad_id=actividad_id,
                year=2026,
            ),
            actividad_id=actividad_id,
            year=2026,
            expected_effect=OperationEffect.UPDATED,
        )

    if definition_id == INVENTORY_CLOSING_AUTHORITY_RECORD_OPERATION_DEFINITION_ID:
        actividad_id = "inventory-closing-seed"
        service.create(
            bucket_id=bucket_id,
            actividad_id=actividad_id,
            year=2026,
            valuation_method="fifo",
            opening_stock=Decimal("100.00"),
            actor="conformance-seed",
        )
        authority_record = build_inventory_conformance_closing_authority_record(actividad_id)
        return InventoryOperationConformanceCase(
            request=InventoryClosingAuthorityRecordRequest(
                profile_id=profile_id,
                actividad_id=actividad_id,
                year=2026,
                authority_record=authority_record,
            ),
            actividad_id=actividad_id,
            year=2026,
            expected_effect=OperationEffect.UPDATED,
        )

    raise ValueError(f"unsupported inventory conformance definition: {definition_id}")


def _prepare_ledger_change_case(
    definition_id: str,
    profile_id: UUID,
    *,
    service: InventoryService,
    bucket_id: str,
) -> InventoryOperationConformanceCase:
    """Seed one inventory holding a movement, retired when the case restores it."""
    actividad_id = "inventory-change-seed"
    service.create(
        bucket_id=bucket_id,
        actividad_id=actividad_id,
        year=2026,
        valuation_method="fifo",
        opening_stock=Decimal("100.00"),
        actor="conformance-seed",
    )
    if definition_id in {
        INVENTORY_MOVEMENT_CORRECT_OPERATION_DEFINITION_ID,
        INVENTORY_MOVEMENT_REVERSE_OPERATION_DEFINITION_ID,
    }:
        service.movement_add(
            bucket_id=bucket_id,
            actividad_id=actividad_id,
            year=2026,
            movement=InventoryMovementCommand(
                movement_id="seed-cogs",
                movement_date=date(2026, 3, 15),
                kind=MovementKind.COGS,
                quantity=Decimal("1"),
            ),
            actor="conformance-seed",
        )
    if definition_id == INVENTORY_RESTORE_OPERATION_DEFINITION_ID:
        service.retire(
            bucket_id=bucket_id,
            actividad_id=actividad_id,
            year=2026,
            correction_id="seed-retire",
            reason=InventoryRetirementReason.CREATED_IN_ERROR,
            actor="conformance-seed",
        )
    change = {"profile_id": profile_id, "actividad_id": actividad_id, "year": 2026, "correction_id": "case-1"}
    reason = InventoryCorrectionReason.KEYING_ERROR
    requests: dict[str, BaseModel] = {
        INVENTORY_INSPECT_OPERATION_DEFINITION_ID: InventoryInspectRequest(
            profile_id=profile_id, actividad_id=actividad_id, year=2026
        ),
        INVENTORY_DESCRIBE_OPERATION_DEFINITION_ID: InventoryDescribeRequest.model_validate(
            {**change, "label": "Hardware"}
        ),
        INVENTORY_CORRECT_OPERATION_DEFINITION_ID: InventoryCorrectRequest.model_validate(
            {**change, "reason": reason, "opening_stock": PublicDecimal(decimal="90.00")}
        ),
        INVENTORY_MOVEMENT_CORRECT_OPERATION_DEFINITION_ID: InventoryMovementCorrectRequest.model_validate(
            {
                **change,
                "target_movement_id": "seed-cogs",
                "reason": reason,
                "movement_id": "seed-cogs-b",
                "movement_date": date(2026, 3, 16),
                "kind": MovementKind.COGS,
                "quantity": PublicDecimal(decimal="1"),
            }
        ),
        INVENTORY_MOVEMENT_REVERSE_OPERATION_DEFINITION_ID: InventoryMovementReverseRequest.model_validate(
            {**change, "target_movement_id": "seed-cogs", "reason": reason}
        ),
        INVENTORY_RETIRE_OPERATION_DEFINITION_ID: InventoryRetireRequest.model_validate(
            {**change, "reason": InventoryRetirementReason.CREATED_IN_ERROR}
        ),
        INVENTORY_RESTORE_OPERATION_DEFINITION_ID: InventoryRestoreRequest.model_validate(change),
    }
    return InventoryOperationConformanceCase(
        request=requests[definition_id],
        actividad_id=actividad_id,
        year=2026,
        expected_effect=(
            OperationEffect.NONE
            if definition_id == INVENTORY_INSPECT_OPERATION_DEFINITION_ID
            else OperationEffect.UPDATED
        ),
    )


def build_inventory_conformance_closing_authority_record(
    actividad_id: str,
) -> InventoryClosingAuthorityRecordInput:
    """Build a canonical movement-derived closing record with complete evidence."""
    continuity = (
        PriorClosingContinuityEvidence(
            reference=FilingEvidenceReference(reference="conformance-prior-closing"),
            content_digest="f" * 64,
        ),
    )
    prior_source_fingerprint = "c" * 64
    prior_closing_fingerprint = fingerprint_prior_authoritative_closing(
        actividad_id=actividad_id,
        filing_year=2025,
        authoritative_closing_value=Decimal("100.00"),
        authoritative_source_fingerprint=prior_source_fingerprint,
        evidence=continuity,
    )
    return InventoryClosingAuthorityRecordInput(
        decision=InventoryClosingAuthorityDecisionRequest(
            decision_id="inventory-closing-decision-2026",
            actividad_id=actividad_id,
            filing_year=2026,
            authority=InventoryClosingAuthority.MOVEMENT_DERIVED,
            reason="Conformance fixture records the evidenced movement-derived authority.",
            actor="conformance-operator",
            source_command="inventory.closing-authority.conformance",
            decided_at=now(),
            evidence=(
                InventoryClosingDecisionEvidence(
                    reference=FilingEvidenceReference(reference="conformance-decision-evidence"),
                    role=InventoryClosingDecisionEvidenceRole.AUTHORITY_RECONCILIATION,
                    content_digest="e" * 64,
                ),
            ),
        ),
        prior_closing_link=InventoryPriorClosingLinkRequest(
            actividad_id=actividad_id,
            current_filing_year=2026,
            prior_filing_year=2025,
            prior_authoritative_closing_value=PublicDecimal(decimal="100.00"),
            current_opening_value=PublicDecimal(decimal="100.00"),
            prior_authoritative_source_fingerprint=prior_source_fingerprint,
            prior_authoritative_closing_fingerprint=prior_closing_fingerprint,
            evidence=continuity,
        ),
    )


def read_inventory_operation_conformance_ledger(
    case: InventoryOperationConformanceCase,
    profile_id: UUID,
    *,
    ports_factory: InventoryServicePortsFactory,
) -> InventoryLedger:
    """Read the committed exact-profile record from its encrypted repository."""
    bucket_id = str(profile_id)
    service = InventoryService(ports=ports_factory(bucket_id=bucket_id))
    return service.show(bucket_id=bucket_id, actividad_id=case.actividad_id, year=case.year)


__all__ = [
    "InventoryOperationConformanceCase",
    "build_inventory_conformance_closing_authority_record",
    "prepare_inventory_operation_conformance_case",
    "read_inventory_operation_conformance_ledger",
]
