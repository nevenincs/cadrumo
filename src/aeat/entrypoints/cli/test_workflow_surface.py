"""Regression tests for the user-facing ``aeat`` CLI surface."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from aeat.application.diagnostics import build_cli_version_report
from aeat.domain.invoices import InvoiceCatalogueRepository
from aeat.domain.transactions import TransactionCatalogueRepository

from . import _import_failure_surface, _startup_import_error_text, app

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
    from aeat.adapters.persistence.storage.sql import dispose_engine

    dispose_engine()
    for name in (
        "AEAT_AUTH_PROVIDER",
        "AEAT_CERTIFICATE_PATH",
        "AEAT_CERTIFICATE_PASSWORD_SECRET",
        "AEAT_CLAVE_MOVIL_DNI_NIE",
        "AEAT_CLAVE_MOVIL_DNI_FECHA",
        "AEAT_CLAVE_MOVIL_NIE_SOPORTE",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "unsecured")
    monkeypatch.setenv("AEAT_ALLOW_UNENCRYPTED", "1")
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'aeat.db').as_posix()}")
    monkeypatch.setenv("AEAT_TOKEN_DIR", str(tmp_path / "tokens"))
    monkeypatch.setenv("AEAT_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("AEAT_FINANCIAL_TXS_DIR", str(tmp_path / "txs"))
    monkeypatch.setenv("AEAT_INVOICES_DIR", str(tmp_path / "invoices"))
    monkeypatch.setenv("AEAT_DRAFTS_DIR", str(tmp_path / "drafts"))


@pytest.fixture
def encrypted_user_cli(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    from aeat.adapters.persistence.storage import EphemeralMasterKeyProvider, override_master_key_provider
    from aeat.adapters.persistence.storage.sql import dispose_engine

    dispose_engine()
    monkeypatch.delenv("AEAT_SECRET_STORE_BACKEND", raising=False)
    monkeypatch.delenv("AEAT_ALLOW_UNENCRYPTED", raising=False)
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'aeat.db').as_posix()}")
    monkeypatch.setenv("AEAT_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("AEAT_FINANCIAL_TXS_DIR", str(tmp_path / "txs"))
    monkeypatch.setenv("AEAT_INVOICES_DIR", str(tmp_path / "invoices"))
    monkeypatch.setenv("AEAT_DRAFTS_DIR", str(tmp_path / "drafts"))
    override_master_key_provider(EphemeralMasterKeyProvider())
    try:
        yield tmp_path
    finally:
        override_master_key_provider(None)
        dispose_engine()


def _assert_secure_database_payload(tmp_path: Path, *plaintext_canaries: str) -> None:
    db_path = tmp_path / "aeat.db"
    assert db_path.exists()
    on_disk = db_path.read_bytes()
    assert b"secure_objects" in on_disk
    for canary in plaintext_canaries:
        assert canary.encode("utf-8") not in on_disk


def test_root_surface_contains_setup_and_app_only() -> None:
    result = _invoke(["--help"])

    assert result.exit_code == 0, result.output
    assert "setup" in result.output
    assert "config" in result.output
    assert "app" in result.output
    assert "--version" in result.output
    assert "--quiet" in result.output
    assert "--verbose" in result.output
    assert "--debug" in result.output
    assert "-V" in result.output
    assert "version" in result.output
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


def test_root_no_args_renders_help_successfully() -> None:
    result = _invoke([])

    assert result.exit_code == 0, result.output
    assert "setup" in result.output
    assert "config" in result.output
    assert "app" in result.output
    assert "--version" in result.output
    assert "Quickstart: aeat setup init --name NAME --tax-id NIF" in result.output


def test_setup_help_lists_commands_in_workflow_order() -> None:
    result = _invoke(["setup", "--help"])

    assert result.exit_code == 0, result.output
    workflow = ("init", "status", "auth", "profile")
    positions = [result.output.index(command) for command in workflow]
    assert positions == sorted(positions)


def test_removed_developer_commands_are_not_registered() -> None:
    removed_commands = [
        ["financial", "--help"],
        ["filing", "--help"],
        ["bootstrap", "--help"],
        ["doctor", "--help"],
        ["config", "doctor-logs", "--help"],
        ["auth", "--help"],
        ["app", "declarations", "--help"],
        ["app", "workspaces", "--help"],
        ["app", "audits", "--help"],
        ["app", "ledger", "split", "--help"],
        ["app", "invoice", "show", "--help"],
    ]

    for command in removed_commands:
        result = _invoke(command)
        assert result.exit_code != 0, command


def test_config_doctor_is_config_scoped_not_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _isolate_user_cli(monkeypatch, tmp_path)

    root_doctor = _invoke(["doctor", "--help"])
    help_result = _invoke(["config", "doctor", "--help"])
    text_result = _invoke(["config", "doctor"])
    json_result = _invoke(["--format", "json", "config", "doctor"])
    logs_result = _invoke(["config", "doctor", "logs", "--lines", "0"])

    assert root_doctor.exit_code != 0
    assert help_result.exit_code == 0, help_result.output
    assert text_result.exit_code == 0, text_result.output
    assert "Overall\t" in text_result.output
    assert "registry.load" in text_result.output
    payload = json.loads(_json_output(json_result))
    assert payload["registry"]["available"] is True
    assert "registry.load" in {check["name"] for check in payload["checks"]}
    assert logs_result.exit_code == 0, logs_result.output
    assert "path\t" in logs_result.output


def test_startup_import_failure_points_to_config_doctor_without_traceback() -> None:
    error = ModuleNotFoundError("No module named 'xlrd'", name="xlrd")

    assert _startup_import_error_text(error) == (
        "Cannot start AEAT command surface: missing dependency 'xlrd'.\nRun: aeat config doctor\n"
    )
    result = _RUNNER.invoke(_import_failure_surface("app", error), [])

    assert result.exit_code == 1, result.output
    assert "missing dependency 'xlrd'" in result.output
    assert "aeat config doctor" in result.output
    assert "Traceback" not in result.output


def test_version_surfaces_render_backend_registry_summary() -> None:
    report = build_cli_version_report()
    assert report.registry.available

    for command in (["--version"], ["-V"], ["version"]):
        result = _invoke(command)

        assert result.exit_code == 0, result.output
        assert f"aeat {report.package_version}" in result.output
        assert f"{report.registry.modelo_count} modelos" in result.output
        assert f"{report.registry.casilla_count} casillas" in result.output
        assert f"{report.registry.formula_count} formulas" in result.output


def test_version_command_can_emit_typed_json_report() -> None:
    expected = build_cli_version_report()

    result = _invoke(["--format", "json", "version"])

    assert result.exit_code == 0, result.output
    payload = json.loads(_json_output(result))
    assert payload["package_name"] == "aeat"
    assert payload["package_version"] == expected.package_version
    assert payload["registry"]["available"] is True
    assert payload["registry"]["modelo_count"] == expected.registry.modelo_count


def test_app_surface_uses_singular_user_domains() -> None:
    result = _invoke(["app", "--help"])

    assert result.exit_code == 0, result.output
    for command in ("overview", "ledger", "invoice", "declaration", "modelo", "registry"):
        assert command in result.output
    for removed_command in ("declarations", "workspaces", "audits", "transactions", "imports"):
        assert removed_command not in result.output


def test_registry_verification_gate_is_registered_under_app_surface() -> None:
    result = _invoke(["app", "registry", "verify", "--help"])

    assert result.exit_code == 0, result.output
    assert "--registry-root" in result.output
    assert "--source-root" in result.output


def test_modelo_introspection_surface_uses_registry_query_backend() -> None:
    listed = _invoke(["--format", "json", "app", "modelo", "list", "--year", "2026"])
    described = _invoke(["--format", "json", "app", "modelo", "describe", "303", "--period", "2026Q1"])
    casillas = _invoke(
        ["--format", "json", "app", "modelo", "casillas", "303", "--period", "2026Q1", "--input-kind", "computed"]
    )
    bindings = _invoke(["--format", "json", "app", "modelo", "bindings", "130", "--period", "2026Q1"])
    formulas = _invoke(["--format", "json", "app", "modelo", "formulas", "303", "--period", "2026Q1"])

    assert listed.exit_code == 0, listed.output
    assert described.exit_code == 0, described.output
    assert casillas.exit_code == 0, casillas.output
    assert bindings.exit_code == 0, bindings.output
    assert formulas.exit_code == 0, formulas.output
    listed_payload = json.loads(_json_output(listed))
    described_payload = json.loads(_json_output(described))
    casilla_payload = json.loads(_json_output(casillas))
    binding_payload = json.loads(_json_output(bindings))
    formula_payload = json.loads(_json_output(formulas))
    assert "303" in {row["code"] for row in listed_payload["modelos"]}
    assert described_payload["code"] == "303"
    assert described_payload["period"] == "1T"
    assert casilla_payload["rows"]
    assert {row["input_kind"] for row in casilla_payload["rows"]} == {"computed"}
    assert any(
        row["binding_id"] == "irpf.previous_year_economic_activity_net_income" for row in binding_payload["rows"]
    )
    assert {row["source"] for row in binding_payload["rows"]} == {"previous_filing"}
    assert any(row["input_casillas"] or row["input_bindings"] for row in formula_payload["rows"])


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


def test_review_filter_help_lists_supported_filter_keys() -> None:
    ledger = _invoke(["app", "ledger", "review", "--help"])
    invoice = _invoke(["app", "invoice", "review", "--help"])

    assert ledger.exit_code == 0, ledger.output
    assert invoice.exit_code == 0, invoice.output
    for token in ("status", "period", "issue", "import"):
        assert token in ledger.output
    compact_invoice_help = " ".join(invoice.output.split())
    for token in ("status=pending", "kind=issued|received"):
        assert token in compact_invoice_help
    assert "period" not in invoice.output


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


def test_auth_configure_lists_only_supported_provider_ids(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "unsecured")
    monkeypatch.setenv("AEAT_ALLOW_UNENCRYPTED", "1")
    monkeypatch.setenv("AEAT_RUNS_DIR", str(tmp_path / "runs"))

    providers = _invoke(["setup", "auth", "providers"])
    configure = _invoke(["setup", "auth", "configure", "--provider", "clave_movil"])
    unsupported_spelling = _invoke(["setup", "auth", "configure", "--provider", "clave-movil"])
    unsupported = _invoke(["setup", "auth", "configure", "--provider", "clave_permanente"])

    assert providers.exit_code == 0, providers.output
    assert "clave_permanente" not in providers.output
    assert "unavailable" not in providers.output
    assert configure.exit_code == 0, configure.output
    assert "clave_movil" in configure.output
    assert unsupported_spelling.exit_code != 0
    assert unsupported.exit_code != 0


def test_setup_auth_reset_help_uses_locale_backed_spanish_copy() -> None:
    result = _invoke(["setup", "auth", "reset", "--help"])

    assert result.exit_code == 0, result.output
    assert "Restablecer sesiones de autenticación persistidas" in result.output
    assert "Remove persisted" not in result.output
    assert "--sessions" in result.output
    assert "--locks" in result.output
    assert "--all" in result.output


def test_invoice_import_kind_help_lists_accepted_cli_values() -> None:
    result = _invoke(["app", "invoice", "import", "--help"])

    assert result.exit_code == 0, result.output
    assert "issued" in result.output
    assert "received" in result.output
    assert "emitidas o recibidas" not in result.output


def test_ledger_import_accepts_n26_csv_dry_run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _isolate_user_cli(monkeypatch, tmp_path)
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


def test_ledger_import_persists_transactions_as_ciphertext_envelope(encrypted_user_cli: Path) -> None:
    tmp_path = encrypted_user_cli
    canary = "CLI_ENCRYPTED_LEDGER_CANARY_5A2F"
    transaction_ref = "n26-secure-row-001"
    statement = tmp_path / "n26-secure.csv"
    statement.write_text(
        "\n".join(
            [
                "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID",
                f"2026-01-05,{canary},Invoice 2026-SEC,121.00,EUR,{transaction_ref}",
            ]
        ),
        encoding="utf-8",
    )

    imported = _invoke(["app", "ledger", "import", str(statement), "--provider", "n26"])

    assert imported.exit_code == 0, imported.output
    assert not (tmp_path / "txs" / "transactions.envelope.json").exists()
    _assert_secure_database_payload(tmp_path, canary, transaction_ref)
    catalogue = TransactionCatalogueRepository().load()
    [stored] = list(catalogue.transactions.values())
    assert stored.raw.counterparty == canary
    assert stored.raw.transaction_id == transaction_ref


def test_ledger_import_verify_source_records_original_file_digest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import hashlib

    _isolate_user_cli(monkeypatch, tmp_path)
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
    source = tmp_path / "n26-q1.pdf"
    source_bytes = b"original downloaded bank statement"
    source.write_bytes(source_bytes)

    imported = _invoke(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "import",
            str(statement),
            "--provider",
            "n26",
            "--dry-run",
            "--verify",
            "--source",
            str(source),
            "--verbose",
        ]
    )

    assert imported.exit_code == 0, imported.output
    payload = json.loads(_json_output(imported))
    assert payload["dry_run"] is True
    assert payload["validation"]["valid"] is True
    assert payload["source"]["requested"] is True
    assert payload["source"]["path"] == str(source.resolve())
    assert payload["source"]["sha256"] == hashlib.sha256(source_bytes).hexdigest()


def test_ledger_import_verify_source_rejects_missing_original_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _isolate_user_cli(monkeypatch, tmp_path)
    monkeypatch.chdir(tmp_path)
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
    missing_source = Path("missing.pdf")

    imported = _invoke(
        [
            "app",
            "ledger",
            "import",
            str(statement),
            "--provider",
            "n26",
            "--dry-run",
            "--verify",
            "--source",
            str(missing_source),
        ]
    )

    assert imported.exit_code != 0
    assert "missing.pdf" in imported.output


def test_declaration_verify_accepts_file_not_export_option() -> None:
    result = _invoke(["app", "declaration", "verify", "--help"])

    assert result.exit_code == 0, result.output
    assert "--file" in result.output
    assert "--export" not in result.output


def test_declaration_validate_uses_root_format_option() -> None:
    root = _invoke(["--help"])
    validate = _invoke(["app", "declaration", "validate", "--help"])

    assert root.exit_code == 0, root.output
    assert validate.exit_code == 0, validate.output
    assert "--format" in root.output
    assert "--format" not in validate.output
    assert "--output" in validate.output


def test_declaration_gate_options_use_user_workflow_descriptions() -> None:
    approve = _invoke(["app", "declaration", "approve", "--help"])
    status = _invoke(["app", "declaration", "status", "--help"])
    validate = _invoke(["app", "declaration", "validate", "--help"])
    verify = _invoke(["app", "declaration", "verify", "--help"])

    assert approve.exit_code == 0, approve.output
    assert status.exit_code == 0, status.output
    assert validate.exit_code == 0, validate.output
    assert verify.exit_code == 0, verify.output
    assert "Persona que revisó la declaración" in approve.output
    assert "Motivo auditado" in approve.output
    assert "status=pending" in status.output
    assert "approved" in status.output
    assert "stale" in status.output
    assert "Ruta del informe" in validate.output
    assert "Archivo local exportado" in verify.output


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
    setup_payload = json.loads(_json_output(setup))
    assert setup_payload["profile_ready"] is False
    assert setup_payload["profile_present_keys"] == 0
    assert setup_payload["profile_total_keys"] > 0
    assert json.loads(_json_output(overview))["transactions"] == 0
    assert "hashed_lookup.compute" not in setup.output
    assert "hashed_lookup.compute" not in overview.output


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


def test_invoice_import_persists_invoices_as_ciphertext_envelope(encrypted_user_cli: Path) -> None:
    tmp_path = encrypted_user_cli
    canary = "CLI_ENCRYPTED_INVOICE_CANARY_7B1D"
    invoice_number = "INV-SEC-001"
    invoice_path = tmp_path / "invoice-secure.json"
    invoice_path.write_text(
        json.dumps(
            {
                "kind": "issued",
                "invoice_number": invoice_number,
                "issued_at": "2026-04-01",
                "counterparty_name": canary,
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

    assert imported.exit_code == 0, imported.output
    assert not (tmp_path / "invoices" / "invoices.envelope.json").exists()
    _assert_secure_database_payload(tmp_path, canary, invoice_number)
    catalogue = InvoiceCatalogueRepository().load()
    [stored] = list(catalogue.values())
    assert stored.counterparty_name == canary
    assert stored.invoice_number == invoice_number


def test_profile_validate_no_active_profile_blocks(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _isolate_user_cli(monkeypatch, tmp_path)

    result = _invoke(["--format", "json", "setup", "profile", "validate"])

    assert result.exit_code == 2, result.output
    payload = json.loads(_json_output(result))
    assert payload["valid"] is False
    assert payload["missing"] == ["profile"]


def test_profile_set_requires_active_profile(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _isolate_user_cli(monkeypatch, tmp_path)

    result = _invoke(["setup", "profile", "set", "tax.id", "12345678Z"])

    assert result.exit_code == 2, result.output
    assert "no-active-profile" in result.output
    assert "aeat setup init --name NAME" in result.output


def test_root_error_boundary_renders_auth_session_errors_without_traceback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _isolate_user_cli(monkeypatch, tmp_path)

    init = _invoke(["setup", "init", "--name", "operator", "--tax-id", "12345678Z"])
    configure = _invoke(["setup", "auth", "configure", "--provider", "clave_movil"])
    result = _invoke(["setup", "auth", "whoami"])

    assert init.exit_code == 0, init.output
    assert configure.exit_code == 0, configure.output
    assert result.exit_code == 3, result.output
    assert "AUTH:" in result.output
    assert "aeat setup auth login" in result.output
    assert "Traceback" not in result.output
    assert "AuthSessionUnavailableError" not in result.output


def test_root_error_boundary_honours_global_json_format(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _isolate_user_cli(monkeypatch, tmp_path)

    init = _invoke(["setup", "init", "--name", "operator", "--tax-id", "12345678Z"])
    configure = _invoke(["setup", "auth", "configure", "--provider", "clave_movil"])
    result = _invoke(["--format", "json", "setup", "auth", "whoami"])

    assert init.exit_code == 0, init.output
    assert configure.exit_code == 0, configure.output
    assert result.exit_code == 3, result.output
    payload = json.loads(_json_output(result))["error"]
    assert payload["category"] == "AUTH"
    assert payload["code"] == "AUTH_CLI_AUTH_SESSION_UNAVAILABLE"
    assert payload["suggestion"] == "aeat setup auth login"
    assert "Traceback" not in result.output


def test_profile_keys_match_domain_registry_names() -> None:
    result = _invoke(["setup", "profile", "list-keys"])

    assert result.exit_code == 0, result.output
    for key in (
        "tax.id",
        "activity",
        "name",
        "surnames",
        "address.postcode",
        "declaration.type",
        "taxpayer.sex",
        "taxpayer.marital_status",
        "taxpayer.birth_date",
        "taxpayer.disability_grade",
        "taxpayer.death_date",
        "spouse.tax.id",
        "spouse.name",
        "spouse.surnames",
        "spouse.birth_date",
        "spouse.sex",
        "spouse.disability_grade",
        "spouse.non_resident_irpf",
        "spouse.eu_eea_resident",
        "spouse.eu_eea_country",
        "family.descendants_eu_eea_deduction",
        "family.minor_children_in_unit",
    ):
        assert key in result.output
    for retired_key in ("tax.name", "activity.label", "activity.code"):
        assert retired_key not in result.output


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
            "operator",
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
    assert payload["present_keys"] == 2
    assert payload["total_keys"] > payload["present_keys"]


def test_profile_validate_text_shows_schema_completeness(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _isolate_user_cli(monkeypatch, tmp_path)

    init = _invoke(
        [
            "setup",
            "init",
            "--name",
            "operator",
            "--activity",
            "design",
            "--tax-id",
            "12345678Z",
        ]
    )
    result = _invoke(["setup", "profile", "validate"])

    assert init.exit_code == 0, init.output
    assert result.exit_code == 0, result.output
    assert "\t2/" in result.output
    assert "Completeness" in result.output or "Completitud" in result.output


def test_profile_show_all_keys_surfaces_unset_schema_rows(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _isolate_user_cli(monkeypatch, tmp_path)

    init = _invoke(
        [
            "setup",
            "init",
            "--name",
            "operator",
            "--activity",
            "design",
            "--tax-id",
            "12345678Z",
        ]
    )
    default_show = _invoke(["setup", "profile", "show"])
    all_keys = _invoke(["setup", "profile", "show", "--all-keys"])

    assert init.exit_code == 0, init.output
    assert default_show.exit_code == 0, default_show.output
    assert all_keys.exit_code == 0, all_keys.output
    assert "tax.id\t12345678Z" in default_show.output
    assert "address.postcode" not in default_show.output
    assert "address.postcode\t<unset>" in all_keys.output
    assert "--all-keys" in _invoke(["setup", "profile", "show", "--help"]).output
    assert "--unset" in _invoke(["setup", "profile", "show", "--help"]).output


def test_profile_show_all_keys_json_uses_typed_rows(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _isolate_user_cli(monkeypatch, tmp_path)

    init = _invoke(["setup", "init", "--name", "operator", "--activity", "design", "--tax-id", "12345678Z"])
    result = _invoke(["--format", "json", "setup", "profile", "show", "--all-keys"])

    assert init.exit_code == 0, init.output
    assert result.exit_code == 0, result.output
    payload = json.loads(_json_output(result))
    rows = {row["key"]: row for row in payload["rows"]}
    assert rows["tax.id"]["is_set"] is True
    assert rows["tax.id"]["value"] == "12345678Z"
    assert rows["address.postcode"]["is_set"] is False
    assert rows["address.postcode"]["value"] is None


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
            "operator",
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


def test_operator_n26_modelo_303_tape_builds_registry_draft_from_invoices(
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
    commands = [
        ["setup", "init", "--name", "operator", "--activity", "design", "--tax-id", "12345678Z"],
        ["setup", "auth", "configure", "--provider", "clave_movil"],
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
    assert calculated.exit_code == 0, calculated.output
    payload = json.loads(_json_output(calculated))
    values = {value["casilla_id"]: value for value in payload["draft"]["values"]}
    assert payload["draft"]["modelo"] == "303"
    assert payload["draft"]["period"] == "2027Q2"
    assert payload["draft"]["schema_version"] == "registry:303:2009-y-siguientes"
    assert values["iva.repercutido.general"]["value"] == "21.00"
    assert values["iva.cuota-devengada-total"]["value"] == "21.00"
    assert values["iva.resultado-regimen-general"]["value"] == "21.00"
    assert payload["summary"]["next_action"] == "resolve-blockers"


def test_setup_profile_list_keys_includes_iva_regime_and_engine_axes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The IVA, IRPF, and modelo enrolment keys the deadline engine reads must be settable.

    Pre-W2, ``aeat setup profile list-keys`` only listed 22 RENTA-shaped
    personal-identity keys, so users could not set the regime values
    the deadline engine consumed -- ``aeat setup profile set
    iva.regime general`` rejected the key. This test guards the
    extension: every engine-consumed axis (iva.regime, iva.roi_enrolled,
    does_intracomunitario, has_employees, ...) appears in list-keys
    output.
    """
    _isolate_user_cli(monkeypatch, tmp_path)
    init_result = _invoke(["setup", "init", "--name", "kent", "--tax-id", "00000000T", "--activity", "Servicios"])
    assert init_result.exit_code == 0, init_result.output

    keys_result = _invoke(["--format", "json", "setup", "profile", "list-keys"])
    assert keys_result.exit_code == 0, keys_result.output
    keys_payload = json.loads(_json_output(keys_result))
    listed = {entry["key"] for entry in keys_payload["keys"]}
    expected = {
        "iva.regime",
        "iva.roi_enrolled",
        "iva.oss_enrolled",
        "iva.intracommunity_operations_exceed_50000_eur",
        "does_intracomunitario",
        "has_employees",
        "uses_objective_estimation_irpf",
        "third_party_transactions_above_347_threshold",
        "bienes_extranjero_above_threshold",
    }
    missing = expected - listed
    assert not missing, f"engine-consumed keys missing from list-keys: {missing}"


