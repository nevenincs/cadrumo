"""Registry entry for Modelo 190 - annual summary of labour withholdings.

Defines the :class:`PortalMetadata` record identified by the :class:`Portal`
code ``PORTAL_M190_RESUMEN_TRABAJO``, exposed as :data:`ENTRY` under the
:class:`PortalCategory` member ``FILING``, consumed by
:data:`cadrumo.domain.portals.PORTAL_REGISTRY` via
:mod:`cadrumo.domain.portals.registry`.
"""

from __future__ import annotations

from ..categories import AuthMethod, PortalCategory, PortalHost, UrlStability
from ..codes import Portal
from ..metadata import PortalMetadata
from .common import build_entry, portal_path

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_M190_RESUMEN_TRABAJO,
    path=portal_path(Portal.PORTAL_M190_RESUMEN_TRABAJO),
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
