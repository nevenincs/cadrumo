"""Registry entry for Modelo 303 - periodic IVA self-assessment.

Defines the :class:`PortalMetadata` record for :class:`Portal`
``PORTAL_M303_IVA_AUTOLIQUIDACION`` under :class:`PortalCategory`
``FILING``, exposed as :data:`ENTRY` and consumed by
:data:`cadrumo.domain.portals.PORTAL_REGISTRY`.
"""

from __future__ import annotations

from ..categories import AuthMethod, PortalCategory, PortalHost, UrlStability
from ..codes import Portal
from ..metadata import PortalMetadata
from .common import build_entry, portal_path

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_M303_IVA_AUTOLIQUIDACION,
    path=portal_path(Portal.PORTAL_M303_IVA_AUTOLIQUIDACION),
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
    label="entries.portal_m303_iva_autoliquidacion.label",
    purpose="entries.portal_m303_iva_autoliquidacion.purpose",
)
"""Portal entry for Modelo 303 (periodic IVA self-assessment)."""
