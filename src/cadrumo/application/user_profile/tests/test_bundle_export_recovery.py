"""Fresh-process crash-window recovery proofs for profile-bundle publication.

A real child process serializes and journals a ``PREPARED`` export, then hard
exits before (or between) the atomic replace and the completion event. A fresh
process reconciles the durable operation state honestly: a prepared operation is
reported as prepared, never upgraded to complete, its orphan staged temp is
cleared, and no ``PROFILE_EXPORTED`` completion event is ever surfaced for an
artifact that was not durably published.

Recovery is proved twice over: once through :func:`reconcile_prepared_exports`
directly, for the reconciliation contract itself, and once through the operator
path -- a plain later :func:`export_profile_bundle` call, with nothing in the
test invoking reconciliation -- so the mechanism is proved reachable in
production rather than only from the harness.
"""

from __future__ import annotations

import contextlib
import os
import subprocess
import sys
from datetime import timedelta
from pathlib import Path
from textwrap import dedent
from typing import override

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.storage.sql import dispose_engine
from ....core.locks import exclusive_file_lock
from ....domain.buckets import BucketEvent, BucketEventType
from ....domain.user_profile import UserProfilePortableExport
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root
from .. import (
    ProfileBundleExportPurpose,
    ProfileBundleExportRequest,
    ProfileBundleExportTransport,
    export_profile_bundle,
    prepare_profile_export,
    profile_storage_session,
    reconcile_prepared_exports,
)
from .._bundle_export import _STAGED_TEMP_SUFFIX
from .._bundle_export_operation import (
    ProfileBundleExportJournalRepository,
    ProfileBundleExportOperationStatus,
)

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

        outcome = reconcile_prepared_exports()
        assert outcome.failures == ()
        assert len(outcome.reconciled) == 1
        assert outcome.reconciled[0].operation_id == prepared_before[0].operation_id
        assert not staged.exists()
        assert not destination.exists()
        assert repository.prepared() == ()
        assert _export_events(bucket_id) == ()


def test_crash_after_replace_reconciles_to_a_completed_event_via_the_content_digest(tmp_path: Path) -> None:
    # Contract: a crash between the atomic replace and the COMPLETED
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

        outcome = reconcile_prepared_exports()
        assert outcome.failures == ()
        assert len(outcome.reconciled) == 1
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
        assert len(first.reconciled) == 1
        assert len(_export_events(bucket_id)) == 1
        # A second reconcile has no journal left to act on and emits nothing new.
        second = reconcile_prepared_exports()
        assert second.reconciled == ()
        assert second.failures == ()
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

        outcome = reconcile_prepared_exports()

        assert outcome.failures == ()
        assert len(outcome.reconciled) == 1
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


def test_a_later_export_clears_a_crashed_run_orphan_journal_and_cleartext_temp(tmp_path: Path) -> None:
    # The production trigger, not the test harness: a crashed export leaves a
    # PREPARED journal and a 0o600 cleartext staged temp holding the whole
    # bundle. Nothing here calls reconcile; the operator's NEXT export -- to an
    # unrelated destination -- is what must clear both, or those bundle bytes
    # sit on disk indefinitely (sensitive-financial-data-secure-storage-only).
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        bucket_id = _create_profile()
        dispose_engine()
        abandoned = tmp_path / "abandoned.json"

        crashed = _run_export_child(storage_root, abandoned, "prepared")
        assert crashed.returncode == _CRASH_EXIT_CODE, (crashed.stdout, crashed.stderr)

        repository = ProfileBundleExportJournalRepository()
        orphaned = repository.prepared()
        assert len(orphaned) == 1
        staged = Path(orphaned[0].staged_path)
        assert staged.is_file()
        # The staged temp really is the readable bundle, not an empty placeholder.
        staged_bundle = UserProfilePortableExport.model_validate_json(staged.read_text(encoding="utf-8"))
        assert staged_bundle.profile.profile_id == bucket_id
        assert not abandoned.exists()

        published = export_profile_bundle(_request(tmp_path / "later.json"))

        assert published.profile_id == bucket_id
        assert (tmp_path / "later.json").is_file()
        assert not staged.exists()
        assert not abandoned.exists()
        assert repository.list() == ()
        assert list(tmp_path.glob(f"*{_STAGED_TEMP_SUFFIX}")) == []
        # The orphan never published, so only the new export owns an event.
        assert len(_export_events(bucket_id)) == 1


