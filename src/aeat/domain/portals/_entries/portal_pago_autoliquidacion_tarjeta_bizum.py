"""Registry entry for self-assessment payment via card or Bizum.

Defines the :class:`PortalMetadata` record identified by the :class:`Portal`
code ``PORTAL_PAGO_AUTOLIQUIDACION_TARJETA_BIZUM``, exposed as :data:`ENTRY`
under the :class:`PortalCategory` member ``PAYMENT``, consumed by
:data:`aeat.domain.portals.PORTAL_REGISTRY` via
:mod:`aeat.domain.portals._registry`.
"""

from __future__ import annotations

from .._categories import AuthMethod, PortalCategory, PortalHost, UrlStability
from .._codes import Portal
from .._metadata import PortalMetadata
from ._common import build_entry, portal_path

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_PAGO_AUTOLIQUIDACION_TARJETA_BIZUM,
    path=portal_path(Portal.PORTAL_PAGO_AUTOLIQUIDACION_TARJETA_BIZUM),
    subdomain=PortalHost.SEDE,
    category=PortalCategory.PAYMENT,
    auth_methods=(
        AuthMethod.CERTIFICATE,
        AuthMethod.CLAVE_PIN,
        AuthMethod.CLAVE_PERMANENTE,
        AuthMethod.DNIE,
    ),
    url_stability=UrlStability.STABLE_WITHIN_CAMPAIGN,
    label="entries.portal_pago_autoliquidacion_tarjeta_bizum.label",
    purpose="entries.portal_pago_autoliquidacion_tarjeta_bizum.purpose",
)
"""Portal entry for self-assessment payment via bank card or Bizum."""
