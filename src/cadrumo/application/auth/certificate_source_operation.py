"""Canonical operation declarations, exact-profile access, and result projection for certificate sources."""

from __future__ import annotations

from typing import Any, cast
from uuid import UUID

from pydantic import BaseModel

from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationTerminalCondition,
    profile_operation_subject,
)
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
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationResultProjector,
)
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
from .certificate_source_contracts import (
    CERTIFICATE_SOURCE_CHECK_OPERATION_DEFINITION_ID,
    CERTIFICATE_SOURCE_LIST_OPERATION_DEFINITION_ID,
    CERTIFICATE_SOURCE_REGISTER_OPERATION_DEFINITION_ID,
    CERTIFICATE_SOURCE_REMOVE_OPERATION_DEFINITION_ID,
    CERTIFICATE_SOURCE_SELECT_OPERATION_DEFINITION_ID,
    CertificateSourceCheckProjection,
    CertificateSourceCheckRequest,
    CertificateSourceListProjection,
    CertificateSourceListRequest,
    CertificateSourceOperationRequest,
    CertificateSourceRegisterProjection,
    CertificateSourceRegisterRequest,
    CertificateSourceRemoveProjection,
    CertificateSourceRemoveRequest,
    CertificateSourceSelectProjection,
    CertificateSourceSelectRequest,
)
from .certificate_source_execution import (
    CERTIFICATE_SOURCE_OPERATION_SHAPES,
    CertificateSourceOperationExecutor,
    CertificateSourceOperationPorts,
    certificate_source_phase_code,
    validate_certificate_source_service_result,
)
from .operator_results import (
    CertificateSourceCheckReport,
    CertificateSourceListResult,
    CertificateSourceMutationResult,
)

_HUMAN_FRONTENDS = frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI})


_READ_ACTIONS = frozenset({AccessAction.SUBMIT, AccessAction.START, AccessAction.OBSERVE, AccessAction.RESULT})


_MUTATION_ACTIONS = _READ_ACTIONS | {AccessAction.COMMIT}


def _definition(
    definition_id: str,
    request_type: type[BaseModel],
    result_type: type[BaseModel],
    ports: CertificateSourceOperationPorts,
    *,
    mutation: bool,
) -> OperationDefinition:
    phases = (
        (
            certificate_source_phase_code(definition_id, "preflight"),
            certificate_source_phase_code(definition_id, "commit"),
            certificate_source_phase_code(definition_id, "settlement"),
        )
        if mutation
        else (
            certificate_source_phase_code(definition_id, "preflight"),
            certificate_source_phase_code(definition_id, "settlement"),
        )
    )
    return OperationDefinition(
        definition_id=definition_id,
        request_type=request_type,
        result_type=result_type,
        executor_factory=OperationExecutorFactory(
            request_type=request_type,
            executor_type=CertificateSourceOperationExecutor,
            build=lambda: CertificateSourceOperationExecutor(ports=ports, definition_id=definition_id),
        ),
        phase_codes=phases,
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
            permitted_effects=frozenset(
                {OperationEffect.NONE, OperationEffect.UNKNOWN, OperationEffect.UPDATED}
                if mutation
                else {OperationEffect.NONE, OperationEffect.UNKNOWN}
            ),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=_HUMAN_FRONTENDS,
    )


def build_certificate_source_register_definition(ports: CertificateSourceOperationPorts) -> OperationDefinition:
    """Declare profile-bound source registration with a fresh write authority."""
    return _definition(
        CERTIFICATE_SOURCE_REGISTER_OPERATION_DEFINITION_ID,
        CertificateSourceRegisterRequest,
        CertificateSourceMutationResult,
        ports,
        mutation=True,
    )


def build_certificate_source_list_definition(ports: CertificateSourceOperationPorts) -> OperationDefinition:
    """Declare profile-bound certificate-source inventory reading."""
    return _definition(
        CERTIFICATE_SOURCE_LIST_OPERATION_DEFINITION_ID,
        CertificateSourceListRequest,
        CertificateSourceListResult,
        ports,
        mutation=False,
    )


def build_certificate_source_select_definition(ports: CertificateSourceOperationPorts) -> OperationDefinition:
    """Declare profile-bound source selection with a fresh write authority."""
    return _definition(
        CERTIFICATE_SOURCE_SELECT_OPERATION_DEFINITION_ID,
        CertificateSourceSelectRequest,
        CertificateSourceMutationResult,
        ports,
        mutation=True,
    )


