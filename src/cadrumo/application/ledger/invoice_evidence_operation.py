"""Registered exact-profile readiness, extraction and invoice confirmation."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Annotated, Protocol, Self
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core.aggregation import IntracomOperationType
from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.config import Settings
from ...core.config_support import LLMProvider
from ...core.confirmation_gate import FindingResolutionAction
from ...core.hashing import canonical_json_bytes
from ...core.hex import Hex64Str
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ...core.time.clock import now
from ...domain.iva.classification import InvoiceKind
from ...domain.iva.regime_legend import RegimeLegend, resolve_regime_legends
from ...domain.iva.schema import IvaCategory
from ...domain.iva.supply_nature import SupplyNature
from ..invoices.catalogue_creation_ports import CatalogueCreationPorts
from ..local_reader import LocalReaderDocumentReadiness, LocalReaderStatus, RoleFitnessState
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.owner import OperationExecutorContext
from ..operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..provisioning_host import RuntimeHostPlatform, RuntimeInstaller
from ..runtime.projection_pages import PROJECTION_DOCUMENT_MAX_BYTES
from ..user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    DisclosureCategory,
    DisclosurePermission,
    OperationAccessPolicy,
    OperationAccessRequest,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .confirmation_gate import FindingResolution
from .counterparty_establishment_ports import CounterpartyEstablishmentRepositoryProtocol
from .evidence import PurchaseInvoiceEvidenceService
from .evidence_ports import LedgerEvidencePorts
from .invoice_confirmation import (
    PreparedInvoiceConfirmation,
    invoice_draft_review_sha256,
    persist_prepared_invoice_confirmation,
    prepare_invoice_confirmation_from_evidence,
)
from .invoice_confirmation_ports import InvoiceConfirmationPorts
from .invoice_draft_extraction import extract_invoice_draft_from_evidence
from .invoice_draft_extraction_ports import EvidenceConsentProof, InvoiceDraftExtractionPorts
from .invoice_evidence_consent_custody import InvoiceEvidenceConsentCustody
from .invoice_evidence_operation_dtos import InvoiceConfirmationProjectionV1, InvoiceDraftProjectionV1
from .invoice_extraction_authority import default_invoice_extraction_period
from .read_access import resolve_ledger_read_access

LEDGER_EVIDENCE_READER_READINESS_OPERATION_DEFINITION_ID = "ledger.evidence.reader-readiness"
LEDGER_EVIDENCE_EXTRACT_OPERATION_DEFINITION_ID = "ledger.evidence.extract"
LEDGER_EVIDENCE_CONFIRM_OPERATION_DEFINITION_ID = "ledger.evidence.confirm"
_EXTRACT_CONSENT_SURFACE = "runtime:ledger.evidence.extract"
_MAX_RESULT_BYTES = PROJECTION_DOCUMENT_MAX_BYTES - 4_096

_Reference = Annotated[str, Field(min_length=1, max_length=64)]
_Label = Annotated[str, Field(max_length=2_048)]
_Note = Annotated[str, Field(max_length=16_384)]
_DecimalText = Annotated[str, Field(min_length=1, max_length=128)]


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


class LedgerEvidenceReaderReadinessRequest(BaseModel):
    """Metadata-only readiness for the authenticated exact profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID


class LedgerEvidenceExtractRequest(BaseModel):
    """One source reference and optional per-invocation off-host consent."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    evidence_id: _Reference | None = None
    attachment_id: _Reference | None = None
    off_host_provider: LLMProvider | None = None
    acknowledge_off_host: bool = False

    @model_validator(mode="after")
    def _one_reference_and_explicit_consent(self) -> Self:
        if (self.evidence_id is None) == (self.attachment_id is None):
            raise ValueError("exactly one evidence or attachment reference is required")
        if self.off_host_provider is None:
            if self.acknowledge_off_host:
                raise ValueError("off-host acknowledgement requires an off-host provider")
        elif self.off_host_provider is LLMProvider.LOCAL or not self.acknowledge_off_host or self.evidence_id is None:
            raise ValueError("off-host reading requires a stored evidence record and per-invocation acknowledgement")
        return self


class FindingResolutionInputV1(BaseModel):
    """Bounded wire form restored to the canonical finding-resolution record."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    blocker_id: Annotated[str, Field(min_length=16, max_length=16)]
    action: FindingResolutionAction
    value: _Label | None = None
    note: _Note = ""

    def to_resolution(self) -> FindingResolution:
        """Restore the canonical one-blocker decision and its validation."""
        return FindingResolution(blocker_id=self.blocker_id, action=self.action, value=self.value, note=self.note)


