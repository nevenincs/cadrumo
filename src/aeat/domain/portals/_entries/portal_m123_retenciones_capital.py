"""Catalogue entry for the *Modelo 123* movable-capital withholdings procedure.

Exposes :data:`ENTRY`, a frozen :class:`aeat.domain.portals.PortalMetadata`
under :attr:`aeat.domain.portals.PortalCategory.FILING` cross-referencing
:attr:`aeat.domain.modelos.ModeloCode.MODELO_123`. Backs the periodic
self-assessment of withholdings on movable-capital income.
"""

from __future__ import annotations

from ...modelos import ModeloCode
from .._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from .._codes import Portal
from .._metadata import PortalMetadata
from ._common import build_entry

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_M123_RETENCIONES_CAPITAL,
    url="https://sede.agenciatributaria.gob.es/Sede/procedimientoini/GH04.shtml",
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
    related_modelo=ModeloCode.MODELO_123,
    label={
        "es": "Modelo 123 — Retenciones capital mobiliario",
        "en": "Modelo 123 — Withholdings on movable capital",
        "hu": "123-as űrlap — Tőkejövedelem forrásadói",
    },
    purpose_es=(
        "Autoliquidación periódica de retenciones e ingresos a cuenta sobre rendimientos del capital mobiliario."
    ),
)
"""Frozen :class:`aeat.domain.portals.PortalMetadata` for the Modelo 123 procedure page."""
