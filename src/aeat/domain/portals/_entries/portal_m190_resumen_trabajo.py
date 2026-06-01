"""Registry entry for Modelo 190 - annual summary of labour withholdings.

Defines the :class:`PortalMetadata` record identified by the :class:`Portal`
code ``PORTAL_M190_RESUMEN_TRABAJO``, exposed as :data:`ENTRY` under the
:class:`PortalCategory` member ``FILING``, consumed by
:data:`aeat.domain.portals.PORTAL_REGISTRY` via
:mod:`aeat.domain.portals._registry`.
"""

from __future__ import annotations

from .._categories import AuthMethod, PortalCategory, PortalHost, UrlStability
from .._codes import Portal
from .._metadata import PortalMetadata
from ._common import build_entry

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_M190_RESUMEN_TRABAJO,
    path="/Sede/procedimientoini/GI10.shtml",
    subdomain=PortalHost.SEDE,
    category=PortalCategory.FILING,
    auth_methods=(
        AuthMethod.CERTIFICATE,
        AuthMethod.CLAVE_PIN,
        AuthMethod.CLAVE_PERMANENTE,
        AuthMethod.DNIE,
    ),
    url_stability=UrlStability.STABLE_PROTOCOL_GRADE,
    label="entries.portal_m190_resumen_trabajo.label",
    purpose="entries.portal_m190_resumen_trabajo.purpose",
)
"""Portal entry for Modelo 190 (annual summary of labour withholdings)."""
