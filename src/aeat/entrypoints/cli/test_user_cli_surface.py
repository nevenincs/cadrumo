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
    assert "app" in result.output
    assert "--version" in result.output
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
    for command in ("overview", "ledger", "invoice", "declaration", "registry"):
        assert command in result.output
    for removed_command in ("declarations", "workspaces", "audits", "transactions", "imports"):
        assert removed_command not in result.output


def test_registry_verification_gate_is_registered_under_app_surface() -> None:
    result = _invoke(["app", "registry", "verify", "--help"])

    assert result.exit_code == 0, result.output
    assert "--registry-root" in result.output
    assert "--source-root" in result.output


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


def test_operator_n26_modelo_303_tape_fails_closed_without_registry_snapshot(
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
    assert calculated.exit_code != 0
    assert "not present in the calculation registry" in calculated.output
    assert not export_path.exists()
