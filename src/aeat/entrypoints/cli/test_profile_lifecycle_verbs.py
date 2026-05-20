"""CLI surface tests for `aeat config profile {switch, show, delete, duplicate, rename}`."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner, Result

from aeat.application.user_profile._testing import register_minimal_profile
from aeat.application.workflow._persistence import workflow_state_repository
from aeat.entrypoints.cli._config import profile_app, repair_app
from aeat.entrypoints.cli import app as root_app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


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


def _seed(name: str = "default") -> None:
    workflow_state_repository().update(lambda state: register_minimal_profile(state, profile_id=name))


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
    from aeat.application.user_profile._orchestration import _ensure_profile_bucket_manifest

    _ensure_profile_bucket_manifest("operator")

    result = cli_runner.invoke(profile_app, ["switch", "operator"])

    assert result.exit_code == 2, result.output
    assert "readiness\tmissing_profile_record" in result.output
    assert "profile_record\tmissing" in result.output
    assert "unknown profile" not in result.output.lower()


def test_config_profile_show_does_not_suggest_switch_for_missing_record(cli_runner: CliRunner) -> None:
    from aeat.application.user_profile._orchestration import _ensure_profile_bucket_manifest

    _ensure_profile_bucket_manifest("operator")

    result = cli_runner.invoke(profile_app, ["show", "operator"])

    assert result.exit_code == 2, result.output
    assert "readiness\tmissing_profile_record" in result.output
    assert "next_action\taeat config repair profile --profile operator" in result.output
    assert "next_action\taeat config profile switch operator" not in result.output


def test_config_profile_create_refuses_manifest_only_profile(cli_runner: CliRunner) -> None:
    from aeat.application.user_profile._orchestration import _ensure_profile_bucket_manifest

    _ensure_profile_bucket_manifest("operator")

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
    from aeat.application.user_profile._orchestration import (
        _ensure_profile_bucket_manifest,
        _write_active_profile_pointer,
    )
    from aeat.core._bucket_pointer_io import read_pointer

    _ensure_profile_bucket_manifest("operator")
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
    _seed("operator")
    result = cli_runner.invoke(profile_app, ["show"])
    assert result.exit_code == 0, result.output
    assert "profile_id\toperator" in result.output
    assert "identity.tax_id\t00000000T" in result.output


def test_config_profile_show_named_profile_includes_canonical_facts(cli_runner: CliRunner) -> None:
    _seed("operator")
    _seed("spouse")
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


def test_config_profile_duplicate_copies_to_new_id(cli_runner: CliRunner) -> None:
    _seed("operator")
    result = cli_runner.invoke(
        profile_app,
        ["duplicate", "operator", "operator-spouse", "--display-name", "Spouse"],
    )
    assert result.exit_code == 0, result.output
    assert "target_profile_id\toperator-spouse" in result.output
    assert "display_name\tSpouse" in result.output
    from aeat.application.workflow._profile_bucket_scan import read_profile_bucket
    assert read_profile_bucket("operator-spouse") is not None


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


# --- Fix (batch 2): profile rename is atomic ---


@pytest.fixture
def _per_bucket_backend(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Fixture that sets up per-bucket storage (no global AEAT_DATABASE_URL).

    ``profile rename`` depends on per-bucket path resolution: the SQLite
    file lives at ``<root>/buckets/<id>/db/aeat.db`` and shutil.move must
    be able to move it.  Tests that use this fixture must NOT also use the
    autouse ``_isolated_backend`` fixture that hard-wires
    ``AEAT_DATABASE_URL`` to a single test file.
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


def test_profile_rename_succeeds_and_profile_list_shows_only_target(
    _per_bucket_backend: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``profile rename A B`` must fully succeed atomically.

    Before fix: WinError 32 on the shutil.move (SQLite file still open)
    left the registry with a ghost B record but the bucket directory still
    named A.  ``profile list`` then showed both A (on disk) and B (in DB).

    After fix: the rename either fully succeeds (only B visible) or fully
    no-ops (only A visible).  A ghost entry must never appear.
    """
    from aeat.adapters.persistence.storage.sql.engine import dispose_engine
    from aeat.entrypoints.cli._config import profile_app
    from aeat.application.workflow._profile_bucket_scan import read_profile_bucket

    runner = CliRunner()

    # Create the source profile using the full CLI create path (wizard).
    result = runner.invoke(
        root_app,
        [
            "config", "profile", "create", "alpha",
            "--quiet",
            "--tax-id", "12345678Z",
            "--name", "Tester",
            "--activity", "design",
            "--iva-regime", "GENERAL",
        ],
    )
    assert result.exit_code == 0, f"create failed: {result.output}"

    # Rename alpha -> beta.
    dispose_engine()
    result = runner.invoke(root_app, ["config", "profile", "rename", "alpha", "beta"])
    assert result.exit_code == 0, f"rename failed: {result.output}"
    assert "target_profile_id\tbeta" in result.output

    # Registry must show exactly one profile (beta), no ghost alpha.
    assert read_profile_bucket("beta") is not None, "beta not registered after rename"
    assert read_profile_bucket("alpha") is None, "alpha still in registry after rename (ghost)"

    # profile list must confirm the same view.
    dispose_engine()
    list_result = runner.invoke(root_app, ["--format", "json", "config", "profile", "list"])
    assert list_result.exit_code == 0, list_result.output
    payload = json.loads(list_result.output)
    names = [p["name"] for p in payload["profiles"]]
    assert names == ["beta"], f"expected only beta, got {names}"
    assert payload["active_profile"] == "beta"


