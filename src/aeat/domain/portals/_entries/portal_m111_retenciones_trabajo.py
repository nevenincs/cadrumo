"""Catalogue entry for the *Modelo 111* withholdings procedure page.

Exposes :data:`ENTRY`, a frozen :class:`aeat.domain.portals.PortalMetadata`
under :attr:`aeat.domain.portals.PortalCategory.FILING`. Backs the periodic
self-assessment of withholdings and on-account payments on labour income
and economic activities.
"""

from __future__ import annotations

from .._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from .._codes import Portal
from .._metadata import PortalMetadata
from ._common import build_entry

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_M111_RETENCIONES_TRABAJO,
    url="https://sede.agenciatributaria.gob.es/Sede/procedimientoini/GH01.shtml",
    subdomain=Subdomain.SEDE,
    category=PortalCategory.FILING,
    auth_methods=(
        AuthMethod.CERTIFICATE,
        AuthMethod.CLAVE_PIN,
        AuthMethod.CLAVE_PERMANENTE,
        AuthMethod.CLAVE_MOVIL,
        AuthMethod.DNIE,
    ),
    url_stability=UrlStability.STABLE_PROTOCOL_GRADE,
    label="entries.portal_m111_retenciones_trabajo.label_774262",
    purpose_es=(
        "Autoliquidación periódica de retenciones e ingresos a cuenta "
        "sobre rendimientos del trabajo y actividades económicas."
    ),
)
"""Frozen :class:`aeat.domain.portals.PortalMetadata` for the Modelo 111 procedure page."""
