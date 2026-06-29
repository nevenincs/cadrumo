"""CLI surface tests for `aeat config profile {show, create, edit, status, repair}` and switch.

The per-bucket rename / import / delete / no-active-session navigation tests
that exercise the same surface live in the sibling
``test_profile_lifecycle_navigation`` module; both share the storage backend,
``seed`` primitive, and torn-bucket stager defined in
``_profile_lifecycle_support``.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest
from click.testing import Result

from ....core.redaction import CLI_PROFILE_ID_PLACEHOLDER
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root
from ._profile_lifecycle_support import seed, stage_bucket_manifest

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    # profile_create_storage_span (called inside seed) resolves the
    # file-backed master-key provider provisioned by this fixture.
    with isolated_profile_storage_root(tmp_path=tmp_path):
        yield


def _invoke_config(args: Sequence[str]) -> Result:
    return invoke_cached_cli(("config", *args))


def _invoke_profile(args: Sequence[str]) -> Result:
    return _invoke_config(("profile", *args))


def _invoke_profile_app(args: Sequence[str]) -> Result:
    return _invoke_profile(args)


def _invoke_repair(args: Sequence[str]) -> Result:
    return _invoke_config(("repair", *args))


def test_config_switch_activates_existing_profile() -> None:
    seed("operator")
    seed("spouse")
    result = _invoke_config(("switch", "operator"))
    assert result.exit_code == 0, result.output
    assert "active_profile\toperator" in result.output


def test_config_switch_refuses_unknown_profile() -> None:
    result = _invoke_config(("switch", "ghost"))
    assert result.exit_code != 0


def test_config_unlock_is_no_longer_a_command() -> None:
    """``config unlock`` was hard-renamed to ``config switch``.

    The rename leaves no alias, synonym, or deprecation shadow: the retired
    spelling must resolve to a click ``No such command`` parse failure, not a
    second working door for the same intent.
    """
    seed("operator")
    result = _invoke_config(("unlock", "operator"))
    assert result.exit_code != 0
    assert "No such command 'unlock'" in result.output


def test_config_switch_reports_manifest_without_profile_record() -> None:
    stage_bucket_manifest("operator", label="operator")

    result = _invoke_config(("switch", "operator"))

    assert result.exit_code == 2, result.output
    assert "readiness\tmissing_profile_record" in result.output
    assert "profile_record\tmissing" in result.output
    assert "unknown profile" not in result.output.lower()


def test_config_profile_show_does_not_suggest_retired_activation_for_missing_record() -> None:
    stage_bucket_manifest("operator", label="operator")

    result = _invoke_profile(("show", "operator"))

    assert result.exit_code == 2, result.output
    assert "readiness\tmissing_profile_record" in result.output
    assert "next_action\taeat config repair profile --profile operator" in result.output
    assert "switch" not in result.output


def test_config_profile_create_refuses_manifest_only_profile() -> None:
    stage_bucket_manifest("operator", label="operator")

    # Invoke through the root CLI so decorate_typer_app's error boundary is active
    # and AeatError exceptions are rendered to output rather than propagating raw.
    result = _invoke_profile(
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
    assert "already exists" in result.output


def test_repair_profile_named_active_clear_active_clears_pointer(tmp_path: Path) -> None:
    from ....application.user_profile._orchestration import _write_active_profile_pointer
    from ....core import read_pointer

    stage_bucket_manifest("operator", label="operator")
    _write_active_profile_pointer("operator")

    result = _invoke_repair(("profile", "--profile", "operator", "--clear-active", "--yes"))

    assert result.exit_code == 0, result.output
    assert "cleared_pointer\tTrue" in result.output
    assert read_pointer(tmp_path) is None


def test_config_profile_create_refuses_existing_profile() -> None:
    seed("operator")

    # Invoke through the root CLI so the error boundary renders AeatError to output.
    result = _invoke_profile(
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
    assert "already exists" in result.output


def test_config_profile_create_bare_name_refusal_names_both_recovery_paths() -> None:
    """A first-timer running `profile create NAME` with no flags, in a
    shell with no interactive terminal, must get a refusal that spells
    out BOTH recovery paths in plain language and leaks no internals.

    Before fix: the refusal mentioned only the interactive path, then a
    trailing `-> Run` line that referenced `--quiet` as if the operator
    had chosen it. After fix: the message itself names the interactive
    path AND the one-step flag path, and never claims `--quiet` was a
    precondition the operator violated.
    """

    result = _invoke_profile(("create", "Cafe Luna"))

    assert result.exit_code != 0
    output = result.output
    # Both concrete recovery paths are named in the message body.
    assert "aeat config profile create NAME" in output
    assert "--quiet --tax-id NIF/CIF/DNI/NIE" in output
    # No internal tokens leak into the operator-facing refusal.
    assert "flow_id" not in output
    assert "('tax-id'" not in output
    assert "missing:" not in output


def test_config_profile_create_quiet_without_flags_names_the_missing_flags() -> None:
    """`profile create NAME --quiet` with the required value omitted
    must name the actual flag to add (`--tax-id`), not a raw Python
    identifier tuple, and must not leak `flow_id`.

    Only `--tax-id` is unconditionally required: `--activity` is gated
    behind the taxpayer's economic-activity declaration and a
    non-activity taxpayer (landlord, pensioner) is never asked for it.
    """

    result = _invoke_profile(("create", "Cafe Luna", "--quiet"))

    assert result.exit_code != 0
    output = result.output
    assert "--tax-id" in output
    # `--activity` is conditional, not unconditionally required, so it
    # must not appear in the missing-required-flags refusal.
    assert "--activity" not in output
    # The internal flow id and the raw missing-id tuple never surface.
    assert "flow_id" not in output
    assert "('tax-id'" not in output
    assert "missing:" not in output


def test_config_profile_edit_refuses_missing_profile_without_creating_bucket() -> None:
    from ....application.workflow._profile_bucket_scan import read_profile_bucket

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


def test_config_switch_emits_profile_activated_event() -> None:
    """`config switch` records a typed PROFILE_ACTIVATED event in the
    bucket-event-history catalogue so downstream auditors can replay
    the activation timeline. Distinct from PROFILE_SELECTED (which
    captures workflow-state-level selection).
    """

    from ....application.user_profile._orchestration import profile_storage_session
    from ....domain.buckets import BucketEventHistoryRepository, BucketEventType

    seed("operator")
    result = _invoke_config(("switch", "operator"))
    assert result.exit_code == 0, result.output

    # The bucket-event-history catalogue is encrypted; reading it requires an
    # active session for the "operator" bucket.
    with profile_storage_session("operator"):
        catalogue = BucketEventHistoryRepository().load()
    matching = [
        event
        for event in catalogue.events.values()
        if event.event_type is BucketEventType.PROFILE_ACTIVATED and event.object_id == "operator"
    ]
    assert matching, [event.event_type for event in catalogue.events.values()]
    assert matching[-1].payload["profile_id"] == "operator"
    assert matching[-1].payload["active_profile"] == "operator"


def test_config_profile_show_emits_active_profile_facts() -> None:
    seed("operator", tax_id="00000000T")
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
    seed("operator", tax_id="00000001R")
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
    seed("operator")
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

    seed("operator")
    assert _invoke_profile_app(("delete", "operator", "--yes")).exit_code == 0
    result = _invoke_profile(("list",))
    assert result.exit_code == 0, result.output
    assert "operator" not in result.output
    assert "<none>" in result.output


def test_config_switch_refuses_a_tombstoned_profile() -> None:
    """Unlocking a tombstoned profile is refused, not silently activated.

    Closes the leak where activation made a deleted profile the active
    one with exit code 0.
    """

    from ....core import resolve_active_bucket_id

    seed("operator")
    assert _invoke_profile_app(("delete", "operator", "--yes")).exit_code == 0
    result = _invoke_config(("switch", "operator"))
    assert result.exit_code != 0, result.output
    # The tombstoned profile was not made active.
    assert resolve_active_bucket_id() is None


def test_config_profile_show_reports_a_tombstoned_profile_as_tombstoned() -> None:
    """``show`` of a tombstoned profile renders ``record_validity tombstoned``.

    Closes the self-contradiction where ``show`` reported
    ``record_validity valid issues=0`` directly above ``status tombstoned``.
    """

    seed("operator")
    assert _invoke_profile_app(("delete", "operator", "--yes")).exit_code == 0
    result = _invoke_profile(("show", "operator"))
    assert result.exit_code == 0, result.output
    assert "status\ttombstoned" in result.output
    assert "record_validity\ttombstoned" in result.output
    assert "record_validity\tvalid" not in result.output


def test_config_profile_duplicate_copies_to_new_id() -> None:
    seed("operator")
    result = _invoke_profile_app(("duplicate", "operator", "operator-spouse", "--display-name", "Spouse"))
    assert result.exit_code == 0, result.output
    # The duplicate lands under a freshly minted profile id; per the
    # centralized-output-redaction contract, raw profile ids are
    # rewritten to a `<profile-id>` placeholder at the rendering
    # boundary before reaching stdout. Assert the placeholder shape; the
    # invariant the test guards is that a NEW record was created (the
    # registry pointer below) and labelled with the supplied
    # --display-name.
    assert f"source_profile_id\t{CLI_PROFILE_ID_PLACEHOLDER}" in result.output
    assert f"target_profile_id\t{CLI_PROFILE_ID_PLACEHOLDER}" in result.output
    assert "display_name\tSpouse" in result.output
    from ....application.workflow._profile_bucket_scan import read_profile_bucket

    assert read_profile_bucket("Spouse") is not None


def test_config_profile_duplicate_refuses_existing_target() -> None:
    seed("operator")
    seed("operator-spouse")
    result = _invoke_profile_app(("duplicate", "operator", "operator-spouse"))
    assert result.exit_code != 0


def test_config_profile_duplicate_target_token_is_the_addressable_label() -> None:
    """``duplicate SOURCE TARGET`` makes the new profile addressable as TARGET.

    Profiles are addressed by their display label (the bucket manifest
    label), and ``duplicate`` adopts the positional ``TARGET`` token as
    that label. The documented follow-on commands address the new
    profile by the same token, so ``duplicate ana-real ana-copy`` must be
    deletable / switchable as ``ana-copy`` without any further argument.

    Before the docs fix the how-to passed ``--display-name "Ana copy"``,
    which re-labelled the bucket to ``"Ana copy"`` and left the doc's own
    next command ``delete ana-copy`` refusing with ``Unknown profile``.
    This test pins the token-equals-label contract the docs now rely on.
    """
    seed("operator")

    duplicated = _invoke_profile_app(("duplicate", "operator", "operator-copy"))
    assert duplicated.exit_code == 0, duplicated.output
    assert "display_name\toperator-copy" in duplicated.output

    from ....application.workflow._profile_bucket_scan import read_profile_bucket

    assert read_profile_bucket("operator-copy") is not None

    # The doc's own next command: delete by the positional TARGET token.
    deleted = _invoke_profile_app(("delete", "operator-copy", "--yes"))
    assert deleted.exit_code == 0, deleted.output


def test_config_profile_duplicate_target_token_is_switchable() -> None:
    """A duplicated profile is switchable by its positional TARGET token.

    Companion to the delete-by-token contract: ``switch`` must also
    resolve the duplicate by the same token used to create it, so an
    operator who ran ``duplicate operator operator-copy`` can return to
    it with ``switch operator-copy``.
    """
    seed("operator")

    duplicated = _invoke_profile_app(("duplicate", "operator", "operator-copy"))
    assert duplicated.exit_code == 0, duplicated.output

    switched = _invoke_config(("switch", "operator-copy"))
    assert switched.exit_code == 0, switched.output
    assert "active_profile\toperator-copy" in switched.output


def test_config_profile_show_runs_validation_inline() -> None:
    seed("operator")
    result = _invoke_profile(("show",))
    assert result.exit_code == 0, result.output
    assert f"profile_id\t{CLI_PROFILE_ID_PLACEHOLDER}" in result.output
    assert "display_name\toperator" in result.output
    assert "record_validity\tvalid" in result.output


def test_show_and_status_do_not_contradict_on_a_freshly_created_profile() -> None:
    """``show`` and ``status`` report two distinct notions without colliding.

    A freshly created profile carries a schema-valid record but has not
    yet declared an activity, so it is *record-valid* yet *not filing
    ready*. The two surfaces previously both printed the bare token
    ``readiness`` with opposite words — ``show: readiness ready`` above
    ``status: readiness blocked`` — which a non-technical operator reads
    as the tool contradicting itself. This pins the disambiguation:
    ``show`` owns ``record_validity`` (schema validity) and ``status``
    owns ``readiness`` (filing readiness), so the same profile never
    shows ``readiness ready`` on one surface and ``readiness blocked`` on
    the other.
    """
    create_result = _invoke_profile(
        (
            "create",
            "maria",
            "--quiet",
            "--tax-id",
            "12345678Z",
            "--entity-type",
            "natural_person",
            "--name",
            "Maria",
            "--surnames",
            "Operator",
        ),
    )
    assert create_result.exit_code == 0, create_result.output

    show_result = _invoke_profile(("show", "maria"))
    status_result = _invoke_profile(("status",))

    assert show_result.exit_code == 0, show_result.output
    assert status_result.exit_code == 0, status_result.output

    # ``show`` reports record validity, not filing readiness.
    assert "record_validity\tvalid" in show_result.output
    assert "readiness\t" not in show_result.output

    # ``status`` reports filing readiness; the freshly created profile has
    # no declared activity, so it is legitimately ``blocked`` for filing.
    assert "readiness\tblocked" in status_result.output
    assert "activities.description\tmissing" in status_result.output
    assert "record_validity\t" not in status_result.output

    # The contradiction reading is gone: no single profile shows the same
    # ``readiness`` token with opposite states across the two surfaces.
    assert "readiness\tready" not in show_result.output
    assert "readiness\tready" not in status_result.output


def test_config_profile_show_refuses_when_no_active_profile() -> None:
    # Clear the active-profile precedence chain (env + pointer) so the
    # resolver returns None and the show verb refuses.
    from ....application.user_profile._orchestration import _clear_active_profile_pointer
    from ....core.config import override_settings

    _clear_active_profile_pointer()
    with override_settings(aeat_active_profile=None):
        result = _invoke_profile(("show",))
    assert result.exit_code != 0


# --- Fix 1: profile create emits visible confirmation on success ---


def test_config_profile_create_quiet_emits_confirmation() -> None:
    """``profile create --quiet`` must emit a confirmation line, not silent exit-0.

    Before fix: zero output, exit 0 — silent success indistinguishable
    from silent failure.  After fix: at least ``profile\\t<name>`` and
    ``Status\\tCreated`` is emitted so the operator knows the command
    succeeded.
    """

    result = _invoke_profile(
        (
            "create",
            "freshprofile",
            "--quiet",
            "--tax-id",
            "12345678Z",
            "--entity-type",
            "natural_person",
            "--name",
            "Test",
            "--surnames",
            "Operator",
            "--activity",
            "Design",
            "--iva-regime",
            "GENERAL",
        ),
    )

    assert result.exit_code == 0, result.output
    assert "profile\tfreshprofile" in result.output
    assert "Status\tcreated" in result.output
    assert "active_profile\tfreshprofile" in result.output
    assert "next\t" in result.output


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
    assert "profile\teditme" in result.output
    assert "Status\tupdated" in result.output


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


def test_config_profile_status_exits_nonzero_for_dangling_pointer() -> None:
    """``config profile status`` exits non-zero when the active profile
    has a dangling pointer (registered but no manifest bucket)."""

    from ....application.user_profile._orchestration import _write_active_profile_pointer

    # Write a pointer to a non-existent bucket so status sees dangling_pointer.
    _write_active_profile_pointer("phantom")

    result = _invoke_profile(("status",))

    assert result.exit_code != 0, result.output
    assert "dangling_pointer" in result.output


# --- Fix 5: NIF/CIF validation errors do not leak internal field names ---


def test_config_profile_create_nif_error_does_not_leak_internal_keys() -> None:
    """A bad NIF/CIF must produce a plain-language error without exposing
    ``prompt_key``, ``question_id``, or raw internal dict dumps."""

    result = _invoke_profile(
        (
            "create",
            "badnif",
            "--quiet",
            "--tax-id",
            "NOTANIF",
            "--name",
            "Test",
            "--activity",
            "Design",
            "--iva-regime",
            "GENERAL",
        ),
    )

    assert result.exit_code != 0
    assert "prompt_key" not in result.output
    assert "question_id" not in result.output
    # The plain-language diagnostic must be present.
    assert "NIF" in result.output or "nif" in result.output or "tax" in result.output.lower()
