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


# ---------------------------------------------------------------------
# Namespace surface
# ---------------------------------------------------------------------


def test_root_help_lists_config_and_app() -> None:
    result = _invoke(["--help"])
    assert result.exit_code == 0
    assert "config" in result.output
    assert "app" in result.output


def test_app_help_lists_singular_domains() -> None:
    result = _invoke(["app", "--help"])
    assert result.exit_code == 0
    for token in ("overview", "ledger", "live", "modelo", "registry", "review"):
        assert token in result.output
    for retired_command in ("aeat app invoice", "aeat app declaration", "aeat app archive", "aeat app topic"):
        assert retired_command not in result.output
    for plural_namespace in ("workspaces", "audits"):
        assert plural_namespace not in result.output


def test_top_level_auth_is_not_user_facing() -> None:
    result = _invoke(["auth", "--help"])
    assert result.exit_code != 0


def test_retired_invoice_declaration_and_topic_surfaces_are_not_user_facing() -> None:
    for command in (["app", "invoice"], ["app", "declaration"], ["app", "topic"], ["app", "archive"]):
        result = _invoke([*command, "--help"])
        assert result.exit_code != 0, command


# ---------------------------------------------------------------------
# App namespace — overview / ledger
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
