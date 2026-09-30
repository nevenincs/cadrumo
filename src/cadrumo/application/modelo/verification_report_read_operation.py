"""Registered, exact-profile reads of persisted verification reports."""

from __future__ import annotations

import asyncio
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, NonNegativeInt, StringConstraints, field_validator, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.casilla_id import CasillaId
from ...core.filing_year import FilingYear
from ...core.hashing import canonical_json_bytes
from ...core.identifier_grammar import FIELD_KEY_PATTERN, NAMESPACED_ID_PATTERN
from ...core.identity.hex_ids import CalculationRevisionId, VerificationReportId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    profile_operation_subject,
)
from ...core.period import Period, PeriodError
from ...core.time.clock import now
from ...core.time.utc import validate_utc_aware
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.ids import (
    LegalRefId,
    ModeloId,
    RevisionId,
    SourceRefId,
    VerificationExpectationId,
)
from ...domain.calculations.registry.schema_references import RegistrySnapshotRef
from ...domain.modelos.calculation_revision import CalculationRevisionCatalogue
from ...domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationCompletenessStatus,
    VerificationReport,
)
from ...domain.modelos.work_unit import WorkUnitCatalogue
from ..calculations.verification_report_gate import require_verification_report_coordinates_current
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
from ..operations.models import CredentialFreeOperationRequest, OperationRequest
from ..operations.owner import OperationExecutorContext
from ..operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..runtime.projection_pages import PROJECTION_DOCUMENT_MAX_BYTES
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
from .calculation_revision_gate import require_calculation_revision_coordinates_current
from .verification_repository_ports import VerificationRepositoryBundle, VerificationRepositoryBundleFactory

MODELO_VERIFICATION_REPORT_LIST_OPERATION_DEFINITION_ID = "modelo.verification_report.list"
MODELO_VERIFICATION_REPORT_VIEW_OPERATION_DEFINITION_ID = "modelo.verification_report.view"

MAX_MODELO_VERIFICATION_REPORT_LIST_ROWS = 4_096
MAX_MODELO_VERIFICATION_REPORT_FINDINGS = 2_048
MAX_MODELO_VERIFICATION_REPORT_CASILLAS = 32_768
MAX_MODELO_VERIFICATION_REPORT_FINDING_REFS = 512
MAX_MODELO_VERIFICATION_REPORT_FACTS = 64
_RESULT_DOCUMENT_MAX_BYTES = PROJECTION_DOCUMENT_MAX_BYTES - 4_096

_FindingLocaleKey = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=3, max_length=200, pattern=NAMESPACED_ID_PATTERN),
]
_FindingFactKey = Annotated[str, StringConstraints(min_length=1, max_length=128, pattern=FIELD_KEY_PATTERN)]
_FindingFactText = Annotated[str, Field(max_length=4_096)]
_FindingFactInteger = Annotated[int, Field(ge=-(10**64), le=10**64)]
_FindingFactValue = _FindingFactText | _FindingFactInteger | bool
_ReportCasillas = Annotated[tuple[CasillaId, ...], Field(max_length=MAX_MODELO_VERIFICATION_REPORT_CASILLAS)]


class ModeloVerificationReportListRequest(CredentialFreeOperationRequest):
    """Select a profile's verification history or one calculation revision."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    calculation_revision_id: CalculationRevisionId | None = None


class ModeloVerificationReportViewRequest(CredentialFreeOperationRequest):
    """Select one persisted verification report in the authenticated profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    verification_report_id: VerificationReportId


