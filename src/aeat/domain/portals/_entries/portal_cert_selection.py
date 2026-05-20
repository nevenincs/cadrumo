"""Catalogue entry for the AEAT certificate-selection WebLogic gateway.

Exposes :data:`ENTRY`, a frozen :class:`aeat.domain.portals.PortalMetadata`
under :attr:`aeat.domain.portals.PortalCategory.AUTH` covering the
``/wlpl/BUCV-JDIT/SelectorCertificado`` certificate picker. URL stability
is :attr:`aeat.domain.portals.UrlStability.VOLATILE_APP_PATH`.
"""

from __future__ import annotations

from .._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from .._codes import Portal
from .._metadata import PortalMetadata
from ._common import build_entry

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_CERT_SELECTION,
    path="/wlpl/BUCV-JDIT/SelectorCertificado",
    subdomain=Subdomain.WWW1,
    category=PortalCategory.AUTH,
    auth_methods=(AuthMethod.CERTIFICATE,),
    url_stability=UrlStability.VOLATILE_APP_PATH,
    label="entries.portal_cert_selection.label",
    purpose="entries.portal_cert_selection.purpose",
    notes=("entries.portal_cert_selection.notes.0",),
)
"""Frozen :class:`aeat.domain.portals.PortalMetadata` for the certificate-selection gateway."""
