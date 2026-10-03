"""Registered exact-profile operation for received-invoice withholding capture."""

from __future__ import annotations

from pydantic import BaseModel

from ..ledger.read_access import resolve_ledger_commit_access
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES
from ..operations.models import OperationRequest
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.profile_guard import require_access_request_profile_payload
from ..operations.registry import (
    ALL_OPERATION_FRONTENDS,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from .invoice_withholding_capture_contracts import (
    MODELO_INVOICE_WITHHOLDING_CAPTURE_OPERATION_DEFINITION_ID,
    MODELO_INVOICE_WITHHOLDING_CAPTURE_PHASES,
    MODELO_INVOICE_WITHHOLDING_CAPTURE_REFUSAL_CODES,
    ModeloInvoiceWithholdingCapturePortsFactory,
    ModeloInvoiceWithholdingCaptureProjection,
    ModeloInvoiceWithholdingCaptureReport,
    ModeloInvoiceWithholdingCaptureRequest,
)
from .invoice_withholding_capture_execution import (
    ModeloInvoiceWithholdingCaptureExecutor,
)
from .invoice_withholding_capture_projection import (
    project_modelo_invoice_withholding_capture_result,
)


def build_modelo_invoice_withholding_capture_definition(
    factory: ModeloInvoiceWithholdingCapturePortsFactory,
) -> OperationDefinition:
    """Declare secure storage, honest effects, and exact-profile mutation custody."""
    return OperationDefinition(
        definition_id=MODELO_INVOICE_WITHHOLDING_CAPTURE_OPERATION_DEFINITION_ID,
        request_type=ModeloInvoiceWithholdingCaptureRequest,
        result_type=ModeloInvoiceWithholdingCaptureReport,
        executor_factory=OperationExecutorFactory(
            request_type=ModeloInvoiceWithholdingCaptureRequest,
            executor_type=ModeloInvoiceWithholdingCaptureExecutor,
            build=lambda: ModeloInvoiceWithholdingCaptureExecutor(factory),
        ),
        phase_codes=MODELO_INVOICE_WITHHOLDING_CAPTURE_PHASES,
        interaction_kinds=frozenset(),
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES,
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=ALL_OPERATION_FRONTENDS,
        refusal_detail_codes=MODELO_INVOICE_WITHHOLDING_CAPTURE_REFUSAL_CODES,
    )


def resolve_modelo_invoice_withholding_capture_access(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    /,
) -> ResolvedOperationAccess:
    """Bind exact profile and all-period invoice-catalogue rights, including fresh COMMIT."""
    payload = require_access_request_profile_payload(
        request,
        definition_id=MODELO_INVOICE_WITHHOLDING_CAPTURE_OPERATION_DEFINITION_ID,
        payload_type=ModeloInvoiceWithholdingCaptureRequest,
        access_profile_id=context.profile_id,
    )
    return resolve_ledger_commit_access(request, context, profile_id=payload.profile_id, periods=frozenset())


def build_modelo_invoice_withholding_capture_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the hidden financial request to its closed safe summary projection."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request",
            schema_version=1,
            model_type=ModeloInvoiceWithholdingCaptureRequest,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result",
            schema_version=2,
            model_type=ModeloInvoiceWithholdingCaptureProjection,
        ),
        result_projector=project_modelo_invoice_withholding_capture_result,
        access_resolver=resolve_modelo_invoice_withholding_capture_access,
    )


__all__ = [
    "build_modelo_invoice_withholding_capture_definition",
    "build_modelo_invoice_withholding_capture_registration",
    "resolve_modelo_invoice_withholding_capture_access",
]
