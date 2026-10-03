"""Registered, profile-bound selection of a persisted modelo calculation revision."""

from __future__ import annotations

from functools import partial
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.filing_year import FilingYear
from ...core.identity.hex_ids import CalculationRevisionId, VerificationReportId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import profile_operation_subject
from ...core.period import Period
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.ids import RevisionId
from ...domain.modelos.calculation_revision import CalculationRevision, CalculationRevisionState
from ...domain.modelos.filing_record import AeatConfirmationState, FilingOrigin, ModeloRecord
from ...domain.modelos.verification_report import VerificationReport
from ...domain.modelos.work_unit import WorkUnit
from ..calculations.verification_report_gate import require_verification_report_coordinates_current
from ..operations.access_resolution import (
    LIFECYCLE_SELECTED_PERIODS_REGISTERED_RESULT_TAX_VALUES_ACCESS,
    OperationAccessContext,
    ResolvedOperationAccess,
    bind_replayed_or_fresh_single_period_access,
)
from ..operations.capabilities import RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES
from ..operations.models import CredentialFreeOperationRequest, OperationRequest
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_access_request_profile_payload
from ..operations.public_period import PublicPeriod
from ..operations.read_capture import capture_read_result
from ..operations.registry import OperationFrontendProjection, OperationPublicDefinitionRegistrationV1
from ..user_profile.access_contracts import (
    AccessDenialCode,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .metadata_projection import ModeloWorkMetadataSnapshot
from .selectors import (
    ModeloCalculationRevisionDefault,
    ModeloCalculationRevisionSelector,
    ModeloCalculationRevisionSelectorError,
    resolve_modelo_calculation_revision_pick,
)
from .verification_repository_ports import VerificationRepositoryBundle, VerificationRepositoryBundleFactory
from .work_addressing import (
    ModeloWorkAddressNotFoundError,
    ModeloWorkPeriodTokenError,
    ModeloWorkSelectorError,
    resolve_modelo_work_unit_for_operator_target,
)
from .work_lifecycle import RevisionParentOperation, require_revision_parent_active

MODELO_WORK_REVISION_OPERATION_DEFINITION_ID = "modelo.work.revision"


class ModeloWorkRevisionRequest(CredentialFreeOperationRequest):
    """Exact or natural work address and canonical calculation-revision pick."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    calculation_revision_id: CalculationRevisionId | None = None
    work_unit_id: Annotated[str, Field(pattern=r"^(?:[0-9a-f]{12}|[0-9a-f]{64})$")] | None = None
    modelo: Annotated[str, Field(min_length=1, max_length=16)] | None = None
    year: FilingYear | None = None
    period: PublicPeriod | None = None
    revision: RevisionId | None = None
    selector: ModeloCalculationRevisionSelector = ModeloCalculationRevisionSelector.CURRENT
    default_for: ModeloCalculationRevisionDefault | None = None


class ModeloWorkRevisionProjection(BaseModel):
    """Bounded selection and existing granting report, without financial values."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result_version: Literal[1] = 1
    profile_id: UUID
    unit: ModeloWorkMetadataSnapshot
    calculation_revision_id: CalculationRevisionId
    calculation_state: CalculationRevisionState
    verification_report_id: VerificationReportId | None
    granted_verificado_completo: bool

    @model_validator(mode="after")
    def _bound_result(self) -> ModeloWorkRevisionProjection:
        if self.unit.bucket_id != str(self.profile_id):
            raise ValueError("revision projection profile does not match its work unit")
        if (self.verification_report_id is not None) != self.granted_verificado_completo:
            raise ValueError("revision projection report and grant must agree")
        return self


def _selects_exact_calculation(payload: ModeloWorkRevisionRequest) -> bool:
    return (
        payload.work_unit_id is None
        and payload.modelo is None
        and payload.year is None
        and payload.period is None
        and payload.revision is None
    )


def _unit(
    payload: ModeloWorkRevisionRequest, bundle: VerificationRepositoryBundle, *, operation: PinnedAuthorityOperation
) -> WorkUnit:
    """Resolve the persisted unit before interpreting its revision selector."""
    profile_id = str(payload.profile_id)
    if bundle.work_unit.bucket_id != profile_id or bundle.calculation.bucket_id != profile_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    catalogue = bundle.work_unit.load()
    if payload.calculation_revision_id is not None and _selects_exact_calculation(payload):
        revision = bundle.calculation.load(operation=operation).get(payload.calculation_revision_id)
        if revision is None:
            # The established verify/file positional-id route also accepts an
            # exact work-unit id and then selects its current calculation.
            unit = catalogue.get(payload.calculation_revision_id) if payload.default_for in {"verify", "file"} else None
        else:
            unit = catalogue.get(revision.work_unit_id)
        if unit is None:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    else:
        unit = resolve_modelo_work_unit_for_operator_target(
            work_unit_id=payload.work_unit_id,
            modelo=payload.modelo,
            year=payload.year,
            period=payload.period.to_period() if payload.period is not None else None,
            registry_revision_id=payload.revision,
            bucket_id=profile_id,
            catalogue=catalogue,
            resolved_bucket_id=profile_id,
            operation=operation,
        )
    if unit.bucket_id != profile_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return unit


def _external_record_coordinates_match(
    record: ModeloRecord, revision: CalculationRevision, unit: WorkUnit, profile_id: UUID
) -> bool:
    return (
        record.bucket_id == str(profile_id)
        and record.work_unit_id == unit.work_unit_id
        and record.calculation_revision_id == revision.calculation_revision_id
        and record.modelo == unit.modelo
        and record.filing_year == unit.filing_year
        and record.period == unit.period
    )


def _confirmed_external_revision_record(
    record: ModeloRecord, revision: CalculationRevision, unit: WorkUnit, profile_id: UUID
) -> bool:
    return (
        _external_record_coordinates_match(record, revision, unit, profile_id)
        and record.origin is FilingOrigin.AEAT
        and record.confirmation is AeatConfirmationState.CONFIRMADA
        and record.external_evidence is not None
        and record.filed_at == revision.filed_at
        and record.filed_by == revision.filed_by
    )


def _filed_external_without_report(
    revision: CalculationRevision,
    unit: WorkUnit,
    bundle: VerificationRepositoryBundle,
    *,
    profile_id: UUID,
) -> bool:
    """Recognize a co-committed AEAT import by its exact filing receipt."""
    if (
        revision.amendment_identity is not None
        or revision.state not in {CalculationRevisionState.PRESENTADO, CalculationRevisionState.PRESENTADO_SUPERSEDIDO}
        or revision.verified_at is None
        or revision.filed_at is None
        or revision.filed_by is None
    ):
        return False
    if bundle.filing.bucket_id != str(profile_id):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    matching = tuple(
        record
        for record in bundle.filing.load().values()
        if _confirmed_external_revision_record(record, revision, unit, profile_id)
    )
    return len(matching) == 1


def _filed_amendment_without_grant(revision: CalculationRevision, granting: tuple[VerificationReport, ...]) -> bool:
    return (
        revision.amendment_identity is not None
        and revision.state in {CalculationRevisionState.PRESENTADO, CalculationRevisionState.PRESENTADO_SUPERSEDIDO}
        and revision.verified_at is not None
        and not granting
    )


def _require_selected_revision_grant_evidence(
    revision: CalculationRevision,
    unit: WorkUnit,
    bundle: VerificationRepositoryBundle,
    profile_id: UUID,
    granting: tuple[VerificationReport, ...],
) -> None:
    # The amendment transaction verifies and files its own new revision without
    # creating a standalone VerificationReport. Its recorded amendment identity
    # and filed state distinguish that path from a broken ordinary verification.
    filed_amendment_without_report = _filed_amendment_without_grant(revision, granting)
    filed_external_without_report = (
        not granting
        and not filed_amendment_without_report
        and _filed_external_without_report(revision, unit, bundle, profile_id=profile_id)
    )
    if len(granting) > 1 or (
        (revision.verified_at is not None) != bool(granting)
        and not filed_amendment_without_report
        and not filed_external_without_report
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)


def _capture(
    payload: ModeloWorkRevisionRequest, bundle: VerificationRepositoryBundle, operation: OperationExecutorContext
) -> ModeloWorkRevisionProjection:
    unit = _unit(payload, bundle, operation=operation.authority_operation)
    selected_id = payload.calculation_revision_id
    if (
        selected_id is not None
        and selected_id == unit.work_unit_id
        and bundle.calculation.load(operation=operation.authority_operation).get(selected_id) is None
    ):
        selected_id = None
    selection = resolve_modelo_calculation_revision_pick(
        unit,
        selector=payload.selector,
        calculation_revision_id=selected_id,
        default_for=payload.default_for,
        calculation_repository=bundle.calculation,
        operation=operation.authority_operation,
    )
    revision = selection.revision
    if payload.default_for in {"verify", "file"}:
        require_revision_parent_active(
            work_unit=unit,
            calculation_revision_id=revision.calculation_revision_id,
            operation=RevisionParentOperation.VERIFY
            if payload.default_for == "verify"
            else RevisionParentOperation.FILE,
        )
    if bundle.verification.bucket_id != str(payload.profile_id):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    reports = require_verification_report_coordinates_current(
        bundle.verification.load(operation=operation.authority_operation), operation=operation.authority_operation
    ).for_calculation_revision(revision.calculation_revision_id)
    granting = tuple(report for report in reports if report.granted_verificado_completo)
    _require_selected_revision_grant_evidence(revision, unit, bundle, payload.profile_id, granting)
    return ModeloWorkRevisionProjection(
        profile_id=payload.profile_id,
        unit=ModeloWorkMetadataSnapshot.from_work_unit(unit),
        calculation_revision_id=revision.calculation_revision_id,
        calculation_state=revision.state,
        verification_report_id=granting[0].verification_report_id if granting else None,
        granted_verificado_completo=bool(granting),
    )


class ModeloWorkRevisionExecutor:
    """Capture one selected revision and its report under pinned authority."""

    def __init__(self, factory: VerificationRepositoryBundleFactory) -> None:
        self._factory = factory

    async def execute(
        self, request: OperationRequest[ModeloWorkRevisionRequest], context: OperationExecutorContext
    ) -> str:
        payload = request.payload
        if (
            request.definition_id != MODELO_WORK_REVISION_OPERATION_DEFINITION_ID
            or request.subject_ref != profile_operation_subject(str(payload.profile_id))
            or context.identity.subject_ref != request.subject_ref
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase(MODELO_WORK_REVISION_OPERATION_DEFINITION_ID)

        return await capture_read_result(
            context,
            partial(
                _capture,
                payload,
                self._factory(str(payload.profile_id), operation=context.authority_operation),
                context,
            ),
            task_name="modelo-revision-read",
        )


def build_modelo_work_revision_definition(factory: VerificationRepositoryBundleFactory) -> OperationDefinition:
    """Declare one credential-free, encrypted-result revision read."""
    return build_single_phase_definition(
        definition_id=MODELO_WORK_REVISION_OPERATION_DEFINITION_ID,
        request_type=ModeloWorkRevisionRequest,
        result_type=ModeloWorkRevisionProjection,
        executor_type=ModeloWorkRevisionExecutor,
        build=lambda: ModeloWorkRevisionExecutor(factory),
        capabilities=RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}),
    )


