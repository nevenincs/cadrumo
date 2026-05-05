"""Regression tests for the user-facing ``aeat`` CLI surface."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from . import app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_RUNNER = CliRunner()


def _invoke(args: list[str]):
    return _RUNNER.invoke(app, args)


def _json_output(result: Any) -> str:
    import re

    # print(f"DEBUG: result.output={result.output!r}")
    match = re.search(r"(\{.*\}|\[.*\])", result.output, re.DOTALL)
    if not match:
        # print("DEBUG: no JSON match found")
        return result.output
    # print(f"DEBUG: matched={match.group(0)!r}")
    return match.group(0)


def _isolate_user_cli(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "unsecured")
    monkeypatch.setenv("AEAT_ALLOW_UNENCRYPTED", "1")
    monkeypatch.setenv("AEAT_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("AEAT_FINANCIAL_TXS_DIR", str(tmp_path / "txs"))
    monkeypatch.setenv("AEAT_INVOICES_DIR", str(tmp_path / "invoices"))
    monkeypatch.setenv("AEAT_DRAFTS_DIR", str(tmp_path / "drafts"))


def test_root_surface_contains_setup_and_app_only() -> None:
    result = _invoke(["--help"])

    assert result.exit_code == 0, result.output
    assert "setup" in result.output
    assert "app" in result.output
    for removed_command in (
        "auth",
        "financial",
        "filing",
        "bootstrap",
        "doctor",
        "declarations",
        "workspaces",
        "audits",
    ):
        assert removed_command not in result.output


def test_removed_developer_commands_are_not_registered() -> None:
    removed_commands = [
        ["financial", "--help"],
        ["filing", "--help"],
        ["bootstrap", "--help"],
        ["doctor", "--help"],
        ["auth", "--help"],
        ["app", "registry", "--help"],
        ["app", "declarations", "--help"],
        ["app", "workspaces", "--help"],
        ["app", "audits", "--help"],
        ["app", "ledger", "split", "--help"],
        ["app", "invoice", "show", "--help"],
    ]

    for command in removed_commands:
        result = _invoke(command)
        assert result.exit_code != 0, command


def test_app_surface_uses_singular_user_domains() -> None:
    result = _invoke(["app", "--help"])

    assert result.exit_code == 0, result.output
    for command in ("overview", "ledger", "invoice", "declaration"):
        assert command in result.output
    for removed_command in ("declarations", "workspaces", "audits", "transactions", "imports"):
        assert removed_command not in result.output


def test_user_help_surfaces_do_not_leak_translation_keys() -> None:
    commands = [
        ["--help"],
        ["setup", "--help"],
        ["setup", "auth", "--help"],
        ["setup", "auth", "status", "--help"],
        ["setup", "auth", "configure", "--help"],
        ["setup", "profile", "--help"],
        ["setup", "profile", "set", "--help"],
        ["setup", "profile", "validate", "--help"],
        ["app", "--help"],
        ["app", "overview", "--help"],
        ["app", "overview", "status", "--help"],
        ["app", "ledger", "--help"],
        ["app", "invoice", "--help"],
        ["app", "declaration", "--help"],
    ]

    for command in commands:
        result = _invoke(command)
        assert result.exit_code == 0, command
        assert "cli." not in result.output, command


def test_ledger_split_is_nested_inside_edit() -> None:
    ledger = _invoke(["app", "ledger", "--help"])
    edit = _invoke(["app", "ledger", "edit", "--help"])

    assert ledger.exit_code == 0, ledger.output
    assert edit.exit_code == 0, edit.output
    assert "--split" in edit.output
    assert "--skip" in edit.output
    assert "--reason" in edit.output


def test_invoice_and_ledger_share_review_wording() -> None:
    invoice = _invoke(["app", "invoice", "--help"])
    ledger = _invoke(["app", "ledger", "--help"])

    assert invoice.exit_code == 0, invoice.output
    assert ledger.exit_code == 0, ledger.output
    assert "review" in invoice.output
    assert "review" in ledger.output
    assert "show" not in invoice.output


def test_invoice_edit_and_match_cover_manual_review_paths() -> None:
    edit = _invoke(["app", "invoice", "edit", "--help"])
    match = _invoke(["app", "invoice", "match", "--help"])

    assert edit.exit_code == 0, edit.output
    assert match.exit_code == 0, match.output
    for field in ("base", "iva.rate", "iva.amount", "iva.category", "retention.rate", "payment.id", "document.path"):
        assert field in edit.output
    assert "--period" in match.output
    assert "--invoice" in match.output
    assert "--ledger" in match.output


def test_auth_configure_supports_user_provider_aliases(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "unsecured")
    monkeypatch.setenv("AEAT_ALLOW_UNENCRYPTED", "1")
    monkeypatch.setenv("AEAT_RUNS_DIR", str(tmp_path / "runs"))

    providers = _invoke(["setup", "auth", "providers"])
    configure = _invoke(["setup", "auth", "configure", "--provider", "clave_movil"])
    unavailable = _invoke(["setup", "auth", "configure", "--provider", "clave_permanente"])

    assert providers.exit_code == 0, providers.output
    assert "clave-permanente" in providers.output
    assert "unavailable" in providers.output
    assert configure.exit_code == 0, configure.output
    assert "clave-movil" in configure.output
    assert unavailable.exit_code != 0
    assert "unavailable-provider" in unavailable.output


def test_ledger_import_accepts_n26_csv_dry_run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "unsecured")
    monkeypatch.setenv("AEAT_ALLOW_UNENCRYPTED", "1")
    monkeypatch.setenv("AEAT_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("AEAT_FINANCIAL_TXS_DIR", str(tmp_path / "txs"))
    statement = tmp_path / "n26-q1.csv"
    statement.write_text(
        "\n".join(
            [
                "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID",
                "2026-01-05,Cliente SL,Invoice 2026-001,121.00,EUR,n26-001",
            ]
        ),
        encoding="utf-8",
    )

    imported = _invoke(
        ["--format", "json", "app", "ledger", "import", str(statement), "--provider", "n26", "--dry-run"]
    )
    overview = _invoke(["--format", "json", "app", "overview", "status"])

    assert imported.exit_code == 0, imported.output
    payload = json.loads(_json_output(imported))
    assert payload["rows"] == 1
    assert payload["dry_run"] is True
    assert payload["imported"] == 0
    assert overview.exit_code == 0, overview.output
    assert json.loads(_json_output(overview))["transactions"] == 0


def test_declaration_verify_accepts_file_not_export_option() -> None:
    result = _invoke(["app", "declaration", "verify", "--help"])

    assert result.exit_code == 0, result.output
    assert "--file" in result.output
    assert "--export" not in result.output


def test_declaration_help_uses_local_export_not_live_submission_wording() -> None:
    declaration = _invoke(["app", "declaration", "--help"])
    approve = _invoke(["app", "declaration", "approve", "--help"])
    combined = f"{declaration.output}\n{approve.output}".lower()

    assert declaration.exit_code == 0, declaration.output
    assert approve.exit_code == 0, approve.output
    assert "exportación local" in combined
    assert "archivo local" in combined
    assert "presentación" not in combined
    assert "submission" not in combined


def test_read_only_status_commands_use_isolated_local_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _isolate_user_cli(monkeypatch, tmp_path)

    setup = _invoke(["--format", "json", "setup", "status"])
    overview = _invoke(["--format", "json", "app", "overview", "status"])

    assert setup.exit_code == 0, setup.output
    assert overview.exit_code == 0, overview.output
    assert json.loads(_json_output(setup))["profile_ready"] is False
    assert json.loads(_json_output(overview))["transactions"] == 0


def test_invoice_import_edit_review_round_trip(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _isolate_user_cli(monkeypatch, tmp_path)
    invoice_path = tmp_path / "invoice.json"
    invoice_path.write_text(
        json.dumps(
            {
                "kind": "issued",
                "invoice_number": "INV-001",
                "issued_at": "2026-04-01",
                "counterparty_name": "Cliente SL",
                "counterparty_tax_id": "B12345674",
                "base_total": "100.00",
                "iva_total": "21.00",
                "grand_total": "121.00",
                "iva_rate": "21",
            }
        ),
        encoding="utf-8",
    )

    imported = _invoke(["app", "invoice", "import", str(invoice_path), "--kind", "issued"])
    reviewed = _invoke(["--format", "json", "app", "invoice", "review"])

    assert imported.exit_code == 0, imported.output
    assert reviewed.exit_code == 0, reviewed.output
    invoice_id = json.loads(_json_output(reviewed))["rows"][0]["id"]
    payment_id = "a" * 64

    edited = _invoke(
        [
            "app",
            "invoice",
            "edit",
            "--id",
            invoice_id,
            "--set",
            "base=120.00",
            "--set",
            "iva.rate=21",
            "--set",
            f"payment.id={payment_id}",
            "--reason",
            "manual-review",
        ]
    )
    after = _invoke(["--format", "json", "app", "invoice", "review"])

    assert edited.exit_code == 0, edited.output
    assert after.exit_code == 0, after.output
    row = json.loads(_json_output(after))["rows"][0]
    assert row["base"] == "120"
    assert row["iva"] == "25.2"
    assert row["payment.id"] == payment_id


def test_profile_validate_no_active_profile_blocks(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _isolate_user_cli(monkeypatch, tmp_path)

    result = _invoke(["--format", "json", "setup", "profile", "validate"])

    assert result.exit_code == 2, result.output
    payload = json.loads(_json_output(result))
    assert payload["valid"] is False
    assert payload["missing"] == ["profile"]


def test_profile_validate_routes_through_application_layer(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _isolate_user_cli(monkeypatch, tmp_path)

    init = _invoke(
        [
            "setup",
            "init",
            "--name",
            "kent",
            "--activity",
            "design",
            "--tax-id",
            "12345678Z",
        ]
    )
    assert init.exit_code == 0, init.output

    result = _invoke(["--format", "json", "setup", "profile", "validate"])

    assert result.exit_code == 0, result.output
    payload = json.loads(_json_output(result))
    assert payload["valid"] is True
    assert payload["missing_required"] == []
    # The application-layer ProfileValidationResult emits the typed
    # `present_required` field; the CLI must surface it through the
    # JSON envelope so machine-readable consumers see the registry
    # decision without re-deriving it.
    assert "tax.id" in payload["present_required"]
    assert "activity" in payload["present_required"]


def test_profile_validate_blocks_when_required_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _isolate_user_cli(monkeypatch, tmp_path)

    init = _invoke(
        [
            "setup",
            "init",
            "--name",
            "kent",
            "--activity",
            "design",
            "--tax-id",
            "12345678Z",
        ]
    )
    assert init.exit_code == 0, init.output

    cleared = _invoke(["setup", "profile", "unset", "tax.id"])
    assert cleared.exit_code == 0, cleared.output

    result = _invoke(["--format", "json", "setup", "profile", "validate"])

    assert result.exit_code == 2, result.output
    payload = json.loads(_json_output(result))
    assert payload["valid"] is False
    assert "tax.id" in payload["missing_required"]


def test_kent_n26_modelo_303_tape_fails_closed_without_registry_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _isolate_user_cli(monkeypatch, tmp_path)
    period = "2027-Q2"
    statement = tmp_path / "n26-q2.csv"
    statement.write_text(
        "\n".join(
            [
                "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID",
                "2027-04-15,Client SL,Invoice 2027-001,121.00,EUR,n26-2027-001",
            ]
        ),
        encoding="utf-8",
    )
    invoices = tmp_path / "invoices.csv"
    invoices.write_text(
        "\n".join(
            [
                "kind,invoice_number,issued_at,counterparty_name,counterparty_tax_id,base_total,iva_total,grand_total,iva_rate",
                "issued,INV-2027-001,2027-04-15,Client SL,B12345674,100.00,21.00,121.00,21",
            ]
        ),
        encoding="utf-8",
    )
    export_path = tmp_path / "modelo-303-2027-q2.txt"

    commands = [
        ["setup", "init", "--name", "kent", "--activity", "design", "--tax-id", "12345678Z"],
        ["setup", "auth", "configure", "--provider", "clave_movil"],
        ["setup", "auth", "login"],
        ["app", "ledger", "import", str(statement), "--provider", "n26", "--dry-run"],
        ["app", "ledger", "import", str(statement), "--provider", "n26", "--period", period, "--verify"],
    ]
    for command in commands:
        result = _invoke(command)
        assert result.exit_code == 0, result.output

    ledger_rows = json.loads(
        _json_output(_invoke(["--format", "json", "app", "ledger", "review", "--filter", f"period={period}"]))
    )
    transaction_id = ledger_rows["rows"][0]["id"]
    assert (
        _invoke(
            [
                "app",
                "ledger",
                "edit",
                "--id",
                transaction_id,
                "--set",
                "treatment=business",
                "--reason",
                "client-payment",
            ]
        ).exit_code
        == 0
    )
    assert _invoke(["app", "invoice", "import", str(invoices), "--kind", "issued"]).exit_code == 0
    invoice_rows = json.loads(
        _json_output(_invoke(["--format", "json", "app", "invoice", "review", "--filter", "status=pending"]))
    )
    invoice_id = invoice_rows["rows"][0]["id"]
    assert (
        _invoke(
            [
                "app",
                "invoice",
                "edit",
                "--id",
                invoice_id,
                "--set",
                f"payment.id={transaction_id}",
                "--reason",
                "match-payment",
            ]
        ).exit_code
        == 0
    )
    assert _invoke(["app", "invoice", "match", "--period", period]).exit_code == 0

    calculated = _invoke(["--format", "json", "app", "declaration", "calculate", "--modelo", "303", "--period", period])
    assert calculated.exit_code != 0
    assert "not present in the calculation registry" in calculated.output
    assert not export_path.exists()
