"""Registry entry for payment of AEAT-issued liquidations and debts.

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
    portal=Portal.PORTAL_PAGO_LIQUIDACIONES_DEUDAS,
    url="https://sede.agenciatributaria.gob.es/Sede/procedimientoini/ES15.shtml",
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
        "es": "Pago de liquidaciones y deudas",
        "en": "Payment of liquidations and debts",
        "hu": "Adókivetések és tartozások kifizetése",
    },
    purpose_es="Pago de liquidaciones tributarias y deudas notificadas por la AEAT.",
)
"""Portal entry for paying AEAT-notified tax liquidations and debts."""
