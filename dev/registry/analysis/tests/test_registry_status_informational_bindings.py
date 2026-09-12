"""The status report carries the informational-binding line beside the advisory.

The unreferenced advisory and the informational disposition are two halves of
one population. If the report printed only the first, authoring a disposition
would look like the residue shrinking rather than like a row being classified,
so the payload is checked for both lines and for their independence.
"""

from __future__ import annotations

import pytest

from ..registry_status import RegistryStatus, _payload

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _status(
    *,
    unreferenced: tuple[tuple[str, int], ...],
    informational: tuple[tuple[str, int], ...],
) -> RegistryStatus:
    """Build a status whose only varying axes are the two binding populations."""
    return RegistryStatus(
        valid=True,
        oracles=True,
        targets=(("current", 1), ("stale", 0), ("drifted", 0), ("never-committed", 0), ("unreadable", 0)),
        target_findings=(),
        authority="current",
        authority_recorded_digest=None,
        authority_candidate_digest=None,
        loadable=True,
        unreferenced_bindings=unreferenced,
        informational_bindings=informational,
        details=(),
    )


def test_payload_reports_informational_bindings_per_modelo() -> None:
    """The informational line carries its own total and per-modelo breakdown."""
    payload = _payload(_status(unreferenced=(("360", 151),), informational=(("303", 4), ("390", 1))), blocking=False)

    assert payload["informational_bindings"] == {"total": 5, "by_modelo": {"303": 4, "390": 1}}
    assert payload["unreferenced_bindings"] == {"total": 151, "by_modelo": {"360": 151}}


def test_informational_bindings_do_not_move_the_reference_coverage_lane() -> None:
    """A dispositioned row is classified, not counted against binding coverage."""
    payload = _payload(_status(unreferenced=(), informational=(("303", 4),)), blocking=False)

    lanes = payload["lanes"]
    informational = payload["informational_bindings"]
    assert isinstance(lanes, dict)
    assert isinstance(informational, dict)
    assert lanes["binding_reference_coverage"] == "passed"
    assert payload["partial_lanes"] == []
    assert informational["total"] == 4


def test_an_empty_corpus_reports_both_lines_as_zero() -> None:
    """Both lines are always present, so silence is reported rather than omitted."""
    payload = _payload(_status(unreferenced=(), informational=()), blocking=False)

    assert payload["informational_bindings"] == {"total": 0, "by_modelo": {}}
    assert payload["unreferenced_bindings"] == {"total": 0, "by_modelo": {}}