def build_modelo_work_revision_registration(
    definition: OperationDefinition, factory: VerificationRepositoryBundleFactory
) -> OperationPublicDefinitionRegistrationV1:
    """Resolve fresh period scope and retain admitted scope for history."""

    def resolve(request: OperationRequest[BaseModel], context: OperationAccessContext, /) -> ResolvedOperationAccess:
        payload = require_access_request_profile_payload(
            request,
            definition_id=MODELO_WORK_REVISION_OPERATION_DEFINITION_ID,
            payload_type=ModeloWorkRevisionRequest,
            access_profile_id=context.profile_id,
        )

        def fresh_period(operation: PinnedAuthorityOperation) -> Period:
            try:
                unit = _unit(payload, factory(str(payload.profile_id), operation=operation), operation=operation)
            except (
                ModeloWorkSelectorError,
                ModeloWorkAddressNotFoundError,
                ModeloWorkPeriodTokenError,
                ModeloCalculationRevisionSelectorError,
            ):
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED) from None
            return unit.period

        return bind_replayed_or_fresh_single_period_access(
            context,
            LIFECYCLE_SELECTED_PERIODS_REGISTERED_RESULT_TAX_VALUES_ACCESS,
            definition_id=request.definition_id,
            fresh_period=fresh_period,
        )

    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=ModeloWorkRevisionProjection,
        access_resolver=resolve,
    )


__all__ = [
    "MODELO_WORK_REVISION_OPERATION_DEFINITION_ID",
    "ModeloWorkRevisionProjection",
    "ModeloWorkRevisionRequest",
    "build_modelo_work_revision_definition",
    "build_modelo_work_revision_registration",
]
