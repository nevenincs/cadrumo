"""Catalogue entry for the retired *Modelo 037* simplified censo declaration.

Exposes :data:`ENTRY`, a :class:`PortalMetadata` record for
:class:`Portal` ``PORTAL_M037_CENSAL_SIMPLIFICADA`` under
:class:`PortalCategory` ``CENSO``, flagged ``active=False`` and
superseded by ``PORTAL_M036_CENSAL``. The procedure was suppressed by
Orden HAC/1526/2024 (BOE-A-2025-410), effective 2025-02-03; the entry
is retained for historical lookup.
"""

from __future__ import annotations

from ..categories import AuthMethod, PortalCategory, PortalHost, UrlStability
from ..codes import Portal
from ..metadata import PortalMetadata
from .common import build_entry, portal_path

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_M037_CENSAL_SIMPLIFICADA,
    path=portal_path(Portal.PORTAL_M037_CENSAL_SIMPLIFICADA),
    subdomain=PortalHost.SEDE,
    category=PortalCategory.CENSO,
    auth_methods=(
        AuthMethod.CERTIFICATE,
        AuthMethod.CLAVE_PIN,
        AuthMethod.CLAVE_PERMANENTE,
    ),
    url_stability=UrlStability.RETIRED,
    label="entries.portal_m037_censal_simplificada.label",
    purpose="entries.portal_m037_censal_simplificada.purpose",
    active=False,
    replaced_by=Portal.PORTAL_M036_CENSAL,
    notes=(
        "entries.portal_m037_censal_simplificada.notes.0",
        "entries.portal_m037_censal_simplificada.notes.1",
    ),
)
"""Frozen :class:`cadrumo.domain.portals.PortalMetadata` for the retired Modelo 037 procedure page."""
