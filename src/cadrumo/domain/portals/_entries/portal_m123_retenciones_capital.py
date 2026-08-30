"""Catalogue entry for the *Modelo 123* movable-capital withholdings procedure.

Exposes :data:`ENTRY`, a :class:`PortalMetadata` record for
:class:`Portal` ``PORTAL_M123_RETENCIONES_CAPITAL`` under
:class:`PortalCategory` ``FILING``. Backs the periodic
self-assessment of withholdings on movable-capital income.
"""

from __future__ import annotations

from ..categories import AuthMethod, PortalCategory, PortalHost, UrlStability
from ..codes import Portal
from ..metadata import PortalMetadata
from .common import build_entry, portal_path

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_M123_RETENCIONES_CAPITAL,
    path=portal_path(Portal.PORTAL_M123_RETENCIONES_CAPITAL),
    subdomain=PortalHost.SEDE,
    category=PortalCategory.FILING,
    auth_methods=(
        AuthMethod.CERTIFICATE,
        AuthMethod.CLAVE_PIN,
        AuthMethod.CLAVE_PERMANENTE,
        AuthMethod.CLAVE_MOVIL,
        AuthMethod.DNIE,
    ),
    url_stability=UrlStability.STABLE_PROTOCOL_GRADE,
    label="entries.portal_m123_retenciones_capital.label",
    purpose="entries.portal_m123_retenciones_capital.purpose",
)
"""Frozen :class:`cadrumo.domain.portals.PortalMetadata` for the Modelo 123 procedure page."""
