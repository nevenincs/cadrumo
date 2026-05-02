"""Registry entry for Modelo 347 — annual third-party transactions return.

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
    portal=Portal.PORTAL_M347_OPERACIONES_TERCEROS,
    url="https://sede.agenciatributaria.gob.es/Sede/procedimientoini/GI27.shtml",
    subdomain=Subdomain.SEDE,
    category=PortalCategory.FILING,
    auth_methods=(
        AuthMethod.CERTIFICATE,
        AuthMethod.CLAVE_PIN,
        AuthMethod.CLAVE_PERMANENTE,
        AuthMethod.DNIE,
    ),
    url_stability=UrlStability.STABLE_PROTOCOL_GRADE,
    related_modelo=ModeloCode.MODELO_347,
    label={
        "es": "Modelo 347 — Operaciones con terceros",
        "en": "Modelo 347 — Third-party transactions",
        "hu": "347-es űrlap — Harmadik felekkel folytatott ügyletek",
    },
    purpose_es="Declaración informativa anual de operaciones con terceras personas por encima del umbral legal.",
)
"""Portal entry for Modelo 347 (annual third-party transactions return)."""
