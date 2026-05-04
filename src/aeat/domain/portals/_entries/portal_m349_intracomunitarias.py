"""Registry entry for Modelo 349 — intra-EU transactions return.

Defines the :class:`~aeat.domain.portals._metadata.PortalMetadata` record
exposed as :data:`ENTRY` and consumed by
:data:`aeat.domain.portals.PORTAL_REGISTRY` via
:mod:`aeat.domain.portals._registry`.
"""

from __future__ import annotations

from .._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from .._codes import Portal
from .._metadata import PortalMetadata
from ._common import build_entry

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_M349_INTRACOMUNITARIAS,
    url="https://sede.agenciatributaria.gob.es/Sede/procedimientoini/GI28.shtml",
    subdomain=Subdomain.SEDE,
    category=PortalCategory.FILING,
    auth_methods=(
        AuthMethod.CERTIFICATE,
        AuthMethod.CLAVE_PIN,
        AuthMethod.CLAVE_PERMANENTE,
        AuthMethod.DNIE,
    ),
    url_stability=UrlStability.STABLE_PROTOCOL_GRADE,
    label="entries.portal_m349_intracomunitarias.label_740192",
    purpose_es="Declaración recapitulativa de entregas y adquisiciones intracomunitarias (VAT VIES).",
)
"""Portal entry for Modelo 349 (intra-EU recapitulative VAT statement)."""
