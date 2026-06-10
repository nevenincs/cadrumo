"""Tests for the WorkflowState-aware user-profile orchestration helpers."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from ....core import resolve_active_bucket_id
from ....core.resources import resources
from ....domain.user_profile import (
    ProfileNotFoundError,
    ProfileSchemaDefinition,
    UserProfileFact,
    UserProfileStatus,
)
from ....tests.secure_sql import isolated_profile_storage_root
from ...workflow._models import WorkflowState
from ...workflow._profile_bucket_scan import read_profile_bucket, read_profile_bucket_by_id
from .._orchestration import (
    profile_create_storage_span,
    read_active_profile,
    register_active_profile,
    remove_active_profile,
    select_profile,
    set_active_field,
    set_active_fields,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


# The application-level conftest already redirects
# Settings.aeat_local_storage_root to tmp_path for every test, so the
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
    with profile_create_storage_span("default") as routing_profile_id:
        updated = register_active_profile(
            state,
            profile_id="default",
            display_name="Default operator",
            facts=_all_required_facts(schema),
            schema=schema,
            routing_profile_id=routing_profile_id,
        )
    assert resolve_active_bucket_id() == "default"
    # The bucket directory is named by the UUID identity ("default"
    # here); its manifest carries the decoupled operator label.
    by_id = read_profile_bucket_by_id("default")
    assert by_id is not None
    assert by_id.bucket_id == "default"
    assert by_id.label == "Default operator"
    # The operator-facing label resolves back to the same bucket.
    assert read_profile_bucket("Default operator") == by_id
    actions = tuple(event.action for event in updated.bucket_events)
    assert actions == ("profile.created", "profile.selected", "profile.values.updated")


def test_select_profile_refuses_when_missing(schema: ProfileSchemaDefinition) -> None:
    state = WorkflowState()
    with pytest.raises(ProfileNotFoundError):
        select_profile(state, profile_id="ghost", schema=schema)


def test_set_active_field_appends_workflow_event(schema: ProfileSchemaDefinition) -> None:
    state = WorkflowState()
    with profile_create_storage_span("default") as routing_profile_id:
        state = register_active_profile(
            state,
            profile_id="default",
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
    with profile_create_storage_span("default") as routing_profile_id:
        state = register_active_profile(
            state,
            profile_id="default",
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
    with profile_create_storage_span("default") as routing_profile_id:
        state = register_active_profile(
            state,
            profile_id="default",
            display_name="Default operator",
            facts=_all_required_facts(schema),
            schema=schema,
            routing_profile_id=routing_profile_id,
        )
        record = read_active_profile(state, schema=schema)
        assert record is not None
        assert record.profile_id == "default"
        assert record.status is UserProfileStatus.ACTIVE


def test_read_active_profile_logs_missing_selected_record(
    caplog: pytest.LogCaptureFixture, schema: ProfileSchemaDefinition
) -> None:
    """A torn active pointer degrades to no record with debug evidence."""

    with profile_create_storage_span("ghost"):
        caplog.set_level(logging.DEBUG, logger="aeat.application.user_profile._orchestration")

        record = read_active_profile(WorkflowState(), schema=schema)

    assert record is None
    assert "active profile selection resolved to a missing profile record" in caplog.text


def test_remove_active_profile_tombstones_and_clears_pointer(schema: ProfileSchemaDefinition) -> None:
    state = WorkflowState()
    with profile_create_storage_span("default") as routing_profile_id:
        state = register_active_profile(
            state,
            profile_id="default",
            display_name="Default operator",
            facts=_all_required_facts(schema),
            schema=schema,
            routing_profile_id=routing_profile_id,
        )
        state = remove_active_profile(state, schema=schema)
    from ....core import resolve_active_bucket_id

    assert resolve_active_bucket_id() is None
    assert state.bucket_events[-1].action == "profile.tombstoned"
