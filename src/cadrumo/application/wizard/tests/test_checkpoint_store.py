"""Create-mode facts-as-checkpoint: real store, resume projection, command wiring.

Every scenario drives the real profile lifecycle authority through an
isolated storage root — the facts genuinely persist to the encrypted
secure-object store and are read back through the real repository, never a
mock. The checkpoint IS those facts: save mints the profile early in
``SETUP_INCOMPLETE`` state, load offers a resume only while incomplete, the
submit path completes it (flipping ``ACTIVE`` and emitting
``PROFILE_SETUP_COMPLETED``), and discard erases it through the existing
lifecycle arms.

Structural assertions read lifecycle status, ``PageStatus`` members, and
persisted fact paths; no localized prose is asserted.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....core.flows import CheckpointAvailability, FlowMode
from ....domain.buckets import BucketEventType
from ....domain.user_profile import UserProfileStatus, new_profile_id
from ....tests.secure_sql import isolated_profile_storage_root
from ...flows import (
    FlowCheckpointError,
    checkpoint_available,
    flow_definition_from_wizard_flow,
    resume_flow,
    run_scripted_flow,
    save_checkpoint,
    start_flow,
)
from ...user_profile import profile_storage_session, record_to_path_values
from ...workflow import read_profile_bucket, workflow_state_repository
from .. import ProfileFactsCheckpointStore
from .._catalogue import SETUP_FLOW
from .._commands import (
    _SETUP_CHECKPOINT,
)
from .test_setup_runtime import _scripted_answers_for_individual_declaration

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_TAX_ID = "12345678Z"


@pytest.fixture
def _backend(tmp_path: Path) -> Iterator[Path]:
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        yield storage_root


def _definition():
    """The bridged setup FlowDefinition carrying the setup checkpoint declaration."""
    return flow_definition_from_wizard_flow(SETUP_FLOW, checkpoint=dict(_SETUP_CHECKPOINT))


def _committed_answers() -> dict[str, str]:
    """Page-keyed committed answers from a full scripted individual-declaration walk."""
    definition = _definition()
    tokens = list(_scripted_answers_for_individual_declaration())
    state, _projection = run_scripted_flow(definition, tokens, mode=FlowMode.CREATE)
    return dict(state.answers)


def _store(profile_id: str, profile_name: str = "operator") -> ProfileFactsCheckpointStore:
    return ProfileFactsCheckpointStore(SETUP_FLOW, profile_id=profile_id, profile_name=profile_name)


def _record_values(bucket_id: str) -> dict[str, str]:
    with profile_storage_session(bucket_id):
        record = workflow_state_repository().load().active_profile_record()
    return record_to_path_values(record)


def _setup_completed_event_count(bucket_id: str) -> int:
    with profile_storage_session(bucket_id):
        catalogue = BucketEventHistoryRepository().load()
    return sum(1 for event in catalogue.events.values() if event.event_type is BucketEventType.PROFILE_SETUP_COMPLETED)


# ── declaration (g) ────────────────────────────────────────────────


def test_setup_checkpoint_declaration_create_available_modify_unavailable() -> None:
    definition = _definition()
    assert checkpoint_available(definition, FlowMode.CREATE) is True
    assert checkpoint_available(definition, FlowMode.MODIFY) is False
    assert _SETUP_CHECKPOINT[FlowMode.CREATE] is CheckpointAvailability.AVAILABLE
    assert _SETUP_CHECKPOINT[FlowMode.MODIFY] is CheckpointAvailability.UNAVAILABLE


def test_modify_mode_save_refuses_loudly() -> None:
    """MODIFY declares checkpointing UNAVAILABLE: a save must refuse, never drop."""
    definition = _definition()
    state = start_flow(definition, mode=FlowMode.MODIFY)
    store = _store(new_profile_id())
    with pytest.raises(FlowCheckpointError) as excinfo:
        save_checkpoint(definition, state, store)
    assert excinfo.value.translated_message == "application.flows.errors.checkpoint_unavailable_mode"


# ── store save / load / discard ────────────────────────────────────


def test_store_save_mints_setup_incomplete_and_persists_the_answered_facts(_backend: Path) -> None:
    profile_id = new_profile_id()
    _store(profile_id).save(SETUP_FLOW.id, _committed_answers())

    pointer = read_profile_bucket("operator")
    assert pointer is not None
    assert pointer.bucket_id == profile_id
    assert pointer.status is UserProfileStatus.SETUP_INCOMPLETE
    # The answered facts reached the encrypted record — read back, not asserted
    # against the store's own echo.
    assert _record_values(profile_id)["identity.tax_id"] == _TAX_ID


def test_store_load_offers_resume_only_while_incomplete(_backend: Path) -> None:
    profile_id = new_profile_id()
    store = _store(profile_id)
    store.save(SETUP_FLOW.id, _committed_answers())

    resumed = store.load(SETUP_FLOW.id)
    assert resumed is not None
    assert resumed["tax-id"] == _TAX_ID

    # Completing the setup ends resume-eligibility (the completion discard).
    from ...user_profile import complete_setup_with_lifecycle_span

    complete_setup_with_lifecycle_span(profile_id)
    assert store.load(SETUP_FLOW.id) is None


def test_store_load_returns_none_for_an_unminted_profile(_backend: Path) -> None:
    assert _store(new_profile_id()).load(SETUP_FLOW.id) is None


def test_store_discard_erases_the_incomplete_profile(_backend: Path) -> None:
    profile_id = new_profile_id()
    store = _store(profile_id)
    store.save(SETUP_FLOW.id, _committed_answers())
    assert read_profile_bucket("operator") is not None

    store.discard(SETUP_FLOW.id)
    assert read_profile_bucket("operator") is None


# ── resume projection routes through resume_flow (b / c) ────────────


def test_resume_projection_recovers_prior_answers_through_resume_flow(_backend: Path) -> None:
    profile_id = new_profile_id()
    store = _store(profile_id)
    store.save(SETUP_FLOW.id, _committed_answers())

    resumed = store.load(SETUP_FLOW.id)
    assert resumed is not None
    definition = _definition()
    state = resume_flow(definition, resumed, mode=FlowMode.CREATE)

    # The prior answers re-validate against the current definition and commit;
    # a fully-answered resume leaves no first-unanswered cursor.
    assert state.answers["tax-id"] == _TAX_ID
    assert state.answers["output-language"] == "en"


def test_resume_flow_carries_a_definition_drift_orphan_as_stale(_backend: Path) -> None:
    """A persisted answer whose page the current definition no longer declares
    lands stale on the resume projection, never silently coerced — the drift
    detection the resume path routes through."""
    profile_id = new_profile_id()
    store = _store(profile_id)
    store.save(SETUP_FLOW.id, _committed_answers())

    resumed = dict(store.load(SETUP_FLOW.id) or {})
    resumed["a-retired-page-id"] = "orphan-value"
    state = resume_flow(_definition(), resumed, mode=FlowMode.CREATE)

    assert "a-retired-page-id" in state.stale
    assert "a-retired-page-id" not in state.answers


# The command-wiring tests that used to live here drove the retired
# interactive walk: save-and-exit, submit completion, resume, discard. The
# walk is gone, so they went with it. What remains is the store itself,
# which the profile manager's own creation path still mints through.
