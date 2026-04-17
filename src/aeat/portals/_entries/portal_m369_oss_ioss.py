"""Portal: Modelo 369 — ventanilla única OSS / IOSS."""

from __future__ import annotations

from ...models import ModeloCode
from .._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from .._codes import Portal
from .._metadata import PortalMetadata
from ._common import build_entry

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_M369_OSS_IOSS,
    url="https://sede.agenciatributaria.gob.es/Sede/procedimientoini/G420.shtml",
    subdomain=Subdomain.SEDE,
    category=PortalCategory.FILING,
    auth_methods=(
        AuthMethod.CERTIFICATE,
        AuthMethod.DNIE,
    ),
    url_stability=UrlStability.STABLE_PROTOCOL_GRADE,
    related_modelo=ModeloCode.MODELO_369,
    label={
        "es": "Modelo 369 — Ventanilla única OSS/IOSS",
        "en": "Modelo 369 — OSS / IOSS one-stop shop",
        "hu": "369-es űrlap — OSS / IOSS egyablakos ügyintézés",
    },
    purpose_es="Autoliquidación del IVA de servicios y ventas a distancia intracomunitarias bajo el régimen OSS/IOSS.",
)
