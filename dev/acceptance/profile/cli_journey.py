"""Public-CLI portions of the isolated PROFILE-01 installed journey.

The implementation intentionally reuses the shared fresh-process CLI adapter.
It never opens an encrypted profile repository, reads product files, or embeds a
second profile mutation path.  The compact evidence objects retain identifiers,
booleans, hashes, and public command statuses only; synthetic fact values and
the unlock credential never enter a receipt.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal, cast

from dev.acceptance.income_tax.cli_journey import CommandEvidence, InstalledCli

from .scenario import ProfileRowLifecycleScenario

_SCHEMA_VERSION = "profile-01-installed-cli-lifecycle-v1"
_ARCHIVE_SUFFIX = ".cadrumo-bucket.tar.gz"


class ProfileCliAcceptanceError(RuntimeError):
    """A stable installed-CLI failure identity suitable for a sanitized receipt."""

    def __init__(self, *, stage: str, diagnostic_code: str) -> None:
        """Keep the stage and stable diagnostic separate from process output."""
        self.stage = stage
        self.diagnostic_code = diagnostic_code
        super().__init__(f"PROFILE-01 installed CLI failed at {stage}: {diagnostic_code}")


@dataclass(frozen=True, slots=True)
class ProfileArchiveConsumerEvidence:
    """Proof that the current encrypted profile remains exportable by its public consumer."""

    archive_schema_version: int
    size: int
    sha256: str


@dataclass(frozen=True, slots=True)
class ProfileCliLifecycleEvidence:
    """Sanitized CLI-only row lifecycle evidence over one isolated secure store."""

    schema_version: str
    status: Literal["proven"]
    row_key: str
    replacement_row_key: str
    no_op_reported: bool
    explicit_clear_survived_reopen: bool
    selector_fact_survived_clear: bool
    removal_survived_reopen: bool
    retired_identifier_refused: bool
    archive_consumer: ProfileArchiveConsumerEvidence
    commands: tuple[CommandEvidence, ...]
    retention: str

    def to_dict(self) -> dict[str, object]:
        """Return receipt-safe evidence with no raw synthetic profile facts."""
        return cast("dict[str, object]", asdict(self))


class ProfileInstalledCli:
    """Narrow public command adapter for one PROFILE-01 encrypted store."""

    def __init__(
        self,
        *,
        executable: Path,
        storage_root: Path,
        authority_root: Path,
        passphrase: str,
    ) -> None:
        """Bind the installed executable to exactly one caller-owned secure store."""
        self._cli = InstalledCli(
            executable,
            storage_root=storage_root,
            authority_root=authority_root,
            passphrase=passphrase,
        )

    @property
    def commands(self) -> tuple[CommandEvidence, ...]:
        """Return only the shared adapter's already-sanitized command summaries."""
        return tuple(self._cli.commands)

    @property
    def executable(self) -> Path:
        """Expose the resolved installed executable for caller-held identity evidence."""
        return self._cli.executable

    def create_profile(self, *, year: int) -> None:
        """Create the complete synthetic profile through the public CLI only."""
        try:
            self._cli.create_profile(year=year)
        except Exception as exc:
            raise ProfileCliAcceptanceError(
                stage="profile_create", diagnostic_code=f"profile_create_{type(exc).__name__}"
            ) from exc

    def add_row(self, scenario: ProfileRowLifecycleScenario) -> str:
        """Add a schema-declared row and return its public stable identifier."""
        tokens = tuple(token for field, value in scenario.add_values() for token in ("--value", f"{field}={value}"))
        result = self._result(
            ("config", "profile", "add-row", scenario.section, *tokens),
            stage="row_add",
        )
        row_index = result.get("row_index")
        if isinstance(row_index, bool) or not isinstance(row_index, int) or row_index < 0:
            raise ProfileCliAcceptanceError(stage="row_add", diagnostic_code="row_index_missing")
        return str(row_index)

    def edit_row(
        self,
        *,
        scenario: ProfileRowLifecycleScenario,
        row_key: str,
        field: str,
        value: str,
    ) -> bool:
        """Modify one identified field, retaining omitted values by contract."""
        result = self._result(
            ("config", "profile", "edit-row", scenario.section, row_key, "--value", f"{field}={value}"),
            stage="row_edit",
        )
        changed = result.get("changed")
        if not isinstance(changed, bool):
            raise ProfileCliAcceptanceError(stage="row_edit", diagnostic_code="changed_flag_missing")
        return changed

    def clear_row_field(self, *, scenario: ProfileRowLifecycleScenario, row_key: str, field: str) -> bool:
        """Explicitly clear exactly one field; omission remains a no-change request."""
        result = self._result(
            ("config", "profile", "edit-row", scenario.section, row_key, "--clear", field),
            stage="row_clear",
        )
        changed = result.get("changed")
        if changed is not True:
            raise ProfileCliAcceptanceError(stage="row_clear", diagnostic_code="clear_not_reported_changed")
        return True

    def remove_row(self, *, scenario: ProfileRowLifecycleScenario, row_key: str) -> None:
        """Remove one exact stable row through the public removal verb."""
        result = self._result(
            ("config", "profile", "remove-row", scenario.section, row_key),
            stage="row_remove",
        )
        if result.get("changed") is not True:
            raise ProfileCliAcceptanceError(stage="row_remove", diagnostic_code="remove_not_reported_changed")

    def removed_row_is_refused(self, *, scenario: ProfileRowLifecycleScenario, row_key: str) -> bool:
        """Prove a retired identifier cannot redirect a later row mutation."""
        try:
            document = self._cli.run(
                (
                    "config",
                    "profile",
                    "edit-row",
                    scenario.section,
                    row_key,
                    "--value",
                    f"{scenario.clearable_field}={scenario.amended_cnae}",
                ),
                allow_error=True,
            )
        except Exception as exc:
            raise ProfileCliAcceptanceError(
                stage="retired_row_refusal", diagnostic_code=f"retired_row_{type(exc).__name__}"
            ) from exc
        latest = self._cli.commands[-1] if self._cli.commands else None
        if latest is None or latest.returncode == 0:
            return False
        return isinstance(document, dict)

    def visible_fact_paths(self) -> frozenset[str]:
        """Read current facts through a fresh public CLI process, not storage internals."""
        result = self._result(("config", "profile", "view"), stage="fresh_profile_view")
        facts = result.get("facts")
        if not isinstance(facts, list):
            raise ProfileCliAcceptanceError(stage="fresh_profile_view", diagnostic_code="facts_missing")
        paths: set[str] = set()
        for fact in facts:
            if not isinstance(fact, dict):
                raise ProfileCliAcceptanceError(stage="fresh_profile_view", diagnostic_code="fact_shape_invalid")
            path = fact.get("path")
            if not isinstance(path, str) or not path:
                raise ProfileCliAcceptanceError(stage="fresh_profile_view", diagnostic_code="fact_path_invalid")
            paths.add(path)
        return frozenset(paths)

    def export_current_profile(self, *, artifact_dir: Path) -> ProfileArchiveConsumerEvidence:
        """Exercise the supported sealed export/inspect consumer without reading its ciphertext."""
        _require_empty_directory(artifact_dir, label="archive artifact directory")
        target = artifact_dir / f"profile{_ARCHIVE_SUFFIX}"
        export = self._result(
            ("config", "profile", "archive", "export", "--output", str(target)),
            stage="archive_export",
        )
        if not target.is_file():
            raise ProfileCliAcceptanceError(stage="archive_export", diagnostic_code="archive_missing")
        archive_schema_version = export.get("archive_schema_version")
        if not isinstance(archive_schema_version, int) or archive_schema_version < 1:
            raise ProfileCliAcceptanceError(stage="archive_export", diagnostic_code="archive_schema_missing")
        inspection = self._result(
            ("config", "profile", "archive", "inspect", "--file", str(target)),
            stage="archive_inspect",
            authenticated=False,
        )
        if inspection.get("archive_schema_version") != archive_schema_version:
            raise ProfileCliAcceptanceError(stage="archive_inspect", diagnostic_code="archive_schema_mismatch")
        payload = target.read_bytes()
        return ProfileArchiveConsumerEvidence(
            archive_schema_version=archive_schema_version,
            size=len(payload),
            sha256=hashlib.sha256(payload).hexdigest(),
        )

    def _result(
        self,
        args: Sequence[str],
        *,
        stage: str,
        authenticated: bool = True,
    ) -> dict[str, Any]:
        try:
            document = self._cli.run(args, authenticated=authenticated)
        except Exception as exc:
            raise ProfileCliAcceptanceError(stage=stage, diagnostic_code=f"command_{type(exc).__name__}") from exc
        result = document.get("result")
        if not isinstance(result, dict):
            raise ProfileCliAcceptanceError(stage=stage, diagnostic_code="result_missing")
        return result


