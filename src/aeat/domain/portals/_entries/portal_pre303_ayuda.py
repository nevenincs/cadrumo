"""Registry entry for the Pre303 pre-filled VAT helper service.

Defines the :class:`~aeat.domain.portals._metadata.PortalMetadata` record
exposed as :data:`ENTRY` and consumed by
:data:`aeat.domain.portals.PORTAL_REGISTRY` via
:mod:`aeat.domain.portals._registry`.
"""

from __future__ import annotations

from ....core.config import Settings
from .._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from .._codes import Portal
from .._metadata import PortalMetadata
from ._common import build_entry

_PRE303 = Settings.external_constants().aeat.pre303

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_PRE303_AYUDA,
    path=_PRE303.presentation_service_path,
    subdomain=Subdomain.WWW1,
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
"""Portal entry for the Pre303 pre-filled VAT helper (Modelo 303 borrador)."""
