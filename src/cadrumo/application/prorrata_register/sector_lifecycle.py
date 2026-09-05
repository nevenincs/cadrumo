"""Per-sector provisional/definitive lifecycle (LIVA arts. 9.1.c / 101 / 105).

A taxpayer with differentiated sectors applies the deduction regime separately
per sector (art. 101.Uno). Each sector therefore runs the same cross-period
lifecycle the whole-entity register runs — seed the year's provisional from the
prior year's definitive (art. 105.Uno), apportion in-year (the sector-aware
ledger IVA aggregation), and regularise at 4T against the year's definitive
(art. 105.Cuatro) — but scoped to the sector's own ``(ejercicio, sector_id)``
register entries.

The one place a sector's lifecycle diverges from the whole-entity one is the
seed SOURCE. The whole-entity carried seed reads the prior-year Modelo 303
settlement observation (:func:`seed_carried_prior_definitiva_entry`), but a
sectorized taxpayer files one whole-entity Modelo 303 that carries a single
percentage — it cannot supply a per-sector definitive. A sector's prior-year
definitive lives in the register's own ``(ejercicio-1, sector_id)`` entry
(written back at that year's settlement), so the per-sector carried seed reads
the register, not the observation catalogue.

See Also:
    :func:`~application.prorrata_register.seed_carried_prior_definitiva_entry`
        Whole-entity carried seed sourced from the prior Modelo 303 observation.
    :func:`~application.calculations._prorrata_regularizacion.build_interrumpida_tres_ultimos_seed`
        The art. 105.Cinco interrupted-activity seed, already sector-parameterised.
    :func:`~domain.iva.compute_prorrata_definitiva_anual`
        Pure substrate that computes the year-end definitive percentage from the
        sector's full-year operation volumes.
"""

from __future__ import annotations

from decimal import Decimal

from ...core.prorrata_register import ProrrataProvisionalProvenance, ProrrataRegisterRegime
from ...domain.iva.prorrata import ProrrataInputs, compute_prorrata_definitiva_anual
from ...domain.prorrata_register.register import ProrrataRegister, ProrrataRegisterEntry


def seed_sector_carried_definitive_from_register(
    register: ProrrataRegister,
    *,
    ejercicio: int,
    sector_id: str,
    regime: ProrrataRegisterRegime = ProrrataRegisterRegime.GENERAL,
) -> ProrrataRegisterEntry | None:
    """Seed a sector's current-year provisional from its own prior-year definitive.

    LIVA art. 105.Uno applied per differentiated sector (art. 101.Uno): the
    provisional percentage a sector applies during the year is that sector's
    prior-year DEFINITIVE, read from the register's own
    ``(ejercicio - 1, sector_id)`` entry. The whole-entity Modelo 303 observation
    is not consulted — it carries a single filing percentage and cannot supply a
    per-sector definitive.

    Returns ``None`` when the prior year holds no settled definitive for the
    sector (the caller surfaces the missing-provisional advisory rather than
    assuming a percentage rather than under-declaring in silence), so a sector's
    first ejercicio, or a gap year, never silently defaults.

    Args:
        register: The active-profile prorrata register.
        ejercicio: Ejercicio whose per-sector provisional is being seeded.
        sector_id: The differentiated sector to seed.
        regime: Prorrata regime in force for the sector this ejercicio.

    Returns:
        A seeded :class:`ProrrataRegisterEntry` carrying the sector's provisional
        percentage with ``CARRIED_PRIOR_DEFINITIVA`` provenance, or ``None``.
    """
    prior = register.entry_for(ejercicio - 1, sector_id=sector_id)
    if prior is None or prior.definitive_percentage is None:
        return None
    return ProrrataRegisterEntry(
        ejercicio=ejercicio,
        regime=regime,
        especial_transition=None,
        sector_id=sector_id,
        provisional_percentage=prior.definitive_percentage,
        provisional_provenance=ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
        source_observation_ref=f"prorrata-register:{ejercicio - 1}:{sector_id}",
    )


def settle_sector_definitive(
    entry: ProrrataRegisterEntry,
    *,
    con_derecho_volume: Decimal,
    sin_derecho_volume: Decimal,
) -> ProrrataRegisterEntry:
    """Compute a sector's year-end definitive from its own volumes and settle it.

    LIVA art. 105.Cuatro applied per differentiated sector: the definitive
    percentage is derived from the sector's OWN full-year operation volumes
    (con-derecho / sin-derecho, art. 104 exclusions already applied) via
    :func:`~domain.iva.compute_prorrata_definitiva_anual`, then written back onto
    the sector's register entry. The provisional fields are preserved so the
    annual regularización can compare the provisional applied in-year against the
    definitive.

    Args:
        entry: The sector's ``(ejercicio, sector_id)`` register entry to settle.
        con_derecho_volume: The sector's annual con-derecho operations volume.
        sin_derecho_volume: The sector's annual sin-derecho operations volume.

    Returns:
        A copy of ``entry`` with the definitive percentage and both volume inputs
        populated (the settled state the next year's carried seed reads).
    """
    definitiva = compute_prorrata_definitiva_anual(
        ProrrataInputs(
            operaciones_con_derecho_deduccion=con_derecho_volume,
            operaciones_sin_derecho_deduccion=sin_derecho_volume,
        ),
        year=entry.ejercicio,
        sector_id=entry.sector_id,
    )
    return entry.model_copy(
        update={
            "definitive_percentage": definitiva.percentage,
            "definitive_volume_con_derecho": con_derecho_volume,
            "definitive_volume_sin_derecho": sin_derecho_volume,
        },
    )


__all__ = [
    "seed_sector_carried_definitive_from_register",
    "settle_sector_definitive",
]
