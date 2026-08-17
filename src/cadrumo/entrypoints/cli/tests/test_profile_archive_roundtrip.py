"""Real-CLI roundtrip for the sealed profile-archive backup surface.

The acceptance anchor for "the operator backs up their local catalogue to an
archive and restores it on a fresh machine without data loss": a real
invocation writes a sealed, AEAD-encrypted archive, ``inspect`` reads its
header without any key, and ``config profile restore`` republishes it into a
storage root that has never seen the profile, with the ledger intact.

Three contract facts this module encodes, each a deliberate decision rather
than an accident of the implementation:

**Restore takes the archive, and there is no ``archive import`` verb.** An
archive and a capsule directory differ only in how their material is READ;
both produce a ``ProfileCapsuleSource`` and reach one shared publication
authority. A second import verb would be a second door onto that authority,
and would leave an operator guessing which of two commands restores a backup.

**The archive carries no label.** A published capsule stores the operator's
chosen label in plaintext beside the ciphertext, so packing the directory
verbatim would leak it to anyone holding the file. The label is supplied by
the operator at restore instead, which is why the restores below name one.

**Restore does not switch the active profile.** Republishing a profile is not
a claim that the operator wants to work in it. An earlier version of this
surface switched automatically and asserted a notice for it; that behaviour is
gone deliberately, not lost.

No mocks. Real registration, real Argon2id, real AEAD sealing, real archive
bytes on disk, the real Click command tree.
"""

from __future__ import annotations

import tarfile
from pathlib import Path

import pytest
from click.testing import Result

from ....adapters.persistence.storage.bucket import ARCHIVE_SCHEMA_VERSION
from ....tests.cli_envelope import unwrap_schema_envelope
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage, isolated_profile_storage_root
from ....tests.user_profile import register_cli_profile
from .privacy_helpers import assert_public_profile_id_not_leaked

