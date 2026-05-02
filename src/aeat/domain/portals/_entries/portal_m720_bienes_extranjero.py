"""Registry entry for Modelo 720 — foreign assets and rights informational return.

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
    portal=Portal.PORTAL_M720_BIENES_EXTRANJERO,
    url="https://sede.agenciatributaria.gob.es/Sede/procedimientoini/GI34.shtml",
    subdomain=Subdomain.SEDE,
    category=PortalCategory.FILING,
    auth_methods=(
        AuthMethod.CERTIFICATE,
        AuthMethod.CLAVE_PIN,
        AuthMethod.CLAVE_PERMANENTE,
        AuthMethod.DNIE,
    ),
    url_stability=UrlStability.STABLE_PROTOCOL_GRADE,
    related_modelo=ModeloCode.MODELO_720,
    label={
        "es": "Modelo 720 — Bienes y derechos en el extranjero",
        "en": "Modelo 720 — Foreign assets and rights",
        "hu": "720-as űrlap — Külföldi vagyontárgyak és jogok",
    },
    purpose_es="Declaración informativa sobre bienes y derechos situados en el extranjero.",
)
"""Portal entry for Modelo 720 (foreign assets and rights informational return)."""
