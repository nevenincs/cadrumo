"""The profile acts, served by the real runtime over a real storage root, do the command line's work."""

from __future__ import annotations

import json
import logging
import shutil
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import SecretBytes

from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from cadrumo.adapters.local_runtime.installation_client import installation_passphrase_document
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.storage.bucket.sealed_archive_writer import CADRUMO_BUCKET_BUNDLE_SUFFIX
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.installation_requests import (
    InstallationAct,
    RuntimeArchiveImportPrepareReply,
    RuntimeArchiveImportPrepareRequest,
    RuntimeArchiveImportReply,
    RuntimeArchiveImportRequest,
    RuntimeArchiveInspectReply,
    RuntimeArchiveInspectRequest,
    RuntimeInstallationCompleted,
    RuntimeInstallationRefused,
    RuntimeProfileListReply,
    RuntimeProfileListRequest,
    RuntimeRecoveryEnrollReply,
    RuntimeRecoveryEnrollRequest,
)
from cadrumo.application.user_profile.authentication import ProfileAuthenticationRefusedError
from cadrumo.application.user_profile.capsule_archive import (
    PROFILE_CAPSULE_ARCHIVE_SUFFIX,
    export_profile_capsule_archive,
    inspect_profile_capsule_archive,
    read_restorable_profile_capsule,
)
from cadrumo.application.user_profile.custody_ports import (
    ProfileCustodyRecordIntegrityError,
    load_profile_custody_password_material,
    unlock_profile_custody_password,
)
from cadrumo.application.user_profile.recovery_custody import (
    ProfileRecoveryError,
    profile_recovery_status,
    reset_profile_passphrase_with_recovery,
    revoke_profile_recovery,
)
from cadrumo.core.config import override_settings
from cadrumo.core.errors.error_codes import get_registered_error_code
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.entrypoints.cli.tests.command_line_rendering import (
    Printed,
    assert_prints,
    command_error,
    command_printed,
    command_result,
    json_document,
)
from cadrumo.entrypoints.cli.tests.scripted_registration_channels import scripted_registration_descriptors

from .installation_profile_support import (
    PROFILE_INPUT,
    PROFILE_LABEL,
    ServedInstallation,
    installation_client,
    served_installation,
    serving_profile_acts,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires real Windows protected pipes"),
    pytest.mark.usefixtures("authority_operation"),
]

_CLI = OperationFrontendProjection.CLI
_COORDINATES = {"request_id", "runtime_boot_id", "connection_id", "kind"}
_RESTORED_LABEL = "Restored Subject"
_REPLACEMENT_INPUT = "a-replacement-passphrase-after-reset"


def _archive_of(installation: ServedInstallation, directory: Path) -> Path:
    target = directory / f"backup{PROFILE_CAPSULE_ARCHIVE_SUFFIX}"
    export_profile_capsule_archive(profile_id=installation.profile_id, target=target, root=installation.root)
    return target


def _capsule_directory_of(installation: ServedInstallation, directory: Path) -> Path:
    """Copy the committed capsule out of the storage root, as an operator copies it out of a backup."""
    committed = load_profile_custody_password_material(installation.profile_id, root=installation.root).capsule_path
    return Path(shutil.copytree(committed, directory / "copied-capsule"))


def _secret(passphrase: str = PROFILE_INPUT) -> bytearray:
    return installation_passphrase_document(bytearray(passphrase, "utf-8"))


def _prepare_request(source: Path, frontend: OperationFrontendProjection = _CLI) -> RuntimeArchiveImportPrepareRequest:
    return RuntimeArchiveImportPrepareRequest(
        request_id=uuid4(), frontend=frontend, label=_RESTORED_LABEL, path=str(source)
    )


def _import_request(
    source: Path, digest: str, frontend: OperationFrontendProjection = _CLI
) -> RuntimeArchiveImportRequest:
    return RuntimeArchiveImportRequest(
        request_id=uuid4(), frontend=frontend, label=_RESTORED_LABEL, path=str(source), source_digest=digest
    )


def _document(reply: RuntimeInstallationCompleted) -> dict[str, object]:
    """Return what a frontend shows of a reply: everything but the coordinates that correlate it."""
    return json_document(reply, exclude=_COORDINATES)


def _profiles_listed(endpoint: WindowsRuntimeEndpoint) -> tuple[str, ...]:
    with installation_client(endpoint) as client:
        listed = client.perform(RuntimeProfileListRequest(request_id=uuid4(), frontend=_CLI), RuntimeProfileListReply)
    assert isinstance(listed, RuntimeProfileListReply)
    return tuple(row.bucket_id for row in listed.profiles)


