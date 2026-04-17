"""Portal: Documentos pendientes de firma."""

from __future__ import annotations

from .._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from .._codes import Portal
from .._metadata import PortalMetadata
from ._common import build_entry

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_MIS_DOCUMENTOS_PENDIENTES_FIRMA,
    url="https://sede.agenciatributaria.gob.es/Sede/gestiones/presentacion-portafirmas.html",
    subdomain=Subdomain.SEDE,
    category=PortalCategory.CONSULTATION,
    auth_methods=(
        AuthMethod.CERTIFICATE,
        AuthMethod.CLAVE_PERMANENTE,
        AuthMethod.DNIE,
    ),
    url_stability=UrlStability.STABLE_WITHIN_CAMPAIGN,
    label={
        "es": "Documentos pendientes de firma",
        "en": "Documents awaiting signature",
        "hu": "Aláírásra váró dokumentumok",
    },
    purpose_es="Portafirmas: documentos en espera de firma electrónica del contribuyente.",
)
