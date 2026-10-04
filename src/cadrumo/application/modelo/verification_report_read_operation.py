"""Register exact-profile reads of complete persisted verification reports."""

from __future__ import annotations

from functools import partial

from pydantic import BaseModel

from ...core.operations import profile_operation_subject
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES
from ..operations.models import OperationRequest
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.read_capture import capture_read_result
from ..operations.registry import OperationFrontendProjection, OperationPublicDefinitionRegistrationV1
from ..user_profile.access_contracts import (
    AccessDenialCode,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .verification_report_read_access import resolve_verification_report_read_access
from .verification_report_read_capture import capture_verification_report_list, capture_verification_report_view
from .verification_report_read_contracts import (
    MODELO_VERIFICATION_REPORT_LIST_OPERATION_DEFINITION_ID,
    MODELO_VERIFICATION_REPORT_VIEW_OPERATION_DEFINITION_ID,
    ModeloVerificationReportListRequest,
    ModeloVerificationReportViewRequest,
)
from .verification_report_read_projection import (
    ModeloVerificationReportListProjection,
    ModeloVerificationReportViewProjection,
)
from .verification_repository_ports import VerificationRepositoryBundleFactory


class ModeloVerificationReportListExecutor:
    """Read complete verification history inside worker-owned profile custody."""

    def __init__(self, factory: VerificationRepositoryBundleFactory) -> None:
        """Retain the composition-supplied exact-profile repository factory."""
        self._factory = factory

    async def execute(
        self,
        request: OperationRequest[ModeloVerificationReportListRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Capture a filtered list into encrypted result custody."""
        payload = request.payload
        subject = profile_operation_subject(str(payload.profile_id))
        if (
            request.definition_id != MODELO_VERIFICATION_REPORT_LIST_OPERATION_DEFINITION_ID
            or request.subject_ref != subject
            or context.identity.definition_id != request.definition_id
            or context.identity.subject_ref != subject
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase(MODELO_VERIFICATION_REPORT_LIST_OPERATION_DEFINITION_ID)

        return await capture_read_result(
            context,
            partial(capture_verification_report_list, payload, self._factory, operation=context.authority_operation),
            task_name="modelo-verification-report-list",
        )


class ModeloVerificationReportViewExecutor:
    """Read one verification report inside worker-owned profile custody."""

    def __init__(self, factory: VerificationRepositoryBundleFactory) -> None:
        """Retain the composition-supplied exact-profile repository factory."""
        self._factory = factory

    async def execute(
        self,
        request: OperationRequest[ModeloVerificationReportViewRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Capture one report into encrypted result custody."""
        payload = request.payload
        subject = profile_operation_subject(str(payload.profile_id))
        if (
            request.definition_id != MODELO_VERIFICATION_REPORT_VIEW_OPERATION_DEFINITION_ID
            or request.subject_ref != subject
            or context.identity.definition_id != request.definition_id
            or context.identity.subject_ref != subject
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase(MODELO_VERIFICATION_REPORT_VIEW_OPERATION_DEFINITION_ID)

        return await capture_read_result(
            context,
            partial(capture_verification_report_view, payload, self._factory, operation=context.authority_operation),
            task_name="modelo-verification-report-view",
        )


def build_modelo_verification_report_list_definition(
    factory: VerificationRepositoryBundleFactory,
) -> OperationDefinition:
    """Declare a credential-free, recorded, nonmutating report-history read."""
    return _build_read_definition(
        definition_id=MODELO_VERIFICATION_REPORT_LIST_OPERATION_DEFINITION_ID,
        request_type=ModeloVerificationReportListRequest,
        result_type=ModeloVerificationReportListProjection,
        executor_type=ModeloVerificationReportListExecutor,
        factory=factory,
    )


def build_modelo_verification_report_view_definition(
    factory: VerificationRepositoryBundleFactory,
) -> OperationDefinition:
    """Declare a credential-free, recorded, nonmutating report view."""
    return _build_read_definition(
        definition_id=MODELO_VERIFICATION_REPORT_VIEW_OPERATION_DEFINITION_ID,
        request_type=ModeloVerificationReportViewRequest,
        result_type=ModeloVerificationReportViewProjection,
        executor_type=ModeloVerificationReportViewExecutor,
        factory=factory,
    )


def _build_read_definition(
    *,
    definition_id: str,
    request_type: type[BaseModel],
    result_type: type[BaseModel],
    executor_type: type[ModeloVerificationReportListExecutor] | type[ModeloVerificationReportViewExecutor],
    factory: VerificationRepositoryBundleFactory,
) -> OperationDefinition:
    """Build the shared read-only operation capability contract."""
    return build_single_phase_definition(
        definition_id=definition_id,
        request_type=request_type,
        result_type=result_type,
        executor_type=executor_type,
        build=lambda: executor_type(factory),
        capabilities=RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI}),
    )


def build_modelo_verification_report_list_registration(
    definition: OperationDefinition,
    factory: VerificationRepositoryBundleFactory,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the complete list schema and exact-period access resolver."""

    def resolve(request: OperationRequest[BaseModel], context: OperationAccessContext, /) -> ResolvedOperationAccess:
        return resolve_verification_report_read_access(
            request,
            context,
            definition_id=MODELO_VERIFICATION_REPORT_LIST_OPERATION_DEFINITION_ID,
            payload_type=ModeloVerificationReportListRequest,
            factory=factory,
        )

    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=ModeloVerificationReportListProjection,
        access_resolver=resolve,
    )


def build_modelo_verification_report_view_registration(
    definition: OperationDefinition,
    factory: VerificationRepositoryBundleFactory,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the full view schema and report-derived period access resolver."""

    def resolve(request: OperationRequest[BaseModel], context: OperationAccessContext, /) -> ResolvedOperationAccess:
        return resolve_verification_report_read_access(
            request,
            context,
            definition_id=MODELO_VERIFICATION_REPORT_VIEW_OPERATION_DEFINITION_ID,
            payload_type=ModeloVerificationReportViewRequest,
            factory=factory,
        )

    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=ModeloVerificationReportViewProjection,
        access_resolver=resolve,
    )
