"""A malformed Drive response is refused, not smoothed into plausible metadata.

``_metadata_from_drive_entry`` is the single site both ``get`` and
``iter_objects`` build :class:`ProviderObjectMetadata` from, so exercising it
directly is exercising both read surfaces — and it is a pure function over the
Drive response dict, so no Drive double is needed or wanted here. The response
shapes below are the ones the API really produces: ``size`` arrives as a
decimal STRING, ``modifiedTime`` as an RFC 3339 instant with a ``Z`` suffix.

Two coercions used to hide upstream corruption. A missing or unparseable
``modifiedTime`` fell back to ``now()``, so a damaged remote object reported
itself as freshly written — and because ``get`` and ``iter_objects`` are two
Drive calls at two instants, the same object then exposed two different
``written_at`` values depending on which surface an operator read. A ``size``
that failed to coerce silently became ``0``, asserting a zero-byte contract
that no downstream check re-tested: ``get`` compares only the DOWNLOADED
payload's length against it, so an empty object with a malformed size passed
both surfaces clean.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from .._google_drive_metadata import _metadata_from_drive_entry
from ..errors import OutboundStorageIntegrityError

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_NAMESPACE = "ledger_transaction"
_HMAC = "abcdef0123456789"
_DIGEST = f"sha256-{'3a' * 32}"


def _entry(**overrides: Any) -> dict[str, Any]:
    """Return a well-formed Drive ``files().get`` response, with overrides applied.

    Every field carries the shape Drive really sends, so a single override is
    the only thing separating a passing case from a refused one.
    """
    entry: dict[str, Any] = {
        "id": "drive-file-id",
        "name": f"{_HMAC[:8]}--label.bin",
        "size": "12",
        "md5Checksum": "0" * 32,
        "modifiedTime": "2026-08-02T01:45:29.978Z",
        "appProperties": {"content_hash": _DIGEST, "object_key_hmac": _HMAC},
    }
    entry.update(overrides)
    return entry


def _metadata(entry: dict[str, Any]):
    return _metadata_from_drive_entry(entry, namespace=_NAMESPACE, object_key_hmac=_HMAC)


def test_a_well_formed_entry_still_converts() -> None:
    """The positive control every refusal below is measured against.

    Without it a helper that refused everything would satisfy the whole
    module.
    """
    metadata = _metadata(_entry())

    assert metadata.byte_length == 12
    assert metadata.written_at == datetime(2026, 8, 2, 1, 45, 29, 978000, tzinfo=UTC)
    assert metadata.content_hash == _DIGEST
    assert metadata.object_key_hmac == _HMAC


@pytest.mark.parametrize(
    "modified_time",
    [
        pytest.param("not-a-time", id="unparseable"),
        pytest.param("", id="blank"),
        pytest.param(None, id="null"),
        pytest.param(1735819200, id="wrong-type-epoch-int"),
        pytest.param("2026-08-02T01:45:29.978", id="tz-naive"),
    ],
)
def test_a_malformed_modified_time_is_refused(modified_time: object) -> None:
    """The adapter reports corruption instead of a freshly minted timestamp."""
    with pytest.raises(OutboundStorageIntegrityError):
        _metadata(_entry(modifiedTime=modified_time))


def test_an_absent_modified_time_is_refused() -> None:
    """A response missing the field entirely is refused like a malformed one.

    Drive is asked for ``modifiedTime`` on every read that builds metadata, so
    its absence is a broken response rather than an optional field.
    """
    entry = _entry()
    del entry["modifiedTime"]

    with pytest.raises(OutboundStorageIntegrityError):
        _metadata(entry)


@pytest.mark.parametrize(
    "size",
    [
        pytest.param("bogus", id="non-numeric-string"),
        pytest.param("", id="blank"),
        pytest.param(None, id="null"),
        pytest.param("-1", id="negative-string"),
        pytest.param(-1, id="negative-int"),
        pytest.param("12.5", id="fractional"),
        pytest.param([12], id="wrong-type-list"),
        pytest.param(True, id="wrong-type-bool"),
    ],
)
def test_a_malformed_size_is_refused(size: object) -> None:
    """A broken size is reported, not silently rewritten to zero.

    ``bool`` is called out because it is an ``int`` subclass: ``int(True)`` is
    ``1``, so a permissive numeric check would have accepted a boolean as a
    one-byte object.
    """
    with pytest.raises(OutboundStorageIntegrityError):
        _metadata(_entry(size=size))


def test_an_absent_size_is_refused() -> None:
    """A response missing ``size`` entirely is refused like a malformed one.

    Every object this adapter writes is an uploaded binary blob, never a
    native Google document — the file kind whose size Drive genuinely omits —
    so an absent size is a broken response rather than an optional field.
    """
    entry = _entry()
    del entry["size"]

    with pytest.raises(OutboundStorageIntegrityError):
        _metadata(entry)


def test_a_malformed_size_on_an_empty_object_is_still_refused() -> None:
    """The case the downstream length check could never catch.

    ``get`` compares only the DOWNLOADED payload's length against
    ``byte_length``, so for an empty payload the coerced ``0`` agreed with
    reality and the malformed response passed clean; ``iter_objects``
    downloads nothing and had no second opinion at all. The refusal has to
    happen where the value is parsed.
    """
    with pytest.raises(OutboundStorageIntegrityError):
        _metadata(_entry(size="bogus", md5Checksum="d41d8cd98f00b204e9800998ecf8427e"))


def test_a_genuinely_empty_object_still_converts() -> None:
    """Zero is a legitimate size, and refusing malformed ones must not ban it."""
    metadata = _metadata(_entry(size="0"))

    assert metadata.byte_length == 0


def test_two_conversions_of_one_entry_report_the_same_instant() -> None:
    """The parity the ``now()`` fallback could not hold.

    ``get`` and ``iter_objects`` convert at different instants, so under the
    fallback the same object reported two different write times. Converting
    the same entry twice is exactly that comparison with the timing removed:
    the answer must come from the response, not from the clock.
    """
    entry = _entry()

    first = _metadata(entry)
    second = _metadata(entry)

    assert first.written_at == second.written_at
    assert first.written_at.tzinfo is not None
    assert first.written_at.utcoffset() is not None