class LedgerEvidenceConfirmRequest(BaseModel):
    """Complete one-document operator statement, bound to a reviewed draft."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    evidence_id: _Reference | None = None
    attachment_id: _Reference | None = None
    expected_source_sha256: Hex64Str
    expected_draft_review_sha256: Hex64Str
    kind: InvoiceKind
    counterparty_country: Annotated[str, Field(min_length=2, max_length=2)] = "ES"
    counterparty_tax_id: _Label | None = None
    counterparty_name: _Label | None = None
    invoice_number: _Label | None = None
    invoice_date: date | None = None
    taxable_base: _DecimalText | None = None
    iva_rate: _DecimalText | None = None
    iva_amount: _DecimalText | None = None
    currency: Annotated[str, Field(min_length=3, max_length=3)] | None = None
    iva_category: Annotated[str, Field(min_length=1, max_length=128)] | None = None
    operation_type: IntracomOperationType | None = None
    operation_date: date | None = None
    retention_rate: _DecimalText | None = None
    retention_amount: _DecimalText | None = None
    recargo_amount: _DecimalText | None = None
    invoice_class: Annotated[str, Field(min_length=1, max_length=128)] | None = None
    supply_nature: SupplyNature | None = None
    series: _Label | None = None
    rectifies_invoice_number: _Label | None = None
    notes: _Note = ""
    resolutions: Annotated[tuple[FindingResolutionInputV1, ...], Field(max_length=128)] = ()

    @field_validator("taxable_base", "iva_rate", "iva_amount", "retention_rate", "retention_amount", "recargo_amount")
    @classmethod
    def _canonical_decimal(cls, value: str | None) -> str | None:
        """Reject malformed figures before they become a durable operation."""
        _decimal(value)
        return value

    @model_validator(mode="after")
    def _one_reference(self) -> Self:
        if (self.evidence_id is None) == (self.attachment_id is None):
            raise ValueError("exactly one evidence or attachment reference is required")
        return self


class ReaderHostProjectionV1(BaseModel):
    """Closed host facts; no provisioning action is available here."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    platform: RuntimeHostPlatform
    endpoint_url: Annotated[str, Field(min_length=1, max_length=2_048)]
    endpoint_local: bool
    executable_located: bool
    reachable: bool
    version: _Label | None = None
    installer: RuntimeInstaller
    available: bool
    failed_condition_id: _Label | None = None


class ReaderRoleProjectionV1(BaseModel):
    """One locally measured model role and its recorded fitness."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    role: Annotated[str, Field(min_length=1, max_length=128)]
    model: _Label | None = None
    installed: bool | None = None
    resident: bool | None = None
    load_admitted: bool | None = None
    contention_causes: Annotated[tuple[str, ...], Field(max_length=32)] = ()
    fitness: RoleFitnessState | None = None
    fit_for_role: bool | None = None
    ready: bool
    failed_condition_id: _Label | None = None


class ReaderPullProjectionV1(BaseModel):
    """The process-local last pull, if one was recorded earlier."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    model: _Label
    pulled: bool
    attempted_at: datetime
    bytes_fetched: Annotated[int, Field(ge=0)] | None = None
    failed_condition_id: _Label | None = None