def test_profile_rename_no_ghost_on_failure(
    _per_bucket_backend: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the directory move fails, the registry must not show a ghost target.

    Simulates the WinError 32 scenario by making shutil.move raise; the
    rollback must reverse the DB changes so profile list shows only the
    original source profile.
    """
    import shutil

    from aeat.adapters.persistence.storage.sql.engine import dispose_engine
    from aeat.application.workflow._profile_bucket_scan import read_profile_bucket

    runner = CliRunner()

    result = runner.invoke(
        root_app,
        [
            "config", "profile", "create", "src_profile",
            "--quiet",
            "--tax-id", "12345678Z",
            "--name", "Source",
            "--activity", "design",
            "--iva-regime", "GENERAL",
        ],
    )
    assert result.exit_code == 0, f"create failed: {result.output}"

    original_move = shutil.move

    def _failing_move(src, dst):
        raise OSError(32, "Simulated WinError 32: file in use")

    monkeypatch.setattr(shutil, "move", _failing_move)

    dispose_engine()
    result = runner.invoke(root_app, ["config", "profile", "rename", "src_profile", "dst_profile"])

    monkeypatch.setattr(shutil, "move", original_move)

    # Must fail with a non-zero exit code.
    assert result.exit_code != 0, f"expected failure, got: {result.output}"

    # Registry must have no ghost dst_profile.
    dispose_engine()
    assert read_profile_bucket("dst_profile") is None, "ghost dst_profile in registry after failed rename"
    # src_profile must still exist (rollback succeeded).
    assert read_profile_bucket("src_profile") is not None, "src_profile was deleted by failed rename"


def test_profile_rename_target_record_is_healthy(
    _per_bucket_backend: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: ``profile rename A B`` must leave B with a readable profile record.

    Before fix: the encrypted record was stored with object_key
    ``user-profile:A:B`` (source bucket_id embedded).  After shutil.move
    the DB was at buckets/B/db/aeat.db; a reader queried
    ``user-profile:B:B`` (target bucket_id) and found nothing, yielding
    readiness ``missing_profile_record``.

    After fix: the re-keying step rewrites the record to
    ``user-profile:B:B`` before the manifest update, so ``profile show B``
    and ``profile status`` both report ``profile_record present`` and
    ``readiness ready``.
    """
    from aeat.adapters.persistence.storage.sql.engine import dispose_engine
    from aeat.application.user_profile._orchestration import build_lifecycle_service
    from aeat.application.workflow._profile_bucket_scan import read_profile_bucket

    runner = CliRunner()

    # Create source profile via the full CLI wizard path.
    create_result = runner.invoke(
        root_app,
        [
            "config", "profile", "create", "alice",
            "--quiet",
            "--tax-id", "12345678Z",
            "--name", "Alice",
            "--activity", "design",
            "--iva-regime", "GENERAL",
        ],
    )
    assert create_result.exit_code == 0, f"create failed: {create_result.output}"

    # Rename alice -> bob.
    dispose_engine()
    rename_result = runner.invoke(root_app, ["config", "profile", "rename", "alice", "bob"])
    assert rename_result.exit_code == 0, f"rename failed: {rename_result.output}"

    # Registry: bob present, alice gone.
    dispose_engine()
    assert read_profile_bucket("bob") is not None, "bob not in registry after rename"
    assert read_profile_bucket("alice") is None, "alice still in registry after rename (ghost)"

    # The critical assertion: the profile record must be readable via the
    # target bucket_id.  Before the fix this raised ProfileNotFoundError
    # because the object_key was keyed to the source bucket_id.
    dispose_engine()
    svc = build_lifecycle_service(bucket_id="bob")
    record = svc.read("bob")
    assert record.profile_id == "bob", f"unexpected profile_id: {record.profile_id!r}"

    # profile show bob must exit 0 and report readiness ready (not missing_profile_record).
    dispose_engine()
    show_result = runner.invoke(root_app, ["config", "profile", "show", "bob"])
    assert show_result.exit_code == 0, f"show failed: {show_result.output}"
    assert "readiness\tready" in show_result.output, show_result.output
    assert "missing_profile_record" not in show_result.output, show_result.output

    # repair profile --profile bob must report profile_record present (explicit record health check).
    dispose_engine()
    repair_result = runner.invoke(root_app, ["config", "repair", "profile", "--profile", "bob"])
    assert repair_result.exit_code == 0, f"repair failed: {repair_result.output}"
    assert "profile_record\tpresent" in repair_result.output, repair_result.output
    assert "readiness\tready" in repair_result.output, repair_result.output
