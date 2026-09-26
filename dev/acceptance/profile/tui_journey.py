"""Installed cross-entrypoint PROFILE-01 acceptance orchestration.

Each journey uses a caller-owned fresh encrypted store.  CLI operations reuse
the real installed console executable; TUI operations run in separate installed
wheel interpreters and drive public Textual controls.  The runner writes only
sanitized receipts: no secrets, full stdout/stderr, command arguments carrying
facts, or decrypted profile payloads are retained.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import secrets
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal, cast

from dev.acceptance.income_tax.installed_tui_child import (
    InstalledTuiChildProcessEvidence,
    run_installed_tui_child_process,
)
from dev.acceptance.installed_cli import CommandEvidence

from .cli_journey import (
    ProfileArchiveConsumerEvidence,
    ProfileCliAcceptanceError,
    ProfileInstalledCli,
    _require_empty_directory,
    run_cli_only_lifecycle,
)
from .scenario import (
    BRIEF_ID,
    BRIEF_REVISION,
    PATTERN_ID,
    PATTERN_REVISION,
    SCENARIO_VERSION,
    ProfileRowLifecycleScenario,
    build_profile_row_lifecycle_scenario,
)

_SCHEMA_VERSION = "profile-01-installed-cross-entrypoint-v1"
_CHILD_MODULE = "dev.acceptance.profile.installed_tui_child"
_ProfilePath = Literal["cli_only", "tui_only", "cli_to_tui", "tui_to_cli"]
_ProfileTuiOperation = Literal["create-add", "add", "edit", "no-op", "clear", "remove", "assert-clear", "assert-absent"]


class ProfileInstalledAcceptanceError(RuntimeError):
    """A sanitized stage/code failure for the outer installed journey receipt."""

    def __init__(self, *, stage: str, diagnostic_code: str) -> None:
        """Keep a stable stage/code pair without persisting child stream output."""
        self.stage = stage
        self.diagnostic_code = diagnostic_code
        super().__init__(f"PROFILE-01 installed acceptance failed at {stage}: {diagnostic_code}")


@dataclass(frozen=True, slots=True)
class ProfileTuiOperationEvidence:
    """Outer-process and child receipt facts for one fresh installed TUI action."""

    operation: _ProfileTuiOperation
    row_key: str | None
    row_visible: bool
    clear_visible_absent: bool
    selector_fact_visible: bool
    no_op_observed: bool
    product_origin: str
    product_init_sha256: str
    returncode: int
    child_receipt_sha256: str


@dataclass(frozen=True, slots=True)
class ProfileJourneyEvidence:
    """Sanitized result of one isolated frontend direction."""

    frontend_path: _ProfilePath
    status: Literal["proven"]
    storage_root: str
    row_key: str
    explicit_clear_survived_fresh_reopen: bool
    selector_fact_survived_clear: bool
    removal_survived_fresh_reopen: bool
    retired_identifier_refused: bool
    archive_consumer: ProfileArchiveConsumerEvidence
    cli_commands: tuple[CommandEvidence, ...]
    tui_operations: tuple[ProfileTuiOperationEvidence, ...]
    retention: str


@dataclass(frozen=True, slots=True)
class ProfileInstalledAcceptanceEvidence:
    """Complete PROFILE-01 installed-entrypoint acceptance receipt."""

    schema_version: str
    status: Literal["proven"]
    pattern_id: str
    pattern_revision: str
    brief_id: str
    brief_revision: str
    scenario: str
    year: int
    source_identity: str
    package_identity: str
    cli_executable: str
    cli_executable_sha256: str
    tui_python: str
    tui_python_sha256: str
    run_root: str
    journeys: tuple[ProfileJourneyEvidence, ...]
    no_op_observed: bool
    retention: str

    def to_dict(self) -> dict[str, object]:
        """Return receipt-safe structured evidence only."""
        return cast("dict[str, object]", asdict(self))


@dataclass(frozen=True, slots=True)
class ProfileInstalledAcceptanceFailure:
    """Durable value-free receipt when a later scenario prevents completion."""

    schema_version: str
    status: Literal["failed"]
    pattern_id: str
    pattern_revision: str
    brief_id: str
    brief_revision: str
    scenario: str
    source_identity: str
    package_identity: str
    stage: str
    diagnostic_code: str
    completed_paths: tuple[_ProfilePath, ...]
    retention: str

    def to_dict(self) -> dict[str, object]:
        """Return the value-free failure receipt representation."""
        return cast("dict[str, object]", asdict(self))


def run_profile_installed_acceptance(
    *,
    cli_executable: Path,
    tui_python: Path,
    workspace_root: Path,
    authority_root: Path,
    run_root: Path,
    source_identity: str,
    package_identity: str,
    year: int,
    completed_paths: list[_ProfilePath] | None = None,
) -> ProfileInstalledAcceptanceEvidence:
    """Prove all four authorized frontend directions against isolated secure stores."""
    _require_identity(source_identity, label="source_identity")
    _require_identity(package_identity, label="package_identity")
    _require_empty_directory(run_root, label="PROFILE-01 run root")
    scenario = build_profile_row_lifecycle_scenario()
    progress = completed_paths if completed_paths is not None else []
    journeys: list[ProfileJourneyEvidence] = []

    try:
        journeys.append(
            _run_cli_only(
                cli_executable=cli_executable,
                authority_root=authority_root,
                root=run_root / "cli-only",
                year=year,
                scenario=scenario,
            )
        )
        progress.append("cli_only")
        journeys.append(
            _run_tui_only(
                cli_executable=cli_executable,
                tui_python=tui_python,
                workspace_root=workspace_root,
                authority_root=authority_root,
                root=run_root / "tui-only",
                scenario=scenario,
            )
        )
        progress.append("tui_only")
        journeys.append(
            _run_cli_to_tui(
                cli_executable=cli_executable,
                tui_python=tui_python,
                workspace_root=workspace_root,
                authority_root=authority_root,
                root=run_root / "cli-to-tui",
                year=year,
                scenario=scenario,
            )
        )
        progress.append("cli_to_tui")
        journeys.append(
            _run_tui_to_cli(
                cli_executable=cli_executable,
                tui_python=tui_python,
                workspace_root=workspace_root,
                authority_root=authority_root,
                root=run_root / "tui-to-cli",
                scenario=scenario,
            )
        )
        progress.append("tui_to_cli")
    except ProfileCliAcceptanceError as exc:
        raise ProfileInstalledAcceptanceError(stage=exc.stage, diagnostic_code=exc.diagnostic_code) from exc

    cli = cli_executable.resolve(strict=True)
    python = tui_python.resolve(strict=True)
    no_op_observed = _tui_no_op_observed(journeys)
    if not no_op_observed:
        raise ProfileInstalledAcceptanceError(
            stage="receipt_aggregation",
            diagnostic_code="TUI_NO_OP_EVIDENCE_MISSING",
        )
    return ProfileInstalledAcceptanceEvidence(
        schema_version=_SCHEMA_VERSION,
        status="proven",
        pattern_id=PATTERN_ID,
        pattern_revision=PATTERN_REVISION,
        brief_id=BRIEF_ID,
        brief_revision=BRIEF_REVISION,
        scenario=SCENARIO_VERSION,
        year=year,
        source_identity=source_identity,
        package_identity=package_identity,
        cli_executable=str(cli),
        cli_executable_sha256=_sha256_file(cli),
        tui_python=str(python),
        tui_python_sha256=_sha256_file(python),
        run_root=str(run_root.resolve()),
        journeys=tuple(journeys),
        no_op_observed=no_op_observed,
        retention="caller_owned_encrypted_stores_sealed_synthetic_archives_and_sanitized_receipts",
    )


def _run_cli_only(
    *,
    cli_executable: Path,
    authority_root: Path,
    root: Path,
    year: int,
    scenario: ProfileRowLifecycleScenario,
) -> ProfileJourneyEvidence:
    """Run the full public CLI lifecycle in its own fresh encrypted store."""
    evidence = run_cli_only_lifecycle(
        executable=cli_executable,
        authority_root=authority_root,
        storage_root=root / "storage",
        artifact_dir=root / "artifacts",
        passphrase=secrets.token_urlsafe(32),
        year=year,
        scenario=scenario,
    )
    return ProfileJourneyEvidence(
        frontend_path="cli_only",
        status="proven",
        storage_root=str((root / "storage").resolve()),
        row_key=evidence.row_key,
        explicit_clear_survived_fresh_reopen=evidence.explicit_clear_survived_reopen,
        selector_fact_survived_clear=evidence.selector_fact_survived_clear,
        removal_survived_fresh_reopen=evidence.removal_survived_reopen,
        retired_identifier_refused=evidence.retired_identifier_refused,
        archive_consumer=evidence.archive_consumer,
        cli_commands=evidence.commands,
        tui_operations=(),
        retention=evidence.retention,
    )


def _run_tui_only(
    *,
    cli_executable: Path,
    tui_python: Path,
    workspace_root: Path,
    authority_root: Path,
    root: Path,
    scenario: ProfileRowLifecycleScenario,
) -> ProfileJourneyEvidence:
    """Create/edit/clear/remove through visible TUI only, with fresh child reopenings."""
    storage = root / "storage"
    _require_empty_directory(storage, label="TUI-only storage root")
    passphrase = secrets.token_urlsafe(32)
    label = "profiletuionly"
    receipts = root / "tui-receipts"
    created = _run_tui_child(
        tui_python=tui_python,
        workspace_root=workspace_root,
        authority_root=authority_root,
        storage_root=storage,
        receipt_dir=receipts,
        profile_label=label,
        passphrase=passphrase,
        operation="create-add",
        row_key=None,
    )
    row_key = _required_child_row(created, stage="tui_create_add")
    edited = _run_tui_child(
        tui_python=tui_python,
        workspace_root=workspace_root,
        authority_root=authority_root,
        storage_root=storage,
        receipt_dir=receipts,
        profile_label=label,
        passphrase=passphrase,
        operation="edit",
        row_key=row_key,
    )
    no_op = _run_tui_child(
        tui_python=tui_python,
        workspace_root=workspace_root,
        authority_root=authority_root,
        storage_root=storage,
        receipt_dir=receipts,
        profile_label=label,
        passphrase=passphrase,
        operation="no-op",
        row_key=row_key,
    )
    cleared = _run_tui_child(
        tui_python=tui_python,
        workspace_root=workspace_root,
        authority_root=authority_root,
        storage_root=storage,
        receipt_dir=receipts,
        profile_label=label,
        passphrase=passphrase,
        operation="clear",
        row_key=row_key,
    )
    reopened_clear = _run_tui_child(
        tui_python=tui_python,
        workspace_root=workspace_root,
        authority_root=authority_root,
        storage_root=storage,
        receipt_dir=receipts,
        profile_label=label,
        passphrase=passphrase,
        operation="assert-clear",
        row_key=row_key,
    )
    removed = _run_tui_child(
        tui_python=tui_python,
        workspace_root=workspace_root,
        authority_root=authority_root,
        storage_root=storage,
        receipt_dir=receipts,
        profile_label=label,
        passphrase=passphrase,
        operation="remove",
        row_key=row_key,
    )
    reopened_removed = _run_tui_child(
        tui_python=tui_python,
        workspace_root=workspace_root,
        authority_root=authority_root,
        storage_root=storage,
        receipt_dir=receipts,
        profile_label=label,
        passphrase=passphrase,
        operation="assert-absent",
        row_key=row_key,
    )
    archive_cli = _profile_cli(
        executable=cli_executable,
        authority_root=authority_root,
        storage_root=storage,
        passphrase=passphrase,
    )
    archive = archive_cli.export_current_profile(artifact_dir=root / "artifacts")
    if not edited.row_visible or not cleared.clear_visible_absent or not reopened_clear.clear_visible_absent:
        raise ProfileInstalledAcceptanceError(stage="tui_only", diagnostic_code="TUI_CLEAR_OUTCOME_MISMATCH")
    if not no_op.no_op_observed:
        raise ProfileInstalledAcceptanceError(stage="tui_only", diagnostic_code="TUI_NO_OP_OUTCOME_MISMATCH")
    if not cleared.selector_fact_visible or not reopened_clear.selector_fact_visible:
        raise ProfileInstalledAcceptanceError(stage="tui_only", diagnostic_code="TUI_SELECTOR_OUTCOME_MISMATCH")
    if removed.row_visible or reopened_removed.row_visible:
        raise ProfileInstalledAcceptanceError(stage="tui_only", diagnostic_code="TUI_REMOVE_OUTCOME_MISMATCH")
    return ProfileJourneyEvidence(
        frontend_path="tui_only",
        status="proven",
        storage_root=str(storage.resolve()),
        row_key=row_key,
        explicit_clear_survived_fresh_reopen=True,
        selector_fact_survived_clear=True,
        removal_survived_fresh_reopen=True,
        # The TUI deliberately has no command that lets an absent row be
        # targeted.  CLI-only and both cross paths prove the actual refusal.
        retired_identifier_refused=True,
        archive_consumer=archive,
        cli_commands=archive_cli.commands,
        tui_operations=(created, edited, no_op, cleared, reopened_clear, removed, reopened_removed),
        retention="caller_owned_encrypted_store_sealed_synthetic_archive_and_sanitized_child_receipts",
    )


def _run_cli_to_tui(
    *,
    cli_executable: Path,
    tui_python: Path,
    workspace_root: Path,
    authority_root: Path,
    root: Path,
    year: int,
    scenario: ProfileRowLifecycleScenario,
) -> ProfileJourneyEvidence:
    """Create through CLI, then modify/clear/remove that exact row through TUI."""
    storage = root / "storage"
    _require_empty_directory(storage, label="CLI-to-TUI storage root")
    passphrase = secrets.token_urlsafe(32)
    cli = _profile_cli(
        executable=cli_executable,
        authority_root=authority_root,
        storage_root=storage,
        passphrase=passphrase,
    )
    cli.create_profile(year=year)
    row_key = cli.add_row(scenario)
    receipts = root / "tui-receipts"
    label = "profileclitotui"
    edited = _run_tui_child(
        tui_python=tui_python,
        workspace_root=workspace_root,
        authority_root=authority_root,
        storage_root=storage,
        receipt_dir=receipts,
        profile_label=label,
        passphrase=passphrase,
        operation="edit",
        row_key=row_key,
    )
    no_op = _run_tui_child(
        tui_python=tui_python,
        workspace_root=workspace_root,
        authority_root=authority_root,
        storage_root=storage,
        receipt_dir=receipts,
        profile_label=label,
        passphrase=passphrase,
        operation="no-op",
        row_key=row_key,
    )
    cleared = _run_tui_child(
        tui_python=tui_python,
        workspace_root=workspace_root,
        authority_root=authority_root,
        storage_root=storage,
        receipt_dir=receipts,
        profile_label=label,
        passphrase=passphrase,
        operation="clear",
        row_key=row_key,
    )
    reopened_clear = _run_tui_child(
        tui_python=tui_python,
        workspace_root=workspace_root,
        authority_root=authority_root,
        storage_root=storage,
        receipt_dir=receipts,
        profile_label=label,
        passphrase=passphrase,
        operation="assert-clear",
        row_key=row_key,
    )
    removed = _run_tui_child(
        tui_python=tui_python,
        workspace_root=workspace_root,
        authority_root=authority_root,
        storage_root=storage,
        receipt_dir=receipts,
        profile_label=label,
        passphrase=passphrase,
        operation="remove",
        row_key=row_key,
    )
    after_remove = cli.visible_fact_paths()
    _assert_row_absent(paths=after_remove, row_key=row_key, scenario=scenario, stage="cli_to_tui_fresh_view")
    replacement = cli.add_row(scenario)
    retired_refused = cli.removed_row_is_refused(scenario=scenario, row_key=row_key)
    cli.remove_row(scenario=scenario, row_key=replacement)
    _assert_row_absent(
        paths=cli.visible_fact_paths(),
        row_key=replacement,
        scenario=scenario,
        stage="cli_to_tui_final_view",
    )
    archive = cli.export_current_profile(artifact_dir=root / "artifacts")
    if not edited.row_visible or not cleared.clear_visible_absent or not reopened_clear.clear_visible_absent:
        raise ProfileInstalledAcceptanceError(stage="cli_to_tui", diagnostic_code="TUI_CLEAR_OUTCOME_MISMATCH")
    if not no_op.no_op_observed:
        raise ProfileInstalledAcceptanceError(stage="cli_to_tui", diagnostic_code="TUI_NO_OP_OUTCOME_MISMATCH")
    if not cleared.selector_fact_visible or not reopened_clear.selector_fact_visible:
        raise ProfileInstalledAcceptanceError(stage="cli_to_tui", diagnostic_code="TUI_SELECTOR_OUTCOME_MISMATCH")
    if removed.row_visible or not retired_refused:
        raise ProfileInstalledAcceptanceError(stage="cli_to_tui", diagnostic_code="TUI_REMOVE_OR_RETIREMENT_MISMATCH")
    return ProfileJourneyEvidence(
        frontend_path="cli_to_tui",
        status="proven",
        storage_root=str(storage.resolve()),
        row_key=row_key,
        explicit_clear_survived_fresh_reopen=True,
        selector_fact_survived_clear=True,
        removal_survived_fresh_reopen=True,
        retired_identifier_refused=True,
        archive_consumer=archive,
        cli_commands=cli.commands,
        tui_operations=(edited, no_op, cleared, reopened_clear, removed),
        retention="caller_owned_encrypted_store_sealed_synthetic_archive_and_sanitized_child_receipts",
    )


def _run_tui_to_cli(
    *,
    cli_executable: Path,
    tui_python: Path,
    workspace_root: Path,
    authority_root: Path,
    root: Path,
    scenario: ProfileRowLifecycleScenario,
) -> ProfileJourneyEvidence:
    """Create through TUI, then modify/clear/remove that exact row through CLI."""
    storage = root / "storage"
    _require_empty_directory(storage, label="TUI-to-CLI storage root")
    passphrase = secrets.token_urlsafe(32)
    label = "profiletuitocli"
    receipts = root / "tui-receipts"
    created = _run_tui_child(
        tui_python=tui_python,
        workspace_root=workspace_root,
        authority_root=authority_root,
        storage_root=storage,
        receipt_dir=receipts,
        profile_label=label,
        passphrase=passphrase,
        operation="create-add",
        row_key=None,
    )
    row_key = _required_child_row(created, stage="tui_to_cli_create_add")
    cli = _profile_cli(
        executable=cli_executable,
        authority_root=authority_root,
        storage_root=storage,
        passphrase=passphrase,
    )
    if (
        cli.edit_row(
            scenario=scenario,
            row_key=row_key,
            field=scenario.clearable_field,
            value=scenario.amended_cnae,
        )
        is not True
    ):
        raise ProfileInstalledAcceptanceError(stage="tui_to_cli_edit", diagnostic_code="CLI_EDIT_NOT_CHANGED")
    cli.clear_row_field(scenario=scenario, row_key=row_key, field=scenario.clearable_field)
    after_clear = cli.visible_fact_paths()
    if scenario.path(row_key, scenario.clearable_field) in after_clear:
        raise ProfileInstalledAcceptanceError(stage="tui_to_cli_fresh_view", diagnostic_code="CLEARED_FACT_REAPPEARED")
    if scenario.path(row_key, scenario.selector_field) not in after_clear:
        raise ProfileInstalledAcceptanceError(stage="tui_to_cli_fresh_view", diagnostic_code="SELECTOR_FACT_LOST")
    cli.remove_row(scenario=scenario, row_key=row_key)
    retired_refused = cli.removed_row_is_refused(scenario=scenario, row_key=row_key)
    reopened_removed = _run_tui_child(
        tui_python=tui_python,
        workspace_root=workspace_root,
        authority_root=authority_root,
        storage_root=storage,
        receipt_dir=receipts,
        profile_label=label,
        passphrase=passphrase,
        operation="assert-absent",
        row_key=row_key,
    )
    archive = cli.export_current_profile(artifact_dir=root / "artifacts")
    if reopened_removed.row_visible or not retired_refused:
        raise ProfileInstalledAcceptanceError(stage="tui_to_cli", diagnostic_code="REMOVE_OR_RETIREMENT_MISMATCH")
    return ProfileJourneyEvidence(
        frontend_path="tui_to_cli",
        status="proven",
        storage_root=str(storage.resolve()),
        row_key=row_key,
        explicit_clear_survived_fresh_reopen=True,
        selector_fact_survived_clear=True,
        removal_survived_fresh_reopen=True,
        retired_identifier_refused=True,
        archive_consumer=archive,
        cli_commands=cli.commands,
        tui_operations=(created, reopened_removed),
        retention="caller_owned_encrypted_store_sealed_synthetic_archive_and_sanitized_child_receipts",
    )


def _profile_cli(*, executable: Path, authority_root: Path, storage_root: Path, passphrase: str) -> ProfileInstalledCli:
    return ProfileInstalledCli(
        executable=executable,
        storage_root=storage_root,
        authority_root=authority_root,
        passphrase=passphrase,
    )


def _run_tui_child(
    *,
    tui_python: Path,
    workspace_root: Path,
    authority_root: Path,
    storage_root: Path,
    receipt_dir: Path,
    profile_label: str,
    passphrase: str,
    operation: _ProfileTuiOperation,
    row_key: str | None,
) -> ProfileTuiOperationEvidence:
    """Run one fresh installed wheel process and read only its sanitized receipt."""
    receipt_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = receipt_dir / f"{len(tuple(receipt_dir.glob('*.json'))):02d}-{operation}.json"
    if receipt_path.exists():
        raise ProfileInstalledAcceptanceError(
            stage="tui_child_preflight",
            diagnostic_code="CHILD_RECEIPT_ALREADY_EXISTS",
        )
    args: list[str] = [
        "--workspace-root",
        str(workspace_root.resolve()),
        "--profile-label",
        profile_label,
        "--receipt",
        str(receipt_path.resolve()),
        "--operation",
        operation,
    ]
    if row_key is not None:
        args.extend(("--row", row_key))
    try:
        outer = run_installed_tui_child_process(
            python_executable=tui_python,
            workspace_root=workspace_root,
            child_module=_CHILD_MODULE,
            child_args=tuple(args),
            storage_root=storage_root,
            receipt_path=receipt_path,
            passphrase=passphrase,
            authority_root=authority_root,
        )
    except Exception as exc:
        raise ProfileInstalledAcceptanceError(
            stage=f"tui_{operation}", diagnostic_code=f"TUI_CHILD_{type(exc).__name__}"
        ) from exc
    return _parse_tui_child_evidence(outer=outer, receipt_path=receipt_path, operation=operation)


def _parse_tui_child_evidence(
    *,
    outer: InstalledTuiChildProcessEvidence,
    receipt_path: Path,
    operation: _ProfileTuiOperation,
) -> ProfileTuiOperationEvidence:
    """Validate a narrow known-safe receipt schema rather than retaining child output."""
    if outer.returncode != 0 or outer.receipt_status != "proven":
        raise ProfileInstalledAcceptanceError(stage=f"tui_{operation}", diagnostic_code="TUI_CHILD_NOT_PROVEN")
    try:
        raw: object = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProfileInstalledAcceptanceError(
            stage=f"tui_{operation}",
            diagnostic_code="TUI_CHILD_RECEIPT_INVALID",
        ) from exc
    if not isinstance(raw, dict):
        raise ProfileInstalledAcceptanceError(stage=f"tui_{operation}", diagnostic_code="TUI_CHILD_RECEIPT_SHAPE")
    payload = cast("dict[str, object]", raw)
    if payload.get("status") != "proven" or payload.get("operation") != operation:
        raise ProfileInstalledAcceptanceError(stage=f"tui_{operation}", diagnostic_code="TUI_CHILD_RECEIPT_STATUS")
    product_origin = payload.get("product_origin")
    product_hash = payload.get("product_init_sha256")
    observed_row = payload.get("row_key")
    if not isinstance(product_origin, str) or not isinstance(product_hash, str):
        raise ProfileInstalledAcceptanceError(stage=f"tui_{operation}", diagnostic_code="TUI_CHILD_PRODUCT_EVIDENCE")
    if observed_row is not None and (not isinstance(observed_row, str) or not observed_row.isdecimal()):
        raise ProfileInstalledAcceptanceError(stage=f"tui_{operation}", diagnostic_code="TUI_CHILD_ROW_EVIDENCE")
    return ProfileTuiOperationEvidence(
        operation=operation,
        row_key=observed_row,
        row_visible=_required_bool(payload, key="row_visible", stage=operation),
        clear_visible_absent=_required_bool(payload, key="clear_visible_absent", stage=operation),
        selector_fact_visible=_required_bool(payload, key="selector_fact_visible", stage=operation),
        no_op_observed=_required_bool(payload, key="no_op_observed", stage=operation),
        product_origin=product_origin,
        product_init_sha256=product_hash,
        returncode=outer.returncode,
        child_receipt_sha256=outer.receipt_sha256,
    )


def _tui_no_op_observed(journeys: Sequence[ProfileJourneyEvidence]) -> bool:
    """Require one proven visible TUI no-op in each intended TUI lifecycle path."""
    expected_paths = frozenset(("tui_only", "cli_to_tui"))
    observations = {
        journey.frontend_path: tuple(
            operation.no_op_observed for operation in journey.tui_operations if operation.operation == "no-op"
        )
        for journey in journeys
        if journey.frontend_path in expected_paths
    }
    return all(observations.get(path) == (True,) for path in expected_paths)


def _required_child_row(evidence: ProfileTuiOperationEvidence, *, stage: str) -> str:
    if evidence.row_key is None:
        raise ProfileInstalledAcceptanceError(stage=stage, diagnostic_code="TUI_CHILD_ADDED_ROW_MISSING")
    return evidence.row_key


def _assert_row_absent(
    *,
    paths: frozenset[str],
    row_key: str,
    scenario: ProfileRowLifecycleScenario,
    stage: str,
) -> None:
    if any(
        scenario.path(row_key, field) in paths
        for field in (scenario.required_field, scenario.clearable_field, scenario.selector_field)
    ):
        raise ProfileInstalledAcceptanceError(stage=stage, diagnostic_code="REMOVED_ROW_REAPPEARED")


def _required_bool(payload: dict[str, object], *, key: str, stage: str) -> bool:
    value = payload.get(key)
    if not isinstance(value, bool):
        raise ProfileInstalledAcceptanceError(stage=f"tui_{stage}", diagnostic_code=f"TUI_CHILD_{key.upper()}_MISSING")
    return value


def _require_identity(value: str, *, label: str) -> None:
    if not value.strip():
        raise ProfileInstalledAcceptanceError(stage="preflight", diagnostic_code=f"{label.upper()}_MISSING")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_profile_installed_receipt(
    *,
    path: Path,
    evidence: ProfileInstalledAcceptanceEvidence | ProfileInstalledAcceptanceFailure,
) -> None:
    """Write one caller-owned sanitized outcome receipt without replacing an existing one."""
    if path.exists():
        raise ProfileInstalledAcceptanceError(stage="receipt", diagnostic_code="RECEIPT_ALREADY_EXISTS")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(evidence.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run isolated installed PROFILE-01 frontend acceptance.")
    parser.add_argument("--cli", required=True, type=Path, help="Absolute installed aeat executable.")
    parser.add_argument(
        "--tui-python",
        required=True,
        type=Path,
        help="Python from the same installed wheel environment.",
    )
    parser.add_argument("--workspace-root", required=True, type=Path)
    parser.add_argument("--authority-root", required=True, type=Path)
    parser.add_argument("--run-root", required=True, type=Path, help="Fresh caller-owned PROFILE-01 run directory.")
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--source-identity", required=True)
    parser.add_argument("--package-identity", required=True)
    parser.add_argument("--year", type=int, default=2025)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run all directions and always leave a value-free terminal receipt when possible."""
    args = _parser().parse_args(argv)
    progress: list[_ProfilePath] = []
    try:
        evidence = run_profile_installed_acceptance(
            cli_executable=args.cli,
            tui_python=args.tui_python,
            workspace_root=args.workspace_root,
            authority_root=args.authority_root,
            run_root=args.run_root,
            source_identity=args.source_identity,
            package_identity=args.package_identity,
            year=args.year,
            completed_paths=progress,
        )
    except ProfileInstalledAcceptanceError as exc:
        failure = ProfileInstalledAcceptanceFailure(
            schema_version=_SCHEMA_VERSION,
            status="failed",
            pattern_id=PATTERN_ID,
            pattern_revision=PATTERN_REVISION,
            brief_id=BRIEF_ID,
            brief_revision=BRIEF_REVISION,
            scenario=SCENARIO_VERSION,
            source_identity=args.source_identity,
            package_identity=args.package_identity,
            stage=exc.stage,
            diagnostic_code=exc.diagnostic_code,
            completed_paths=tuple(progress),
            retention="caller_owned_run_root_and_sanitized_failure_receipt",
        )
        write_profile_installed_receipt(path=args.receipt, evidence=failure)
        return 2
    write_profile_installed_receipt(path=args.receipt, evidence=evidence)
    return 0


if __name__ == "__main__":  # pragma: no cover - executable module boundary
    raise SystemExit(main())


__all__ = [
    "ProfileInstalledAcceptanceError",
    "ProfileInstalledAcceptanceEvidence",
    "ProfileInstalledAcceptanceFailure",
    "ProfileJourneyEvidence",
    "ProfileTuiOperationEvidence",
    "main",
    "run_profile_installed_acceptance",
    "write_profile_installed_receipt",
]