class LedgerEvidenceReaderReadinessProjection(BaseModel):
    """Exact-profile reader status without document or tax values."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    host: ReaderHostProjectionV1
    roles: Annotated[tuple[ReaderRoleProjectionV1, ...], Field(max_length=32)]
    last_pull: ReaderPullProjectionV1 | None = None
    extraction_ready: bool
    document_readiness: LocalReaderDocumentReadiness
    text_layer_model_fill_available: bool

    @classmethod
    def from_status(cls, profile_id: UUID, status: LocalReaderStatus) -> Self:
        """Copy measured host and role facts without a provisioning action."""
        host = status.host
        last_pull = status.last_pull
        return cls(
            profile_id=profile_id,
            host=ReaderHostProjectionV1(
                platform=host.platform,
                endpoint_url=host.endpoint_url,
                endpoint_local=host.endpoint_local,
                executable_located=host.executable_located,
                reachable=host.reachable,
                version=host.version,
                installer=host.installer,
                available=host.available,
                failed_condition_id=(
                    None if host.precondition_verdict is None else host.precondition_verdict.failed_condition_id
                ),
            ),
            roles=tuple(
                ReaderRoleProjectionV1(
                    role=row.role.value,
                    model=row.model,
                    installed=row.installed,
                    resident=row.resident,
                    load_admitted=row.load_admitted,
                    contention_causes=tuple(cause.value for cause in row.contention_causes),
                    fitness=row.fitness,
                    fit_for_role=row.fit_for_role,
                    ready=row.ready,
                    failed_condition_id=row.failed_condition_id,
                )
                for row in status.roles
            ),
            last_pull=(
                None
                if last_pull is None
                else ReaderPullProjectionV1(
                    model=last_pull.model,
                    pulled=last_pull.pulled,
                    attempted_at=last_pull.attempted_at,
                    bytes_fetched=last_pull.bytes_fetched,
                    failed_condition_id=last_pull.failed_condition_id,
                )
            ),
            extraction_ready=status.extraction_ready,
            document_readiness=status.document_readiness,
            text_layer_model_fill_available=status.text_layer_model_fill_available,
        )


class LedgerEvidenceExtractProjection(BaseModel):
    """Full draft plus verified raw source and exact review digest."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    evidence_id: _Reference | None = None
    attachment_id: _Reference | None = None
    source_sha256: Hex64Str
    draft_review_sha256: Hex64Str
    off_host_provider: LLMProvider | None = None
    consent_audit_effect: OperationEffect
    draft: InvoiceDraftProjectionV1


class LedgerEvidenceConfirmProjection(BaseModel):
    """Canonical invoice result and the re-read draft used to confirm it."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    evidence_id: _Reference | None = None
    attachment_id: _Reference | None = None
    source_sha256: Hex64Str
    reviewed_draft_sha256: Hex64Str
    confirmation: InvoiceConfirmationProjectionV1


class LedgerEvidenceReaderReadinessExecutionResult(BaseModel):
    """Encrypted worker result scoped to the exact profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    result: LedgerEvidenceReaderReadinessProjection


class LedgerEvidenceExtractExecutionResult(BaseModel):
    """Encrypted worker draft and consent effect witness."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    result: LedgerEvidenceExtractProjection


class LedgerEvidenceConfirmExecutionResult(BaseModel):
    """Encrypted worker confirmation result scoped to the exact profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    result: LedgerEvidenceConfirmProjection


def _require_worker_identity[PayloadT: BaseModel](
    request: OperationRequest[PayloadT],
    context: OperationExecutorContext,
    *,
    definition_id: str,
    bucket_id: str,
) -> None:
    subject = profile_operation_subject(bucket_id)
    if (
        request.definition_id != definition_id
        or context.identity.definition_id != definition_id
        or request.subject_ref != subject
        or context.identity.subject_ref != subject
        or require_active_bucket_id() != bucket_id
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


def _require_bound_ports(ports: InvoiceEvidenceOperationPorts, *, bucket_id: str) -> None:
    if ports.bucket_id != bucket_id or require_active_bucket_id() != bucket_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


def _check_result_size(result: BaseModel) -> None:
    if len(canonical_json_bytes(result.model_dump(mode="json"))) > _MAX_RESULT_BYTES:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)


def _decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    try:
        parsed = Decimal(value)
    except InvalidOperation:
        raise ValueError("invalid decimal confirmation field") from None
    if not parsed.is_finite() or str(parsed) != value:
        raise ValueError("confirmation decimal must be finite and canonical")
    return parsed


