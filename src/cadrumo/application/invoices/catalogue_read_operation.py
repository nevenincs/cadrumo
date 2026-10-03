"""Recorded invoice inspection under exact-profile, whole-period authority."""

from __future__ import annotations

import asyncio
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.identity.hex_ids import InvoiceId
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
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.invoices.models import Invoice, InvoiceCatalogue
from ...domain.iva.classification import InvoiceKind
from ..ledger.read_access import resolve_ledger_read_access
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.models import CredentialFreeOperationRequest, OperationRequest, OperationTerminalReceipt
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.refusal_evidence import OperationRefusalEvidence
from ..operations.registry import ALL_OPERATION_FRONTENDS, OperationPublicDefinitionRegistrationV1
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .catalogue_lifecycle import resolve_catalogue_invoice
from .catalogue_read_projection import CatalogueInvoiceSnapshot
from .catalogue_selection import InvoiceLookupRefusalReason, InvoiceLookupRefusedError
from .inspection_read_ports import InvoiceInspectionReadPortsFactory

INVOICE_LIST_OPERATION_DEFINITION_ID = "ledger.invoice.list"
INVOICE_VIEW_OPERATION_DEFINITION_ID = "ledger.invoice.view"
INVOICE_VIEW_REFUSAL_CODE = "REFUSED_INVOICE_LOOKUP"


class InvoiceListRequest(CredentialFreeOperationRequest):
    """Inspect the whole canonical catalogue, optionally selecting invoice kind."""

    profile_id: UUID
    kind: InvoiceKind | None = None


class InvoiceViewRequest(BaseModel):
    """An invoice identity or prefix, kept out of the generic operation journal."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    invoice_id: str


class InvoiceViewSuccess(BaseModel):
    """One explicitly selected canonical record."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["success"] = "success"
    invoice: CatalogueInvoiceSnapshot


class InvoiceViewRefusal(BaseModel):
    """Finite lookup guidance released only through authorized result access."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["refused"] = "refused"
    reason: InvoiceLookupRefusalReason
    candidate_ids: tuple[InvoiceId, ...] = ()

    @model_validator(mode="after")
    def _candidates(self) -> Self:
        if self.reason is InvoiceLookupRefusalReason.AMBIGUOUS:
            if len(self.candidate_ids) < 2 or len(set(self.candidate_ids)) != len(self.candidate_ids):
                raise ValueError("ambiguous invoice lookup requires distinct candidates")
        elif self.candidate_ids:
            raise ValueError("non-ambiguous invoice lookup cannot carry candidates")
        return self


type InvoiceViewOutcome = Annotated[InvoiceViewSuccess | InvoiceViewRefusal, Field(discriminator="kind")]


def _validate_invoices(
    profile_id: UUID, kind: InvoiceKind | None, invoices: tuple[CatalogueInvoiceSnapshot, ...]
) -> None:
    if len({row.invoice_id for row in invoices}) != len(invoices):
        raise ValueError("duplicate invoice identities")
    for row in invoices:
        if row.bucket_id is not None and str(row.bucket_id) != str(profile_id):
            raise ValueError("invoice snapshot belongs to another profile")
        if kind is not None and row.kind is not kind:
            raise ValueError("invoice snapshot differs from selected kind")


def _validate_view(profile_id: UUID, invoice_id: str, outcome: InvoiceViewOutcome) -> None:
    selector = invoice_id.strip()
    if isinstance(outcome, InvoiceViewSuccess):
        _validate_invoices(profile_id, None, (outcome.invoice,))
        if not selector or not outcome.invoice.invoice_id.startswith(selector):
            raise ValueError("invoice snapshot differs from selected identity")
    elif (outcome.reason is InvoiceLookupRefusalReason.REQUIRED) != (not selector):
        raise ValueError("invoice refusal contradicts selector")
    elif any(not candidate.startswith(selector) for candidate in outcome.candidate_ids):
        raise ValueError("invoice refusal contains unrelated candidates")


class InvoiceListResult(BaseModel):
    """Encrypted inventory snapshot with the exact request scope."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    kind: InvoiceKind | None
    invoices: tuple[CatalogueInvoiceSnapshot, ...]

    @model_validator(mode="after")
    def _scope(self) -> Self:
        _validate_invoices(self.profile_id, self.kind, self.invoices)
        return self


