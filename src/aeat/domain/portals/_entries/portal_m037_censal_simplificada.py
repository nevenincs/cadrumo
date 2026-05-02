"""Catalogue entry for the retired *Modelo 037* simplified census declaration.

Exposes :data:`ENTRY`, a frozen :class:`aeat.domain.portals.PortalMetadata`
flagged ``active=False`` and superseded by
:attr:`aeat.domain.portals.Portal.PORTAL_M036_CENSAL`. The procedure was
suppressed by Orden HAC/1526/2024 (BOE-A-2025-410), effective 2025-02-03;
the entry is retained for historical lookup. URL stability is therefore
:attr:`aeat.domain.portals.UrlStability.RETIRED`.
"""

from __future__ import annotations

from ...modelos import ModeloCode
from .._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from .._codes import Portal
from .._metadata import PortalMetadata
from ._common import build_entry

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
"""Frozen :class:`aeat.domain.portals.PortalMetadata` for the retired Modelo 037 procedure page."""
