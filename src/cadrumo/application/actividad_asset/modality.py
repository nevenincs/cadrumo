"""Map the taxpayer profile's IRPF estimation regime to a direct-estimation modality."""

from __future__ import annotations

from ...domain.calculations.registry.governed_fact_scope import GovernedFactSource
from ...domain.calculations.registry.irpf_regimes import (
    irpf_estimation_regime_directa_normal_token,
    irpf_estimation_regime_directa_simplificada_token,
)
from ...domain.renta.actividad_asset.election import DirectEstimationRegime
from ...domain.renta.actividad_asset.errors import ActividadAssetIncompleteError, ActividadAssetUnsupportedError


def direct_estimation_modality(profile_token: str | None, *, authority: GovernedFactSource) -> DirectEstimationRegime:
    """Resolve the profile's governed regime token, refusing anything but direct estimation.

    The modality is a taxpayer-wide fact (RIRPF art. 28.3), so an asset's
    election is judged against this value rather than trusted on its own.
    """
    token = (profile_token or "").strip()
    if not token:
        raise ActividadAssetIncompleteError(translated_message="ledger.actividad_asset.errors.modality_not_declared")
    modalities: dict[str, DirectEstimationRegime] = {
        str(irpf_estimation_regime_directa_normal_token(authority=authority)): DirectEstimationRegime.NORMAL,
        str(irpf_estimation_regime_directa_simplificada_token(authority=authority)): DirectEstimationRegime.SIMPLIFIED,
    }
    modality = modalities.get(token)
    if modality is None:
        raise ActividadAssetUnsupportedError(
            context={"regime": token},
            translated_message="ledger.actividad_asset.errors.modality_not_direct_estimation",
        )
    return modality


__all__ = ["direct_estimation_modality"]
