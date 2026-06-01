"""Catalogue entry for the AEAT *Cl@ve PIN gestiones* self-service page.

Exposes :data:`ENTRY`, a frozen :class:`PortalMetadata` record identified
by the :class:`Portal` code ``PORTAL_CLAVE_GESTIONES`` under the
:class:`PortalCategory` member
:attr:`aeat.domain.portals.PortalCategory.AUTH`, covering password
registration, recovery, and renewal via Cl@ve permanente.
"""

from __future__ import annotations

from .._categories import AuthMethod, PortalCategory, PortalHost, UrlStability
from .._codes import Portal
from .._metadata import PortalMetadata
from ._common import build_entry

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_CLAVE_GESTIONES,
    path="/Sede/clave-pin/gestiones.html",
    subdomain=PortalHost.SEDE,
    category=PortalCategory.AUTH,
    auth_methods=(AuthMethod.CLAVE_PERMANENTE,),
    url_stability=UrlStability.STABLE_WITHIN_CAMPAIGN,
    label="entries.portal_clave_gestiones.label",
    purpose="entries.portal_clave_gestiones.purpose",
)
"""Frozen :class:`aeat.domain.portals.PortalMetadata` for the Cl@ve self-service page."""
