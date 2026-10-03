"""Canonical wizard and bulk invoice import under exact-profile worker authority."""

from __future__ import annotations

from dataclasses import replace

from pydantic import BaseModel

from ..ledger.read_access import resolve_ledger_read_access
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_PARTIAL_UPDATE_CAPABILITIES
from ..operations.models import OperationRequest
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
)
from ..user_profile.access_contracts import AccessAction, AccessDenialCode, OperationAccessPolicy
from ..user_profile.access_errors import ProfileAccessRefusedError
from .catalogue_intake_contracts import (
    INVOICE_IMPORT_OPERATION_DEFINITION_ID,
    INVOICE_INTAKE_PROJECTION_TYPES,
    INVOICE_INTAKE_REQUEST_TYPES,
    INVOICE_WIZARD_OPERATION_DEFINITION_ID,
    InvoiceImportRequest,
    InvoiceIntakeExecutionResult,
    InvoiceWizardRequest,
)
from .catalogue_intake_executor import InvoiceIntakeExecutor
from .catalogue_intake_operation_ports import InvoiceIntakePortsFactory
from .catalogue_intake_projection import project_invoice_intake_result
from .catalogue_intake_refusal import (
    INVOICE_WIZARD_VALIDATION_REFUSAL_CODE,
)


def _definition(definition_id: str, factory: InvoiceIntakePortsFactory) -> OperationDefinition:
    request_type = INVOICE_INTAKE_REQUEST_TYPES[definition_id]
    return OperationDefinition(
        definition_id=definition_id,
        request_type=request_type,
        result_type=InvoiceIntakeExecutionResult,
        executor_factory=OperationExecutorFactory(
            request_type=request_type, executor_type=InvoiceIntakeExecutor, build=lambda: InvoiceIntakeExecutor(factory)
        ),
        phase_codes=(definition_id,),
        interaction_kinds=frozenset(),
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_PARTIAL_UPDATE_CAPABILITIES,
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI}),
        refusal_detail_codes=(
            frozenset({INVOICE_WIZARD_VALIDATION_REFUSAL_CODE})
            if definition_id == INVOICE_WIZARD_OPERATION_DEFINITION_ID
            else frozenset()
        ),
    )


def build_invoice_import_definition(factory: InvoiceIntakePortsFactory) -> OperationDefinition:
    """Enroll the existing human invoice-book import."""
    return _definition(INVOICE_IMPORT_OPERATION_DEFINITION_ID, factory)


def build_invoice_wizard_definition(factory: InvoiceIntakePortsFactory) -> OperationDefinition:
    """Enroll the existing all-fields human wizard without substituting add."""
    return _definition(INVOICE_WIZARD_OPERATION_DEFINITION_ID, factory)


def resolve_invoice_intake_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """The existing catalogue reads require whole-profile rights and actual COMMIT."""
    if type(request.payload) is not INVOICE_INTAKE_REQUEST_TYPES.get(request.definition_id) or not isinstance(
        request.payload, (InvoiceImportRequest, InvoiceWizardRequest)
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    resolved = resolve_ledger_read_access(request, context, profile_id=request.payload.profile_id, periods=frozenset())
    return replace(
        resolved,
        policy=OperationAccessPolicy.model_validate(
            {**dict(resolved.policy), "actions": resolved.policy.actions | {AccessAction.COMMIT}}
        ),
    )


def build_invoice_intake_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Compile both closed schemas and bind truthful receipt disclosure."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=INVOICE_INTAKE_PROJECTION_TYPES[definition.definition_id],
        result_projector=project_invoice_intake_result,
        access_resolver=resolve_invoice_intake_access,
    )


__all__ = [
    "build_invoice_import_definition",
    "build_invoice_intake_registration",
    "build_invoice_wizard_definition",
    "resolve_invoice_intake_access",
]