def _authority_legends(context: OperationExecutorContext) -> tuple[RegimeLegend, ...]:
    period = default_invoice_extraction_period()
    return resolve_regime_legends(operation=context.authority_operation, effective_date=period.end_date)


class LedgerEvidenceReaderReadinessExecutor:
    """Read local runtime and recorded fitness without loading a model."""

    def __init__(self, read_status: Callable[[], LocalReaderStatus]) -> None:
        """Bind the read-only canonical status provider."""
        self._read_status = read_status

    async def execute(
        self, request: OperationRequest[LedgerEvidenceReaderReadinessRequest], context: OperationExecutorContext
    ) -> str:
        """Measure local readiness and capture a bounded profile result."""
        profile_id = request.payload.profile_id
        _require_worker_identity(
            request,
            context,
            definition_id=LEDGER_EVIDENCE_READER_READINESS_OPERATION_DEFINITION_ID,
            bucket_id=str(profile_id),
        )
        await context.events.phase(LEDGER_EVIDENCE_READER_READINESS_OPERATION_DEFINITION_ID)
        await context.events.effect(OperationEffect.NONE)

        async def read_and_capture() -> str:
            status = await asyncio.to_thread(self._read_status)
            result = LedgerEvidenceReaderReadinessProjection.from_status(profile_id, status)
            _check_result_size(result)
            return await context.operands.put(
                LedgerEvidenceReaderReadinessExecutionResult(profile_id=profile_id, result=result),
                written_at=now(),
            )

        return await await_cancellation_complete(read_and_capture(), task_name="ledger-evidence-reader-readiness")


