"""Portal: Renta Web borrador (IRPF pre-filled draft)."""

from __future__ import annotations

from ...models import ModeloCode
from .._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from .._codes import Portal
from .._metadata import PortalMetadata
from ._common import build_entry

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_RENTA_WEB_BORRADOR,
    url="https://www2.agenciatributaria.gob.es/wlpl/OVCT-CXEW/SesionHTML",
    subdomain=Subdomain.WWW2,
    category=PortalCategory.BORRADOR,
    auth_methods=(
        AuthMethod.CERTIFICATE,
        AuthMethod.CLAVE_PIN,
        AuthMethod.CLAVE_PERMANENTE,
        AuthMethod.CLAVE_MOVIL,
        AuthMethod.DNIE,
        AuthMethod.REFERENCE_NUMBER,
    ),
    url_stability=UrlStability.STABLE_WITHIN_CAMPAIGN,
    related_modelo=ModeloCode.MODELO_100,
    label={
        "es": "Renta Web — Borrador IRPF",
        "en": "Renta Web — IRPF pre-filled draft",
        "hu": "Renta Web — IRPF előzetes vázlat",
    },
    purpose_es="Acceso al borrador y servicio Renta Web para la declaración del IRPF.",
    notes_es=("Ruta WebLogic: puede rotar entre campañas Renta.",),
)
