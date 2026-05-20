"""Catalogue entry for the *Modelo 100* IRPF annual return procedure page.

Exposes :data:`ENTRY`, a frozen :class:`aeat.domain.portals.PortalMetadata`
under :attr:`aeat.domain.portals.PortalCategory.FILING`. Accepts the IRPF-only
:attr:`aeat.domain.portals.AuthMethod.REFERENCE_NUMBER` credential in
addition to the standard certificate / Cl@ve / DNIe set.
"""

from __future__ import annotations

from .._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from .._codes import Portal
from .._metadata import PortalMetadata
from ._common import build_entry

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_M100_RENTA,
    path="/Sede/procedimientoini/G229.shtml",
    subdomain=Subdomain.SEDE,
    category=PortalCategory.FILING,
    auth_methods=(
        AuthMethod.CERTIFICATE,
        AuthMethod.CLAVE_PIN,
        AuthMethod.CLAVE_PERMANENTE,
        AuthMethod.CLAVE_MOVIL,
        AuthMethod.DNIE,
        AuthMethod.REFERENCE_NUMBER,
    ),
    url_stability=UrlStability.STABLE_PROTOCOL_GRADE,
    label="entries.portal_m100_renta.label",
    purpose="entries.portal_m100_renta.purpose",
)
"""Frozen :class:`aeat.domain.portals.PortalMetadata` for the Modelo 100 IRPF Renta page."""
