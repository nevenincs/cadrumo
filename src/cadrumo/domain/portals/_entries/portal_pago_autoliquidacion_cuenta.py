"""Registry entry for self-assessment payment via bank-account direct debit (NRC).

Defines the :class:`PortalMetadata` record for :class:`Portal`
``PORTAL_PAGO_AUTOLIQUIDACION_CUENTA`` under :class:`PortalCategory`
``PAYMENT``, exposed as :data:`ENTRY` and consumed by
:data:`aeat.domain.portals.PORTAL_REGISTRY`.
"""

from __future__ import annotations

from .._categories import AuthMethod, PortalCategory, PortalHost, UrlStability
from .._codes import Portal
from .._metadata import PortalMetadata
from ._common import build_entry, portal_path

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_PAGO_AUTOLIQUIDACION_CUENTA,
    path=portal_path(Portal.PORTAL_PAGO_AUTOLIQUIDACION_CUENTA),
    subdomain=PortalHost.SEDE,
    category=PortalCategory.PAYMENT,
    auth_methods=(
        AuthMethod.CERTIFICATE,
        AuthMethod.CLAVE_PIN,
        AuthMethod.CLAVE_PERMANENTE,
        AuthMethod.DNIE,
    ),
    url_stability=UrlStability.STABLE_WITHIN_CAMPAIGN,
    label="entries.portal_pago_autoliquidacion_cuenta.label",
    purpose="entries.portal_pago_autoliquidacion_cuenta.purpose",
)
"""Portal entry for self-assessment payment via bank account (NRC issuance)."""
