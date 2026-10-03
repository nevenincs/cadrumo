"""Native-worker proofs for ``aeat config profile archive reconcile``.

The export service reconciles before every publication, so an operator who
keeps exporting never needs this verb. It exists for the crash case where an
orphan journal and its ``0o600`` cleartext ``.export-tmp`` would otherwise
remain on disk. These cases seed that real journal through the canonical
service, then invoke the registered exact-profile worker route.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ....application.user_profile.bundle_export import PreparedProfileExport, prepare_profile_export
from ....application.user_profile.bundle_export_contracts import (
    ProfileBundleExportPurpose,
    ProfileBundleExportRequest,
    ProfileBundleExportTransport,
)
from ....application.user_profile.bundle_export_operation import (
    PROFILE_EXPORT_STAGED_TEMP_SUFFIX,
    ProfileBundleExportJournalRepository,
)
from ....application.user_profile.login_session import resolve_login_target
from ....core.directory_scan import scan_directory
from ....core.type_adapters import STR_KEYED_MAPPING_ADAPTER
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.user_profile.portable_export import UserProfilePortableExport
from .cli_runner import invoke_cached_cli
from .runtime_profile_cli_fixture import NativeCliProfileFixture, native_cli_profile_scope

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="reconcile now uses native profile workers"),
]

_RECONCILE_ARGV = ("--format", "json", "config", "profile", "archive", "reconcile")
_PROFILE_FACTS = {
    "identity.tax_id": "12345678Z",
    "activities.description": "design",
    "taxpayer_type.entity_type": "natural_person",
    "identity.name": "Subject",
    "identity.surnames": "Access",
}


def _request(profile_name: str, destination: Path) -> ProfileBundleExportRequest:
    return ProfileBundleExportRequest(
        profile_name=profile_name,
        destination=destination,
        purpose=ProfileBundleExportPurpose.PORTABLE_TRANSFER,
        transport=ProfileBundleExportTransport.CLEARTEXT_LOCAL,
    )


def _journal(profile: NativeCliProfileFixture) -> ProfileBundleExportJournalRepository:
    return ProfileBundleExportJournalRepository(storage_root=profile.storage_root)


def _prepare_export(profile: NativeCliProfileFixture, destination: Path) -> PreparedProfileExport:
    """Prepare one exact-profile orphan under the fixture's pinned authority."""
    if profile.label is None:
        raise AssertionError("native profile was not registered")
    profile_id = resolve_login_target(profile.label).bucket_id
    with bundled_indexed_authority().operation() as operation:
        return prepare_profile_export(
            _request(profile.label, destination),
            journal=_journal(profile),
            authority_operation=operation,
            profile_decode_context=operation.profile_decode_context(),
            authorized_profile_id=profile_id,
        )


def _load_export(profile: NativeCliProfileFixture, path: Path) -> UserProfilePortableExport:
    """Decode a staged bundle with the same pinned profile context."""
    if profile.label is None:
        raise AssertionError("native profile was not registered")
    with bundled_indexed_authority().operation() as operation:
        return UserProfilePortableExport.model_validate_json(
            path.read_text(encoding="utf-8"),
            context=operation.profile_decode_context(),
        )


def _reconcile_json(profile: NativeCliProfileFixture) -> dict[str, object]:
    if profile.label is None:
        raise AssertionError("native profile was not registered")
    close_active_bucket_session()
    result = invoke_cached_cli(
        (
            "--language",
            "en",
            "--profile",
            profile.label,
            "--profile-secrets-stdin",
            *_RECONCILE_ARGV,
        ),
        input=json.dumps({"profile_passphrase": profile.passphrase}),
    )
    assert profile.passphrase not in result.output
    assert result.exit_code == 0, result.output
    envelope = STR_KEYED_MAPPING_ADAPTER.validate_json(result.output)
    return STR_KEYED_MAPPING_ADAPTER.validate_python(envelope["result"])


def _first_row(rows: object) -> dict[str, object]:
    """Return one keyed envelope row and check the public collection shape."""
    assert isinstance(rows, list)
    assert rows, "expected at least one row"
    row = rows[0]
    assert isinstance(row, dict)
    return {str(key): value for key, value in row.items()}


def test_the_verb_clears_an_abandoned_crash_orphan_and_its_cleartext_staged_file(tmp_path: Path) -> None:
    """A registered worker clears the exact profile's unpublished staged bundle."""
    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(label="archive-reconcile-subject", facts=_PROFILE_FACTS)
        destination = tmp_path / "portable.json"
        prepared = _prepare_export(profile, destination)
        staged = Path(prepared.staged_path)
        staged_bundle = _load_export(profile, staged)
        assert any(fact.path == "identity.name" and fact.value == "Subject" for fact in staged_bundle.profile.facts)
        assert len(_journal(profile).prepared()) == 1

        payload = _reconcile_json(profile)

        assert payload["reconciled_count"] == 1
        assert payload["failed_count"] == 0
        first = _first_row(payload["reconciled"])
        assert first["operation_id"] == prepared.operation.operation_id
        assert first["destination"] == str(destination)
        assert not staged.exists()
        assert not destination.exists()
        assert list(scan_directory(tmp_path, pattern=f"*{PROFILE_EXPORT_STAGED_TEMP_SUFFIX}")) == []
        assert _journal(profile).list() == ()


