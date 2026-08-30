"""Registry entry for payment of AEAT-issued liquidations and debts.

Defines the :class:`PortalMetadata` record for :class:`Portal`
``PORTAL_PAGO_LIQUIDACIONES_DEUDAS`` under :class:`PortalCategory`
``PAYMENT``, exposed as :data:`ENTRY` and consumed by
:data:`cadrumo.domain.portals.PORTAL_REGISTRY`.
"""

from __future__ import annotations

from ..categories import AuthMethod, PortalCategory, PortalHost, UrlStability
from ..codes import Portal
from ..metadata import PortalMetadata
from .common import build_entry, portal_path

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_PAGO_LIQUIDACIONES_DEUDAS,
    path=portal_path(Portal.PORTAL_PAGO_LIQUIDACIONES_DEUDAS),
    subdomain=PortalHost.SEDE,
    category=PortalCategory.PAYMENT,
    auth_methods=(
        AuthMethod.CERTIFICATE,
        AuthMethod.CLAVE_PIN,
        AuthMethod.CLAVE_PERMANENTE,
        AuthMethod.DNIE,
    ),
    url_stability=UrlStability.STABLE_WITHIN_CAMPAIGN,
    label="entries.portal_pago_liquidaciones_deudas.label",
    purpose="entries.portal_pago_liquidaciones_deudas.purpose",
)
"""Portal entry for paying AEAT-notified tax liquidations and debts."""
