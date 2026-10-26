"""Deferred runtime ownership spans real adapter reopen and failure boundaries."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import TracebackType

import pytest

from .. import cli_journey

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


class _RuntimeScope:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.active = False
        self.entered = 0
        self.exited = 0
        self.exit_error: BaseException | None = None

    def __enter__(self) -> object:
        assert self.root.is_dir()
        assert not any(self.root.iterdir())
        self.entered += 1
        self.active = True
        return self

    def __exit__(
        self,
        error_type: type[BaseException] | None,
        error: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.exit_error = error
        self.active = False
        self.exited += 1


def test_scope_enters_after_fresh_store_validation_and_retains_both_reopens_on_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executable = tmp_path / "packaged-python"
    executable.touch()
    root = tmp_path / "store"
    scope = _RuntimeScope(root)
    stages: list[tuple[str, ...]] = []

    def execute(argv: list[str], **options: object) -> subprocess.CompletedProcess[str]:
        assert scope.active
        start = next(i for i, value in enumerate(argv) if value in {"app", "config"})
        args = tuple(argv[start:])
        stages.append(args)
        result: dict[str, object] = {}
        if args[:4] == ("app", "ledger", "evidence", "add"):
            result = {"evidence_id": "evidence"}
        elif args[:3] == ("app", "ledger", "add"):
            result = {"transaction_id": "sale" if "INCOMING" in args else "purchase"}
        elif args[:4] == ("app", "ledger", "invoice", "add"):
            result = {"invoice_id": "issued" if "issued" in args else "received"}
        elif args == ("app", "ledger", "list"):
            result = {"rows": [{"transaction_id": "sale"}, {"transaction_id": "purchase"}]}
        elif args == ("app", "ledger", "invoice", "list"):
            result = {"rows": [{"invoice_id": "issued"}, {"invoice_id": "received"}]}
        elif args == ("app", "ledger", "evidence", "list"):
            result = {"rows": [{"evidence_id": "evidence"}]}
        elif args[:4] == ("app", "modelo", "work", "create"):
            result = {"work_unit_id": "work"}
        elif args[:4] == ("app", "modelo", "work", "calculate"):
            result = {
                "saved": True,
                "calculation_revision_id": "revision",
                "casilla_values": {"iva.resultado": "10.50"},
            }
        elif args[:4] == ("app", "modelo", "work", "verify"):
            result = {
                "verification_report_id": "verification",
                "calculation_revision_id": "revision",
                "completeness_status": "incomplete",
                "granted_verificado_completo": False,
            }
        return subprocess.CompletedProcess(argv, 0, json.dumps({"status": "ok", "result": result}), "")

    monkeypatch.setattr(subprocess, "run", execute)
    authority = Path(__file__).resolve().parents[4] / ".authority"
    with pytest.raises(cli_journey.IvaCliJourneyError, match="did not grant complete verification") as refusal:
        cli_journey.run_iva_m303_cli_journey(
            executable=executable,
            authority_root=authority,
            storage_root=root,
            artifact_root=tmp_path / "artifacts",
            year=2025,
            runtime_scope=scope,
        )
    assert (scope.entered, scope.exited, scope.active) == (1, 1, False)
    assert scope.exit_error is refusal.value
    assert ("app", "ledger", "list") in stages
    assert stages[-1] == ("app", "modelo", "work", "verify", "revision")
    assert not any(args[:3] == ("app", "modelo", "export") for args in stages)


def test_dirty_store_refuses_before_runtime_scope_entry(tmp_path: Path) -> None:
    root = tmp_path / "store"
    root.mkdir()
    sentinel = root / "existing"
    sentinel.write_bytes(b"retain")
    scope = _RuntimeScope(root)
    authority = Path(__file__).resolve().parents[4] / ".authority"
    with pytest.raises(cli_journey.IvaCliJourneyError, match="fresh and empty"):
        cli_journey.run_iva_m303_cli_journey(
            executable=tmp_path / "unused-executable",
            authority_root=authority,
            storage_root=root,
            artifact_root=tmp_path / "artifacts",
            year=2025,
            runtime_scope=scope,
        )
    assert (scope.entered, scope.exited, scope.active) == (0, 0, False)
    assert sentinel.read_bytes() == b"retain"
    assert not (tmp_path / "artifacts").exists()