class ModeloVerificationFactProjection(BaseModel):
    """One bounded immutable locale fact without an open-ended object schema."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    key: _FindingFactKey
    value_kind: Literal["text", "integer", "boolean", "decimal"]
    value: _FindingFactValue

    @model_validator(mode="after")
    def _value_matches_kind(self) -> Self:
        if self.value_kind == "text" and not isinstance(self.value, str):
            raise ValueError("text verification fact requires a string value")
        if self.value_kind == "integer" and type(self.value) is not int:
            raise ValueError("integer verification fact requires an integer value")
        if self.value_kind == "boolean" and type(self.value) is not bool:
            raise ValueError("boolean verification fact requires a boolean value")
        if self.value_kind == "decimal":
            if not isinstance(self.value, str) or len(self.value) > 128:
                raise ValueError("decimal verification fact requires a decimal string")
            try:
                decimal_value = Decimal(self.value)
            except Exception:
                raise ValueError("decimal verification fact is invalid") from None
            if not _decimal_fact_is_bounded(decimal_value):
                raise ValueError("decimal verification fact exceeds the public result bound")
        return self

    @classmethod
    def from_fact(cls, key: str, value: str | int | bool | Decimal) -> ModeloVerificationFactProjection:
        """Copy one typed domain fact into its bounded JSON representation."""
        kind: Literal["text", "integer", "boolean", "decimal"]
        if isinstance(value, bool):
            kind = "boolean"
            wire_value: str | int | bool = value
        elif isinstance(value, int):
            kind = "integer"
            wire_value = value
        elif isinstance(value, Decimal):
            if not _decimal_fact_is_bounded(value):
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
            kind = "decimal"
            wire_value = str(value)
        else:
            if len(value) > 4_096:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
            kind = "text"
            wire_value = value
        return cls(key=key, value_kind=kind, value=wire_value)


class ModeloVerificationRegistrySnapshotProjection(BaseModel):
    """Closed scalar coordinates for a verification report's registry ref."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    modelo: ModeloId
    revision_id: RevisionId
    modelo_year: FilingYear
    period: Annotated[str, Field(min_length=1, max_length=16)]

    @model_validator(mode="after")
    def _period_is_canonical(self) -> Self:
        try:
            parsed = Period.from_year_and_code(self.modelo_year, self.period)
        except PeriodError:
            raise ValueError("verification report registry period is invalid") from None
        if parsed.registry_token != self.period:
            raise ValueError("verification report registry period must be canonical")
        return self

    @classmethod
    def from_snapshot(cls, reference: RegistrySnapshotRef) -> ModeloVerificationRegistrySnapshotProjection:
        """Copy the domain reference into schema-safe scalar fields."""
        return cls(
            modelo=str(reference.modelo),
            revision_id=str(reference.revision_id),
            modelo_year=reference.modelo_year,
            period=str(reference.period),
        )


_FindingFacts = Annotated[
    tuple[ModeloVerificationFactProjection, ...], Field(max_length=MAX_MODELO_VERIFICATION_REPORT_FACTS)
]


class ModeloVerificationFindingProjection(BaseModel):
    """Bounded locale-neutral finding facts, retaining legal and source refs."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: ModeloVerificationFindingKind
    severity: ModeloVerificationFindingSeverity
    casilla_id: CasillaId | None = None
    expectation_id: VerificationExpectationId | None = None
    message_locale_key: _FindingLocaleKey
    message_facts: _FindingFacts = ()
    legal_refs: Annotated[
        tuple[LegalRefId, ...], Field(min_length=1, max_length=MAX_MODELO_VERIFICATION_REPORT_FINDING_REFS)
    ]
    source_refs: Annotated[tuple[SourceRefId, ...], Field(max_length=MAX_MODELO_VERIFICATION_REPORT_FINDING_REFS)] = ()

    @model_validator(mode="after")
    def _unique_refs(self) -> Self:
        if len(set(self.legal_refs)) != len(self.legal_refs) or len(set(self.source_refs)) != len(self.source_refs):
            raise ValueError("verification finding references must not repeat")
        fact_keys = tuple(fact.key for fact in self.message_facts)
        if fact_keys != tuple(sorted(set(fact_keys))):
            raise ValueError("verification finding facts must be unique and ordered")
        return self

    @classmethod
    def from_finding(cls, finding: ModeloVerificationFinding) -> ModeloVerificationFindingProjection:
        """Copy every locale-neutral finding fact without rendering or truncating it."""
        if (
            len(finding.message_facts) > MAX_MODELO_VERIFICATION_REPORT_FACTS
            or any(len(key) > 128 for key in finding.message_facts)
            or len(finding.legal_refs) > MAX_MODELO_VERIFICATION_REPORT_FINDING_REFS
            or len(finding.source_refs) > MAX_MODELO_VERIFICATION_REPORT_FINDING_REFS
            or any(not _finding_fact_value_is_bounded(item) for item in finding.message_facts.values())
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        return cls(
            kind=finding.kind,
            severity=finding.severity,
            casilla_id=finding.casilla_id,
            expectation_id=finding.expectation_id,
            message_locale_key=finding.message_locale_key,
            message_facts=tuple(
                ModeloVerificationFactProjection.from_fact(key, value)
                for key, value in sorted(finding.message_facts.items())
            ),
            legal_refs=finding.legal_refs,
            source_refs=finding.source_refs,
        )


def _decimal_fact_is_bounded(value: Decimal) -> bool:
    """Apply the public fact bounds without changing a decimal value."""
    if not value.is_finite():
        return False
    parts = value.as_tuple()
    exponent = parts.exponent
    if not isinstance(exponent, int):
        return False
    return len(parts.digits) + max(exponent, 0) <= 64 and max(-exponent, 0) <= 32


def _finding_fact_value_is_bounded(value: str | int | bool | Decimal) -> bool:
    """Check one fact against the immutable public DTO's scalar bounds."""
    if isinstance(value, bool):
        return True
    if isinstance(value, int):
        return -(10**64) <= value <= 10**64
    if isinstance(value, Decimal):
        return _decimal_fact_is_bounded(value) and len(str(value)) <= 128
    return len(value) <= 4_096


