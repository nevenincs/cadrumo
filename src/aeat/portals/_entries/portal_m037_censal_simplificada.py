"""Portal: Modelo 037 — declaración censal simplificada (retired 2025-02-03)."""

from __future__ import annotations

from aeat.models import ModeloCode
from aeat.portals._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from aeat.portals._codes import Portal
from aeat.portals._entries._common import build_entry
from aeat.portals._metadata import PortalMetadata

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_M037_CENSAL_SIMPLIFICADA,
    url="https://sede.agenciatributaria.gob.es/Sede/procedimientoini/G324.shtml",
    subdomain=Subdomain.SEDE,
    category=PortalCategory.CENSUS,
    auth_methods=(
        AuthMethod.CERTIFICATE,
        AuthMethod.CLAVE_PIN,
        AuthMethod.CLAVE_PERMANENTE,
    ),
    url_stability=UrlStability.RETIRED,
    related_modelo=ModeloCode.MODELO_037,
    label={
        "es": "Modelo 037 — Declaración censal simplificada (suprimido)",
        "en": "Modelo 037 — Simplified census declaration (retired)",
        "hu": "037-es űrlap — Egyszerűsített adóalanyi nyilvántartás (visszavont)",
    },
    purpose_es="Declaración censal simplificada. Suprimida por Orden HAC/1526/2024 el 2025-02-03.",
    active=False,
    replaced_by=Portal.PORTAL_M036_CENSAL,
    notes_es=(
        "Suprimido por Orden HAC/1526/2024 (BOE-A-2025-410), efectivo 2025-02-03.",
        "Cualquier alta, modificación o baja se canaliza ahora por el Modelo 036.",
    ),
)
