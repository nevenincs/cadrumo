"""CLI surface tests for `aeat config profile {switch, show, delete, duplicate, rename}`."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner, Result

from aeat.adapters.persistence.storage.bucket._layout import provision_bucket_directory
from aeat.adapters.persistence.storage.bucket._manifest import (
    BucketLifecycleStatus,
    BucketManifest,
    ManifestKdfParams,
)
from aeat.adapters.persistence.storage.bucket._manifest_io import write_manifest
from aeat.application.user_profile._testing import register_minimal_profile
from aeat.application.workflow._persistence import workflow_state_repository
from aeat.core.config import load_settings
from aeat.entrypoints.cli import app as root_app
from aeat.entrypoints.cli._config import profile_app, repair_app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def _stage_bucket_manifest(bucket_id: str, *, label: str) -> None:
    """Stage a bucket directory + manifest with no secure record.

    A bucket directory and plaintext manifest with no encrypted
    profile-value row is exactly the ``missing_profile_record`` torn
    state these CLI verbs must detect; this helper materialises that
    state directly through the bucket-layout primitives, since
    ``ProfileRepository`` always writes the record alongside.
    """

    root = load_settings().aeat_local_storage_root
    paths = provision_bucket_directory(root, bucket_id)
    write_manifest(
        paths,
        BucketManifest(
            bucket_id=bucket_id,
            label=label,
            created_at=datetime.now(UTC),
            last_unlocked_at=None,
            kdf_params=ManifestKdfParams(
                algorithm="argon2id",
                version=0x13,
                memory_cost=19_456,
                time_cost=2,
                parallelism=1,
                salt=b"0123456789abcdef",
                output_length=32,
            ),
            recovery_enrolled=False,
            schema_version=1,
            status=BucketLifecycleStatus.ACTIVE,
        ),
    )


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    from aeat.adapters.persistence.storage import get_master_key_provider
    from aeat.adapters.persistence.storage.sql.engine import dispose_engine

    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'profile-verbs.db').as_posix()}")
    monkeypatch.setenv("AEAT_LOCAL_STORAGE_ROOT", str(tmp_path))
    monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "unsecured")
    monkeypatch.setenv("AEAT_ALLOW_UNENCRYPTED", "1")
    dispose_engine()
    try:
        with get_master_key_provider():
            yield
    finally:
        dispose_engine()


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


def _seed(name: str = "default", *, tax_id: str | None = None) -> None:
    # ``register_minimal_profile`` derives a profile-unique NIF by
    # default so two ``_seed`` calls never collide on the
    # duplicate-tax-id refusal; a test that asserts a specific tax id
    # passes it explicitly.
    overrides = {"identity.tax_id": tax_id} if tax_id is not None else None
    workflow_state_repository().update(
        lambda state: register_minimal_profile(state, profile_id=name, overrides=overrides)
    )


def _json_payload(result: Result) -> dict[str, object]:
    match = re.search(r"\{.*\}", result.output, re.DOTALL)
    assert match, result.output
    return json.loads(match.group(0))


def test_config_profile_switch_activates_existing_profile(cli_runner: CliRunner) -> None:
    _seed("operator")
    _seed("spouse")
    result = cli_runner.invoke(profile_app, ["switch", "operator"])
    assert result.exit_code == 0, result.output
    assert "active_profile\toperator" in result.output


def test_config_profile_switch_refuses_unknown_profile(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(profile_app, ["switch", "ghost"])
    assert result.exit_code != 0


def test_config_profile_switch_reports_manifest_without_profile_record(cli_runner: CliRunner) -> None:
    _stage_bucket_manifest("operator", label="operator")

    result = cli_runner.invoke(profile_app, ["switch", "operator"])

    assert result.exit_code == 2, result.output
    assert "readiness\tmissing_profile_record" in result.output
    assert "profile_record\tmissing" in result.output
    assert "unknown profile" not in result.output.lower()


def test_config_profile_show_does_not_suggest_switch_for_missing_record(cli_runner: CliRunner) -> None:
    _stage_bucket_manifest("operator", label="operator")

    result = cli_runner.invoke(profile_app, ["show", "operator"])

    assert result.exit_code == 2, result.output
    assert "readiness\tmissing_profile_record" in result.output
    assert "next_action\taeat config repair profile --profile operator" in result.output
    assert "next_action\taeat config profile switch operator" not in result.output


def test_config_profile_create_refuses_manifest_only_profile(cli_runner: CliRunner) -> None:
    _stage_bucket_manifest("operator", label="operator")

    result = cli_runner.invoke(
        profile_app,
        [
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
        ],
    )

    assert result.exit_code != 0
    assert "already exists" in result.output


def test_repair_profile_named_active_clear_active_clears_pointer(cli_runner: CliRunner, tmp_path: Path) -> None:
    from aeat.application.user_profile._orchestration import _write_active_profile_pointer
    from aeat.core._bucket_pointer_io import read_pointer

    _stage_bucket_manifest("operator", label="operator")
    _write_active_profile_pointer("operator")

    result = cli_runner.invoke(repair_app, ["profile", "--profile", "operator", "--clear-active", "--yes"])

    assert result.exit_code == 0, result.output
    assert "cleared_pointer\tTrue" in result.output
    assert read_pointer(tmp_path) is None


def test_config_profile_create_refuses_existing_profile(cli_runner: CliRunner) -> None:
    _seed("operator")

    result = cli_runner.invoke(
        profile_app,
        [
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
        ],
    )

    assert result.exit_code != 0
    assert "already exists" in result.output


def test_config_profile_create_bare_name_refusal_names_both_recovery_paths(
    cli_runner: CliRunner,
) -> None:
    """A first-timer running `profile create NAME` with no flags, in a
    shell with no interactive terminal, must get a refusal that spells
    out BOTH recovery paths in plain language and leaks no internals.

    Before fix: the refusal mentioned only the interactive path, then a
    trailing `-> Run` line that referenced `--quiet` as if the operator
    had chosen it. After fix: the message itself names the interactive
    path AND the one-step flag path, and never claims `--quiet` was a
    precondition the operator violated.
    """

    result = cli_runner.invoke(root_app, ["config", "profile", "create", "Cafe Luna"])

    assert result.exit_code != 0
    output = result.output
    # Both concrete recovery paths are named in the message body.
    assert "aeat config profile create NAME" in output
    assert "--quiet --tax-id NIF --activity ACTIVITY" in output
    # No internal tokens leak into the operator-facing refusal.
    assert "flow_id" not in output
    assert "('tax-id'" not in output
    assert "missing:" not in output


def test_config_profile_create_quiet_without_flags_names_the_missing_flags(
    cli_runner: CliRunner,
) -> None:
    """`profile create NAME --quiet` with the required values omitted
    must name the actual flags to add (`--tax-id`, `--activity`), not a
    raw Python identifier tuple, and must not leak `flow_id`.
    """

    result = cli_runner.invoke(root_app, ["config", "profile", "create", "Cafe Luna", "--quiet"])

    assert result.exit_code != 0
    output = result.output
    assert "--tax-id" in output
    assert "--activity" in output
    # The internal flow id and the raw missing-id tuple never surface.
    assert "flow_id" not in output
    assert "('tax-id'" not in output
    assert "missing:" not in output


def test_config_profile_edit_refuses_missing_profile_without_creating_bucket(cli_runner: CliRunner) -> None:
    from aeat.application.workflow._profile_bucket_scan import read_profile_bucket

    result = cli_runner.invoke(
        profile_app,
        [
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
        ],
    )

    assert result.exit_code != 0
    assert "does not exist" in result.output
    assert read_profile_bucket("ghost") is None


def test_config_profile_switch_emits_profile_activated_event(cli_runner: CliRunner) -> None:
    """`config profile switch` records a typed PROFILE_ACTIVATED event in the
    bucket-event-history catalogue so downstream auditors can replay
    the activation timeline. Distinct from PROFILE_SELECTED (which
    captures workflow-state-level selection).
    """

    from aeat.domain.buckets import BucketEventHistoryRepository, BucketEventType

    _seed("operator")
    result = cli_runner.invoke(profile_app, ["switch", "operator"])
    assert result.exit_code == 0, result.output

    catalogue = BucketEventHistoryRepository().load()
    matching = [
        event
        for event in catalogue.events.values()
        if event.event_type is BucketEventType.PROFILE_ACTIVATED
        and event.object_id == "operator"
    ]
    assert matching, [event.event_type for event in catalogue.events.values()]
    assert matching[-1].payload["profile_id"] == "operator"
    assert matching[-1].payload["active_profile"] == "operator"


def test_config_profile_show_emits_active_profile_facts(cli_runner: CliRunner) -> None:
    _seed("operator", tax_id="00000000T")
    result = cli_runner.invoke(profile_app, ["show"])
    assert result.exit_code == 0, result.output
    assert "profile_id\toperator" in result.output
    assert "identity.tax_id\t00000000T" in result.output


def test_config_profile_show_named_profile_includes_canonical_facts(cli_runner: CliRunner) -> None:
    _seed("operator", tax_id="00000001R")
    _seed("spouse", tax_id="00000000T")
    result = cli_runner.invoke(profile_app, ["show", "spouse"])
    assert result.exit_code == 0, result.output
    assert "profile_id\tspouse" in result.output
    assert "identity.tax_id\t00000000T" in result.output
    assert "iva.regime\tGENERAL" in result.output
    assert "tax_residence.ccaa\tmadrid" in result.output


def test_config_profile_delete_requires_yes(cli_runner: CliRunner) -> None:
    _seed("operator")
    result = cli_runner.invoke(profile_app, ["delete", "operator"])
    assert result.exit_code != 0


def test_config_profile_delete_tombstones_with_yes(cli_runner: CliRunner) -> None:
    _seed("operator")
    result = cli_runner.invoke(profile_app, ["delete", "operator", "--yes"])
    assert result.exit_code == 0, result.output
    assert "status\ttombstoned" in result.output
    from aeat.application.workflow._models import resolve_active_bucket_id

    assert resolve_active_bucket_id() is None


def test_config_profile_list_excludes_a_tombstoned_profile(cli_runner: CliRunner) -> None:
    """After ``delete`` the profile leaves ``config profile list``.

    Closes the leak where a tombstoned profile stayed visible in the
    listing, indistinguishable from a live one.
    """

    _seed("operator")
    assert cli_runner.invoke(profile_app, ["delete", "operator", "--yes"]).exit_code == 0
    result = cli_runner.invoke(profile_app, ["list"])
    assert result.exit_code == 0, result.output
    assert "operator" not in result.output
    assert "<none>" in result.output


def test_config_profile_switch_refuses_a_tombstoned_profile(cli_runner: CliRunner) -> None:
    """Switching to a tombstoned profile is refused, not silently activated.

    Closes the leak where ``switch`` made a deleted profile the active
    one with exit code 0.
    """

    from aeat.application.workflow._models import resolve_active_bucket_id

    _seed("operator")
    assert cli_runner.invoke(profile_app, ["delete", "operator", "--yes"]).exit_code == 0
    result = cli_runner.invoke(profile_app, ["switch", "operator"])
    assert result.exit_code != 0, result.output
    # The tombstoned profile was not made active.
    assert resolve_active_bucket_id() is None


def test_config_profile_show_reports_a_tombstoned_profile_as_tombstoned(
    cli_runner: CliRunner,
) -> None:
    """``show`` of a tombstoned profile renders ``readiness tombstoned``.

    Closes the self-contradiction where ``show`` reported
    ``readiness ready issues=0`` directly above ``status tombstoned``.
    """

    _seed("operator")
    assert cli_runner.invoke(profile_app, ["delete", "operator", "--yes"]).exit_code == 0
    result = cli_runner.invoke(profile_app, ["show", "operator"])
    assert result.exit_code == 0, result.output
    assert "status\ttombstoned" in result.output
    assert "readiness\ttombstoned" in result.output
    assert "readiness\tready" not in result.output


def test_deleted_profile_name_is_reusable_by_create_and_rename(
    cli_runner: CliRunner,
) -> None:
    """After ``delete`` the freed display name is reusable.

    Per the profile-UUID-identity ADR, display-name uniqueness is
    enforced only among live profiles; a tombstoned profile's name is
    free to reuse by both ``create`` and ``rename``.
    """

    _seed("operator", tax_id="00000000T")
    assert cli_runner.invoke(profile_app, ["delete", "operator", "--yes"]).exit_code == 0

    created = cli_runner.invoke(
        profile_app,
        [
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
        ],
    )
    assert created.exit_code == 0, created.output

    # And the freed name is reachable through ``rename`` too. Delete the
    # recreated profile, seed a live one, rename it onto the freed name.
    assert cli_runner.invoke(profile_app, ["delete", "operator", "--yes"]).exit_code == 0
    _seed("colleague", tax_id="00000001R")
    renamed = cli_runner.invoke(profile_app, ["rename", "colleague", "operator"])
    assert renamed.exit_code == 0, renamed.output
    assert "display_name\toperator" in renamed.output


def test_config_profile_duplicate_copies_to_new_id(cli_runner: CliRunner) -> None:
    import re

    _seed("operator")
    result = cli_runner.invoke(
        profile_app,
        ["duplicate", "operator", "operator-spouse", "--display-name", "Spouse"],
    )
    assert result.exit_code == 0, result.output
    # The duplicate lands under a freshly minted UUID identity and the
    # supplied --display-name as its operator label.
    uuid_re = r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
    match = re.search(r"target_profile_id\t(\S+)", result.output)
    assert match and re.fullmatch(uuid_re, match.group(1)), result.output
    assert "display_name\tSpouse" in result.output
    from aeat.application.workflow._profile_bucket_scan import read_profile_bucket
    assert read_profile_bucket("Spouse") is not None


def test_config_profile_duplicate_refuses_existing_target(cli_runner: CliRunner) -> None:
    _seed("operator")
    _seed("operator-spouse")
    result = cli_runner.invoke(profile_app, ["duplicate", "operator", "operator-spouse"])
    assert result.exit_code != 0


def test_config_profile_show_runs_validation_inline(cli_runner: CliRunner) -> None:
    _seed("operator")
    result = cli_runner.invoke(profile_app, ["show"])
    assert result.exit_code == 0, result.output
    assert "profile_id\toperator" in result.output
    assert "readiness\tready" in result.output


def test_config_profile_show_refuses_when_no_active_profile(cli_runner: CliRunner) -> None:
    # Clear the active-profile precedence chain (env + pointer) so the
    # resolver returns None and the show verb refuses.
    from aeat.application.user_profile._orchestration import _clear_active_profile_pointer
    from aeat.core.config import override_settings

    _clear_active_profile_pointer()
    with override_settings(aeat_active_profile=None):
        result = cli_runner.invoke(profile_app, ["show"])
    assert result.exit_code != 0


# --- Fix 1: profile create emits visible confirmation on success ---


def test_config_profile_create_quiet_emits_confirmation(cli_runner: CliRunner) -> None:
    """``profile create --quiet`` must emit a confirmation line, not silent exit-0.

    Before fix: zero output, exit 0 — silent success indistinguishable
    from silent failure.  After fix: at least ``profile\\t<name>`` and
    ``status\\tcreated`` are emitted so the operator knows the command
    succeeded.
    """

    result = cli_runner.invoke(
        profile_app,
        [
            "create",
            "freshprofile",
            "--quiet",
            "--tax-id",
            "12345678Z",
            "--name",
            "Test",
            "--activity",
            "Design",
            "--iva-regime",
            "GENERAL",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "profile\tfreshprofile" in result.output
    assert "status\tcreated" in result.output
    assert "active_profile\tfreshprofile" in result.output
    assert "next\t" in result.output


def test_config_profile_edit_quiet_emits_updated_confirmation(cli_runner: CliRunner) -> None:
    """``profile edit --quiet`` must emit a confirmation line with ``status\\tupdated``."""

    _seed("editme")

    result = cli_runner.invoke(
        profile_app,
        [
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
        ],
    )

    assert result.exit_code == 0, result.output
    assert "profile\teditme" in result.output
    assert "status\tupdated" in result.output


def test_config_profile_edit_non_tty_recovery_hint_points_at_edit(cli_runner: CliRunner) -> None:
    """A non-interactive ``profile edit`` (no flags) refuses with an edit-specific hint.

    The shared no-console message names ``profile create``, which reads
    as a destructive replacement when reached via ``profile edit``. The
    refusal must instead name the non-interactive ``profile edit``
    patch form so the operator does not believe their profile will be
    overwritten.
    """

    _seed("editme")

    result = cli_runner.invoke(profile_app, ["edit", "editme"])

    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output
    flat = result.output.replace("\n", " ")
    # The recovery hint names the non-interactive `profile edit` form.
    assert "profile edit editme --quiet" in flat
    # It must NOT steer the operator to a destructive `profile create`.
    assert "profile create" not in flat


# --- Fix 3: degraded profile status exits non-zero ---


def test_config_profile_status_exits_nonzero_for_dangling_pointer(cli_runner: CliRunner) -> None:
    """``config profile status`` exits non-zero when the active profile
    has a dangling pointer (registered but no manifest bucket)."""

    from aeat.application.user_profile._orchestration import _write_active_profile_pointer

    # Write a pointer to a non-existent bucket so status sees dangling_pointer.
    _write_active_profile_pointer("phantom")

    result = cli_runner.invoke(profile_app, ["status"])

    assert result.exit_code != 0, result.output
    assert "dangling_pointer" in result.output


# --- Fix 5: NIF/CIF validation errors do not leak internal field names ---


def test_config_profile_create_nif_error_does_not_leak_internal_keys(cli_runner: CliRunner) -> None:
    """A bad NIF/CIF must produce a plain-language error without exposing
    ``prompt_key``, ``question_id``, or raw internal dict dumps."""

    result = cli_runner.invoke(
        profile_app,
        [
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
        ],
    )

    assert result.exit_code != 0
    assert "prompt_key" not in result.output
    assert "question_id" not in result.output
    # The plain-language diagnostic must be present.
    assert "NIF" in result.output or "nif" in result.output or "tax" in result.output.lower()


# --- profile rename is a label-only edit ---


@pytest.fixture
def _per_bucket_backend(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Per-bucket storage (no global AEAT_DATABASE_URL).

    Each profile bucket resolves its own SQLite file from the
    active-profile pointer chain, the production cold-start path.
    Tests using this fixture must NOT also rely on the autouse
    ``_isolated_backend`` fixture that hard-wires ``AEAT_DATABASE_URL``.
    """
    from aeat.adapters.persistence.storage.sql.engine import dispose_engine

    monkeypatch.delenv("AEAT_DATABASE_URL", raising=False)
    monkeypatch.setenv("AEAT_LOCAL_STORAGE_ROOT", str(tmp_path))
    monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "unsecured")
    monkeypatch.setenv("AEAT_ALLOW_UNENCRYPTED", "1")
    dispose_engine()
    try:
        yield tmp_path
    finally:
        dispose_engine()


