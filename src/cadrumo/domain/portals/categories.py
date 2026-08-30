"""Closed taxonomies used by the portal registry.

These enums are the keying dimensions the registry exposes on
:class:`cadrumo.domain.portals.PortalMetadata`: the functional category a portal
belongs to, the authentication method(s) it accepts, the URL-stability
tier it sits in, and the AEAT-family subdomain it is hosted on. Every
enum is a :class:`enum.StrEnum` so members compare equal to their
canonical string representation across JSON / CLI boundaries.
"""

from __future__ import annotations

from enum import StrEnum


class PortalCategory(StrEnum):
    """Functional category of an AEAT portal.

    ``FILING`` and ``CENSO`` cover per-modelo procedure pages (the
    ``/Sede/procedimientoini/G<code>.shtml`` namespace). ``BORRADOR``
    covers pre-filled draft entry points (Renta Web, Pre303).
    ``CONSULTATION`` covers "Mi área personal" family surfaces.
    ``PAYMENT`` covers NRC / payment flows. ``AUTH`` covers the Cl@ve
    / certificate / DNIe gateways. ``CALENDAR_REFERENCE`` covers
    informational reference pages (tax calendar, index).
    """

    AUTH = "auth"
    FILING = "filing"
    CENSO = "censo"
    CONSULTATION = "consultation"
    BORRADOR = "borrador"
    PAYMENT = "payment"
    CALENDAR_REFERENCE = "calendar_reference"


class AuthMethod(StrEnum):
    """Accepted authentication method on a gated portal.

    ``ANONYMOUS`` marks portals that require no authentication; it is
    mutually exclusive with every other method. ``REFERENCE_NUMBER``
    is IRPF-only (Renta Web borrador accepts the previous year's
    box 505 as the credential).
    """

    ANONYMOUS = "anonymous"
    CLAVE_PIN = "clave_pin"
    CLAVE_PERMANENTE = "clave_permanente"
    CLAVE_MOVIL = "clave_movil"
    CERTIFICATE = "certificate"
    DNIE = "dnie"
    REFERENCE_NUMBER = "reference_number"


class UrlStability(StrEnum):
    """Stability tier of a portal URL.

    ``STABLE_PROTOCOL_GRADE`` URLs are BOE-referenced and change only
    via explicit Orden publication. ``STABLE_WITHIN_CAMPAIGN`` URLs
    are stable for a tax campaign year and may rotate at the boundary.
    ``VOLATILE_APP_PATH`` URLs live on the WebLogic ``/wlpl/...``
    shells and rotate at AEAT's discretion. ``RETIRED`` marks URLs
    that have been suppressed but are retained for historical lookup.
    """

    STABLE_PROTOCOL_GRADE = "stable_protocol_grade"
    STABLE_WITHIN_CAMPAIGN = "stable_within_campaign"
    VOLATILE_APP_PATH = "volatile_app_path"
    RETIRED = "retired"


class PortalHost(StrEnum):
    """AEAT-family hosts the scraper must navigate.

    Values are stable registry keys, not hostnames. The hostname
    authority lives in :mod:`cadrumo.core.external_constants`, and portal
    validation resolves these keys through that central registry.
    ``CLAVE_GOB`` is the whole-of-government identity provider; it sits
    adjacent to AEAT but is in scope because the scraper hands off to it
    during Cl@ve flows.
    """

    SEDE = "sede"
    WWW1 = "www1"
    WWW2 = "www2"
    WWW3 = "www3"
    AGENCIATRIBUTARIA_GOB = "aeat_gob"
    AGENCIATRIBUTARIA_ES = "legacy_www"
    CLAVE_GOB = "clave"
