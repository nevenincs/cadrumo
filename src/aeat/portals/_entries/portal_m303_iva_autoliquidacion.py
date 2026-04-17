"""Portal: Modelo 303 — IVA autoliquidación periódica."""

from __future__ import annotations

from ...models import ModeloCode
from .._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from .._codes import Portal
from .._metadata import PortalMetadata
from ._common import build_entry

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_M303_IVA_AUTOLIQUIDACION,
    url="https://sede.agenciatributaria.gob.es/Sede/procedimientoini/G414.shtml",
    subdomain=Subdomain.SEDE,
    category=PortalCategory.FILING,
    auth_methods=(
        AuthMethod.CERTIFICATE,
        AuthMethod.CLAVE_PIN,
        AuthMethod.CLAVE_PERMANENTE,
        AuthMethod.CLAVE_MOVIL,
        AuthMethod.DNIE,
    ),
    url_stability=UrlStability.STABLE_PROTOCOL_GRADE,
    related_modelo=ModeloCode.MODELO_303,
    label={
        "es": "Modelo 303 — IVA autoliquidación",
        "en": "Modelo 303 — Periodic VAT self-assessment",
        "hu": "303-as űrlap — Időszakos IVA-önbevallás",
    },
    purpose_es="Autoliquidación periódica del Impuesto sobre el Valor Añadido (IVA).",
)
