"""Canonical wizard and bulk invoice import under exact-profile worker authority."""

from __future__ import annotations

from pydantic import BaseModel

from ..ledger.read_access import resolve_ledger_read_access
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess, with_commit_action
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_PARTIAL_UPDATE_CAPABILITIES
from ..operations.execution_actor import OperationExecutionCallerReader
from ..operations.models import OperationRequest
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.registry import OperationPublicDefinitionRegistrationV1
from ..operations.subject_reference import OperationSubjectReferenceV1
from ..user_profile.access_contracts import (
    AccessDenialCode,
)
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


def _definition(
    definition_id: str,
    factory: InvoiceIntakePortsFactory,
    *,
    execution_caller_reader: OperationExecutionCallerReader | None = None,
) -> OperationDefinition:
    request_type = INVOICE_INTAKE_REQUEST_TYPES[definition_id]
    return build_single_phase_definition(
        definition_id=definition_id,
        request_type=request_type,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=InvoiceIntakeExecutionResult,
        executor_type=InvoiceIntakeExecutor,
        build=lambda: InvoiceIntakeExecutor(factory, execution_caller_reader=execution_caller_reader),
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_PARTIAL_UPDATE_CAPABILITIES,
        refusal_detail_codes=frozenset({INVOICE_WIZARD_VALIDATION_REFUSAL_CODE})
        if definition_id == INVOICE_WIZARD_OPERATION_DEFINITION_ID
        else frozenset(),
    )


def build_invoice_import_definition(factory: InvoiceIntakePortsFactory) -> OperationDefinition:
    """Enroll the existing human invoice-book import."""
    return _definition(
        INVOICE_IMPORT_OPERATION_DEFINITION_ID,
        factory,
    )


def build_invoice_wizard_definition(
    factory: InvoiceIntakePortsFactory,
    *,
    execution_caller_reader: OperationExecutionCallerReader | None = None,
) -> OperationDefinition:
    """Enroll the all-fields typed invoice entry without substituting add.

    Every field is stated up front and validated here, so an agent may make the
    entry as a person does. ``execution_caller_reader`` names the frontend and
    session that admitted an execution, so an agent's entry is recorded under
    its session's label.
    """
    return _definition(
        INVOICE_WIZARD_OPERATION_DEFINITION_ID,
        factory,
        execution_caller_reader=execution_caller_reader,
    )


def resolve_invoice_intake_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """The existing catalogue reads require whole-profile rights and actual COMMIT."""
    if type(request.payload) is not INVOICE_INTAKE_REQUEST_TYPES.get(request.definition_id) or not isinstance(
        request.payload, (InvoiceImportRequest, InvoiceWizardRequest)
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    resolved = resolve_ledger_read_access(request, context, profile_id=request.payload.profile_id, periods=frozenset())
    return with_commit_action(resolved)


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