_NIF_CONTROL_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"


def _distinct_nif(name: str) -> str:
    """Return a checksum-valid NIF derived deterministically from ``name``.

    ``profile create`` refuses two profiles that share a tax id, so a
    test creating several profiles needs a distinct, valid NIF per
    profile rather than one hard-coded literal.
    """

    import hashlib

    number = int(hashlib.sha256(name.encode("utf-8")).hexdigest(), 16) % 100_000_000
    return f"{number:08d}{_NIF_CONTROL_LETTERS[number % 23]}"


def _create_via_cli(runner: CliRunner, name: str, *, tax_id: str | None = None) -> None:
    result = runner.invoke(
        root_app,
        [
            "config", "profile", "create", name,
            "--quiet",
            "--tax-id", tax_id or _distinct_nif(name),
            "--name", name.capitalize(),
            "--activity", "design",
            "--iva-regime", "GENERAL",
        ],
    )
    assert result.exit_code == 0, f"create {name!r} failed: {result.output}"


def test_profile_rename_is_label_only_and_keeps_uuid_directory_and_key(
    _per_bucket_backend: Path,
) -> None:
    """``profile rename A B`` changes only the operator label.

    Profile identity is an immutable UUID. After a rename the UUID,
    the bucket directory, and the secure-object record key are all
    unchanged; only ``display_name`` on the record and ``label`` on
    the manifest move from A to B.
    """
    from aeat.adapters.persistence.storage.sql.engine import dispose_engine
    from aeat.application.workflow._profile_bucket_scan import read_profile_bucket

    runner = CliRunner()
    _create_via_cli(runner, "alpha")

    pointer_before = read_profile_bucket("alpha")
    assert pointer_before is not None
    uuid_before = pointer_before.bucket_id
    bucket_dir = _per_bucket_backend / "buckets" / uuid_before
    assert bucket_dir.is_dir()

    dispose_engine()
    result = runner.invoke(root_app, ["config", "profile", "rename", "alpha", "beta"])
    assert result.exit_code == 0, f"rename failed: {result.output}"
    assert "display_name\tbeta" in result.output
    assert "previous_display_name\talpha" in result.output

    dispose_engine()
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
    from aeat.adapters.persistence.storage.sql.engine import dispose_engine
    from aeat.application.user_profile._orchestration import build_lifecycle_service
    from aeat.application.workflow._profile_bucket_scan import read_profile_bucket

    runner = CliRunner()
    _create_via_cli(runner, "alice")
    uuid_before = read_profile_bucket("alice").bucket_id

    dispose_engine()
    rename_result = runner.invoke(root_app, ["config", "profile", "rename", "alice", "bob"])
    assert rename_result.exit_code == 0, f"rename failed: {rename_result.output}"

    dispose_engine()
    svc = build_lifecycle_service(bucket_id=uuid_before)
    record = svc.read(uuid_before)
    # The identity is unchanged; only the label moved.
    assert record.profile_id == uuid_before
    assert record.display_name == "bob"

    dispose_engine()
    show_result = runner.invoke(root_app, ["config", "profile", "show", "bob"])
    assert show_result.exit_code == 0, f"show failed: {show_result.output}"
    assert "readiness\tready" in show_result.output, show_result.output
    assert "missing_profile_record" not in show_result.output, show_result.output
    assert f"profile_id\t{uuid_before}" in show_result.output


