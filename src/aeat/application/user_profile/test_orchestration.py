"""Tests for the WorkflowState-aware user-profile orchestration helpers."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ...adapters.persistence.storage import EphemeralMasterKeyProvider, override_master_key_provider
from ...adapters.persistence.storage.sql import SecureObjectRepository, create_engine_from_settings
from ...adapters.persistence.storage.sql._orm import Base
from ...application.workflow._models import resolve_active_bucket_id
from ...core.config import Settings
from ...core.resources import resources
from ...domain.user_profile import (
    ProfileNotFoundError,
    UserProfileFact,
    UserProfileStatus,
)
from ..workflow._models import WorkflowState
from ._orchestration import (
    read_active_profile,
    register_active_profile,
    remove_active_profile,
    select_profile,
    set_active_field,
    set_active_fields,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


# The application-level conftest already redirects
# Settings.aeat_local_storage_root to tmp_path for every test, so the
# orchestration's pointer-file write stays inside the sandbox without
# any per-file fixture wiring here.


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    provider = EphemeralMasterKeyProvider()
    override_master_key_provider(provider)
    engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{(tmp_path / 'aeat.db').as_posix()}"))
    Base.metadata.create_all(engine)
    try:
        yield SecureObjectRepository(engine=engine)
    finally:
        engine.dispose()
        override_master_key_provider(None)


@pytest.fixture(scope="module")
def schema():
    return resources().user_profile_schema.singleton


def _all_required_facts(schema) -> tuple[UserProfileFact, ...]:
    facts: list[UserProfileFact] = []
    for section in schema.sections:
        if section.repeatable:
            continue
        for field in section.fields:
            if field.required:
                facts.append(UserProfileFact(path=f"{section.key}.{field.key}", value="placeholder"))
    return tuple(facts)


def test_register_active_profile_threads_state_and_emits_events(secure_objects, schema) -> None:
    state = WorkflowState()
    updated = register_active_profile(
        state,
        profile_id="default",
        display_name="Default operator",
        facts=_all_required_facts(schema),
        secure_objects=secure_objects,
        schema=schema,
    )
    assert resolve_active_bucket_id() == "default"
    assert "default" in updated.profiles
    actions = tuple(event.action for event in updated.bucket_events)
    assert actions == ("profile.created", "profile.selected", "profile.values.updated")


def test_select_profile_refuses_when_missing(secure_objects, schema) -> None:
    state = WorkflowState()
    with pytest.raises(ProfileNotFoundError):
        select_profile(state, profile_id="ghost", secure_objects=secure_objects, schema=schema)


def test_set_active_field_appends_workflow_event(secure_objects, schema) -> None:
    state = WorkflowState()
    state = register_active_profile(
        state,
        profile_id="default",
        display_name="Default operator",
        facts=_all_required_facts(schema),
        secure_objects=secure_objects,
        schema=schema,
    )
    state = set_active_field(
        state,
        UserProfileFact(path="identity.email", value="op@example.test"),
        secure_objects=secure_objects,
        schema=schema,
    )
    last_event = state.bucket_events[-1]
    assert last_event.action == "profile.values.updated"
    assert last_event.object_id == "identity.email"

    state = set_active_field(
        state,
        UserProfileFact(path="identity.email", value=None),
        secure_objects=secure_objects,
        schema=schema,
    )
    cleared = state.bucket_events[-1]
    assert cleared.action == "profile.values.cleared"


def test_set_active_fields_bulk_threads_each_workflow_event(secure_objects, schema) -> None:
    state = WorkflowState()
    state = register_active_profile(
        state,
        profile_id="default",
        display_name="Default operator",
        facts=_all_required_facts(schema),
        secure_objects=secure_objects,
        schema=schema,
    )
    bulk_facts = (
        UserProfileFact(path="identity.email", value="a@example.test"),
        UserProfileFact(path="identity.notes", value="freelance"),
    )
    state = set_active_fields(state, bulk_facts, secure_objects=secure_objects, schema=schema)
    bulk_events = [e for e in state.bucket_events if e.object_id in {"identity.email", "identity.notes"}]
    assert len(bulk_events) == 2


def test_read_active_profile_returns_record(secure_objects, schema) -> None:
    state = WorkflowState()
    state = register_active_profile(
        state,
        profile_id="default",
        display_name="Default operator",
        facts=_all_required_facts(schema),
        secure_objects=secure_objects,
        schema=schema,
    )
    record = read_active_profile(state, secure_objects=secure_objects, schema=schema)
    assert record is not None
    assert record.profile_id == "default"
    assert record.status is UserProfileStatus.ACTIVE


def test_remove_active_profile_tombstones_and_clears_pointer(secure_objects, schema) -> None:
    state = WorkflowState()
    state = register_active_profile(
        state,
        profile_id="default",
        display_name="Default operator",
        facts=_all_required_facts(schema),
        secure_objects=secure_objects,
        schema=schema,
    )
    state = remove_active_profile(state, secure_objects=secure_objects, schema=schema)
    from aeat.application.workflow._models import resolve_active_bucket_id

    assert resolve_active_bucket_id() is None
    assert state.bucket_events[-1].action == "profile.tombstoned"
