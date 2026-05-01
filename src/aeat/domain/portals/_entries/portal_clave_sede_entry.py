"""Portal: Cl@ve gateway on AEAT Sede."""

from __future__ import annotations

from .._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from .._codes import Portal
from .._metadata import PortalMetadata
from ._common import build_entry

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_CLAVE_SEDE_ENTRY,
    url="https://sede.agenciatributaria.gob.es/Sede/clave.html",
    subdomain=Subdomain.SEDE,
    category=PortalCategory.AUTH,
    auth_methods=(AuthMethod.ANONYMOUS,),
    url_stability=UrlStability.STABLE_WITHIN_CAMPAIGN,
    label={
        "es": "Acceso Cl@ve en la Sede",
        "en": "Cl@ve gateway on Sede",
        "hu": "Cl@ve beléptető oldal a székhelyen",
    },
    purpose_es="Punto de entrada a Cl@ve desde la Sede Electrónica (redirige a clave.gob.es).",
)
