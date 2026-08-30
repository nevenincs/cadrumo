"""Catalogue entry for the AEAT *Domiciliación bancaria* procedure page.

Exposes :data:`ENTRY`, a :class:`PortalMetadata` record for
:class:`Portal` ``PORTAL_DOMICILIACION_BANCARIA`` under
:class:`PortalCategory` ``PAYMENT``. Used to set up, inspect, and
revoke direct-debit instructions on the AEAT autoliquidación flow.
"""

from __future__ import annotations

from ..categories import AuthMethod, PortalCategory, PortalHost, UrlStability
from ..codes import Portal
from ..metadata import PortalMetadata
from .common import build_entry, portal_path

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_DOMICILIACION_BANCARIA,
    path=portal_path(Portal.PORTAL_DOMICILIACION_BANCARIA),
    subdomain=PortalHost.SEDE,
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
"""Frozen :class:`cadrumo.domain.portals.PortalMetadata` for the bank direct-debit page."""
