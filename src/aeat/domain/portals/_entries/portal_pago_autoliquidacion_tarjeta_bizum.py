"""Registry entry for self-assessment payment via card or Bizum.

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
    portal=Portal.PORTAL_PAGO_AUTOLIQUIDACION_TARJETA_BIZUM,
    url="https://sede.agenciatributaria.gob.es/Sede/procedimientoini/ES18.shtml",
    subdomain=Subdomain.SEDE,
    category=PortalCategory.PAYMENT,
    auth_methods=(
        AuthMethod.CERTIFICATE,
        AuthMethod.CLAVE_PIN,
        AuthMethod.CLAVE_PERMANENTE,
        AuthMethod.DNIE,
    ),
    url_stability=UrlStability.STABLE_WITHIN_CAMPAIGN,
    label={
        "es": "Pago autoliquidaciones con tarjeta o Bizum",
        "en": "Self-assessment payment by card or Bizum",
        "hu": "Önbevallások kifizetése bankkártyával vagy Bizummal",
    },
    purpose_es="Pago de autoliquidaciones mediante tarjeta bancaria o Bizum.",
)
"""Portal entry for self-assessment payment via bank card or Bizum."""
