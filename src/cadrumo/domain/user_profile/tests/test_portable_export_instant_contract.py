"""Carried secure-object rows hold the canonical UTC instant contract.

``CarriedSecureObject.written_at`` documented a UTC write instant and enforced
nothing, so a portable bundle could transport an ambiguous local time into
another bucket, where it would be read back as though it were UTC.

The bundle serialises as JSON, which preserves the offset, so the canonical
``validate_utc_aware`` contract is enforceable at this boundary. That is
deliberately not true of the SQL-column-backed records elsewhere: SQLite drops
the offset on read, so the same validator there would refuse the row the
current code just wrote.

Each refusal is paired with the valid value it accepts, so a validator that
begins refusing everything is distinguishable from one that refuses the right
thing.
"""

from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from ....core.classification.policies import SensitivityClass
from ..portable_export import CarriedSecureObject

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_AWARE = datetime(2026, 4, 1, 10, 30, tzinfo=UTC)
_NAIVE = datetime(2026, 4, 1, 10, 30)
_OFFSET = datetime(2026, 4, 1, 10, 30, tzinfo=timezone(timedelta(hours=1)))


def _carried(written_at: datetime) -> CarriedSecureObject:
    return CarriedSecureObject(
        namespace="secure-objects",
        object_key="object-1",
        classification=SensitivityClass.FINANCIAL,
        schema_version=1,
        written_at=written_at,
        payload_b64=base64.b64encode(b"ciphertext").decode("ascii"),
    )


def test_utc_aware_write_instant_is_accepted() -> None:
    """Positive control: the contract admits the value it exists to require."""
    assert _carried(_AWARE).written_at == _AWARE


def test_naive_write_instant_is_refused() -> None:
    with pytest.raises(ValidationError):
        _carried(_NAIVE)


def test_non_utc_offset_write_instant_is_refused() -> None:
    """A non-zero offset is a different instant claim, not a formatting detail."""
    with pytest.raises(ValidationError):
        _carried(_OFFSET)


def test_json_round_trip_preserves_the_instant() -> None:
    """The transport that makes this contract enforceable is exercised here."""
    original = _carried(_AWARE)

    restored = CarriedSecureObject.model_validate_json(original.model_dump_json())

    assert restored.written_at == _AWARE
    assert restored.written_at.tzinfo is not None
    assert restored == original
