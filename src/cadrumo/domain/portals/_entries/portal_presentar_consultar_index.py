"""Registry entry for the official submit-and-consult declarations index.

Defines the :class:`PortalMetadata` record identified by the :class:`Portal`
code ``PORTAL_PRESENTAR_CONSULTAR_INDEX``, exposed as :data:`ENTRY` under
the :class:`PortalCategory` member ``FILING``, consumed by
:data:`cadrumo.domain.portals.PORTAL_REGISTRY` via
:mod:`cadrumo.domain.portals.registry`.
"""

from __future__ import annotations

from ..categories import AuthMethod, PortalCategory, PortalHost, UrlStability
from ..codes import Portal
from ..metadata import PortalMetadata
from .common import build_entry, portal_path

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_PRESENTAR_CONSULTAR_INDEX,
    path=portal_path(Portal.PORTAL_PRESENTAR_CONSULTAR_INDEX),
    subdomain=PortalHost.SEDE,
    category=PortalCategory.CALENDAR_REFERENCE,
    auth_methods=(AuthMethod.ANONYMOUS,),
    url_stability=UrlStability.STABLE_PROTOCOL_GRADE,
    label="entries.portal_presentar_consultar_index.label",
    purpose="entries.portal_presentar_consultar_index.purpose",
)
"""Portal entry for the AEAT submit-and-consult declarations index."""
