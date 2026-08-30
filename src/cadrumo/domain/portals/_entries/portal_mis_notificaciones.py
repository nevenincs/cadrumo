"""Registry entry for the AEAT electronic notifications mailbox.

Defines the :class:`PortalMetadata` record for :class:`Portal`
``PORTAL_MIS_NOTIFICACIONES`` under :class:`PortalCategory`
``CONSULTATION``, exposed as :data:`ENTRY` and consumed by
:data:`cadrumo.domain.portals.PORTAL_REGISTRY`.
"""

from __future__ import annotations

from ..categories import AuthMethod, PortalCategory, PortalHost, UrlStability
from ..codes import Portal
from ..metadata import PortalMetadata
from .common import build_entry, portal_path

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_MIS_NOTIFICACIONES,
    path=portal_path(Portal.PORTAL_MIS_NOTIFICACIONES),
    subdomain=PortalHost.SEDE,
    category=PortalCategory.CONSULTATION,
    auth_methods=(
        AuthMethod.CERTIFICATE,
        AuthMethod.CLAVE_PIN,
        AuthMethod.CLAVE_PERMANENTE,
        AuthMethod.DNIE,
    ),
    url_stability=UrlStability.STABLE_WITHIN_CAMPAIGN,
    label="entries.portal_mis_notificaciones.label",
    purpose="entries.portal_mis_notificaciones.purpose",
)
"""Portal entry for the AEAT electronic notifications and communications mailbox."""