def _enable_recovery(*, reveal_identifiers: bool) -> dict[str, object]:
    """Run ``config profile recovery enable`` headlessly and return the result it printed."""
    with scripted_registration_descriptors() as (handoff, verification):
        return command_result(
            "config",
            "profile",
            "recovery",
            "enable",
            "--secrets-stdin",
            "--recovery-handoff-fd",
            str(handoff),
            "--recovery-verification-fd",
            str(verification),
            stdin=json.dumps({"passphrase": PROFILE_INPUT}),
            reveal_identifiers=reveal_identifiers,
        )


def _import_with_the_command(source: Path, root: Path, *, reveal_identifiers: bool) -> dict[str, object]:
    """Run ``config profile archive import`` against a storage root of its own and return what it printed."""
    with override_settings(cadrumo_local_storage_root=root):
        try:
            return command_result(
                "config",
                "profile",
                "archive",
                "import",
                _RESTORED_LABEL,
                "--file",
                str(source),
                "--secrets-stdin",
                stdin=json.dumps({"passphrase": PROFILE_INPUT}),
                reveal_identifiers=reveal_identifiers,
            )
        finally:
            close_active_bucket_session()


def test_the_archive_suffix_is_the_one_the_sealed_archive_writer_enforces() -> None:
    assert PROFILE_CAPSULE_ARCHIVE_SUFFIX == CADRUMO_BUCKET_BUNDLE_SUFFIX


def test_the_listing_act_answers_every_frontend_with_what_the_command_prints(tmp_path: Path) -> None:
    answers: dict[OperationFrontendProjection, dict[str, object]] = {}

    with served_installation(tmp_path) as installation:
        printed = command_printed("config", "profile", "list")
        for frontend in (OperationFrontendProjection.CLI, OperationFrontendProjection.TUI):
            with installation_client(installation.endpoint) as client:
                reply = client.perform(
                    RuntimeProfileListRequest(request_id=uuid4(), frontend=frontend), RuntimeProfileListReply
                )
            assert isinstance(reply, RuntimeProfileListReply)
            answers[frontend] = reply.model_dump(mode="json", exclude={"request_id", "connection_id"})
            assert_prints(_document(reply), printed)
            assert reply.active_profile == PROFILE_LABEL
            # The reply carries the real identifier a caller names the profile by.
            assert [(row.name, row.bucket_id, row.active) for row in reply.profiles] == [
                (PROFILE_LABEL, str(installation.profile_id), True)
            ]

    assert str(installation.profile_id) not in json.dumps(printed.default)
    assert len(answers) == 2
    assert answers[OperationFrontendProjection.TUI] == answers[_CLI]


def test_the_inspect_act_reports_the_header_the_command_prints_and_refuses_what_is_no_archive(
    tmp_path: Path,
) -> None:
    missing = tmp_path / f"missing{PROFILE_CAPSULE_ARCHIVE_SUFFIX}"

    with served_installation(tmp_path) as installation, installation_client(installation.endpoint) as client:
        archive = _archive_of(installation, tmp_path)
        printed = command_printed("config", "profile", "archive", "inspect", "--file", str(archive))
        header = inspect_profile_capsule_archive(archive)
        reply = client.perform(
            RuntimeArchiveInspectRequest(request_id=uuid4(), frontend=_CLI, path=str(archive)),
            RuntimeArchiveInspectReply,
        )
        absent = client.perform(
            RuntimeArchiveInspectRequest(request_id=uuid4(), frontend=_CLI, path=str(missing)),
            RuntimeArchiveInspectReply,
        )

    assert isinstance(reply, RuntimeArchiveInspectReply)
    assert_prints(_document(reply), printed)
    assert (reply.product, reply.archive_schema_version, reply.created_at, reply.manifest_digest) == (
        header.product,
        header.archive_schema_version,
        header.created_at,
        header.manifest_digest,
    )
    assert reply.bucket_id == str(installation.profile_id)
    assert isinstance(absent, RuntimeInstallationRefused)
    assert absent.act is InstallationAct.ARCHIVE_INSPECT


