"""Focused safety/receipt coverage for the PROFILE-01 CLI acceptance driver."""

from __future__ import annotations

import json
import secrets
from pathlib import Path
from typing import Any

import pytest

from dev.acceptance.installed_cli import CommandEvidence

from .. import cli_journey as journey_module
from ..cli_journey import ProfileCliAcceptanceError, run_cli_only_lifecycle
from ..scenario import build_profile_row_lifecycle_scenario

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


class _PublicCliFixture:
    """A command-envelope fixture, never a private profile-store substitute."""

    def __init__(self, executable: Path, *, storage_root: Path, authority_root: Path, passphrase: str) -> None:
        self.executable = executable.resolve()
        self.storage_root = storage_root
        self.authority_root = authority_root
        self.passphrase = passphrase
        self.commands: list[CommandEvidence] = []
        self._next_row = 1
        self._retired: set[str] = set()
        self._fields: set[str] = set()
        self._cnae = ""

    def create_profile(self, *, year: int) -> None:
        self.commands.append(CommandEvidence("config profile create", 0, "success", ()))

    def run(
        self,
        args: tuple[str, ...] | list[str],
        *,
        authenticated: bool = True,
        allow_error: bool = False,
    ) -> dict[str, Any]:
        del authenticated
        tokens = tuple(args)
        command = " ".join(tokens[:4])
        operation = tokens[2] if len(tokens) > 2 else ""
        if operation == "add-row":
            row = str(self._next_row)
            self._next_row += 1
            self._fields.update(
                {
                    f"activities.{row}.description",
                    f"activities.{row}.cnae",
                    f"activities.{row}.iae_epigraph",
                }
            )
            self._cnae = "6201"
            result: dict[str, object] = {"row_index": int(row)}
            return self._record(command, 0, "success", result)
        if operation == "edit-row":
            row = tokens[4]
            if row in self._retired:
                if not allow_error:
                    raise RuntimeError("retired row must be invoked with allow_error")
                return self._record(command, 2, "error", {})
            if "--clear" in tokens:
                self._fields.discard(f"activities.{row}.cnae")
                return self._record(command, 0, "success", {"changed": True})
            value = tokens[-1].partition("=")[2]
            changed = value != self._cnae
            self._cnae = value
            return self._record(command, 0, "success", {"changed": changed})
        if operation == "remove-row":
            row = tokens[4]
            self._retired.add(row)
            self._fields = {path for path in self._fields if not path.startswith(f"activities.{row}.")}
            return self._record(command, 0, "success", {"changed": True})
        if operation == "view":
            facts = [{"path": path} for path in sorted(self._fields)]
            return self._record(command, 0, "success", {"facts": facts})
        if operation == "archive" and tokens[3] == "export":
            target = Path(tokens[-1])
            target.write_bytes(b"synthetic-sealed-profile")
            return self._record(command, 0, "success", {"archive_schema_version": 4})
        if operation == "archive" and tokens[3] == "inspect":
            return self._record(command, 0, "success", {"archive_schema_version": 4})
        raise AssertionError(f"unexpected public command shape {tokens[:4]!r}")

    def _record(self, command: str, returncode: int, status: str, result: dict[str, object]) -> dict[str, Any]:
        self.commands.append(CommandEvidence(command, returncode, status, ()))
        return {"status": status, "result": result}


def test_cli_lifecycle_receipt_proves_clear_remove_reopen_and_retired_id_without_fact_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The driver keeps public lifecycle evidence while omitting values and credentials."""
    executable = tmp_path / "aeat.exe"
    authority = tmp_path / "authority"
    executable.write_bytes(b"fixture executable")
    authority.mkdir()
    monkeypatch.setattr(journey_module, "InstalledCli", _PublicCliFixture)
    secret = secrets.token_urlsafe(24)

    evidence = run_cli_only_lifecycle(
        executable=executable,
        authority_root=authority,
        storage_root=tmp_path / "storage",
        artifact_dir=tmp_path / "artifacts",
        passphrase=secret,
        year=2025,
        scenario=build_profile_row_lifecycle_scenario(),
    )

    payload = json.dumps(evidence.to_dict(), sort_keys=True)
    assert evidence.explicit_clear_survived_reopen is True
    assert evidence.removal_survived_reopen is True
    assert evidence.retired_identifier_refused is True
    assert evidence.replacement_row_key == "2"
    assert "Synthetic acceptance activity" not in payload
    assert "6201" not in payload
    assert secret not in payload


def test_cli_driver_refuses_a_nonempty_caller_owned_store(tmp_path: Path) -> None:
    """A new-run boundary fails closed rather than reusing or deleting an existing store."""
    store = tmp_path / "store"
    store.mkdir()
    sentinel = store / "operator-owned-sentinel"
    sentinel.write_text("keep", encoding="utf-8")

    with pytest.raises(ProfileCliAcceptanceError) as raised:
        run_cli_only_lifecycle(
            executable=tmp_path / "missing-aeat.exe",
            authority_root=tmp_path,
            storage_root=store,
            artifact_dir=tmp_path / "artifacts",
            passphrase=secrets.token_urlsafe(24),
            year=2025,
            scenario=build_profile_row_lifecycle_scenario(),
        )

    assert raised.value.diagnostic_code == "CLI-only_storage_root_not_empty"
    assert sentinel.read_text(encoding="utf-8") == "keep"
