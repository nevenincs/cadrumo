"""Registry entry for Modelo 390 — annual VAT summary.

Defines the :class:`~aeat.domain.portals._metadata.PortalMetadata` record
exposed as :data:`ENTRY` and consumed by
:data:`aeat.domain.portals.PORTAL_REGISTRY` via
:mod:`aeat.domain.portals._registry`.
"""

from __future__ import annotations

from ...modelos import ModeloCode
from .._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from .._codes import Portal
from .._metadata import PortalMetadata
from ._common import build_entry

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_M390_RESUMEN_IVA,
    url="https://sede.agenciatributaria.gob.es/Sede/procedimientoini/G412.shtml",
    subdomain=Subdomain.SEDE,
    category=PortalCategory.FILING,
    auth_methods=(
        AuthMethod.CERTIFICATE,
        AuthMethod.CLAVE_PIN,
        AuthMethod.CLAVE_PERMANENTE,
        AuthMethod.DNIE,
    ),
    url_stability=UrlStability.STABLE_PROTOCOL_GRADE,
    related_modelo=ModeloCode.MODELO_390,
    label={
        "es": "Modelo 390 — Resumen anual IVA",
        "en": "Modelo 390 — Annual VAT summary",
        "hu": "390-es űrlap — Éves IVA-összefoglaló",
    },
    purpose_es="Declaración-resumen anual del IVA (complementa a las autoliquidaciones periódicas del Modelo 303).",
)
"""Portal entry for Modelo 390 (annual VAT summary)."""
