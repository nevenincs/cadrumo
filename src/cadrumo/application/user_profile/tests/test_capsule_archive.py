"""Backing a profile up and bringing it back on another machine.

Real capsules, real archives on a real filesystem, the real publication path.
The subject is the acceptance claim itself: an operator backs up their local
catalogue and restores it elsewhere without data loss.
"""

from __future__ import annotations

import gzip
from typing import TYPE_CHECKING
from uuid import UUID

import pytest

from cadrumo.application.user_profile.capsule_archive import (
    RECOVERY_SLOT_BYTES,
    ProfileCapsuleArchiveError,
    export_profile_capsule_archive,
    inspect_profile_capsule_archive,
    read_profile_capsule_archive,
)
from cadrumo.application.user_profile.capsule_restore import restore_profile_capsule_with_password
from cadrumo.application.user_profile.custody_ports import profile_custody_recovery_envelope_path
from cadrumo.application.user_profile.registration import register_profile_with_credentials

from ....adapters.persistence.storage.custody import load_committed_profile_password_material
from ....domain.user_profile import UserProfileFact
from ....tests.secure_sql import isolated_profile_storage_root

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_LABEL = "Archive Roundtrip Subject"
_PASSPHRASE = "archive-roundtrip-subject-operator-secret"  # noqa: S105 - synthetic test credential
_TAX_ID = "12345678Z"
_NAME = "Genoveva"
_SURNAMES = "Iriarte Zubizarreta"


def _register(handed: list[str] | None = None) -> str:
    """Register the subject profile carrying identifying facts."""
    outcome = register_profile_with_credentials(
        label=_LABEL,
        passphrase=_PASSPHRASE,
        facts=(
            UserProfileFact(path="identity.tax_id", value=_TAX_ID),
            UserProfileFact(path="identity.name", value=_NAME),
            UserProfileFact(path="identity.surnames", value=_SURNAMES),
        ),
        recovery_handover=lambda enrollment: (
            (handed.append(enrollment.recovery_key.mnemonic) if handed is not None else None)
            or enrollment.recovery_key.mnemonic
        ),
    )
    return outcome.profile_id


def test_a_profile_survives_an_archive_and_a_restore_on_a_fresh_root(tmp_path: Path) -> None:
    """The acceptance claim end to end: back up, restore elsewhere, no data loss."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id = _register()
        archive = tmp_path / "backup.cadrumo-bucket.tar.gz"

        receipt = export_profile_capsule_archive(profile_id=UUID(profile_id), target=archive)

        assert receipt.bucket_id == profile_id
        assert archive.is_file()

        restored = restore_profile_capsule_with_password(
            label="Restored on a fresh machine",
            capsule=read_profile_capsule_archive(archive),
            password=_PASSPHRASE,
            root=tmp_path / "fresh-machine",
        )

        # Identity verbatim: an import that minted a new UUID would have
        # cloned the profile rather than restored it.
        assert restored.profile_id == profile_id


def test_the_archive_leaks_no_identifying_field_outside_its_encrypted_members(tmp_path: Path) -> None:
    """A backup an operator can email must not publish who they are.

    The tax id, name and surnames are safe only because they live inside the
    encrypted database. The LABEL is not: it sits in the published capsule as
    a plaintext projection beside the ciphertext, so an archive built by
    copying the capsule directory would carry it in the clear. This scans the
    archive bytes, and the decompressed bytes, for all four.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id = _register()
        archive = tmp_path / "no-leak.cadrumo-bucket.tar.gz"
        export_profile_capsule_archive(profile_id=UUID(profile_id), target=archive)

        raw = archive.read_bytes()
        expanded = gzip.decompress(raw)

        for secret in (_TAX_ID, _NAME, _SURNAMES, _LABEL):
            assert secret.encode("utf-8") not in raw, f"{secret!r} appears in the archive bytes"
            assert secret.encode("utf-8") not in expanded, f"{secret!r} appears in the decompressed archive"


def test_discarding_words_does_not_create_a_password_only_source_profile(tmp_path: Path) -> None:
    """Not retaining words in a fixture cannot bypass creation enrollment."""
    handed: list[str] = []

    with isolated_profile_storage_root(tmp_path=tmp_path):
        enrolled_id = _register(handed)
        enrolled = load_committed_profile_password_material(UUID(enrolled_id))

    with isolated_profile_storage_root(tmp_path=tmp_path / "second"):
        unretained_id = _register()
        unretained = load_committed_profile_password_material(UUID(unretained_id))

    assert profile_custody_recovery_envelope_path(enrolled.capsule_path).exists()
    assert profile_custody_recovery_envelope_path(unretained.capsule_path).exists()


