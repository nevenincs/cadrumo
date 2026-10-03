"""Resolve revision mutations against the execution profile's persisted scope."""

from __future__ import annotations

from pydantic import BaseModel

from ..operations.access_port import OperationAccessResolver
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from ..operations.models import OperationRequest
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
from .operation_definitions import (
    MODELO_EXPORT_OPERATION_DEFINITION_ID,
    MODELO_WORK_AMEND_OPERATION_DEFINITION_ID,
    MODELO_WORK_FILE_OPERATION_DEFINITION_ID,
    MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID,
    ModeloExportRequest,
    ModeloWorkAmendRequest,
    ModeloWorkFileRequest,
    ModeloWorkVerifyRequest,
)
from .review_package_operation import (
    MODELO_REVIEW_PACKAGE_BUILD_OPERATION_DEFINITION_ID,
    ModeloReviewPackageBuildRequest,
)
from .revision_snapshot_operation import (
    MODELO_WORK_REVISION_SNAPSHOT_OPERATION_DEFINITION_ID,
    ModeloWorkRevisionSnapshotRequest,
)
from .verification_repository_ports import VerificationRepositoryBundleFactory


def compose_modelo_revision_access(factory: VerificationRepositoryBundleFactory) -> OperationAccessResolver:
    """Bind exact revision and work-unit reads without inferring scope from IDs."""

    def resolve(request: OperationRequest[BaseModel], context: OperationAccessContext, /) -> ResolvedOperationAccess:
        payload = request.payload
        filing_id = None
        if request.definition_id == MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID and isinstance(
            payload, ModeloWorkVerifyRequest
        ):
            revision_id = payload.calculation_revision_id
        elif request.definition_id == MODELO_WORK_FILE_OPERATION_DEFINITION_ID and isinstance(
            payload, ModeloWorkFileRequest
        ):
            revision_id = payload.approval.calculation_revision_id
        elif request.definition_id == MODELO_WORK_AMEND_OPERATION_DEFINITION_ID and isinstance(
            payload, ModeloWorkAmendRequest
        ):
            filing_id = payload.baseline.from_filing_record_id
            revision_id = None
        elif request.definition_id == MODELO_EXPORT_OPERATION_DEFINITION_ID and isinstance(
            payload, ModeloExportRequest
        ):
            revision_id = payload.calculation_revision_id
        elif (
            request.definition_id == MODELO_REVIEW_PACKAGE_BUILD_OPERATION_DEFINITION_ID
            and isinstance(payload, ModeloReviewPackageBuildRequest)
        ) or (
            request.definition_id == MODELO_WORK_REVISION_SNAPSHOT_OPERATION_DEFINITION_ID
            and isinstance(payload, ModeloWorkRevisionSnapshotRequest)
        ):
            if payload.profile_id != context.profile_id:
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            revision_id = payload.calculation_revision_id
        else:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        admitted = context.admitted_request
        if admitted is not None and context.action in {
            AccessAction.OBSERVE,
            AccessAction.RESULT,
            AccessAction.CANCEL,
            AccessAction.DETACH,
        }:
            if (
                admitted.profile_id != context.profile_id
                or admitted.definition_id != request.definition_id
                or admitted.action is not AccessAction.SUBMIT
                or admitted.period_independent
                or len(admitted.periods) != 1
            ):
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
            periods = admitted.periods
        else:
            if context.authority_operation is None:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
            repositories = factory(str(context.profile_id), operation=context.authority_operation)
            if repositories.calculation.bucket_id != str(context.profile_id) or repositories.work_unit.bucket_id != str(
                context.profile_id
            ):
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            filing = None
            if filing_id is not None:
                if repositories.filing.bucket_id != str(context.profile_id):
                    raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
                filing = repositories.filing.load().get(filing_id)
                if filing is None:
                    raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
                if filing.bucket_id != str(context.profile_id):
                    raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
                revision_id = filing.calculation_revision_id
            if revision_id is None:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
            revision = repositories.calculation.load(operation=context.authority_operation).get(revision_id)
            if revision is None or request.subject_ref != revision.work_unit_id:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
            unit = repositories.work_unit.load().get(revision.work_unit_id)
            if unit is None:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
            if unit.bucket_id != str(context.profile_id):
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            if filing is not None and (
                filing.work_unit_id != unit.work_unit_id
                or filing.modelo != unit.modelo
                or filing.filing_year != unit.filing_year
                or filing.period != unit.period
            ):
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
            periods = frozenset({unit.period})
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
                category=DisclosureCategory.TAX_VALUES,
            )
        return ResolvedOperationAccess(
            request=OperationAccessRequest(
                profile_id=context.profile_id,
                definition_id=request.definition_id,
                action=context.action,
                frontend=context.frontend,
                periods=periods,
                period_independent=False,
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
                        AccessAction.COMMIT,
                        AccessAction.OBSERVE,
                        AccessAction.RESULT,
                        AccessAction.CANCEL,
                        AccessAction.DETACH,
                    }
                )
                - (
                    frozenset({AccessAction.COMMIT})
                    if request.definition_id == MODELO_WORK_REVISION_SNAPSHOT_OPERATION_DEFINITION_ID
                    else frozenset()
                ),
                disclosures=frozenset((disclosure,)) if disclosure is not None else frozenset(),
                periods=periods,
                allow_period_independent=False,
                backend=Availability.AVAILABLE,
                published_authority=context.published_authority,
                provider=Availability.NOT_REQUIRED,
                transaction_authority_required=False,
            ),
        )

    return resolve
