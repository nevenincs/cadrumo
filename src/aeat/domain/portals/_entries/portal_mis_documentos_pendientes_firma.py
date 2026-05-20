"""Registry entry for the documents-awaiting-signature portfolio (portafirmas).

Defines the :class:`~aeat.domain.portals._metadata.PortalMetadata` record
exposed as :data:`ENTRY` and consumed by
:data:`aeat.domain.portals.PORTAL_REGISTRY` via
:mod:`aeat.domain.portals._registry`.
"""

from __future__ import annotations

from .._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from .._codes import Portal
from .._metadata import PortalMetadata
from ._common import build_entry

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_MIS_DOCUMENTOS_PENDIENTES_FIRMA,
    path="/Sede/gestiones/presentacion-portafirmas.html",
    subdomain=Subdomain.SEDE,
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
