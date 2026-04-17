"""Portal: Modelo 349 — operaciones intracomunitarias."""

from __future__ import annotations

from aeat.models import ModeloCode
from aeat.portals._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from aeat.portals._codes import Portal
from aeat.portals._entries._common import build_entry
from aeat.portals._metadata import PortalMetadata

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_M349_INTRACOMUNITARIAS,
    url="https://sede.agenciatributaria.gob.es/Sede/procedimientoini/GI28.shtml",
    subdomain=Subdomain.SEDE,
    category=PortalCategory.FILING,
    auth_methods=(
        AuthMethod.CERTIFICATE,
        AuthMethod.CLAVE_PIN,
        AuthMethod.CLAVE_PERMANENTE,
        AuthMethod.DNIE,
    ),
    url_stability=UrlStability.STABLE_PROTOCOL_GRADE,
    related_modelo=ModeloCode.MODELO_349,
    label={
        "es": "Modelo 349 — Operaciones intracomunitarias",
        "en": "Modelo 349 — Intra-EU transactions",
        "hu": "349-es űrlap — Közösségen belüli ügyletek",
    },
    purpose_es="Declaración recapitulativa de entregas y adquisiciones intracomunitarias (VAT VIES).",
)
