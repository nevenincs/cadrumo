"""Registry entry for Renta Web — IRPF pre-filled draft (borrador).

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
    portal=Portal.PORTAL_RENTA_WEB_BORRADOR,
    path="/wlpl/OVCT-CXEW/SesionHTML",
    subdomain=Subdomain.WWW2,
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
