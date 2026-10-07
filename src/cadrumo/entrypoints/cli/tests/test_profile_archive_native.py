"""Native-worker acceptance for exact-profile archive and mirror CLI routes."""

from __future__ import annotations

import json
import sys
import tarfile
from pathlib import Path

import pytest
from click.testing import Result

from ....adapters.outbound.google.records import DriveConfig
from ....adapters.outbound.google.tests.session_records import save_drive_config
from ....adapters.persistence.storage.bucket.export_archive_header import ARCHIVE_SCHEMA_VERSION
from ....adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
from ....adapters.persistence.storage.secure_object_namespaces import GOOGLE_DRIVE_CONFIG_NAMESPACE
from ....application.user_profile.capsule_archive import inspect_profile_capsule_archive
from ....application.user_profile.login_session import resolve_login_target
from ....tests.cli_envelope import require_error_document, unwrap_cli_result, unwrap_envelope_notices
from ..command_schema import command_schema_type
from .cli_runner import invoke_cached_cli
from .runtime_profile_cli_fixture import NativeCliProfileFixture, native_cli_profile_scope

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]


def _invoke(profile: NativeCliProfileFixture, *command: str, json_output: bool = True) -> Result:
    assert profile.label is not None
    from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session

    close_active_bucket_session()
    result = invoke_cached_cli(
        (
            "--format",
            "json" if json_output else "text",
            "--profile",
            profile.label,
            "--profile-secrets-stdin",
            *command,
        ),
        input=json.dumps({"profile_passphrase": profile.passphrase}),
    )
    assert profile.passphrase not in result.output
    return result


def test_native_profile_archive_export_keeps_identity_sealed_and_refusals_local(tmp_path: Path) -> None:
    """The registered export writes the exact bound profile and preserves target refusals."""
    from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session

    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(label="native-archive-profile", facts={})
        assert profile.label is not None
        profile_id = resolve_login_target(profile.label).bucket_id
        target = tmp_path / "native-backup.cadrumo-bucket.tar.gz"

        exported = _invoke(profile, "config", "profile", "archive", "export", profile.label, "--output", str(target))

        assert exported.exit_code == 0, exported.output
        document = unwrap_cli_result(exported)
        assert set(document) == {"bucket_id", "target", "archive_schema_version", "recovery_enrolled"}
        assert document["target"] == str(target)
        assert document["archive_schema_version"] == ARCHIVE_SCHEMA_VERSION
        assert isinstance(document["recovery_enrolled"], bool)
        assert target.is_file()
        assert profile_id not in exported.output
        assert document["bucket_id"] == "<bucket-id>"

        with tarfile.open(target, mode="r:gz") as archive:
            member_payloads: dict[str, bytes] = {}
            for member in archive.getmembers():
                if not member.isfile():
                    continue
                extracted = archive.extractfile(member)
                assert extracted is not None
                member_payloads[member.name] = extracted.read()
        assert set(member_payloads) == {"header.json", "payload.envelope"}
        assert profile.label.encode("utf-8") not in b"\n".join(member_payloads.values())
        assert str(inspect_profile_capsule_archive(target).bucket_id) == profile_id

        default_target = tmp_path / "default-profile-backup.cadrumo-bucket.tar.gz"
        default_export = _invoke(
            profile,
            "config",
            "profile",
            "archive",
            "export",
            "--output",
            str(default_target),
        )
        assert default_export.exit_code == 0, default_export.output
        assert unwrap_cli_result(default_export)["target"] == str(default_target)
        assert str(inspect_profile_capsule_archive(default_target).bucket_id) == profile_id

        invalid_target = tmp_path / "wrong-suffix.zip"
        suffix_refusal = _invoke(
            profile,
            "config",
            "profile",
            "archive",
            "export",
            "--output",
            str(invalid_target),
        )
        assert suffix_refusal.exit_code == 2, suffix_refusal.output
        suffix_error = require_error_document(suffix_refusal.output)["error"]
        assert suffix_error["code"] == "REFUSED_CLI_BOUNDARY"
        assert suffix_error["context"] == {"suffix": ".cadrumo-bucket.tar.gz"}
        assert not invalid_target.exists()

        original = target.read_bytes()
        exists_refusal = _invoke(
            profile,
            "config",
            "profile",
            "archive",
            "export",
            "--output",
            str(target),
        )
        assert exists_refusal.exit_code == 2, exists_refusal.output
        assert require_error_document(exists_refusal.output)["error"]["code"] == "REFUSED_CLI_BOUNDARY"
        assert target.read_bytes() == original

        close_active_bucket_session()
        inspected = invoke_cached_cli(
            ("--format", "json", "config", "profile", "archive", "inspect", "--file", str(target)),
        )
        assert inspected.exit_code == 0, inspected.output
        assert json.loads(inspected.output)["command"] == "config.profile.archive.inspect"
        assert profile.label not in json.dumps(json.loads(inspected.output)["result"])


def test_native_archive_push_dry_run_and_reconcile_use_registered_worker(tmp_path: Path) -> None:
    """A dry-run needs no Drive credentials; the exact profile then reconciles locally."""
    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(label="native-archive-reconcile", facts={})
        assert profile.label is not None
        profile_id = resolve_login_target(profile.label).bucket_id
        save_drive_config(profile_id, DriveConfig(root_folder_id="offline-test-root"))
        namespace = GOOGLE_DRIVE_CONFIG_NAMESPACE.namespace
        expected_rows = len(
            tuple(secure_object_repository_for_active_bucket().iter_all_records_raw(namespace=namespace))
        )

        preview = _invoke(profile, "config", "profile", "archive", "push", "--dry-run", "--namespace", namespace)

        assert preview.exit_code == 0, preview.output
        push_result = (
            command_schema_type("config.profile.archive.push")
            .model_validate(unwrap_cli_result(preview))
            .model_dump(mode="json")
        )
        assert push_result["dry_run"] is True
        assert push_result["root_folder_id"] == "offline-test-root"
        assert push_result["pushed_total"] == 0
        assert push_result["skipped_total"] == expected_rows
        assert push_result["failed_total"] == 0
        assert push_result["manifest_pushed_total"] == 0
        assert profile_id not in preview.output

        reconciled = _invoke(profile, "config", "profile", "archive", "reconcile")

        assert reconciled.exit_code == 0, reconciled.output
        reconcile_result = (
            command_schema_type("config.profile.archive.reconcile")
            .model_validate(unwrap_cli_result(reconciled))
            .model_dump(mode="json")
        )
        assert reconcile_result["reconciled_count"] == 0
        assert reconcile_result["failed_count"] == 0
        notices = unwrap_envelope_notices(reconciled.output)
        assert [
            notice["code"] for notice in notices if notice["code"].startswith("config.profile.archive.reconcile.")
        ] == ["config.profile.archive.reconcile.nothing_to_reconcile"]

        text_result = _invoke(profile, "config", "profile", "archive", "reconcile", json_output=False)
        assert text_result.exit_code == 0, text_result.output
        assert "reconciled\t0" in text_result.output
        assert "failed\t0" in text_result.output
