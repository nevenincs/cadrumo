"""A locked profile is reported as locked, and an absent record still as absent.

The health projection once collapsed both into one verdict. The active-record
resolver caught the session-required refusal and returned a bare ``None``, and
the projection could only read that null as an absent record, so an operator
who had simply not logged in was told their profile record was missing. The
same lock reached the other entry point as an unreadable record, because the
encrypted workflow state opened first and refused for want of the same session.
Both spellings asserted something false and alarming about intact data.

The lock exists only across a process boundary: a process that publishes the
capsule leaves a live record authority behind it, and that is precisely the
configuration in which the defect cannot appear. The publisher here therefore
runs as a child interpreter that exits before anything is assessed.

Both directions are proven, because correcting one by fabricating the other
would be worse than the original defect. A capsule that is genuinely gone must
keep its own alarming verdict, and a record destroyed underneath a live session
must report unreadable rather than hide behind the benign lock.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from textwrap import dedent

import pytest

from ....core import BucketPointer, write_pointer
from ....core.config import override_settings
from ....tests.subprocess_cli import run_subprocess_cli_harness
from cadrumo.application.user_profile import (
    profile_bind_bucket_session,
    profile_bucket_session_open_resumed,
    profile_close_bucket_session,
)
from ...user_profile import close_active_profile_record_session
from .._profile_health import assess_active_profile_health
from ._locked_profile_support import DEK, PROFILE_ID, PROFILE_LABEL, RECORD_NAMESPACE

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PUBLISHER_SOURCE = dedent(
    """
    from __future__ import annotations

    import sys
    from pathlib import Path

    from cadrumo.application.workflow.tests._locked_profile_support import publish_capsule_and_pointer

    publish_capsule_and_pointer(Path(sys.argv[1]))
    """,
)
"""Child program: publish the capsule, point the selector at it, then exit."""


@pytest.fixture(autouse=True)
def _no_inherited_session() -> Iterator[None]:
    """Guarantee each case starts and ends with no authority latched in-process.

    The record authority is process-local and installed on first successful
    derivation, so an unlocked case leaking its authority into a later case
    would let a locked profile read as unlocked -- the assertion would then
    describe test ordering rather than the code.
    """
    close_active_profile_record_session()
    profile_close_bucket_session()
    yield
    close_active_profile_record_session()
    profile_close_bucket_session()


def _publish_in_a_separate_process(root: Path) -> None:
    """Publish the capsule in a genuinely fresh interpreter, then let it exit."""
    completed = run_subprocess_cli_harness(
        _PUBLISHER_SOURCE,
        [str(root)],
        env_strip_prefixes=("AEAT_", "PYTEST_", "CADRUMO_"),
    )
    assert completed.returncode == 0, f"publisher process failed:\n{completed.stdout}\n{completed.stderr}"


def _bind_real_custody_session(root: Path) -> None:
    """Authenticate this process against the published capsule for real."""
    instant = datetime.now(UTC)
    profile_bind_bucket_session(
        profile_bucket_session_open_resumed(
            bucket_id=PROFILE_ID,
            dek=DEK,
            idle_minutes=15,
            opened_at=instant,
            idle_deadline=instant + timedelta(minutes=15),
            absolute_deadline=instant + timedelta(hours=4),
            storage_root=root,
        ),
    )


def _capsule_database(root: Path) -> Path:
    databases = sorted(root.rglob("cadrumo.db"))
    assert len(databases) == 1, f"expected exactly one published capsule database, found {databases}"
    return databases[0]


def _destroy_the_profile_record_row(root: Path) -> None:
    """Delete the one current-record row, leaving the rest of the capsule intact."""
    connection = sqlite3.connect(_capsule_database(root))
    try:
        deleted = connection.execute(
            "DELETE FROM secure_objects WHERE namespace = ?",
            (RECORD_NAMESPACE,),
        ).rowcount
        connection.commit()
    finally:
        connection.close()
    assert deleted == 1, f"expected to destroy exactly one record row, destroyed {deleted}"


def test_a_locked_profile_reports_a_lock_and_routes_the_operator_to_login(tmp_path: Path) -> None:
    """The record is intact and unread; the operator is told to log in, not that it is gone."""
    _publish_in_a_separate_process(tmp_path)

    with override_settings(cadrumo_local_storage_root=tmp_path, cadrumo_active_profile=None):
        health = assess_active_profile_health()

    assert health.status == "profile_locked"
    assert health.status != "missing_profile_record"
    assert health.status != "profile_record_unreadable"
    assert health.registered_bucket is True
    assert health.active_profile_label == PROFILE_LABEL
    # A lock is not a broken pointer, so it must not offer to clear one.
    assert health.repairable_by_clearing_pointer is False

    verdict = health.precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == "profile.session.logged_in"
    assert verdict.action is not None
    assert verdict.action.action_id == "operator.profile.login"
    # The remedy names WHICH profile to log into, from the capsule's own label.
    assert {binding.argument_name: binding.value for binding in verdict.argument_bindings} == {"name": PROFILE_LABEL}
    assert verdict.missing_argument_names == ()


def test_a_locked_profile_reports_the_same_lock_when_the_caller_supplies_state(tmp_path: Path) -> None:
    """Both entry points agree, so the verdict cannot depend on who called it.

    A supplied state skips the encrypted workflow-state load; without one that
    load runs first and is refused by the same absent session. The two paths
    once produced different false diagnostics for one profile.
    """
    from .._models import WorkflowState

    _publish_in_a_separate_process(tmp_path)

    with override_settings(cadrumo_local_storage_root=tmp_path, cadrumo_active_profile=None):
        supplied = assess_active_profile_health(WorkflowState())
        loaded = assess_active_profile_health()

    assert supplied.status == "profile_locked"
    assert loaded.status == "profile_locked"


def test_an_unlocked_profile_is_read_through_to_ready(tmp_path: Path) -> None:
    """The control: with a real session the lock verdict must not fire at all.

    Without this the locked assertions above would hold for a projection that
    reported every profile locked, which is the inverse defect.
    """
    _publish_in_a_separate_process(tmp_path)
    _bind_real_custody_session(tmp_path)

    with override_settings(cadrumo_local_storage_root=tmp_path, cadrumo_active_profile=None):
        health = assess_active_profile_health()

    assert health.status == "ready"
    assert health.profile_record_present is True
    assert health.precondition_verdict is None


def test_a_selector_with_no_committed_capsule_is_not_softened_into_a_lock(tmp_path: Path) -> None:
    """Genuine absence keeps its own alarming verdict; nothing is hidden behind the lock."""
    write_pointer(tmp_path, BucketPointer(bucket_id=PROFILE_ID, schema_version=1))

    with override_settings(cadrumo_local_storage_root=tmp_path, cadrumo_active_profile=None):
        health = assess_active_profile_health()

    assert health.status == "dangling_pointer"
    assert health.status != "profile_locked"
    assert health.repairable_by_clearing_pointer is True


def test_a_record_destroyed_under_a_live_session_reports_unreadable_not_locked(tmp_path: Path) -> None:
    """A session exists, so the absent row is knowable and must be reported as such."""
    _publish_in_a_separate_process(tmp_path)
    _bind_real_custody_session(tmp_path)
    _destroy_the_profile_record_row(tmp_path)

    with override_settings(cadrumo_local_storage_root=tmp_path, cadrumo_active_profile=None):
        health = assess_active_profile_health()

    assert health.status == "profile_record_unreadable"
    assert health.status != "profile_locked"
    assert health.profile_record_present is False
    assert health.profile_record_error != ""
