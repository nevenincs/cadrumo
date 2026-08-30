"""Registry entry for Modelo 369 - OSS / IOSS one-stop-shop return.

Defines the :class:`PortalMetadata` record for :class:`Portal`
``PORTAL_M369_OSS_IOSS`` under :class:`PortalCategory` ``FILING``,
exposed as :data:`ENTRY` and consumed by
:data:`cadrumo.domain.portals.PORTAL_REGISTRY`.
"""

from __future__ import annotations

from ..categories import AuthMethod, PortalCategory, PortalHost, UrlStability
from ..codes import Portal
from ..metadata import PortalMetadata
from .common import build_entry, portal_path

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_M369_OSS_IOSS,
    path=portal_path(Portal.PORTAL_M369_OSS_IOSS),
    subdomain=PortalHost.SEDE,
    category=PortalCategory.FILING,
    auth_methods=(
        AuthMethod.CERTIFICATE,
        AuthMethod.DNIE,
    ),
    url_stability=UrlStability.STABLE_PROTOCOL_GRADE,
    label="entries.portal_m369_oss_ioss.label",
    purpose="entries.portal_m369_oss_ioss.purpose",
)
"""Portal entry for Modelo 369 (OSS / IOSS one-stop-shop IVA return)."""
