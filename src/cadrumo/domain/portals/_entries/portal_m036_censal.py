"""Catalogue entry for the *Modelo 036* censo-declaration procedure page.

Exposes :data:`ENTRY`, a frozen :class:`PortalMetadata` record identified
by the :class:`Portal` code ``PORTAL_M036_CENSAL`` under the
:class:`PortalCategory` member
:attr:`cadrumo.domain.portals.PortalCategory.CENSO`. Covers registration,
modification, and deregistration on the censo of entrepreneurs,
professionals, and withholders.
"""

from __future__ import annotations

from ..categories import AuthMethod, PortalCategory, PortalHost, UrlStability
from ..codes import Portal
from ..metadata import PortalMetadata
from .common import build_entry, portal_path

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_M036_CENSAL,
    path=portal_path(Portal.PORTAL_M036_CENSAL),
    subdomain=PortalHost.SEDE,
    category=PortalCategory.CENSO,
    auth_methods=(
        AuthMethod.CERTIFICATE,
        AuthMethod.CLAVE_PIN,
        AuthMethod.CLAVE_PERMANENTE,
        AuthMethod.CLAVE_MOVIL,
        AuthMethod.DNIE,
    ),
    url_stability=UrlStability.STABLE_PROTOCOL_GRADE,
    label="entries.portal_m036_censal.label",
    purpose="entries.portal_m036_censal.purpose",
)
"""Frozen :class:`cadrumo.domain.portals.PortalMetadata` for the Modelo 036 censo procedure page."""
