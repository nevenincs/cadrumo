"""Registry entry for the documents-awaiting-signature portfolio (portafirmas).

Defines the :class:`PortalMetadata` record for :class:`Portal`
``PORTAL_MIS_DOCUMENTOS_PENDIENTES_FIRMA`` under
:class:`PortalCategory` ``CONSULTATION``, exposed as :data:`ENTRY`
and consumed by :data:`aeat.domain.portals.PORTAL_REGISTRY`.
"""

from __future__ import annotations

from .._categories import AuthMethod, PortalCategory, PortalHost, UrlStability
from .._codes import Portal
from .._metadata import PortalMetadata
from ._common import build_entry, portal_path

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_MIS_DOCUMENTOS_PENDIENTES_FIRMA,
    path=portal_path(Portal.PORTAL_MIS_DOCUMENTOS_PENDIENTES_FIRMA),
    subdomain=PortalHost.SEDE,
    category=PortalCategory.CONSULTATION,
    auth_methods=(
        AuthMethod.CERTIFICATE,
        AuthMethod.CLAVE_PERMANENTE,
        AuthMethod.DNIE,
    ),
    url_stability=UrlStability.STABLE_WITHIN_CAMPAIGN,
    label="entries.portal_mis_documentos_pendientes_firma.label",
    purpose="entries.portal_mis_documentos_pendientes_firma.purpose",
)
"""Portal entry for the portafirmas (documents awaiting electronic signature)."""
