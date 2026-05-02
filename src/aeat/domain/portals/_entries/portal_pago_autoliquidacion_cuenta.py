"""Registry entry for self-assessment payment via bank-account direct debit (NRC).

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
    portal=Portal.PORTAL_PAGO_AUTOLIQUIDACION_CUENTA,
    url="https://sede.agenciatributaria.gob.es/Sede/procedimientoini/ES14.shtml",
    subdomain=Subdomain.SEDE,
    category=PortalCategory.PAYMENT,
    auth_methods=(
        AuthMethod.CERTIFICATE,
        AuthMethod.CLAVE_PIN,
        AuthMethod.CLAVE_PERMANENTE,
        AuthMethod.DNIE,
    ),
    url_stability=UrlStability.STABLE_WITHIN_CAMPAIGN,
    label={
        "es": "Pago autoliquidaciones en cuenta",
        "en": "Self-assessment payment via bank account",
        "hu": "Önbevallások kifizetése bankszámláról",
    },
    purpose_es="Pago de autoliquidaciones con cargo en cuenta bancaria generando NRC.",
)
"""Portal entry for self-assessment payment via bank account (NRC issuance)."""
