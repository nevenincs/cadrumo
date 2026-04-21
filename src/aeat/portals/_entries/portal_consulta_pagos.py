"""Portal: Consulta de pagos y NRC."""

from __future__ import annotations

from .._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from .._codes import Portal
from .._metadata import PortalMetadata
from ._common import build_entry

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_CONSULTA_PAGOS,
    url="https://sede.agenciatributaria.gob.es/Sede/procedimientoini/ES09.shtml",
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
        "es": "Consulta de pagos",
        "en": "Payment and NRC enquiry",
        "hu": "Kifizetések és NRC lekérdezése",
    },
    purpose_es="Consulta del estado de pagos realizados y recuperación de NRC generados.",
)
