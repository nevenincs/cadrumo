"""Portal: Modelo 232 — operaciones vinculadas."""

from __future__ import annotations

from ...models import ModeloCode
from .._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from .._codes import Portal
from .._metadata import PortalMetadata
from ._common import build_entry

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_M232_VINCULADAS,
    url="https://sede.agenciatributaria.gob.es/Sede/procedimientoini/GI43.shtml",
    subdomain=Subdomain.SEDE,
    category=PortalCategory.FILING,
    auth_methods=(
        AuthMethod.CERTIFICATE,
        AuthMethod.DNIE,
    ),
    url_stability=UrlStability.STABLE_PROTOCOL_GRADE,
    related_modelo=ModeloCode.MODELO_232,
    label={
        "es": "Modelo 232 — Operaciones vinculadas",
        "en": "Modelo 232 — Related-party transactions",
        "hu": "232-es űrlap — Kapcsolt felek közötti ügyletek",
    },
    purpose_es="Declaración informativa de operaciones vinculadas y con paraísos fiscales.",
)
