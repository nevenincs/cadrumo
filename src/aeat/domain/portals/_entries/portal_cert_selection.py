"""Catalogue entry for the AEAT certificate-selection WebLogic gateway.

Exposes :data:`ENTRY`, a :class:`PortalMetadata` record for
:class:`Portal` ``PORTAL_CERT_SELECTION`` under :class:`PortalCategory`
``AUTH`` covering the ``/wlpl/BUCV-JDIT/SelectorCertificado``
certificate picker. URL stability is
:attr:`aeat.domain.portals.UrlStability.VOLATILE_APP_PATH`.
"""

from __future__ import annotations

from .._categories import AuthMethod, PortalCategory, PortalHost, UrlStability
from .._codes import Portal
from .._metadata import PortalMetadata
from ._common import build_entry, portal_path

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_CERT_SELECTION,
    path=portal_path(Portal.PORTAL_CERT_SELECTION),
    subdomain=PortalHost.WWW1,
    category=PortalCategory.AUTH,
    auth_methods=(AuthMethod.CERTIFICATE,),
    url_stability=UrlStability.VOLATILE_APP_PATH,
    label="entries.portal_cert_selection.label",
    purpose="entries.portal_cert_selection.purpose",
    notes=("entries.portal_cert_selection.notes.0",),
)
"""Frozen :class:`aeat.domain.portals.PortalMetadata` for the certificate-selection gateway."""
