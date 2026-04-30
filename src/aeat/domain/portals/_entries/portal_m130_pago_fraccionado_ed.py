"""Portal: Modelo 130 — pago fraccionado IRPF estimación directa."""

from __future__ import annotations

from ...modelos import ModeloCode
from .._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from .._codes import Portal
from .._metadata import PortalMetadata
from ._common import build_entry

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_M130_PAGO_FRACCIONADO_ED,
    url="https://sede.agenciatributaria.gob.es/Sede/procedimientoini/G601.shtml",
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
    related_modelo=ModeloCode.MODELO_130,
    label={
        "es": "Modelo 130 — Pago fraccionado IRPF (estimación directa)",
        "en": "Modelo 130 — IRPF instalment payment (direct assessment)",
        "hu": "130-as űrlap — IRPF részletfizetés (közvetlen megállapítás)",
    },
    purpose_es="Pago fraccionado a cuenta del IRPF para empresarios y profesionales en estimación directa.",
)
