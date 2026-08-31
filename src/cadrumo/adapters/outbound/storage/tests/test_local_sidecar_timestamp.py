"""A damaged sidecar timestamp is corruption, not a fresh write.

``get`` and ``iter_objects`` each parsed the local sidecar's persisted
``written_at`` with their own copy of the same three lines, and both replaced a
missing or unparseable value with ``now()``. The payload stayed readable while
its chronology quietly did not, and — because the two surfaces call the clock
at different instants — the SAME object reported two different write times
depending on which read surface an operator used. Nothing downstream could
learn the sidecar had been damaged.

Both paths now go through one parser that refuses. The parity assertion is the
load-bearing one: an equality between the two surfaces is what the ``now()``
fallback could not satisfy and no amount of per-surface patching would.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from .._local import LocalFileSystemProvider
from ..errors import StorageCorruptionError

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_NAMESPACE = "ledger_transaction"
_HMAC = "abcdef0123456789"
_PAYLOAD = b"sidecar timestamp probe"


def _hash(payload: bytes) -> str:
    return f"sha256-{hashlib.sha256(payload).hexdigest()}"


def _stored_sidecar(provider: LocalFileSystemProvider) -> Path:
    """Write one real object and return its sidecar path."""
    metadata = provider.put(
        _NAMESPACE,
        _HMAC,
        _PAYLOAD,
        content_hash=_hash(_PAYLOAD),
        label="timestamp-probe",
    )
    target = Path(metadata.provider_object_id)
    return target.with_name(target.stem + ".meta.json")


def _rewrite_written_at(sidecar: Path, value: object) -> None:
    """Replace only the sidecar's ``written_at``, leaving every other field intact.

    Damaging one field keeps the payload, digest and byte length correct, so a
    refusal here can only come from the timestamp and not from the content-hash
    or byte-length gate.
    """
    body = json.loads(sidecar.read_text(encoding="utf-8"))
    if value is None:
        body.pop("written_at", None)
    else:
        body["written_at"] = value
    sidecar.write_text(json.dumps(body), encoding="utf-8")


_DAMAGED = (
    pytest.param("not-a-time", id="unparseable"),
    pytest.param("", id="blank"),
    pytest.param(None, id="absent"),
    pytest.param("2026-01-02T12:00:00", id="tz-naive"),
    pytest.param(1735819200, id="wrong-type-epoch-int"),
)


@pytest.mark.parametrize("damaged", _DAMAGED)
def test_get_refuses_a_damaged_sidecar_timestamp(
    provider: LocalFileSystemProvider,
    damaged: object,
) -> None:
    """``get`` raises a typed corruption error instead of inventing a time."""
    sidecar = _stored_sidecar(provider)
    _rewrite_written_at(sidecar, damaged)

    with pytest.raises(StorageCorruptionError):
        provider.get(_NAMESPACE, _HMAC)


@pytest.mark.parametrize("damaged", _DAMAGED)
def test_iter_objects_refuses_a_damaged_sidecar_timestamp(
    provider: LocalFileSystemProvider,
    damaged: object,
) -> None:
    """``iter_objects`` refuses identically, rather than yielding a synthetic row.

    Enumerating is where the invented timestamp did the most damage: an
    operator listing a namespace saw a plausible recent write for an object
    whose metadata was destroyed.
    """
    sidecar = _stored_sidecar(provider)
    _rewrite_written_at(sidecar, damaged)

    with pytest.raises(StorageCorruptionError):
        list(provider.iter_objects(_NAMESPACE))


def test_a_naive_timestamp_is_refused_rather_than_read_as_utc(provider: LocalFileSystemProvider) -> None:
    """Assuming UTC would recover a wrong instant wherever the writer was not.

    Called out on its own because it is the tempting weakening: a naive value
    parses, so a lenient reader accepts it and silently shifts the instant by
    the writer's offset. The writer always stores an aware instant, so a naive
    one is damage.
    """
    sidecar = _stored_sidecar(provider)
    _rewrite_written_at(sidecar, "2026-01-02T12:00:00")

    with pytest.raises(StorageCorruptionError):
        provider.get(_NAMESPACE, _HMAC)


def test_the_two_read_surfaces_report_one_timestamp_for_an_intact_object(
    provider: LocalFileSystemProvider,
) -> None:
    """The parity the ``now()`` fallback could not hold.

    Two clock reads at different instants produced two different ``written_at``
    values for one object. Both surfaces now report the persisted instant, so
    they agree by construction rather than by luck of timing. This is also the
    positive control for the refusals above: an intact sidecar must still read.
    """
    provider.put(
        _NAMESPACE,
        _HMAC,
        _PAYLOAD,
        content_hash=_hash(_PAYLOAD),
        label="timestamp-probe",
    )

    _, from_get = provider.get(_NAMESPACE, _HMAC)
    (from_iter,) = [row for row in provider.iter_objects(_NAMESPACE) if row.object_key_hmac == _HMAC]

    assert from_get.written_at == from_iter.written_at
    assert from_get.written_at.tzinfo is not None
    assert from_get.written_at.utcoffset() is not None


def test_the_damage_is_confined_to_the_timestamp(provider: LocalFileSystemProvider) -> None:
    """Prove the fixture damages only ``written_at``.

    Without this the refusals above could be earned by a mangled sidecar
    failing the content-hash or byte-length gate, which would prove the
    pre-existing guards rather than the new one.
    """
    sidecar = _stored_sidecar(provider)
    intact = json.loads(sidecar.read_text(encoding="utf-8"))
    _rewrite_written_at(sidecar, "not-a-time")
    damaged = json.loads(sidecar.read_text(encoding="utf-8"))

    assert damaged["content_hash"] == intact["content_hash"]
    assert damaged["byte_length"] == intact["byte_length"]
    assert damaged["object_key_hmac"] == intact["object_key_hmac"]
    assert {key for key in damaged if damaged[key] != intact.get(key)} == {"written_at"}
