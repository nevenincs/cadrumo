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

from collections.abc import Callable, Iterator, Mapping, Sequence
from pathlib import Path

import pytest
import typer

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....core.flows import CheckpointAvailability, FlowMode
from ....domain.buckets import BucketEventType
from ....domain.user_profile import UserProfileStatus, new_profile_id
from ....tests.secure_sql import isolated_profile_storage_root
from ...flows import (
    CheckpointStore,
    FlowCheckpointError,
    FlowDefinition,
    FlowState,
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
    InteractiveFlowRunner,
    _resolve_profile_id_for_mode,
    build_wizard_command,
)
from .._persistence import WizardPersistMode
from ._support import scripted_run_over_setup_definition
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
    return sum(
        1 for event in catalogue.events.values() if event.event_type is BucketEventType.PROFILE_SETUP_COMPLETED
    )


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


# ── command wiring: save-exit (a), submit completion (d), resume (e), discard (f)


def _invoke_interactive(mode: WizardPersistMode, runner: InteractiveFlowRunner, args: Sequence[str]) -> None:
    command = build_wizard_command(SETUP_FLOW, mode=mode, interactive_flow_runner=runner)
    app = typer.Typer()
    app.command()(command)
    typer.main.get_command(app).main(args=list(args), standalone_mode=False)


def _submit_runner(tokens: Sequence[str]):
    """Runner that walks the flow to a submitted state (the operator submits)."""

    def _runner(
        definition: FlowDefinition,
        *,
        mode: FlowMode,
        registered_values: Mapping[str, str] | None = None,
        on_language_activated: Callable[[str, str], bool] | None = None,
        checkpoint_store: CheckpointStore | None = None,
    ) -> FlowState:
        del registered_values, on_language_activated, checkpoint_store
        state, _projection = scripted_run_over_setup_definition(definition, tokens, mode=mode)
        return state

    return _runner


def _save_exit_runner(tokens: Sequence[str]):
    """Runner that answers the flow then saves-and-exits through the store.

    Mirrors a frontend save-and-exit: the engine reaches a state and the
    checkpoint port persists it, exactly as ``LineFlowFrontend`` does when the
    operator picks save-and-exit at review instead of submit.
    """

    def _runner(
        definition: FlowDefinition,
        *,
        mode: FlowMode,
        registered_values: Mapping[str, str] | None = None,
        on_language_activated: Callable[[str, str], bool] | None = None,
        checkpoint_store: CheckpointStore | None = None,
    ) -> FlowState:
        del registered_values, on_language_activated
        state, _projection = scripted_run_over_setup_definition(definition, tokens, mode=mode)
        assert checkpoint_store is not None
        save_checkpoint(definition, state, checkpoint_store)
        return state

    return _runner


def test_interactive_create_save_exit_leaves_the_profile_setup_incomplete(_backend: Path) -> None:
    tokens = list(_scripted_answers_for_individual_declaration())
    _invoke_interactive("create", _save_exit_runner(tokens), ["operator"])

    pointer = read_profile_bucket("operator")
    assert pointer is not None
    assert pointer.status is UserProfileStatus.SETUP_INCOMPLETE
    # The answered facts persisted, and no completion event fired.
    assert _record_values(pointer.bucket_id)["identity.tax_id"] == _TAX_ID
    assert _setup_completed_event_count(pointer.bucket_id) == 0


def test_interactive_create_submit_completes_the_setup_once(_backend: Path) -> None:
    tokens = list(_scripted_answers_for_individual_declaration())
    _invoke_interactive("create", _submit_runner(tokens), ["operator"])

    pointer = read_profile_bucket("operator")
    assert pointer is not None
    assert pointer.status is UserProfileStatus.ACTIVE
    assert _record_values(pointer.bucket_id)["identity.tax_id"] == _TAX_ID
    assert _setup_completed_event_count(pointer.bucket_id) == 1


def test_second_create_for_an_incomplete_label_resumes_never_duplicates(_backend: Path) -> None:
    tokens = list(_scripted_answers_for_individual_declaration())
    _invoke_interactive("create", _save_exit_runner(tokens), ["operator"])
    pointer = read_profile_bucket("operator")
    assert pointer is not None

    # A second create for the same incomplete label resolves to the SAME
    # bucket (resume) rather than refusing as a duplicate label.
    resolved = _resolve_profile_id_for_mode(SETUP_FLOW, "create", "operator")
    assert resolved == pointer.bucket_id
    # And the prior answers are offered back for the resumed walk.
    assert (_store(resolved).load(SETUP_FLOW.id) or {})["tax-id"] == _TAX_ID


def test_second_create_submit_after_resume_completes_the_profile(_backend: Path) -> None:
    tokens = list(_scripted_answers_for_individual_declaration())
    _invoke_interactive("create", _save_exit_runner(tokens), ["operator"])
    # Re-enter the same label and submit: the incomplete profile completes.
    _invoke_interactive("create", _submit_runner(tokens), ["operator"])

    pointer = read_profile_bucket("operator")
    assert pointer is not None
    assert pointer.status is UserProfileStatus.ACTIVE
    assert _setup_completed_event_count(pointer.bucket_id) == 1


def test_discard_then_fresh_create_starts_clean(_backend: Path) -> None:
    tokens = list(_scripted_answers_for_individual_declaration())
    _invoke_interactive("create", _save_exit_runner(tokens), ["operator"])
    first = read_profile_bucket("operator")
    assert first is not None

    _store(first.bucket_id).discard(SETUP_FLOW.id)
    assert read_profile_bucket("operator") is None

    # A fresh create for the freed label mints a brand-new identity.
    resolved = _resolve_profile_id_for_mode(SETUP_FLOW, "create", "operator")
    assert resolved != first.bucket_id
