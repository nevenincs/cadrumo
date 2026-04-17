"""Portal: Presentar y consultar declaraciones — index."""

from __future__ import annotations

from aeat.portals._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from aeat.portals._codes import Portal
from aeat.portals._entries._common import build_entry
from aeat.portals._metadata import PortalMetadata

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_PRESENTAR_CONSULTAR_INDEX,
    url="https://sede.agenciatributaria.gob.es/Sede/presentar-consultar-declaraciones-modelo.html",
    subdomain=Subdomain.SEDE,
    category=PortalCategory.CALENDAR_REFERENCE,
    auth_methods=(AuthMethod.ANONYMOUS,),
    url_stability=UrlStability.STABLE_PROTOCOL_GRADE,
    label={
        "es": "Presentar y consultar declaraciones — índice",
        "en": "Submit and consult declarations — index",
        "hu": "Bevallások benyújtása és lekérdezése — tárgymutató",
    },
    purpose_es="Índice oficial de modelos y procedimientos de presentación y consulta.",
)