def test_profile_rename_refuses_a_label_taken_by_another_live_profile(
    _per_bucket_backend: Path,
) -> None:
    """``profile rename A B`` is refused when label B already belongs to a profile."""
    from aeat.adapters.persistence.storage.sql.engine import dispose_engine

    runner = CliRunner()
    _create_via_cli(runner, "alpha")
    _create_via_cli(runner, "beta")

    dispose_engine()
    result = runner.invoke(root_app, ["config", "profile", "rename", "alpha", "beta"])
    assert result.exit_code != 0, f"expected refusal, got: {result.output}"


def test_profile_create_refuses_case_insensitive_duplicate_label(
    _per_bucket_backend: Path,
) -> None:
    """Display-name uniqueness is enforced case-insensitively across live profiles."""
    from aeat.adapters.persistence.storage.sql.engine import dispose_engine

    runner = CliRunner()
    _create_via_cli(runner, "operator")

    dispose_engine()
    result = runner.invoke(
        root_app,
        [
            "config", "profile", "create", "OPERATOR",
            "--quiet",
            "--tax-id", "12345678Z",
            "--name", "Operator2",
            "--activity", "design",
            "--iva-regime", "GENERAL",
        ],
    )
    assert result.exit_code != 0, f"expected case-insensitive refusal, got: {result.output}"


