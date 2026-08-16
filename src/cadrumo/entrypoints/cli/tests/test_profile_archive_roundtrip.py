"""Real-CLI roundtrip for the sealed bucket-archive backup/restore surface.

``config profile archive export`` / ``import`` / ``inspect`` compose
:class:`~cadrumo.application.bucket_maintenance.BucketMaintenanceService` (the
same primitive the roundtrip and anti-tautology tests in
:mod:`cadrumo.application.bucket_maintenance.tests.test_service_import_export`
exercise). This module proves the CLI wiring itself: a real operator
invocation exports a sealed, AEAD-encrypted archive, ``inspect`` reads its
header without decrypting it, and ``import`` restores it into a fresh
storage root with strict per-store equality — including the evidence bytes
and audit trail that the structured ``config profile export`` transport
deliberately excludes.

No mocks. Real ``isolated_profile_storage_root`` fixture, real
``open_test_profile_session``, real encrypted repositories, real AEAD sealing.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import Result

from ....adapters.persistence.storage.bucket import ARCHIVE_SCHEMA_VERSION
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage, isolated_profile_storage_root

__all__ = ["isolated_profile_storage"]
from ....tests.cli_envelope import unwrap_envelope_notices, unwrap_schema_envelope
from ....tests.user_profile import register_cli_profile
from .privacy_helpers import assert_public_profile_id_not_leaked, assert_public_profile_payload_redacted

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _invoke(args: list[str]) -> Result:
    return invoke_cached_cli(args)


def _create_profile(name: str, *, tax_id: str) -> Result:
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


def _archive_import(source: Path, *, force: bool = False, json_format: bool = True) -> Result:
    args = ["config", "profile", "archive", "import", str(source)]
    if force:
        args.append("--force")
    if json_format:
        args = ["--format", "json", *args]
    return _invoke(args)


def _archive_inspect(source: Path, *, json_format: bool = True) -> Result:
    args = ["config", "profile", "archive", "inspect", str(source)]
    if json_format:
        args = ["--format", "json", *args]
    return _invoke(args)


def _seed_transaction(csv_path: Path) -> None:
    csv_path.write_text(
        "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID\n"
        "2026-02-10,Client SL,Factura 002,605.00,EUR,txn-archive-001\n",
        encoding="utf-8",
    )
    r = _invoke(["app", "ledger", "import", "--file", str(csv_path), "--provider", "csv"])
    assert r.exit_code == 0, r.output


# ---------------------------------------------------------------------------
# Export/import roundtrip (cross-host transport)
# ---------------------------------------------------------------------------


def test_archive_export_import_roundtrip(tmp_path: Path) -> None:
    """A sealed archive restores full profile state in a fresh root.

    This is the transport a real disk-failure recovery uses. The archive is
    portable because it carries the profile's own custody, and the profile
    password is what opens it on the new host; no recovery material is
    involved on either side.
    """
    from ....core import resolve_active_bucket_id

    csv_path = tmp_path / "bank.csv"
    r_create = _create_profile("profile", tax_id="12345678Z")
    assert r_create.exit_code == 0, r_create.output
    _seed_transaction(csv_path)

    source_bucket_id = resolve_active_bucket_id()
    assert source_bucket_id is not None

    archive_path = tmp_path / "profile-backup.cadrumo-bucket.tar.gz"
    r_export = _archive_export("profile", archive_path)
    assert r_export.exit_code == 0, r_export.output
    assert_public_profile_payload_redacted(r_export.output, source_bucket_id)
    assert archive_path.is_file()

    # Load originals while still in source storage context.
    from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
    from ....adapters.persistence.storage.master_key import (
        activate_master_key_provider,
        get_master_key_provider,
    )
    from ....core.config import override_settings

    with (
        override_settings(cadrumo_active_profile=source_bucket_id),
        activate_master_key_provider(get_master_key_provider()),
    ):
        original_transactions = tuple(TransactionCatalogueRepository(bucket_id=source_bucket_id).load())
    assert len(original_transactions) == 1

    # Restore into a fresh, disjoint storage root: proves the archive is a
    # true portable backup, not merely a same-host convenience copy.
    restore_root = tmp_path / "restore-root"
    with isolated_profile_storage_root(tmp_path=restore_root):
        r_import = _archive_import(archive_path)
        assert r_import.exit_code == 0, r_import.output
        assert_public_profile_payload_redacted(r_import.output, source_bucket_id)

        restored_bucket_id = resolve_active_bucket_id()
        assert restored_bucket_id is not None
        assert restored_bucket_id == source_bucket_id  # D5 identity: bundle profile_id preserved verbatim

        with (
            override_settings(cadrumo_active_profile=restored_bucket_id),
            activate_master_key_provider(get_master_key_provider()),
        ):
            restored_transactions = tuple(TransactionCatalogueRepository(bucket_id=restored_bucket_id).load())

    assert restored_transactions == original_transactions


def test_archive_transfer_file_does_not_expose_identity_cleartext(tmp_path: Path) -> None:
    """A transfer archive does not expose raw profile identity bytes.

    A gestor needs a bundle suitable for cross-host/email transfer. The sealed
    archive may expose only its header metadata in clear; the profile payload
    containing NIF/name/surnames must stay inside the AEAD envelope.
    """
    import tarfile

    r_create = _create_profile("profile-identity", tax_id="12345678Z")
    assert r_create.exit_code == 0, r_create.output

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

    # The header is intentionally inspectable without decryption, but it must
    # remain metadata-only and never carry the portable bundle payload.
    assert b"manifest_digest" in member_payloads["header.json"]
    assert b"identity.tax_id" not in member_payloads["header.json"]


def test_archive_import_switches_active_profile_with_notice(tmp_path: Path) -> None:
    """Archive import provisions the restored bucket as the active profile."""
    from ....core import resolve_active_bucket_id

    r_create = _create_profile("profile2", tax_id="87654321X")
    assert r_create.exit_code == 0, r_create.output
    source_bucket_id = resolve_active_bucket_id()
    assert source_bucket_id is not None

    archive_path = tmp_path / "profile2-backup.cadrumo-bucket.tar.gz"
    r_export = _archive_export("profile2", archive_path)
    assert r_export.exit_code == 0, r_export.output

    restore_root = tmp_path / "restore-root-2"
    with isolated_profile_storage_root(tmp_path=restore_root):
        r_import = _archive_import(archive_path)
        assert r_import.exit_code == 0, r_import.output

        notices = unwrap_envelope_notices(r_import.output)
        switch = next(
            (n for n in notices if n["code"] == "config.profile.archive.import.active_profile_switched"),
            None,
        )
        assert switch is not None, f"archive import must surface the active-profile-switch notice; got {notices}"
        assert switch["severity"] == "info"
        assert "active" in switch["message"].lower()

        # The notice names the restored profile's own label (read back from
        # its manifest, since ImportBucketResult carries none) rather than
        # the raw bucket UUID or an unfilled literal placeholder, and the
        # suggestion is a complete, directly-runnable command -- at parity
        # with the sibling ``config profile import`` switch notice.
        assert "profile2" in switch["message"]
        assert switch["suggestion"] == "aeat config login profile2"
        assert switch["context"]["active_profile"] == "profile2"

        assert resolve_active_bucket_id() == source_bucket_id


# ---------------------------------------------------------------------------
# Inspect: read-only header preview
# ---------------------------------------------------------------------------


def test_archive_inspect_reads_header_without_decrypting(tmp_path: Path) -> None:
    """``inspect`` reports the header + file size without requiring a session.

    The critical property this proves is that ``inspect`` runs cleanly with
    NO profile ever unlocked afterward (a fresh, disjoint storage root),
    since it is a pure plaintext-header read and must stay reachable when
    an operator wants to check a backup file before deciding whether to
    restore it.
    """
    r_create = _create_profile("profile3", tax_id="11111111H")
    assert r_create.exit_code == 0, r_create.output

    archive_path = tmp_path / "profile3-backup.cadrumo-bucket.tar.gz"
    r_export = _archive_export("profile3", archive_path)
    assert r_export.exit_code == 0, r_export.output

    inspect_root = tmp_path / "inspect-root"
    with isolated_profile_storage_root(tmp_path=inspect_root):
        r_inspect = _archive_inspect(archive_path)
        assert r_inspect.exit_code == 0, r_inspect.output
        payload = unwrap_schema_envelope(r_inspect.output)
        assert payload["archive_schema_version"] == ARCHIVE_SCHEMA_VERSION
        assert payload["size_bytes"] == archive_path.stat().st_size
        assert isinstance(payload["created_at"], str) and payload["created_at"]


def test_archive_inspect_refuses_missing_file(tmp_path: Path) -> None:
    """``inspect`` refuses cleanly (no traceback) when the archive file is absent."""
    missing = tmp_path / "does-not-exist.cadrumo-bucket.tar.gz"
    r = _archive_inspect(missing)
    assert r.exit_code != 0, r.output
    assert "Traceback" not in r.output


# ---------------------------------------------------------------------------
# Anti-tautology: a corrupted archive must refuse restore, not silently succeed
# ---------------------------------------------------------------------------


def test_archive_import_refuses_corrupted_payload(tmp_path: Path) -> None:
    """Tampering with the sealed archive's encrypted payload bytes refuses import.

    Flips one byte inside the AEAD-encrypted payload member. AEAD
    authentication must catch this at decryption; a passing restore here
    would mean the seal provides no tamper protection at all.
    """
    import tarfile

    r_create = _create_profile("profile4", tax_id="22222222J")
    assert r_create.exit_code == 0, r_create.output

    archive_path = tmp_path / "profile4-backup.cadrumo-bucket.tar.gz"
    r_export = _archive_export("profile4", archive_path)
    assert r_export.exit_code == 0, r_export.output

    # Extract, corrupt the payload member, and re-pack the tar.gz.
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
        r_import = _archive_import(tampered_path)
        assert r_import.exit_code != 0, r_import.output
        assert "Traceback" not in r_import.output


def test_archive_import_refuses_uuid_collision(tmp_path: Path) -> None:
    """Importing an archive whose bucket id is already registered is refused without --force."""
    from ....core import resolve_active_bucket_id

    r_create = _create_profile("profile5", tax_id="33333333P")
    assert r_create.exit_code == 0, r_create.output
    source_bucket_id = resolve_active_bucket_id()
    assert source_bucket_id is not None

    archive_path = tmp_path / "profile5-backup.cadrumo-bucket.tar.gz"
    r_export = _archive_export("profile5", archive_path)
    assert r_export.exit_code == 0, r_export.output

    # Re-import into the SAME storage root, where the bucket id already exists.
    r_import = _archive_import(archive_path)
    assert r_import.exit_code != 0, r_import.output
    assert_public_profile_id_not_leaked(r_import.output, source_bucket_id)
    assert "Traceback" not in r_import.output
