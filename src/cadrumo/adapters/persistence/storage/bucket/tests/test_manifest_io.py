"""Tests for the manifest atomic-write and strict-read surface."""

from __future__ import annotations

import tomllib
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from ......core.errors import build_error_envelope
from ......core.external_constants import UTF_8_ENCODING
from ......domain.user_profile import UserProfileStatus
from ...errors import StorageValidationError
from .._layout import BucketPaths, bucket_paths, provision_bucket_directory
from .._manifest import (
    BUCKET_MANIFEST_SCHEMA_VERSION,
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
        schema_version=BUCKET_MANIFEST_SCHEMA_VERSION,
        status=UserProfileStatus.ACTIVE,
    )


def _write_fixture_manifest(
    tmp_path: Path,
    *,
    last_unlocked: bool = True,
) -> tuple[BucketPaths, BucketManifest]:
    paths = provision_bucket_directory(tmp_path, "alpha")
    manifest = _fixture_manifest(last_unlocked=last_unlocked)
    write_manifest(paths, manifest)
    return paths, manifest


def test_write_then_read_round_trip(tmp_path: Path) -> None:
    paths, manifest = _write_fixture_manifest(tmp_path)
    loaded = read_manifest(paths)

    assert loaded == manifest
    assert loaded.kdf_params.salt == manifest.kdf_params.salt


def test_round_trip_preserves_absent_last_unlocked(tmp_path: Path) -> None:
    paths, manifest = _write_fixture_manifest(tmp_path, last_unlocked=False)
    loaded = read_manifest(paths)

    assert loaded.last_unlocked_at is None
    assert loaded == manifest


def test_write_is_atomic_no_tmp_file_lingers(tmp_path: Path) -> None:
    paths, _manifest = _write_fixture_manifest(tmp_path)

    target = manifest_path(paths)
    assert target.is_file()
    assert list(target.parent.glob("*.tmp")) == []


def test_overwrite_replaces_previous_manifest(tmp_path: Path) -> None:
    paths = provision_bucket_directory(tmp_path, "alpha")
    first = _fixture_manifest()
    second = first.model_copy(update={"label": "Renamed"})

    write_manifest(paths, first)
    write_manifest(paths, second)
    loaded = read_manifest(paths)

    assert loaded.label == "Renamed"


def test_read_rejects_unknown_key(tmp_path: Path) -> None:
    paths, _manifest = _write_fixture_manifest(tmp_path)

    target = manifest_path(paths)
    text = target.read_text(encoding=UTF_8_ENCODING)
    target.write_text(text + 'stowaway = "x"\n', encoding=UTF_8_ENCODING)

    with pytest.raises(ValidationError):
        read_manifest(paths)


def test_read_rejects_missing_status_key(tmp_path: Path) -> None:
    paths, _manifest = _write_fixture_manifest(tmp_path)

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

    paths, manifest = _write_fixture_manifest(tmp_path)

    text = manifest_path(paths).read_text(encoding=UTF_8_ENCODING)
    assert "created_at = 2026-05-14T12:00:00+00:00\n" in text
    assert "last_unlocked_at = 2026-05-14T13:30:00+00:00\n" in text

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


def test_write_refuses_an_invalid_manifest_and_writes_no_bytes(tmp_path: Path) -> None:
    """The write ingress validates, so an invalid instance never reaches disk.

    ``model_copy(update=...)`` skips validation, which is precisely how an
    invalid instance can exist in memory: several manifest writers mutate that
    way. ``idle_lock_minutes`` carries ``gt=0``, so setting it to ``0`` through
    ``model_copy`` produces a genuinely constraint-violating manifest without
    fabricating any persisted shape.

    Refusing at write time rather than on the next read matters on this format
    specifically: the bucket-scan path swallows manifest read failures, so a
    deferred refusal would not surface as an error — the profile would simply
    disappear from the operator's listing.
    """
    paths = provision_bucket_directory(tmp_path, "alpha")
    write_manifest(paths, _fixture_manifest())
    good_bytes = manifest_path(paths).read_bytes()

    invalid = _fixture_manifest().model_copy(update={"idle_lock_minutes": 0})
    with pytest.raises(StorageValidationError):
        write_manifest(paths, invalid)

    assert manifest_path(paths).read_bytes() == good_bytes, (
        "write_manifest refused the invalid manifest but had already replaced the file; "
        "the validation must happen before any byte is serialised or written"
    )