def test_re_exporting_to_the_crashed_target_clears_its_orphan_before_reusing_the_journal(tmp_path: Path) -> None:
    # The operation id is clock-free and derived from profile, target identity,
    # and purpose, so re-exporting to the SAME target reuses -- and overwrites --
    # the crashed run's journal, which holds the only record of where its
    # cleartext temp was staged. The reconcile must therefore run before the
    # journal is rewritten, or that file is stranded with no way back to it.
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        bucket_id = _create_profile()
        dispose_engine()
        destination = tmp_path / "portable.json"

        crashed = _run_export_child(storage_root, destination, "prepared")
        assert crashed.returncode == _CRASH_EXIT_CODE, (crashed.stdout, crashed.stderr)

        repository = ProfileBundleExportJournalRepository()
        orphaned = repository.prepared()
        assert len(orphaned) == 1
        abandoned_temp = Path(orphaned[0].staged_path)
        assert abandoned_temp.is_file()

        published = export_profile_bundle(_request(destination))

        assert published.profile_id == bucket_id
        assert destination.is_file()
        assert not abandoned_temp.exists()
        assert repository.list() == ()
        assert list(tmp_path.glob(f"*{_STAGED_TEMP_SUFFIX}")) == []
        assert len(_export_events(bucket_id)) == 1


def test_a_later_export_emits_the_owed_event_for_a_crash_published_bundle(tmp_path: Path) -> None:
    # The un-audited-egress half of the same trigger: a crash between the atomic
    # replace and the audit event leaves a durably-published bundle with no
    # PROFILE_EXPORTED record. The next export to an unrelated destination must
    # settle that owed event.
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        bucket_id = _create_profile()
        dispose_engine()
        crashed_destination = tmp_path / "published-uneventfully.json"

        crashed = _run_export_child(storage_root, crashed_destination, "replaced")
        assert crashed.returncode == _CRASH_EXIT_CODE, (crashed.stdout, crashed.stderr)
        assert crashed_destination.is_file()
        assert _export_events(bucket_id) == ()

        export_profile_bundle(_request(tmp_path / "later.json"))

        # One event owed by the crashed publication, one for the new export.
        assert len(_export_events(bucket_id)) == 2
        assert ProfileBundleExportJournalRepository().list() == ()
        assert crashed_destination.is_file()


def _write_corrupt_journal(repository: ProfileBundleExportJournalRepository, journal_id: str) -> Path:
    """Write a real unparseable journal file, as a torn write would leave."""
    path = repository.path_for(journal_id)
    path.write_text("{not valid json", encoding="utf-8")
    return path


def test_a_corrupt_journal_does_not_starve_the_healthy_operation_behind_it(tmp_path: Path) -> None:
    # Isolation contract: journals are walked in start-time order, so a corrupt
    # record ordered ahead of a healthy one used to abort the whole sweep and
    # leave the healthy operation's cleartext staged temp on disk forever. The
    # corrupt journal must be reported, not silently skipped, and must not
    # prevent the healthy operation from being reconciled.
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _create_profile()
        destination = tmp_path / "portable.json"

        prepared = prepare_profile_export(_request(destination))
        staged = Path(prepared.staged_path)
        repository = ProfileBundleExportJournalRepository()
        corrupt_id = "c" * 64
        corrupt_path = _write_corrupt_journal(repository, corrupt_id)
        assert staged.is_file()

        outcome = reconcile_prepared_exports()

        # The healthy operation reconciled despite the corrupt journal.
        assert len(outcome.reconciled) == 1
        assert outcome.reconciled[0].operation_id == prepared.operation.operation_id
        assert not staged.exists()
        # The corrupt journal is reported by id, with nothing known about its
        # destination, and is left on disk rather than quietly deleted.
        assert len(outcome.failures) == 1
        assert outcome.failures[0].journal_id == corrupt_id
        assert outcome.failures[0].destination is None
        assert outcome.failures[0].reason == "ProfileBundleExportJournalCorruptError"
        assert corrupt_path.is_file()


