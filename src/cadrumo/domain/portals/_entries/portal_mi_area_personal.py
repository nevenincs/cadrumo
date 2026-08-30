"""Registry entry for the Sede Electronica authenticated personal area.

Defines the :class:`PortalMetadata` record identified by the :class:`Portal`
code ``PORTAL_MI_AREA_PERSONAL``, exposed as :data:`ENTRY` under the
:class:`PortalCategory` member ``PERSONAL_AREA``, consumed by
:data:`cadrumo.domain.portals.PORTAL_REGISTRY` via
:mod:`cadrumo.domain.portals.registry`.
"""

from __future__ import annotations

from ..categories import AuthMethod, PortalCategory, PortalHost, UrlStability
from ..codes import Portal
from ..metadata import PortalMetadata
from .common import build_entry, portal_path

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_MI_AREA_PERSONAL,
    path=portal_path(Portal.PORTAL_MI_AREA_PERSONAL),
    subdomain=PortalHost.SEDE,
    category=PortalCategory.AUTH,
    auth_methods=(
        AuthMethod.CLAVE_PIN,
        AuthMethod.CLAVE_PERMANENTE,
        AuthMethod.CLAVE_MOVIL,
        AuthMethod.CERTIFICATE,
        AuthMethod.DNIE,
    ),
    url_stability=UrlStability.STABLE_WITHIN_CAMPAIGN,
    label="entries.portal_mi_area_personal.label",
    purpose="entries.portal_mi_area_personal.purpose",
)
"""Portal entry for the taxpayer's personal area (authenticated landing)."""
