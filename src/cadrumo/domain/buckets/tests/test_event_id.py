"""Real-behavior tests for the :data:`~domain.buckets.BucketEventId` alias.

``BucketEventId`` is one of the hex-64 identity aliases that all derive from
the single canonical :data:`~core.Hex64Str` primitive (see
:mod:`~core.tests.test_hex64_identity`), so this suite proves it accepts and
rejects the same canonical shape as the core-owned siblings and stays a
literal reuse of the shared primitive rather than a re-declared equivalent.
"""

from __future__ import annotations

import hashlib

import pytest
from pydantic import ValidationError

from ....core.hex import Hex64Str
from ....tests.fixtures.identity_holder import single_field_holder
from ..event import BucketEventId

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_Holder = single_field_holder("event_id", BucketEventId)
_CANONICAL_DIGEST = hashlib.sha256(b"payload").hexdigest()


def test_bucket_event_id_is_the_canonical_hex64_primitive() -> None:
    assert BucketEventId is Hex64Str


def test_bucket_event_id_accepts_canonical_digest() -> None:
    assert _Holder.value_of(_Holder.build(_CANONICAL_DIGEST)) == _CANONICAL_DIGEST


@pytest.mark.parametrize(
    "event_id",
    (
        pytest.param(_CANONICAL_DIGEST.upper(), id="uppercase"),
        pytest.param("a" * 63, id="too-short"),
        pytest.param("a" * 65, id="too-long"),
        pytest.param("g" * 64, id="non-hex"),
    ),
)
def test_bucket_event_id_rejects_invalid_values(event_id: str) -> None:
    with pytest.raises(ValidationError):
        _Holder.build(event_id)