def test_an_unfinalisable_operation_does_not_starve_the_one_behind_it(tmp_path: Path) -> None:
    # The other isolation half, and the realistic one: a profile deleted after
    # its export crashed leaves a COMPLETED journal whose owed audit event can
    # never be written. That operation must be isolated and reported, keeping
    # its journal for a later retry, while every other operation still recovers.
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _create_profile()
        destination = tmp_path / "portable.json"

        prepared = prepare_profile_export(_request(destination))
        staged = Path(prepared.staged_path)
        repository = ProfileBundleExportJournalRepository()
        stranded = prepared.operation.model_copy(
            update={
                "operation_id": "a" * 64,
                "status": ProfileBundleExportOperationStatus.COMPLETED,
                "profile_id": "00000000-0000-4000-8000-000000000000",
                "destination": str(tmp_path / "stranded.json"),
                "staged_path": str(tmp_path / f"stranded.json.1.abcdef12{_STAGED_TEMP_SUFFIX}"),
                "started_at": prepared.operation.started_at - timedelta(minutes=5),
                "updated_at": prepared.operation.updated_at - timedelta(minutes=5),
            },
        )
        repository.save(stranded)
        # Ordered ahead of the healthy operation, so an aborting sweep would
        # never reach the healthy one.
        assert repository.list()[0].operation_id == stranded.operation_id

        outcome = reconcile_prepared_exports()

        assert len(outcome.reconciled) == 1
        assert outcome.reconciled[0].operation_id == prepared.operation.operation_id
        assert not staged.exists()
        assert len(outcome.failures) == 1
        assert outcome.failures[0].journal_id == stranded.operation_id
        assert outcome.failures[0].destination == stranded.destination
        # Kept for a later retry rather than dropped.
        assert repository.load(stranded.operation_id).operation_id == stranded.operation_id


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
            outcome = reconcile_prepared_exports()

        # A held target lock is a healthy in-flight export: a skip, not a failure.
        assert outcome.reconciled == ()
        assert outcome.failures == ()
        assert staged.exists()
        assert len(repository.prepared()) == 1

        # Once the lock is released, the same operation reconciles normally.
        cleared = reconcile_prepared_exports()
        assert len(cleared.reconciled) == 1
        assert cleared.reconciled[0].operation_id == prepared.operation.operation_id
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


_PREPARE_ONLY_HARNESS = _SETTINGS_PREAMBLE + dedent(
    """
    from cadrumo.application.user_profile import (
        ProfileBundleExportPurpose,
        ProfileBundleExportRequest,
        ProfileBundleExportTransport,
        prepare_profile_export,
    )

    destination = Path(sys.argv[2])
    prepare_profile_export(
        ProfileBundleExportRequest(
            profile_name="subject",
            destination=destination,
            purpose=ProfileBundleExportPurpose.PORTABLE_TRANSFER,
            transport=ProfileBundleExportTransport.CLEARTEXT_LOCAL,
        ),
    )
    os._exit(91)
    """,
)


