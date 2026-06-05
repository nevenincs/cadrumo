"""Tests for the manifest atomic-write and strict-read surface."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from ......core.errors import build_error_envelope
from ......core.external_constants import UTF_8_ENCODING
from ...errors import StorageValidationError
from .._layout import bucket_paths, provision_bucket_directory
from .._manifest import (
    BucketLifecycleStatus,
    BucketManifest,
    ManifestKdfParams,
)
from .._manifest_io import (
    manifest_path,
    read_manifest,
    write_manifest,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def _fixture_manifest(*, last_unlocked: bool = True) -> BucketManifest:
    kdf = ManifestKdfParams(
        algorithm="argon2id",
        version=19,
        memory_cost=19_456,
        time_cost=2,
        parallelism=1,
        salt=b"0123456789abcdef",
        output_length=32,
    )
    return BucketManifest(
        bucket_id="alpha",
        label="Alpha bucket",
        created_at=datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC),
        last_unlocked_at=datetime(2026, 5, 14, 13, 30, 0, tzinfo=UTC) if last_unlocked else None,
        kdf_params=kdf,
        recovery_enrolled=True,
        schema_version=1,
        status=BucketLifecycleStatus.ACTIVE,
    )


def test_write_then_read_round_trip(tmp_path: Path) -> None:
    paths = provision_bucket_directory(tmp_path, "alpha")
    manifest = _fixture_manifest()

    write_manifest(paths, manifest)
    loaded = read_manifest(paths)

    assert loaded == manifest
    assert loaded.kdf_params.salt == manifest.kdf_params.salt


def test_write_emits_datetime_fields_as_toml_offset_datetimes(tmp_path: Path) -> None:
    paths = provision_bucket_directory(tmp_path, "alpha")
    manifest = _fixture_manifest()

    write_manifest(paths, manifest)
    text = manifest_path(paths).read_text(encoding=UTF_8_ENCODING)

    assert "created_at = 2026-05-14T12:00:00+00:00\n" in text
    assert "last_unlocked_at = 2026-05-14T13:30:00+00:00\n" in text


def test_round_trip_preserves_absent_last_unlocked(tmp_path: Path) -> None:
    paths = provision_bucket_directory(tmp_path, "alpha")
    manifest = _fixture_manifest(last_unlocked=False)

    write_manifest(paths, manifest)
    loaded = read_manifest(paths)

    assert loaded.last_unlocked_at is None
    assert loaded == manifest


def test_write_is_atomic_no_tmp_file_lingers(tmp_path: Path) -> None:
    paths = provision_bucket_directory(tmp_path, "alpha")
    manifest = _fixture_manifest()

    write_manifest(paths, manifest)

    target = manifest_path(paths)
    assert target.is_file()
    assert not target.with_suffix(target.suffix + ".tmp").exists()


def test_overwrite_replaces_previous_manifest(tmp_path: Path) -> None:
    paths = provision_bucket_directory(tmp_path, "alpha")
    first = _fixture_manifest()
    second = first.model_copy(update={"label": "Renamed"})

    write_manifest(paths, first)
    write_manifest(paths, second)
    loaded = read_manifest(paths)

    assert loaded.label == "Renamed"


def test_read_rejects_unknown_key(tmp_path: Path) -> None:
    paths = provision_bucket_directory(tmp_path, "alpha")
    write_manifest(paths, _fixture_manifest())

    target = manifest_path(paths)
    text = target.read_text(encoding=UTF_8_ENCODING)
    target.write_text(text + 'stowaway = "x"\n', encoding=UTF_8_ENCODING)

    with pytest.raises(ValidationError):
        read_manifest(paths)


def test_read_rejects_missing_status_key(tmp_path: Path) -> None:
    paths = provision_bucket_directory(tmp_path, "alpha")
    write_manifest(paths, _fixture_manifest())

    target = manifest_path(paths)
    text = target.read_text(encoding=UTF_8_ENCODING)
    target.write_text(
        "\n".join(line for line in text.splitlines() if not line.startswith("status = ")) + "\n",
        encoding=UTF_8_ENCODING,
    )

    with pytest.raises(StorageValidationError, match="lifecycle status"):
        read_manifest(paths)


def test_read_raises_when_manifest_absent(tmp_path: Path) -> None:
    paths = provision_bucket_directory(tmp_path, "alpha")

    with pytest.raises(StorageValidationError, match="bucket manifest is missing") as excinfo:
        read_manifest(paths)
    assert isinstance(excinfo.value.__cause__, FileNotFoundError)
    assert excinfo.value.translated_message == "errors.integrity.integrity_storage_bucket_validation"
    assert str(tmp_path) not in str(excinfo.value)
    envelope = build_error_envelope(excinfo.value)
    assert str(tmp_path) not in envelope.model_dump_json()


def test_write_wraps_missing_bucket_directory_as_storage_validation(tmp_path: Path) -> None:
    paths = bucket_paths(tmp_path, "alpha")

    with pytest.raises(StorageValidationError, match="bucket manifest cannot be written") as excinfo:
        write_manifest(paths, _fixture_manifest())
    assert isinstance(excinfo.value.__cause__, FileNotFoundError)
    assert excinfo.value.translated_message == "errors.integrity.integrity_storage_bucket_validation"
    assert str(tmp_path) not in str(excinfo.value)
    envelope = build_error_envelope(excinfo.value)
    assert str(tmp_path) not in envelope.model_dump_json()


def test_torn_write_does_not_corrupt_existing_manifest(tmp_path: Path) -> None:
    """A crash before os.replace leaves the previous good manifest intact.

    Simulated by writing a good manifest, then dropping a partial payload at
    the ``.tmp`` sibling (as if the process crashed before the rename), and
    finally re-reading; the canonical manifest must still validate.
    """

    paths = provision_bucket_directory(tmp_path, "alpha")
    good = _fixture_manifest()
    write_manifest(paths, good)

    target = manifest_path(paths)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text('bucket_id = "partial', encoding=UTF_8_ENCODING)

    loaded = read_manifest(paths)
    assert loaded == good


def test_manifest_datetimes_are_written_as_rfc3339_offset_datetimes(tmp_path: Path) -> None:
    """On-disk inspection: manifest datetimes are bare RFC-3339 offset datetimes.

    ``read_manifest`` round-tripping a value proves the writer and the
    reader agree, but not that the *wire* form is the TOML-native
    offset-datetime the manifest contract declares. A regression that
    quoted the datetime (TOML string) or dropped the offset would still
    round-trip through ``tomllib`` as a plain string while corrupting
    interoperability with any other RFC-3339 consumer. This test reads
    the raw ``manifest.toml`` bytes and asserts each datetime line
    carries an unquoted, timezone-aware, UTC ISO-8601 value.
    """

    import tomllib

    paths = provision_bucket_directory(tmp_path, "alpha")
    manifest = _fixture_manifest()
    write_manifest(paths, manifest)

    text = manifest_path(paths).read_text(encoding=UTF_8_ENCODING)
    lines = {
        key: value.strip()
        for key, _, value in (line.partition(" = ") for line in text.splitlines())
        if key in {"created_at", "last_unlocked_at"}
    }

    # Bare (unquoted) TOML datetime, not a string literal.
    assert lines["created_at"] and not lines["created_at"].startswith(('"', "'"))
    assert lines["last_unlocked_at"] and not lines["last_unlocked_at"].startswith(('"', "'"))

    for raw in (lines["created_at"], lines["last_unlocked_at"]):
        parsed = datetime.fromisoformat(raw)
        assert parsed.tzinfo is not None and parsed.utcoffset() == UTC.utcoffset(None)

    # tomllib parses the bare value back into a real aware datetime.
    document = tomllib.loads(text)
    assert document["created_at"] == manifest.created_at
    assert document["last_unlocked_at"] == manifest.last_unlocked_at
