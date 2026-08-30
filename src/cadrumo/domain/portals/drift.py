"""Typed portal-drift record and read-only divergence detection.

A :class:`PortalDriftEvent` captures a single detected divergence between a
*registered* portal assumption (the canonical URL / host declared on the
frozen :class:`~domain.portals.PortalMetadata` entry) and an *observed*
live state. Detection is advisory and read-only: :func:`evaluate_portal_drift`
compares an already-observed value the caller supplies against the registry
entry and, when they diverge, materialises the typed record. This module never
contacts AEAT — the observation itself is produced elsewhere, under the
live-read access gate, and handed in as a plain value. The catalogue package as
a whole performs no live AEAT access (see the package docstring); this module
only *describes* a divergence someone else observed.

The record carries the entry's :class:`~domain.portals.UrlStability` tier
so downstream health reporting (the ``portal-registry:health`` doctor row in
:mod:`application.preflight`) can grade a drift by how stable the URL was
promised to be: a drift on a BOE-referenced ``STABLE_PROTOCOL_GRADE`` URL is a
real integrity concern, whereas a drift on a ``VOLATILE_APP_PATH`` shell URL is
an expected rotation.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from urllib.parse import urlsplit

from pydantic import AwareDatetime, BaseModel, Field, model_validator

from ...core import STRICT_FROZEN_CONFIG
from ...core.time import now as _now
from .categories import UrlStability
from .codes import Portal
from .errors import PortalValidationError
from .metadata import PortalMetadata

__all__ = [
    "PortalDriftEvent",
    "PortalDriftField",
    "evaluate_portal_drift",
]


class PortalDriftField(StrEnum):
    """The registered portal assumption a :class:`PortalDriftEvent` diverges on.

    ``URL`` — the observed canonical URL differs from the registered URL
    (same host, different path or query). ``SUBDOMAIN`` — the observed URL
    is hosted on a different AEAT-family host than the registered
    :class:`~domain.portals.PortalHost`. ``AVAILABILITY`` — the portal
    did not answer as reachable when the registered assumption is that it is
    a live surface.
    """

    URL = "url"
    SUBDOMAIN = "subdomain"
    AVAILABILITY = "availability"


class PortalDriftEvent(BaseModel):
    """One detected divergence between a registered portal assumption and live state.

    A strict, frozen record. It asserts an *actual* divergence: ``expected``
    (the registered assumption) and ``observed`` (the live state) must differ,
    so a :class:`PortalDriftEvent` can only exist for a genuine drift.

    Attributes:
        portal: The :class:`~domain.portals.Portal` whose assumption drifted.
        field: The :class:`PortalDriftField` that diverged.
        expected: The registered assumption value (the registry's truth).
        observed: The observed live-state value the caller supplied.
        url_stability: The registered
            :class:`~domain.portals.UrlStability` tier of the entry,
            carried so health reporting can grade the drift.
        detected_at: UTC-aware instant the divergence was observed.
        note: Optional free-text operator note describing the observation.
    """

    model_config = STRICT_FROZEN_CONFIG

    portal: Portal
    field: PortalDriftField
    expected: str = Field(min_length=1)
    observed: str
    url_stability: UrlStability
    detected_at: AwareDatetime
    note: str = ""

    @model_validator(mode="after")
    def _validate_divergence(self) -> PortalDriftEvent:
        """Reject a record whose observed value equals its expected value."""
        if self.expected == self.observed:
            raise PortalValidationError(
                f"portal {self.portal.value} drift on {self.field.value} carries no divergence: "
                f"expected == observed == {self.expected!r}",
            )
        return self


def evaluate_portal_drift(
    metadata: PortalMetadata,
    *,
    observed_url: str,
    detected_at: datetime | None = None,
) -> PortalDriftEvent | None:
    """Compare a registered portal entry against an observed live URL.

    Read-only and pure: performs no network access. The ``observed_url`` is a
    value the caller obtained under the live-read access gate (or from a
    recorded observation) and passes in for comparison against the registry
    truth. When the observed URL matches the registered URL exactly, there is
    no drift and ``None`` is returned. Otherwise a typed
    :class:`PortalDriftEvent` is materialised: a differing host yields a
    :attr:`PortalDriftField.SUBDOMAIN` record; any other difference yields a
    :attr:`PortalDriftField.URL` record.

    Args:
        metadata: The registered :class:`~domain.portals.PortalMetadata`.
        observed_url: The URL observed for the portal in live state.
        detected_at: The UTC-aware observation instant. Defaults to the
            clock-seam :func:`core.time.now` reading when omitted.

    Returns:
        A :class:`PortalDriftEvent` when the observed URL diverges from the
        registered URL, or ``None`` when they match.
    """
    registered_url = str(metadata.url)
    if observed_url == registered_url:
        return None

    stamped_at = detected_at if detected_at is not None else _now()
    expected_host = metadata.url.host
    observed_host = urlsplit(observed_url).hostname
    if observed_host is not None and expected_host is not None and observed_host != expected_host:
        return PortalDriftEvent(
            portal=metadata.portal,
            field=PortalDriftField.SUBDOMAIN,
            expected=expected_host,
            observed=observed_host,
            url_stability=metadata.url_stability,
            detected_at=stamped_at,
        )
    return PortalDriftEvent(
        portal=metadata.portal,
        field=PortalDriftField.URL,
        expected=registered_url,
        observed=observed_url,
        url_stability=metadata.url_stability,
        detected_at=stamped_at,
    )
