"""CLI tests for per-bucket profile lifecycle navigation.

These tests drive ``aeat config profile`` from a cold per-bucket storage
backend: ``delete`` / ``login`` / ``list`` / ``status`` / ``show`` all
resolve correctly from a no-active-session state, the active-profile
delete is deliberately refused, and the retired verbs (``rename``,
``export``, ``import``) stay unregistered. They are the
navigation-and-delete sibling of ``test_profile_lifecycle_verbs`` (which
owns the record-level show / create / edit / repair surface); both share
the fixtures and helpers in ``_profile_lifecycle_support``.

The ``"buckets"`` literal below is deliberate: ``isolated_profile_storage_root``
overrides only the secret store, so ``_per_bucket_backend / "buckets" /
uuid_before`` checks production's real DEFAULT-derived bucket directory, not
an injected value. Re-deriving it from the taxonomy accessor would make the
assertion agree unconditionally with the code path it exists to
independently confirm.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Final

import pytest
from click.testing import Result

from ....core.config import load_settings
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage
from ....tests.user_profile import register_cli_profile

__all__ = ["isolated_profile_storage"]
from ._profile_lifecycle_support import create_profile_via_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

PINNED_TAXONOMY_LITERALS: Final[frozenset[str]] = frozenset({"buckets"})
"""Taxonomy-vocabulary literals this module deliberately pins. See the module docstring."""


def _invoke(args: Sequence[str]) -> Result:
    # `config profile create` mints a custody envelope, so it needs the operator
    # passphrase and its confirmation, and a test runner is not a terminal: the
    # bounded strict-JSON channel is the only one the verb accepts.
    if "create" in args and "profile" in args and "--secrets-stdin" not in args:
        return invoke_cached_cli(
            (*args, "--secrets-stdin"),
            input=json.dumps({"passphrase": _dev_passphrase(), "passphrase_confirmation": _dev_passphrase()}),
        )
    # `login` OPENS an existing envelope rather than minting one, so it takes the
    # passphrase alone and refuses a payload carrying the confirmation field.
    if "login" in args and "--secrets-stdin" not in args:
        return invoke_cached_cli(
            (*args, "--secrets-stdin"),
            input=json.dumps({"passphrase": _dev_passphrase()}),
        )
    return invoke_cached_cli(args)


def _dev_passphrase() -> str:
    """The secret the isolated backend seeds custody envelopes with."""
    return load_settings().cadrumo_dev_test_database_password.get_secret_value()


@pytest.fixture
def _per_bucket_backend(tmp_path: Path) -> Iterator[Path]:
    """Per-bucket storage (no global CADRUMO_DATABASE_URL).

    Each profile bucket resolves its own SQLite file from the
    active-profile pointer chain, the production cold-start path.
    The autouse ``isolated_profile_storage`` fixture runs first and installs
    an empty isolated_profile_storage_root; this fixture layers on
    top by yielding the same tmp_path storage root so callers can
    use create_profile_via_cli.
    """
    # isolated_profile_storage already set
    # cadrumo_local_storage_root to tmp_path / "cadrumo-storage".
    yield load_settings().cadrumo_local_storage_root


# --- the retired rename verb stays unregistered ---


def test_profile_rename_verb_is_not_registered(_per_bucket_backend: Path) -> None:
    """The retired ``rename`` verb stays unregistered: click refuses it.

    ``rename`` was a label-only edit; the custody redesign retired the
    verb outright. This pin asserts the negative conformance — the exact
    unknown-command refusal — so a re-registration reds here immediately.
    """
    from cadrumo.application.workflow.profile_bucket_scan import read_profile_bucket

    create_profile_via_cli("alpha")

    result = _invoke(("config", "profile", "rename", "alpha", "beta"))
    assert result.exit_code != 0, result.output
    assert "No such command 'rename'" in result.output

    pointer = read_profile_bucket("alpha")
    assert pointer is not None, "the profile label must be unchanged after the refusal"
    assert read_profile_bucket("beta") is None


def test_profile_create_refuses_case_insensitive_duplicate_label(
    _per_bucket_backend: Path,
) -> None:
    """Display-name uniqueness is enforced case-insensitively across live profiles."""

    first = _invoke(("config", "profile", "create", "Only One", "--quiet"))
    assert first.exit_code == 0, first.output

    second = _invoke(("config", "profile", "create", "only one", "--quiet"))
    assert second.exit_code != 0, second.output
    flat = second.output.lower()
    assert "ya existe" in flat or "already exists" in flat

    listed = _invoke(("config", "profile", "list"))
    assert listed.exit_code == 0, listed.output
    assert "Only One" in listed.output


# --- profile-lifecycle navigation from a no-active-session state ---
#
# These tests drive the full root CLI so the CLI root callback (the
# active-session gate) participates. The ``profile_app``-direct tests
# in the sibling module never reach that callback, so they cannot observe
# the lockout where a lifecycle-navigation verb reaches a decrypting read
# with no bucket session opened for it.


def test_delete_active_profile_is_refused_and_survivors_stay_reachable(
    _per_bucket_backend: Path,
) -> None:
    """The active profile cannot be deleted; survivors stay reachable.

    Reproduces the delete-active hazard: with two profiles, ``login`` to
    the first so it is active, then ``delete`` it. The custody redesign
    refuses the delete outright — the refusal is the lockout guard — and
    the survivor must remain reachable afterwards.
    """
    from cadrumo.application.workflow.profile_bucket_scan import read_profile_bucket
    from ....core.bucket_pointer import resolve_active_bucket_id

    create_profile_via_cli("alpha")
    create_profile_via_cli("beta")
    assert _invoke(("config", "login", "alpha")).exit_code == 0

    deleted = _invoke(("config", "profile", "delete", "alpha", "--yes"))
    assert deleted.exit_code != 0, deleted.output
    flat = deleted.output.lower()
    assert "eliminar el perfil activo" in flat or "active profile" in flat
    assert "config logout" in deleted.output

    # The refusal is a projection: the target profile still resolves.
    survivor = read_profile_bucket("alpha")
    assert survivor is not None
    assert resolve_active_bucket_id() == survivor.bucket_id

    switched = _invoke(("config", "login", "beta"))
    assert switched.exit_code == 0, switched.output
    assert "active_profile\tbeta" in switched.output


def test_first_switch_from_a_no_active_profile_state_succeeds(
    _per_bucket_backend: Path,
) -> None:
    """``switch`` works from a cold no-active-profile state.

    ``create`` lands a profile and leaves it active; logging out clears
    the pointer so no session resolves at root-callback time. ``switch``
    must still open its own session and activate the named profile.
    """
    from ....core.bucket_pointer import resolve_active_bucket_id

    create_profile_via_cli("solo")

    assert _invoke(("config", "logout")).exit_code == 0
    assert resolve_active_bucket_id() is None

    switched = _invoke(("config", "login", "solo"))
    assert switched.exit_code == 0, switched.output
    assert "active_profile\tsolo" in switched.output


def test_list_and_status_work_from_a_no_active_session_state(
    _per_bucket_backend: Path,
) -> None:
    """``list`` and ``status`` resolve without a bucket session.

    Both are lifecycle-navigation surfaces; neither must be gated behind
    an active session. With the active pointer cleared, ``list`` still
    enumerates registered profiles and ``status`` reports the empty
    no-active-profile state instead of refusing.
    """

    create_profile_via_cli("alpha")

    assert _invoke(("config", "logout")).exit_code == 0

    listed = _invoke(("config", "profile", "list"))
    assert listed.exit_code == 0, listed.output
    assert "alpha" in listed.output

    status = _invoke(("config", "profile", "status"))
    assert status.exit_code == 0, status.output
    assert "bucket session" not in status.output


def test_delete_active_profile_refuses_and_keeps_the_pointer_intact(
    _per_bucket_backend: Path,
) -> None:
    """Deleting the active profile is refused; the pointer survives.

    The old delete-active path cleared the active-profile pointer; the
    custody redesign refuses the delete instead. The refusal must not
    leave the pointer cleared — the profile remains active afterwards.
    """
    from ....core.bucket_pointer import resolve_active_bucket_id

    create_profile_via_cli("alpha")
    assert _invoke(("config", "login", "alpha")).exit_code == 0
    pointer_before = resolve_active_bucket_id()
    assert pointer_before is not None

    deleted = _invoke(("config", "profile", "delete", "alpha", "--yes"))
    assert deleted.exit_code != 0, deleted.output
    assert "deleted\ttrue" not in deleted.output
    flat = deleted.output.lower()
    assert "eliminar el perfil activo" in flat or "active profile" in flat
    assert resolve_active_bucket_id() == pointer_before


def test_delete_non_active_profile_omits_the_cleared_pointer_notice(
    _per_bucket_backend: Path,
) -> None:
    """Deleting a profile from a no-active-session state does not claim the pointer was cleared.

    The cleared-pointer notice belonged only to the old delete-active
    path; deleting an inactive profile from a no-active-session state
    leaves no pointer to clear and must not emit the notice.
    """

    create_profile_via_cli("alpha")
    create_profile_via_cli("beta")
    assert _invoke(("config", "logout")).exit_code == 0

    deleted = _invoke(("config", "profile", "delete", "alpha", "--yes"))
    assert deleted.exit_code == 0, deleted.output
    assert "deleted\ttrue" in deleted.output
    assert "active_profile" not in deleted.output


def test_delete_unknown_profile_refuses_with_an_unknown_profile_message(
    _per_bucket_backend: Path,
) -> None:
    """``delete <unknown>`` gives an unknown-profile refusal, not a session error.

    With no active session, deleting a name that no profile carries must
    surface a clear ``unknown profile`` refusal. The operator must be
    able to tell the name does not exist — distinct from any
    session-state diagnostic.
    """

    create_profile_via_cli("alpha")

    assert _invoke(("config", "logout")).exit_code == 0

    refused = _invoke(("config", "profile", "delete", "ghost", "--yes"))
    assert refused.exit_code != 0, refused.output
    flat = refused.output.lower()
    # The refusal names the unknown profile and does NOT leak the
    # session-state diagnostic.
    assert "ghost" in flat
    assert "desconocido" in flat or "unknown" in flat
    assert "bucket session" not in flat


def test_delete_valid_profile_with_no_active_session_succeeds(
    _per_bucket_backend: Path,
) -> None:
    """``delete <valid>`` works with no pre-existing session.

    Deleting a registered, non-active profile from a no-active-session
    state must succeed — ``delete`` opens its own bucket session scoped
    to the target, it does not require one to already be open.
    """
    from cadrumo.application.workflow.profile_bucket_scan import read_profile_bucket

    create_profile_via_cli("alpha")

    assert _invoke(("config", "logout")).exit_code == 0

    deleted = _invoke(("config", "profile", "delete", "alpha", "--yes"))
    assert deleted.exit_code == 0, deleted.output
    assert "deleted\ttrue" in deleted.output
    # The profile is gone from the live surface.
    assert read_profile_bucket("alpha") is None


def test_deleted_profile_name_is_reusable_by_create(
    _per_bucket_backend: Path,
) -> None:
    """After ``delete`` the freed display name is reusable.

    Per the profile-UUID identity contract, display-name uniqueness is
    enforced only among live profiles; a deleted profile's name is free
    for a new registration.
    """

    # The production creation door records the empty legal-hold and
    # filing-retention snapshots the deletion preflight requires; the
    # test seeding door deliberately does not, so a deletion subject
    # must be born through the scripted CLI door.
    create_profile_via_cli("operator")
    create_profile_via_cli("other")
    assert _invoke(("config", "logout")).exit_code == 0
    _deleted = _invoke(("config", "profile", "delete", "operator", "--yes"))
    assert _deleted.exit_code == 0, _deleted.output

    register_cli_profile(
        label="operator",
        facts={
            "identity.tax_id": "12345678Z",
            "taxpayer_type.entity_type": "natural_person",
            "identity.name": "Operator",
            "identity.surnames": "Operator",
            "activities.description": "design",
            "iva.regime": "GENERAL",
            "tax_residence.jurisdiction_scope": "common_regime",
            "iva.m303_regime_composition": "general",
            "iva.redeme_enrolled": "false",
            "iva.cash_accounting_regime_enrolled": "false",
            "iva.voluntary_sii_enrolled": "false",
            "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
        },
    )

    listed = _invoke(("config", "profile", "list"))
    assert listed.exit_code == 0, listed.output
    assert "operator" in listed.output