@pytest.mark.parametrize("shape", ["archive", "directory"])
def test_an_import_republishes_the_prepared_source_and_answers_what_the_command_prints(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, shape: str
) -> None:
    served_root = tmp_path / "fresh-machine"
    served_root.mkdir()
    caplog.set_level(logging.DEBUG)

    with served_installation(tmp_path) as installation:
        source = (
            _archive_of(installation, tmp_path) if shape == "archive" else _capsule_directory_of(installation, tmp_path)
        )
        read_digest = read_restorable_profile_capsule(source).digest
        with serving_profile_acts(served_root) as endpoint, installation_client(endpoint) as client:
            prepared = client.perform(_prepare_request(source), RuntimeArchiveImportPrepareReply)
            assert isinstance(prepared, RuntimeArchiveImportPrepareReply)
            secret = _secret()
            imported = client.perform(
                _import_request(source, prepared.source_digest), RuntimeArchiveImportReply, secret=secret
            )
            published = _profiles_listed(endpoint)
            # The republished capsule opens under the passphrase that was sent.
            restored = load_profile_custody_password_material(installation.profile_id, root=served_root)
            unlock_profile_custody_password(restored, password=PROFILE_INPUT)
        # A source is imported once into a root, so each run of the command gets a fresh root of its own.
        printed = Printed(
            default=_import_with_the_command(source, tmp_path / "fresh-command", reveal_identifiers=False),
            revealed=_import_with_the_command(source, tmp_path / "fresh-revealed", reveal_identifiers=True),
        )

    assert prepared.source_digest == read_digest
    assert isinstance(imported, RuntimeArchiveImportReply)
    assert_prints(_document(imported), printed)
    assert imported.profile_id == str(installation.profile_id)
    assert (imported.label, imported.authority, imported.recovery_enrolled) == (_RESTORED_LABEL, "password", False)
    assert published == (str(installation.profile_id),)
    assert not any(secret)
    assert PROFILE_INPUT not in imported.model_dump_json()
    assert PROFILE_INPUT not in caplog.text
    assert all(PROFILE_INPUT not in repr(record.__dict__) for record in caplog.records)