def test_the_write_validation_accepts_a_valid_manifest(tmp_path: Path) -> None:
    """The other half: the ingress is discriminating, not always-refusing.

    Without this the refusal above would pass just as happily if the ingress
    rejected everything, which would be a gate that cannot distinguish the
    property it guards.
    """
    paths = provision_bucket_directory(tmp_path, "alpha")
    valid = _fixture_manifest().model_copy(update={"idle_lock_minutes": 1})
    write_manifest(paths, valid)
    assert read_manifest(paths).idle_lock_minutes == 1


class TestManifestClaimsItsDirectory:
    """A manifest cannot name a bucket other than the directory it lives in.

    The directory name IS the bucket's identity: the storage route, the
    per-bucket keystore, and every secure-object row are addressed by it. The
    manifest's own ``bucket_id`` was validated only for shape, so a manifest
    claiming a different bucket read back cleanly and the scan surfaces
    published the CLAIMED id — a pointer resolved by directory carried the
    wrong identity while a lookup by the claimed id found nothing.
    """

    def _foreign_manifest(self) -> BucketManifest:
        return _fixture_manifest().model_copy(update={"bucket_id": "beta"})

    def test_write_refuses_a_manifest_naming_another_bucket(self, tmp_path: Path) -> None:
        paths = provision_bucket_directory(tmp_path, "alpha")

        with pytest.raises(StorageValidationError):
            write_manifest(paths, self._foreign_manifest())

    def test_write_refusal_names_both_identities(self, tmp_path: Path) -> None:
        """An operator must be able to see which two ids disagreed."""
        paths = provision_bucket_directory(tmp_path, "alpha")

        with pytest.raises(StorageValidationError) as excinfo:
            write_manifest(paths, self._foreign_manifest())

        assert "alpha" in str(excinfo.value)
        assert "beta" in str(excinfo.value)

    def test_read_refuses_a_manifest_naming_another_bucket(self, tmp_path: Path) -> None:
        """The refusal must hold for bytes already on disk, not only new writes."""
        paths = provision_bucket_directory(tmp_path, "alpha")
        write_manifest(paths, _fixture_manifest())
        raw = manifest_path(paths).read_text(encoding=UTF_8_ENCODING)
        manifest_path(paths).write_text(
            raw.replace('bucket_id = "alpha"', 'bucket_id = "beta"'),
            encoding=UTF_8_ENCODING,
        )

        with pytest.raises(StorageValidationError):
            read_manifest(paths)

    def test_matching_identity_still_round_trips(self, tmp_path: Path) -> None:
        """The guard must not refuse the legitimate write-then-read path."""
        paths, manifest = _write_fixture_manifest(tmp_path)

        assert read_manifest(paths) == manifest

    @pytest.mark.parametrize("bad", ["", "   ", "a" * 129])
    def test_manifest_bucket_id_carries_the_canonical_contract(self, bad: str) -> None:
        """The field is the canonical ``BucketId``, not a bare non-empty string.

        A blank-after-strip or overlength id is refused at construction, so it
        cannot reach disk and then fail only against the directory comparison.
        """
        fields = _fixture_manifest().model_dump(mode="python")

        with pytest.raises(ValidationError):
            BucketManifest.model_validate({**fields, "bucket_id": bad})

        assert BucketManifest.model_validate({**fields, "bucket_id": "a" * 128}).bucket_id == "a" * 128

    def test_whitespace_wrapped_id_is_canonicalized_not_stored_padded(self) -> None:
        """A padded declaration normalises to the spelling the directory uses."""
        rebuilt = BucketManifest.model_validate(
            {**_fixture_manifest().model_dump(mode="python"), "bucket_id": "  alpha  "},
        )

        assert rebuilt.bucket_id == "alpha"
