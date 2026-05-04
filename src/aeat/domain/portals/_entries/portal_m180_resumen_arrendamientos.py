"""Registry entry for Modelo 180 — annual summary of rental withholdings.

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
    portal=Portal.PORTAL_M180_RESUMEN_ARRENDAMIENTOS,
    url="https://sede.agenciatributaria.gob.es/Sede/procedimientoini/GI00.shtml",
    subdomain=Subdomain.SEDE,
    category=PortalCategory.FILING,
    auth_methods=(
        AuthMethod.CERTIFICATE,
        AuthMethod.CLAVE_PIN,
        AuthMethod.CLAVE_PERMANENTE,
        AuthMethod.DNIE,
    ),
    url_stability=UrlStability.STABLE_PROTOCOL_GRADE,
    related_modelo=ModeloCode.MODELO_180,
    label="entries.portal_m180_resumen_arrendamientos.label_962375",
    purpose_es=(
        "Resumen anual de retenciones e ingresos a cuenta sobre "
        "arrendamientos de inmuebles urbanos (complementa al Modelo 115)."
    ),
)
"""Portal entry for Modelo 180 (annual summary of rental withholdings)."""
