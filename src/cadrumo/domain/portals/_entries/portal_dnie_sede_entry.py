"""Catalogue entry for the AEAT Sede DNI electrónico (DNIe) entry point.

Exposes :data:`ENTRY`, a :class:`PortalMetadata` record for
:class:`Portal` ``PORTAL_DNIE_SEDE_ENTRY`` under
:class:`PortalCategory` ``AUTH``. Reuses the shared certificate
gateway for credential exchange.
"""

from __future__ import annotations

from ..categories import AuthMethod, PortalCategory, PortalHost, UrlStability
from ..codes import Portal
from ..metadata import PortalMetadata
from .common import build_entry, portal_path

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_DNIE_SEDE_ENTRY,
    path=portal_path(Portal.PORTAL_DNIE_SEDE_ENTRY),
    subdomain=PortalHost.SEDE,
    category=PortalCategory.AUTH,
    auth_methods=(AuthMethod.DNIE,),
    url_stability=UrlStability.STABLE_WITHIN_CAMPAIGN,
    label="entries.portal_dnie_sede_entry.label",
    purpose="entries.portal_dnie_sede_entry.purpose",
)
"""Frozen :class:`cadrumo.domain.portals.PortalMetadata` for the DNIe Sede entry page."""