# --- profile import --label re-imports an exported profile ---


def test_profile_import_label_lands_second_copy_under_new_name(
    _per_bucket_backend: Path,
) -> None:
    """`profile import --label` imports an exported bundle under a fresh name.

    Re-importing an exported profile into a storage root that already
    carries it must not dead-end on a duplicate-label refusal. `--label`
    lands the second copy under a new operator-facing name while still
    minting its own immutable UUID identity.
    """
    from aeat.adapters.persistence.storage.sql.engine import dispose_engine
    from aeat.application.workflow._profile_bucket_scan import read_profile_bucket

    runner = CliRunner()
    _create_via_cli(runner, "operator")

    dispose_engine()
    bundle_path = _per_bucket_backend / "operator-bundle.json"
    export_result = runner.invoke(
        root_app,
        ["config", "profile", "export", "operator", "--to", str(bundle_path)],
    )
    assert export_result.exit_code == 0, export_result.output
    assert bundle_path.is_file()

    # Re-importing under the original name dead-ends on a refusal.
    dispose_engine()
    clash = runner.invoke(root_app, ["config", "profile", "import", str(bundle_path)])
    assert clash.exit_code != 0, clash.output

    # Re-importing with --label lands a fresh copy.
    dispose_engine()
    relabelled = runner.invoke(
        root_app,
        ["config", "profile", "import", str(bundle_path), "--label", "operator-restored"],
    )
    assert relabelled.exit_code == 0, relabelled.output
    assert "display_name\toperator-restored" in relabelled.output

    original = read_profile_bucket("operator")
    restored = read_profile_bucket("operator-restored")
    assert original is not None
    assert restored is not None
    # Distinct buckets, distinct minted UUID identities.
    assert original.bucket_id != restored.bucket_id


