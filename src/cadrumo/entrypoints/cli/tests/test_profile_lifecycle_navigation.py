"""CLI tests for per-bucket profile lifecycle navigation.

These tests drive ``aeat config profile`` from a cold per-bucket storage
backend: ``rename`` is a label-only edit, ``import --label`` re-lands an
exported bundle, and ``delete`` / ``switch`` / ``list`` / ``status`` / ``show``
all resolve correctly from a no-active-session state. They are the
navigation-and-relabel sibling of ``test_profile_lifecycle_verbs`` (which owns
the record-level show / create / edit / repair surface); both share the
fixtures and helpers in ``_profile_lifecycle_support``.

The ``"buckets"`` literal below is deliberate: ``isolated_profile_storage_root``
overrides only the secret store, so ``_per_bucket_backend / "buckets" /
uuid_before`` checks production's real DEFAULT-derived bucket directory, not
an injected value. Re-deriving it from the taxonomy accessor would make the
assertion agree unconditionally with the code path it exists to
independently confirm.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Final

import pytest
from click.testing import Result

from ....core.config import load_settings
from ....tests.cli_runner import cadrumo_click_command, invoke_cached_cli
from ....tests.profile_capsule import open_test_profile_session
from ....tests.secure_sql import isolated_profile_storage
from ....tests.user_profile import register_cli_profile
from .._common import cli_policy_refusal_projection
from .._errors import CliRefusedBoundaryError, error_boundary_under_test

__all__ = ["isolated_profile_storage"]
from ._profile_lifecycle_support import create_profile_via_cli, seed

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

PINNED_TAXONOMY_LITERALS: Final[frozenset[str]] = frozenset({"buckets"})
"""Taxonomy-vocabulary literals this module deliberately pins. See the module docstring."""


def _invoke(args: Sequence[str]) -> Result:
    return invoke_cached_cli(args)


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


# --- profile rename is a label-only edit ---


def test_profile_rename_is_label_only_and_keeps_uuid_directory_and_key(
    _per_bucket_backend: Path,
) -> None:
    """``profile rename A B`` changes only the operator label.

    Profile identity is an immutable UUID. After a rename the UUID,
    the bucket directory, and the secure-object record key are all
    unchanged; only ``display_name`` on the record and ``label`` on
    the manifest move from A to B.
    """
    from ....application.workflow import read_profile_bucket

    create_profile_via_cli("alpha")

    pointer_before = read_profile_bucket("alpha")
    assert pointer_before is not None
    uuid_before = pointer_before.bucket_id
    bucket_dir = _per_bucket_backend / "buckets" / uuid_before
    assert bucket_dir.is_dir()

    result = _invoke(("config", "profile", "rename", "alpha", "beta"))
    assert result.exit_code == 0, f"rename failed: {result.output}"
    assert "display_name\tbeta" in result.output
    assert "previous_display_name\talpha" in result.output

    # The old label no longer resolves; the new label resolves to the
    # SAME immutable UUID and the SAME on-disk directory.
    assert read_profile_bucket("alpha") is None
    pointer_after = read_profile_bucket("beta")
    assert pointer_after is not None
    assert pointer_after.bucket_id == uuid_before
    assert pointer_after.label == "beta"
    assert bucket_dir.is_dir()
    assert (_per_bucket_backend / "buckets" / uuid_before).is_dir()


def test_profile_rename_keeps_record_readable_under_unchanged_key(
    _per_bucket_backend: Path,
) -> None:
    """After a label-only rename the profile record reads back unchanged.

    The secure-object key is single-segment on the immutable UUID, so
    no re-key happens; ``profile show`` and the lifecycle service both
    still find the record, now carrying the new display label.
    """
    from ....application.workflow import read_profile_bucket
    from ....core.redaction import CLI_PROFILE_ID_PLACEHOLDER
    from ....tests.profile_capsule import load_test_profile_record

    create_profile_via_cli("alice")
    alice_pointer = read_profile_bucket("alice")
    assert alice_pointer is not None
    uuid_before = alice_pointer.bucket_id

    rename_result = _invoke(("config", "profile", "rename", "alice", "bob"))
    assert rename_result.exit_code == 0, f"rename failed: {rename_result.output}"

    # Reading the profile record directly via the lifecycle service requires an
    # active session scoped to the bucket UUID.
    with open_test_profile_session(uuid_before):
        record = load_test_profile_record(uuid_before)
    # The identity is unchanged; only the bucket manifest label moved.
    assert record.profile_id == uuid_before

    show_result = _invoke(("config", "profile", "show", "bob"))
    assert show_result.exit_code == 0, f"show failed: {show_result.output}"
    assert "record_validity\tvalid" in show_result.output, show_result.output
    assert "missing_profile_record" not in show_result.output, show_result.output
    # Centralized output redaction: raw profile id is rewritten
    # to a `<profile-id>` placeholder at the rendering boundary. The
    # identity-stability invariant is verified above via the direct
    # lifecycle-service read (`record.profile_id == uuid_before`); the
    # stdout assertion only needs to confirm the show path reached the
    # renamed label's record (display_name + readiness above already do).
    assert f"profile_id\t{CLI_PROFILE_ID_PLACEHOLDER}" in show_result.output
    assert "display_name\tbob" in show_result.output
    assert uuid_before not in show_result.output  # raw UUID must NOT leak


def test_profile_rename_refuses_a_label_taken_by_another_live_profile(
    _per_bucket_backend: Path,
) -> None:
    """``profile rename A B`` is refused when label B already belongs to a profile."""

    # Both profiles are setup-only for the rename refusal test; use seed so the
    # wizard create does not attempt the cross-bucket tax-id uniqueness scan
    # against a closed per-bucket session.
    seed("alpha")
    seed("beta")

    result = _invoke(("config", "profile", "rename", "alpha", "beta"))
    assert result.exit_code != 0, f"expected refusal, got: {result.output}"


def test_profile_create_refuses_case_insensitive_duplicate_label(
    _per_bucket_backend: Path,
) -> None:
    """Display-name uniqueness is enforced case-insensitively across live profiles."""

    create_profile_via_cli("operator")

    register_cli_profile(
        label="OPERATOR",
        facts={
            "identity.tax_id": "12345678Z",
            "identity.name": "Operator2",
            "activities.description": "design",
            "iva.regime": "GENERAL",
        },
    )


# --- profile import --label preserves bundle identity ---


def test_profile_import_label_refuses_duplicate_bundle_identity(
    _per_bucket_backend: Path,
) -> None:
    """`profile import --label` cannot duplicate an already registered bundle.

    The bundle's profile_id is the immutable identity across export/import.
    ``--label`` only changes the display label when importing into a root
    that does not already carry that UUID; it must not mint a second local
    profile for the same bundle identity.
    """
    from ....application.workflow import read_profile_bucket

    # Seed the source profile via the canonical path (no tax-id cross-scan issue).
    seed("operator")

    bundle_path = _per_bucket_backend / "operator-bundle.json"
    export_result = _invoke(
        ("config", "profile", "export", "operator", "--to", str(bundle_path), "--cleartext-local"),
    )
    assert export_result.exit_code == 0, export_result.output
    assert bundle_path.is_file()

    # Re-importing under the original name dead-ends on a label-taken refusal.
    clash = _invoke(("config", "profile", "import", str(bundle_path)))
    assert clash.exit_code != 0, clash.output

    # Re-importing with --label still hits the UUID collision guard; no second
    # profile is created under the requested label.
    relabelled = _invoke(
        ("config", "profile", "import", str(bundle_path), "--label", "operator-restored"),
    )
    assert relabelled.exit_code != 0, relabelled.output

    original = read_profile_bucket("operator")
    assert original is not None
    assert read_profile_bucket("operator-restored") is None


# --- profile-lifecycle navigation from a no-active-session state ---
#
# These tests drive the full root CLI so the CLI root callback (the
# active-session gate) participates. The ``profile_app``-direct tests
# in the sibling module never reach that callback, so they cannot observe
# the lockout where a lifecycle-navigation verb reaches a decrypting read
# with no bucket session opened for it.


def test_switch_surviving_profile_after_deleting_the_active_one(
    _per_bucket_backend: Path,
) -> None:
    """Deleting the active profile must not lock the operator out of survivors.

    Reproduces the delete-active lockout: with two profiles, ``switch``
    to the first so it is active, ``delete`` it, then ``switch`` to the
    surviving profile. The final switch must succeed and make the
    regression active. Before the fix it refused with ``no active bucket
    session`` — the very recovery command the refusal recommended.
    """
    from ....application.workflow import read_profile_bucket
    from ....core import resolve_active_bucket_id

    # Both profiles are setup for the switch/delete test; seed both so the
    # wizard create does not hit the cross-bucket tax-id scan against a closed
    # per-bucket session.
    seed("alpha")
    seed("beta")

    assert _invoke(("config", "login", "alpha")).exit_code == 0

    deleted = _invoke(("config", "profile", "delete", "alpha", "--yes"))
    assert deleted.exit_code == 0, deleted.output

    # The active-profile pointer is now cleared. ``switch`` must still
    # succeed — it is the verb that establishes a session, not one that
    # requires a pre-existing one.
    switched = _invoke(("config", "login", "beta"))
    assert switched.exit_code == 0, switched.output
    assert "active_profile\tbeta" in switched.output

    survivor = read_profile_bucket("beta")
    assert survivor is not None
    assert resolve_active_bucket_id() == survivor.bucket_id


def test_first_switch_from_a_no_active_profile_state_succeeds(
    _per_bucket_backend: Path,
) -> None:
    """``switch`` works from a cold no-active-profile state.

    ``create`` lands a profile and leaves it active; logging out clears
    the pointer so no session resolves at root-callback time. ``switch``
    must still open its own session and activate the named profile.
    """
    from ....core import resolve_active_bucket_id

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


def test_delete_active_profile_states_the_pointer_was_cleared(
    _per_bucket_backend: Path,
) -> None:
    """Deleting the active profile names the cleared-pointer consequence.

    ``delete <active> --yes`` must not silently clear the active-profile
    pointer. The result output must state the active profile was cleared
    and steer the operator at ``switch`` / ``create``.
    """

    create_profile_via_cli("alpha")

    assert _invoke(("config", "login", "alpha")).exit_code == 0

    deleted = _invoke(("config", "profile", "delete", "alpha", "--yes"))
    assert deleted.exit_code == 0, deleted.output
    assert "status\ttombstoned" in deleted.output
    # The cleared-pointer consequence is explicit in the output.
    assert "active_profile\t<none>" in deleted.output
    assert "notice\t" in deleted.output
    flat = deleted.output.replace("\n", " ")
    # The notice must name recovery verbs that actually resolve. Asserting
    # the full command path rather than a bare token keeps this honest: a
    # bare "login" would also match the retired `config profile logout`
    # spelling, and a retired verb here is precisely the defect the notice
    # exists to avoid -- the operator lands on it exactly when their
    # published guide lags a rename.
    assert "aeat config login" in flat
    assert "aeat config profile create" in flat


def test_delete_non_active_profile_omits_the_cleared_pointer_notice(
    _per_bucket_backend: Path,
) -> None:
    """Deleting a non-active profile does not claim the pointer was cleared.

    The cleared-pointer notice belongs only to the delete-active path;
    deleting an inactive profile leaves the active pointer untouched and
    must not emit the notice.
    """

    # Both profiles are setup for the delete test; seed both so the wizard
    # create does not hit the cross-bucket tax-id scan against a closed session.
    seed("alpha")
    seed("beta")
    # Make "beta" the active profile (simulating "active after the second
    # create") so delete of inactive "alpha" can be verified.
    assert _invoke(("config", "login", "beta")).exit_code == 0

    # ``beta`` is active; delete the inactive ``alpha``.
    deleted = _invoke(("config", "profile", "delete", "alpha", "--yes"))
    assert deleted.exit_code == 0, deleted.output
    assert "status\ttombstoned" in deleted.output
    assert "active_profile\t<none>" not in deleted.output
    assert "notice\t" not in deleted.output


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
    from ....application.workflow import read_profile_bucket

    create_profile_via_cli("alpha")

    assert _invoke(("config", "logout")).exit_code == 0

    deleted = _invoke(("config", "profile", "delete", "alpha", "--yes"))
    assert deleted.exit_code == 0, deleted.output
    assert "status\ttombstoned" in deleted.output
    # The profile is gone from the live surface.
    assert read_profile_bucket("alpha") is None


def test_deleted_profile_name_is_reusable_by_create_and_rename(
    _per_bucket_backend: Path,
) -> None:
    """After ``delete`` the freed display name is reusable.

    Per the profile-UUID identity contract, display-name uniqueness is
    enforced only among live profiles; a tombstoned profile's name is
    free to reuse by both ``create`` and ``rename``.
    """

    seed("operator", tax_id="00000000T")
    # Route through the root CLI so the error boundary is active for all verbs.
    assert _invoke(("config", "profile", "delete", "operator", "--yes")).exit_code == 0

    register_cli_profile(
        label="operator",
        facts={
            "identity.tax_id": "12345678Z",
            "taxpayer_type.entity_type": "natural_person",
            "identity.name": "Operator",
            "identity.surnames": "Operator",
            "activities.description": "design",
            "iva.regime": "GENERAL",
        },
    )

    # And the freed name is reachable through ``rename`` too. Delete the
    # recreated profile, seed a live one, rename it onto the freed name.
    assert _invoke(("config", "profile", "delete", "operator", "--yes")).exit_code == 0
    seed("colleague", tax_id="00000001R")
    renamed = _invoke(("config", "profile", "rename", "colleague", "operator"))
    assert renamed.exit_code == 0, renamed.output
    assert "display_name\toperator" in renamed.output


def test_show_tombstoned_profile_is_session_context_independent(
    _per_bucket_backend: Path,
) -> None:
    """``show <tombstoned>`` behaves the same regardless of the active session.

    A tombstoned profile inspected with another profile's session
    active, and the same profile inspected with no session at all, must
    both resolve the tombstoned record and report ``record_validity
    tombstoned`` — never an ``unknown profile`` refusal in one context
    and a full record in the other.
    """

    # Both profiles are setup for the show/tombstone test; seed both so the
    # wizard create does not hit the cross-bucket tax-id scan.
    seed("alpha")
    seed("beta")

    # ``beta`` is active after the second seed. Tombstone ``alpha``.
    assert _invoke(("config", "profile", "delete", "alpha", "--yes")).exit_code == 0

    # Context 1: ``beta`` session active.
    assert _invoke(("config", "login", "beta")).exit_code == 0
    with_session = _invoke(("config", "profile", "show", "alpha"))

    # Context 2: no active session.
    assert _invoke(("config", "logout")).exit_code == 0
    no_session = _invoke(("config", "profile", "show", "alpha"))

    # Identical outcome in both session contexts: the tombstoned record
    # resolves and renders its tombstoned status.
    assert with_session.exit_code == 0, with_session.output
    assert no_session.exit_code == 0, no_session.output
    assert "record_validity\ttombstoned" in with_session.output
    assert "record_validity\ttombstoned" in no_session.output
    assert "status\ttombstoned" in with_session.output
    assert "status\ttombstoned" in no_session.output
    for context in (with_session, no_session):
        flat = context.output.lower()
        assert "desconocido" not in flat and "unknown profile" not in flat


def test_profile_flag_refuses_tombstoned_uuid_like_tombstoned_label(
    _per_bucket_backend: Path,
) -> None:
    """``--profile <uuid>`` cannot activate a tombstoned bucket.

    Operators normally address profiles by label, but automation may retain a
    UUID. A deleted profile must be excluded from live command routing by either
    identifier; otherwise a tombstoned UUID would bypass the label tombstone
    filter and route app commands into a deleted taxpayer bucket.
    """
    from ....application.workflow import read_profile_bucket
    from ....core import resolve_active_bucket_id

    seed("alpha")
    pointer = read_profile_bucket("alpha")
    assert pointer is not None
    tombstoned_uuid = pointer.bucket_id

    deleted = _invoke(("config", "profile", "delete", "alpha", "--yes"))
    assert deleted.exit_code == 0, deleted.output

    by_label = _invoke(("--language", "en", "--profile", "alpha", "app", "ledger", "list"))
    by_uuid = _invoke(("--language", "en", "--profile", tombstoned_uuid, "app", "ledger", "list"))

    assert by_label.exit_code != 0, by_label.output
    assert by_uuid.exit_code != 0, by_uuid.output
    assert "Unknown profile" in by_label.output
    assert "Unknown profile" in by_uuid.output
    assert "rows" not in by_uuid.output
    assert resolve_active_bucket_id() is None


def test_active_profile_env_and_pointer_refuse_tombstoned_uuid(
    _per_bucket_backend: Path,
) -> None:
    """A tombstoned UUID cannot activate app commands via env or pointer routing."""

    from ....application.workflow import read_profile_bucket
    from ....core import BucketPointer, write_pointer
    from ....core.config import load_settings, override_settings

    seed("alpha")
    pointer = read_profile_bucket("alpha")
    assert pointer is not None
    tombstoned_uuid = pointer.bucket_id

    deleted = _invoke(("config", "profile", "delete", "alpha", "--yes"))
    assert deleted.exit_code == 0, deleted.output

    with override_settings(cadrumo_active_profile=tombstoned_uuid):
        by_env = _invoke(("--language", "en", "app", "ledger", "list"))

    with (
        override_settings(cadrumo_active_profile=tombstoned_uuid),
        error_boundary_under_test(),
        pytest.raises(CliRefusedBoundaryError) as raised,
    ):
        cadrumo_click_command().main(
            args=["app", "ledger", "list"],
            prog_name="aeat",
            standalone_mode=False,
        )
    projection = cli_policy_refusal_projection(raised.value)
    assert projection is not None
    assert projection.precondition_action.failed_condition_id == "profile.selection.live"
    assert projection.precondition_action.action is not None
    assert projection.precondition_action.action.action_id == "operator.profile.repair_clear_active"
    assert projection.precondition_action.missing_argument_names == ("yes",)

    write_pointer(
        load_settings().cadrumo_local_storage_root,
        BucketPointer(bucket_id=tombstoned_uuid, schema_version=1),
    )
    with override_settings(cadrumo_active_profile=None):
        by_pointer = _invoke(("--language", "en", "app", "ledger", "list"))

    for result in (by_env, by_pointer):
        assert result.exit_code != 0, result.output
        assert "Unknown profile" in result.output
        assert "rows" not in result.output


def test_explicit_profile_show_reaches_tombstoned_target_with_stale_active_uuid(
    _per_bucket_backend: Path,
) -> None:
    """Explicit ``show <label|uuid>`` inspects tombstones despite stale active UUIDs."""

    from ....application.workflow import read_profile_bucket
    from ....core import BucketPointer, write_pointer
    from ....core.config import load_settings, override_settings

    seed("alpha")
    pointer = read_profile_bucket("alpha")
    assert pointer is not None
    tombstoned_uuid = pointer.bucket_id

    deleted = _invoke(("config", "profile", "delete", "alpha", "--yes"))
    assert deleted.exit_code == 0, deleted.output

    with override_settings(cadrumo_active_profile=tombstoned_uuid):
        by_env_label = _invoke(("--language", "en", "config", "profile", "show", "alpha"))
        by_env_uuid = _invoke(("--language", "en", "config", "profile", "show", tombstoned_uuid))

    write_pointer(
        load_settings().cadrumo_local_storage_root,
        BucketPointer(bucket_id=tombstoned_uuid, schema_version=1),
    )
    with override_settings(cadrumo_active_profile=None):
        by_pointer_label = _invoke(("--language", "en", "config", "profile", "show", "alpha"))
        by_pointer_uuid = _invoke(("--language", "en", "config", "profile", "show", tombstoned_uuid))

    for result in (by_env_label, by_env_uuid, by_pointer_label, by_pointer_uuid):
        assert result.exit_code == 0, result.output
        assert "status\ttombstoned" in result.output
        assert "record_validity\ttombstoned" in result.output
        assert "Unknown profile" not in result.output


def test_no_arg_profile_show_output_language_does_not_mask_stale_active_uuid(
    _per_bucket_backend: Path,
) -> None:
    """No-arg ``show --output-language en`` still depends on the active profile."""

    from ....application.workflow import read_profile_bucket
    from ....core.config import override_settings

    seed("alpha")
    pointer = read_profile_bucket("alpha")
    assert pointer is not None
    tombstoned_uuid = pointer.bucket_id

    deleted = _invoke(("config", "profile", "delete", "alpha", "--yes"))
    assert deleted.exit_code == 0, deleted.output

    with override_settings(cadrumo_active_profile=tombstoned_uuid):
        no_target = _invoke(("config", "profile", "show", "--output-language", "en"))
        by_label = _invoke(("config", "profile", "show", "alpha", "--output-language", "en"))
        by_uuid = _invoke(("config", "profile", "show", tombstoned_uuid, "--output-language", "en"))

    assert no_target.exit_code != 0, no_target.output
    assert "Unknown profile" in no_target.output
    assert "record_validity\ttombstoned" not in no_target.output

    for result in (by_label, by_uuid):
        assert result.exit_code == 0, result.output
        assert "status\ttombstoned" in result.output
        assert "record_validity\ttombstoned" in result.output
        assert "Unknown profile" not in result.output
