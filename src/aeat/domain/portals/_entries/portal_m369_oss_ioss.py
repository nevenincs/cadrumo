"""Registry entry for Modelo 369 — OSS / IOSS one-stop-shop return.

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
    portal=Portal.PORTAL_M369_OSS_IOSS,
    url="https://sede.agenciatributaria.gob.es/Sede/procedimientoini/G420.shtml",
    subdomain=Subdomain.SEDE,
    category=PortalCategory.FILING,
    auth_methods=(
        AuthMethod.CERTIFICATE,
        AuthMethod.DNIE,
    ),
    url_stability=UrlStability.STABLE_PROTOCOL_GRADE,
    related_modelo=ModeloCode.MODELO_369,
    label="entries.portal_m369_oss_ioss.label_354748",
    purpose_es="Autoliquidación del IVA de servicios y ventas a distancia intracomunitarias bajo el régimen OSS/IOSS.",
)
"""Portal entry for Modelo 369 (OSS / IOSS one-stop-shop VAT return)."""
