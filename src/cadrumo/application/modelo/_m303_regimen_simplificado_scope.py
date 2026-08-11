"""Secure-profile scope resolution for the M303 simplified-regime branch."""

from __future__ import annotations

from ...core import Modelo
from ...domain.deadlines import M303RegimeComposition, TaxpayerProfile
from ...domain.iva import M303RegimenSimplificadoScope, M303RegimenSimplificadoScopeDecision
from ...domain.modelos import WorkUnit
from ...domain.user_profile import ProfileNotFoundError, UserProfileStatus
from ..user_profile import UserProfileLifecycleRepository, projection_for_taxpayer
from ._action_errors import ModeloProfileReadinessError


def resolve_m303_regimen_simplificado_scope(
    work_unit: WorkUnit,
) -> M303RegimenSimplificadoScopeDecision | None:
    """Derive the closed scope from the active secure profile's IVA composition only."""
    if work_unit.modelo != Modelo.M303:
        return None
    try:
        record = UserProfileLifecycleRepository(bucket_id=work_unit.bucket_id).load(work_unit.bucket_id)
    except ProfileNotFoundError as exc:
        raise ModeloProfileReadinessError("Modelo 303 requires an active secure profile") from exc
    if record.status is not UserProfileStatus.ACTIVE:
        raise ModeloProfileReadinessError("Modelo 303 requires an active secure profile")
    return m303_regimen_simplificado_scope_for_profile(projection_for_taxpayer(record))


def m303_regimen_simplificado_scope_for_profile(
    profile: TaxpayerProfile,
) -> M303RegimenSimplificadoScopeDecision:
    """Map the canonical secure IVA profile composition to the closed S59 scope."""
    iva_profile = profile.iva
    if iva_profile is None:
        raise ModeloProfileReadinessError("Modelo 303 requires a complete IVA profile composition")
    composition = iva_profile.regime_composition
    if composition is M303RegimeComposition.GENERAL:
        scope = M303RegimenSimplificadoScope.REGIMEN_SIMPLIFICADO_NOT_CLAIMED
    elif composition in {M303RegimeComposition.SIMPLIFIED, M303RegimeComposition.MIXED}:
        scope = M303RegimenSimplificadoScope.REGIMEN_SIMPLIFICADO_EVIDENCE_REQUIRED
    else:
        raise ModeloProfileReadinessError("Modelo 303 IVA regime composition is unknown")
    return M303RegimenSimplificadoScopeDecision(
        scope=scope,
    )


__all__ = [
    "m303_regimen_simplificado_scope_for_profile",
    "resolve_m303_regimen_simplificado_scope",
]
