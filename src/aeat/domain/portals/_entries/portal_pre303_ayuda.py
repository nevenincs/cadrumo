"""Registry entry for the Pre303 pre-filled IVA helper service.

Defines the :class:`PortalMetadata` record for :class:`Portal`
``PORTAL_PRE303_AYUDA`` under :class:`PortalCategory` ``BORRADOR``,
exposed as :data:`ENTRY` and consumed by
:data:`aeat.domain.portals.PORTAL_REGISTRY`.
"""

from __future__ import annotations

from ....core.config import Settings
from .._categories import AuthMethod, PortalCategory, PortalHost, UrlStability
from .._codes import Portal
from .._metadata import PortalMetadata
from ._common import build_entry

_PRE303 = Settings.external_constants().aeat.pre303

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_PRE303_AYUDA,
    path=_PRE303.presentation_service_path,
    subdomain=PortalHost.WWW1,
    category=PortalCategory.BORRADOR,
    auth_methods=(
        AuthMethod.CERTIFICATE,
        AuthMethod.DNIE,
        AuthMethod.CLAVE_PIN,
    ),
    url_stability=UrlStability.STABLE_WITHIN_CAMPAIGN,
    label="entries.portal_pre303_ayuda.label",
    purpose="entries.portal_pre303_ayuda.purpose",
)
"""Portal entry for the Pre303 pre-filled IVA helper (Modelo 303 borrador)."""
