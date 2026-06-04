"""Registry entry for Modelo 349 - intra-EU transactions return.

Defines the :class:`PortalMetadata` record for :class:`Portal`
``PORTAL_M349_INTRACOMUNITARIAS`` under :class:`PortalCategory`
``FILING``, exposed as :data:`ENTRY` and consumed by
:data:`aeat.domain.portals.PORTAL_REGISTRY`.
"""

from __future__ import annotations

from .._categories import AuthMethod, PortalCategory, PortalHost, UrlStability
from .._codes import Portal
from .._metadata import PortalMetadata
from ._common import build_entry, portal_path

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_M349_INTRACOMUNITARIAS,
    path=portal_path(Portal.PORTAL_M349_INTRACOMUNITARIAS),
    subdomain=PortalHost.SEDE,
    category=PortalCategory.FILING,
    auth_methods=(
        AuthMethod.CERTIFICATE,
        AuthMethod.CLAVE_PIN,
        AuthMethod.CLAVE_PERMANENTE,
        AuthMethod.DNIE,
    ),
    url_stability=UrlStability.STABLE_PROTOCOL_GRADE,
    label="entries.portal_m349_intracomunitarias.label",
    purpose="entries.portal_m349_intracomunitarias.purpose",
)
"""Portal entry for Modelo 349 (intra-EU recapitulative IVA statement)."""
