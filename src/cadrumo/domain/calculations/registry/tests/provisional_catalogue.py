"""Fixture projections of the canonical prorrata vocabulary."""

from __future__ import annotations

from datetime import date

from .....core.prorrata_register import ProrrataProvisionalProvenance
from ..governed_fact_scope import GovernedFactSource
from ..prorrata_register_catalogue import resolve_prorrata_register_catalogue


def aeat_autorizada_prorrata_provenance(
    *, effective_date: date | None = None, authority: GovernedFactSource | None = None
) -> ProrrataProvisionalProvenance:
    """Return the registry-declared AEAT-authorised provenance token."""
    return resolve_prorrata_register_catalogue(
        effective_date=effective_date, authority=authority
    ).aeat_autorizada_provenance


def inicio_actividad_prorrata_provenance(
    *, effective_date: date | None = None, authority: GovernedFactSource | None = None
) -> ProrrataProvisionalProvenance:
    """Return the registry-declared start-of-activity provenance token."""
    return resolve_prorrata_register_catalogue(
        effective_date=effective_date, authority=authority
    ).inicio_actividad_provenance
