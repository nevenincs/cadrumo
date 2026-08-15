"""Tests for the :class:`BucketPointer` active-bucket pointer record."""

from __future__ import annotations

import multiprocessing
import os
import stat
import time
from multiprocessing.synchronize import Event
from pathlib import Path
from typing import Literal, TypedDict, get_args

import pytest
from pydantic import ValidationError

from .. import (
    BucketPointer,
    capture_pointer,
    clear_pointer,
    iter_directory,
    pointer_path,
    read_pointer,
    restore_pointer,
    scan_directory,
    write_pointer,
)
from .._bucket_pointer import POINTER_SCHEMA_VERSION

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


class _BucketPointerKwargs(TypedDict):
    bucket_id: str
    schema_version: Literal[1]


_CHILD_TIMEOUT_SECONDS = 10.0


def _restore_pointer_until_interrupted(root: Path, payload: bytes, started: Event) -> None:
    started.set()
    while True:
        restore_pointer(root, payload)


def test_json_round_trip() -> None:
    pointer = BucketPointer(bucket_id="bucket-001", schema_version=1)
    revived = BucketPointer.model_validate_json(pointer.model_dump_json())
    assert revived == pointer


def test_pointer_bucket_id_uses_canonical_identity_normalization() -> None:
    """Pointer selectors trim at the same strict boundary as every bucket-bearing record."""
    pointer = BucketPointer(bucket_id="  profile-bucket  ", schema_version=1)
    assert pointer.bucket_id == "profile-bucket"


def test_toml_round_trip() -> None:
    """The current document survives to_toml/from_toml, quoting included.

    Both cases carry the canonical version because that is the only version
    the record accepts: the bucket-id shapes are what vary here, and the
    escaped-quote case is the one that exercises the hand-written serialiser.
    """
    for bucket_id in ("bucket-001", 'bucket "weird" id'):
        pointer = BucketPointer(bucket_id=bucket_id, schema_version=POINTER_SCHEMA_VERSION)

        text = pointer.to_toml()

        assert f"schema_version = {POINTER_SCHEMA_VERSION}\n" in text
        assert BucketPointer.from_toml(text) == pointer


def test_the_declared_version_is_the_version_the_model_enforces() -> None:
    """The named constant and the constraint that refuses must agree.

    They are declared independently -- one as a module constant, one as a
    ``Literal`` annotation -- so this is a real relation rather than a value
    compared against its own definition. Without it the constant could drift
    into naming a version the record does not actually accept.
    """
    enforced = get_args(BucketPointer.model_fields["schema_version"].annotation)

    assert enforced == (POINTER_SCHEMA_VERSION,), (
        f"the pointer record enforces schema_version in {enforced} while the declared "
        f"current version is {POINTER_SCHEMA_VERSION}; the constant and the Literal must move together"
    )


def test_rejects_invalid_constructor_fields() -> None:
    cases: tuple[_BucketPointerKwargs, ...] = (
        {"bucket_id": "", "schema_version": 1},
        {"bucket_id": "   ", "schema_version": 1},
        {"bucket_id": "x" * 129, "schema_version": 1},
    )
    for kwargs in cases:
        with pytest.raises(ValidationError):
            BucketPointer(**kwargs)


@pytest.mark.parametrize("claimed", [0, 2, 7])
def test_from_toml_refuses_a_non_current_schema_version(claimed: int) -> None:
    """A pointer claiming any other version refuses, naming both versions.

    Pre-current and future refuse alike: neither is a document this code
    implements, and the pointer decides which encrypted bucket every later
    read and write lands in.
    """
    text = f'bucket_id = "bucket-001"\nschema_version = {claimed}\n'

    with pytest.raises(ValidationError) as excinfo:
        BucketPointer.from_toml(text)

    errors = excinfo.value.errors()
    assert [error["loc"] for error in errors] == [("schema_version",)]
    assert errors[0]["input"] == claimed
    rendered = str(excinfo.value)
    assert str(claimed) in rendered
    assert str(POINTER_SCHEMA_VERSION) in rendered


def test_from_toml_refuses_a_pointer_omitting_the_schema_version() -> None:
    """A document making no version claim is not read as the current one."""
    with pytest.raises(ValidationError) as excinfo:
        BucketPointer.from_toml('bucket_id = "bucket-001"\n')

    errors = excinfo.value.errors()
    assert [error["loc"] for error in errors] == [("schema_version",)]
    assert errors[0]["type"] == "missing"


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


def test_deleting_the_version_line_on_disk_surfaces_at_read(tmp_path: Path) -> None:
    """Anti-tautology proof: a real pointer stripped of its version must refuse at read.

    Writes the pointer through the production write path, removes the
    ``schema_version`` line from the bytes on disk, then reads it back through
    :func:`read_pointer`. A tolerant record would re-default the field and
    hand back a pointer naming the bucket every later read and write lands in,
    so the refusal is what proves the pinned version reaches the file boundary
    rather than only the in-memory constructor.
    """
    pointer = BucketPointer(bucket_id="bucket-001", schema_version=POINTER_SCHEMA_VERSION)
    write_pointer(tmp_path, pointer)
    assert read_pointer(tmp_path) == pointer

    target = pointer_path(tmp_path)
    stripped = "".join(
        line
        for line in target.read_text(encoding="utf-8").splitlines(keepends=True)
        if not line.startswith("schema_version")
    )
    assert "schema_version" not in stripped, "the fixture must actually remove the version line"
    target.write_text(stripped, encoding="utf-8")

    with pytest.raises(ValidationError):
        read_pointer(tmp_path)


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
    assert scan_directory(tmp_path, pattern="active-profile.*.tmp") == ()
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
            observed_temp = next(iter_directory(tmp_path, pattern=temp_pattern), None)
            if observed_temp is not None:
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
        for child_temp in scan_directory(tmp_path, pattern=temp_pattern):
            child_temp.unlink(missing_ok=True)
        process.close()