__all__ = ["isolated_profile_storage"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _invoke(args: list[str]) -> Result:
    return invoke_cached_cli(args)


def _test_passphrase() -> str:
    from ....core.config import load_settings

    return load_settings().cadrumo_dev_test_database_password.get_secret_value()


def _create_profile(name: str, *, tax_id: str) -> str:
    """Register the profile through the shared CLI registration door."""
    return register_cli_profile(
        label=name,
        facts={
            "identity.tax_id": tax_id,
            "activities.description": "design",
            "taxpayer_type.entity_type": "natural_person",
            "iva.regime": "GENERAL",
            "identity.name": "Archive",
            "identity.surnames": "Roundtrip",
        },
    )


def _archive_export(name: str, out: Path, *, json_format: bool = True) -> Result:
    args = ["config", "profile", "archive", "export", name, "--to", str(out)]
    if json_format:
        args = ["--format", "json", *args]
    return _invoke(args)


def _archive_inspect(source: Path, *, json_format: bool = True) -> Result:
    args = ["config", "profile", "archive", "inspect", "--file", str(source)]
    if json_format:
        args = ["--format", "json", *args]
    return _invoke(args)


def _restore_from(source: Path, *, label: str, json_format: bool = True) -> Result:
    """Restore an archive through the one restore door, which takes either shape."""
    args = ["config", "profile", "restore", label, "--file", str(source), "--secrets-stdin"]
    if json_format:
        args = ["--format", "json", *args]
    return invoke_cached_cli(args, input=f'{{"password": "{_test_passphrase()}"}}')


def _seed_transaction(csv_path: Path) -> None:
    csv_path.write_text(
        "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID\n"
        "2026-02-10,Client SL,Factura 002,605.00,EUR,txn-archive-001\n",
        encoding="utf-8",
    )
    r = _invoke(["app", "ledger", "import", "--file", str(csv_path), "--provider", "csv"])
    assert r.exit_code == 0, r.output


# ---------------------------------------------------------------------------
# Export/restore roundtrip (cross-host transport)
# ---------------------------------------------------------------------------


def test_archive_export_restore_roundtrip(tmp_path: Path) -> None:
    """A sealed archive restores full profile state in a fresh root.

    This is the transport a real disk-failure recovery uses, and it is the
    acceptance capability itself. The archive is portable because it carries
    the profile's own custody, so the profile password is what opens it on the
    new host; no recovery material is involved on either side.

    The ledger row is the payload that proves "without data loss" -- an
    archive that restored an empty but structurally valid profile would pass
    every other assertion here.
    """
    from ....core import resolve_active_bucket_id

    csv_path = tmp_path / "bank.csv"
    _create_profile("profile", tax_id="12345678Z")
    _seed_transaction(csv_path)

    source_bucket_id = resolve_active_bucket_id()
    assert source_bucket_id is not None

    archive_path = tmp_path / "profile-backup.cadrumo-bucket.tar.gz"
    r_export = _archive_export("profile", archive_path)
    assert r_export.exit_code == 0, r_export.output
    assert_public_profile_id_not_leaked(r_export.output, source_bucket_id)
    assert archive_path.is_file()

    from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
    from ....core.config import override_settings

    with override_settings(cadrumo_active_profile=source_bucket_id):
        original_transactions = tuple(TransactionCatalogueRepository(bucket_id=source_bucket_id).load())
    assert len(original_transactions) == 1

    # Restore into a fresh, disjoint storage root: proves the archive is a
    # true portable backup, not merely a same-host convenience copy.
    restore_root = tmp_path / "restore-root"
    with isolated_profile_storage_root(tmp_path=restore_root) as storage_root:
        r_restore = _restore_from(archive_path, label="Restored From Archive")
        assert r_restore.exit_code == 0, r_restore.output

        # Identity is preserved verbatim: bucket identity IS profile identity,
        # so a restore that minted a new id would have cloned the records
        # rather than recovered them, and every reference the operator holds
        # would dangle.
        assert (storage_root / "buckets" / source_bucket_id).is_dir()

        with override_settings(cadrumo_active_profile=source_bucket_id):
            restored_transactions = tuple(TransactionCatalogueRepository(bucket_id=source_bucket_id).load())

    assert restored_transactions == original_transactions


def test_archive_file_does_not_expose_identity_cleartext(tmp_path: Path) -> None:
    """A transfer archive exposes no profile identity outside the AEAD envelope.

    A gestor needs a bundle suitable for cross-host or email transfer. Only
    header metadata may be in clear; the NIF, name, surnames and the
    operator's chosen LABEL must all stay inside the encrypted member.

    The label is the one an obvious implementation gets wrong: it lives in
    plaintext inside a published capsule, so an archive built by packing the
    capsule directory verbatim would carry it in the clear.
    """
    _create_profile("profile-identity", tax_id="12345678Z")

    archive_path = tmp_path / "profile-identity-transfer.cadrumo-bucket.tar.gz"
    r_export = _archive_export("profile-identity", archive_path)
    assert r_export.exit_code == 0, r_export.output
    assert archive_path.is_file()

    member_payloads: dict[str, bytes] = {}
    with tarfile.open(archive_path, mode="r:gz") as archive:
        for member in archive.getmembers():
            if not member.isfile():
                continue
            extracted = archive.extractfile(member)
            assert extracted is not None
            member_payloads[member.name] = extracted.read()

    assert set(member_payloads) == {"header.json", "payload.envelope"}
    joined_members = b"\n".join(member_payloads.values())
    for forbidden in (b"12345678Z", b"Archive", b"Roundtrip", b"profile-identity"):
        assert forbidden not in joined_members

    assert b"identity.tax_id" not in member_payloads["header.json"]


# ---------------------------------------------------------------------------
# Inspect: read-only header preview
# ---------------------------------------------------------------------------


def test_archive_inspect_reads_header_without_decrypting(tmp_path: Path) -> None:
    """``inspect`` reports the header with no profile ever unlocked.

    It is a pure plaintext-header read and must stay reachable when an
    operator wants to check a backup file before deciding whether to restore
    it -- which is precisely the moment they may have no working profile.
    """
    _create_profile("profile3", tax_id="11111111H")

    archive_path = tmp_path / "profile3-backup.cadrumo-bucket.tar.gz"
    r_export = _archive_export("profile3", archive_path)
    assert r_export.exit_code == 0, r_export.output

    inspect_root = tmp_path / "inspect-root"
    with isolated_profile_storage_root(tmp_path=inspect_root):
        r_inspect = _archive_inspect(archive_path)
        assert r_inspect.exit_code == 0, r_inspect.output
        payload = unwrap_schema_envelope(r_inspect.output)
        assert payload["archive_schema_version"] == ARCHIVE_SCHEMA_VERSION
        assert isinstance(payload["created_at"], str)
        assert payload["created_at"]
        # Everything inspect prints is readable by anyone holding the file, so
        # the operator's chosen label must not be among it.
        assert "profile3" not in r_inspect.output


def test_archive_inspect_refuses_missing_file(tmp_path: Path) -> None:
    """``inspect`` refuses cleanly (no traceback) when the archive is absent."""
    missing = tmp_path / "does-not-exist.cadrumo-bucket.tar.gz"
    r = _archive_inspect(missing)
    assert r.exit_code != 0, r.output
    assert "Traceback" not in r.output


# ---------------------------------------------------------------------------
# Anti-tautology: a corrupted archive must refuse restore, not silently succeed
# ---------------------------------------------------------------------------


def test_archive_restore_refuses_corrupted_payload(tmp_path: Path) -> None:
    """Tampering with the sealed payload bytes refuses the restore.

    Flips one byte inside the AEAD-encrypted payload member. AEAD
    authentication must catch this at decryption; a passing restore here would
    mean the seal provides no tamper protection at all, and every other
    assertion in this module would be worthless.
    """
    _create_profile("profile4", tax_id="22222222J")

    archive_path = tmp_path / "profile4-backup.cadrumo-bucket.tar.gz"
    r_export = _archive_export("profile4", archive_path)
    assert r_export.exit_code == 0, r_export.output

    extract_dir = tmp_path / "extracted"
    extract_dir.mkdir()
    with tarfile.open(archive_path, mode="r:gz") as archive:
        archive.extractall(extract_dir, filter="data")

    payload_path = extract_dir / "payload.envelope"
    assert payload_path.is_file()
    raw = bytearray(payload_path.read_bytes())
    assert len(raw) > 16
    raw[-8] ^= 0xFF  # Flip a byte deep inside the AEAD ciphertext/tag region.
    payload_path.write_bytes(bytes(raw))

    tampered_path = tmp_path / "profile4-backup-tampered.cadrumo-bucket.tar.gz"
    with tarfile.open(tampered_path, mode="w:gz") as archive:
        for member_name in ("header.json", "payload.envelope"):
            member_path = extract_dir / member_name
            assert member_path.is_file()
            archive.add(member_path, arcname=member_name)

    restore_root = tmp_path / "restore-tampered-root"
    with isolated_profile_storage_root(tmp_path=restore_root):
        r_restore = _restore_from(tampered_path, label="Tampered")
        assert r_restore.exit_code != 0, r_restore.output
        assert "Traceback" not in r_restore.output


def test_archive_restore_refuses_an_identity_already_published(tmp_path: Path) -> None:
    """Restoring over a live profile of the same identity is refused.

    Bucket identity is profile identity, so republishing an archive into the
    root that already holds that identity would collide with a capsule the
    operator is actively using. The refusal must not leak the raw id.
    """
    from ....core import resolve_active_bucket_id

    _create_profile("profile5", tax_id="33333333P")
    source_bucket_id = resolve_active_bucket_id()
    assert source_bucket_id is not None

    archive_path = tmp_path / "profile5-backup.cadrumo-bucket.tar.gz"
    r_export = _archive_export("profile5", archive_path)
    assert r_export.exit_code == 0, r_export.output

    # Restore into the SAME storage root, where the identity already exists.
    r_restore = _restore_from(archive_path, label="Collision")
    assert r_restore.exit_code != 0, r_restore.output
    assert_public_profile_id_not_leaked(r_restore.output, source_bucket_id)
    assert "Traceback" not in r_restore.output