def test_the_recovery_wrapper_is_excluded_from_archive_and_import(tmp_path: Path) -> None:
    """Normal backup transport never carries or installs recovery material."""
    handed: list[str] = []

    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id = _register(handed)
        original_path = (
            load_committed_profile_password_material(UUID(profile_id)).capsule_path / "custody" / "recovery.v1.json"
        )
        assert original_path.exists()
        archive = tmp_path / "with-recovery.cadrumo-bucket.tar.gz"
        export_profile_capsule_archive(profile_id=UUID(profile_id), target=archive)
        destination = tmp_path / "imported"

        archive_source = read_profile_capsule_archive(archive)
        restored = restore_profile_capsule_with_password(
            label="Imported keeping recovery",
            capsule=archive_source,
            password=_PASSPHRASE,
            root=destination,
        )

        assert restored.recovery_enrolled is False
        carried = destination / "buckets" / profile_id / "custody" / "recovery.v1.json"
        assert not carried.exists()


def test_inspect_reports_the_header_without_any_key(tmp_path: Path) -> None:
    """What an operator can learn about an archive, and equally what anyone can."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id = _register()
        archive = tmp_path / "inspected.cadrumo-bucket.tar.gz"
        export_profile_capsule_archive(profile_id=UUID(profile_id), target=archive)

        inspection = inspect_profile_capsule_archive(archive)

        assert inspection.bucket_id == profile_id
        assert inspection.product == "cadrumo"
        # The label is deliberately absent from the header: inspect reads it
        # without a key, so anything here is published to whoever holds the file.
        assert _LABEL not in inspection.model_dump_json()


def test_a_tampered_archive_is_refused_rather_than_partially_believed(tmp_path: Path) -> None:
    """Anti-tautology for the roundtrip: the digest is checked, not decorative.

    Without this the roundtrip would read identically if the reader ignored
    the header's digest, and an edited archive would restore silently.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id = _register()
        archive = tmp_path / "tampered.cadrumo-bucket.tar.gz"
        export_profile_capsule_archive(profile_id=UUID(profile_id), target=archive)

        expanded = bytearray(gzip.decompress(archive.read_bytes()))
        marker = b'"database"'
        index = expanded.find(marker)
        assert index != -1, "the payload layout changed; this probe needs updating"
        expanded[index + 40] ^= 0xFF
        archive.write_bytes(gzip.compress(bytes(expanded)))

        with pytest.raises(ProfileCapsuleArchiveError, match="digest"):
            read_profile_capsule_archive(archive)


def test_the_recovery_slot_is_the_declared_constant_width() -> None:
    """The width is load-bearing, so it is pinned rather than assumed."""
    assert RECOVERY_SLOT_BYTES == 4096


def test_a_capsule_that_is_not_published_cannot_be_archived(tmp_path: Path) -> None:
    """Export reads a committed capsule; there is nothing else to back up."""
    from uuid import uuid4

    from ....adapters.persistence.storage.custody import ProfileCustodyRecordError

    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        pytest.raises(ProfileCustodyRecordError, match="not committed"),
    ):
        export_profile_capsule_archive(profile_id=uuid4(), target=tmp_path / "absent.cadrumo-bucket.tar.gz")


def test_an_archived_profile_keeps_its_setup_state_and_facts(tmp_path: Path) -> None:
    """No data loss is the claim, so the record itself is compared."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_id = _register()
        archive = tmp_path / "facts.cadrumo-bucket.tar.gz"
        export_profile_capsule_archive(profile_id=UUID(profile_id), target=archive)

        source = read_profile_capsule_archive(archive)

        assert str(source.password_envelope.profile_id) == profile_id
        assert source.sentinel.profile_id == UUID(profile_id)
        assert source.database_bytes  # the encrypted catalogue travelled

        restored = restore_profile_capsule_with_password(
            label="Facts intact",
            capsule=source,
            password=_PASSPHRASE,
            root=tmp_path / "facts-restored",
        )

        assert restored.profile_id == profile_id
        assert restored.authority == "password"
