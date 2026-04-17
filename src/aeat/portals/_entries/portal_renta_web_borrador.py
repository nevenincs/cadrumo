"""Portal: Renta Web borrador (IRPF pre-filled draft)."""

from __future__ import annotations

from aeat.models import ModeloCode
from aeat.portals._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from aeat.portals._codes import Portal
from aeat.portals._entries._common import build_entry
from aeat.portals._metadata import PortalMetadata

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
