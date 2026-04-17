"""Portal: Modelo 115 — retenciones arrendamientos urbanos."""

from __future__ import annotations

from ...models import ModeloCode
from .._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from .._codes import Portal
from .._metadata import PortalMetadata
from ._common import build_entry

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_M115_RETENCIONES_ARRENDAMIENTOS,
    url="https://sede.agenciatributaria.gob.es/Sede/procedimientoini/GH02.shtml",
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
    related_modelo=ModeloCode.MODELO_115,
    label={
        "es": "Modelo 115 — Retenciones arrendamientos urbanos",
        "en": "Modelo 115 — Withholdings on urban rentals",
        "hu": "115-ös űrlap — Városi bérleti forrásadók",
    },
    purpose_es=(
        "Autoliquidación periódica de retenciones e ingresos a cuenta "
        "sobre rendimientos de arrendamiento de inmuebles urbanos."
    ),
)
