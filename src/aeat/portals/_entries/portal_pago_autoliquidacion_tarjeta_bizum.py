"""Portal: Pago de autoliquidaciones con tarjeta o Bizum."""

from __future__ import annotations

from aeat.portals._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from aeat.portals._codes import Portal
from aeat.portals._entries._common import build_entry
from aeat.portals._metadata import PortalMetadata

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
