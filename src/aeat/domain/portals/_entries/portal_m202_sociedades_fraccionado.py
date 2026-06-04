"""Registry entry for Modelo 202 - corporate-tax instalment payment.

Defines the :class:`PortalMetadata` record identified by the :class:`Portal`
code ``PORTAL_M202_SOCIEDADES_FRACCIONADO``, exposed as :data:`ENTRY` under
the :class:`PortalCategory` member ``FILING``, consumed by
:data:`aeat.domain.portals.PORTAL_REGISTRY` via
:mod:`aeat.domain.portals._registry`.
"""

from __future__ import annotations

from .._categories import AuthMethod, PortalCategory, PortalHost, UrlStability
from .._codes import Portal
from .._metadata import PortalMetadata
from ._common import build_entry, portal_path

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_M202_SOCIEDADES_FRACCIONADO,
    path=portal_path(Portal.PORTAL_M202_SOCIEDADES_FRACCIONADO),
    subdomain=PortalHost.SEDE,
    category=PortalCategory.FILING,
    auth_methods=(
        AuthMethod.CERTIFICATE,
        AuthMethod.DNIE,
    ),
    url_stability=UrlStability.STABLE_PROTOCOL_GRADE,
    label="entries.portal_m202_sociedades_fraccionado.label",
    purpose="entries.portal_m202_sociedades_fraccionado.purpose",
)
"""Portal entry for Modelo 202 (corporate-tax instalment payment)."""
