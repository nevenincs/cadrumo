"""Interpreter invocation survives IVA readback and verification reopen boundaries."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping
from pathlib import Path

import pytest

from dev.acceptance.installed_cli import CommandEvidence, InstalledCli

from .. import cli_journey

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_bootstrap_prefix_survives_both_reopens_without_accepting_incomplete_verification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executable = tmp_path / "packaged-python"
    executable.touch()
    prefix = (
        "-c",
        "from cadrumo.entrypoints.cli.bootstrap import main; import sys; sys.argv=['aeat',*sys.argv[1:]]; main()",
    )
    clients: list[InstalledCli] = []
    receipts: list[cli_journey.SanitizedCommandReceipt] = []
    invocations: list[tuple[list[str], dict[str, object]]] = []
    make_receipt = cli_journey._command_receipt

    def record_receipt(
        *,
        args: tuple[str, ...],
        evidence: CommandEvidence,
        artifact: Path,
        result_ids: tuple[str, ...],
        redacted_paths: Mapping[Path, str] | None = None,
        cli_argument_prefix: tuple[str, ...] = (),
    ) -> cli_journey.SanitizedCommandReceipt:
        receipt = make_receipt(
            args=args,
            evidence=evidence,
            artifact=artifact,
            result_ids=result_ids,
            redacted_paths=redacted_paths,
            cli_argument_prefix=cli_argument_prefix,
        )
        receipts.append(receipt)
        return receipt

    def open_cli(
        executable: Path,
        *,
        storage_root: Path,
        authority_root: Path,
        passphrase: str,
        cli_argument_prefix: tuple[str, ...] = (),
    ) -> InstalledCli:
        cli = InstalledCli(
            executable,
            storage_root=storage_root,
            authority_root=authority_root,
            passphrase=passphrase,
            cli_argument_prefix=cli_argument_prefix,
        )
        clients.append(cli)
        return cli

    def execute(argv: list[str], **options: object) -> subprocess.CompletedProcess[str]:
        invocations.append((argv, options))
        assert argv[:5] == [str(executable.resolve()), *prefix, "--format", "json"]
        start = next(i for i, value in enumerate(argv) if value in {"app", "config"})
        args = argv[start:]
        result: dict[str, object] = {}
        if args[:4] == ["app", "ledger", "evidence", "add"]:
            result = {"evidence_id": "evidence-1"}
        elif args[:3] == ["app", "ledger", "add"]:
            result = {"transaction_id": "sale-1" if "INCOMING" in args else "purchase-1"}
        elif args[:4] == ["app", "ledger", "invoice", "add"]:
            result = {"invoice_id": "issued-1" if "issued" in args else "received-1"}
        elif args == ["app", "ledger", "list"]:
            result = {"rows": [{"transaction_id": "sale-1"}, {"transaction_id": "purchase-1"}]}
        elif args == ["app", "ledger", "invoice", "list"]:
            result = {"rows": [{"invoice_id": "issued-1"}, {"invoice_id": "received-1"}]}
        elif args == ["app", "ledger", "evidence", "list"]:
            result = {"rows": [{"evidence_id": "evidence-1"}]}
        elif args[:4] == ["app", "modelo", "work", "create"]:
            result = {"work_unit_id": "work-1"}
        elif args[:4] == ["app", "modelo", "work", "calculate"]:
            result = {
                "saved": True,
                "calculation_revision_id": "revision-1",
                "casilla_values": {"iva.resultado": "10.50"},
            }
        elif args[:4] == ["app", "modelo", "work", "verify"]:
            result = {
                "verification_report_id": "report-1",
                "calculation_revision_id": "revision-1",
                "completeness_status": "incomplete",
                "granted_verificado_completo": False,
            }
        return subprocess.CompletedProcess(argv, 0, json.dumps({"status": "ok", "result": result}), "")

    monkeypatch.setattr(cli_journey, "InstalledCli", open_cli)
    monkeypatch.setattr(cli_journey, "_command_receipt", record_receipt)
    monkeypatch.setattr(subprocess, "run", execute)
    authority_root = Path(__file__).resolve().parents[4] / ".authority"
    with pytest.raises(cli_journey.IvaCliJourneyError, match="did not grant complete verification"):
        cli_journey.run_iva_m303_cli_journey(
            executable=executable,
            authority_root=authority_root,
            storage_root=tmp_path / "storage",
            artifact_root=tmp_path / "artifacts",
            year=2025,
            cli_argument_prefix=prefix,
        )

    assert len(clients) == 3
    assert all(cli.cli_argument_prefix == prefix for cli in clients)
    assert clients[1].commands[0].command == "app ledger list"
    assert clients[2].commands[-1].command == "app modelo work verify"
    assert all(receipt.argv[:4] == (*prefix, "--format", "json") for receipt in receipts)
    secret = clients[0].passphrase
    assert all(secret not in repr(argv) + repr(options["env"]) for argv, options in invocations)
    assert secret not in repr(receipts)
    assert "synthetic-purchase.pdf" not in repr(receipts)
    assert not any("export" in argv for argv, _options in invocations)
