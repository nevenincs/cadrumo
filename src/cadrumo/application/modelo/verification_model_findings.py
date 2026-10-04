"""Run model-specific checks only when the selected registry snapshot is readable."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cadrumo.application.calculations.observations_repository import (
    CalculationObservationRepositoryProtocol,
)

from ...core.operator_action_enums import ActionEvidenceProvenance
from ...domain.modelos.calculation_revision import (
    CalculationRevision,
)
from ...domain.modelos.protocols import (
    CalculationRevisionCatalogueRepositoryProtocol,
)
from ...domain.modelos.verification_report import (
    ModeloVerificationFinding,
)
from ...domain.modelos.work_unit import WorkUnit
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from ..calculations.iva_compensation_history_ports import IvaCompensationHistoryRepositoryProtocol
from ._m210_agrupacion_renta import m210_agrupacion_renta_verification_findings
from ._m303_m349_reconcile import m303_m349_intracom_reconcile_findings
from ._m720_redeclaration_gate import modelo_720_redeclaration_findings
from .m193_settled_row_gate import modelo_193_settled_row_verification_finding
from .preconditions import ModeloPreconditionFailure
from .pulled_filing_reconcile import pulled_filing_divergence_findings
from .verification_finding_contracts import REGISTRY_SNAPSHOT_REFUSAL_SCENARIOS
from .verification_preconditions import (
    build_verification_precondition_failure,
)
from .verification_repository_ports import VerificationRepositoryBundle

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation


def append_model_specific_findings(
    findings: list[ModeloVerificationFinding],
    *,
    failures_by_finding_id: dict[int, ModeloPreconditionFailure],
    work_unit: WorkUnit,
    target: CalculationRevision,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
    observation_repository: CalculationObservationRepositoryProtocol,
    iva_history_repository: IvaCompensationHistoryRepositoryProtocol,
    operation: PinnedAuthorityOperation,
) -> None:
    """Append cross-model and detail-row verification findings in one place."""
    findings.extend(
        m303_m349_intracom_reconcile_findings(
            work_unit=work_unit,
            target=target,
            work_unit_repository=work_unit_repository,
            calculation_repository=calculation_repository,
            operation=operation,
        ),
    )
    findings.extend(
        pulled_filing_divergence_findings(
            work_unit=work_unit,
            target=target,
            observation_repository=observation_repository,
            operation=operation,
        ),
    )
    m210_agrupacion_findings = m210_agrupacion_renta_verification_findings(
        work_unit=work_unit,
        revision=target,
        operation=operation,
    )
    findings.extend(m210_agrupacion_findings)
    for finding in m210_agrupacion_findings:
        failures_by_finding_id[id(finding)] = build_verification_precondition_failure(
            calculation_revision_id=target.calculation_revision_id,
            work_unit_id=target.work_unit_id,
            condition_id="modelo.work.verify.m210.agrupacion.valid",
            scenario_id="modelo.work.verify.m210.agrupacion.invalid",
            evidence_id="modelo.work.verify.m210.agrupacion",
            evidence_values={
                "detail_row_count": len(target.detail_rows),
                "official_tipo_renta_present": target.m210_official_tipo_renta_code is not None,
            },
            provenance=ActionEvidenceProvenance.PERSISTED_STATE,
        )
    findings.extend(
        modelo_720_redeclaration_findings(
            work_unit=work_unit,
            revision=target,
            observation_repository=observation_repository,
            iva_history_repository=iva_history_repository,
            operation=operation,
        ),
    )
    # Non-blocking and without a precondition failure: filing and export refuse
    # the revision themselves, and this tells the operator before they try.
    settled_row_finding = modelo_193_settled_row_verification_finding(work_unit, target)
    if settled_row_finding is not None:
        findings.append(settled_row_finding)


def append_readable_model_findings(
    findings: list[ModeloVerificationFinding],
    failures_by_finding_id: dict[int, ModeloPreconditionFailure],
    work_unit: WorkUnit,
    target: CalculationRevision,
    repos: VerificationRepositoryBundle,
    operation: PinnedAuthorityOperation,
) -> None:
    """Skip model checks only after an explicit registry-snapshot refusal."""
    registry_snapshot_refused = any(
        failure.scenario_id in REGISTRY_SNAPSHOT_REFUSAL_SCENARIOS for failure in failures_by_finding_id.values()
    )
    if not registry_snapshot_refused:
        append_model_specific_findings(
            findings,
            failures_by_finding_id=failures_by_finding_id,
            work_unit=work_unit,
            target=target,
            work_unit_repository=repos.work_unit,
            calculation_repository=repos.calculation,
            observation_repository=repos.observation,
            iva_history_repository=repos.iva_compensation_history,
            operation=operation,
        )
