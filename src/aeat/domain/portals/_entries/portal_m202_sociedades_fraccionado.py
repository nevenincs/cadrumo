"""Registry entry for Modelo 202 — corporate-tax instalment payment.

Defines the :class:`~aeat.domain.portals._metadata.PortalMetadata` record
exposed as :data:`ENTRY` and consumed by
:data:`aeat.domain.portals.PORTAL_REGISTRY` via
:mod:`aeat.domain.portals._registry`.
"""

from __future__ import annotations

from ...modelos import ModeloCode
from .._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from .._codes import Portal
from .._metadata import PortalMetadata
from ._common import build_entry

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_M202_SOCIEDADES_FRACCIONADO,
    url="https://sede.agenciatributaria.gob.es/Sede/procedimientoini/GE00.shtml",
    subdomain=Subdomain.SEDE,
    category=PortalCategory.FILING,
    auth_methods=(
        AuthMethod.CERTIFICATE,
        AuthMethod.DNIE,
    ),
    url_stability=UrlStability.STABLE_PROTOCOL_GRADE,
    related_modelo=ModeloCode.MODELO_202,
    label="entries.portal_m202_sociedades_fraccionado.label_203074",
    purpose_es="Pago fraccionado a cuenta del Impuesto sobre Sociedades.",
)
"""Portal entry for Modelo 202 (corporate-tax instalment payment)."""
