"""Registry entry for Modelo 232 — related-party transactions return.

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
    portal=Portal.PORTAL_M232_VINCULADAS,
    url="https://sede.agenciatributaria.gob.es/Sede/procedimientoini/GI43.shtml",
    subdomain=Subdomain.SEDE,
    category=PortalCategory.FILING,
    auth_methods=(
        AuthMethod.CERTIFICATE,
        AuthMethod.DNIE,
    ),
    url_stability=UrlStability.STABLE_PROTOCOL_GRADE,
    related_modelo=ModeloCode.MODELO_232,
    label="entries.portal_m232_vinculadas.label_589847",
    purpose_es="Declaración informativa de operaciones vinculadas y con paraísos fiscales.",
)
"""Portal entry for Modelo 232 (related-party and tax-haven transactions)."""