class LedgerEvidenceExtractExecutor:
    """Extract one verified source with optional one-invocation off-host consent."""

    def __init__(self, ports_factory: InvoiceEvidenceOperationPortsFactory) -> None:
        """Bind the exact-profile evidence capability factory."""
        self._ports_factory = ports_factory

    async def execute(
        self, request: OperationRequest[LedgerEvidenceExtractRequest], context: OperationExecutorContext
    ) -> str:
        """Extract with actual consent writes, then capture the closed draft."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        _require_worker_identity(
            request, context, definition_id=LEDGER_EVIDENCE_EXTRACT_OPERATION_DEFINITION_ID, bucket_id=bucket_id
        )
        await context.events.phase(LEDGER_EVIDENCE_EXTRACT_OPERATION_DEFINITION_ID)
        await context.events.effect(OperationEffect.NONE)
        custody = InvoiceEvidenceConsentCustody(context) if payload.off_host_provider is not None else None

        def extract() -> LedgerEvidenceExtractProjection:
            ports = self._ports_factory(
                bucket_id=bucket_id,
                before_consent_save=None if custody is None else custody.before_save,
                after_consent_save=None if custody is None else custody.after_save,
            )
            _require_bound_ports(ports, bucket_id=bucket_id)
            source_sha256 = payload.attachment_id
            consent_token: EvidenceConsentProof | None = None
            if payload.evidence_id is not None:
                record = PurchaseInvoiceEvidenceService(ports=ports.evidence_ports).view(
                    bucket_id=bucket_id, evidence_id=payload.evidence_id
                )
                if (
                    record.bucket_id != bucket_id
                    or record.evidence_id != payload.evidence_id
                    or record.attachment_id != record.source_sha256
                ):
                    raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
                source_sha256 = record.source_sha256
            if source_sha256 is None:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
            if payload.off_host_provider is not None:
                consent_token = ports.mint_consent(
                    payload.off_host_provider,
                    payload.acknowledge_off_host,
                    _EXTRACT_CONSENT_SURFACE,
                    source_sha256,
                )
                if consent_token.evidence_content_address != source_sha256:
                    raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
            legends = _authority_legends(context)
            draft = extract_invoice_draft_from_evidence(
                bucket_id=bucket_id,
                evidence_id=payload.evidence_id,
                attachment_id=payload.attachment_id,
                settings=ports.settings,
                off_host_provider=payload.off_host_provider,
                consent_token=consent_token,
                ports=ports.extraction_ports,
                operation=context.authority_operation,
                legends=legends,
            )
            result = LedgerEvidenceExtractProjection(
                profile_id=payload.profile_id,
                evidence_id=payload.evidence_id,
                attachment_id=payload.attachment_id,
                source_sha256=source_sha256,
                draft_review_sha256=invoice_draft_review_sha256(draft),
                off_host_provider=payload.off_host_provider,
                consent_audit_effect=OperationEffect.NONE if custody is None else custody.current_effect,
                draft=InvoiceDraftProjectionV1.from_draft(draft),
            )
            _check_result_size(result)
            return result

        async def extract_and_capture() -> str:
            result = await asyncio.to_thread(extract)
            return await context.operands.put(
                LedgerEvidenceExtractExecutionResult(profile_id=payload.profile_id, result=result),
                written_at=now(),
            )

        return await await_cancellation_complete(extract_and_capture(), task_name="ledger-evidence-extract")


class LedgerEvidenceConfirmExecutor:
    """Re-read the reviewed source, then write exactly one canonical confirmation."""

    def __init__(self, ports_factory: InvoiceEvidenceOperationPortsFactory) -> None:
        """Bind the exact-profile confirmation capability factory."""
        self._ports_factory = ports_factory

    async def execute(
        self, request: OperationRequest[LedgerEvidenceConfirmRequest], context: OperationExecutorContext
    ) -> str:
        """Check the reviewed source before entering canonical write custody."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        _require_worker_identity(
            request, context, definition_id=LEDGER_EVIDENCE_CONFIRM_OPERATION_DEFINITION_ID, bucket_id=bucket_id
        )
        await context.events.phase(LEDGER_EVIDENCE_CONFIRM_OPERATION_DEFINITION_ID)
        await context.events.effect(OperationEffect.NONE)
        ports = self._ports_factory(bucket_id=bucket_id)
        _require_bound_ports(ports, bucket_id=bucket_id)

        def prepare() -> PreparedInvoiceConfirmation:
            return prepare_invoice_confirmation_from_evidence(
                bucket_id=bucket_id,
                kind=payload.kind,
                counterparty_country=payload.counterparty_country,
                evidence_id=payload.evidence_id,
                attachment_id=payload.attachment_id,
                counterparty_tax_id=payload.counterparty_tax_id,
                counterparty_name=payload.counterparty_name,
                invoice_number=payload.invoice_number,
                invoice_date=payload.invoice_date,
                taxable_base=_decimal(payload.taxable_base),
                iva_rate=_decimal(payload.iva_rate),
                iva_amount=_decimal(payload.iva_amount),
                currency=payload.currency,
                iva_category=None if payload.iva_category is None else IvaCategory(payload.iva_category),
                operation_type=payload.operation_type,
                operation_date=payload.operation_date,
                retention_rate=_decimal(payload.retention_rate),
                retention_amount=_decimal(payload.retention_amount),
                recargo_amount=_decimal(payload.recargo_amount),
                invoice_class_token=payload.invoice_class,
                supply_nature=payload.supply_nature,
                series=payload.series,
                rectifies_invoice_number=payload.rectifies_invoice_number,
                notes=payload.notes,
                resolutions=tuple(row.to_resolution() for row in payload.resolutions),
                expected_source_sha256=payload.expected_source_sha256,
                expected_draft_review_sha256=payload.expected_draft_review_sha256,
                settings=ports.settings,
                catalogue_creation_ports=ports.catalogue_creation_ports,
                counterparty_establishment_repository=ports.counterparty_establishment_repository,
                evidence_ports=ports.evidence_ports,
                extraction_ports=ports.extraction_ports,
                operation=context.authority_operation,
                legends=_authority_legends(context),
            )

        async def prepare_persist_capture() -> str:
            prepared = await asyncio.to_thread(prepare)
            async with context.cancellation.irreversible_section():
                await context.events.effect(OperationEffect.UNKNOWN)
                confirmation = await asyncio.to_thread(
                    persist_prepared_invoice_confirmation,
                    prepared,
                    confirmed_by=f"operation:{context.identity.operation_id}",
                    catalogue_creation_ports=ports.catalogue_creation_ports,
                    invoice_confirmation_ports=ports.invoice_confirmation_ports,
                    evidence_ports=ports.evidence_ports,
                )
                await context.events.effect(OperationEffect.UPDATED)
            result = LedgerEvidenceConfirmProjection(
                profile_id=payload.profile_id,
                evidence_id=payload.evidence_id,
                attachment_id=payload.attachment_id,
                source_sha256=payload.expected_source_sha256,
                reviewed_draft_sha256=payload.expected_draft_review_sha256,
                confirmation=InvoiceConfirmationProjectionV1.from_result(confirmation),
            )
            _check_result_size(result)
            return await context.operands.put(
                LedgerEvidenceConfirmExecutionResult(profile_id=payload.profile_id, result=result),
                written_at=now(),
            )

        return await await_cancellation_complete(prepare_persist_capture(), task_name="ledger-evidence-confirm")


