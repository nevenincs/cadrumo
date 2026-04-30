"""Portal: Cl@ve whole-of-government IdP root."""

from __future__ import annotations

from .._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from .._codes import Portal
from .._metadata import PortalMetadata
from ._common import build_entry

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_CLAVE_IDP_ROOT,
    url="https://clave.gob.es/",
    subdomain=Subdomain.CLAVE_GOB,
    category=PortalCategory.AUTH,
    auth_methods=(AuthMethod.ANONYMOUS,),
    url_stability=UrlStability.STABLE_PROTOCOL_GRADE,
    label={
        "es": "Cl@ve — Identidad Electrónica para las Administraciones",
        "en": "Cl@ve — Spanish public-sector identity provider",
        "hu": "Cl@ve — spanyol közszolgálati azonosító",
    },
    purpose_es="Página raíz del proveedor de identidad Cl@ve (clave.gob.es).",
)
