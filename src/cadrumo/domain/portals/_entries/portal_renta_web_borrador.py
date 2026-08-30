"""Registry entry for Renta Web - IRPF pre-filled draft (borrador).

Defines the :class:`PortalMetadata` record for :class:`Portal`
``PORTAL_RENTA_WEB_BORRADOR`` under :class:`PortalCategory`
``BORRADOR``, exposed as :data:`ENTRY` and consumed by
:data:`cadrumo.domain.portals.PORTAL_REGISTRY`.
"""

from __future__ import annotations

from ..categories import AuthMethod, PortalCategory, PortalHost, UrlStability
from ..codes import Portal
from ..metadata import PortalMetadata
from .common import build_entry, portal_path

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_RENTA_WEB_BORRADOR,
    path=portal_path(Portal.PORTAL_RENTA_WEB_BORRADOR),
    subdomain=PortalHost.WWW2,
    category=PortalCategory.BORRADOR,
    auth_methods=(
        AuthMethod.CERTIFICATE,
        AuthMethod.CLAVE_PIN,
        AuthMethod.CLAVE_PERMANENTE,
        AuthMethod.CLAVE_MOVIL,
        AuthMethod.DNIE,
        AuthMethod.REFERENCE_NUMBER,
    ),
    url_stability=UrlStability.STABLE_WITHIN_CAMPAIGN,
    label="entries.portal_renta_web_borrador.label",
    purpose="entries.portal_renta_web_borrador.purpose",
    notes=("entries.portal_renta_web_borrador.notes.0",),
)
"""Portal entry for Renta Web (IRPF pre-filled draft and filing service)."""
