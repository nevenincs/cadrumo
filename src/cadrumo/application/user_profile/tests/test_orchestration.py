"""Tests for the WorkflowState-aware user-profile orchestration helpers."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

import pytest

from ....adapters.persistence.storage import (
    LockAcquisitionError,
    activate_master_key_provider,
    get_master_key_provider,
    has_active_bucket_session,
)
from ....adapters.persistence.storage.bucket import BucketLockedError
from ....adapters.persistence.storage.master_key import current_active_bucket_session
from ....core import BucketPointer, capture_pointer, read_pointer, resolve_active_bucket_id
from ....core.config import load_settings, override_settings
from ....core.resources import resources
from ....domain.user_profile import (
    ProfileNotFoundError,
    ProfileSchemaDefinition,
    UserProfileFact,
    UserProfileStatus,
)
from ....tests.secure_sql import isolated_profile_storage_root
from ...workflow import (
    WorkflowState,
    read_profile_bucket,
    read_profile_bucket_by_id,
)
from .._orchestration import (
    ProfileLogoutOverrideError,
    logout_active_profile,
    profile_create_storage_span,
    register_active_profile,
    remove_active_profile,
    select_profile,
    set_active_field,
    set_active_fields,
)
from .._profile_pointer_transaction import active_profile_pointer_transaction

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_DEFAULT_PROFILE_ID = "1a1a1a1a-1a1a-4a1a-8a1a-1a1a1a1a1a1a"
_MISSING_PROFILE_ID = "2b2b2b2b-2b2b-4b2b-8b2b-2b2b2b2b2b2b"


# The application-level conftest already redirects
# Settings.cadrumo_local_storage_root to tmp_path for every test, so the
# orchestration's pointer-file write stays inside the sandbox without
# any per-file fixture wiring here.


@pytest.fixture(autouse=True)
def _storage_root(tmp_path: Path):
    with isolated_profile_storage_root(tmp_path=tmp_path):
        yield


@pytest.fixture(scope="module")
def schema() -> ProfileSchemaDefinition:
    return resources().user_profile_schema.singleton


def _all_required_facts(schema: ProfileSchemaDefinition) -> tuple[UserProfileFact, ...]:
    facts: list[UserProfileFact] = []
    for section in schema.sections:
        if section.repeatable:
            continue
        for field in section.fields:
            if field.required:
                facts.append(UserProfileFact(path=f"{section.key}.{field.key}", value="placeholder"))
    return tuple(facts)


def test_register_active_profile_threads_state_and_emits_events(schema: ProfileSchemaDefinition) -> None:
    state = WorkflowState()
    with profile_create_storage_span(_DEFAULT_PROFILE_ID) as routing_profile_id:
        updated = register_active_profile(
            state,
            profile_id=_DEFAULT_PROFILE_ID,
            display_name="Default operator",
            facts=_all_required_facts(schema),
            schema=schema,
            routing_profile_id=routing_profile_id,
        )
    assert resolve_active_bucket_id() == _DEFAULT_PROFILE_ID
    # The bucket directory is named by the UUID identity; its manifest carries
    # the decoupled operator label.
    by_id = read_profile_bucket_by_id(_DEFAULT_PROFILE_ID)
    assert by_id is not None
    assert by_id.bucket_id == _DEFAULT_PROFILE_ID
    assert by_id.label == "Default operator"
    # The operator-facing label resolves back to the same bucket.
    assert read_profile_bucket("Default operator") == by_id
    actions = tuple(event.action for event in updated.bucket_events)
    assert actions == ("profile.created", "profile.selected", "profile.values.updated")


def test_select_profile_refuses_when_missing(schema: ProfileSchemaDefinition) -> None:
    state = WorkflowState()
    with pytest.raises(ProfileNotFoundError):
        select_profile(state, profile_id=_MISSING_PROFILE_ID, schema=schema)


def test_set_active_field_appends_workflow_event(schema: ProfileSchemaDefinition) -> None:
    state = WorkflowState()
    with profile_create_storage_span(_DEFAULT_PROFILE_ID) as routing_profile_id:
        state = register_active_profile(
            state,
            profile_id=_DEFAULT_PROFILE_ID,
            display_name="Default operator",
            facts=_all_required_facts(schema),
            schema=schema,
            routing_profile_id=routing_profile_id,
        )
        state = set_active_field(
            state,
            UserProfileFact(path="identity.email", value="op@example.test"),
            schema=schema,
        )
        last_event = state.bucket_events[-1]
        assert last_event.action == "profile.values.updated"
        assert last_event.object_id == "identity.email"

        state = set_active_field(
            state,
            UserProfileFact(path="identity.email", value=None),
            schema=schema,
        )
        cleared = state.bucket_events[-1]
        assert cleared.action == "profile.values.cleared"


def test_set_active_fields_bulk_threads_each_workflow_event(schema: ProfileSchemaDefinition) -> None:
    state = WorkflowState()
    with profile_create_storage_span(_DEFAULT_PROFILE_ID) as routing_profile_id:
        state = register_active_profile(
            state,
            profile_id=_DEFAULT_PROFILE_ID,
            display_name="Default operator",
            facts=_all_required_facts(schema),
            schema=schema,
            routing_profile_id=routing_profile_id,
        )
        bulk_facts = (
            UserProfileFact(path="identity.email", value="a@example.test"),
            UserProfileFact(path="identity.notes", value="freelance"),
        )
        state = set_active_fields(state, bulk_facts, schema=schema)
        bulk_events = [e for e in state.bucket_events if e.object_id in {"identity.email", "identity.notes"}]
        assert len(bulk_events) == 2


def test_read_active_profile_returns_record(schema: ProfileSchemaDefinition) -> None:
    state = WorkflowState()
    with profile_create_storage_span(_DEFAULT_PROFILE_ID) as routing_profile_id:
        state = register_active_profile(
            state,
            profile_id=_DEFAULT_PROFILE_ID,
            display_name="Default operator",
            facts=_all_required_facts(schema),
            schema=schema,
            routing_profile_id=routing_profile_id,
        )
        record = state.active_profile_record(schema=schema)
        assert record is not None
        assert record.profile_id == _DEFAULT_PROFILE_ID
        assert record.status is UserProfileStatus.ACTIVE


def test_read_active_profile_logs_missing_selected_record(
    caplog: pytest.LogCaptureFixture,
    schema: ProfileSchemaDefinition,
) -> None:
    """A torn active pointer degrades to no record with debug evidence."""

    with profile_create_storage_span(_MISSING_PROFILE_ID):
        caplog.set_level(logging.DEBUG, logger="cadrumo.application.workflow._models")

        record = WorkflowState().active_profile_record(schema=schema)

    assert record is None
    assert "active profile record resolution returned no profile record" in caplog.text


def test_remove_active_profile_tombstones_and_clears_pointer(schema: ProfileSchemaDefinition) -> None:
    state = WorkflowState()
    with profile_create_storage_span(_DEFAULT_PROFILE_ID) as routing_profile_id:
        state = register_active_profile(
            state,
            profile_id=_DEFAULT_PROFILE_ID,
            display_name="Default operator",
            facts=_all_required_facts(schema),
            schema=schema,
            routing_profile_id=routing_profile_id,
        )
        state = remove_active_profile(state, schema=schema)
    from ....core import resolve_active_bucket_id

    assert resolve_active_bucket_id() is None
    assert state.bucket_events[-1].action == "profile.tombstoned"


def test_logout_closes_real_storage_clears_pointer_releases_lock_and_is_idempotent(
    schema: ProfileSchemaDefinition,
) -> None:
    state = WorkflowState()
    with profile_create_storage_span(_DEFAULT_PROFILE_ID) as routing_profile_id:
        register_active_profile(
            state,
            profile_id=_DEFAULT_PROFILE_ID,
            display_name="Default operator",
            facts=_all_required_facts(schema),
            schema=schema,
            routing_profile_id=routing_profile_id,
        )

    settings = load_settings()
    storage_root = settings.cadrumo_local_storage_root
    assert read_pointer(storage_root) == BucketPointer(bucket_id=_DEFAULT_PROFILE_ID, schema_version=1)
    pointer_before_logout = capture_pointer(storage_root)
    assert pointer_before_logout is not None

    provider = get_master_key_provider()
    with activate_master_key_provider(provider):
        session = current_active_bucket_session()
        assert session is not None
        assert session.bucket_id == _DEFAULT_PROFILE_ID
        engine = session.acquire_engine(settings)
        with engine.connect() as connection:
            assert connection.exec_driver_sql("SELECT 1").scalar_one() == 1
        pool_before_logout = engine.pool

        lock_acquired = Event()
        release_lock = Event()

        def hold_pointer_transaction() -> None:
            with active_profile_pointer_transaction(storage_root):
                lock_acquired.set()
                if not release_lock.wait(timeout=10.0):
                    raise TimeoutError("pointer transaction release handshake timed out")

        def read_pointer_under_fresh_transaction() -> BucketPointer | None:
            with active_profile_pointer_transaction(storage_root) as transaction:
                return transaction.read()

        with ThreadPoolExecutor(max_workers=1) as executor:
            holder = executor.submit(hold_pointer_transaction)
            try:
                assert lock_acquired.wait(timeout=10.0), "worker did not acquire the pointer transaction"
                with (
                    override_settings(
                        cadrumo_active_profile=None,
                        cadrumo_file_lock_timeout_s=0.05,
                        cadrumo_file_lock_retry_backoff_s=0.01,
                    ),
                    pytest.raises(LockAcquisitionError),
                ):
                    logout_active_profile()

                assert capture_pointer(storage_root) == pointer_before_logout
                assert current_active_bucket_session() is session
                assert has_active_bucket_session() is True
                assert session.sealed is False
                assert engine.pool is pool_before_logout
                with engine.connect() as connection:
                    assert connection.exec_driver_sql("SELECT 1").scalar_one() == 1
            finally:
                release_lock.set()
                holder.result(timeout=10.0)

            assert logout_active_profile() == _DEFAULT_PROFILE_ID
            released_pointer = executor.submit(read_pointer_under_fresh_transaction).result(timeout=10.0)

        assert current_active_bucket_session() is None
        assert has_active_bucket_session() is False
        assert session.sealed is True
        assert engine.pool is not pool_before_logout
        with pytest.raises(BucketLockedError):
            session.acquire_engine(settings)
        assert released_pointer is None

    assert resolve_active_bucket_id() is None
    assert logout_active_profile() is None
    assert read_pointer(storage_root) is None
    assert current_active_bucket_session() is None
    assert has_active_bucket_session() is False


def test_logout_refuses_explicit_profile_override_without_mutating_session_or_pointer(
    schema: ProfileSchemaDefinition,
) -> None:
    state = WorkflowState()
    with profile_create_storage_span(_DEFAULT_PROFILE_ID) as routing_profile_id:
        register_active_profile(
            state,
            profile_id=_DEFAULT_PROFILE_ID,
            display_name="Default operator",
            facts=_all_required_facts(schema),
            schema=schema,
            routing_profile_id=routing_profile_id,
        )

    storage_root = load_settings().cadrumo_local_storage_root
    pointer_before = capture_pointer(storage_root)
    assert pointer_before is not None

    provider = get_master_key_provider()
    with activate_master_key_provider(provider):
        session = current_active_bucket_session()
        assert session is not None
        assert session.bucket_id == _DEFAULT_PROFILE_ID
        with (
            override_settings(cadrumo_active_profile=_MISSING_PROFILE_ID),
            pytest.raises(ProfileLogoutOverrideError) as exc_info,
        ):
            assert resolve_active_bucket_id() == _MISSING_PROFILE_ID
            logout_active_profile()

        assert exc_info.value.translated_message == "errors.refused.refused_profile_logout_override"
        assert exc_info.value.suggestion is None
        assert capture_pointer(storage_root) == pointer_before
        assert read_pointer(storage_root) == BucketPointer(bucket_id=_DEFAULT_PROFILE_ID, schema_version=1)
        assert current_active_bucket_session() is session
        assert has_active_bucket_session() is True
        assert session.sealed is False
