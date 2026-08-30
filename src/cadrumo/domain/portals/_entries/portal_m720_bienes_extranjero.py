"""Registry entry for Modelo 720 - foreign assets and rights informational return.

Defines the :class:`PortalMetadata` record for :class:`Portal`
``PORTAL_M720_BIENES_EXTRANJERO`` under :class:`PortalCategory`
``FILING``, exposed as :data:`ENTRY` and consumed by
:data:`cadrumo.domain.portals.PORTAL_REGISTRY`.
"""

from __future__ import annotations

from ..categories import AuthMethod, PortalCategory, PortalHost, UrlStability
from ..codes import Portal
from ..metadata import PortalMetadata
from .common import build_entry, portal_path

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_M720_BIENES_EXTRANJERO,
    path=portal_path(Portal.PORTAL_M720_BIENES_EXTRANJERO),
    subdomain=PortalHost.SEDE,
    category=PortalCategory.FILING,
    auth_methods=(
        AuthMethod.CERTIFICATE,
        AuthMethod.CLAVE_PIN,
        AuthMethod.CLAVE_PERMANENTE,
        AuthMethod.DNIE,
    ),
    url_stability=UrlStability.STABLE_PROTOCOL_GRADE,
    label="entries.portal_m720_bienes_extranjero.label",
    purpose="entries.portal_m720_bienes_extranjero.purpose",
)
"""Portal entry for Modelo 720 (foreign assets and rights informational return)."""