class InvoiceListProjection(BaseModel):
    """Independent authorized frontend inventory schema."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    kind: InvoiceKind | None
    invoices: tuple[CatalogueInvoiceSnapshot, ...]

    @model_validator(mode="after")
    def _scope(self) -> Self:
        _validate_invoices(self.profile_id, self.kind, self.invoices)
        return self


class InvoiceViewResult(BaseModel):
    """Encrypted selected record or bounded refusal facts."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    invoice_id: str
    outcome: InvoiceViewOutcome

    @model_validator(mode="after")
    def _scope(self) -> Self:
        _validate_view(self.profile_id, self.invoice_id, self.outcome)
        return self


class InvoiceViewProjection(BaseModel):
    """Independent authorized schema for selected-record disclosure."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    invoice_id: str
    outcome: InvoiceViewOutcome

    @model_validator(mode="after")
    def _scope(self) -> Self:
        _validate_view(self.profile_id, self.invoice_id, self.outcome)
        return self


def _receipt(receipt: OperationTerminalReceipt, *, definition_id: str, profile_id: UUID, refused: bool) -> None:
    code = INVOICE_VIEW_REFUSAL_CODE if refused else None
    if (
        receipt.identity.definition_id != definition_id
        or receipt.identity.subject_ref != profile_operation_subject(str(profile_id))
        or receipt.effect is not OperationEffect.NONE
        or receipt.condition
        is not (OperationTerminalCondition.REFUSED if refused else OperationTerminalCondition.SUCCEEDED)
        or receipt.refusal_ref != code
        or (receipt.refusal_detail_ref is not None) != refused
    ):
        raise ValueError("invoice projection differs from its terminal receipt")


def project_invoice_list_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> InvoiceListProjection:
    """Release only a coherent inventory from a successful exact-profile read."""
    if type(result) is not InvoiceListResult:
        raise ValueError("invalid invoice inventory result")
    private = InvoiceListResult.model_validate(result.model_dump(mode="python"), strict=True)
    _receipt(receipt, definition_id=INVOICE_LIST_OPERATION_DEFINITION_ID, profile_id=private.profile_id, refused=False)
    return InvoiceListProjection(profile_id=private.profile_id, kind=private.kind, invoices=private.invoices)


def project_invoice_view_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> InvoiceViewProjection:
    """Validate refusal and success facts against their distinct terminal conditions."""
    if type(result) is not InvoiceViewResult:
        raise ValueError("invalid invoice selection result")
    private = InvoiceViewResult.model_validate(result.model_dump(mode="python"), strict=True)
    _receipt(
        receipt,
        definition_id=INVOICE_VIEW_OPERATION_DEFINITION_ID,
        profile_id=private.profile_id,
        refused=isinstance(private.outcome, InvoiceViewRefusal),
    )
    return InvoiceViewProjection(profile_id=private.profile_id, invoice_id=private.invoice_id, outcome=private.outcome)


class InvoiceCatalogueReadExecutor:
    """Read one canonical catalogue inside immutable worker custody."""

    def __init__(self, factory: InvoiceInspectionReadPortsFactory, definition_id: str) -> None:
        """Retain the declared reader and exact operation identity."""
        self._factory = factory
        self._definition_id = definition_id

    def _capture(
        self, payload: InvoiceListRequest | InvoiceViewRequest, operation: PinnedAuthorityOperation
    ) -> InvoiceListResult | InvoiceViewResult:
        profile = str(payload.profile_id)
        ports = self._factory(bucket_id=profile, operation=operation)
        if ports.bucket_id != profile or ports.invoices.bucket_id != profile:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        with validating_governed_facts(operation):
            catalogue = ports.invoices.load()
            if any(row.bucket_id is not None and str(row.bucket_id) != profile for row in catalogue.values()):
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            if isinstance(payload, InvoiceListRequest):
                return _capture_invoice_list(payload, catalogue)
            return _capture_invoice_view(payload, catalogue)

    async def execute(
        self, request: OperationRequest[InvoiceListRequest | InvoiceViewRequest], context: OperationExecutorContext
    ) -> str | OperationRefusalEvidence:
        """Retain read/publication ownership until all encrypted operands settle."""
        payload = request.payload
        expected = (
            INVOICE_LIST_OPERATION_DEFINITION_ID
            if isinstance(payload, InvoiceListRequest)
            else INVOICE_VIEW_OPERATION_DEFINITION_ID
        )
        if request.definition_id != expected or request.definition_id != self._definition_id:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(self._definition_id)

        async def capture() -> str | OperationRefusalEvidence:
            result = await asyncio.to_thread(self._capture, payload, context.authority_operation)
            reference = await context.operands.put(result, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            if isinstance(result, InvoiceViewResult) and isinstance(result.outcome, InvoiceViewRefusal):
                return OperationRefusalEvidence(refusal_code=INVOICE_VIEW_REFUSAL_CODE, detail_ref=reference)
            return reference

        return await await_cancellation_complete(capture(), task_name="invoice-catalogue-read")


def _capture_invoice_list(payload: InvoiceListRequest, catalogue: InvoiceCatalogue) -> InvoiceListResult:
    return InvoiceListResult(
        profile_id=payload.profile_id,
        kind=payload.kind,
        invoices=tuple(
            CatalogueInvoiceSnapshot.from_invoice(row)
            for row in catalogue.values()
            if payload.kind is None or row.kind is payload.kind
        ),
    )


def _capture_invoice_view(payload: InvoiceViewRequest, catalogue: InvoiceCatalogue) -> InvoiceViewResult:
    try:
        invoice: Invoice = resolve_catalogue_invoice(catalogue, payload.invoice_id)
    except InvoiceLookupRefusedError as exc:
        outcome: InvoiceViewOutcome = InvoiceViewRefusal(reason=exc.reason, candidate_ids=exc.candidate_ids)
    else:
        outcome = InvoiceViewSuccess(invoice=CatalogueInvoiceSnapshot.from_invoice(invoice))
    return InvoiceViewResult(profile_id=payload.profile_id, invoice_id=payload.invoice_id, outcome=outcome)


def _definition(
    definition_id: str,
    request_type: type[BaseModel],
    result_type: type[BaseModel],
    factory: InvoiceInspectionReadPortsFactory,
    *,
    private_request: bool,
) -> OperationDefinition:
    return build_single_phase_definition(
        definition_id=definition_id,
        request_type=request_type,
        result_type=result_type,
        executor_type=InvoiceCatalogueReadExecutor,
        build=lambda: InvoiceCatalogueReadExecutor(factory, definition_id),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.NONE,
            request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE
            if private_request
            else OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL,
            sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE
            if private_request
            else OperationSensitiveInputPolicy.NONE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN}),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        permitted_frontends=ALL_OPERATION_FRONTENDS,
        refusal_detail_codes=frozenset({INVOICE_VIEW_REFUSAL_CODE}) if private_request else frozenset(),
    )


def build_invoice_list_definition(factory: InvoiceInspectionReadPortsFactory) -> OperationDefinition:
    """Declare a whole-profile catalogue inventory without mutation capability."""
    return _definition(
        INVOICE_LIST_OPERATION_DEFINITION_ID, InvoiceListRequest, InvoiceListResult, factory, private_request=False
    )


def build_invoice_view_definition(factory: InvoiceInspectionReadPortsFactory) -> OperationDefinition:
    """Declare selected-record inspection with encrypted request/refusal custody."""
    return _definition(
        INVOICE_VIEW_OPERATION_DEFINITION_ID, InvoiceViewRequest, InvoiceViewResult, factory, private_request=True
    )


def resolve_invoice_read_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require all periods because catalogue discovery and prefix matching span years."""
    payload = request.payload
    if not isinstance(payload, (InvoiceListRequest, InvoiceViewRequest)):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    expected = (
        INVOICE_LIST_OPERATION_DEFINITION_ID
        if isinstance(payload, InvoiceListRequest)
        else INVOICE_VIEW_OPERATION_DEFINITION_ID
    )
    if request.definition_id != expected:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return resolve_ledger_read_access(request, context, profile_id=payload.profile_id, periods=frozenset())


def build_invoice_list_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Expose independently typed inventory output behind the shared access policy."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=InvoiceListProjection,
        result_projector=project_invoice_list_result,
        access_resolver=resolve_invoice_read_access,
    )


def build_invoice_view_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Expose a guarded selected record or explicitly registered refusal detail."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=InvoiceViewProjection,
        result_projector=project_invoice_view_result,
        access_resolver=resolve_invoice_read_access,
    )
