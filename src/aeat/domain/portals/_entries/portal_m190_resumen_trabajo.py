"""Registry entry for Modelo 190 — annual summary of labour withholdings.

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
    portal=Portal.PORTAL_M190_RESUMEN_TRABAJO,
    url="https://sede.agenciatributaria.gob.es/Sede/procedimientoini/GI10.shtml",
    subdomain=Subdomain.SEDE,
    category=PortalCategory.FILING,
    auth_methods=(
        AuthMethod.CERTIFICATE,
        AuthMethod.CLAVE_PIN,
        AuthMethod.CLAVE_PERMANENTE,
        AuthMethod.DNIE,
    ),
    url_stability=UrlStability.STABLE_PROTOCOL_GRADE,
    related_modelo=ModeloCode.MODELO_190,
    label="entries.portal_m190_resumen_trabajo.label_059630",
    purpose_es=(
        "Resumen anual de retenciones e ingresos a cuenta sobre trabajo y actividades (complementa al Modelo 111)."
    ),
)
"""Portal entry for Modelo 190 (annual summary of labour withholdings)."""