class ModeloVerificationReportProjection(BaseModel):
    """Complete bounded public facts from one persisted verification report."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    verification_report_id: VerificationReportId
    calculation_revision_id: CalculationRevisionId
    registry_snapshot_ref: ModeloVerificationRegistrySnapshotProjection
    completeness_status: VerificationCompletenessStatus
    granted_verificado_completo: bool
    resolved_casilla_ids: _ReportCasillas
    missing_required_casilla_ids: _ReportCasillas
    run_at: datetime
    verified_by: Annotated[str, Field(min_length=1, max_length=64)]
    findings: Annotated[
        tuple[ModeloVerificationFindingProjection, ...], Field(max_length=MAX_MODELO_VERIFICATION_REPORT_FINDINGS)
    ]

    @field_validator("run_at")
    @classmethod
    def _run_at_is_utc(cls, value: datetime) -> datetime:
        return validate_utc_aware(value)

    @model_validator(mode="after")
    def _report_invariants(self) -> Self:
        if set(self.resolved_casilla_ids) & set(self.missing_required_casilla_ids):
            raise ValueError("verification report casillas cannot be both resolved and missing")
        if len(set(self.resolved_casilla_ids)) != len(self.resolved_casilla_ids):
            raise ValueError("resolved verification report casillas must not repeat")
        if len(set(self.missing_required_casilla_ids)) != len(self.missing_required_casilla_ids):
            raise ValueError("missing verification report casillas must not repeat")
        has_blocking = any(finding.severity is ModeloVerificationFindingSeverity.BLOCKING for finding in self.findings)
        if self.granted_verificado_completo != (
            self.completeness_status is VerificationCompletenessStatus.COMPLETE and not has_blocking
        ):
            raise ValueError("verification report grant must match its completeness and findings")
        if self.run_at.tzinfo is None:
            raise ValueError("verification report timestamp must be timezone-aware")
        return self

    @classmethod
    def from_report(cls, report: VerificationReport) -> ModeloVerificationReportProjection:
        """Copy the full report projection, refusing instead of clipping large records."""
        if (
            len(report.findings) > MAX_MODELO_VERIFICATION_REPORT_FINDINGS
            or len(report.resolved_casilla_ids) > MAX_MODELO_VERIFICATION_REPORT_CASILLAS
            or len(report.missing_required_casilla_ids) > MAX_MODELO_VERIFICATION_REPORT_CASILLAS
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        return cls(
            verification_report_id=report.verification_report_id,
            calculation_revision_id=report.calculation_revision_id,
            registry_snapshot_ref=ModeloVerificationRegistrySnapshotProjection.from_snapshot(
                report.registry_snapshot_ref
            ),
            completeness_status=report.completeness_status,
            granted_verificado_completo=report.granted_verificado_completo,
            resolved_casilla_ids=report.resolved_casilla_ids,
            missing_required_casilla_ids=report.missing_required_casilla_ids,
            run_at=report.run_at,
            verified_by=report.verified_by,
            findings=tuple(ModeloVerificationFindingProjection.from_finding(finding) for finding in report.findings),
        )


def _report_order_key(report: VerificationReport) -> tuple[str, datetime]:
    """Keep the existing report-list order."""
    return report.calculation_revision_id, report.run_at


def _projection_order_key(report: ModeloVerificationReportProjection) -> tuple[str, datetime]:
    return report.calculation_revision_id, report.run_at


class ModeloVerificationReportListProjection(BaseModel):
    """Complete, ordered report history captured for one exact profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result_version: Literal[1] = 1
    profile_id: UUID
    calculation_revision_id_filter: CalculationRevisionId | None
    report_count: NonNegativeInt
    reports: Annotated[
        tuple[ModeloVerificationReportProjection, ...], Field(max_length=MAX_MODELO_VERIFICATION_REPORT_LIST_ROWS)
    ]

    @model_validator(mode="after")
    def _correlate_reports(self) -> Self:
        if self.report_count != len(self.reports):
            raise ValueError("verification report count does not match its rows")
        if any(
            self.calculation_revision_id_filter is not None
            and report.calculation_revision_id != self.calculation_revision_id_filter
            for report in self.reports
        ):
            raise ValueError("verification report list exceeds its calculation revision filter")
        if len({report.verification_report_id for report in self.reports}) != len(self.reports):
            raise ValueError("verification report list repeats an identity")
        if self.reports != tuple(sorted(self.reports, key=_projection_order_key)):
            raise ValueError("verification report list is not in the established order")
        return self