# --- profile-lifecycle navigation from a no-active-session state ---
#
# These tests drive the full ``root_app`` so the CLI root callback (the
# active-session gate) participates. The ``profile_app``-direct tests
# above never reach that callback, so they cannot observe the lockout
# where a lifecycle-navigation verb reaches a decrypting read with no
# bucket session opened for it.


def test_switch_to_surviving_profile_after_deleting_the_active_one(
    _per_bucket_backend: Path,
) -> None:
    """Deleting the active profile must not lock the operator out of survivors.

    Reproduces the delete-active lockout: with two profiles, ``switch``
    the first so it is active, ``delete`` it, then ``switch`` to the
    surviving profile. The final switch must succeed and make the
    survivor active. Before the fix it refused with ``no active bucket
    session`` — the very recovery command the refusal recommended.
    """
    from aeat.adapters.persistence.storage.sql.engine import dispose_engine
    from aeat.application.workflow._models import resolve_active_bucket_id
    from aeat.application.workflow._profile_bucket_scan import read_profile_bucket

    runner = CliRunner()
    _create_via_cli(runner, "alpha")
    _create_via_cli(runner, "beta")

    dispose_engine()
    assert runner.invoke(root_app, ["config", "profile", "switch", "alpha"]).exit_code == 0

    dispose_engine()
    deleted = runner.invoke(root_app, ["config", "profile", "delete", "alpha", "--yes"])
    assert deleted.exit_code == 0, deleted.output

    # The active-profile pointer is now cleared. ``switch`` must still
    # succeed — it is the verb that establishes a session, not one that
    # requires a pre-existing one.
    dispose_engine()
    switched = runner.invoke(root_app, ["config", "profile", "switch", "beta"])
    assert switched.exit_code == 0, switched.output
    assert "active_profile\tbeta" in switched.output

    dispose_engine()
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
    from aeat.adapters.persistence.storage.sql.engine import dispose_engine
    from aeat.application.workflow._models import resolve_active_bucket_id

    runner = CliRunner()
    _create_via_cli(runner, "solo")

    dispose_engine()
    assert runner.invoke(root_app, ["config", "profile", "logout"]).exit_code == 0
    dispose_engine()
    assert resolve_active_bucket_id() is None

    dispose_engine()
    switched = runner.invoke(root_app, ["config", "profile", "switch", "solo"])
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
    from aeat.adapters.persistence.storage.sql.engine import dispose_engine

    runner = CliRunner()
    _create_via_cli(runner, "alpha")

    dispose_engine()
    assert runner.invoke(root_app, ["config", "profile", "logout"]).exit_code == 0

    dispose_engine()
    listed = runner.invoke(root_app, ["config", "profile", "list"])
    assert listed.exit_code == 0, listed.output
    assert "alpha" in listed.output

    dispose_engine()
    status = runner.invoke(root_app, ["config", "profile", "status"])
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
    from aeat.adapters.persistence.storage.sql.engine import dispose_engine

    runner = CliRunner()
    _create_via_cli(runner, "alpha")

    dispose_engine()
    assert runner.invoke(root_app, ["config", "profile", "switch", "alpha"]).exit_code == 0

    dispose_engine()
    deleted = runner.invoke(root_app, ["config", "profile", "delete", "alpha", "--yes"])
    assert deleted.exit_code == 0, deleted.output
    assert "status\ttombstoned" in deleted.output
    # The cleared-pointer consequence is explicit in the output.
    assert "active_profile\t<none>" in deleted.output
    assert "notice\t" in deleted.output
    flat = deleted.output.replace("\n", " ")
    assert "switch" in flat and "create" in flat


