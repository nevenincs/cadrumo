"""Registry entry for the Pre303 pre-filled VAT helper service.

Defines the :class:`~aeat.domain.portals._metadata.PortalMetadata` record
exposed as :data:`ENTRY` and consumed by
:data:`aeat.domain.portals.PORTAL_REGISTRY` via
:mod:`aeat.domain.portals._registry`.
"""

from __future__ import annotations

from .._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from .._codes import Portal
from .._metadata import PortalMetadata
from ._common import build_entry

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_PRE303_AYUDA,
    url="https://sede.agenciatributaria.gob.es/Sede/iva/autoliquidacion-iva-modelo-303/pre303.html",
    subdomain=Subdomain.SEDE,
    category=PortalCategory.BORRADOR,
    auth_methods=(
        AuthMethod.CERTIFICATE,
        AuthMethod.CLAVE_PERMANENTE,
    ),
    url_stability=UrlStability.STABLE_WITHIN_CAMPAIGN,
    label="entries.portal_pre303_ayuda.label_935129",
    purpose="entries.portal_pre303_ayuda.purpose",
)
"""Portal entry for the Pre303 pre-filled VAT helper (Modelo 303 borrador)."""
