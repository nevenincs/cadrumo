"""Registry entry for Modelo 390 - annual IVA summary.

Defines the :class:`PortalMetadata` record identified by the :class:`Portal`
code ``PORTAL_M390_RESUMEN_IVA``, exposed as :data:`ENTRY` under the
:class:`PortalCategory` member ``INFORMATIVA``, consumed by
:data:`aeat.domain.portals.PORTAL_REGISTRY` via
:mod:`aeat.domain.portals._registry`.
"""

from __future__ import annotations

from .._categories import AuthMethod, PortalCategory, PortalHost, UrlStability
from .._codes import Portal
from .._metadata import PortalMetadata
from ._common import build_entry, portal_path

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_M390_RESUMEN_IVA,
    path=portal_path(Portal.PORTAL_M390_RESUMEN_IVA),
    subdomain=PortalHost.SEDE,
    category=PortalCategory.FILING,
    auth_methods=(
        AuthMethod.CERTIFICATE,
        AuthMethod.CLAVE_PIN,
        AuthMethod.CLAVE_PERMANENTE,
        AuthMethod.DNIE,
    ),
    url_stability=UrlStability.STABLE_PROTOCOL_GRADE,
    label="entries.portal_m390_resumen_iva.label",
    purpose="entries.portal_m390_resumen_iva.purpose",
)
"""Portal entry for Modelo 390 (annual IVA summary)."""
