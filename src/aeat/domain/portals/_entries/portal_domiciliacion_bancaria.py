"""Catalogue entry for the AEAT *Domiciliación bancaria* procedure page.

Exposes :data:`ENTRY`, a frozen :class:`aeat.domain.portals.PortalMetadata`
under :attr:`aeat.domain.portals.PortalCategory.PAYMENT`. Used to set up,
inspect, and revoke direct-debit instructions on the AEAT autoliquidación
flow.
"""

from __future__ import annotations

from .._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from .._codes import Portal
from .._metadata import PortalMetadata
from ._common import build_entry

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_DOMICILIACION_BANCARIA,
    path="/Sede/procedimientoini/GA16.shtml",
    subdomain=Subdomain.SEDE,
    category=PortalCategory.PAYMENT,
    auth_methods=(
        AuthMethod.CERTIFICATE,
        AuthMethod.CLAVE_PIN,
        AuthMethod.CLAVE_PERMANENTE,
        AuthMethod.DNIE,
    ),
    url_stability=UrlStability.STABLE_WITHIN_CAMPAIGN,
    label="entries.portal_domiciliacion_bancaria.label",
    purpose="entries.portal_domiciliacion_bancaria.purpose",
)
"""Frozen :class:`aeat.domain.portals.PortalMetadata` for the bank direct-debit page."""