def _capabilities(*, mutates: bool, off_host_optional: bool = False) -> OperationCapabilities:
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


def build_ledger_evidence_reader_readiness_definition(
    read_status: Callable[[], LocalReaderStatus],
) -> OperationDefinition:
    """Register one read-only local reader measurement for the exact profile."""
    return OperationDefinition(
        definition_id=LEDGER_EVIDENCE_READER_READINESS_OPERATION_DEFINITION_ID,
        request_type=LedgerEvidenceReaderReadinessRequest,
        result_type=LedgerEvidenceReaderReadinessExecutionResult,
        executor_factory=OperationExecutorFactory(
            request_type=LedgerEvidenceReaderReadinessRequest,
            executor_type=LedgerEvidenceReaderReadinessExecutor,
            build=lambda: LedgerEvidenceReaderReadinessExecutor(read_status),
        ),
        phase_codes=(LEDGER_EVIDENCE_READER_READINESS_OPERATION_DEFINITION_ID,),
        interaction_kinds=frozenset(),
        capabilities=_capabilities(mutates=False),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}),
    )


def build_ledger_evidence_extract_definition(
    ports_factory: InvoiceEvidenceOperationPortsFactory,
) -> OperationDefinition:
    """Register on-host extraction and explicit per-invocation off-host reading."""
    return OperationDefinition(
        definition_id=LEDGER_EVIDENCE_EXTRACT_OPERATION_DEFINITION_ID,
        request_type=LedgerEvidenceExtractRequest,
        result_type=LedgerEvidenceExtractExecutionResult,
        executor_factory=OperationExecutorFactory(
            request_type=LedgerEvidenceExtractRequest,
            executor_type=LedgerEvidenceExtractExecutor,
            build=lambda: LedgerEvidenceExtractExecutor(ports_factory),
        ),
        phase_codes=(LEDGER_EVIDENCE_EXTRACT_OPERATION_DEFINITION_ID,),
        interaction_kinds=frozenset(),
        capabilities=_capabilities(mutates=False, off_host_optional=True),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}),
    )


def build_ledger_evidence_confirm_definition(
    ports_factory: InvoiceEvidenceOperationPortsFactory,
) -> OperationDefinition:
    """Register one reviewed invoice confirmation with canonical audit writes."""
    return OperationDefinition(
        definition_id=LEDGER_EVIDENCE_CONFIRM_OPERATION_DEFINITION_ID,
        request_type=LedgerEvidenceConfirmRequest,
        result_type=LedgerEvidenceConfirmExecutionResult,
        executor_factory=OperationExecutorFactory(
            request_type=LedgerEvidenceConfirmRequest,
            executor_type=LedgerEvidenceConfirmExecutor,
            build=lambda: LedgerEvidenceConfirmExecutor(ports_factory),
        ),
        phase_codes=(LEDGER_EVIDENCE_CONFIRM_OPERATION_DEFINITION_ID,),
        interaction_kinds=frozenset(),
        capabilities=_capabilities(mutates=True),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}),
    )


