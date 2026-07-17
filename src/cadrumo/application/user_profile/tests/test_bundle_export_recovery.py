"""Fresh-process crash-window recovery proofs for profile-bundle publication.

A real child process serializes and journals a ``PREPARED`` export, then hard
exits before (or between) the atomic replace and the completion event. A fresh
process reconciles the durable operation state honestly: a prepared operation is
reported as prepared, never upgraded to complete, its orphan staged temp is
cleared, and no ``PROFILE_EXPORTED`` completion event is ever surfaced for an
artifact that was not durably published.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.storage.sql import dispose_engine
from ....domain.buckets import BucketEvent, BucketEventType
from ....domain.user_profile import UserProfilePortableExport
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root
from .. import (
    ProfileBundleExportPurpose,
    ProfileBundleExportRequest,
    ProfileBundleExportTransport,
    prepare_profile_export,
    profile_storage_session,
    reconcile_prepared_exports,
)
from .._bundle_export import _STAGED_TEMP_SUFFIX
from .._bundle_export_operation import ProfileBundleExportJournalRepository

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_CRASH_EXIT_CODE = 91

_SETTINGS_PREAMBLE = dedent(
    """
    from __future__ import annotations

    import os
    import sys
    from pathlib import Path

    from cadrumo.core import config as config_module
    from cadrumo.core.config import DEV_TEST_DATABASE_PASSWORD, Settings

    root = Path(sys.argv[1])
    settings = Settings(
        _env_file=None,
        cadrumo_local_storage_root=root,
        cadrumo_active_profile=None,
        cadrumo_secret_store_backend="file",
        cadrumo_secret_store_dir=root.parent / "secrets",
        cadrumo_secret_passphrase=DEV_TEST_DATABASE_PASSWORD,
        cadrumo_output_language="en",
    )
    token = config_module._settings_override.set(settings)
    """,
)

_EXPORT_HARNESS = _SETTINGS_PREAMBLE + dedent(
    """
    from cadrumo.application.user_profile import (
        ProfileBundleExportPurpose,
        ProfileBundleExportRequest,
        ProfileBundleExportTransport,
        export_profile_bundle,
        prepare_profile_export,
    )

    destination = Path(sys.argv[2])
    mode = sys.argv[3]
    request = ProfileBundleExportRequest(
        profile_name="subject",
        destination=destination,
        purpose=ProfileBundleExportPurpose.PORTABLE_TRANSFER,
        transport=ProfileBundleExportTransport.CLEARTEXT_LOCAL,
    )
    if mode == "publish":
        export_profile_bundle(request)
        config_module._settings_override.reset(token)
        sys.exit(0)
    prepared = prepare_profile_export(request)
    if mode == "replaced":
        os.replace(prepared.staged_path, destination)
    os._exit(91)
    """,
)


def _child_env(root: Path, *, extra: dict[str, str] | None = None) -> dict[str, str]:
    from ....core.config import DEV_TEST_DATABASE_PASSWORD

    env = {key: value for key, value in os.environ.items() if not key.startswith(("AEAT_", "CADRUMO_", "PYTEST_"))}
    env.update(
        {
            "CADRUMO_LOCAL_STORAGE_ROOT": str(root),
            "CADRUMO_SECRET_STORE_BACKEND": "file",
            "CADRUMO_SECRET_STORE_DIR": str(root.parent / "secrets"),
            "CADRUMO_SECRET_PASSPHRASE": DEV_TEST_DATABASE_PASSWORD,
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUTF8": "1",
        },
    )
    if extra is not None:
        env.update(extra)
    return env


def _run_export_child(
    root: Path,
    destination: Path,
    mode: str,
    *,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - fixed interpreter and repository-owned harness
        [sys.executable, "-c", _EXPORT_HARNESS, str(root), str(destination), mode],
        cwd=Path.cwd(),
        env=_child_env(root, extra=extra_env),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )


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


def _export_events(bucket_id: str) -> tuple[BucketEvent, ...]:
    with profile_storage_session(bucket_id):
        catalogue = BucketEventHistoryRepository().load()
    return tuple(event for event in catalogue.events.values() if event.event_type is BucketEventType.PROFILE_EXPORTED)


def _request(destination: Path) -> ProfileBundleExportRequest:
    return ProfileBundleExportRequest(
        profile_name="subject",
        destination=destination,
        purpose=ProfileBundleExportPurpose.PORTABLE_TRANSFER,
        transport=ProfileBundleExportTransport.CLEARTEXT_LOCAL,
    )


def test_crash_before_replace_reconciles_as_prepared_with_no_completion_event(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        bucket_id = _create_profile()
        dispose_engine()
        destination = tmp_path / "portable.json"

        crashed = _run_export_child(storage_root, destination, "prepared")
        assert crashed.returncode == _CRASH_EXIT_CODE, (crashed.stdout, crashed.stderr)

        repository = ProfileBundleExportJournalRepository()
        prepared_before = repository.prepared()
        assert len(prepared_before) == 1
        staged = Path(prepared_before[0].staged_path)
        assert staged.exists()
        assert not destination.exists()
        assert _export_events(bucket_id) == ()

        reconciled = reconcile_prepared_exports()
        assert len(reconciled) == 1
        assert reconciled[0].operation_id == prepared_before[0].operation_id
        assert not staged.exists()
        assert not destination.exists()
        assert repository.prepared() == ()
        assert _export_events(bucket_id) == ()


def test_crash_after_replace_reconciles_to_a_completed_event_via_the_content_digest(tmp_path: Path) -> None:
    # Contract (S11): a crash between the atomic replace and the COMPLETED
    # journal write leaves a durably-published bundle with only a PREPARED
    # journal. Reconcile detects the publication via the recorded content digest
    # and emits the owed PROFILE_EXPORTED event, so no durably-published bundle is
    # left without its audit event.
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        bucket_id = _create_profile()
        dispose_engine()
        destination = tmp_path / "portable.json"

        crashed = _run_export_child(storage_root, destination, "replaced")
        assert crashed.returncode == _CRASH_EXIT_CODE, (crashed.stdout, crashed.stderr)

        repository = ProfileBundleExportJournalRepository()
        assert len(repository.prepared()) == 1
        assert destination.exists()
        published = UserProfilePortableExport.model_validate_json(destination.read_text(encoding="utf-8"))
        assert published.profile.profile_id == bucket_id
        # No premature event yet: the crash was before the event write.
        assert _export_events(bucket_id) == ()

        reconciled = reconcile_prepared_exports()
        assert len(reconciled) == 1
        assert destination.exists()
        assert repository.list() == ()
        # The digest-matched publication is completed: the owed event is emitted.
        assert len(_export_events(bucket_id)) == 1


def test_reconcile_completion_is_idempotent_for_a_published_operation(tmp_path: Path) -> None:
    # Running reconcile more than once must emit the completion event exactly
    # once, because it derives from the operation's fixed event_occurred_at.
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        bucket_id = _create_profile()
        dispose_engine()
        destination = tmp_path / "portable.json"

        crashed = _run_export_child(storage_root, destination, "replaced")
        assert crashed.returncode == _CRASH_EXIT_CODE, (crashed.stdout, crashed.stderr)

        first = reconcile_prepared_exports()
        assert len(first) == 1
        assert len(_export_events(bucket_id)) == 1
        # A second reconcile has no journal left to act on and emits nothing new.
        second = reconcile_prepared_exports()
        assert second == ()
        assert len(_export_events(bucket_id)) == 1


def test_digest_matched_reconcile_leaves_no_cleartext_staged_temp(tmp_path: Path) -> None:
    # Sensitive-data posture: even in the coincidental edge where a pre-replace
    # crash leaves the destination already holding byte-identical content from a
    # prior identical export (so the digest matches without our replace running),
    # reconcile must not leave the cleartext staged .export-tmp on disk.
    with isolated_profile_storage_root(tmp_path=tmp_path):
        bucket_id = _create_profile()
        destination = tmp_path / "portable.json"

        prepared = prepare_profile_export(_request(destination))
        staged = Path(prepared.staged_path)
        # A prior identical export having landed exactly these bytes, then a
        # crash before this operation's os.replace: the destination coincidentally
        # matches the recorded digest while the staged temp still exists.
        destination.write_bytes(staged.read_bytes())
        assert staged.exists()
        repository = ProfileBundleExportJournalRepository()
        assert len(repository.prepared()) == 1
        events_before = len(_export_events(bucket_id))

        reconciled = reconcile_prepared_exports()

        assert len(reconciled) == 1
        assert repository.list() == ()
        assert len(_export_events(bucket_id)) == events_before + 1
        assert destination.exists()
        # The cleartext staged temp must be gone.
        assert not staged.exists()
        assert list(tmp_path.glob(f"*{_STAGED_TEMP_SUFFIX}")) == []


def test_completed_export_leaves_no_journal_and_one_event(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        bucket_id = _create_profile()
        dispose_engine()
        destination = tmp_path / "portable.json"

        completed = _run_export_child(storage_root, destination, "publish")
        assert completed.returncode == 0, (completed.stdout, completed.stderr)

        repository = ProfileBundleExportJournalRepository()
        assert repository.list() == ()
        assert destination.exists()
        dispose_engine()
        assert len(_export_events(bucket_id)) == 1


def test_prepared_staged_temp_is_restrictive_and_unpublished(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _create_profile()
        destination = tmp_path / "portable.json"

        prepared = prepare_profile_export(_request(destination))
        staged = Path(prepared.staged_path)
        try:
            assert staged.exists()
            assert staged.is_file()
            assert not destination.exists()
            if os.name == "posix":
                assert staged.stat().st_mode & 0o777 == 0o600
        finally:
            reconcile_prepared_exports()
        assert not staged.exists()
        assert not destination.exists()


def test_export_publishes_into_a_freshly_created_parent_directory(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        bucket_id = _create_profile()
        dispose_engine()
        destination = tmp_path / "nested" / "output" / "dir" / "portable.json"
        assert not destination.parent.exists()

        completed = _run_export_child(storage_root, destination, "publish")
        assert completed.returncode == 0, (completed.stdout, completed.stderr)

        assert destination.is_file()
        published = UserProfilePortableExport.model_validate_json(destination.read_text(encoding="utf-8"))
        assert published.profile.profile_id == bucket_id


def test_reconcile_skips_a_prepared_operation_whose_target_lock_is_held(tmp_path: Path) -> None:
    from ....core.locks import exclusive_file_lock

    with isolated_profile_storage_root(tmp_path=tmp_path):
        _create_profile()
        destination = tmp_path / "portable.json"

        prepared = prepare_profile_export(_request(destination))
        staged = Path(prepared.staged_path)
        repository = ProfileBundleExportJournalRepository()
        assert len(repository.prepared()) == 1
        assert staged.exists()

        # A live export holds the destination lock across its whole publication.
        # Reconcile must not touch this in-flight operation.
        with exclusive_file_lock(destination):
            reconciled = reconcile_prepared_exports()

        assert reconciled == ()
        assert staged.exists()
        assert len(repository.prepared()) == 1

        # Once the lock is released, the same operation reconciles normally.
        cleared = reconcile_prepared_exports()
        assert len(cleared) == 1
        assert cleared[0].operation_id == prepared.operation.operation_id
        assert not staged.exists()
        assert not destination.exists()


def test_same_target_export_is_excluded_while_the_target_lock_is_held(tmp_path: Path) -> None:
    from ....core.locks import exclusive_file_lock

    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        _create_profile()
        dispose_engine()
        destination = tmp_path / "portable.json"

        with exclusive_file_lock(destination):
            blocked = _run_export_child(
                storage_root,
                destination,
                "publish",
                extra_env={"CADRUMO_FILE_LOCK_TIMEOUT_S": "1"},
            )

        assert blocked.returncode != 0
        combined = f"{blocked.stdout}\n{blocked.stderr}".lower()
        assert "lock" in combined
        assert not destination.exists()
