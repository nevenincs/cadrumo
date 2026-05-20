"""Catalogue entry for the *Modelo 115* urban-rental withholdings procedure.

Exposes :data:`ENTRY`, a frozen :class:`aeat.domain.portals.PortalMetadata`
under :attr:`aeat.domain.portals.PortalCategory.FILING`. Backs the periodic
self-assessment of withholdings and on-account payments on income from
urban property leases.
"""

from __future__ import annotations

from .._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from .._codes import Portal
from .._metadata import PortalMetadata
from ._common import build_entry

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_M115_RETENCIONES_ARRENDAMIENTOS,
    path="/Sede/procedimientoini/GH02.shtml",
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
    label="entries.portal_m115_retenciones_arrendamientos.label",
    purpose="entries.portal_m115_retenciones_arrendamientos.purpose",
)
"""Frozen :class:`aeat.domain.portals.PortalMetadata` for the Modelo 115 procedure page."""
