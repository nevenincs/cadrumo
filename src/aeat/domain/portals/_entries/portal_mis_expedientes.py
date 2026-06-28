"""Registry entry for the taxpayer's case-file consultation portal.

Defines the :class:`PortalMetadata` record identified by the :class:`Portal`
code ``PORTAL_MIS_EXPEDIENTES``, exposed as :data:`ENTRY` under the
:class:`PortalCategory` member ``PERSONAL_AREA``, consumed by
:data:`aeat.domain.portals.PORTAL_REGISTRY` via
:mod:`aeat.domain.portals._registry`.
"""

from __future__ import annotations

from .._categories import AuthMethod, PortalCategory, PortalHost, UrlStability
from .._codes import Portal
from .._metadata import PortalMetadata
from ._common import build_entry, portal_path

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_MIS_EXPEDIENTES,
    path=portal_path(Portal.PORTAL_MIS_EXPEDIENTES),
    subdomain=PortalHost.SEDE,
    category=PortalCategory.CONSULTATION,
    auth_methods=(
        AuthMethod.CERTIFICATE,
        AuthMethod.CLAVE_PIN,
        AuthMethod.CLAVE_PERMANENTE,
        AuthMethod.DNIE,
    ),
    url_stability=UrlStability.STABLE_WITHIN_CAMPAIGN,
    label="entries.portal_mis_expedientes.label",
    purpose="entries.portal_mis_expedientes.purpose",
)
"""Portal entry for administrative case-file status consultation."""