def build_certificate_source_remove_definition(ports: CertificateSourceOperationPorts) -> OperationDefinition:
    """Declare profile-bound source removal with idempotent effect facts."""
    return _definition(
        CERTIFICATE_SOURCE_REMOVE_OPERATION_DEFINITION_ID,
        CertificateSourceRemoveRequest,
        CertificateSourceMutationResult,
        ports,
        mutation=True,
    )


def build_certificate_source_check_definition(ports: CertificateSourceOperationPorts) -> OperationDefinition:
    """Declare profile-bound local health checking without mutation authority."""
    return _definition(
        CERTIFICATE_SOURCE_CHECK_OPERATION_DEFINITION_ID,
        CertificateSourceCheckRequest,
        CertificateSourceCheckReport,
        ports,
        mutation=False,
    )


def resolve_certificate_source_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require exact-profile human authority and fresh result disclosure."""
    payload, mutation = _require_certificate_source_access_request(request, context)
    actions = _require_certificate_source_action(context, mutation=mutation)
    disclosures = _certificate_source_disclosures(request, context)
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
            actions=actions,
            disclosures=disclosures,
            periods=frozenset(),
            allow_period_independent=True,
            backend=Availability.AVAILABLE,
            published_authority=context.published_authority,
            provider=Availability.NOT_REQUIRED,
            transaction_authority_required=False,
            requires_human=True,
        ),
    )


def _require_certificate_source_access_request(
    request: OperationRequest[BaseModel], context: OperationAccessContext
) -> tuple[CertificateSourceOperationRequest, bool]:
    payload = request.payload
    shape = CERTIFICATE_SOURCE_OPERATION_SHAPES.get(request.definition_id)
    if (
        shape is None
        or type(payload) is not shape[0]
        or not isinstance(
            payload,
            (
                CertificateSourceRegisterRequest,
                CertificateSourceListRequest,
                CertificateSourceSelectRequest,
                CertificateSourceRemoveRequest,
                CertificateSourceCheckRequest,
            ),
        )
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    profile_id = payload.profile_id
    if (
        request.definition_id != context.contract.definition_id
        or profile_id != context.profile_id
        or request.subject_ref != profile_operation_subject(str(profile_id))
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return payload, shape[2]


def _require_certificate_source_action(context: OperationAccessContext, *, mutation: bool) -> frozenset[AccessAction]:
    if context.frontend not in _HUMAN_FRONTENDS:
        raise ProfileAccessRefusedError(AccessDenialCode.FRONTEND_DENIED)
    actions = _MUTATION_ACTIONS if mutation else _READ_ACTIONS
    if context.action not in actions:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    return actions


def _certificate_source_disclosures(
    request: OperationRequest[BaseModel], context: OperationAccessContext
) -> frozenset[DisclosurePermission]:
    disclosures = frozenset[DisclosurePermission]()
    if context.action is AccessAction.OBSERVE:
        disclosure = DisclosurePermission(
            destination_id=context.destination_id,
            projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
            category=DisclosureCategory.OPERATION_METADATA,
        )
        disclosures = frozenset((cast(Any, disclosure),))
    elif context.action is AccessAction.RESULT:
        schema = context.contract.result_schema
        if schema is None or schema.schema_id != request.definition_id + ".result":
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        disclosure = DisclosurePermission(
            destination_id=context.destination_id,
            projection_id=schema.schema_id,
            category=DisclosureCategory.PROFILE_VALUES,
        )
        disclosures = frozenset((cast(Any, disclosure),))
    return disclosures


def _profile_from_receipt(receipt: OperationTerminalReceipt, *, definition_id: str) -> UUID:
    if (
        receipt.identity.definition_id != definition_id
        or receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.result_ref is None
        or receipt.refusal_ref is not None
        or receipt.refusal_detail_ref is not None
        or receipt.failure_error_code is not None
        or receipt.diagnostic_ref is not None
    ):
        raise ValueError("certificate source result contradicts its terminal receipt")
    subject = receipt.identity.subject_ref
    try:
        profile_id = UUID(subject.removeprefix("profile:"))
    except ValueError:
        raise ValueError("certificate source result has an invalid profile subject") from None
    if subject != profile_operation_subject(str(profile_id)):
        raise ValueError("certificate source result has an invalid profile subject")
    return profile_id


def project_certificate_source_register_result(
    result: BaseModel, receipt: OperationTerminalReceipt, /
) -> CertificateSourceRegisterProjection:
    """Project one successful source registration for its receipt profile."""
    private = validate_certificate_source_service_result(result, CertificateSourceMutationResult)
    if not private.name or not private.certificate_path or private.removed:
        raise ValueError("certificate source registration result is incomplete")
    if receipt.effect is not OperationEffect.UPDATED:
        raise ValueError("certificate source registration effect is inconsistent")
    return CertificateSourceRegisterProjection(
        profile_id=_profile_from_receipt(receipt, definition_id=CERTIFICATE_SOURCE_REGISTER_OPERATION_DEFINITION_ID),
        result=private,
    )


def project_certificate_source_list_result(
    result: BaseModel, receipt: OperationTerminalReceipt, /
) -> CertificateSourceListProjection:
    """Project a canonical source inventory for its receipt profile."""
    private = validate_certificate_source_service_result(result, CertificateSourceListResult)
    if receipt.effect is not OperationEffect.NONE:
        raise ValueError("certificate source list effect is inconsistent")
    return CertificateSourceListProjection(
        profile_id=_profile_from_receipt(receipt, definition_id=CERTIFICATE_SOURCE_LIST_OPERATION_DEFINITION_ID),
        result=private,
    )


def project_certificate_source_select_result(
    result: BaseModel, receipt: OperationTerminalReceipt, /
) -> CertificateSourceSelectProjection:
    """Project the newly selected source for its receipt profile."""
    private = validate_certificate_source_service_result(result, CertificateSourceMutationResult)
    if not private.name or not private.certificate_path or not private.active or private.removed:
        raise ValueError("certificate source selection result is incomplete")
    if receipt.effect is not OperationEffect.UPDATED:
        raise ValueError("certificate source selection effect is inconsistent")
    return CertificateSourceSelectProjection(
        profile_id=_profile_from_receipt(receipt, definition_id=CERTIFICATE_SOURCE_SELECT_OPERATION_DEFINITION_ID),
        result=private,
    )


def project_certificate_source_remove_result(
    result: BaseModel, receipt: OperationTerminalReceipt, /
) -> CertificateSourceRemoveProjection:
    """Project a source removal, preserving its actual no-op or update effect."""
    private = validate_certificate_source_service_result(result, CertificateSourceMutationResult)
    expected_effect = OperationEffect.UPDATED if private.removed else OperationEffect.NONE
    if not private.name or receipt.effect is not expected_effect:
        raise ValueError("certificate source removal result contradicts its effect")
    return CertificateSourceRemoveProjection(
        profile_id=_profile_from_receipt(receipt, definition_id=CERTIFICATE_SOURCE_REMOVE_OPERATION_DEFINITION_ID),
        result=private,
    )


def project_certificate_source_check_result(
    result: BaseModel, receipt: OperationTerminalReceipt, /
) -> CertificateSourceCheckProjection:
    """Project local health facts for the profile identified by the receipt."""
    private = validate_certificate_source_service_result(result, CertificateSourceCheckReport)
    if receipt.effect is not OperationEffect.NONE:
        raise ValueError("certificate source check effect is inconsistent")
    return CertificateSourceCheckProjection(
        profile_id=_profile_from_receipt(receipt, definition_id=CERTIFICATE_SOURCE_CHECK_OPERATION_DEFINITION_ID),
        result=private,
    )


def _registration(
    definition: OperationDefinition,
    *,
    projection_type: type[BaseModel],
    projector: OperationResultProjector,
) -> OperationPublicDefinitionRegistrationV1:
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=projection_type,
        result_projector=projector,
        access_resolver=resolve_certificate_source_access,
    )


def build_certificate_source_register_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind registration request and exact-profile result contracts."""
    return _registration(
        definition,
        projection_type=CertificateSourceRegisterProjection,
        projector=project_certificate_source_register_result,
    )


def build_certificate_source_list_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind inventory request and exact-profile result contracts."""
    return _registration(
        definition,
        projection_type=CertificateSourceListProjection,
        projector=project_certificate_source_list_result,
    )


def build_certificate_source_select_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind selection request and exact-profile result contracts."""
    return _registration(
        definition,
        projection_type=CertificateSourceSelectProjection,
        projector=project_certificate_source_select_result,
    )


def build_certificate_source_remove_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind removal request and exact-profile result contracts."""
    return _registration(
        definition,
        projection_type=CertificateSourceRemoveProjection,
        projector=project_certificate_source_remove_result,
    )


def build_certificate_source_check_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind health-check request and exact-profile result contracts."""
    return _registration(
        definition,
        projection_type=CertificateSourceCheckProjection,
        projector=project_certificate_source_check_result,
    )
