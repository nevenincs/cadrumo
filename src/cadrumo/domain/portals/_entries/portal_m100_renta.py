"""Catalogue entry for the *Modelo 100* IRPF annual return procedure page.

Exposes :data:`ENTRY`, a :class:`PortalMetadata` record for
:class:`Portal` ``PORTAL_M100_RENTA`` under :class:`PortalCategory`
``FILING``. Accepts the IRPF-only ``REFERENCE_NUMBER`` credential in
addition to the standard certificate / Cl@ve / DNIe set.
"""

from __future__ import annotations

from ..categories import AuthMethod, PortalCategory, PortalHost, UrlStability
from ..codes import Portal
from ..metadata import PortalMetadata
from .common import build_entry, portal_path

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_M100_RENTA,
    path=portal_path(Portal.PORTAL_M100_RENTA),
    subdomain=PortalHost.SEDE,
    category=PortalCategory.FILING,
    auth_methods=(
        AuthMethod.CERTIFICATE,
        AuthMethod.CLAVE_PIN,
        AuthMethod.CLAVE_PERMANENTE,
        AuthMethod.CLAVE_MOVIL,
        AuthMethod.DNIE,
        AuthMethod.REFERENCE_NUMBER,
    ),
    url_stability=UrlStability.STABLE_PROTOCOL_GRADE,
    label="entries.portal_m100_renta.label",
    purpose="entries.portal_m100_renta.purpose",
)
"""Frozen :class:`cadrumo.domain.portals.PortalMetadata` for the Modelo 100 IRPF Renta page."""