class ModeloVerificationReportViewProjection(BaseModel):
    """One report bound to the requested profile and report identity."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result_version: Literal[1] = 1
    profile_id: UUID
    verification_report_id: VerificationReportId
    report: ModeloVerificationReportProjection

    @model_validator(mode="after")
    def _correlate_report(self) -> Self:
        if self.report.verification_report_id != self.verification_report_id:
            raise ValueError("verification report view does not match the requested identity")
        return self


def _bundle_for_profile(
    factory: VerificationRepositoryBundleFactory,
    profile_id: str,
    *,
    operation: PinnedAuthorityOperation,
) -> VerificationRepositoryBundle:
    """Open only the repositories bound to the admitted profile."""
    bundle = factory(profile_id, operation=operation)
    if any(
        repository.bucket_id != profile_id for repository in (bundle.calculation, bundle.work_unit, bundle.verification)
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return bundle


def _revision_period(
    revision_id: CalculationRevisionId,
    *,
    profile_id: str,
    calculation_catalogue: CalculationRevisionCatalogue,
    work_units: WorkUnitCatalogue,
    operation: PinnedAuthorityOperation,
) -> Period:
    """Resolve one calculation revision to its exact, profile-owned period."""
    revision = calculation_catalogue.get(revision_id)
    if revision is None or revision.calculation_revision_id != revision_id:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    require_calculation_revision_coordinates_current(revision, operation=operation)
    unit = work_units.get(revision.work_unit_id)
    if unit is None or unit.bucket_id != profile_id or unit.work_unit_id != revision.work_unit_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    snapshot = revision.registry_snapshot_ref
    if (
        str(snapshot.modelo) != str(unit.modelo)
        or snapshot.modelo_year != unit.filing_year
        or str(snapshot.period) != unit.period.registry_token
        or snapshot.revision_id != unit.revision_id
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return unit.period


def _report_period(
    report: VerificationReport,
    *,
    profile_id: str,
    calculation_catalogue: CalculationRevisionCatalogue,
    work_units: WorkUnitCatalogue,
    operation: PinnedAuthorityOperation,
) -> Period:
    """Correlate the report with the one profile-owned revision it records."""
    period = _revision_period(
        report.calculation_revision_id,
        profile_id=profile_id,
        calculation_catalogue=calculation_catalogue,
        work_units=work_units,
        operation=operation,
    )
    revision = calculation_catalogue.get(report.calculation_revision_id)
    if revision is None or report.registry_snapshot_ref != revision.registry_snapshot_ref:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return period


def _load_scope(
    factory: VerificationRepositoryBundleFactory,
    profile_id: str,
    *,
    operation: PinnedAuthorityOperation,
) -> tuple[VerificationRepositoryBundle, CalculationRevisionCatalogue, WorkUnitCatalogue]:
    """Load only repositories for the exact profile under the pinned authority."""
    bundle = _bundle_for_profile(factory, profile_id, operation=operation)
    calculations = bundle.calculation.load(operation=operation)
    work_units = bundle.work_unit.load()
    return bundle, calculations, work_units


def _capture_list(
    payload: ModeloVerificationReportListRequest,
    factory: VerificationRepositoryBundleFactory,
    *,
    operation: PinnedAuthorityOperation,
) -> ModeloVerificationReportListProjection:
    """Capture the complete filtered history without clipping any report."""
    profile_id = str(payload.profile_id)
    bundle, calculations, work_units = _load_scope(factory, profile_id, operation=operation)
    catalogue = require_verification_report_coordinates_current(
        bundle.verification.load(operation=operation), operation=operation
    )
    reports = tuple(
        sorted(
            (
                report
                for report in catalogue.reports.values()
                if payload.calculation_revision_id is None
                or report.calculation_revision_id == payload.calculation_revision_id
            ),
            key=_report_order_key,
        )
    )
    if len(reports) > MAX_MODELO_VERIFICATION_REPORT_LIST_ROWS:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    for report in reports:
        _report_period(
            report,
            profile_id=profile_id,
            calculation_catalogue=calculations,
            work_units=work_units,
            operation=operation,
        )
    projection = ModeloVerificationReportListProjection(
        profile_id=payload.profile_id,
        calculation_revision_id_filter=payload.calculation_revision_id,
        report_count=len(reports),
        reports=tuple(ModeloVerificationReportProjection.from_report(report) for report in reports),
    )
    if len(canonical_json_bytes(projection.model_dump(mode="json"))) > _RESULT_DOCUMENT_MAX_BYTES:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    return projection


def _capture_view(
    payload: ModeloVerificationReportViewRequest,
    factory: VerificationRepositoryBundleFactory,
    *,
    operation: PinnedAuthorityOperation,
) -> ModeloVerificationReportViewProjection:
    """Capture one report and refuse missing or mismatched profile evidence."""
    profile_id = str(payload.profile_id)
    bundle, calculations, work_units = _load_scope(factory, profile_id, operation=operation)
    catalogue = require_verification_report_coordinates_current(
        bundle.verification.load(operation=operation), operation=operation
    )
    report = catalogue.get(payload.verification_report_id)
    if report is None or report.verification_report_id != payload.verification_report_id:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    _report_period(
        report,
        profile_id=profile_id,
        calculation_catalogue=calculations,
        work_units=work_units,
        operation=operation,
    )
    projection = ModeloVerificationReportViewProjection(
        profile_id=payload.profile_id,
        verification_report_id=payload.verification_report_id,
        report=ModeloVerificationReportProjection.from_report(report),
    )
    if len(canonical_json_bytes(projection.model_dump(mode="json"))) > _RESULT_DOCUMENT_MAX_BYTES:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    return projection


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

        async def capture() -> str:
            projection = await asyncio.to_thread(
                _capture_list, payload, self._factory, operation=context.authority_operation
            )
            reference = await context.operands.put(projection, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return reference

        return await await_cancellation_complete(capture(), task_name="modelo-verification-report-list")


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

        async def capture() -> str:
            projection = await asyncio.to_thread(
                _capture_view, payload, self._factory, operation=context.authority_operation
            )
            reference = await context.operands.put(projection, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return reference

        return await await_cancellation_complete(capture(), task_name="modelo-verification-report-view")


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
    return OperationDefinition(
        definition_id=definition_id,
        request_type=request_type,
        result_type=result_type,
        executor_factory=OperationExecutorFactory(
            request_type=request_type,
            executor_type=executor_type,
            build=lambda: executor_type(factory),
        ),
        phase_codes=(definition_id,),
        interaction_kinds=frozenset(),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.NONE,
            request_storage=OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL,
            sensitive_input=OperationSensitiveInputPolicy.NONE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN}),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI}),
    )


def _disclosures(context: OperationAccessContext) -> frozenset[DisclosurePermission]:
    """Return only operation metadata or the schema-bound tax-value result."""
    if context.action in {AccessAction.OBSERVE, AccessAction.CANCEL, AccessAction.DETACH}:
        return frozenset(
            (
                DisclosurePermission(
                    destination_id=context.destination_id,
                    projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
                    category=DisclosureCategory.OPERATION_METADATA,
                ),
            )
        )
    if context.action is AccessAction.RESULT:
        schema = context.contract.result_schema
        if schema is None:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        return frozenset(
            (
                DisclosurePermission(
                    destination_id=context.destination_id,
                    projection_id=schema.schema_id,
                    category=DisclosureCategory.TAX_VALUES,
                ),
            )
        )
    return frozenset[DisclosurePermission]()


def _access_resolution(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    *,
    definition_id: str,
    payload_type: type[ModeloVerificationReportListRequest] | type[ModeloVerificationReportViewRequest],
    factory: VerificationRepositoryBundleFactory,
) -> ResolvedOperationAccess:
    """Resolve the profile and exact report period for access and result reads."""
    payload = request.payload
    if request.definition_id != definition_id or not isinstance(payload, payload_type):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    profile_id = str(payload.profile_id)
    if payload.profile_id != context.profile_id or request.subject_ref != profile_operation_subject(profile_id):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)

    independent = isinstance(payload, ModeloVerificationReportListRequest) and payload.calculation_revision_id is None
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
            or admitted.period_independent != independent
            or (independent and admitted.periods)
            or (not independent and len(admitted.periods) != 1)
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        periods: frozenset[Period] = admitted.periods
    elif independent:
        periods = frozenset[Period]()
    else:
        if context.authority_operation is None:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        bundle, calculations, work_units = _load_scope(factory, profile_id, operation=context.authority_operation)
        if isinstance(payload, ModeloVerificationReportListRequest):
            if payload.calculation_revision_id is None:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
            period = _revision_period(
                payload.calculation_revision_id,
                profile_id=profile_id,
                calculation_catalogue=calculations,
                work_units=work_units,
                operation=context.authority_operation,
            )
        else:
            catalogue = require_verification_report_coordinates_current(
                bundle.verification.load(operation=context.authority_operation), operation=context.authority_operation
            )
            report = catalogue.get(payload.verification_report_id)
            if report is None:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
            period = _report_period(
                report,
                profile_id=profile_id,
                calculation_catalogue=calculations,
                work_units=work_units,
                operation=context.authority_operation,
            )
        periods = frozenset({period})

    return ResolvedOperationAccess(
        request=OperationAccessRequest(
            profile_id=context.profile_id,
            definition_id=request.definition_id,
            action=context.action,
            frontend=context.frontend,
            periods=periods,
            period_independent=independent,
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
                    AccessAction.OBSERVE,
                    AccessAction.RESULT,
                    AccessAction.CANCEL,
                    AccessAction.DETACH,
                }
            ),
            disclosures=_disclosures(context),
            periods=periods,
            allow_period_independent=independent,
            requires_all_periods=independent,
            backend=Availability.AVAILABLE,
            published_authority=context.published_authority,
            provider=Availability.NOT_REQUIRED,
            transaction_authority_required=False,
        ),
    )


def build_modelo_verification_report_list_registration(
    definition: OperationDefinition,
    factory: VerificationRepositoryBundleFactory,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the complete list schema and exact-period access resolver."""

    def resolve(request: OperationRequest[BaseModel], context: OperationAccessContext, /) -> ResolvedOperationAccess:
        return _access_resolution(
            request,
            context,
            definition_id=MODELO_VERIFICATION_REPORT_LIST_OPERATION_DEFINITION_ID,
            payload_type=ModeloVerificationReportListRequest,
            factory=factory,
        )

    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request",
            schema_version=1,
            model_type=ModeloVerificationReportListRequest,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result",
            schema_version=1,
            model_type=ModeloVerificationReportListProjection,
        ),
        access_resolver=resolve,
    )


