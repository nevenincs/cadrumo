"""Registry entry for Modelo 232 - related-party transactions return.

Defines the :class:`PortalMetadata` record for :class:`Portal`
``PORTAL_M232_VINCULADAS`` under :class:`PortalCategory` ``FILING``,
exposed as :data:`ENTRY` and consumed by
:data:`cadrumo.domain.portals.PORTAL_REGISTRY`.
"""

from __future__ import annotations

from ..categories import AuthMethod, PortalCategory, PortalHost, UrlStability
from ..codes import Portal
from ..metadata import PortalMetadata
from .common import build_entry, portal_path

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_M232_VINCULADAS,
    path=portal_path(Portal.PORTAL_M232_VINCULADAS),
    subdomain=PortalHost.SEDE,
    category=PortalCategory.FILING,
    auth_methods=(
        AuthMethod.CERTIFICATE,
        AuthMethod.DNIE,
    ),
    url_stability=UrlStability.STABLE_PROTOCOL_GRADE,
    label="entries.portal_m232_vinculadas.label",
    purpose="entries.portal_m232_vinculadas.purpose",
)
"""Portal entry for Modelo 232 (related-party and tax-haven transactions)."""
