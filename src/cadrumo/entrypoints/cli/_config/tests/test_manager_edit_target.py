"""What ``profile edit NAME`` does with the name on the manager arm.

The manager edits whichever profile is ACTIVE — it resolves its subject
through the active-bucket pointer and never reads the verb's argument. So
the argument has to be checked before the diversion, or it is honoured in
the routing and dropped in the work: naming another taxpayer opened the
active profile's page instead, and every field edited from there landed on
the wrong one.

A name for another live profile is offered that profile's login screen, so
this host — which cannot show one — is also the proof of the fallback: the
offer declines and the refusal it protects stays reachable. The path where
the screen IS shown needs a terminal no test host here provides, so it is
left to the login screen's own tests rather than simulated with a double.

These are real registrations against an isolated storage root rather than
a described scenario, because the whole property is about which of two
concrete profiles the pointer names.
"""

from __future__ import annotations

import ast
import inspect

import pytest
import typer
from typer.core import TyperCommand

from .....tests.secure_sql import isolated_profile_storage_root
from ... import _common
from .. import _manager_dispatch
from .._manager_dispatch import open_the_edit_target_or_refuse

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _context() -> typer.Context:
    """A real Typer context, which the offer needs to re-point the profile."""
    return typer.Context(TyperCommand("edit"), obj={"format": "text"})


#: One passphrase for every profile a test registers. Profiles in a storage
#: root share the master-key store, so a second registration under a
#: different passphrase fails the unwrap rather than creating a profile —
#: which would make a two-profile test fail in setup for a reason that has
#: nothing to do with what it is checking.
_OPERATOR_SECRET = "manager-edit-target-operator-secret"  # noqa: S105 - synthetic test fixture


def test_manager_uses_the_canonical_cli_active_profile_label_resolver() -> None:
    """The manager must not redeclare the CLI identity projection."""
    tree = ast.parse(inspect.getsource(_manager_dispatch))
    declarations = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and node.name == "active_profile_label"
    ]
    assert declarations == []
    assert _manager_dispatch.active_profile_label is _common.active_profile_label


def _register(label: str) -> str:
    """Create one live profile and return its bucket id.

    Registration leaves its profile unlocked and selected, so the LAST
    call decides which profile is active — which is what lets a test
    below name a live profile that is deliberately not the active one.
    """
    from .._manager_frontend import attempt_registration

    attempt = attempt_registration(label, _OPERATOR_SECRET, "en", lambda enrollment: enrollment.recovery_key.mnemonic)
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
        assert open_the_edit_target_or_refuse(_context(), None) is None
        assert open_the_edit_target_or_refuse(_context(), "") is None
        assert open_the_edit_target_or_refuse(_context(), "   ") is None


def test_naming_the_active_profile_is_allowed_through(tmp_path) -> None:
    """Naming the profile you are already on is not an error.

    This is the positive control for the refusal below: without it, a
    check that refused every named target would pass that test too, and
    would have broken the one invocation the operator makes most.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        bucket_id = _register("Active Subject")
        assert _active_bucket_id() == bucket_id, "registration must leave this profile active"

        assert open_the_edit_target_or_refuse(_context(), "Active Subject") is None
        assert open_the_edit_target_or_refuse(_context(), bucket_id) is None


def test_naming_another_live_profile_never_edits_the_active_one(tmp_path) -> None:
    """The defect: a live profile that is not the active one.

    Both profiles are real and both resolve, so the outcome cannot come
    from the target being unknown — it comes from it not being the one the
    manager would open, which is the whole point. Asserted against the
    pointer rather than registration order, so the test still means what
    it says if registration ever stops selecting what it creates.

    On a host that can show a screen the operator would be offered the
    named profile's login page. This host cannot, so what is proved here
    is the other half of that: the offer declines and the refusal it
    protects still fires. Either way the one outcome ruled out is the
    defect — silently editing the active profile.
    """
    from ..._errors import CliRefusedBoundaryError

    with isolated_profile_storage_root(tmp_path=tmp_path):
        other_id = _register("Other Subject")
        active_id = _register("Active Subject")
        assert _active_bucket_id() == active_id, "the second registration must be the active one"
        assert other_id != active_id

        with pytest.raises(CliRefusedBoundaryError):
            open_the_edit_target_or_refuse(_context(), "Other Subject")


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
            open_the_edit_target_or_refuse(_context(), "Aktive Subjekt")
