"""Portal: Modelo 131 — pago fraccionado IRPF estimación objetiva."""

from __future__ import annotations

from ...models import ModeloCode
from .._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from .._codes import Portal
from .._metadata import PortalMetadata
from ._common import build_entry

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_M131_PAGO_FRACCIONADO_EO,
    url="https://sede.agenciatributaria.gob.es/Sede/procedimientoini/G602.shtml",
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
    related_modelo=ModeloCode.MODELO_131,
    label={
        "es": "Modelo 131 — Pago fraccionado IRPF (estimación objetiva)",
        "en": "Modelo 131 — IRPF instalment payment (objective assessment)",
        "hu": "131-es űrlap — IRPF részletfizetés (módszeres megállapítás)",
    },
    purpose_es="Pago fraccionado a cuenta del IRPF para empresarios en estimación objetiva (módulos).",
)
