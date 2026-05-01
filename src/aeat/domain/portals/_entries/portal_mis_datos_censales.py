"""Portal: Mis datos censales."""

from __future__ import annotations

from .._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from .._codes import Portal
from .._metadata import PortalMetadata
from ._common import build_entry

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_MIS_DATOS_CENSALES,
    url="https://sede.agenciatributaria.gob.es/Sede/procedimientoini/G313.shtml",
    subdomain=Subdomain.SEDE,
    category=PortalCategory.CONSULTATION,
    auth_methods=(
        AuthMethod.CERTIFICATE,
        AuthMethod.CLAVE_PIN,
        AuthMethod.CLAVE_PERMANENTE,
        AuthMethod.DNIE,
    ),
    url_stability=UrlStability.STABLE_WITHIN_CAMPAIGN,
    label={
        "es": "Mis datos censales",
        "en": "My census data",
        "hu": "Nyilvántartási adataim",
    },
    purpose_es="Consulta y modificación ligera de los datos censales registrados por la AEAT.",
)
