"""Secure-profile scope resolution for the M303 simplified-regime branch."""

from __future__ import annotations

from collections.abc import Mapping

from ...core.modelo import Modelo
from ...core.operator_action_enums import ActionEvidenceProvenance
from ...domain.deadlines.models import M303RegimeComposition, TaxpayerProfile
from ...domain.iva.regimen_simplificado_rows import M303RegimenSimplificadoScope, M303RegimenSimplificadoScopeDecision
from ...domain.modelos.work_unit import WorkUnit
from ...domain.user_profile.errors import ProfileNotFoundError
from ...domain.user_profile.values import ProfileSetupState
from ..user_profile.profile_record_repository import ProfileRecordRepository
from ..user_profile.projections import projection_for_taxpayer
from .action_errors import ModeloProfileReadinessError
from .preconditions import ModeloPreconditionFailure, build_modelo_precondition_failure_for_scenario

_READINESS_SUBJECT_LEAF_KEY = "modelo.work.calculate"
_READINESS_SCENARIO_PREFIX = "modelo.work.calculate.m303_profile_readiness"


def m303_profile_readiness_failure(
    scenario_code: str,
    evidence_values: Mapping[str, str | int | bool],
) -> ModeloPreconditionFailure:
    """Return the declared failure for one Modelo 303 profile-readiness scenario."""
    return build_modelo_precondition_failure_for_scenario(
        subject_leaf_key=_READINESS_SUBJECT_LEAF_KEY,
        scenario_id=f"{_READINESS_SCENARIO_PREFIX}.{scenario_code}",
        evidence_id=f"{_READINESS_SCENARIO_PREFIX}.{scenario_code}.observation",
        evidence_values=evidence_values,
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
    )


def active_taxpayer_profile(work_unit: WorkUnit) -> TaxpayerProfile:
    """Return the work unit's active, setup-complete taxpayer profile, or raise."""
    try:
        record = ProfileRecordRepository.for_current_session(work_unit.bucket_id).load(work_unit.bucket_id)
    except ProfileNotFoundError as exc:
        raise ModeloProfileReadinessError(
            precondition_failure=m303_profile_readiness_failure("profile_absent", {"profile_present": False}),
        ) from exc
    if record.setup_state is not ProfileSetupState.COMPLETE:
        raise ModeloProfileReadinessError(
            precondition_failure=m303_profile_readiness_failure(
                "profile_inactive",
                {"profile_present": True, "profile_setup_state": str(record.setup_state)},
            ),
        )
    return projection_for_taxpayer(record)


def resolve_m303_regimen_simplificado_scope(
    work_unit: WorkUnit,
) -> M303RegimenSimplificadoScopeDecision | None:
    """Derive the closed scope from the active secure profile's IVA composition only."""
    if work_unit.modelo != Modelo.M303:
        return None
    return m303_regimen_simplificado_scope_for_profile(active_taxpayer_profile(work_unit))


def m303_regimen_simplificado_scope_for_profile(
    profile: TaxpayerProfile,
) -> M303RegimenSimplificadoScopeDecision:
    """Map the canonical secure IVA profile composition to the closed simplified-regime scope."""
    iva_profile = profile.iva
    if iva_profile is None:
        raise ModeloProfileReadinessError(
            precondition_failure=m303_profile_readiness_failure(
                "iva_composition_missing",
                {"iva_profile_present": False},
            ),
        )
    return m303_regimen_simplificado_scope_for_composition(iva_profile.regime_composition)


def m303_regimen_simplificado_scope_for_composition(
    composition: M303RegimeComposition | str,
) -> M303RegimenSimplificadoScopeDecision:
    """Map one canonical or serialized IVA composition to the closed scope."""
    if composition is M303RegimeComposition.GENERAL:
        scope = M303RegimenSimplificadoScope.REGIMEN_SIMPLIFICADO_NOT_CLAIMED
    elif composition in {M303RegimeComposition.SIMPLIFIED, M303RegimeComposition.MIXED}:
        scope = M303RegimenSimplificadoScope.REGIMEN_SIMPLIFICADO_EVIDENCE_REQUIRED
    else:
        raise ModeloProfileReadinessError(
            precondition_failure=m303_profile_readiness_failure(
                "iva_composition_unknown",
                {"iva_profile_present": True, "regime_composition": str(composition)},
            ),
        )
    return M303RegimenSimplificadoScopeDecision(
        scope=scope,
    )


def m303_regimen_simplificado_annual_summary_applies(work_unit: WorkUnit) -> bool:
    """Return whether regimen simplificado reaches this work unit's taxpayer.

    The single derivation the Modelo 390 annual-summary guard, resolver, and
    persisted-handoff validator all consult, so one taxpayer cannot be judged
    applicable by one and not another. Boxes 74--83 ride on every Modelo 390
    form, so a revision declaring that binding family says what the FORM
    carries and never that the regime reaches this filer: LIVA art. 122 Uno
    applies regimen simplificado only to sujetos pasivos meeting its three
    stated requirements.
    """
    return not m303_regimen_simplificado_scope_for_profile(active_taxpayer_profile(work_unit)).is_not_claimed


__all__ = [
    "active_taxpayer_profile",
    "m303_regimen_simplificado_annual_summary_applies",
    "m303_regimen_simplificado_scope_for_composition",
    "m303_regimen_simplificado_scope_for_profile",
    "resolve_m303_regimen_simplificado_scope",
]
