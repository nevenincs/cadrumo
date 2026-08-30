"""Catalogue entry for the *Modelo 115* urban-rental withholdings procedure.

Exposes :data:`ENTRY`, a :class:`PortalMetadata` record for
:class:`Portal` ``PORTAL_M115_RETENCIONES_ARRENDAMIENTOS`` under
:class:`PortalCategory` ``FILING``. Backs the periodic
self-assessment of withholdings on urban property lease income.
"""

from __future__ import annotations

from ..categories import AuthMethod, PortalCategory, PortalHost, UrlStability
from ..codes import Portal
from ..metadata import PortalMetadata
from .common import build_entry, portal_path

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_M115_RETENCIONES_ARRENDAMIENTOS,
    path=portal_path(Portal.PORTAL_M115_RETENCIONES_ARRENDAMIENTOS),
    subdomain=PortalHost.SEDE,
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
"""Frozen :class:`cadrumo.domain.portals.PortalMetadata` for the Modelo 115 procedure page."""
