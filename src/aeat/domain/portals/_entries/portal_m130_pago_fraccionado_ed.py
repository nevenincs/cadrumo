"""Catalogue entry for the *Modelo 130* IRPF instalment payment procedure.

Exposes :data:`ENTRY`, a frozen :class:`PortalMetadata` record identified
by the :class:`Portal` code ``PORTAL_M130_PAGO_FRACCIONADO_ED`` under
the :class:`PortalCategory` member
:attr:`aeat.domain.portals.PortalCategory.FILING`. Used by entrepreneurs
and professionals on the IRPF direct-assessment (estimación directa)
regime to settle on-account quarterly instalments.
"""

from __future__ import annotations

from .._categories import AuthMethod, PortalCategory, PortalHost, UrlStability
from .._codes import Portal
from .._metadata import PortalMetadata
from ._common import build_entry, portal_path

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_M130_PAGO_FRACCIONADO_ED,
    path=portal_path(Portal.PORTAL_M130_PAGO_FRACCIONADO_ED),
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
    label="entries.portal_m130_pago_fraccionado_ed.label",
    purpose="entries.portal_m130_pago_fraccionado_ed.purpose",
)
"""Frozen :class:`aeat.domain.portals.PortalMetadata` for the Modelo 130 procedure page."""
