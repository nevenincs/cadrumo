"""Persisted certificate-session metadata holds the canonical UTC instants.

``PersistedSessionMetadata.authenticated_at`` and ``idle_deadline`` documented
UTC and enforced nothing. Both are compared against the clock when a session
is resumed, so a naive value would be read as though it were UTC and could
extend or expire an idle deadline by the local offset — silently lengthening
a session the operator believes has already lapsed.

The metadata persists inside the encrypted session envelope as JSON
(``model_dump_json`` / ``model_validate_json`` in ``session_store``), which
preserves the offset, so the canonical contract is enforceable here. That is
deliberately not true of the SQL-column-backed records elsewhere, where
SQLite drops the offset on read.

Every refusal is paired with the value it accepts, so a validator that begins
refusing everything is distinguishable from one that refuses the right thing.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from ..authenticator_persistence import PersistedSessionMetadata

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_AWARE = datetime(2026, 4, 1, 10, 30, tzinfo=UTC)
_LATER = datetime(2026, 4, 1, 12, 30, tzinfo=UTC)
_NAIVE = datetime(2026, 4, 1, 10, 30)
_OFFSET = datetime(2026, 4, 1, 10, 30, tzinfo=timezone(timedelta(hours=1)))
_SHA = "a" * 64


def _metadata(**overrides: object) -> PersistedSessionMetadata:
    fields: dict[str, object] = {
        "certificate_thumbprint": "thumb",
        "certificate_subject": "CN=Operator",
        "certificate_nif": "12345678Z",
        "authenticated_at": _AWARE,
        "idle_deadline": _LATER,
        "storage_state_sha256": _SHA,
    }
    fields.update(overrides)
    return PersistedSessionMetadata.model_validate(fields)


def test_utc_aware_instants_are_accepted() -> None:
    """Positive control: the contract admits the values it exists to require."""
    metadata = _metadata()

    assert metadata.authenticated_at == _AWARE
    assert metadata.idle_deadline == _LATER


@pytest.mark.parametrize("field", ["authenticated_at", "idle_deadline"])
def test_naive_instant_is_refused(field: str) -> None:
    with pytest.raises(ValidationError):
        _metadata(**{field: _NAIVE})


@pytest.mark.parametrize("field", ["authenticated_at", "idle_deadline"])
def test_non_utc_offset_instant_is_refused(field: str) -> None:
    """A non-zero offset shifts the deadline the resume path compares against."""
    with pytest.raises(ValidationError):
        _metadata(**{field: _OFFSET})


def test_json_round_trip_preserves_both_instants() -> None:
    """The transport that makes this contract enforceable is exercised here."""
    original = _metadata()

    restored = PersistedSessionMetadata.model_validate_json(original.model_dump_json())

    assert restored == original
    assert restored.authenticated_at.tzinfo is not None
    assert restored.idle_deadline.tzinfo is not None
