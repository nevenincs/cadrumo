"""Catalogue entry for the *Modelo 123* movable-capital withholdings procedure.

Exposes :data:`ENTRY`, a frozen :class:`aeat.domain.portals.PortalMetadata`
under :attr:`aeat.domain.portals.PortalCategory.FILING`. Backs the periodic
self-assessment of withholdings on movable-capital income.
"""

from __future__ import annotations

from .._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from .._codes import Portal
from .._metadata import PortalMetadata
from ._common import build_entry

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_M123_RETENCIONES_CAPITAL,
    path="/Sede/procedimientoini/GH04.shtml",
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
    label="entries.portal_m123_retenciones_capital.label",
    purpose="entries.portal_m123_retenciones_capital.purpose",
)
"""Frozen :class:`aeat.domain.portals.PortalMetadata` for the Modelo 123 procedure page."""
