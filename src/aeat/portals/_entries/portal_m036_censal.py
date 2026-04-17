"""Portal: Modelo 036 — declaración censal."""

from __future__ import annotations

from aeat.models import ModeloCode
from aeat.portals._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from aeat.portals._codes import Portal
from aeat.portals._entries._common import build_entry
from aeat.portals._metadata import PortalMetadata

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_M036_CENSAL,
    url="https://sede.agenciatributaria.gob.es/Sede/procedimientoini/G322.shtml",
    subdomain=Subdomain.SEDE,
    category=PortalCategory.CENSUS,
    auth_methods=(
        AuthMethod.CERTIFICATE,
        AuthMethod.CLAVE_PIN,
        AuthMethod.CLAVE_PERMANENTE,
        AuthMethod.CLAVE_MOVIL,
        AuthMethod.DNIE,
    ),
    url_stability=UrlStability.STABLE_PROTOCOL_GRADE,
    related_modelo=ModeloCode.MODELO_036,
    label={
        "es": "Modelo 036 — Declaración censal",
        "en": "Modelo 036 — Census declaration",
        "hu": "036-os űrlap — Adóalanyi nyilvántartásba vétel",
    },
    purpose_es="Alta, modificación y baja en el censo de empresarios, profesionales y retenedores.",
)
