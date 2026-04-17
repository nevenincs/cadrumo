"""Portal: Sede Electrónica landing page."""

from __future__ import annotations

from aeat.portals._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from aeat.portals._codes import Portal
from aeat.portals._entries._common import build_entry
from aeat.portals._metadata import PortalMetadata

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_SEDE_ROOT,
    url="https://sede.agenciatributaria.gob.es/",
    subdomain=Subdomain.SEDE,
    category=PortalCategory.AUTH,
    auth_methods=(AuthMethod.ANONYMOUS,),
    url_stability=UrlStability.STABLE_PROTOCOL_GRADE,
    label={
        "es": "Sede Electrónica de la AEAT",
        "en": "AEAT electronic headquarters",
        "hu": "AEAT elektronikus székhely",
    },
    purpose_es="Página raíz de la Sede Electrónica de la AEAT.",
)
