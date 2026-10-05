"""Capture complete verification report history under pinned profile authority."""

from __future__ import annotations

from datetime import datetime

from ...core.hashing import canonical_json_bytes
from ...core.identity.hex_ids import CalculationRevisionId
from ...core.period import Period
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.modelos.calculation_revision import CalculationRevisionCatalogue
from ...domain.modelos.verification_report import (
    VerificationReport,
)
from ...domain.modelos.work_unit import WorkUnitCatalogue
from ..calculations.verification_report_gate import require_verification_report_coordinates_current
from ..user_profile.access_contracts import (
    AccessDenialCode,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .calculation_revision_gate import require_calculation_revision_coordinates_current
from .verification_report_public_facts import ModeloVerificationReportProjection
from .verification_report_read_contracts import (
    MAX_MODELO_VERIFICATION_REPORT_LIST_ROWS,
    VERIFICATION_REPORT_RESULT_DOCUMENT_MAX_BYTES,
    ModeloVerificationReportListRequest,
    ModeloVerificationReportViewRequest,
)
from .verification_report_read_projection import (
    ModeloVerificationReportListProjection,
    ModeloVerificationReportViewProjection,
)
from .verification_repository_ports import VerificationRepositoryBundle, VerificationRepositoryBundleFactory


def _report_order_key(report: VerificationReport) -> tuple[str, datetime]:
    """Keep the existing report-list order."""
    return report.calculation_revision_id, report.run_at


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


def verification_calculation_revision_period(
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


def verification_report_period(
    report: VerificationReport,
    *,
    profile_id: str,
    calculation_catalogue: CalculationRevisionCatalogue,
    work_units: WorkUnitCatalogue,
    operation: PinnedAuthorityOperation,
) -> Period:
    """Correlate the report with the one profile-owned revision it records."""
    period = verification_calculation_revision_period(
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


def load_verification_report_read_scope(
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


def capture_verification_report_list(
    payload: ModeloVerificationReportListRequest,
    factory: VerificationRepositoryBundleFactory,
    *,
    operation: PinnedAuthorityOperation,
) -> ModeloVerificationReportListProjection:
    """Capture the complete filtered history without clipping any report."""
    profile_id = str(payload.profile_id)
    bundle, calculations, work_units = load_verification_report_read_scope(factory, profile_id, operation=operation)
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
        verification_report_period(
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
    if len(canonical_json_bytes(projection.model_dump(mode="json"))) > VERIFICATION_REPORT_RESULT_DOCUMENT_MAX_BYTES:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    return projection


def capture_verification_report_view(
    payload: ModeloVerificationReportViewRequest,
    factory: VerificationRepositoryBundleFactory,
    *,
    operation: PinnedAuthorityOperation,
) -> ModeloVerificationReportViewProjection:
    """Capture one report and refuse missing or mismatched profile evidence."""
    profile_id = str(payload.profile_id)
    bundle, calculations, work_units = load_verification_report_read_scope(factory, profile_id, operation=operation)
    catalogue = require_verification_report_coordinates_current(
        bundle.verification.load(operation=operation), operation=operation
    )
    report = catalogue.get(payload.verification_report_id)
    if report is None or report.verification_report_id != payload.verification_report_id:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    verification_report_period(
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
    if len(canonical_json_bytes(projection.model_dump(mode="json"))) > VERIFICATION_REPORT_RESULT_DOCUMENT_MAX_BYTES:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    return projection
