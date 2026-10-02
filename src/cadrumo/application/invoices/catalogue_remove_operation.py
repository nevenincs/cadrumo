"""Guarded removal of one canonical invoice inside profile worker custody."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    profile_operation_subject,
)
from ...core.time.clock import now
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
from ..operations.models import OperationRequest
from ..operations.owner import OperationExecutorContext
from ..operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..user_profile.access_contracts import AccessAction, AccessDenialCode, OperationAccessPolicy
from ..user_profile.access_errors import ProfileAccessRefusedError
from .catalogue_lifecycle import remove_catalogue_invoice
from .catalogue_lifecycle_ports import CatalogueLifecyclePortsFactory
from .catalogue_read_projection import CatalogueInvoiceSnapshot

INVOICE_REMOVE_OPERATION_DEFINITION_ID = "ledger.invoice.remove"


class InvoiceRemoveRequest(BaseModel):
    """Exact profile and selected record or unambiguous prefix."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    invoice_id: str = Field(min_length=1, max_length=64)


class InvoiceRemoveResult(BaseModel):
    """Committed record snapshot, held as an encrypted operation operand."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    invoice_id: str
    invoice: CatalogueInvoiceSnapshot

    @model_validator(mode="after")
    def _identity(self) -> InvoiceRemoveResult:
        if (
            not self.invoice_id.strip()
            or not self.invoice.invoice_id.startswith(self.invoice_id.strip())
            or (self.invoice.bucket_id is not None and str(self.invoice.bucket_id) != str(self.profile_id))
        ):
            raise ValueError("removed invoice differs from requested identity")
        return self


class InvoiceRemoveExecutor:
    """Use the existing lifecycle service under the runtime commit fence."""

    def __init__(self, factory: CatalogueLifecyclePortsFactory) -> None:
        """Retain the worker's lifecycle port composition."""
        self._factory = factory

    async def execute(self, request: OperationRequest[InvoiceRemoveRequest], context: OperationExecutorContext) -> str:
        """Keep the commit fence through deletion and encrypted receipt publication."""
        payload = request.payload
        profile = str(payload.profile_id)
        if (
            request.definition_id != INVOICE_REMOVE_OPERATION_DEFINITION_ID
            or request.subject_ref != profile_operation_subject(profile)
            or context.identity.definition_id != request.definition_id
            or context.identity.subject_ref != request.subject_ref
            or require_active_bucket_id() != profile
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase(INVOICE_REMOVE_OPERATION_DEFINITION_ID)

        def remove() -> InvoiceRemoveResult:
            ports = self._factory(bucket_id=profile)
            removed = remove_catalogue_invoice(bucket_id=profile, invoice_id=payload.invoice_id, ports=ports)
            return InvoiceRemoveResult(
                profile_id=payload.profile_id,
                invoice_id=payload.invoice_id,
                invoice=CatalogueInvoiceSnapshot.from_invoice(removed.invoice),
            )

        async def commit() -> str:
            async with context.cancellation.irreversible_section():
                await context.events.effect(OperationEffect.UNKNOWN)
                result = await asyncio.to_thread(remove)
                await context.events.effect(OperationEffect.UPDATED)
                return await context.operands.put(result, written_at=now())

        return await await_cancellation_complete(commit(), task_name="invoice-remove-publication")


def build_invoice_remove_definition(factory: CatalogueLifecyclePortsFactory) -> OperationDefinition:
    """Declare one durable, guarded removal with honest uncertain effects."""
    return OperationDefinition(
        definition_id=INVOICE_REMOVE_OPERATION_DEFINITION_ID,
        request_type=InvoiceRemoveRequest,
        result_type=InvoiceRemoveResult,
        executor_factory=OperationExecutorFactory(
            request_type=InvoiceRemoveRequest,
            executor_type=InvoiceRemoveExecutor,
            build=lambda: InvoiceRemoveExecutor(factory),
        ),
        phase_codes=(INVOICE_REMOVE_OPERATION_DEFINITION_ID,),
        interaction_kinds=frozenset(),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.NONE,
            request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
            sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.UNKNOWN}),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset(
            {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI, OperationFrontendProjection.MCP}
        ),
    )


def resolve_invoice_remove_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require whole-profile ledger rights and a fresh commit fence."""
    if request.definition_id != INVOICE_REMOVE_OPERATION_DEFINITION_ID or not isinstance(
        request.payload, InvoiceRemoveRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    resolved = resolve_ledger_read_access(request, context, profile_id=request.payload.profile_id, periods=frozenset())
    policy = OperationAccessPolicy.model_validate(
        {**dict(resolved.policy), "actions": resolved.policy.actions | {AccessAction.COMMIT}}
    )
    return replace(resolved, policy=policy)


def build_invoice_remove_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Enroll exact request and result schemas at the canonical registry."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request", schema_version=1, model_type=InvoiceRemoveRequest
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result", schema_version=1, model_type=InvoiceRemoveResult
        ),
        access_resolver=resolve_invoice_remove_access,
    )
