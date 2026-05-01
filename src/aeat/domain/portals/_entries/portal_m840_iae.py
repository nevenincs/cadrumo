"""Portal: Modelo 840 — Impuesto sobre Actividades Económicas."""

from __future__ import annotations

from ...modelos import ModeloCode
from .._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from .._codes import Portal
from .._metadata import PortalMetadata
from ._common import build_entry

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_M840_IAE,
    url="https://sede.agenciatributaria.gob.es/Sede/procedimientoini/G323.shtml",
    subdomain=Subdomain.SEDE,
    category=PortalCategory.FILING,
    auth_methods=(
        AuthMethod.CERTIFICATE,
        AuthMethod.CLAVE_PIN,
        AuthMethod.CLAVE_PERMANENTE,
        AuthMethod.DNIE,
    ),
    url_stability=UrlStability.STABLE_PROTOCOL_GRADE,
    related_modelo=ModeloCode.MODELO_840,
    label={
        "es": "Modelo 840 — Impuesto sobre Actividades Económicas",
        "en": "Modelo 840 — Economic activities tax",
        "hu": "840-es űrlap — Gazdasági tevékenységi adó",
    },
    purpose_es="Alta, variación y baja en el Impuesto sobre Actividades Económicas (IAE).",
)