def test_delete_non_active_profile_omits_the_cleared_pointer_notice(
    _per_bucket_backend: Path,
) -> None:
    """Deleting a non-active profile does not claim the pointer was cleared.

    The cleared-pointer notice belongs only to the delete-active path;
    deleting an inactive profile leaves the active pointer untouched and
    must not emit the notice.
    """
    from aeat.adapters.persistence.storage.sql.engine import dispose_engine

    runner = CliRunner()
    _create_via_cli(runner, "alpha")
    _create_via_cli(runner, "beta")

    # ``beta`` is active after the second create; delete the inactive
    # ``alpha``.
    dispose_engine()
    deleted = runner.invoke(root_app, ["config", "profile", "delete", "alpha", "--yes"])
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
    from aeat.adapters.persistence.storage.sql.engine import dispose_engine

    runner = CliRunner()
    _create_via_cli(runner, "alpha")

    dispose_engine()
    assert runner.invoke(root_app, ["config", "profile", "logout"]).exit_code == 0

    dispose_engine()
    refused = runner.invoke(root_app, ["config", "profile", "delete", "ghost", "--yes"])
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
    from aeat.adapters.persistence.storage.sql.engine import dispose_engine
    from aeat.application.workflow._profile_bucket_scan import read_profile_bucket

    runner = CliRunner()
    _create_via_cli(runner, "alpha")

    dispose_engine()
    assert runner.invoke(root_app, ["config", "profile", "logout"]).exit_code == 0

    dispose_engine()
    deleted = runner.invoke(root_app, ["config", "profile", "delete", "alpha", "--yes"])
    assert deleted.exit_code == 0, deleted.output
    assert "status\ttombstoned" in deleted.output
    # The profile is gone from the live surface.
    dispose_engine()
    assert read_profile_bucket("alpha") is None


