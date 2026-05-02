"""Catalogue entry for the *Modelo 115* urban-rental withholdings procedure.

Exposes :data:`ENTRY`, a frozen :class:`aeat.domain.portals.PortalMetadata`
under :attr:`aeat.domain.portals.PortalCategory.FILING` cross-referencing
:attr:`aeat.domain.modelos.ModeloCode.MODELO_115`. Backs the periodic
self-assessment of withholdings and on-account payments on income from
urban property leases.
"""

from __future__ import annotations

from ...modelos import ModeloCode
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
"""Frozen :class:`aeat.domain.portals.PortalMetadata` for the Modelo 115 procedure page."""
