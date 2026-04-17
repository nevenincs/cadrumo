"""Portal: Pago de liquidaciones y deudas."""

from __future__ import annotations

from aeat.portals._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from aeat.portals._codes import Portal
from aeat.portals._entries._common import build_entry
from aeat.portals._metadata import PortalMetadata

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_PAGO_LIQUIDACIONES_DEUDAS,
    url="https://sede.agenciatributaria.gob.es/Sede/procedimientoini/ES15.shtml",
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
        "es": "Pago de liquidaciones y deudas",
        "en": "Payment of liquidations and debts",
        "hu": "Adókivetések és tartozások kifizetése",
    },
    purpose_es="Pago de liquidaciones tributarias y deudas notificadas por la AEAT.",
)
