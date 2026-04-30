"""Portal: certificate validation endpoint."""

from __future__ import annotations

from .._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from .._codes import Portal
from .._metadata import PortalMetadata
from ._common import build_entry

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_CERT_VALIDATION_REST,
    url="https://sede.agenciatributaria.gob.es/Sede/certificados.html",
    subdomain=Subdomain.SEDE,
    category=PortalCategory.AUTH,
    auth_methods=(AuthMethod.CERTIFICATE,),
    url_stability=UrlStability.STABLE_WITHIN_CAMPAIGN,
    label={
        "es": "Validación de certificado electrónico",
        "en": "Electronic certificate validation",
        "hu": "Elektronikus tanúsítvány ellenőrzése",
    },
    purpose_es="Información y validación de certificados electrónicos admitidos por la AEAT.",
)
