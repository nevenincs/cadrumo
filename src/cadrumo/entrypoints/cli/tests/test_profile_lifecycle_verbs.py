"""CLI surface tests for `aeat config profile {show, edit, status, repair}` and login.

The per-bucket rename / import / delete / no-active-session navigation tests
that exercise the same surface live in the sibling
``test_profile_lifecycle_navigation`` module; both share the storage backend,
``seed`` primitive, and torn-bucket stager defined in
``_profile_lifecycle_support``.

``create`` is absent from that list on purpose. Credential registration is
the only creation door, so the wizard `create` arm refuses unconditionally
and there is no CLI-scriptable creation contract left to assert. Seven tests
that drove it were retired with this change; each is named below with what,
if anything, answers it now, so a later reader does not read the deletions as
lost coverage:

- create_second_profile_uses_requested_identity_while_first_is_active: not
  retired. Its subject -- a second profile must not reuse the first's bucket
  -- is re-founded below against the registration door.
- create_bare_name_refusal_names_both_recovery_paths,
  create_quiet_without_flags_names_the_missing_flags,
  create_error_language siblings: the missing-required-flags refusal is
  unreachable from every live surface -- `create` refuses above it and a
  non-interactive `edit` is a patch that never checks required flags -- so
  the assertion has no subject rather than a different home.
- create_quiet_emits_confirmation: the confirmation line belongs to a
  creation success that cannot occur.
- create_nif_error_does_not_leak_internal_keys,
  create_joint_family_validation_names_failing_flags: refusal CONTENT on the
  retired path. The manager frontend renders its own refusals and the
  application layer renders none, so neither has a successor here.
- create_invalid_nif_does_not_leave_orphan_bucket: rollback on a failed
  create is covered at the surviving door by
  application/user_profile/tests/test_atomic_create_rollback.py.

`create` still refuses a label that already exists, and that refusal fires
ahead of the retirement check, so ``create_refuses_existing_profile`` below
is live coverage rather than a leftover.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

import pytest
from click.testing import Result

from ....core.config import load_settings
from ....core.i18n import tr
from ....core.redaction import CLI_PROFILE_ID_PLACEHOLDER
from ....tests.cli_runner import invoke_cached_cli
from ....tests.profile_capsule import open_test_profile_session
from ....tests.profile_storage_root_fixture import profile_storage_root_fixture
from ....tests.user_profile import register_cli_profile
from ._profile_lifecycle_support import seed

__all__ = ["profile_storage_root_fixture"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PROFILE_LABEL = tr("application.wizard.output_labels.profile", locale="en")
_STATUS_LABEL = tr("application.wizard.output_labels.status", locale="en")
_UPDATED = tr("wizard.commands.status.updated", locale="en")


@pytest.fixture(autouse=True)
def _isolated_backend(profile_storage_root: Path) -> Path:
    # open_test_profile_session (called inside seed) resolves the
    # file-backed master-key provider provisioned by this fixture.
    return profile_storage_root


def _invoke_config(args: Sequence[str]) -> Result:
    return invoke_cached_cli(("config", *args))


def _dev_passphrase() -> str:
    """The secret the seeded custody envelopes were created with."""
    return load_settings().cadrumo_dev_test_database_password.get_secret_value()


def _invoke_profile_with_secret(args: Sequence[str]) -> Result:
    """Run a `config profile` verb that mints custody, over the secrets channel.

    Creating a profile derives a custody envelope, so the verb needs the
    operator passphrase. A test runner is not a TTY and the secret is
    resolvable from neither settings nor the environment, so without this the
    verb refuses for want of a channel and never reaches the behaviour under
    test.
    """
    return invoke_cached_cli(
        ("config", "profile", *args, "--secrets-stdin"),
        input=json.dumps(
            # `create` mints custody rather than opening it, so it requires the
            # confirmation field too and refuses a payload carrying only one.
            {"passphrase": _dev_passphrase(), "passphrase_confirmation": _dev_passphrase()},
        ),
    )


def _login(name: str) -> Result:
    """Unlock ``name`` over the only channel ``config login`` still accepts.

    The passphrase is not resolvable from settings or the environment, and a
    test runner is not a TTY, so the verb refuses outright unless the secret
    arrives on the bounded strict-JSON channel. The value is the one the seeded
    custody envelope was created with, or it would not open.
    """
    return invoke_cached_cli(
        ("config", "login", name, "--secrets-stdin"),
        input=json.dumps(
            {"passphrase": load_settings().cadrumo_dev_test_database_password.get_secret_value()},
        ),
    )


def _invoke_profile(args: Sequence[str]) -> Result:
    return _invoke_config(("profile", *args))


def _invoke_profile_app(args: Sequence[str]) -> Result:
    return _invoke_profile(args)


def test_registering_a_second_profile_uses_its_own_identity_while_the_first_is_active() -> None:
    """Registering beta in alpha's live root must not reuse alpha's bucket.

    Two profiles registered back to back in one process must land on two
    distinct buckets, each addressable by its own label, with neither one's
    facts visible through the other. This was previously driven through
    scripted ``profile create``; the door moved to credential registration
    and the invariant did not.
    """
    from ....application.workflow import read_profile_bucket

    register_cli_profile(
        label="alpha",
        facts={
            "taxpayer_type.entity_type": "natural_person",
            "identity.name": "Alpha",
            "identity.surnames": "Operator",
            "activities.description": "alpha-design",
            "iva.regime": "GENERAL",
            "tax_residence.jurisdiction_scope": "common_regime",
            "iva.m303_regime_composition": "general",
            "iva.redeme_enrolled": "false",
            "iva.cash_accounting_regime_enrolled": "false",
            "iva.voluntary_sii_enrolled": "false",
            "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
        },
    )
    register_cli_profile(
        label="beta",
        facts={
            "taxpayer_type.entity_type": "natural_person",
            "identity.name": "Beta",
            "identity.surnames": "Operator",
            "activities.description": "beta-consulting",
            "iva.regime": "GENERAL",
            "tax_residence.jurisdiction_scope": "common_regime",
            "iva.m303_regime_composition": "general",
            "iva.redeme_enrolled": "false",
            "iva.cash_accounting_regime_enrolled": "false",
            "iva.voluntary_sii_enrolled": "false",
            "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
        },
    )

    alpha_pointer = read_profile_bucket("alpha")
    beta_pointer = read_profile_bucket("beta")
    assert alpha_pointer is not None
    assert beta_pointer is not None
    assert alpha_pointer.bucket_id != beta_pointer.bucket_id

    listing = _invoke_profile(("list",))
    assert listing.exit_code == 0, listing.output
    assert "active_profile	beta" in listing.output
    assert " 	alpha" in listing.output
    assert "*	beta" in listing.output

    alpha_show = invoke_cached_cli(("--profile", "alpha", "config", "profile", "show"))
    beta_show = invoke_cached_cli(("--profile", "beta", "config", "profile", "show"))
    assert alpha_show.exit_code == 0, alpha_show.output
    assert beta_show.exit_code == 0, beta_show.output

    assert "display_name	alpha" in alpha_show.output
    assert "identity.name	Alpha" in alpha_show.output
    assert "activities.description	alpha-design" in alpha_show.output
    assert "display_name	beta" not in alpha_show.output
    assert "activities.description	beta-consulting" not in alpha_show.output

    assert "display_name	beta" in beta_show.output
    assert "identity.name	Beta" in beta_show.output
    assert "activities.description	beta-consulting" in beta_show.output
    assert "display_name	alpha" not in beta_show.output
    assert "activities.description	alpha-design" not in beta_show.output


def test_config_login_activates_existing_profile() -> None:
    # Registered through the real credential door, not ``seed``: that helper
    # provisions a raw session key rather than a passphrase-backed custody
    # envelope, so there is no operator passphrase for ``config login`` to
    # accept and the verb can only ever refuse.
    register_cli_profile(label="operator")
    register_cli_profile(label="spouse")
    result = _login("operator")
    assert result.exit_code == 0, result.output
    assert "active_profile\toperator" in result.output


def test_config_login_refuses_unknown_profile() -> None:
    result = _login("ghost")
    assert result.exit_code != 0


def test_config_unlock_is_no_longer_a_command() -> None:
    """``config unlock`` was hard-renamed, and its successor renamed again to ``config login``.

    The rename leaves no alias, synonym, or deprecation shadow: the retired
    spelling must resolve to a click ``No such command`` parse failure, not a
    second working door for the same intent.
    """
    seed("operator")
    result = _invoke_config(("unlock", "operator"))
    assert result.exit_code != 0
    assert "No such command 'unlock'" in result.output


def test_config_profile_create_refuses_existing_profile() -> None:
    seed("operator")

    # Invoke through the root CLI so the error boundary renders CadrumoError to output.
    result = _invoke_profile_with_secret(
        (
            "create",
            "operator",
            "--quiet",
            "--accept-defaults",
            "--tax-id",
            "12345678Z",
            "--name",
            "Operator",
            "--activity",
            "design",
            "--iva-regime",
            "GENERAL",
        ),
    )

    assert result.exit_code != 0
    # Asserted on the profile the refusal names rather than on an English
    # phrase: the envelope is localised, so pinning "already exists" pins the
    # catalogue this suite happens to render in.
    assert "operator" in result.output
    assert "login" in result.output


def test_config_profile_edit_refuses_missing_profile_without_creating_bucket() -> None:
    from ....application.workflow import read_profile_bucket

    result = _invoke_profile_app(
        (
            "edit",
            "ghost",
            "--quiet",
            "--accept-defaults",
            "--tax-id",
            "12345678Z",
            "--name",
            "Ghost",
            "--activity",
            "design",
            "--iva-regime",
            "GENERAL",
        ),
    )

    assert result.exit_code != 0
    assert "does not exist" in result.output
    assert read_profile_bucket("ghost") is None


def test_config_login_emits_profile_activated_event() -> None:
    """`config login` records a typed PROFILE_ACTIVATED event in the
    bucket-event-history catalogue so downstream auditors can replay
    the activation timeline. Distinct from PROFILE_SELECTED (which
    captures workflow-state-level selection).
    """

    from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
    from ....application.workflow import read_profile_bucket
    from ....domain.buckets import BucketEventType

    # Registered through the real credential door: ``seed`` provisions a raw
    # session key, not a passphrase-backed custody envelope, so ``config login``
    # has no operator passphrase to accept.
    register_cli_profile(label="operator")
    pointer = read_profile_bucket("operator")
    assert pointer is not None
    result = _login("operator")
    assert result.exit_code == 0, result.output

    # The bucket-event-history catalogue is encrypted; reading it requires an
    # active session for the operator profile's UUID bucket.
    with open_test_profile_session(pointer.bucket_id):
        catalogue = BucketEventHistoryRepository().load()
    matching = [
        event
        for event in catalogue.events.values()
        if event.event_type is BucketEventType.PROFILE_ACTIVATED and event.object_id == pointer.bucket_id
    ]
    assert matching, [event.event_type for event in catalogue.events.values()]
    assert matching[-1].payload["profile_id"] == pointer.bucket_id
    assert matching[-1].payload["active_profile"] == pointer.bucket_id


def test_config_profile_show_emits_active_profile_facts() -> None:
    # Registered and logged in rather than seeded: `seed` opens a session that
    # closes with its context, so the verb runs with no active profile.
    register_cli_profile(label="operator", facts={"identity.tax_id": "00000000T"})
    assert _login("operator").exit_code == 0
    result = _invoke_profile(("show",))
    assert result.exit_code == 0, result.output
    assert f"profile_id\t{CLI_PROFILE_ID_PLACEHOLDER}" in result.output
    assert "display_name\toperator" in result.output
    # NIF is identity-class data; centralized output redaction rewrites it to a
    # sha256 fingerprint before it reaches stdout. Assert the
    # redaction shape; assert the raw value does NOT leak.
    assert "identity.tax_id\tsha256:" in result.output
    assert "00000000T" not in result.output


def test_config_profile_show_named_profile_includes_canonical_facts() -> None:
    # Registered and logged in: `seed` opens a session that closes with its
    # context, leaving the verb with no active profile.
    register_cli_profile(label="operator", facts={"identity.tax_id": "00000001R"})
    assert _login("operator").exit_code == 0
    seed("spouse", tax_id="00000000T")
    result = _invoke_profile(("show", "spouse"))
    assert result.exit_code == 0, result.output
    assert f"profile_id\t{CLI_PROFILE_ID_PLACEHOLDER}" in result.output
    assert "display_name\tspouse" in result.output
    # Centralized output redaction: NIF redacted to sha256
    # fingerprint at the rendering boundary; raw value must not leak.
    assert "identity.tax_id\tsha256:" in result.output
    assert "00000000T" not in result.output
    assert "00000001R" not in result.output
    assert "iva.regime\tGENERAL" in result.output
    assert "tax_residence.ccaa\tmadrid" in result.output


def test_config_profile_delete_requires_yes() -> None:
    seed("operator")
    result = _invoke_profile_app(("delete", "operator"))
    assert result.exit_code != 0


def test_config_profile_delete_tombstones_with_yes() -> None:
    # Registered but deliberately NOT activated: deleting the ACTIVE profile is
    # refused, so a login here would block the verb under test.
    register_cli_profile(label="operator")
    result = _invoke_profile_app(("delete", "operator", "--yes"))
    assert result.exit_code == 0, result.output
    assert "status\ttombstoned" in result.output
    from ....core import resolve_active_bucket_id

    assert resolve_active_bucket_id() is None


def test_config_profile_list_excludes_a_tombstoned_profile() -> None:
    """After ``delete`` the profile leaves ``config profile list``.

    Closes the leak where a tombstoned profile stayed visible in the
    listing, indistinguishable from a live one.
    """

    # Registered but deliberately NOT activated: deleting the ACTIVE profile is
    # refused, so a login here would block the verb under test.
    register_cli_profile(label="operator")
    assert _invoke_profile_app(("delete", "operator", "--yes")).exit_code == 0
    result = _invoke_profile(("list",))
    assert result.exit_code == 0, result.output
    assert "operator" not in result.output
    assert "<none>" in result.output


def test_config_login_refuses_a_tombstoned_profile() -> None:
    """Unlocking a tombstoned profile is refused, not silently activated.

    Closes the leak where activation made a deleted profile the active
    one with exit code 0.
    """

    from ....core import resolve_active_bucket_id

    # Registered through the real credential door: ``seed`` provisions a raw
    # session key, not a passphrase-backed custody envelope, so ``config login``
    # has no operator passphrase to accept.
    register_cli_profile(label="operator")
    assert _invoke_profile_app(("delete", "operator", "--yes")).exit_code == 0
    result = _login("operator")
    assert result.exit_code != 0, result.output
    # The tombstoned profile was not made active.
    assert resolve_active_bucket_id() is None


def test_config_profile_show_reports_a_tombstoned_profile_as_tombstoned() -> None:
    """``show`` of a tombstoned profile renders ``record_validity tombstoned``.

    Closes the self-contradiction where ``show`` reported
    ``record_validity valid issues=0`` directly above ``status tombstoned``.
    """

    # Registered but deliberately NOT activated: deleting the ACTIVE profile is
    # refused, so a login here would block the verb under test.
    register_cli_profile(label="operator")
    assert _invoke_profile_app(("delete", "operator", "--yes")).exit_code == 0
    result = _invoke_profile(("show", "operator"))
    assert result.exit_code == 0, result.output
    assert "status\ttombstoned" in result.output
    assert "record_validity\ttombstoned" in result.output
    assert "record_validity\tvalid" not in result.output


def test_config_profile_show_inspects_a_tombstoned_profile_by_label_and_uuid() -> None:
    """``show`` preserves tombstoned inspect behavior for label and UUID targets."""

    from ....application.workflow import read_profile_bucket

    # Registered but deliberately NOT activated: deleting the ACTIVE profile is
    # refused, so a login here would block the verb under test.
    register_cli_profile(label="operator")
    pointer = read_profile_bucket("operator")
    assert pointer is not None
    tombstoned_uuid = pointer.bucket_id

    assert _invoke_profile_app(("delete", "operator", "--yes")).exit_code == 0
    by_label = _invoke_profile(("show", "operator"))
    by_uuid = _invoke_profile(("show", tombstoned_uuid))

    for result in (by_label, by_uuid):
        assert result.exit_code == 0, result.output
        assert "status\ttombstoned" in result.output
        assert "record_validity\ttombstoned" in result.output
        assert "Unknown profile" not in result.output


def test_config_profile_show_runs_validation_inline() -> None:
    # Registered and logged in: `seed` opens a session that closes with its
    # context, leaving the verb with no active profile.
    register_cli_profile(label="operator")
    assert _login("operator").exit_code == 0
    result = _invoke_profile(("show",))
    assert result.exit_code == 0, result.output
    assert f"profile_id\t{CLI_PROFILE_ID_PLACEHOLDER}" in result.output
    assert "display_name\toperator" in result.output
    assert "record_validity\tvalid" in result.output


def test_show_and_status_do_not_contradict_on_a_registered_profile() -> None:
    """``show`` and ``status`` report two distinct notions without colliding.

    A registered profile carries a schema-valid record but has not yet
    declared an activity, so it is *record-valid* yet *not filing ready*.
    The two surfaces previously both printed the bare token ``readiness``
    with opposite words — ``show: readiness ready`` above ``status:
    readiness blocked`` — which a non-technical operator reads as the tool
    contradicting itself. This pins the disambiguation: ``show`` owns
    ``record_validity`` (schema validity) and ``status`` owns ``readiness``
    (filing readiness), so the same profile never shows ``readiness ready``
    on one surface and ``readiness blocked`` on the other.

    The profile is seeded through the credential registration door with no
    activity declared: that is the state the contradiction appeared in, and
    it is reachable without the retired scripted-creation path.
    """
    register_cli_profile(
        label="maria",
        facts={
            "identity.tax_id": "12345678Z",
            "taxpayer_type.entity_type": "natural_person",
            "identity.name": "Maria",
            "identity.surnames": "Operator",
            # Blank drops the placeholder, leaving the activity undeclared,
            # which is precisely what makes ``status`` legitimately blocked.
            "activities.description": "",
        },
    )

    show_result = _invoke_profile(("show", "maria"))
    status_result = _invoke_profile(("status",))

    assert show_result.exit_code == 0, show_result.output
    assert status_result.exit_code == 0, status_result.output

    # ``show`` reports record validity, not filing readiness.
    assert "record_validity\tvalid" in show_result.output
    assert "readiness\t" not in show_result.output

    # ``status`` reports filing readiness; the registered profile has no
    # declared activity, so it is legitimately ``blocked`` for filing.
    assert "readiness\tblocked" in status_result.output
    assert "activities.description\tmissing" in status_result.output
    assert "record_validity\t" not in status_result.output

    # The contradiction reading is gone: no single profile shows the same
    # ``readiness`` token with opposite states across the two surfaces.
    assert "readiness\tready" not in show_result.output
    assert "readiness\tready" not in status_result.output


def test_config_profile_show_refuses_when_no_active_profile(_isolated_backend: Path) -> None:
    # Clear the active-profile precedence chain (env + pointer) so the
    # resolver returns None and the show verb refuses.
    from ....core import clear_pointer
    from ....core.config import override_settings

    clear_pointer(_isolated_backend)
    with override_settings(cadrumo_active_profile=None):
        result = _invoke_profile(("show",))
    assert result.exit_code != 0


def test_config_profile_edit_quiet_emits_updated_confirmation() -> None:
    """``profile edit --quiet`` must emit a confirmation line with ``Status\\tupdated``."""

    seed("editme")

    result = _invoke_profile_app(
        (
            "edit",
            "editme",
            "--quiet",
            "--tax-id",
            "12345678Z",
            "--name",
            "Edited",
            "--activity",
            "Design",
            "--iva-regime",
            "GENERAL",
        ),
    )

    assert result.exit_code == 0, result.output
    assert f"{_PROFILE_LABEL}\teditme" in result.output
    assert f"{_STATUS_LABEL}\t{_UPDATED}" in result.output


def test_config_profile_edit_non_tty_recovery_hint_points_at_edit() -> None:
    """A non-interactive ``profile edit`` (no flags) refuses with an edit-specific hint.

    The shared no-console message names ``profile create``, which reads
    as a destructive replacement when reached via ``profile edit``. The
    refusal must instead name the non-interactive ``profile edit``
    patch form so the operator does not believe their profile will be
    overwritten.
    """

    seed("editme")

    result = _invoke_profile_app(("edit", "editme"))

    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output
    flat = result.output.replace("\n", " ")
    # The recovery hint names the non-interactive `profile edit` form.
    assert "profile edit editme --quiet" in flat
    # It must NOT steer the operator to a destructive `profile create`.
    assert "profile create" not in flat


# --- Fix 3: degraded profile status exits non-zero ---


def test_config_profile_status_exits_nonzero_for_dangling_pointer(_isolated_backend: Path) -> None:
    """``config profile status`` exits non-zero when the active profile
    has a dangling pointer (registered but no manifest bucket)."""

    from ....core import BucketPointer, write_pointer

    # Write a pointer to a non-existent bucket so status sees dangling_pointer.
    write_pointer(_isolated_backend, BucketPointer(bucket_id="phantom", schema_version=1))

    result = _invoke_profile(("status",))

    assert result.exit_code != 0, result.output
    assert "dangling_pointer" in result.output
