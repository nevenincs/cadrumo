"""Resolve exact profile and period admission for verification report reads."""

from __future__ import annotations

from pydantic import BaseModel

from ...core.period import Period
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.modelos.calculation_revision import CalculationRevisionCatalogue
from ...domain.modelos.work_unit import WorkUnitCatalogue
from ..calculations.verification_report_gate import require_verification_report_coordinates_current
from ..operations.access_resolution import (
    ADMISSION_REPLAY_ACTIONS,
    LIFECYCLE_SELECTED_PERIODS_REGISTERED_RESULT_TAX_VALUES_ACCESS,
    LIFECYCLE_WHOLE_PROFILE_REGISTERED_RESULT_TAX_VALUES_ACCESS,
    OperationAccessContext,
    ResolvedOperationAccess,
    bind_operation_access_profile,
    require_period_independent_admission,
    require_single_period_admission,
)
from ..operations.models import OperationRequest
from ..operations.profile_guard import require_access_request_profile_payload
from ..user_profile.access_contracts import (
    AccessDenialCode,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .verification_report_read_capture import (
    load_verification_report_read_scope,
    verification_calculation_revision_period,
    verification_report_period,
)
from .verification_report_read_contracts import ModeloVerificationReportListRequest, ModeloVerificationReportViewRequest
from .verification_repository_ports import VerificationRepositoryBundle, VerificationRepositoryBundleFactory


def _selected_report_read_period(
    payload: ModeloVerificationReportListRequest | ModeloVerificationReportViewRequest,
    profile_id: str,
    bundle: VerificationRepositoryBundle,
    calculations: CalculationRevisionCatalogue,
    work_units: WorkUnitCatalogue,
    *,
    operation: PinnedAuthorityOperation,
) -> Period:
    if isinstance(payload, ModeloVerificationReportListRequest):
        if payload.calculation_revision_id is None:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        return verification_calculation_revision_period(
            payload.calculation_revision_id,
            profile_id=profile_id,
            calculation_catalogue=calculations,
            work_units=work_units,
            operation=operation,
        )
    catalogue = require_verification_report_coordinates_current(
        bundle.verification.load(operation=operation), operation=operation
    )
    report = catalogue.get(payload.verification_report_id)
    if report is None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    return verification_report_period(
        report,
        profile_id=profile_id,
        calculation_catalogue=calculations,
        work_units=work_units,
        operation=operation,
    )


def resolve_verification_report_read_access(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    *,
    definition_id: str,
    payload_type: type[ModeloVerificationReportListRequest] | type[ModeloVerificationReportViewRequest],
    factory: VerificationRepositoryBundleFactory,
) -> ResolvedOperationAccess:
    """Resolve the profile and exact report period for access and result reads."""
    payload = require_access_request_profile_payload(
        request,
        definition_id=definition_id,
        payload_type=payload_type,
        access_profile_id=context.profile_id,
    )
    profile_id = str(payload.profile_id)

    independent = isinstance(payload, ModeloVerificationReportListRequest) and payload.calculation_revision_id is None
    admitted = context.admitted_request
    if admitted is not None and context.action in ADMISSION_REPLAY_ACTIONS:
        periods = frozenset[Period]()
        if independent:
            require_period_independent_admission(
                admitted, profile_id=context.profile_id, definition_id=request.definition_id
            )
        else:
            periods = require_single_period_admission(
                admitted, profile_id=context.profile_id, definition_id=request.definition_id
            )
    elif independent:
        periods = frozenset[Period]()
    else:
        if context.authority_operation is None:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        bundle, calculations, work_units = load_verification_report_read_scope(
            factory, profile_id, operation=context.authority_operation
        )
        period = _selected_report_read_period(
            payload, profile_id, bundle, calculations, work_units, operation=context.authority_operation
        )
        periods = frozenset({period})

    return bind_operation_access_profile(
        context,
        LIFECYCLE_WHOLE_PROFILE_REGISTERED_RESULT_TAX_VALUES_ACCESS
        if independent
        else LIFECYCLE_SELECTED_PERIODS_REGISTERED_RESULT_TAX_VALUES_ACCESS,
        profile_id=context.profile_id,
        definition_id=request.definition_id,
        periods=periods,
    )
