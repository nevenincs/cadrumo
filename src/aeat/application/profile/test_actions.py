"""Tests for profile actions across workflow pointers and profile buckets.

Profile values are stored only in the profile bucket namespace. Workflow state
keeps pointer records, and actions resolve the active pointer before reading or
writing profile-bound values through the profile bucket repository.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import ValidationError

from ..workflow._models import ProfileBucketPointer, WorkflowState
from ..workflow._persistence import workflow_state_repository
from ._actions import clear_profile_values, set_active_profile, set_profile_values
from ._models import ProfileRecord
from ._repository import profile_bucket_repository

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture(autouse=True)
def _isolated_secure_bucket_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'profiles.db').as_posix()}")
    monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "unsecured")
    monkeypatch.setenv("AEAT_ALLOW_UNENCRYPTED", "1")

    from ...adapters.persistence.storage.sql.engine import dispose_engine

    dispose_engine()
    try:
        yield
    finally:
        dispose_engine()


def _stored_profile(name: str) -> ProfileRecord:
    profile = profile_bucket_repository().load(name)
    assert isinstance(profile, ProfileRecord)
    return profile


def test_workflow_state_rejects_value_bearing_profile_payloads() -> None:
    with pytest.raises(ValidationError):
        WorkflowState.model_validate({"profiles": {"kent": {"tax.id": "12345678Z"}}})


def test_workflow_state_repository_refuses_unvalidated_value_bearing_profile_payloads() -> None:
    from ..workflow import WorkflowError

    repository = workflow_state_repository()
    invalid = WorkflowState().model_copy(update={"profiles": {"kent": {"tax.id": "12345678Z"}}})

    with pytest.raises(WorkflowError, match="workflow state refused invalid payload"):
        repository.save(invalid)

    assert repository.load().profiles == {}


def test_active_profile_record_dereferences_pointer_bucket_id() -> None:
    profile_bucket_repository().save(ProfileRecord(name="actual-bucket", values={"tax.id": "12345678Z"}))
    state = WorkflowState.model_validate(
        {
            "active_profile": "alias",
            "profiles": {"alias": {"bucket_id": "actual-bucket"}},
        }
    )

    record = state.active_profile_record()

    assert record is not None
    assert record.name == "actual-bucket"
    assert record.values["tax.id"] == "12345678Z"


# ---------------------------------------------------------------------------
# set_active_profile
# ---------------------------------------------------------------------------


def test_set_active_profile_creates_new_profile_when_absent() -> None:
    state = WorkflowState()

    updated = set_active_profile(state, "kent")

    assert updated.active_profile == "kent"
    assert "kent" in updated.profiles
    assert updated.profiles["kent"].bucket_id == "kent"
    assert _stored_profile("kent").values == {}
    assert [(event.action, event.bucket_id, event.object_id) for event in updated.bucket_events] == [
        ("profile.created", "kent", "kent"),
        ("profile.selected", "kent", "kent"),
    ]


def test_set_active_profile_preserves_existing_profile_entry() -> None:
    """When the profile exists, the bucket is left intact — only
    active_profile updates."""
    profile_bucket_repository().save(ProfileRecord(name="kent", values={"tax.id": "12345678Z"}))
    initial = WorkflowState().model_copy(update={"profiles": {"kent": ProfileBucketPointer(bucket_id="kent")}})

    updated = set_active_profile(initial, "kent")

    assert updated.active_profile == "kent"
    assert _stored_profile("kent").values["tax.id"] == "12345678Z"


def test_set_active_profile_raises_on_blank_name() -> None:
    state = WorkflowState()

    with pytest.raises(ValueError, match="profile name must not be blank"):
        set_active_profile(state, "")


def test_set_active_profile_strips_surrounding_whitespace() -> None:
    state = WorkflowState()

    updated = set_active_profile(state, "  kent  ")

    assert updated.active_profile == "kent"
    assert "kent" in updated.profiles


# ---------------------------------------------------------------------------
# set_profile_values
# ---------------------------------------------------------------------------


def test_set_profile_values_creates_new_profile_with_normalised_keys() -> None:
    state = WorkflowState()

    updated = set_profile_values(state, "kent", {"TAX.ID": "12345678Z"})

    assert updated.profiles["kent"].bucket_id == "kent"
    profile = _stored_profile("kent")
    assert profile.values == {"tax.id": "12345678Z"}
    assert [(event.action, event.bucket_id, event.object_id) for event in updated.bucket_events] == [
        ("profile.created", "kent", "kent"),
        ("profile.values.updated", "kent", "tax.id"),
    ]


def test_set_profile_values_merges_new_values_into_existing_profile() -> None:
    profile_bucket_repository().save(ProfileRecord(name="kent", values={"tax.id": "12345678Z"}))
    initial = WorkflowState().model_copy(update={"profiles": {"kent": ProfileBucketPointer(bucket_id="kent")}})

    set_profile_values(initial, "kent", {"activity": "software"})

    profile = _stored_profile("kent")
    assert profile.values == {"tax.id": "12345678Z", "activity": "software"}


def test_set_profile_values_summarises_large_update_event_ids() -> None:
    state = WorkflowState()
    values = {f"very.long.profile.key.{index:03d}": "set" for index in range(40)}

    updated = set_profile_values(state, "kent", values)

    profile = _stored_profile("kent")
    assert set(profile.values) == set(values)
    event = updated.bucket_events[-1]
    assert event.action == "profile.values.updated"
    assert event.object_id is not None
    assert event.object_id.startswith("keys:40:")
    assert len(event.object_id) < 128


def test_set_profile_values_overwrites_overlapping_keys() -> None:
    profile_bucket_repository().save(ProfileRecord(name="kent", values={"tax.id": "12345678Z"}))
    initial = WorkflowState().model_copy(update={"profiles": {"kent": ProfileBucketPointer(bucket_id="kent")}})

    set_profile_values(initial, "kent", {"tax.id": "87654321B"})

    profile = _stored_profile("kent")
    assert profile.values["tax.id"] == "87654321B"


def test_set_profile_values_folds_dash_into_dot_via_normalise_key() -> None:
    """Documented key-normalisation: dashes fold to dots; consumes
    domain.profile._normalise._normalise_key."""
    state = WorkflowState()

    set_profile_values(state, "kent", {"tax-id": "12345678Z"})

    profile = _stored_profile("kent")
    assert profile.values == {"tax.id": "12345678Z"}


def test_set_profile_values_strips_value_whitespace() -> None:
    state = WorkflowState()

    set_profile_values(state, "kent", {"tax.id": "  12345678Z  "})

    profile = _stored_profile("kent")
    assert profile.values["tax.id"] == "12345678Z"


def test_set_profile_values_sets_active_profile_invariant() -> None:
    """Side effect: the named profile becomes the active one
    regardless of what was active before."""
    initial = WorkflowState().model_copy(
        update={
            "active_profile": "other",
            "profiles": {"other": ProfileBucketPointer(bucket_id="other")},
        }
    )

    updated = set_profile_values(initial, "kent", {"tax.id": "12345678Z"})

    assert updated.active_profile == "kent"


# ---------------------------------------------------------------------------
# clear_profile_values
# ---------------------------------------------------------------------------


def test_clear_profile_values_removes_existing_key() -> None:
    initial = WorkflowState().model_copy(
        update={
            "profiles": {
                "kent": ProfileBucketPointer(bucket_id="kent"),
            }
        }
    )
    profile_bucket_repository().save(ProfileRecord(name="kent", values={"tax.id": "12345678Z", "activity": "software"}))

    updated = clear_profile_values(initial, "kent", ("tax.id",))

    profile = _stored_profile("kent")
    assert "tax.id" not in profile.values
    assert profile.values["activity"] == "software"
    assert [(event.action, event.bucket_id, event.object_id) for event in updated.bucket_events] == [
        ("profile.values.cleared", "kent", "tax.id"),
    ]


def test_clear_profile_values_tolerates_absent_key() -> None:
    """Missing key → no-op, no raise."""
    profile_bucket_repository().save(ProfileRecord(name="kent", values={"tax.id": "12345678Z"}))
    initial = WorkflowState().model_copy(update={"profiles": {"kent": ProfileBucketPointer(bucket_id="kent")}})

    clear_profile_values(initial, "kent", ("not-a-real-key",))

    profile = _stored_profile("kent")
    assert profile.values == {"tax.id": "12345678Z"}


def test_clear_profile_values_removes_multiple_keys() -> None:
    initial = WorkflowState().model_copy(
        update={
            "profiles": {
                "kent": ProfileBucketPointer(bucket_id="kent"),
            }
        }
    )
    profile_bucket_repository().save(
        ProfileRecord(name="kent", values={"tax.id": "12345678Z", "activity": "software", "iva.regime": "general"})
    )

    clear_profile_values(initial, "kent", ("tax.id", "iva.regime"))

    profile = _stored_profile("kent")
    assert profile.values == {"activity": "software"}


def test_clear_profile_values_normalises_key_before_lookup() -> None:
    """Passing `'TAX-ID'` removes the entry stored under `'tax.id'`.
    Mirrors `set_profile_values`'s key-normalisation invariant."""
    profile_bucket_repository().save(ProfileRecord(name="kent", values={"tax.id": "12345678Z"}))
    initial = WorkflowState().model_copy(update={"profiles": {"kent": ProfileBucketPointer(bucket_id="kent")}})

    clear_profile_values(initial, "kent", ("TAX-ID",))

    profile = _stored_profile("kent")
    assert profile.values == {}


def test_clear_profile_values_sets_active_profile_even_when_no_values_change() -> None:
    """Side effect mirror of set_profile_values: the named profile
    becomes active regardless of whether any value actually
    changed."""
    initial = WorkflowState().model_copy(
        update={
            "active_profile": "other",
            "profiles": {
                "other": ProfileBucketPointer(bucket_id="other"),
                "kent": ProfileBucketPointer(bucket_id="kent"),
            },
        }
    )

    updated = clear_profile_values(initial, "kent", ("not-a-real-key",))

    assert updated.active_profile == "kent"