def _require_terminal_success(
    result: BaseModel,
    receipt: OperationTerminalReceipt,
    *,
    definition_id: str,
    profile_id: UUID,
    effects: frozenset[OperationEffect],
) -> None:
    if (
        receipt.identity.definition_id != definition_id
        or receipt.identity.subject_ref != profile_operation_subject(str(profile_id))
        or receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.result_ref is None
        or receipt.refusal_ref is not None
        or receipt.refusal_detail_ref is not None
        or receipt.failure_error_code is not None
        or receipt.diagnostic_ref is not None
        or receipt.effect not in effects
        or getattr(result, "profile_id", None) != profile_id
    ):
        raise ValueError("invoice evidence result has an incompatible terminal receipt")


def _project_readiness(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    if type(result) is not LedgerEvidenceReaderReadinessExecutionResult:
        raise ValueError("invalid reader readiness result")
    _require_terminal_success(
        result,
        receipt,
        definition_id=LEDGER_EVIDENCE_READER_READINESS_OPERATION_DEFINITION_ID,
        profile_id=result.profile_id,
        effects=frozenset({OperationEffect.NONE}),
    )
    if result.result.profile_id != result.profile_id:
        raise ValueError("reader readiness result belongs to another profile")
    return result.result


def _project_extract(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    if type(result) is not LedgerEvidenceExtractExecutionResult:
        raise ValueError("invalid invoice extraction result")
    projection = result.result
    _require_terminal_success(
        result,
        receipt,
        definition_id=LEDGER_EVIDENCE_EXTRACT_OPERATION_DEFINITION_ID,
        profile_id=result.profile_id,
        effects=frozenset({projection.consent_audit_effect}),
    )
    if (
        projection.consent_audit_effect not in {OperationEffect.NONE, OperationEffect.UPDATED}
        or (projection.profile_id != result.profile_id)
        or (projection.off_host_provider is None and projection.consent_audit_effect is not OperationEffect.NONE)
    ):
        raise ValueError("invoice extraction result has incompatible consent effect or profile")
    return projection


def _project_confirm(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    if type(result) is not LedgerEvidenceConfirmExecutionResult:
        raise ValueError("invalid invoice confirmation result")
    _require_terminal_success(
        result,
        receipt,
        definition_id=LEDGER_EVIDENCE_CONFIRM_OPERATION_DEFINITION_ID,
        profile_id=result.profile_id,
        effects=frozenset({OperationEffect.UPDATED}),
    )
    if result.result.profile_id != result.profile_id:
        raise ValueError("invoice confirmation result belongs to another profile")
    return result.result


def _resolve_metadata_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    payload = request.payload
    if (
        request.definition_id != LEDGER_EVIDENCE_READER_READINESS_OPERATION_DEFINITION_ID
        or type(payload) is not LedgerEvidenceReaderReadinessRequest
        or context.contract.definition_id != request.definition_id
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if payload.profile_id != context.profile_id or request.subject_ref != profile_operation_subject(
        str(payload.profile_id)
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    disclosure = None
    if context.action in {AccessAction.OBSERVE, AccessAction.CANCEL, AccessAction.DETACH}:
        disclosure = DisclosurePermission(
            destination_id=context.destination_id,
            projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
            category=DisclosureCategory.OPERATION_METADATA,
        )
    elif context.action is AccessAction.RESULT:
        schema = context.contract.result_schema
        if schema is None:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        disclosure = DisclosurePermission(
            destination_id=context.destination_id,
            projection_id=schema.schema_id,
            category=DisclosureCategory.PROFILE_VALUES,
        )
    return ResolvedOperationAccess(
        request=OperationAccessRequest(
            profile_id=payload.profile_id,
            definition_id=request.definition_id,
            action=context.action,
            frontend=context.frontend,
            periods=frozenset(),
            period_independent=True,
            destination_id=context.destination_id,
        ),
        policy=OperationAccessPolicy(
            definition_id=request.definition_id,
            definition_contract_digest=context.contract.definition_contract_digest,
            actions=frozenset(
                {
                    AccessAction.SUBMIT,
                    AccessAction.START,
                    AccessAction.RESUME,
                    AccessAction.OBSERVE,
                    AccessAction.RESULT,
                    AccessAction.CANCEL,
                    AccessAction.DETACH,
                }
            ),
            disclosures=frozenset((disclosure,)) if disclosure is not None else frozenset(),
            periods=frozenset(),
            allow_period_independent=True,
            requires_all_periods=False,
            backend=Availability.AVAILABLE,
            published_authority=context.published_authority,
            provider=Availability.NOT_REQUIRED,
            transaction_authority_required=False,
        ),
    )


def _resolve_extract_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    if (
        request.definition_id != LEDGER_EVIDENCE_EXTRACT_OPERATION_DEFINITION_ID
        or type(request.payload) is not LedgerEvidenceExtractRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    resolved = resolve_ledger_read_access(request, context, profile_id=request.payload.profile_id, periods=frozenset())
    if request.payload.off_host_provider is None:
        return resolved
    policy = OperationAccessPolicy.model_validate(
        {**dict(resolved.policy), "actions": resolved.policy.actions | {AccessAction.COMMIT}}
    )
    return ResolvedOperationAccess(request=resolved.request, policy=policy)


def _resolve_confirm_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    if (
        request.definition_id != LEDGER_EVIDENCE_CONFIRM_OPERATION_DEFINITION_ID
        or type(request.payload) is not LedgerEvidenceConfirmRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    resolved = resolve_ledger_read_access(request, context, profile_id=request.payload.profile_id, periods=frozenset())
    policy = OperationAccessPolicy.model_validate(
        {**dict(resolved.policy), "actions": resolved.policy.actions | {AccessAction.COMMIT}}
    )
    return ResolvedOperationAccess(request=resolved.request, policy=policy)


def build_ledger_evidence_reader_readiness_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind metadata disclosure and the closed readiness schema."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request",
            schema_version=1,
            model_type=LedgerEvidenceReaderReadinessRequest,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result",
            schema_version=1,
            model_type=LedgerEvidenceReaderReadinessProjection,
        ),
        result_projector=_project_readiness,
        access_resolver=_resolve_metadata_access,
    )


def build_ledger_evidence_extract_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind all-period tax disclosure and the exact consent effect witness."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request", schema_version=1, model_type=LedgerEvidenceExtractRequest
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result",
            schema_version=1,
            model_type=LedgerEvidenceExtractProjection,
        ),
        result_projector=_project_extract,
        access_resolver=_resolve_extract_access,
    )


def build_ledger_evidence_confirm_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind all-period tax disclosure and UPDATED confirmation receipts."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request", schema_version=1, model_type=LedgerEvidenceConfirmRequest
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result",
            schema_version=1,
            model_type=LedgerEvidenceConfirmProjection,
        ),
        result_projector=_project_confirm,
        access_resolver=_resolve_confirm_access,
    )


__all__ = [
    "LEDGER_EVIDENCE_CONFIRM_OPERATION_DEFINITION_ID",
    "LEDGER_EVIDENCE_EXTRACT_OPERATION_DEFINITION_ID",
    "LEDGER_EVIDENCE_READER_READINESS_OPERATION_DEFINITION_ID",
    "FindingResolutionInputV1",
    "InvoiceEvidenceOperationPorts",
    "InvoiceEvidenceOperationPortsFactory",
    "LedgerEvidenceConfirmExecutionResult",
    "LedgerEvidenceConfirmExecutor",
    "LedgerEvidenceConfirmProjection",
    "LedgerEvidenceConfirmRequest",
    "LedgerEvidenceExtractExecutionResult",
    "LedgerEvidenceExtractExecutor",
    "LedgerEvidenceExtractProjection",
    "LedgerEvidenceExtractRequest",
    "LedgerEvidenceReaderReadinessExecutionResult",
    "LedgerEvidenceReaderReadinessExecutor",
    "LedgerEvidenceReaderReadinessProjection",
    "LedgerEvidenceReaderReadinessRequest",
    "ReaderHostProjectionV1",
    "ReaderPullProjectionV1",
    "ReaderRoleProjectionV1",
    "build_ledger_evidence_confirm_definition",
    "build_ledger_evidence_confirm_registration",
    "build_ledger_evidence_extract_definition",
    "build_ledger_evidence_extract_registration",
    "build_ledger_evidence_reader_readiness_definition",
    "build_ledger_evidence_reader_readiness_registration",
]
