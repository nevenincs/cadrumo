"""Catalogue entry for the *Modelo 111* withholdings procedure page.

Exposes :data:`ENTRY`, a frozen :class:`PortalMetadata` record identified
by the :class:`Portal` code ``PORTAL_M111_RETENCIONES_TRABAJO`` under
the :class:`PortalCategory` member
:attr:`cadrumo.domain.portals.PortalCategory.FILING`. Backs the periodic
self-assessment of withholdings and on-account payments on labour income
and economic activities.
"""

from __future__ import annotations

from ..categories import AuthMethod, PortalCategory, PortalHost, UrlStability
from ..codes import Portal
from ..metadata import PortalMetadata
from .common import build_entry, portal_path

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_M111_RETENCIONES_TRABAJO,
    path=portal_path(Portal.PORTAL_M111_RETENCIONES_TRABAJO),
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
    label="entries.portal_m111_retenciones_trabajo.label",
    purpose="entries.portal_m111_retenciones_trabajo.purpose",
)
"""Frozen :class:`cadrumo.domain.portals.PortalMetadata` for the Modelo 111 procedure page."""
