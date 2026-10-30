"""Registered read of the closed vocabularies an inventory form offers.

Every value comes from its canonical enum, so a frontend holds no list of its own.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final, Literal
from uuid import UUID

from pydantic import BaseModel

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ...core.bucket_pointer import require_active_bucket_id
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect, profile_operation_subject
from ...core.time.clock import now
from ...domain.contribuyente.inventory.closing_foundations import (
    InventoryClosingAuthority,
    InventoryClosingDecisionEvidenceRole,
    InventoryClosingValuationBasis,
    PhysicalClosingEvidenceRole,
)
from ...domain.contribuyente.inventory.records import (
    InventoryAcquisitionEvidenceKind,
    InventoryAttributableCostKind,
    InventoryCorrectionReason,
    InventoryHistoryKind,
    InventoryRetirementReason,
    MovementKind,
    ValuationMethod,
)
from ..ledger.read_access import resolve_ledger_read_access
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES
from ..operations.models import (
    OperationRequest,
    OperationTerminalReceipt,
    require_succeeded_terminal_receipt,
)
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.registry import OperationPublicDefinitionRegistrationV1
from ..operations.subject_reference import OperationSubjectReferenceV1
from ..user_profile.access_errors import ProfileAccessRefusedError

INVENTORY_OPTIONS_OPERATION_DEFINITION_ID = "ledger.inventory.options"

INVENTORY_OPTION_FAMILIES: Final[tuple[tuple[str, type[StrEnum]], ...]] = (
    ("acquisition_evidence_kind", InventoryAcquisitionEvidenceKind),
    ("attributable_cost_kind", InventoryAttributableCostKind),
    ("closing_authority", InventoryClosingAuthority),
    ("closing_valuation_basis", InventoryClosingValuationBasis),
    ("correction_reason", InventoryCorrectionReason),
    ("decision_evidence_role", InventoryClosingDecisionEvidenceRole),
    ("history_kind", InventoryHistoryKind),
    ("movement_kind", MovementKind),
    ("physical_evidence_role", PhysicalClosingEvidenceRole),
    ("retirement_reason", InventoryRetirementReason),
    ("valuation_method", ValuationMethod),
)
"""Each form vocabulary and the enum that owns it; its words live under one label family."""

type InventoryOptionRole = Literal["cost_check", "iva_check", "count_authority", "purchase"]

_OPTION_ROLES: Final[dict[StrEnum, InventoryOptionRole]] = {
    InventoryAcquisitionEvidenceKind.ATTRIBUTABLE_COST_REVIEW: "cost_check",
    InventoryAcquisitionEvidenceKind.IVA_RECOVERABILITY_REVIEW: "iva_check",
    InventoryClosingAuthority.PHYSICAL_OBSERVATION: "count_authority",
    MovementKind.PURCHASE: "purchase",
}
"""The members a form treats specially, named by the enums themselves so a rename cannot leave a stale copy."""


class InventoryOptionsRequest(BaseModel):
    """Ask for the vocabularies; they do not vary by inventory."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID


class InventoryOptionProjection(BaseModel):
    """One offered value and the key of its word."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    value: str
    label_key: str
    role: InventoryOptionRole | None = None


class InventoryOptionFamilyProjection(BaseModel):
    """One closed vocabulary."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    family: str
    options: tuple[InventoryOptionProjection, ...]


class InventoryOptionsProjection(BaseModel):
    """Every vocabulary an inventory form offers."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    families: tuple[InventoryOptionFamilyProjection, ...]


class InventoryOptionsExecutionResult(BaseModel):
    """Private result kept in the worker's encrypted operation record."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result: InventoryOptionsProjection


def inventory_options(profile_id: UUID) -> InventoryOptionsProjection:
    """Derive every vocabulary from its canonical enum."""
    return InventoryOptionsProjection(
        profile_id=profile_id,
        families=tuple(
            InventoryOptionFamilyProjection(
                family=family,
                options=tuple(
                    InventoryOptionProjection(
                        value=member.value,
                        label_key=f"application.inventory.labels.{family}.{member.value}",
                        role=_OPTION_ROLES.get(member),
                    )
                    for member in enum
                ),
            )
            for family, enum in INVENTORY_OPTION_FAMILIES
        ),
    )


class InventoryOptionsExecutor:
    """Answer the vocabularies inside the exact profile's worker."""

    async def execute(
        self,
        request: OperationRequest[InventoryOptionsRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Check the exact profile, then answer; nothing is read or written."""
        bucket_id = str(request.payload.profile_id)
        subject = profile_operation_subject(bucket_id)
        if (
            request.definition_id != INVENTORY_OPTIONS_OPERATION_DEFINITION_ID
            or context.identity.definition_id != INVENTORY_OPTIONS_OPERATION_DEFINITION_ID
            or request.subject_ref != subject
            or context.identity.subject_ref != subject
            or require_active_bucket_id() != bucket_id
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase(INVENTORY_OPTIONS_OPERATION_DEFINITION_ID)
        return await context.operands.put(
            InventoryOptionsExecutionResult(result=inventory_options(request.payload.profile_id)),
            written_at=now(),
        )


def _project_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    if type(result) is not InventoryOptionsExecutionResult:
        raise ValueError("invalid inventory options result")
    require_succeeded_terminal_receipt(
        receipt,
        definition_id=INVENTORY_OPTIONS_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(result.result.profile_id)),
        effect=OperationEffect.NONE,
        message="inventory options has an incompatible terminal receipt",
    )
    return result.result


def build_inventory_options_definition() -> OperationDefinition:
    """Declare the exact-profile read of the inventory form vocabularies."""
    return build_single_phase_definition(
        definition_id=INVENTORY_OPTIONS_OPERATION_DEFINITION_ID,
        request_type=InventoryOptionsRequest,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=InventoryOptionsExecutionResult,
        executor_type=InventoryOptionsExecutor,
        build=InventoryOptionsExecutor,
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES,
    )


def resolve_inventory_options_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Bind the read to the exact profile, as every inventory read is."""
    if request.definition_id != INVENTORY_OPTIONS_OPERATION_DEFINITION_ID or not isinstance(
        request.payload, InventoryOptionsRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return resolve_ledger_read_access(request, context, profile_id=request.payload.profile_id, periods=frozenset())


def build_inventory_options_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind bounded schemas, exact-profile access and receipt projection."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=InventoryOptionsProjection,
        result_projector=_project_result,
        access_resolver=resolve_inventory_options_access,
    )


__all__ = [
    "INVENTORY_OPTIONS_OPERATION_DEFINITION_ID",
    "INVENTORY_OPTION_FAMILIES",
    "InventoryOptionFamilyProjection",
    "InventoryOptionProjection",
    "InventoryOptionsExecutionResult",
    "InventoryOptionsExecutor",
    "InventoryOptionsProjection",
    "InventoryOptionsRequest",
    "build_inventory_options_definition",
    "build_inventory_options_registration",
    "inventory_options",
    "resolve_inventory_options_access",
]
