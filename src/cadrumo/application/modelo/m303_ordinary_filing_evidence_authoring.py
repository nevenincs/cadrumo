"""Transient authoring of the ordinary 2025 Modelo 303 filing-evidence envelope."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, model_validator

from ...core.modelo import Modelo
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.period import Period
from ...domain.attachments.protocols import AttachmentStoreProtocol
from ...domain.calculations.registry.m303_orden_resolution import resolve_m303_regimen_simplificado_snapshot
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
from .action_errors import M303FilingEvidenceError, ModeloProfileReadinessError
from .m303_exonerado_390_applicability_attestation import (
    resolve_m303_exonerado_390_not_applicable_attestation,
)
from .m303_filing_evidence import validate_m303_filing_instance_evidence_for_revision
from .m303_regimen_simplificado_scope import (
    m303_regimen_simplificado_scope_for_profile,
    taxpayer_profile_for_work,
)
from .profile_readiness_gate import load_modelo_work_profile
from .work_profile import ModeloWorkProfile

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation

_ORDINARY_M303_FILING_YEAR = 2025


class OrdinaryM303FilingEvidenceRequest(BaseModel):
    """The complete operator-owned input for one ordinary 2025 M303 envelope."""

    model_config = STRICT_FROZEN_CONFIG

    filing_year: int = Field(ge=1)
    period: Period
    joint_return_elected: bool
    annual_volume_nonzero: bool
    exonerado_390_applicability_reference: FilingEvidenceReference

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
    _require_ordinary_work_coordinate(work_unit=work_unit, request=request)
    registry_snapshot = operation.snapshot("303", filing_year=request.filing_year, period=request.period.registry_token)
    if registry_snapshot.revision.id != work_unit.revision_id:
        raise M303FilingEvidenceError("ordinary M303 evidence authority revision is stale for this work unit")
    profile = _require_current_profile(work_unit=work_unit, operation=operation, profile=profile)
    scope = m303_regimen_simplificado_scope_for_profile(taxpayer_profile_for_work(profile))
    if not scope.is_not_claimed:
        raise M303FilingEvidenceError("simplified-regime profile requires its unsupported evidence branch")
    applicability_reference = resolve_m303_exonerado_390_not_applicable_attestation(
        bucket_id=work_unit.bucket_id,
        filing_year=request.filing_year,
        period=request.period,
        evidence_reference=request.exonerado_390_applicability_reference,
        operation=operation,
        store=attachment_store,
        profile=profile,
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
            annual_volume_nonzero=request.annual_volume_nonzero,
            insolvency=None,
            exonerado_390=M303Exonerado390FilingEvidence(
                applicable=False,
                applicability_reference=applicability_reference,
                endpoints=(),
                activity_rows=(),
                operaciones_terceros_declarables=None,
                operaciones_terceros_reference=None,
            ),
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


def _require_ordinary_work_coordinate(*, work_unit: WorkUnit, request: OrdinaryM303FilingEvidenceRequest) -> None:
    if (
        work_unit.modelo != Modelo("303")
        or request.filing_year != _ORDINARY_M303_FILING_YEAR
        or not request.period.is_quarterly
        or (work_unit.filing_year, work_unit.period) != (request.filing_year, request.period)
    ):
        raise M303FilingEvidenceError(
            "ordinary evidence authoring supports only the exact 2025 quarterly Modelo 303 work unit"
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


__all__ = ["OrdinaryM303FilingEvidenceRequest", "author_ordinary_m303_filing_instance_evidence"]
