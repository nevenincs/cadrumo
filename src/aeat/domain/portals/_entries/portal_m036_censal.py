"""Catalogue entry for the *Modelo 036* census-declaration procedure page.

Exposes :data:`ENTRY`, a frozen :class:`aeat.domain.portals.PortalMetadata`
under :attr:`aeat.domain.portals.PortalCategory.CENSUS` cross-referencing
:attr:`aeat.domain.modelos.ModeloCode.MODELO_036`. Covers registration,
modification, and deregistration on the census of entrepreneurs,
professionals, and withholders.
"""

from __future__ import annotations

from ...modelos import ModeloCode
from .._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from .._codes import Portal
from .._metadata import PortalMetadata
from ._common import build_entry

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_M036_CENSAL,
    url="https://sede.agenciatributaria.gob.es/Sede/procedimientoini/G322.shtml",
    subdomain=Subdomain.SEDE,
    category=PortalCategory.CENSUS,
    auth_methods=(
        AuthMethod.CERTIFICATE,
        AuthMethod.CLAVE_PIN,
        AuthMethod.CLAVE_PERMANENTE,
        AuthMethod.CLAVE_MOVIL,
        AuthMethod.DNIE,
    ),
    url_stability=UrlStability.STABLE_PROTOCOL_GRADE,
    related_modelo=ModeloCode.MODELO_036,
    label={
        "es": "Modelo 036 — Declaración censal",
        "en": "Modelo 036 — Census declaration",
        "hu": "036-os űrlap — Adóalanyi nyilvántartásba vétel",
    },
    purpose_es="Alta, modificación y baja en el censo de empresarios, profesionales y retenedores.",
)
"""Frozen :class:`aeat.domain.portals.PortalMetadata` for the Modelo 036 census procedure page."""