def build_modelo_verification_report_view_registration(
    definition: OperationDefinition,
    factory: VerificationRepositoryBundleFactory,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the full view schema and report-derived period access resolver."""

    def resolve(request: OperationRequest[BaseModel], context: OperationAccessContext, /) -> ResolvedOperationAccess:
        return _access_resolution(
            request,
            context,
            definition_id=MODELO_VERIFICATION_REPORT_VIEW_OPERATION_DEFINITION_ID,
            payload_type=ModeloVerificationReportViewRequest,
            factory=factory,
        )

    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request",
            schema_version=1,
            model_type=ModeloVerificationReportViewRequest,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result",
            schema_version=1,
            model_type=ModeloVerificationReportViewProjection,
        ),
        access_resolver=resolve,
    )


def build_modelo_verification_report_read_definitions(
    factory: VerificationRepositoryBundleFactory,
) -> tuple[OperationDefinition, OperationDefinition]:
    """Return the complete canonical definition population for report reads."""
    return (
        build_modelo_verification_report_list_definition(factory),
        build_modelo_verification_report_view_definition(factory),
    )


def build_modelo_verification_report_read_registrations(
    definitions: tuple[OperationDefinition, ...],
    factory: VerificationRepositoryBundleFactory,
) -> tuple[OperationPublicDefinitionRegistrationV1, ...]:
    """Bind both report-read definitions to their public schemas and policies."""
    builders = {
        MODELO_VERIFICATION_REPORT_LIST_OPERATION_DEFINITION_ID: build_modelo_verification_report_list_registration,
        MODELO_VERIFICATION_REPORT_VIEW_OPERATION_DEFINITION_ID: build_modelo_verification_report_view_registration,
    }
    registrations: list[OperationPublicDefinitionRegistrationV1] = []
    for definition in definitions:
        try:
            builder = builders[definition.definition_id]
        except KeyError:
            raise ValueError("unexpected verification-report read definition") from None
        registrations.append(builder(definition, factory))
    if len(registrations) != len(builders):
        raise ValueError("verification-report read registration population is incomplete")
    return tuple(registrations)


__all__ = [
    "MAX_MODELO_VERIFICATION_REPORT_CASILLAS",
    "MAX_MODELO_VERIFICATION_REPORT_FACTS",
    "MAX_MODELO_VERIFICATION_REPORT_FINDINGS",
    "MAX_MODELO_VERIFICATION_REPORT_FINDING_REFS",
    "MAX_MODELO_VERIFICATION_REPORT_LIST_ROWS",
    "MODELO_VERIFICATION_REPORT_LIST_OPERATION_DEFINITION_ID",
    "MODELO_VERIFICATION_REPORT_VIEW_OPERATION_DEFINITION_ID",
    "ModeloVerificationFactProjection",
    "ModeloVerificationFindingProjection",
    "ModeloVerificationRegistrySnapshotProjection",
    "ModeloVerificationReportListExecutor",
    "ModeloVerificationReportListProjection",
    "ModeloVerificationReportListRequest",
    "ModeloVerificationReportProjection",
    "ModeloVerificationReportViewExecutor",
    "ModeloVerificationReportViewProjection",
    "ModeloVerificationReportViewRequest",
    "build_modelo_verification_report_list_definition",
    "build_modelo_verification_report_list_registration",
    "build_modelo_verification_report_read_definitions",
    "build_modelo_verification_report_read_registrations",
    "build_modelo_verification_report_view_definition",
    "build_modelo_verification_report_view_registration",
]
