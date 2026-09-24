"""Transient authoring of the ordinary Modelo 303 filing-evidence envelope."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from pydantic import BaseModel, model_validator

from ...core.filing_year import FilingYear
from ...core.modelo import Modelo
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.period import Period
from ...domain.attachments.errors import AttachmentNotFoundError, AttachmentValidationError
from ...domain.attachments.protocols import AttachmentStoreProtocol
from ...domain.calculations.registry.m303_orden_resolution import resolve_m303_regimen_simplificado_snapshot
from ...domain.calculations.registry.schedules import applicable_filing_schedules
from ...domain.filing_evidence import FilingEvidenceReference
from ...domain.iva.regimen_simplificado_rows import RegimenSimplificadoFilingRows
from ...domain.modelos.calculation_revision_m303_evidence import M303Exonerado390FilingEvidence
from ...domain.modelos.calculation_revision_m303_handoff import (
    FilingInstanceEvidence,
    M303FilingInstanceEvidence,
    M303RegimenSimplificadoFilingEvidence,
)
from ...domain.modelos.work_unit import WorkUnit
from ..calculations.m303_regimen_simplificado import calculate_m303_regimen_simplificado_result
from .action_errors import (
    M303Exonerado390AttestationUnadmissibleError,
    M303FilingEvidenceError,
    ModeloProfileReadinessError,
)
from .m303_exonerado_390_applicability_attestation import (
    m303_exonerado_390_filing_evidence_reference,
    modelo_390_question_asked,
    require_modelo_390_question_in_period,
    resolve_m303_exonerado_390_not_applicable_attestation,
)
from .m303_filing_evidence import m303_filing_evidence_failure, validate_m303_filing_instance_evidence_for_revision
from .m303_ordinary_evidence_coordinate import ordinary_m303_evidence_coordinate_supported
from .m303_regimen_simplificado_scope import (
    m303_regimen_simplificado_scope_for_profile,
    taxpayer_profile_for_work,
)
from .profile_readiness_gate import load_modelo_work_profile
from .work_profile import ModeloWorkProfile

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.calculations.registry.schema import ModeloRevision
    from ...domain.deadlines.models import TaxpayerProfile


class OrdinaryM303FilingEvidenceRequest(BaseModel):
    """The complete operator-owned input for one ordinary M303 envelope.

    The Modelo 390 attestation reference is present exactly in the last
    settlement period of the year, the only return that asks the exemption.
    The ordinary path asks no annual-volume answer: the record prints it only
    for a filer exempt from Modelo 390, whose branch is not supported here.
    """

    model_config = STRICT_FROZEN_CONFIG

    filing_year: FilingYear
    period: Period
    joint_return_elected: bool
    exonerado_390_applicability_reference: FilingEvidenceReference | None

    @model_validator(mode="after")
    def _period_matches_filing_year(self) -> OrdinaryM303FilingEvidenceRequest:
        if self.period.filing_year != self.filing_year:
            raise M303FilingEvidenceError("ordinary M303 evidence period disagrees with filing year")
        return self


def author_ordinary_m303_filing_instance_evidence(
    *,
    work_unit: WorkUnit,
    request: OrdinaryM303FilingEvidenceRequest,
    operation: PinnedAuthorityOperation,
    attachment_store: AttachmentStoreProtocol,
    profile: ModeloWorkProfile | None = None,
) -> FilingInstanceEvidence:
    """Construct validated ordinary evidence ready for ``calculate_modelo_revision``.

    The returned transient envelope is the existing calculation action's
    ``filing_instance_evidence`` input; it is durable only when that action
    persists the resulting calculation revision.
    """
    _require_ordinary_work_coordinate(work_unit=work_unit, request=request, operation=operation)
    _require_period_scoped_attestation(request, operation=operation)
    registry_snapshot = operation.snapshot("303", filing_year=request.filing_year, period=request.period.registry_token)
    if registry_snapshot.revision.id != work_unit.revision_id:
        raise M303FilingEvidenceError("ordinary M303 evidence authority revision is stale for this work unit")
    profile = _require_current_profile(work_unit=work_unit, operation=operation, profile=profile)
    taxpayer = taxpayer_profile_for_work(profile)
    _require_period_in_the_profile_filing_schedule(
        revision=registry_snapshot.revision, taxpayer=taxpayer, period=request.period
    )
    scope = m303_regimen_simplificado_scope_for_profile(taxpayer)
    if not scope.is_not_claimed:
        raise M303FilingEvidenceError("simplified-regime profile requires its unsupported evidence branch")
    exonerado_390 = _modelo_390_exemption_evidence(
        work_unit=work_unit, request=request, operation=operation, attachment_store=attachment_store, profile=profile
    )
    regimen_snapshot = resolve_m303_regimen_simplificado_snapshot(
        registry_snapshot=registry_snapshot,
        scope_decision=scope,
    )
    rows = RegimenSimplificadoFilingRows(ejercicio=request.filing_year, activities=())
    regimen_evidence = M303RegimenSimplificadoFilingEvidence(
        scope_decision=scope,
        rows=rows,
        regimen_snapshot=regimen_snapshot,
        dana_eligibility=None,
        calculation_result=calculate_m303_regimen_simplificado_result(
            period=request.period,
            scope_decision=scope,
            rows=rows,
            regimen_snapshot=regimen_snapshot,
            dana_eligibility=None,
            operation=operation,
        ),
    )
    evidence = FilingInstanceEvidence(
        m303=M303FilingInstanceEvidence(
            period=request.period,
            joint_return_elected=request.joint_return_elected,
            annual_volume_nonzero=None,
            insolvency=None,
            exonerado_390=exonerado_390,
            regimen_simplificado=regimen_evidence,
        )
    )
    validated = validate_m303_filing_instance_evidence_for_revision(
        work_unit=work_unit,
        registry_snapshot=registry_snapshot,
        evidence=evidence,
        casilla_values={},
        observations=(),
        operation=operation,
        profile=profile,
    )
    if validated is None:
        raise M303FilingEvidenceError("Modelo 303 evidence validation produced no evidence")
    return validated


def author_ordinary_m303_evidence_for_work(
    *,
    work_unit: WorkUnit,
    joint_return_elected: bool,
    exonerado_390_attachment_id: str | None,
    exonerado_390_sha256: str | None,
    operation: PinnedAuthorityOperation,
    open_attachment_store: Callable[[], AttachmentStoreProtocol],
    profile: ModeloWorkProfile | None = None,
) -> FilingInstanceEvidence:
    """Author ordinary evidence from the operator's answers exactly as every entrypoint receives them.

    The attestation arrives as two public identifiers that must be supplied
    together; the work unit supplies the year, period and revision. Custody is
    opened only once the identifiers are well formed.
    """
    if (exonerado_390_attachment_id is None) != (exonerado_390_sha256 is None):
        raise M303Exonerado390AttestationUnadmissibleError(
            "Modelo 390 applicability attestation needs both its attachment id and its SHA-256",
            context={"reason": "incomplete_identity"},
        )
    reference = (
        None
        if exonerado_390_attachment_id is None or exonerado_390_sha256 is None
        else m303_exonerado_390_filing_evidence_reference(
            attachment_id=exonerado_390_attachment_id, sha256=exonerado_390_sha256
        )
    )
    return author_ordinary_m303_filing_instance_evidence(
        work_unit=work_unit,
        request=OrdinaryM303FilingEvidenceRequest(
            filing_year=work_unit.filing_year,
            period=work_unit.period,
            joint_return_elected=joint_return_elected,
            exonerado_390_applicability_reference=reference,
        ),
        operation=operation,
        attachment_store=open_attachment_store(),
        profile=profile,
    )


def _require_period_in_the_profile_filing_schedule(
    *, revision: ModeloRevision, taxpayer: TaxpayerProfile, period: Period
) -> None:
    """Refuse a settlement period no filing schedule of this revision assigns to the taxpayer.

    The revision's schedules carry RD 1624/1992 art. 71: REDEME-registered and
    large-company filers settle monthly, every other filer quarterly, so a
    quarterly filer cannot author a monthly return nor a monthly filer a quarterly one.
    """
    if revision.filing_schedules and not applicable_filing_schedules(revision, taxpayer, period=period.registry_token):
        raise M303FilingEvidenceError(
            precondition_failure=m303_filing_evidence_failure(
                "period_outside_filing_schedule",
                {"period": period.registry_token, "applicable_schedule_present": False},
            )
        )


def _require_period_scoped_attestation(
    request: OrdinaryM303FilingEvidenceRequest, *, operation: PinnedAuthorityOperation
) -> None:
    """Refuse an attestation the period does not ask for, or a last period without one, before any custody."""
    supplied = request.exonerado_390_applicability_reference is not None
    if not modelo_390_question_asked(request.period, operation=operation):
        if supplied:
            require_modelo_390_question_in_period(request.period, operation=operation)
        return
    if not supplied:
        raise M303FilingEvidenceError(
            precondition_failure=m303_filing_evidence_failure(
                "missing",
                {"period": request.period.registry_token, "exonerado_390_attestation_present": False},
            )
        )


def _modelo_390_exemption_evidence(
    *,
    work_unit: WorkUnit,
    request: OrdinaryM303FilingEvidenceRequest,
    operation: PinnedAuthorityOperation,
    attachment_store: AttachmentStoreProtocol,
    profile: ModeloWorkProfile,
) -> M303Exonerado390FilingEvidence | None:
    """Resolve the last period's exemption attestation; every other period carries none."""
    reference = request.exonerado_390_applicability_reference
    if reference is None:
        return None
    try:
        applicability_reference = resolve_m303_exonerado_390_not_applicable_attestation(
            bucket_id=work_unit.bucket_id,
            filing_year=request.filing_year,
            period=request.period,
            evidence_reference=reference,
            operation=operation,
            store=attachment_store,
            profile=profile,
        )
    except (AttachmentNotFoundError, AttachmentValidationError) as exc:
        raise M303Exonerado390AttestationUnadmissibleError(
            "Modelo 390 applicability attestation cannot back this Modelo 303 work unit",
            context={"reason": type(exc).__name__},
        ) from exc
    return M303Exonerado390FilingEvidence(
        applicable=False,
        applicability_reference=applicability_reference,
        endpoints=(),
        activity_rows=(),
        operaciones_terceros_declarables=None,
        operaciones_terceros_reference=None,
    )


