"""Real-behavior tests for the portal-drift record and detection.

:func:`~cadrumo.domain.portals.evaluate_portal_drift` compares a real registered
:class:`~cadrumo.domain.portals.PortalMetadata` entry against an observed URL and
materialises a typed :class:`~cadrumo.domain.portals.PortalDriftEvent` when they
diverge. These tests drive the real frozen registry entries — no mocks — and
assert that a matching URL yields no drift, a path divergence yields a ``URL``
record, a host divergence yields a ``SUBDOMAIN`` record, and that the record
refuses to exist without an actual divergence.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ...portals.categories import UrlStability
from ...portals.drift import PortalDriftEvent, PortalDriftField, evaluate_portal_drift
from ...portals.metadata import PortalMetadata
from ...portals.registry import PORTAL_REGISTRY

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_FIXED_INSTANT = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)


def _any_entry() -> PortalMetadata:
    """Return one real registered portal metadata entry."""
    return next(iter(PORTAL_REGISTRY.values()))


def test_matching_observed_url_yields_no_drift() -> None:
    """An observed URL equal to the registered URL is not a divergence."""
    entry = _any_entry()
    assert evaluate_portal_drift(entry, observed_url=str(entry.url)) is None


def test_path_divergence_yields_url_drift_record() -> None:
    """A same-host different-path observation is a URL-field drift."""
    entry = _any_entry()
    observed = str(entry.url).rstrip("/") + "/drifted-path-segment"
    event = evaluate_portal_drift(entry, observed_url=observed, detected_at=_FIXED_INSTANT)
    assert event is not None
    assert event.field is PortalDriftField.URL
    assert event.portal is entry.portal
    assert event.expected == str(entry.url)
    assert event.observed == observed
    assert event.url_stability is entry.url_stability
    assert event.detected_at == _FIXED_INSTANT


def test_host_divergence_yields_subdomain_drift_record() -> None:
    """An observation on a different host is a SUBDOMAIN-field drift."""
    entry = _any_entry()
    observed = "https://impostor.example.org/some/path"
    event = evaluate_portal_drift(entry, observed_url=observed, detected_at=_FIXED_INSTANT)
    assert event is not None
    assert event.field is PortalDriftField.SUBDOMAIN
    assert event.expected == entry.url.host
    assert event.observed == "impostor.example.org"


def test_detected_at_defaults_to_clock_seam() -> None:
    """Omitting the instant stamps the record from the clock seam, UTC-aware."""
    entry = _any_entry()
    event = evaluate_portal_drift(entry, observed_url=str(entry.url) + "x")
    assert event is not None
    assert event.detected_at.tzinfo is not None


def test_event_rejects_non_divergent_expected_and_observed() -> None:
    """A PortalDriftEvent with expected == observed carries no drift and is refused."""
    entry = _any_entry()
    with pytest.raises(ValidationError, match=r"carries no divergence"):
        PortalDriftEvent(
            portal=entry.portal,
            field=PortalDriftField.URL,
            expected="https://same.example/",
            observed="https://same.example/",
            url_stability=UrlStability.VOLATILE_APP_PATH,
            detected_at=_FIXED_INSTANT,
        )
