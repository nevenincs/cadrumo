"""Catalogue entry for the *Modelo 131* IRPF instalment payment procedure.

Exposes :data:`ENTRY`, a frozen :class:`aeat.domain.portals.PortalMetadata`
under :attr:`aeat.domain.portals.PortalCategory.FILING`. Used by entrepreneurs on
the IRPF *objective-assessment* (módulos) regime to settle on-account
quarterly instalments.
"""

from __future__ import annotations

from .._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from .._codes import Portal
from .._metadata import PortalMetadata
from ._common import build_entry

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_M131_PAGO_FRACCIONADO_EO,
    path="/Sede/procedimientoini/G602.shtml",
    subdomain=Subdomain.SEDE,
    category=PortalCategory.FILING,
    auth_methods=(
        AuthMethod.CERTIFICATE,
        AuthMethod.CLAVE_PIN,
        AuthMethod.CLAVE_PERMANENTE,
        AuthMethod.CLAVE_MOVIL,
        AuthMethod.DNIE,
    ),
    url_stability=UrlStability.STABLE_PROTOCOL_GRADE,
    label="entries.portal_m131_pago_fraccionado_eo.label",
    purpose="entries.portal_m131_pago_fraccionado_eo.purpose",
)
"""Frozen :class:`aeat.domain.portals.PortalMetadata` for the Modelo 131 procedure page."""