def test_setup_profile_set_iva_regime_round_trips_to_deadline_engine(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Setting ``iva.regime general`` must reach the deadline engine as IVARegime.GENERAL.

    Round-trip: ``setup profile set iva.regime general`` -> stored in
    user_cli state -> ``_profile_to_autonomo`` -> ``IVARegime.GENERAL``.
    The case-insensitive parser also accepts ``GENERAL``,
    ``simplificado``, etc.
    """
    from aeat.application.workflow import workflow_state_repository
    from aeat.domain.deadlines import IVARegime, autonomo_profile_from_mapping

    _isolate_user_cli(monkeypatch, tmp_path)
    init_result = _invoke(["setup", "init", "--name", "kent", "--tax-id", "00000000T", "--activity", "Servicios"])
    assert init_result.exit_code == 0, init_result.output

    set_result = _invoke(["setup", "profile", "set", "iva.regime", "general"])
    assert set_result.exit_code == 0, set_result.output

    state = workflow_state_repository().load()
    record = state.active_profile_record()
    assert record is not None
    profile = autonomo_profile_from_mapping(record.values, tax_id_default="00000000T")
    assert profile.iva_regime is IVARegime.GENERAL


def test_setup_profile_set_does_intracomunitario_round_trips_underscore_form(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Underscored keys must survive the user-cli store and surface to the engine.

    The engine reads ``does_intracomunitario`` as a literal key. The
    user-cli normaliser preserves underscores so the stored form
    matches the engine lookup; this test pins the round-trip.
    """
    from aeat.application.workflow import workflow_state_repository
    from aeat.domain.deadlines import autonomo_profile_from_mapping

    _isolate_user_cli(monkeypatch, tmp_path)
    init_result = _invoke(["setup", "init", "--name", "kent", "--tax-id", "00000000T", "--activity", "Servicios"])
    assert init_result.exit_code == 0, init_result.output

    set_result = _invoke(["setup", "profile", "set", "does_intracomunitario", "true"])
    assert set_result.exit_code == 0, set_result.output

    get_result = _invoke(["--format", "json", "setup", "profile", "get", "does_intracomunitario"])
    assert get_result.exit_code == 0, get_result.output
    get_payload = json.loads(_json_output(get_result))
    assert get_payload["value"] == "true"

    state = workflow_state_repository().load()
    record = state.active_profile_record()
    assert record is not None
    profile = autonomo_profile_from_mapping(record.values, tax_id_default="00000000T")
    assert profile.does_intracomunitario is True


def test_declaration_calculate_accepts_binding_assignment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """``--binding KEY=VALUE`` must inject the value into the calculate inputs.

    Without ``--binding``, ``aeat app declaration calculate --modelo 130
    --period 2026Q1`` rejects with a missing-binding error because the
    pago-fraccionado bracket per RD 439/2007 art. 110 needs the prior
    year's net income from economic activity. With the binding
    supplied, calculate succeeds, blockers drop to zero, and the next
    action becomes ``approve`` rather than ``resolve-blockers``.
    """
    _isolate_user_cli(monkeypatch, tmp_path)
    init_result = _invoke(["setup", "init", "--name", "kent", "--tax-id", "00000000T", "--activity", "Servicios"])
    assert init_result.exit_code == 0, init_result.output

    without = _invoke(["app", "declaration", "calculate", "--modelo", "130", "--period", "2026Q1"])
    assert without.exit_code != 0
    assert "previous_year_economic_activity_net_income" in without.output

    with_binding = _invoke(
        [
            "--format",
            "json",
            "app",
            "declaration",
            "calculate",
            "--modelo",
            "130",
            "--period",
            "2026Q1",
            "--binding",
            "irpf.previous_year_economic_activity_net_income=13000",
        ]
    )
    assert with_binding.exit_code == 0, with_binding.output
    payload = json.loads(_json_output(with_binding))
    assert payload["summary"]["blocker_count"] == 0
    assert payload["summary"]["next_action"] in {"approve", "review", "export"}


def test_declaration_calculate_rejects_malformed_binding(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Malformed ``--binding`` arguments must raise the typed CLI usage error.

    Two failure modes:
    - missing ``=``: the parser cannot split the assignment.
    - non-decimal value: the parser cannot coerce the value.

    Both must exit non-zero with an i18n-rendered message; no traceback,
    no silent acceptance, no calculate run.
    """
    _isolate_user_cli(monkeypatch, tmp_path)
    init_result = _invoke(["setup", "init", "--name", "kent", "--tax-id", "00000000T", "--activity", "Servicios"])
    assert init_result.exit_code == 0, init_result.output

    no_equals = _invoke(
        [
            "app",
            "declaration",
            "calculate",
            "--modelo",
            "130",
            "--period",
            "2026Q1",
            "--binding",
            "noequals",
        ]
    )
    assert no_equals.exit_code != 0
    assert "noequals" in no_equals.output
    assert "Traceback" not in no_equals.output

    bad_value = _invoke(
        [
            "app",
            "declaration",
            "calculate",
            "--modelo",
            "130",
            "--period",
            "2026Q1",
            "--binding",
            "key=not_a_number",
        ]
    )
    assert bad_value.exit_code != 0
    assert "not_a_number" in bad_value.output
    assert "Traceback" not in bad_value.output


@pytest.mark.parametrize("verb", ["validate", "preview"])
def test_declaration_verbs_accept_modelo_period_selector(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    verb: str,
) -> None:
    """Every declaration verb must resolve a draft from ``(--modelo, --period)``.

    Pre-W4, only ``status`` and ``review`` accepted the
    ``(--modelo, --period)`` selector; ``approve``, ``validate``,
    ``preview``, ``export``, and ``edit`` required ``--id``. The
    operator could not chain ``calculate`` -> ``validate`` without
    capturing the draft id manually. This test pins the unified
    selector contract on the read-only verbs (validate and preview),
    which are safe to call against an uncommitted draft.
    """
    _isolate_user_cli(monkeypatch, tmp_path)
    init_result = _invoke(["setup", "init", "--name", "kent", "--tax-id", "00000000T", "--activity", "Servicios"])
    assert init_result.exit_code == 0, init_result.output

    calc = _invoke(
        [
            "app",
            "declaration",
            "calculate",
            "--modelo",
            "130",
            "--period",
            "2026Q1",
            "--binding",
            "irpf.previous_year_economic_activity_net_income=13000",
        ]
    )
    assert calc.exit_code == 0, calc.output

    invoked = _invoke(["app", "declaration", verb, "--modelo", "130", "--period", "2026Q1"])
    assert invoked.exit_code == 0, f"verb={verb} output={invoked.output}"
    assert "No such option" not in invoked.output


@pytest.mark.parametrize("verb", ["approve", "validate", "preview"])
def test_declaration_verbs_reject_ambiguous_selector(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    verb: str,
) -> None:
    """Passing both ``--id`` and ``--modelo``/``--period`` must raise the typed error.

    Guards against silent precedence: the unified selector contract
    rejects ambiguous combinations with the i18n'd
    ``draft_selector_ambiguous`` message rather than picking one form
    and ignoring the other.
    """
    _isolate_user_cli(monkeypatch, tmp_path)
    init_result = _invoke(["setup", "init", "--name", "kent", "--tax-id", "00000000T", "--activity", "Servicios"])
    assert init_result.exit_code == 0, init_result.output

    extra: list[str] = []
    if verb == "approve":
        extra = ["--by", "tester", "--reason", "test"]

    result = _invoke(
        [
            "app",
            "declaration",
            verb,
            "--id",
            "abc",
            "--modelo",
            "303",
            "--period",
            "2026Q1",
            *extra,
        ]
    )
    assert result.exit_code != 0
    assert "Traceback" not in result.output


def _normalise_help_output(raw: str) -> str:
    import re

    # Strip Unicode box-drawing chars Typer/Click renders around help cells,
    # then collapse all whitespace runs into single spaces so the wrapped
    # help text reads as one continuous string.
    stripped = re.sub(r"[─-╿]", " ", raw)
    return re.sub(r"\s+", " ", stripped)


def test_root_help_exposes_shell_completion_options() -> None:
    """``aeat --help`` must expose Typer's completion install/show options (UX-013).

    The audit's UX-013 listed shell completion as a separate feature
    request. Typer ships the install/show completion flags out of the
    box once ``add_completion=True`` is set on the root app. This test
    pins that wiring so the completion surface cannot regress.
    """
    result = _invoke(["--help"])
    assert result.exit_code == 0, result.output
    output = _normalise_help_output(result.output)
    assert "--install-completion" in output, output
    assert "--show-completion" in output, output


def test_setup_init_help_carries_examples_and_format_hints() -> None:
    """``aeat setup init --help`` must surface format hints and examples (UX-004).

    The audit (UX-004) flagged the ``--name``, ``--activity``, and
    ``--tax-id`` help strings as surface-only one-liners with no
    format hint, no example, and no discovery pointer. After uplift,
    each flag's help text carries an ``Ejemplo:`` (in the default
    Spanish locale) and the tax-id help mentions the NIF / NIE / CIF
    canonical formats explicitly.
    """
    result = _invoke(["setup", "init", "--help"])
    assert result.exit_code == 0, result.output
    output = _normalise_help_output(result.output)
    assert "Ejemplo:" in output, output
    assert "12345678Z" in output, output
    assert "IAE/CNAE" in output or "CNAE" in output, output


def test_setup_auth_configure_help_points_at_providers_command() -> None:
    """``aeat setup auth configure --help`` must reference the discovery command (UX-004).

    The audit flagged ``--provider`` as accepting free TEXT without a
    pointer to ``aeat setup auth providers`` for valid values. The
    uplifted help text MUST reference the discovery command so the
    operator can list supported providers without external docs.
    """
    result = _invoke(["setup", "auth", "configure", "--help"])
    assert result.exit_code == 0, result.output
    output = _normalise_help_output(result.output)
    assert "aeat setup auth providers" in output, output
    assert "certificate" in output, output
    assert "clave_movil" in output, output


def test_declaration_calculate_enumerates_blockers_with_runnable_next_action(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Calculate output must enumerate blocker rows and a copy-paste next-action.

    UX-021: the previous output reported only an aggregate count
    ``Bloqueos: 2`` plus the recipe token ``Siguiente: resolve-blockers``,
    leaving the operator no path to act. Now each blocker renders on
    its own line as ``blocker\\tcasilla.<id>\\t<message>`` and the
    Siguiente line carries a runnable command parameterised on the
    current modelo and period.
    """
    _isolate_user_cli(monkeypatch, tmp_path)
    init_result = _invoke(["setup", "init", "--name", "kent", "--tax-id", "00000000T", "--activity", "Servicios"])
    assert init_result.exit_code == 0, init_result.output

    calc = _invoke(["app", "declaration", "calculate", "--modelo", "303", "--period", "2026Q1"])
    assert calc.exit_code == 0, calc.output
    blocker_lines = [line for line in calc.output.splitlines() if line.startswith("blocker\t")]
    assert blocker_lines, f"expected at least one blocker line; got: {calc.output}"
    next_line = next(
        (line for line in calc.output.splitlines() if "aeat app declaration" in line),
        None,
    )
    assert next_line is not None, calc.output
    assert "--modelo 303" in next_line and "--period 2026Q1" in next_line