def test_show_tombstoned_profile_is_session_context_independent(
    _per_bucket_backend: Path,
) -> None:
    """``show <tombstoned>`` behaves the same regardless of the active session.

    A tombstoned profile inspected with another profile's session
    active, and the same profile inspected with no session at all, must
    both resolve the tombstoned record and report ``readiness
    tombstoned`` — never an ``unknown profile`` refusal in one context
    and a full record in the other.
    """
    from aeat.adapters.persistence.storage.sql.engine import dispose_engine

    runner = CliRunner()
    _create_via_cli(runner, "alpha")
    _create_via_cli(runner, "beta")

    # ``beta`` is active after the second create. Tombstone ``alpha``.
    dispose_engine()
    assert runner.invoke(root_app, ["config", "profile", "delete", "alpha", "--yes"]).exit_code == 0

    # Context 1: ``beta`` session active.
    dispose_engine()
    assert runner.invoke(root_app, ["config", "profile", "switch", "beta"]).exit_code == 0
    dispose_engine()
    with_session = runner.invoke(root_app, ["config", "profile", "show", "alpha"])

    # Context 2: no active session.
    dispose_engine()
    assert runner.invoke(root_app, ["config", "profile", "logout"]).exit_code == 0
    dispose_engine()
    no_session = runner.invoke(root_app, ["config", "profile", "show", "alpha"])

    # Identical outcome in both session contexts: the tombstoned record
    # resolves and renders its tombstoned status.
    assert with_session.exit_code == 0, with_session.output
    assert no_session.exit_code == 0, no_session.output
    assert "readiness\ttombstoned" in with_session.output
    assert "readiness\ttombstoned" in no_session.output
    assert "status\ttombstoned" in with_session.output
    assert "status\ttombstoned" in no_session.output
    for context in (with_session, no_session):
        flat = context.output.lower()
        assert "desconocido" not in flat and "unknown profile" not in flat
