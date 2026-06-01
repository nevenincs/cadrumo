"""Registry entry for the taxpayer's censo-data consultation portal.

Defines the :class:`PortalMetadata` record for :class:`Portal`
``PORTAL_MIS_DATOS_CENSALES`` under :class:`PortalCategory`
``CONSULTATION``, exposed as :data:`ENTRY` and consumed by
:data:`aeat.domain.portals.PORTAL_REGISTRY`.
"""

from __future__ import annotations

from ....core.config import Settings
from .._categories import AuthMethod, PortalCategory, PortalHost, UrlStability
from .._codes import Portal
from .._metadata import PortalMetadata
from ._common import build_entry

_SEDE_PATHS = Settings.external_constants().aeat.sede_paths

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_MIS_DATOS_CENSALES,
    path=_SEDE_PATHS.censo_g313_launcher,
    subdomain=PortalHost.SEDE,
    category=PortalCategory.CONSULTATION,
    auth_methods=(
        AuthMethod.CERTIFICATE,
        AuthMethod.CLAVE_PIN,
        AuthMethod.CLAVE_PERMANENTE,
        AuthMethod.DNIE,
    ),
    url_stability=UrlStability.STABLE_WITHIN_CAMPAIGN,
    label="entries.portal_mis_datos_censales.label",
    purpose="entries.portal_mis_datos_censales.purpose",
)
"""Portal entry for censo-data consultation and light modification."""
