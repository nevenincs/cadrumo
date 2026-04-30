"""Portal: DNIe Sede entry point."""

from __future__ import annotations

from .._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from .._codes import Portal
from .._metadata import PortalMetadata
from ._common import build_entry

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_DNIE_SEDE_ENTRY,
    url="https://sede.agenciatributaria.gob.es/Sede/dnie-electronico.html",
    subdomain=Subdomain.SEDE,
    category=PortalCategory.AUTH,
    auth_methods=(AuthMethod.DNIE,),
    url_stability=UrlStability.STABLE_WITHIN_CAMPAIGN,
    label={
        "es": "Acceso con DNIe electrónico",
        "en": "DNIe electronic ID access",
        "hu": "DNIe elektronikus személyi igazolvány belépés",
    },
    purpose_es="Acceso mediante DNI electrónico a la Sede; reutiliza la pasarela de certificado.",
)