def test_an_import_under_a_wrong_passphrase_is_refused_and_publishes_nothing(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    served_root = tmp_path / "fresh-machine"
    served_root.mkdir()
    wrong = "not-the-passphrase-of-this-capsule"
    caplog.set_level(logging.DEBUG)

    with served_installation(tmp_path) as installation:
        archive = _archive_of(installation, tmp_path)
        with serving_profile_acts(served_root) as endpoint, installation_client(endpoint) as client:
            prepared = client.perform(_prepare_request(archive), RuntimeArchiveImportPrepareReply)
            assert isinstance(prepared, RuntimeArchiveImportPrepareReply)
            refused = client.perform(
                _import_request(archive, prepared.source_digest, OperationFrontendProjection.TUI),
                RuntimeArchiveImportReply,
                secret=_secret(wrong),
            )
            published = _profiles_listed(endpoint)

    assert isinstance(refused, RuntimeInstallationRefused)
    assert refused.act is InstallationAct.ARCHIVE_IMPORT
    assert refused.detail.error_code == get_registered_error_code(ProfileAuthenticationRefusedError).code
    assert published == ()
    assert wrong not in refused.model_dump_json()
    assert wrong not in caplog.text


def test_a_source_changed_after_it_was_prepared_is_refused_before_the_passphrase_is_asked_for(
    tmp_path: Path,
) -> None:
    served_root = tmp_path / "fresh-machine"
    served_root.mkdir()

    with served_installation(tmp_path) as installation:
        source = _capsule_directory_of(installation, tmp_path)
        database = read_restorable_profile_capsule(source).source.database_bytes
        member = next(path for path in source.rglob("*") if path.is_file() and path.read_bytes() == database)
        with serving_profile_acts(served_root) as endpoint, installation_client(endpoint) as client:
            prepared = client.perform(_prepare_request(source), RuntimeArchiveImportPrepareReply)
            assert isinstance(prepared, RuntimeArchiveImportPrepareReply)
            member.write_bytes(database + b"\x00")
            secret = _secret()
            with pytest.raises(RuntimeFrontendRefusedError) as changed:
                client.perform(
                    _import_request(source, prepared.source_digest, OperationFrontendProjection.TUI),
                    RuntimeArchiveImportReply,
                    secret=secret,
                )
            published = _profiles_listed(endpoint)

    assert changed.value.reason == "conflict"
    assert published == ()
    assert not any(secret)


def test_an_unreadable_source_is_refused_when_it_is_prepared(tmp_path: Path) -> None:
    tampered = tmp_path / f"tampered{PROFILE_CAPSULE_ARCHIVE_SUFFIX}"

    with served_installation(tmp_path) as installation, installation_client(installation.endpoint) as client:
        archive = _archive_of(installation, tmp_path)
        tampered.write_bytes(archive.read_bytes()[:-64])
        refused = client.perform(_prepare_request(tampered), RuntimeArchiveImportPrepareReply)

    assert isinstance(refused, RuntimeInstallationRefused)
    assert refused.act is InstallationAct.ARCHIVE_IMPORT_PREPARE


def test_enrolment_hands_out_a_code_that_resets_the_passphrase_and_answers_what_the_command_prints(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    held: list[str] = []
    caplog.set_level(logging.DEBUG)

    def hold(delivered: bytearray) -> SecretBytes:
        """Keep the code and type it back as a person does, in another letter case."""
        held.append(delivered.decode("utf-8"))
        return SecretBytes(held[-1].lower().encode("utf-8"))

    with served_installation(tmp_path) as installation, installation_client(installation.endpoint) as client:
        profile, root = installation.profile_id, installation.root
        # Each run of the command enrols the profile; the enrolment is removed so the next run, and then
        # the act, is asked for the same work on the same storage.
        default = _enable_recovery(reveal_identifiers=False)
        revoke_profile_recovery(profile_id=profile, current_passphrase=PROFILE_INPUT, root=root)
        revealed = _enable_recovery(reveal_identifiers=True)
        revoke_profile_recovery(profile_id=profile, current_passphrase=PROFILE_INPUT, root=root)
        secret = _secret()
        # No profile is named: the act enrols the selected one, as the command does.
        reply = client.perform(
            RuntimeRecoveryEnrollRequest(request_id=uuid4(), frontend=OperationFrontendProjection.TUI),
            RuntimeRecoveryEnrollReply,
            secret=secret,
            hold_secret=hold,
        )
        enrolled = profile_recovery_status(profile_id=profile, root=root).enrolled
        again = client.perform(
            RuntimeRecoveryEnrollRequest(request_id=uuid4(), frontend=_CLI, profile_id=profile),
            RuntimeRecoveryEnrollReply,
            secret=_secret(),
            hold_secret=hold,
        )
        with bundled_indexed_authority().operation() as operation:
            reset = reset_profile_passphrase_with_recovery(
                profile_id=profile,
                recovery_code=held[0],
                new_passphrase=_REPLACEMENT_INPUT,
                new_passphrase_confirmation=_REPLACEMENT_INPUT,
                root=root,
                profile_decode_context=operation.profile_decode_context(),
            )
        material = load_profile_custody_password_material(profile, root=root)
        unlock_profile_custody_password(material, password=_REPLACEMENT_INPUT)

    assert isinstance(reply, RuntimeRecoveryEnrollReply)
    assert_prints(_document(reply), Printed(default=default, revealed=revealed))
    assert (reply.profile_id, reply.enrolled, reply.changed) == (str(profile), True, True)
    assert enrolled
    assert isinstance(again, RuntimeInstallationRefused)
    assert again.detail.error_code == get_registered_error_code(ProfileRecoveryError).code
    assert again.detail.message_key == "application.user_profile.errors.recovery_already_enrolled"
    assert len(held) == 1
    assert reset.recovery_enrollment_retained and reset.dek_epoch_preserved
    assert not any(secret)
    for private in (PROFILE_INPUT, held[0], held[0].lower()):
        assert private not in reply.model_dump_json()
        assert private not in caplog.text
        assert all(private not in repr(record.__dict__) for record in caplog.records)


@pytest.mark.parametrize("read_back", ["another-code-entirely", "éè is no recovery code"])
def test_enrolment_installs_nothing_when_the_code_read_back_is_not_the_one_handed_out(
    tmp_path: Path, read_back: str
) -> None:
    with served_installation(tmp_path) as installation, installation_client(installation.endpoint) as client:
        refused = client.perform(
            RuntimeRecoveryEnrollRequest(request_id=uuid4(), frontend=_CLI, profile_id=installation.profile_id),
            RuntimeRecoveryEnrollReply,
            secret=_secret(),
            hold_secret=lambda _delivered: SecretBytes(read_back.encode("utf-8")),
        )
        enrolled = profile_recovery_status(profile_id=installation.profile_id, root=installation.root).enrolled

    assert isinstance(refused, RuntimeInstallationRefused)
    assert refused.detail.message_key == "application.user_profile.errors.recovery_possession_mismatch"
    assert not enrolled


def test_a_store_whose_listing_cannot_be_trusted_is_refused_and_never_answered_as_an_empty_one(
    tmp_path: Path,
) -> None:
    with served_installation(tmp_path) as installation, installation_client(installation.endpoint) as client:
        next(installation.root.rglob("profile-label.v1.json")).write_bytes(b"{")
        printed = command_error("config", "profile", "list")
        refused = client.perform(RuntimeProfileListRequest(request_id=uuid4(), frontend=_CLI), RuntimeProfileListReply)

    assert isinstance(refused, RuntimeInstallationRefused)
    assert refused.act is InstallationAct.PROFILE_LIST
    assert refused.detail.error_code == get_registered_error_code(ProfileCustodyRecordIntegrityError).code
    assert refused.detail.error_code == printed["code"]
