"""Catalogue entry for the AEAT certificate-validation information page.

Exposes :data:`ENTRY`, a :class:`PortalMetadata` record for
:class:`Portal` ``PORTAL_CERT_VALIDATION_REST`` under
:class:`PortalCategory` ``AUTH``, describing the
``/Sede/certificados.html`` page that lists admissible electronic
certificates.
"""

from __future__ import annotations

from .._categories import AuthMethod, PortalCategory, PortalHost, UrlStability
from .._codes import Portal
from .._metadata import PortalMetadata
from ._common import build_entry, portal_path

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_CERT_VALIDATION_REST,
    path=portal_path(Portal.PORTAL_CERT_VALIDATION_REST),
    subdomain=PortalHost.SEDE,
    category=PortalCategory.AUTH,
    auth_methods=(AuthMethod.CERTIFICATE,),
    url_stability=UrlStability.STABLE_WITHIN_CAMPAIGN,
    label="entries.portal_cert_validation_rest.label",
    purpose="entries.portal_cert_validation_rest.purpose",
)
"""Frozen :class:`aeat.domain.portals.PortalMetadata` for the certificate-validation page."""
