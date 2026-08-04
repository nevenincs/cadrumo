"""What ``profile edit NAME`` does with the name on the manager arm.

The manager edits whichever profile is ACTIVE — it resolves its subject
through the active-bucket pointer and never reads the verb's argument. So
the argument has to be checked before the diversion, or it is honoured in
the routing and dropped in the work: naming another taxpayer opened the
active profile's page instead, and every field edited from there landed on
the wrong one.

These are real registrations against an isolated storage root rather than
a described scenario, because the whole property is about which of two
concrete profiles the pointer names.
"""

from __future__ import annotations

import pytest

from .....tests.secure_sql import isolated_profile_storage_root
from .._manager_dispatch import refuse_an_edit_target_the_manager_cannot_open

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


#: One passphrase for every profile a test registers. Profiles in a storage
#: root share the master-key store, so a second registration under a
#: different passphrase fails the unwrap rather than creating a profile —
#: which would make a two-profile test fail in setup for a reason that has
#: nothing to do with what it is checking.
_OPERATOR_SECRET = "manager-edit-target-operator-secret"  # noqa: S105 - synthetic test fixture


def _register(label: str) -> str:
    """Create one live profile and return its bucket id.

    Registration leaves its profile unlocked and selected, so the LAST
    call decides which profile is active — which is what lets a test
    below name a live profile that is deliberately not the active one.
    """
    from .._manager_frontend import attempt_registration

    attempt = attempt_registration(label, _OPERATOR_SECRET, "en")
    assert attempt.outcome is not None, f"the fixture profile must exist, but: {attempt.refusal}"
    return attempt.outcome.bucket_id


def _active_bucket_id() -> str | None:
    from .....core import resolve_active_bucket_id

    return resolve_active_bucket_id()


def test_an_unnamed_edit_is_left_alone(tmp_path) -> None:
    """The commonest invocation must not acquire a new refusal.

    ``profile edit`` with no name means "the profile I am on", which is
    exactly what the manager already opens.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _register("Solo Subject")
        assert refuse_an_edit_target_the_manager_cannot_open(None) is None
        assert refuse_an_edit_target_the_manager_cannot_open("") is None
        assert refuse_an_edit_target_the_manager_cannot_open("   ") is None


def test_naming_the_active_profile_is_allowed_through(tmp_path) -> None:
    """Naming the profile you are already on is not an error.

    This is the positive control for the refusal below: without it, a
    check that refused every named target would pass that test too, and
    would have broken the one invocation the operator makes most.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        bucket_id = _register("Active Subject")
        assert _active_bucket_id() == bucket_id, "registration must leave this profile active"

        assert refuse_an_edit_target_the_manager_cannot_open("Active Subject") is None
        assert refuse_an_edit_target_the_manager_cannot_open(bucket_id) is None


def test_naming_another_live_profile_refuses_instead_of_editing_the_active_one(tmp_path) -> None:
    """The defect: a live profile that is not the active one.

    Both profiles are real and both resolve, so the refusal cannot come
    from the target being unknown — it comes from it not being the one the
    manager would open, which is the whole point. Asserted against the
    pointer rather than registration order, so the test still means what
    it says if registration ever stops selecting what it creates.
    """
    from ..._errors import CliRefusedBoundaryError

    with isolated_profile_storage_root(tmp_path=tmp_path):
        other_id = _register("Other Subject")
        active_id = _register("Active Subject")
        assert _active_bucket_id() == active_id, "the second registration must be the active one"
        assert other_id != active_id

        with pytest.raises(CliRefusedBoundaryError):
            refuse_an_edit_target_the_manager_cannot_open("Other Subject")


def test_an_unknown_edit_target_refuses_as_login_would(tmp_path) -> None:
    """A mistyped label refuses rather than silently editing the active profile.

    The refusal comes from the same resolver ``login NAME`` uses, so the
    two verbs cannot drift into different answers about what counts as a
    profile.
    """
    from .....domain.user_profile import ProfileNotFoundError

    with isolated_profile_storage_root(tmp_path=tmp_path):
        _register("Active Subject")
        with pytest.raises(ProfileNotFoundError):
            refuse_an_edit_target_the_manager_cannot_open("Aktive Subjekt")
