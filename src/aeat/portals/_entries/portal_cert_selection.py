"""Portal: Certificate selection entry point on the WebLogic shell."""

from __future__ import annotations

from aeat.portals._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from aeat.portals._codes import Portal
from aeat.portals._entries._common import build_entry
from aeat.portals._metadata import PortalMetadata

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_CERT_SELECTION,
    url="https://www1.agenciatributaria.gob.es/wlpl/BUCV-JDIT/SelectorCertificado",
    subdomain=Subdomain.WWW1,
    category=PortalCategory.AUTH,
    auth_methods=(AuthMethod.CERTIFICATE,),
    url_stability=UrlStability.VOLATILE_APP_PATH,
    label={
        "es": "Selector de certificado",
        "en": "Certificate selector",
        "hu": "Tanúsítvány-választó",
    },
    purpose_es="Punto de selección de certificado digital en la pasarela autenticada de la AEAT.",
    notes_es=("Ruta volátil: puede rotar entre campañas sin aviso previo.",),
)
