"""Focused unit tests for application.profile._actions.

Three pure state-transition helpers operate on `WorkflowState` and
return new states via `model_copy` (no in-place mutation):

- `set_active_profile(state, name)` — selects or creates an active
  profile; trims name; raises on blank.
- `set_profile_values(state, profile_name, values)` — merges values
  into the named profile; normalises keys via `_normalise_key`;
  selects the profile as active.
- `clear_profile_values(state, profile_name, keys)` — removes the
  specified normalised keys; tolerates absent keys; selects the
  profile as active.

Previously no direct unit-test coverage. A regression in any branch
(dropping the key-normalisation, mutating the input state, skipping
the active_profile swap) would silently corrupt every operator's
profile-management flow.

Tests pin each helper's documented state-transition contract.
"""

from __future__ import annotations

import pytest

from ..workflow._models import WorkflowState
from ._actions import clear_profile_values, set_active_profile, set_profile_values
from ._models import ProfileRecord

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


# ---------------------------------------------------------------------------
# set_active_profile
# ---------------------------------------------------------------------------


def test_set_active_profile_creates_new_profile_when_absent() -> None:
    state = WorkflowState()

    updated = set_active_profile(state, "kent")

    assert updated.active_profile == "kent"
    assert "kent" in updated.profiles


def test_set_active_profile_preserves_existing_profile_entry() -> None:
    """When the profile exists, the entry is left intact — only
    active_profile updates."""
    initial = WorkflowState().model_copy(
        update={"profiles": {"kent": ProfileRecord(name="kent", values={"tax.id": "12345678Z"})}}
    )

    updated = set_active_profile(initial, "kent")

    assert updated.active_profile == "kent"
    profile = updated.profiles["kent"]
    assert isinstance(profile, ProfileRecord)
    assert profile.values["tax.id"] == "12345678Z"


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

    profile = updated.profiles["kent"]
    assert isinstance(profile, ProfileRecord)
    assert profile.values == {"tax.id": "12345678Z"}


def test_set_profile_values_merges_new_values_into_existing_profile() -> None:
    initial = WorkflowState().model_copy(
        update={"profiles": {"kent": ProfileRecord(name="kent", values={"tax.id": "12345678Z"})}}
    )

    updated = set_profile_values(initial, "kent", {"activity": "software"})

    profile = updated.profiles["kent"]
    assert isinstance(profile, ProfileRecord)
    assert profile.values == {"tax.id": "12345678Z", "activity": "software"}


def test_set_profile_values_overwrites_overlapping_keys() -> None:
    initial = WorkflowState().model_copy(
        update={"profiles": {"kent": ProfileRecord(name="kent", values={"tax.id": "12345678Z"})}}
    )

    updated = set_profile_values(initial, "kent", {"tax.id": "87654321B"})

    profile = updated.profiles["kent"]
    assert isinstance(profile, ProfileRecord)
    assert profile.values["tax.id"] == "87654321B"


def test_set_profile_values_folds_dash_into_dot_via_normalise_key() -> None:
    """Documented key-normalisation: dashes fold to dots; consumes
    domain.profile._normalise._normalise_key."""
    state = WorkflowState()

    updated = set_profile_values(state, "kent", {"tax-id": "12345678Z"})

    profile = updated.profiles["kent"]
    assert isinstance(profile, ProfileRecord)
    assert profile.values == {"tax.id": "12345678Z"}


def test_set_profile_values_strips_value_whitespace() -> None:
    state = WorkflowState()

    updated = set_profile_values(state, "kent", {"tax.id": "  12345678Z  "})

    profile = updated.profiles["kent"]
    assert isinstance(profile, ProfileRecord)
    assert profile.values["tax.id"] == "12345678Z"


def test_set_profile_values_sets_active_profile_invariant() -> None:
    """Side effect: the named profile becomes the active one
    regardless of what was active before."""
    initial = WorkflowState().model_copy(
        update={
            "active_profile": "other",
            "profiles": {"other": ProfileRecord(name="other")},
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
                "kent": ProfileRecord(name="kent", values={"tax.id": "12345678Z", "activity": "software"}),
            }
        }
    )

    updated = clear_profile_values(initial, "kent", ("tax.id",))

    profile = updated.profiles["kent"]
    assert isinstance(profile, ProfileRecord)
    assert "tax.id" not in profile.values
    assert profile.values["activity"] == "software"


def test_clear_profile_values_tolerates_absent_key() -> None:
    """Missing key → no-op, no raise."""
    initial = WorkflowState().model_copy(
        update={"profiles": {"kent": ProfileRecord(name="kent", values={"tax.id": "12345678Z"})}}
    )

    updated = clear_profile_values(initial, "kent", ("not-a-real-key",))

    profile = updated.profiles["kent"]
    assert isinstance(profile, ProfileRecord)
    assert profile.values == {"tax.id": "12345678Z"}


def test_clear_profile_values_removes_multiple_keys() -> None:
    initial = WorkflowState().model_copy(
        update={
            "profiles": {
                "kent": ProfileRecord(
                    name="kent",
                    values={"tax.id": "12345678Z", "activity": "software", "iva.regime": "general"},
                ),
            }
        }
    )

    updated = clear_profile_values(initial, "kent", ("tax.id", "iva.regime"))

    profile = updated.profiles["kent"]
    assert isinstance(profile, ProfileRecord)
    assert profile.values == {"activity": "software"}


def test_clear_profile_values_normalises_key_before_lookup() -> None:
    """Passing `'TAX-ID'` removes the entry stored under `'tax.id'`.
    Mirrors `set_profile_values`'s key-normalisation invariant."""
    initial = WorkflowState().model_copy(
        update={"profiles": {"kent": ProfileRecord(name="kent", values={"tax.id": "12345678Z"})}}
    )

    updated = clear_profile_values(initial, "kent", ("TAX-ID",))

    profile = updated.profiles["kent"]
    assert isinstance(profile, ProfileRecord)
    assert profile.values == {}


def test_clear_profile_values_sets_active_profile_even_when_no_values_change() -> None:
    """Side effect mirror of set_profile_values: the named profile
    becomes active regardless of whether any value actually
    changed."""
    initial = WorkflowState().model_copy(
        update={
            "active_profile": "other",
            "profiles": {
                "other": ProfileRecord(name="other"),
                "kent": ProfileRecord(name="kent"),
            },
        }
    )

    updated = clear_profile_values(initial, "kent", ("not-a-real-key",))

    assert updated.active_profile == "kent"
