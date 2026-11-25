"""The status report carries the informational-binding line.

An unreferenced binding is a registry refusal, so the only residue the report
prints is the dispositioned population: rows the author classed as having no
calculation consumer. The payload is checked for that line, for its independence
from the coverage lanes, and for the retirement of the advisory it replaced.
"""

from __future__ import annotations

import pytest

from ..registry_status import RegistryStatus, registry_status_payload

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _status(*, informational: tuple[tuple[str, int], ...]) -> RegistryStatus:
    """Build a status whose only varying axis is the informational population."""
    return RegistryStatus(
        valid=True,
        oracles=True,
        targets=(("current", 1), ("stale", 0), ("drifted", 0), ("never-committed", 0), ("unreadable", 0)),
        target_findings=(),
        authority="current",
        authority_recorded_digest=None,
        authority_candidate_digest=None,
        loadable=True,
        informational_bindings=informational,
        details=(),
    )


def test_payload_reports_informational_bindings_per_modelo() -> None:
    """The informational line carries its own total and per-modelo breakdown."""
    payload = registry_status_payload(_status(informational=(("303", 4), ("390", 1))), blocking=False)

    assert payload["informational_bindings"] == {"total": 5, "by_modelo": {"303": 4, "390": 1}}


def test_informational_bindings_do_not_make_any_lane_partial() -> None:
    """A dispositioned row is classified, not counted against any coverage lane."""
    payload = registry_status_payload(_status(informational=(("303", 4),)), blocking=False)

    informational = payload["informational_bindings"]
    assert isinstance(informational, dict)
    assert payload["partial_lanes"] == []
    assert informational["total"] == 4


def test_an_empty_corpus_reports_the_line_as_zero() -> None:
    """The line is always present, so silence is reported rather than omitted."""
    payload = registry_status_payload(_status(informational=()), blocking=False)

    assert payload["informational_bindings"] == {"total": 0, "by_modelo": {}}


def test_the_retired_unreferenced_advisory_is_not_reported() -> None:
    """Unreferenced bindings refuse the registry, so neither a line nor a lane remains."""
    payload = registry_status_payload(_status(informational=()), blocking=False)

    lanes = payload["lanes"]
    assert isinstance(lanes, dict)
    assert "unreferenced_bindings" not in payload
    assert "binding_reference_coverage" not in lanes