def run_cli_only_lifecycle(
    *,
    executable: Path,
    authority_root: Path,
    storage_root: Path,
    artifact_dir: Path,
    passphrase: str,
    year: int,
    scenario: ProfileRowLifecycleScenario,
) -> ProfileCliLifecycleEvidence:
    """Run add/edit/no-op/clear/remove/reopen through fresh installed CLI processes.

    The caller owns both supplied roots.  This function only creates them when
    absent and refuses any nonempty root, so it can never overwrite another
    acceptance run or an operator store.
    """
    _require_empty_directory(storage_root, label="CLI-only storage root")
    cli = ProfileInstalledCli(
        executable=executable,
        storage_root=storage_root,
        authority_root=authority_root,
        passphrase=passphrase,
    )
    cli.create_profile(year=year)
    row_key = cli.add_row(scenario)

    if (
        cli.edit_row(
            scenario=scenario,
            row_key=row_key,
            field=scenario.clearable_field,
            value=scenario.amended_cnae,
        )
        is not True
    ):
        raise ProfileCliAcceptanceError(stage="row_edit", diagnostic_code="edit_not_reported_changed")
    no_op_reported = (
        cli.edit_row(
            scenario=scenario,
            row_key=row_key,
            field=scenario.clearable_field,
            value=scenario.amended_cnae,
        )
        is False
    )
    if not no_op_reported:
        raise ProfileCliAcceptanceError(stage="row_no_op", diagnostic_code="no_op_not_reported")

    cli.clear_row_field(scenario=scenario, row_key=row_key, field=scenario.clearable_field)
    after_clear = cli.visible_fact_paths()
    clear_path = scenario.path(row_key, scenario.clearable_field)
    selector_path = scenario.path(row_key, scenario.selector_field)
    required_path = scenario.path(row_key, scenario.required_field)
    if clear_path in after_clear:
        raise ProfileCliAcceptanceError(stage="fresh_reopen_after_clear", diagnostic_code="cleared_fact_reappeared")
    if selector_path not in after_clear or required_path not in after_clear:
        raise ProfileCliAcceptanceError(stage="fresh_reopen_after_clear", diagnostic_code="row_state_not_preserved")

    cli.remove_row(scenario=scenario, row_key=row_key)
    after_remove = cli.visible_fact_paths()
    if any(
        scenario.path(row_key, field) in after_remove
        for field in (scenario.required_field, scenario.clearable_field, scenario.selector_field)
    ):
        raise ProfileCliAcceptanceError(stage="fresh_reopen_after_remove", diagnostic_code="removed_row_reappeared")

    replacement_row_key = cli.add_row(scenario)
    if int(replacement_row_key) <= int(row_key):
        raise ProfileCliAcceptanceError(stage="replacement_add", diagnostic_code="retired_row_identifier_reused")
    retired_identifier_refused = cli.removed_row_is_refused(scenario=scenario, row_key=row_key)
    if not retired_identifier_refused:
        raise ProfileCliAcceptanceError(stage="retired_row_refusal", diagnostic_code="retired_row_accepted")
    cli.remove_row(scenario=scenario, row_key=replacement_row_key)
    final_paths = cli.visible_fact_paths()
    if any(
        scenario.path(candidate, field) in final_paths
        for candidate in (row_key, replacement_row_key)
        for field in (scenario.required_field, scenario.clearable_field, scenario.selector_field)
    ):
        raise ProfileCliAcceptanceError(stage="final_reopen", diagnostic_code="removed_row_reappeared")

    archive = cli.export_current_profile(artifact_dir=artifact_dir)
    return ProfileCliLifecycleEvidence(
        schema_version=_SCHEMA_VERSION,
        status="proven",
        row_key=row_key,
        replacement_row_key=replacement_row_key,
        no_op_reported=True,
        explicit_clear_survived_reopen=True,
        selector_fact_survived_clear=True,
        removal_survived_reopen=True,
        retired_identifier_refused=True,
        archive_consumer=archive,
        commands=cli.commands,
        retention="caller_owned_encrypted_store_and_sealed_synthetic_archive",
    )


def _require_empty_directory(path: Path, *, label: str) -> None:
    """Create exactly one caller-owned run directory or refuse a nonempty one."""
    if path.exists() and not path.is_dir():
        raise ProfileCliAcceptanceError(stage="preflight", diagnostic_code=f"{label.replace(' ', '_')}_not_directory")
    if path.exists() and any(path.iterdir()):
        raise ProfileCliAcceptanceError(stage="preflight", diagnostic_code=f"{label.replace(' ', '_')}_not_empty")
    path.mkdir(parents=True, exist_ok=True)


__all__ = [
    "ProfileArchiveConsumerEvidence",
    "ProfileCliAcceptanceError",
    "ProfileCliLifecycleEvidence",
    "ProfileInstalledCli",
    "run_cli_only_lifecycle",
]
