"""Registry entry for the AEAT Sede Electronica root landing page.

Defines the :class:`PortalMetadata` record for :class:`Portal`
``PORTAL_SEDE_ROOT`` under :class:`PortalCategory` ``AUTH``, exposed
as :data:`ENTRY` and consumed by
:data:`aeat.domain.portals.PORTAL_REGISTRY`.
"""

from __future__ import annotations

from .._categories import AuthMethod, PortalCategory, PortalHost, UrlStability
from .._codes import Portal
from .._metadata import PortalMetadata
from ._common import build_entry, portal_path

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_SEDE_ROOT,
    path=portal_path(Portal.PORTAL_SEDE_ROOT),
    subdomain=PortalHost.SEDE,
    category=PortalCategory.AUTH,
    auth_methods=(AuthMethod.ANONYMOUS,),
    url_stability=UrlStability.STABLE_PROTOCOL_GRADE,
    label="entries.portal_sede_root.label",
    purpose="entries.portal_sede_root.purpose",
)
"""Portal entry for the Sede Electrónica root URL."""