def _spawn_prepare_child(root: Path, destination: Path) -> subprocess.Popen[str]:
    return subprocess.Popen(  # noqa: S603 - fixed interpreter and repository-owned harness
        [sys.executable, "-c", _PREPARE_ONLY_HARNESS, str(root), str(destination)],
        cwd=Path.cwd(),
        env=_child_env(root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _cleartext_temps(directory: Path) -> list[Path]:
    """Every staged cleartext file, including the hardened writer's inner temp.

    The inner temp does NOT end in the staged suffix, so a plain
    ``*.export-tmp`` sweep is blind to it -- the exact blindness this helper
    exists to remove from the assertions below.
    """
    return sorted(path for path in directory.iterdir() if _STAGED_TEMP_SUFFIX in path.name)


def test_the_prepare_child_really_reaches_staging_when_nothing_blocks_it(tmp_path: Path) -> None:
    # Non-vacuity control for the kill test below: the same harness, unblocked,
    # must genuinely journal AND stage. Without this, a kill test that finds no
    # cleartext proves nothing -- the child might never have got that far.
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        _create_profile()
        dispose_engine()
        destination = tmp_path / "portable.json"

        child = _spawn_prepare_child(storage_root, destination)
        assert child.wait(timeout=120) == _CRASH_EXIT_CODE

        repository = ProfileBundleExportJournalRepository()
        assert len(repository.prepared()) == 1
        assert _cleartext_temps(tmp_path) != []


def test_a_crash_before_the_journal_lands_leaves_no_unreachable_cleartext(tmp_path: Path) -> None:
    # The pre-journal window. Staging used to run BEFORE the journal was
    # written, so a crash in between left a full cleartext bundle on disk with
    # no journal naming it -- unreachable by a journal-driven sweep forever.
    # Holding the journal repository lock widens that window to the whole life
    # of the child, which is then hard-killed inside it.
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        _create_profile()
        dispose_engine()
        destination = tmp_path / "portable.json"
        repository = ProfileBundleExportJournalRepository()
        repository.root.mkdir(parents=True, exist_ok=True)

        with exclusive_file_lock(repository.lock_target):
            child = _spawn_prepare_child(storage_root, destination)
            with contextlib.suppress(subprocess.TimeoutExpired):
                child.wait(timeout=25)
            child.kill()
            child.wait(timeout=60)

        # Nothing was journalled, so nothing may have been staged either.
        assert repository.list() == ()
        assert _cleartext_temps(tmp_path) == []
        assert not destination.exists()


def test_reconcile_removes_the_hardened_writers_own_inner_temp(tmp_path: Path) -> None:
    # The hardened writer stages through an inner sibling and unlinks it in a
    # finally, which a hard kill never runs. That file holds the whole cleartext
    # bundle and does NOT end in the staged suffix, so the orphan guard used to
    # reject it and recovery could never reach it.
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _create_profile()
        destination = tmp_path / "portable.json"

        prepared = prepare_profile_export(_request(destination))
        staged = Path(prepared.staged_path)
        # Exactly what a kill mid-write leaves behind, byte-for-byte.
        inner_temp = staged.with_name(f"{staged.name}.4242.deadbeef.tmp")
        inner_temp.write_bytes(staged.read_bytes())
        assert UserProfilePortableExport.model_validate_json(inner_temp.read_text(encoding="utf-8"))

        outcome = reconcile_prepared_exports()

        assert outcome.failures == ()
        assert len(outcome.reconciled) == 1
        assert not staged.exists()
        assert not inner_temp.exists()
        assert _cleartext_temps(tmp_path) == []


class _RepositoryWithAVanishingJournal(ProfileBundleExportJournalRepository):
    """Reproduce the state a peer's completion leaves mid-scan.

    A peer export finishing between the directory walk and the load deletes its
    own journal, so the walk yields a path whose file is already gone. Only the
    walk is pinned here: the real :meth:`scan` classification, the real
    :meth:`load`, and the real filesystem all run, and the journal really is
    absent rather than being reported absent by a stand-in.
    """

    def __init__(self, *, vanished: Path) -> None:
        super().__init__()
        self._vanished = vanished

    @override
    def _journal_paths(self) -> tuple[Path, ...]:
        return (*super()._journal_paths(), self._vanished)


def test_a_journal_that_vanishes_mid_scan_is_a_skip_not_a_failure(tmp_path: Path) -> None:
    # Reporting a peer's normal completion as a failure would tell the operator
    # an unencrypted file may remain when nothing at all was left behind.
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _create_profile()
        base = ProfileBundleExportJournalRepository()
        prepared = prepare_profile_export(_request(tmp_path / "portable.json"))
        vanished = base.path_for("f" * 64)
        assert not vanished.exists()
        repository = _RepositoryWithAVanishingJournal(vanished=vanished)
        # The walk really does hand scan() a path with no file behind it.
        assert vanished in repository._journal_paths()

        outcome = reconcile_prepared_exports(journal=repository)

        assert outcome.failures == ()
        assert len(outcome.reconciled) == 1
        assert outcome.reconciled[0].operation_id == prepared.operation.operation_id
