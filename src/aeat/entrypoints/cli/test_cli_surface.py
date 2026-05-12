"""Integration tests for the user-facing ``aeat`` CLI.

These tests assert that every command namespace exists, that the thin
transport handlers route into the application layer, and that the
JSON envelope matches the typed records the backend exposes. They
do NOT exercise live AEAT, certificate auth, or any network surface.

Each test isolates state through ``AEAT_RUNS_DIR`` /
``AEAT_FINANCIAL_TXS_DIR`` / ``AEAT_INVOICES_DIR`` /
``AEAT_DRAFTS_DIR`` env vars set on a per-test ``tmp_path``, and
through ``AEAT_SECRET_STORE_BACKEND=unsecured`` so the encrypted
state envelope writes through the in-process plain-bytes backend.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aeat.application.filing import FilingOperatorProfile, build_draft, build_runtime_schema_provider
from aeat.domain.calculations.registry import RegistryError
from aeat.domain.filing import FilingBuilderError

from . import app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_RUNNER = CliRunner()


def _isolate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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


def _invoke(args: list[str]):
    return _RUNNER.invoke(app, args)


def _registry_modelo_calculable_without_cli_sources() -> str:
    provider = build_runtime_schema_provider()
    profile = FilingOperatorProfile(tax_id="12345678Z", display_name="CLI surface")
    for modelo in sorted(provider.subviews):
        try:
            build_draft(
                modelo=modelo,
                period="2026Q1",
                profile=profile,
                inputs={},
                schema_provider=provider,
            )
        except (FilingBuilderError, RegistryError):
            # FilingBuilderError: missing CLI-supplied inputs.
            # RegistryError: modelo has no revision covering the test period.
            continue
        return modelo
    raise AssertionError("registry has no modelo calculable from current CLI sources")


def _registry_modelo_requiring_cli_sources() -> str:
    provider = build_runtime_schema_provider()
    profile = FilingOperatorProfile(tax_id="12345678Z", display_name="CLI surface")
    for modelo in sorted(provider.subviews):
        try:
            build_draft(
                modelo=modelo,
                period="2026Q1",
                profile=profile,
                inputs={},
                schema_provider=provider,
            )
        except FilingBuilderError as exc:
            if "has no supplied value" in str(exc):
                return modelo
            continue
        except RegistryError:
            # Modelo lacks a revision for the test period — not a CLI-input gap.
            continue
    raise AssertionError("registry has no modelo requiring additional CLI sources")


# ---------------------------------------------------------------------
# Namespace surface
# ---------------------------------------------------------------------


def test_root_help_lists_config_and_app() -> None:
    result = _invoke(["--help"])
    assert result.exit_code == 0
    assert "config" in result.output
    assert "app" in result.output
    assert "auth" not in result.output


def test_app_help_lists_singular_domains() -> None:
    result = _invoke(["app", "--help"])
    assert result.exit_code == 0
    for token in ("overview", "ledger", "invoice", "declaration"):
        assert token in result.output
    for plural_namespace in ("workspaces", "audits", "declarations"):
        assert plural_namespace not in result.output


def test_top_level_auth_is_not_user_facing() -> None:
    result = _invoke(["auth", "--help"])
    assert result.exit_code != 0


def test_app_declaration_help_carries_subcommands() -> None:
    result = _invoke(["app", "declaration", "--help"])
    assert result.exit_code == 0
    for token in ("calculate", "review", "status", "edit", "approve", "validate", "preview", "export", "verify"):
        assert token in result.output


# ---------------------------------------------------------------------
# App namespace — overview / ledger / invoice / declaration
# ---------------------------------------------------------------------


def test_app_overview_status_bare_renders_counts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    result = _invoke(["--format", "json", "app", "overview", "status"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["transactions"] == 0
    assert payload["invoices"] == 0
    assert payload["drafts"] == 0


def test_app_overview_status_calendar_renders_period_table(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _isolate(monkeypatch, tmp_path)
    result = _invoke(
        [
            "--format",
            "json",
            "app",
            "overview",
            "status",
            "--calendar",
            "--from",
            "2026-01-01",
            "--to",
            "2026-04-30",
        ]
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert "calendar" in payload
    assert payload["calendar"]["range"]["from_date"] == "2026-01-01"


def test_app_overview_status_calendar_requires_dates(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _isolate(monkeypatch, tmp_path)
    result = _invoke(["app", "overview", "status", "--calendar"])
    assert result.exit_code != 0


def test_app_ledger_import_dry_run_does_not_persist(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _isolate(monkeypatch, tmp_path)
    statement = tmp_path / "n26.csv"
    statement.write_text(
        "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID\n"
        "2026-04-15,Client SL,Invoice 1,121.00,EUR,n26-001\n",
        encoding="utf-8",
    )
    dry = _invoke(["--format", "json", "app", "ledger", "import", str(statement), "--provider", "csv", "--dry-run"])
    assert dry.exit_code == 0
    payload = json.loads(dry.output)
    assert payload["dry_run"] is True
    assert payload["imported"] == 0
    after = _invoke(["--format", "json", "app", "overview", "status"])
    assert json.loads(after.output)["transactions"] == 0


def test_app_ledger_import_reimport_edit_review_round_trips_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _isolate(monkeypatch, tmp_path)
    statement = tmp_path / "n26.csv"
    statement.write_text(
        "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID\n"
        "2026-04-15,Client SL,Invoice 1,121.00,EUR,n26-001\n"
        "2026-04-16,SaaS Vendor,Subscription,-48.40,EUR,n26-002\n",
        encoding="utf-8",
    )
    imported = _invoke(["--format", "json", "app", "ledger", "import", str(statement), "--provider", "csv"])
    assert imported.exit_code == 0
    imported_payload = json.loads(imported.output)
    assert imported_payload["rows"] == 2
    assert imported_payload["imported"] == 2
    assert imported_payload["skipped"] == 0

    repeated = _invoke(["--format", "json", "app", "ledger", "import", str(statement), "--provider", "csv"])
    assert repeated.exit_code == 0
    repeated_payload = json.loads(repeated.output)
    assert repeated_payload["rows"] == 2
    assert repeated_payload["imported"] == 0
    assert repeated_payload["skipped"] == 2

    review = _invoke(["--format", "json", "app", "ledger", "review"])
    assert review.exit_code == 0
    payload = json.loads(review.output)
    rows_by_description = {row["description"]: row for row in payload["rows"]}
    assert set(rows_by_description) == {"Invoice 1", "Subscription"}
    assert {row["status"] for row in payload["rows"]} == {"pending"}
    vendor_id = rows_by_description["Subscription"]["id"]

    edited = _invoke(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "edit",
            "--id",
            vendor_id,
            "--set",
            "category=software",
            "--set",
            "business.share=0.75",
            "--split",
            "business=0.75",
            "--split",
            "personal=0.25",
            "--reason",
            "classify mixed-use software subscription",
        ]
    )
    assert edited.exit_code == 0
    edited_payload = json.loads(edited.output)
    assert edited_payload["review"]["fields"] == {"business.share": "0.75", "category": "software"}
    assert edited_payload["review"]["split"]["business_share"] == "0.75"
    assert edited_payload["review"]["split"]["personal_share"] == "0.25"

    single = _invoke(["--format", "json", "app", "ledger", "review", "--id", vendor_id])
    assert single.exit_code == 0
    single_payload = json.loads(single.output)
    assert single_payload["amount"] == "-48.4"
    assert single_payload["review"]["fields"]["category"] == "software"
    assert single_payload["review"]["split"]["reason"] == "classify mixed-use software subscription"

    reviewed = _invoke(["--format", "json", "app", "ledger", "review", "--filter", "status=reviewed"])
    assert reviewed.exit_code == 0
    reviewed_payload = json.loads(reviewed.output)
    assert reviewed_payload["rows"] == [
        {
            "id": vendor_id,
            "date": "2026-04-16",
            "amount": "-48.40",
            "description": "Subscription",
            "status": "reviewed",
        }
    ]

    cleared = _invoke(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "edit",
            "--id",
            vendor_id,
            "--split",
            "clear",
            "--reason",
            "remove mixed-use split",
        ]
    )
    assert cleared.exit_code == 0
    cleared_payload = json.loads(cleared.output)
    assert cleared_payload["review"]["split"] is None
    assert cleared_payload["review"]["fields"] == {"business.share": "0.75", "category": "software"}


def test_app_ledger_review_filter_rejects_unknown_key(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _isolate(monkeypatch, tmp_path)
    result = _invoke(["app", "ledger", "review", "--filter", "kind=received"])
    assert result.exit_code != 0


def test_app_ledger_edit_skip_requires_reason(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _isolate(monkeypatch, tmp_path)
    result = _invoke(["app", "ledger", "edit", "--id", "abc", "--skip", "true"])
    # missing --reason ⇒ Typer exits non-zero
    assert result.exit_code != 0


def test_app_invoice_review_filter_kind_lowercase(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _isolate(monkeypatch, tmp_path)
    result = _invoke(["--format", "json", "app", "invoice", "review", "--filter", "kind=issued"])
    assert result.exit_code == 0


def test_app_invoice_match_period_renders_typed_result(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _isolate(monkeypatch, tmp_path)
    result = _invoke(["--format", "json", "app", "invoice", "match", "--period", "2026-Q1"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["period"] == "2026Q1"
    assert payload["matched"] == []
    assert payload["unmatched"] == []


def test_app_invoice_import_reimport_edit_match_round_trips_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _isolate(monkeypatch, tmp_path)
    statement = tmp_path / "bank.csv"
    statement.write_text(
        "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID\n"
        "2026-04-15,Client SL,Invoice F-001,121.00,EUR,bank-001\n",
        encoding="utf-8",
    )
    ledger_import = _invoke(["--format", "json", "app", "ledger", "import", str(statement), "--provider", "csv"])
    assert ledger_import.exit_code == 0
    ledger_review = _invoke(["--format", "json", "app", "ledger", "review"])
    assert ledger_review.exit_code == 0
    payment_id = json.loads(ledger_review.output)["rows"][0]["id"]

    invoices = tmp_path / "issued.json"
    invoices.write_text(
        json.dumps(
            [
                {
                    "invoice_number": "F-001",
                    "issued_at": "2026-04-14",
                    "counterparty_tax_id": "B12345674",
                    "counterparty_name": "Client SL",
                    "base_total": "100.00",
                    "iva_rate": "21",
                    "iva_total": "21.00",
                    "grand_total": "121.00",
                }
            ]
        ),
        encoding="utf-8",
    )

    imported = _invoke(["--format", "json", "app", "invoice", "import", str(invoices), "--kind", "issued"])
    assert imported.exit_code == 0
    imported_payload = json.loads(imported.output)
    assert imported_payload == {"rows": 1, "imported": 1, "skipped": 0}

    repeated = _invoke(["--format", "json", "app", "invoice", "import", str(invoices), "--kind", "issued"])
    assert repeated.exit_code == 0
    repeated_payload = json.loads(repeated.output)
    assert repeated_payload == {"rows": 1, "imported": 0, "skipped": 1}

    invoice_rows = _invoke(["--format", "json", "app", "invoice", "review"])
    assert invoice_rows.exit_code == 0
    invoice_id = json.loads(invoice_rows.output)["rows"][0]["id"]

    review = _invoke(["--format", "json", "app", "invoice", "review", "--id", invoice_id])
    assert review.exit_code == 0
    review_payload = json.loads(review.output)
    assert review_payload["base"] == "100"
    assert review_payload["iva"] == "21"
    assert review_payload["payment"] is None

    edited = _invoke(
        [
            "--format",
            "json",
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
            "align invoice with collected payment",
        ]
    )
    assert edited.exit_code == 0
    edited_payload = json.loads(edited.output)
    assert edited_payload["review"]["fields"] == {
        "base": "120",
        "iva.rate": "21",
        "payment.id": payment_id,
    }

    matched = _invoke(["--format", "json", "app", "invoice", "match", "--period", "2026-Q1"])
    assert matched.exit_code == 0
    matched_payload = json.loads(matched.output)
    assert matched_payload["matched"] == [{"invoice": invoice_id, "payment": payment_id}]
    assert matched_payload["unmatched"] == []

    paid_rows = _invoke(["--format", "json", "app", "invoice", "review", "--filter", "status=paid"])
    assert paid_rows.exit_code == 0
    paid_payload = json.loads(paid_rows.output)
    assert paid_payload["rows"] == [
        {
            "id": invoice_id,
            "kind": "ISSUED",
            "base": "120",
            "iva": "25.2",
            "status": "paid",
            "payment": payment_id,
            "payment.id": payment_id,
        }
    ]


def test_app_declaration_status_filter_reports_match_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from aeat.application.workflow import update_declaration_pointer, workflow_state_repository

    _isolate(monkeypatch, tmp_path)
    workflow_state_repository().update(
        lambda current: update_declaration_pointer(
            current,
            modelo="303",
            period="2026Q1",
            draft_id="draft_303_2026Q1",
            status="READY_TO_SUBMIT",
        )
    )

    pending = _invoke(
        [
            "--format",
            "json",
            "app",
            "declaration",
            "status",
            "--period",
            "2026Q1",
            "--modelo",
            "303",
            "--filter",
            "status=pending",
        ]
    )
    approved = _invoke(
        [
            "--format",
            "json",
            "app",
            "declaration",
            "status",
            "--period",
            "2026Q1",
            "--modelo",
            "303",
            "--filter",
            "status=approved",
        ]
    )

    assert pending.exit_code == 0, pending.output
    assert approved.exit_code == 0, approved.output
    assert json.loads(pending.output)["matches_filter"] is True
    assert json.loads(approved.output)["matches_filter"] is False


def test_app_declaration_verify_rejects_missing_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _isolate(monkeypatch, tmp_path)
    result = _invoke(["app", "declaration", "verify", "--id", "fictional", "--file", str(tmp_path / "missing.bin")])
    assert result.exit_code != 0
