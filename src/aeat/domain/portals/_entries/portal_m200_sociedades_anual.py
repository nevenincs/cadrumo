"""Registry entry for Modelo 200 — annual corporate-income-tax self-assessment.

Defines the :class:`~aeat.domain.portals._metadata.PortalMetadata` record
exposed as :data:`ENTRY` and consumed by
:data:`aeat.domain.portals.PORTAL_REGISTRY` via
:mod:`aeat.domain.portals._registry`.
"""

from __future__ import annotations

from ...modelos import ModeloCode
from .._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from .._codes import Portal
from .._metadata import PortalMetadata
from ._common import build_entry

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_M200_SOCIEDADES_ANUAL,
    url="https://sede.agenciatributaria.gob.es/Sede/procedimientoini/GE04.shtml",
    subdomain=Subdomain.SEDE,
    category=PortalCategory.FILING,
    auth_methods=(
        AuthMethod.CERTIFICATE,
        AuthMethod.DNIE,
    ),
    url_stability=UrlStability.STABLE_PROTOCOL_GRADE,
    related_modelo=ModeloCode.MODELO_200,
    label="entries.portal_m200_sociedades_anual.label_979781",
    purpose_es="Autoliquidación anual del Impuesto sobre Sociedades.",
)
"""Portal entry for Modelo 200 (annual corporate-income-tax self-assessment)."""
