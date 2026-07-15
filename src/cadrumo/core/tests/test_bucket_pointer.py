"""Tests for the :class:`BucketPointer` active-bucket pointer record."""

from __future__ import annotations

import multiprocessing
import os
import stat
import time
from multiprocessing.synchronize import Event
from pathlib import Path
from typing import TypedDict

import pytest
from pydantic import ValidationError

from .. import (
    BucketPointer,
    capture_pointer,
    clear_pointer,
    pointer_path,
    restore_pointer,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


class _BucketPointerKwargs(TypedDict):
    bucket_id: str
    schema_version: int


_CHILD_TIMEOUT_SECONDS = 10.0


def _restore_pointer_until_interrupted(root: Path, payload: bytes, started: Event) -> None:
    started.set()
    while True:
        restore_pointer(root, payload)


def test_json_round_trip() -> None:
    pointer = BucketPointer(bucket_id="bucket-001", schema_version=1)
    revived = BucketPointer.model_validate_json(pointer.model_dump_json())
    assert revived == pointer


def test_toml_round_trip() -> None:
    for bucket_id, schema_version in (
        ("bucket-001", 1),
        ('bucket "weird" id', 2),
    ):
        pointer = BucketPointer(bucket_id=bucket_id, schema_version=schema_version)
        revived = BucketPointer.from_toml(pointer.to_toml())
        assert revived == pointer


def test_rejects_invalid_constructor_fields() -> None:
    cases: tuple[_BucketPointerKwargs, ...] = (
        {"bucket_id": "", "schema_version": 1},
        {"bucket_id": "bucket-001", "schema_version": 0},
    )
    for kwargs in cases:
        with pytest.raises(ValidationError):
            BucketPointer(**kwargs)


def test_rejects_unknown_keys() -> None:
    with pytest.raises(ValidationError):
        BucketPointer.model_validate(
            {
                "bucket_id": "bucket-001",
                "schema_version": 1,
                "unexpected": "nope",
            },
        )


def test_from_toml_rejects_invalid_payloads() -> None:
    for text in (
        'bucket_id = "bucket-001"\nschema_version = 1\nrogue = "x"\n',
        "schema_version = 1\n",
    ):
        with pytest.raises(ValidationError):
            BucketPointer.from_toml(text)


def test_pointer_capture_restore_and_clear_preserve_exact_bytes(tmp_path: Path) -> None:
    prior_payload = b"prior-pointer-bytes\n"
    payload = b"\xef\xbb\xbfnot-toml\x00\xff\x80\nline-two\r\ntrailing\r"

    assert capture_pointer(tmp_path) is None

    restore_pointer(tmp_path, prior_payload)
    assert capture_pointer(tmp_path) == prior_payload

    restore_pointer(tmp_path, payload)

    target = pointer_path(tmp_path)
    assert target.read_bytes() == payload
    assert capture_pointer(tmp_path) == payload
    assert list(tmp_path.glob("active-profile.*.tmp")) == []
    if os.name != "nt":
        assert stat.S_IMODE(target.stat().st_mode) == 0o600

    clear_pointer(tmp_path)
    assert capture_pointer(tmp_path) is None
    assert not target.exists()

    clear_pointer(tmp_path)
    assert capture_pointer(tmp_path) is None
    assert not target.exists()

    restore_pointer(tmp_path, payload)
    restore_pointer(tmp_path, None)
    assert capture_pointer(tmp_path) is None
    assert not target.exists()


def test_interrupted_restore_never_exposes_torn_pointer(tmp_path: Path) -> None:
    old_payload = b"OLD\x00\xff\ncomplete\r\n"
    new_payload = b"NEW\x80\x00\xff\r\n" + bytes(range(256)) * 65_536
    restore_pointer(tmp_path, old_payload)

    context = multiprocessing.get_context("spawn")
    started = context.Event()
    process = context.Process(
        target=_restore_pointer_until_interrupted,
        args=(tmp_path, new_payload, started),
    )
    process.start()
    temp_pattern = f"active-profile.{process.pid}.*.tmp"
    try:
        assert started.wait(timeout=_CHILD_TIMEOUT_SECONDS)

        observed_temp: Path | None = None
        deadline = time.monotonic() + _CHILD_TIMEOUT_SECONDS
        while time.monotonic() < deadline and process.is_alive():
            child_temps = list(tmp_path.glob(temp_pattern))
            if child_temps:
                observed_temp = child_temps[0]
                break
            process.join(timeout=0.001)

        assert observed_temp is not None
        assert process.is_alive()

        process.terminate()
        process.join(timeout=_CHILD_TIMEOUT_SECONDS)
        if process.is_alive():
            process.kill()
            process.join(timeout=_CHILD_TIMEOUT_SECONDS)

        assert not process.is_alive()
        assert process.exitcode is not None
        assert process.exitcode != 0
        assert capture_pointer(tmp_path) in {old_payload, new_payload}
    finally:
        if process.is_alive():
            process.terminate()
            process.join(timeout=_CHILD_TIMEOUT_SECONDS)
            if process.is_alive():
                process.kill()
                process.join(timeout=_CHILD_TIMEOUT_SECONDS)
        for child_temp in tmp_path.glob(temp_pattern):
            child_temp.unlink(missing_ok=True)
        process.close()
