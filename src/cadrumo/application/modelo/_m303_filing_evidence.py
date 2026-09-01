"""Atomic Modelo 303 filing-evidence validation before revision persistence."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal

from ...core.casilla_id import CasillaId
from ...core.modelo import Modelo
from ...core.operator_action_enums import ActionEvidenceProvenance
from ...domain.calculations.registry.authority import bundled_authority
from ...domain.calculations.registry.bindings import CasillaObservation
from ...domain.calculations.registry.m303_orden_resolution import resolve_m303_regimen_simplificado_snapshot
from ...domain.calculations.registry.schema import RegistrySnapshot
from ...domain.iva.refund_eligibility import is_last_filing_period_of_year
from ...domain.iva.regimen_simplificado_rows import validate_regimen_simplificado_rows
from ...domain.modelos.calculation_revision import FilingInstanceEvidence
from ...domain.modelos.calculation_revision_m303_handoff import M303FilingInstanceEvidence
from ...domain.modelos.work_unit import WorkUnit
from ..calculations.m303_regimen_simplificado import calculate_m303_regimen_simplificado_result
from ._m303_regimen_simplificado_scope import (
    active_taxpayer_profile,
    m303_regimen_simplificado_scope_for_profile,
)
from .action_errors import M303FilingEvidenceError
from .preconditions import ModeloPreconditionFailure, build_modelo_precondition_failure_for_scenario

_EVIDENCE_SUBJECT_LEAF_KEY = "modelo.work.calculate"
_EVIDENCE_SCENARIO_PREFIX = "modelo.work.calculate.m303_filing_evidence"


def m303_filing_evidence_failure(
    scenario_code: str,
    evidence_values: Mapping[str, str | int | bool | Decimal],
) -> ModeloPreconditionFailure:
    """Return the declared failure for one Modelo 303 filing-evidence scenario.

    The scenario identity resolves its own condition and recovery from the
    declared catalogue, so this producer supplies only the observed facts and
    never an action or a rendered explanation of its own.
    """
    return build_modelo_precondition_failure_for_scenario(
        subject_leaf_key=_EVIDENCE_SUBJECT_LEAF_KEY,
        scenario_id=f"{_EVIDENCE_SCENARIO_PREFIX}.{scenario_code}",
        evidence_id=f"{_EVIDENCE_SCENARIO_PREFIX}.{scenario_code}.observation",
        evidence_values=evidence_values,
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
    )


def validate_m303_filing_instance_evidence_for_revision(
    *,
    work_unit: WorkUnit,
    registry_snapshot: RegistrySnapshot,
    evidence: FilingInstanceEvidence | None,
    casilla_values: Mapping[CasillaId, Decimal],
    observations: Sequence[CasillaObservation],
) -> FilingInstanceEvidence | None:
    """Validate the complete revision evidence against every canonical owner."""
    if work_unit.modelo != Modelo.M303:
        if evidence is not None:
            raise M303FilingEvidenceError(
                precondition_failure=m303_filing_evidence_failure(
                    "unsupported_modelo",
                    {"modelo": str(work_unit.modelo), "evidence_present": True},
                ),
            )
        return None
    if evidence is None:
        raise M303FilingEvidenceError(
            precondition_failure=m303_filing_evidence_failure(
                "missing",
                {"modelo": str(work_unit.modelo), "evidence_present": False},
            ),
        )
    m303 = evidence.m303
    if m303.period != work_unit.period:
        raise M303FilingEvidenceError(
            precondition_failure=m303_filing_evidence_failure(
                "period_mismatch",
                {
                    "work_unit_period": work_unit.period.registry_token,
                    "evidence_period": m303.period.registry_token,
                    "periods_match": False,
                },
            ),
        )

    _validate_m303_simplified_filing_evidence(
        work_unit=work_unit,
        registry_snapshot=registry_snapshot,
        evidence=m303,
    )
    _validate_m303_exonerado_filing_evidence(
        work_unit=work_unit,
        registry_snapshot=registry_snapshot,
        evidence=m303,
        casilla_values=casilla_values,
        observations=observations,
    )
    return evidence


def _validate_m303_simplified_filing_evidence(
    *,
    work_unit: WorkUnit,
    registry_snapshot: RegistrySnapshot,
    evidence: M303FilingInstanceEvidence,
) -> None:
    """Validate the simplified-regime evidence against profile and rows."""
    regimen = evidence.regimen_simplificado

    expected_snapshot = resolve_m303_regimen_simplificado_snapshot(
        registry_snapshot=registry_snapshot,
        scope_decision=regimen.scope_decision,
    )
    if regimen.regimen_snapshot != expected_snapshot:
        raise M303FilingEvidenceError(
            precondition_failure=m303_filing_evidence_failure(
                "regimen_snapshot_mismatch",
                {"snapshot_matches_scope_decision": False},
            ),
        )
    profile = active_taxpayer_profile(work_unit)
    if regimen.scope_decision != m303_regimen_simplificado_scope_for_profile(profile):
        raise M303FilingEvidenceError(
            precondition_failure=m303_filing_evidence_failure(
                "regimen_scope_profile_divergence",
                {"scope_decision_matches_censo_profile": False},
            ),
        )
    censo_iae_epigraphs: frozenset[str] = (
        frozenset({profile.iae_epigraph}) if profile.iae_epigraph else frozenset[str]()
    )
    validate_regimen_simplificado_rows(
        regimen.rows,
        orden=regimen.regimen_snapshot.orden.activities,
        agricultural_authority=regimen.regimen_snapshot.orden.agricultural_authority,
        applicable=not regimen.scope_decision.is_not_claimed,
        censo_iae_epigraphs=censo_iae_epigraphs,
    )
    expected_result = calculate_m303_regimen_simplificado_result(
        period=evidence.period,
        scope_decision=regimen.scope_decision,
        rows=regimen.rows,
        regimen_snapshot=regimen.regimen_snapshot,
        dana_2024_eligibility=regimen.dana_2024_eligibility,
        catalogues=bundled_authority().catalogues,
    )
    if regimen.calculation_result != expected_result:
        raise M303FilingEvidenceError(
            precondition_failure=m303_filing_evidence_failure(
                "simplified_calculation_result_divergence",
                {"calculation_result_matches_annual_orden": False},
            ),
        )


def _validate_m303_exonerado_filing_evidence(
    *,
    work_unit: WorkUnit,
    registry_snapshot: RegistrySnapshot,
    evidence: M303FilingInstanceEvidence,
    casilla_values: Mapping[CasillaId, Decimal],
    observations: Sequence[CasillaObservation],
) -> None:
    """Validate final-period A28 endpoints and their value/observation agreement."""
    exonerado = evidence.exonerado_390

    if exonerado.applicable and not is_last_filing_period_of_year(work_unit.period):
        raise M303FilingEvidenceError(
            precondition_failure=m303_filing_evidence_failure(
                "exonerado_390_not_final_period",
                {"applicable": True, "is_last_filing_period": False},
            ),
        )
    expected_ids = {
        casilla.id
        for casilla in registry_snapshot.revision.casillas
        if tuple(casilla.section)[:2] == ("iva", "exonerado_390")
    }
    actual_values = {endpoint.casilla_id: endpoint.value for endpoint in exonerado.endpoints}
    if exonerado.applicable:
        _validate_m303_exonerado_applicable_values(
            expected_ids=expected_ids,
            actual_values=actual_values,
            casilla_values=casilla_values,
            observations=observations,
        )
    elif actual_values:
        raise M303FilingEvidenceError(
            precondition_failure=m303_filing_evidence_failure(
                "exonerado_390_endpoints_on_non_applicable",
                {"applicable": False, "endpoint_count": len(actual_values)},
            ),
        )


def _validate_m303_exonerado_applicable_values(
    *,
    expected_ids: set[CasillaId],
    actual_values: Mapping[CasillaId, Decimal],
    casilla_values: Mapping[CasillaId, Decimal],
    observations: Sequence[CasillaObservation],
) -> None:
    """Require complete A28 endpoints and agreement with revision/observations."""
    if set(actual_values) != expected_ids:
        raise M303FilingEvidenceError(
            precondition_failure=m303_filing_evidence_failure(
                "exonerado_390_endpoint_coverage_incomplete",
                {"expected_endpoint_count": len(expected_ids), "declared_endpoint_count": len(actual_values)},
            ),
        )
    revision_values = {casilla_id: casilla_values.get(casilla_id) for casilla_id in expected_ids}
    if revision_values != actual_values:
        raise M303FilingEvidenceError(
            precondition_failure=m303_filing_evidence_failure(
                "exonerado_390_revision_value_divergence",
                {"values_match_revision": False, "endpoint_count": len(actual_values)},
            ),
        )
    observation_values = {
        observation.casilla_id: observation.value
        for observation in observations
        if observation.casilla_id in expected_ids
    }
    if observation_values != actual_values:
        raise M303FilingEvidenceError(
            precondition_failure=m303_filing_evidence_failure(
                "exonerado_390_observation_value_divergence",
                {"values_match_observations": False, "endpoint_count": len(actual_values)},
            ),
        )


__all__ = ["m303_filing_evidence_failure", "validate_m303_filing_instance_evidence_for_revision"]
