"""A retried profile write lands one audit event, not two.

The workflow-state update is compare-and-swap: on a revision conflict it
re-runs its callback from fresh state. The callback that writes profile facts
also emits a bucket event, and that event's id is derived from the instant it
carries -- so a retry that read the clock afresh minted a second id, and one
logical edit left two immutable rows in the audit catalogue.

These drive a REAL conflict: a competing writer bumps the workflow-state
revision between the callback's read and its save, so the retry is the
substrate's own, not a hand-rolled second call.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ....domain.user_profile import UserProfileFact
from ....tests.secure_sql import isolated_profile_storage_root
from ...workflow import WorkflowState, workflow_state_repository
from .._orchestration import set_active_field
from .._registration import register_profile_with_credentials

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_PASSPHRASE = "correct horse battery staple"  # noqa: S105 - synthetic test fixture
_EDITED_PATH = "identity.name"


@pytest.fixture(autouse=True)
def _storage_root(tmp_path: Path):
    with isolated_profile_storage_root(tmp_path=tmp_path):
        yield


def _seed() -> None:
    """Create and unlock one profile, so profile-bound storage is reachable."""
    register_profile_with_credentials(label="Retry subject", passphrase=_PASSPHRASE)


def _competing_instant():
    """An instant distinct from whatever the state currently holds."""
    from datetime import UTC, datetime

    return datetime.now(UTC)


def _edit_events() -> tuple[object, ...]:
    """Every catalogue entry describing a profile-value change."""
    from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository

    catalogue = BucketEventHistoryRepository().load()
    # Keyed by event id, which is the content-addressing a retry is supposed
    # to collapse onto: a stable id overwrites its own entry, a re-minted one
    # adds a second.
    return tuple(event for event in catalogue.events.values() if "values" in str(event.event_type))


def _drive_edit_with_one_conflict(value: str) -> int:
    """Apply one field, forcing exactly one real CAS conflict. Returns attempts."""
    repository = workflow_state_repository()
    attempts = {"n": 0}

    def _callback(state: WorkflowState) -> WorkflowState:
        attempts["n"] += 1
        if attempts["n"] == 1:
            # Bump the workflow-state revision out of band, so the save this
            # attempt is about to make loses the compare-and-swap. A second
            # repository handle is a genuinely competing writer -- the retry
            # below is the substrate's, not ours.
            #
            # The change has to be a real one: an update whose callback returns
            # the state unchanged short-circuits before writing, so it would
            # never move the revision. Stamping ``updated_at`` moves it without
            # emitting a bucket event, which keeps the audit count this test
            # reads attributable to the edit alone.
            workflow_state_repository().update(
                lambda other: other.model_copy(update={"updated_at": _competing_instant()}),
            )
        return set_active_field(state, UserProfileFact(path=_EDITED_PATH, value=value))

    repository.update(_callback)
    return attempts["n"]


def test_a_retried_edit_lands_one_audit_event() -> None:
    """The conflict re-runs the callback, and the catalogue still gains one row."""
    _seed()
    before = len(_edit_events())

    attempts = _drive_edit_with_one_conflict("Retried once")

    assert attempts >= 2, "the callback never re-ran, so no retry was exercised"
    after = _edit_events()
    gained = len(after) - before
    assert gained == 1, f"one logical edit left {gained} audit rows; a retry duplicated the event"


def test_the_conflict_probe_actually_conflicts() -> None:
    """Positive control: without the competing writer the callback runs once.

    If this ever ran twice the sibling test would pass for the wrong reason --
    it would be asserting over a path that never retried.
    """
    _seed()
    repository = workflow_state_repository()
    attempts = {"n": 0}

    def _callback(state: WorkflowState) -> WorkflowState:
        attempts["n"] += 1
        return set_active_field(state, UserProfileFact(path=_EDITED_PATH, value="Uncontended"))

    repository.update(_callback)
    assert attempts["n"] == 1, "an uncontended update retried; the sibling test proves nothing"
