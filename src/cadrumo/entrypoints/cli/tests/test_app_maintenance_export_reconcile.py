"""Operator-path proofs for ``aeat app maintenance profile-bundle-reconcile``.

The export service reconciles before every publication, so an operator who keeps
exporting never needs this verb. It exists for the one case that trigger
structurally cannot reach: a crash followed by no further export, where the
orphan journal and its ``0o600`` cleartext ``.export-tmp`` -- holding the whole
profile bundle -- would otherwise sit on disk indefinitely.

Every proof drives the real CLI through the runner. Nothing here calls
``reconcile_prepared_exports`` to do the work; the point is that the operator's
own invocation is what clears the file.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ....application.user_profile import (
    ProfileBundleExportPurpose,
    ProfileBundleExportRequest,
    ProfileBundleExportTransport,
    prepare_profile_export,
)
from ....application.user_profile._bundle_export import _STAGED_TEMP_SUFFIX
from ....application.user_profile._bundle_export_operation import ProfileBundleExportJournalRepository
from ....domain.user_profile import UserProfilePortableExport
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_RECONCILE_ARGV = ("--format", "json", "app", "maintenance", "profile-bundle-reconcile")


def _create_profile() -> str:
    result = invoke_cached_cli(
        [
            "config",
            "profile",
            "create",
            "subject",
            "--quiet",
            "--tax-id",
            "12345678Z",
            "--activity",
            "design",
            "--entity-type",
            "natural_person",
            "--name",
            "Subject",
            "--surnames",
            "Access",
        ],
    )
    assert result.exit_code == 0, result.output

    from ....core import resolve_active_bucket_id

    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None
    return bucket_id


def _request(destination: Path) -> ProfileBundleExportRequest:
    return ProfileBundleExportRequest(
        profile_name="subject",
        destination=destination,
        purpose=ProfileBundleExportPurpose.PORTABLE_TRANSFER,
        transport=ProfileBundleExportTransport.CLEARTEXT_LOCAL,
    )


def _reconcile_json() -> dict[str, object]:
    result = invoke_cached_cli(list(_RECONCILE_ARGV))
    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    payload = envelope["result"]
    assert isinstance(payload, dict)
    return payload


def test_the_verb_clears_an_abandoned_crash_orphan_and_its_cleartext_staged_file(tmp_path: Path) -> None:
    # The case the pre-flight trigger cannot reach: the operator crashed and
    # never exported again. Only this verb clears the bundle bytes.
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _create_profile()
        destination = tmp_path / "portable.json"

        prepared = prepare_profile_export(_request(destination))
        staged = Path(prepared.staged_path)
        # The staged temp really is the readable bundle, not an empty placeholder.
        staged_bundle = UserProfilePortableExport.model_validate_json(staged.read_text(encoding="utf-8"))
        assert staged_bundle.profile.display_name == "subject"
        assert len(ProfileBundleExportJournalRepository().prepared()) == 1

        payload = _reconcile_json()

        assert payload["reconciled_count"] == 1
        assert payload["failed_count"] == 0
        reconciled = payload["reconciled"]
        assert isinstance(reconciled, list)
        assert reconciled[0]["operation_id"] == prepared.operation.operation_id
        assert reconciled[0]["destination"] == str(destination)
        # The cleartext bundle bytes are gone from disk, and no export ran.
        assert not staged.exists()
        assert not destination.exists()
        assert list(tmp_path.glob(f"*{_STAGED_TEMP_SUFFIX}")) == []
        assert ProfileBundleExportJournalRepository().list() == ()


def test_the_verb_reports_an_isolated_failure_without_dropping_its_journal(tmp_path: Path) -> None:
    # A journal the sweep cannot read must be reported to the operator, not
    # silently skipped: it may still describe cleartext bytes on disk. It is
    # kept for a later attempt rather than deleted.
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _create_profile()
        repository = ProfileBundleExportJournalRepository()
        prepare_profile_export(_request(tmp_path / "portable.json"))
        corrupt_id = "d" * 64
        corrupt_path = repository.path_for(corrupt_id)
        corrupt_path.write_text("{not valid json", encoding="utf-8")

        payload = _reconcile_json()

        assert payload["reconciled_count"] == 1
        assert payload["failed_count"] == 1
        failed = payload["failed"]
        assert isinstance(failed, list)
        assert failed[0]["journal_id"] == corrupt_id
        assert failed[0]["destination"] is None
        assert failed[0]["reason"] == "ProfileBundleExportJournalCorruptError"
        # Kept for a retry rather than dropped.
        assert corrupt_path.is_file()


def test_the_verb_reports_a_clean_sweep_rather_than_staying_silent(tmp_path: Path) -> None:
    # An operator running recovery on healthy state must be told there was
    # nothing to recover, so "nothing to do" cannot read as "it did not run".
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _create_profile()

        result = invoke_cached_cli(list(_RECONCILE_ARGV))

        assert result.exit_code == 0, result.output
        envelope = json.loads(result.output)
        assert envelope["result"]["reconciled_count"] == 0
        assert envelope["result"]["failed_count"] == 0
        codes = [notice["code"] for notice in envelope["notices"]]
        assert codes == ["app.maintenance.profile_bundle_reconcile.nothing_to_reconcile"]


def test_a_failed_sweep_carries_a_warning_notice_and_a_clean_one_does_not(tmp_path: Path) -> None:
    # Severity is the operator's signal that bundle bytes may still be on disk,
    # so it must track the outcome rather than being constant.
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _create_profile()
        repository = ProfileBundleExportJournalRepository()
        prepare_profile_export(_request(tmp_path / "portable.json"))
        repository.path_for("e" * 64).write_text("{not valid json", encoding="utf-8")

        failed_run = invoke_cached_cli(list(_RECONCILE_ARGV))
        assert failed_run.exit_code == 0, failed_run.output
        failed_notices = json.loads(failed_run.output)["notices"]
        assert [notice["severity"] for notice in failed_notices] == ["info", "warning"]
        assert failed_notices[1]["code"] == "app.maintenance.profile_bundle_reconcile.failures"
        assert failed_notices[1]["context"]["journal_ids"] == "e" * 64

        # The corrupt journal survives, so a second run still warns; remove it
        # and the sweep goes quiet, proving the warning tracks real state.
        repository.path_for("e" * 64).unlink()
        clean_run = invoke_cached_cli(list(_RECONCILE_ARGV))
        assert clean_run.exit_code == 0, clean_run.output
        clean_notices = json.loads(clean_run.output)["notices"]
        assert [notice["severity"] for notice in clean_notices] == ["info"]