def _require_ordinary_work_coordinate(
    *, work_unit: WorkUnit, request: OrdinaryM303FilingEvidenceRequest, operation: PinnedAuthorityOperation
) -> None:
    if (
        work_unit.modelo != Modelo("303")
        or (work_unit.filing_year, work_unit.period) != (request.filing_year, request.period)
        or not ordinary_m303_evidence_coordinate_supported(
            filing_year=request.filing_year, period=request.period, operation=operation
        )
    ):
        raise M303FilingEvidenceError(
            "ordinary evidence authoring supports only a quarterly or monthly Modelo 303 work unit whose "
            "selected record design declares the ordinary evidence header fields"
        )


def _require_current_profile(
    *, work_unit: WorkUnit, operation: PinnedAuthorityOperation, profile: ModeloWorkProfile | None
) -> ModeloWorkProfile:
    if profile is None:
        profile = load_modelo_work_profile(
            bucket_id=work_unit.bucket_id,
            profile_decode_context=operation.profile_decode_context(),
        )
    if profile is None or str(profile.record.profile_id) != str(work_unit.bucket_id):
        raise ModeloProfileReadinessError("ordinary M303 evidence requires an authenticated current profile")
    return profile


__all__ = [
    "OrdinaryM303FilingEvidenceRequest",
    "author_ordinary_m303_evidence_for_work",
    "author_ordinary_m303_filing_instance_evidence",
]
