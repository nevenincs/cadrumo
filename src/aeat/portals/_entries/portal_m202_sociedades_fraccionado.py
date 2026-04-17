"""Portal: Modelo 202 — IS pago fraccionado."""

from __future__ import annotations

from ...models import ModeloCode
from .._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from .._codes import Portal
from .._metadata import PortalMetadata
from ._common import build_entry

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_M202_SOCIEDADES_FRACCIONADO,
    url="https://sede.agenciatributaria.gob.es/Sede/procedimientoini/GE00.shtml",
    subdomain=Subdomain.SEDE,
    category=PortalCategory.FILING,
    auth_methods=(
        AuthMethod.CERTIFICATE,
        AuthMethod.DNIE,
    ),
    url_stability=UrlStability.STABLE_PROTOCOL_GRADE,
    related_modelo=ModeloCode.MODELO_202,
    label={
        "es": "Modelo 202 — IS pago fraccionado",
        "en": "Modelo 202 — Corporate tax instalment payment",
        "hu": "202-es űrlap — Társasági adó részletfizetés",
    },
    purpose_es="Pago fraccionado a cuenta del Impuesto sobre Sociedades.",
)