def test_the_verb_reports_an_isolated_failure_without_dropping_its_journal(tmp_path: Path) -> None:
    """A readable exact-profile journal failure is retained beside successful cleanup."""
    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(label="archive-reconcile-corrupt", facts=_PROFILE_FACTS)
        _prepare_export(profile, tmp_path / "portable.json")
        repository = _journal(profile)
        failed = _prepare_export(profile, tmp_path / "unrecoverable.json")
        corrupt_id = failed.operation.operation_id
        corrupt_path = repository.path_for(corrupt_id)
        repository.save(failed.operation.model_copy(update={"target_identity": "unsupported-target"}))

        payload = _reconcile_json(profile)

        assert payload["reconciled_count"] == 1
        assert payload["failed_count"] == 1
        first = _first_row(payload["failed"])
        assert first["journal_id"] == corrupt_id
        assert first["destination"] == str(tmp_path / "unrecoverable.json")
        assert first["reason"] == "ProfileExportError"
        assert corrupt_path.is_file()


def test_the_verb_reports_a_clean_sweep_rather_than_staying_silent(tmp_path: Path) -> None:
    """An authenticated empty sweep keeps the explicit informational notice."""
    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(label="archive-reconcile-empty", facts=_PROFILE_FACTS)
        payload = _reconcile_json(profile)
        assert payload["reconciled_count"] == 0
        assert payload["failed_count"] == 0

        close_active_bucket_session()
        result = invoke_cached_cli(
            (
                "--language",
                "en",
                "--profile",
                profile.label or "",
                "--profile-secrets-stdin",
                *_RECONCILE_ARGV,
            ),
            input=json.dumps({"profile_passphrase": profile.passphrase}),
        )
        assert result.exit_code == 0, result.output
        codes = [notice["code"] for notice in json.loads(result.output)["notices"]]
        assert [code for code in codes if code.startswith("config.profile.archive.reconcile.")] == [
            "config.profile.archive.reconcile.nothing_to_reconcile"
        ]


def test_a_failed_sweep_carries_a_warning_notice_and_a_clean_one_does_not(tmp_path: Path) -> None:
    """Warning severity tracks retained exact-profile journal failures across worker calls."""
    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(label="archive-reconcile-warning", facts=_PROFILE_FACTS)
        _prepare_export(profile, tmp_path / "portable.json")
        repository = _journal(profile)
        failed = _prepare_export(profile, tmp_path / "unrecoverable.json")
        corrupt_id = failed.operation.operation_id
        corrupt_path = repository.path_for(corrupt_id)
        repository.save(failed.operation.model_copy(update={"target_identity": "unsupported-target"}))

        _reconcile_json(profile)
        close_active_bucket_session()
        failed_run = invoke_cached_cli(
            (
                "--language",
                "en",
                "--profile",
                profile.label or "",
                "--profile-secrets-stdin",
                *_RECONCILE_ARGV,
            ),
            input=json.dumps({"profile_passphrase": profile.passphrase}),
        )
        assert failed_run.exit_code == 0, failed_run.output
        failed_notices = [
            notice
            for notice in json.loads(failed_run.output)["notices"]
            if notice["code"].startswith("config.profile.archive.reconcile.")
        ]
        assert [notice["severity"] for notice in failed_notices] == ["warning"]
        assert failed_notices[0]["code"] == "config.profile.archive.reconcile.failures"
        assert failed_notices[0]["context"]["journal_ids"] == corrupt_id
        assert failed_notices[0]["action"] == {
            "action": {
                "action_id": "operator.profile.archive.reconcile",
                "target_command_key": "config.profile.archive.reconcile",
                "cli_path": ["config", "profile", "archive", "reconcile"],
            },
            "argument_bindings": [],
        }

        corrupt_path.unlink()
        close_active_bucket_session()
        clean_run = invoke_cached_cli(
            (
                "--language",
                "en",
                "--profile",
                profile.label or "",
                "--profile-secrets-stdin",
                *_RECONCILE_ARGV,
            ),
            input=json.dumps({"profile_passphrase": profile.passphrase}),
        )
        assert clean_run.exit_code == 0, clean_run.output
        clean_notices = [
            notice
            for notice in json.loads(clean_run.output)["notices"]
            if notice["code"].startswith("config.profile.archive.reconcile.")
        ]
        assert [notice["severity"] for notice in clean_notices] == ["info"]
