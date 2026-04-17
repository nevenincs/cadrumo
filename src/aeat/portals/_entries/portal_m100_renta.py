"""Portal: Modelo 100 — IRPF renta anual."""

from __future__ import annotations

from ...models import ModeloCode
from .._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from .._codes import Portal
from .._metadata import PortalMetadata
from ._common import build_entry

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_M100_RENTA,
    url="https://sede.agenciatributaria.gob.es/Sede/procedimientoini/G229.shtml",
    subdomain=Subdomain.SEDE,
    category=PortalCategory.FILING,
    auth_methods=(
        AuthMethod.CERTIFICATE,
        AuthMethod.CLAVE_PIN,
        AuthMethod.CLAVE_PERMANENTE,
        AuthMethod.CLAVE_MOVIL,
        AuthMethod.DNIE,
        AuthMethod.REFERENCE_NUMBER,
    ),
    url_stability=UrlStability.STABLE_PROTOCOL_GRADE,
    related_modelo=ModeloCode.MODELO_100,
    label={
        "es": "Modelo 100 — IRPF declaración anual",
        "en": "Modelo 100 — Annual personal income tax",
        "hu": "100-as űrlap — Éves személyi jövedelemadó",
    },
    purpose_es="Presentación de la declaración anual del IRPF (Renta).",
)
