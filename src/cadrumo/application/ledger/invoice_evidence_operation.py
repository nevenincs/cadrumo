"""Shared exact-profile custody and result rules for invoice evidence operations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Protocol
from uuid import UUID

from pydantic import BaseModel, Field

from ...core.bucket_pointer import require_active_bucket_id
from ...core.config import Settings
from ...core.config_support import LLMProvider
from ...core.hashing import canonical_json_bytes
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ...domain.iva.regime_legend import RegimeLegend, resolve_regime_legends
from ..invoices.catalogue_creation_ports import CatalogueCreationPorts
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.models import OperationTerminalReceipt
from ..operations.owner import OperationExecutorContext
from ..runtime.projection_pages import PROJECTION_DOCUMENT_MAX_BYTES
from ..user_profile.access_contracts import (
    AccessDenialCode,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .counterparty_establishment_ports import CounterpartyEstablishmentRepositoryProtocol
from .evidence_ports import LedgerEvidencePorts
from .invoice_confirmation_ports import InvoiceConfirmationPorts
from .invoice_draft_extraction_ports import EvidenceConsentProof, InvoiceDraftExtractionPorts
from .invoice_extraction_authority import default_invoice_extraction_period

_MAX_RESULT_BYTES = PROJECTION_DOCUMENT_MAX_BYTES - 4_096


InvoiceEvidenceReference = Annotated[str, Field(min_length=1, max_length=64)]


InvoiceEvidenceLabel = Annotated[str, Field(max_length=2_048)]


InvoiceEvidenceNote = Annotated[str, Field(max_length=16_384)]


InvoiceEvidenceDecimalText = Annotated[str, Field(min_length=1, max_length=128)]


@dataclass(frozen=True, slots=True)
class InvoiceEvidenceOperationPorts:
    """One exact-profile capability bundle supplied by executable composition."""

    bucket_id: str
    settings: Settings
    evidence_ports: LedgerEvidencePorts
    extraction_ports: InvoiceDraftExtractionPorts
    catalogue_creation_ports: CatalogueCreationPorts
    invoice_confirmation_ports: InvoiceConfirmationPorts
    counterparty_establishment_repository: CounterpartyEstablishmentRepositoryProtocol
    mint_consent: Callable[[LLMProvider, bool, str, str], EvidenceConsentProof]


class InvoiceEvidenceOperationPortsFactory(Protocol):
    """Bind one profile's evidence and optional consent-ledger write hooks."""

    def __call__(
        self,
        *,
        bucket_id: str,
        before_consent_save: Callable[[], None] | None = None,
        after_consent_save: Callable[[bool], None] | None = None,
    ) -> InvoiceEvidenceOperationPorts:
        """Return exact-profile authorities and paired optional save hooks."""
        ...


def require_bound_invoice_evidence_ports(ports: InvoiceEvidenceOperationPorts, *, bucket_id: str) -> None:
    """Require the supplied operation bundle to match active-profile custody."""
    if ports.bucket_id != bucket_id or require_active_bucket_id() != bucket_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


def check_invoice_evidence_result_size(result: BaseModel) -> None:
    """Refuse a private result document that exceeds the registered projection bound."""
    if len(canonical_json_bytes(result.model_dump(mode="json"))) > _MAX_RESULT_BYTES:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)


def invoice_evidence_operation_capabilities(*, mutates: bool, off_host_optional: bool = False) -> OperationCapabilities:
    """Build the shared durable capability policy from operation effect ownership."""
    effects = (
        frozenset({OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.UNKNOWN})
        if mutates or off_host_optional
        else frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN})
    )
    return OperationCapabilities(
        durability=OperationDurability.RECORDED,
        cancellation=OperationCancellation.UNSUPPORTED,
        deadline=OperationDeadline.ABSENT,
        replay=OperationReplayPolicy.NONE,
        baseline=OperationBaselinePolicy.NONE,
        request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
        sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
        conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
        owned_resources=frozenset(),
        permitted_effects=effects,
        close_policy=OperationClosePolicy.DETACH_ALLOWED,
    )


def resolve_invoice_evidence_authority_legends(context: OperationExecutorContext) -> tuple[RegimeLegend, ...]:
    """Resolve invoice confirmation legends under the retained authority operation."""
    period = default_invoice_extraction_period()
    return resolve_regime_legends(operation=context.authority_operation, effective_date=period.end_date)


def require_invoice_evidence_terminal_success(
    result: BaseModel,
    receipt: OperationTerminalReceipt,
    *,
    definition_id: str,
    profile_id: UUID,
    effects: frozenset[OperationEffect],
) -> None:
    """Require exact result identity, successful terminal state, and an allowed effect."""
    _require_invoice_evidence_terminal_binding(
        result,
        receipt,
        definition_id=definition_id,
        profile_id=profile_id,
    )
    _require_invoice_evidence_terminal_outcome(receipt, effects=effects)


def _require_invoice_evidence_terminal_binding(
    result: BaseModel,
    receipt: OperationTerminalReceipt,
    *,
    definition_id: str,
    profile_id: UUID,
) -> None:
    if (
        receipt.identity.definition_id != definition_id
        or receipt.identity.subject_ref != profile_operation_subject(str(profile_id))
        or getattr(result, "profile_id", None) != profile_id
    ):
        raise ValueError("invoice evidence result has an incompatible terminal receipt")


def _require_invoice_evidence_terminal_outcome(
    receipt: OperationTerminalReceipt,
    *,
    effects: frozenset[OperationEffect],
) -> None:
    if (
        receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.result_ref is None
        or receipt.refusal_ref is not None
        or receipt.refusal_detail_ref is not None
        or receipt.failure_error_code is not None
        or receipt.diagnostic_ref is not None
        or receipt.effect not in effects
    ):
        raise ValueError("invoice evidence result has an incompatible terminal receipt")


__all__ = [
    "InvoiceEvidenceDecimalText",
    "InvoiceEvidenceLabel",
    "InvoiceEvidenceNote",
    "InvoiceEvidenceOperationPorts",
    "InvoiceEvidenceOperationPortsFactory",
    "InvoiceEvidenceReference",
    "check_invoice_evidence_result_size",
    "invoice_evidence_operation_capabilities",
    "require_bound_invoice_evidence_ports",
    "require_invoice_evidence_terminal_success",
    "resolve_invoice_evidence_authority_legends",
]
