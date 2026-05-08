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

import hashlib
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aeat.application.auth import AuthProviderKind, acquire_auth_acquisition_lock
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


def test_root_help_lists_only_setup_and_app() -> None:
    result = _invoke(["--help"])
    assert result.exit_code == 0
    assert "setup" in result.output
    assert "app" in result.output
    assert "auth" not in result.output


def test_setup_help_lists_init_status_auth_profile() -> None:
    result = _invoke(["setup", "--help"])
    assert result.exit_code == 0
    for token in ("init", "status", "auth", "profile"):
        assert token in result.output


def test_app_help_lists_singular_domains() -> None:
    result = _invoke(["app", "--help"])
    assert result.exit_code == 0
    for token in ("overview", "ledger", "invoice", "declaration"):
        assert token in result.output
    for plural_namespace in ("workspaces", "audits", "declarations"):
        assert plural_namespace not in result.output


def test_setup_profile_help_carries_subcommands() -> None:
    result = _invoke(["setup", "profile", "--help"])
    assert result.exit_code == 0
    for token in ("use", "show", "list-keys", "get", "set", "unset", "validate", "list"):
        assert token in result.output


def test_setup_auth_help_carries_subcommands() -> None:
    result = _invoke(["setup", "auth", "--help"])
    assert result.exit_code == 0
    for token in ("providers", "configure", "login", "status", "reset", "whoami", "logout"):
        assert token in result.output


def test_setup_auth_login_help_carries_manual_recovery_flags() -> None:
    result = _invoke(["setup", "auth", "login", "--help"])
    assert result.exit_code == 0
    assert "--fresh" in result.output
    assert "--reset-lock" in result.output


def test_top_level_auth_is_not_user_facing() -> None:
    result = _invoke(["auth", "--help"])
    assert result.exit_code != 0


def test_app_declaration_help_carries_subcommands() -> None:
    result = _invoke(["app", "declaration", "--help"])
    assert result.exit_code == 0
    for token in ("calculate", "review", "status", "edit", "approve", "validate", "preview", "export", "verify"):
        assert token in result.output


# ---------------------------------------------------------------------
# Setup namespace
# ---------------------------------------------------------------------


def test_setup_status_returns_typed_payload(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    result = _invoke(["--format", "json", "setup", "status"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["active_profile"] is None
    assert payload["profile_ready"] is False
    assert payload["next_action"].startswith("aeat setup ")


def test_setup_init_seeds_profile_and_activates(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    result = _invoke(
        [
            "--format",
            "json",
            "setup",
            "init",
            "--name",
            "operator",
            "--tax-id",
            "12345678Z",
            "--activity",
            "design",
        ]
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["active_profile"] == "operator"
    assert payload["values"]["tax.id"] == "12345678Z"


def test_setup_profile_validate_routes_through_application_api(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _isolate(monkeypatch, tmp_path)
    init = _invoke(["setup", "init", "--name", "operator", "--tax-id", "12345678Z", "--activity", "design"])
    assert init.exit_code == 0
    result = _invoke(["--format", "json", "setup", "profile", "validate"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["valid"] is True
    assert "tax.id" in payload["present_required"]


def test_setup_profile_validate_blocks_when_required_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _isolate(monkeypatch, tmp_path)
    assert _invoke(["setup", "init", "--name", "operator"]).exit_code == 0
    result = _invoke(["--format", "json", "setup", "profile", "validate"])
    assert result.exit_code == 2


def test_setup_profile_list_keys_renders_registry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    result = _invoke(["--format", "json", "setup", "profile", "list-keys"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    keys = {entry["key"] for entry in payload["keys"]}
    assert "tax.id" in keys
    assert "activity" in keys


def test_setup_profile_set_get_unset_round_trip(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    assert _invoke(["setup", "init", "--name", "operator"]).exit_code == 0
    set_result = _invoke(["--format", "json", "setup", "profile", "set", "tax.id", "X1234567L"])
    assert set_result.exit_code == 0
    get_result = _invoke(["--format", "json", "setup", "profile", "get", "tax.id"])
    assert get_result.exit_code == 0
    assert json.loads(get_result.output)["value"] == "X1234567L"
    assert _invoke(["setup", "profile", "unset", "tax.id"]).exit_code == 0


def test_setup_profile_get_rejects_unknown_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    assert _invoke(["setup", "init", "--name", "operator"]).exit_code == 0
    result = _invoke(["setup", "profile", "get", "fictional.key"])
    assert result.exit_code != 0


def test_setup_profile_list_renders_active_marker(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    assert _invoke(["setup", "init", "--name", "operator"]).exit_code == 0
    result = _invoke(["--format", "json", "setup", "profile", "list"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    # Field is named `active` (the active profile name) plus `profiles` (the list).
    active = payload.get("active") or payload.get("active_profile")
    assert active == "operator"
    assert "operator" in payload["profiles"]


# ---------------------------------------------------------------------
# Auth namespace
# ---------------------------------------------------------------------


def test_setup_auth_providers_renders_catalogue(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)
    result = _invoke(["--format", "json", "setup", "auth", "providers"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    ids = {row["id"] for row in payload["providers"]}
    assert ids == {"certificate", "clave_movil"}
    assert all("availability" not in row for row in payload["providers"])


def test_setup_auth_configure_rejects_unsupported_provider(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)

    result = _invoke(["setup", "auth", "configure", "--provider", "clave_permanente"])
    assert result.exit_code == 2


def test_setup_auth_configure_certificate_requires_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _isolate(monkeypatch, tmp_path)
    result = _invoke(["setup", "auth", "configure", "--provider", "certificate"])
    assert result.exit_code != 0


def test_setup_auth_configure_clave_movil_round_trips(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _isolate(monkeypatch, tmp_path)

    assert _invoke(["setup", "init", "--name", "operator", "--tax-id", "12345678Z"]).exit_code == 0
    configure = _invoke(["--format", "json", "setup", "auth", "configure", "--provider", "clave_movil"])
    assert configure.exit_code == 0
    status = _invoke(["--format", "json", "setup", "auth", "status"])
    assert status.exit_code == 0
    payload = json.loads(status.output)
    assert payload["auth"]["provider"] == "clave_movil"
    assert payload["ready"] is False
    assert payload["acquisition_lock"]["state"] == "absent"
    assert _invoke(["setup", "auth", "logout"]).exit_code == 0


def test_setup_auth_status_reports_live_acquisition_lock(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _isolate(monkeypatch, tmp_path)

    assert _invoke(["setup", "init", "--name", "operator", "--tax-id", "12345678Z"]).exit_code == 0
    assert _invoke(["setup", "auth", "configure", "--provider", "clave_movil"]).exit_code == 0

    from aeat.core.config import Settings

    settings = Settings().model_copy(
        update={
            "aeat_token_dir": tmp_path / "tokens",
            "aeat_default_profile_name": "default",
            "aeat_clave_movil_dni_nie": "12345678Z",
        }
    )
    with acquire_auth_acquisition_lock(
        settings,
        AuthProviderKind.CLAVE_MOVIL,
        ttl_seconds=300,
        operation="test-auth-login",
    ):
        status = _invoke(["--format", "json", "setup", "auth", "status"])

    assert status.exit_code == 0, status.output
    payload = json.loads(status.output)
    assert payload["ready"] is False
    assert payload["acquisition_lock"]["state"] == "held"
    assert payload["acquisition_lock"]["record"]["operation"] == "test-auth-login"


def test_setup_auth_reset_requires_explicit_scope(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _isolate(monkeypatch, tmp_path)

    assert _invoke(["setup", "init", "--name", "operator", "--tax-id", "12345678Z"]).exit_code == 0
    assert _invoke(["setup", "auth", "configure", "--provider", "clave_movil"]).exit_code == 0

    reset = _invoke(["setup", "auth", "reset"])

    assert reset.exit_code == 2


def test_setup_auth_reset_locks_removes_manual_acquisition_lock(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _isolate(monkeypatch, tmp_path)

    assert _invoke(["setup", "init", "--name", "operator", "--tax-id", "12345678Z"]).exit_code == 0
    assert _invoke(["setup", "auth", "configure", "--provider", "clave_movil"]).exit_code == 0

    from aeat.core.config import Settings

    settings = Settings().model_copy(
        update={
            "aeat_token_dir": tmp_path / "tokens",
            "aeat_default_profile_name": "default",
            "aeat_clave_movil_dni_nie": "12345678Z",
        }
    )
    with acquire_auth_acquisition_lock(
        settings,
        AuthProviderKind.CLAVE_MOVIL,
        ttl_seconds=300,
        operation="test-auth-login",
    ):
        reset = _invoke(["--format", "json", "setup", "auth", "reset", "--locks"])

    assert reset.exit_code == 0, reset.output
    payload = json.loads(reset.output)
    assert payload["reset_lock"]["state"] == "held"
    assert payload["reset_lock"]["reason"] == "operator-reset-command"
    assert payload["removed_sessions"] == []


def test_setup_auth_clave_movil_status_and_logout_do_not_mark_login_without_verified_session(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Cl@ve Móvil status/logout do not create local readiness without a verified backend session."""
    _isolate(monkeypatch, tmp_path)

    init = _invoke(["setup", "init", "--name", "operator"])
    assert init.exit_code == 0, init.output

    configure = _invoke(["--format", "json", "setup", "auth", "configure", "--provider", "clave_movil"])
    assert configure.exit_code == 0, configure.output
    configured = json.loads(configure.output)
    assert configured["auth"]["provider"] == "clave_movil"
    assert configured["auth"]["certificate_path"] is None
    assert configured["next"] == "aeat setup auth login"

    status = _invoke(["--format", "json", "setup", "auth", "status"])
    assert status.exit_code == 0, status.output
    ready = json.loads(status.output)
    assert ready["ready"] is False
    assert ready["auth"]["provider"] == "clave_movil"

    logout = _invoke(["--format", "json", "setup", "auth", "logout"])
    assert logout.exit_code == 0, logout.output
    logged_out = json.loads(logout.output)
    assert logged_out["auth"]["provider"] == "clave_movil"
    assert logged_out["auth"]["authenticated_at"] is None
    assert logged_out["auth"]["subject"] is None


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


def test_app_declaration_calculate_review_approve_export_verify_round_trips(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _isolate(monkeypatch, tmp_path)
    assert (
        _invoke(["setup", "init", "--name", "operator", "--tax-id", "12345678Z", "--activity", "design"]).exit_code == 0
    )
    assert _invoke(["setup", "profile", "set", "declaration.type", "I"]).exit_code == 0
    assert _invoke(["setup", "profile", "set", "surnames", "EXPORT TEST"]).exit_code == 0
    assert _invoke(["setup", "profile", "set", "name", "ANA"]).exit_code == 0
    modelo = _registry_modelo_calculable_without_cli_sources()
    result = _invoke(["--format", "json", "app", "declaration", "calculate", "--period", "2026Q1", "--modelo", modelo])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["draft"]["modelo"] == modelo
    assert payload["draft"]["period"] == "2026Q1"
    draft_id = payload["draft"]["draft_id"]
    assert payload["summary"]["next_action"] in {
        "review",
        "approve",
        "export",
        "refresh-approval",
        "amend",
        "resolve-blockers",
    }

    review_by_id = _invoke(["--format", "json", "app", "declaration", "review", "--id", draft_id])
    assert review_by_id.exit_code == 0
    review_by_id_payload = json.loads(review_by_id.output)
    assert review_by_id_payload["draft"]["draft_id"] == draft_id
    assert review_by_id_payload["values"]

    review_by_period = _invoke(
        [
            "--format",
            "json",
            "app",
            "declaration",
            "review",
            "--modelo",
            modelo,
            "--period",
            "2026Q1",
        ]
    )
    assert review_by_period.exit_code == 0
    review_by_period_payload = json.loads(review_by_period.output)
    assert review_by_period_payload["draft"]["draft_id"] == draft_id
    assert review_by_period_payload["values"] == review_by_id_payload["values"]

    approved = _invoke(
        [
            "--format",
            "json",
            "app",
            "declaration",
            "approve",
            "--id",
            draft_id,
            "--by",
            "qa",
            "--reason",
            "roundtrip export verification",
        ]
    )
    assert approved.exit_code == 0
    approved_payload = json.loads(approved.output)
    assert approved_payload["draft_id"] == draft_id
    assert approved_payload["status"] == "APPROVED"

    first_output = tmp_path / "first-export.txt"
    first_export = _invoke(
        ["--format", "json", "app", "declaration", "export", "--id", draft_id, "--output", str(first_output)]
    )
    assert first_export.exit_code == 0
    first_payload = json.loads(first_export.output)
    first_bytes = first_output.read_bytes()
    assert first_payload["receipt"]["draft_id"] == draft_id
    assert first_payload["receipt"]["byte_size"] == len(first_bytes)
    assert first_payload["receipt"]["file_sha256"] == hashlib.sha256(first_bytes).hexdigest()

    second_output = tmp_path / "second-export.txt"
    second_export = _invoke(
        ["--format", "json", "app", "declaration", "export", "--id", draft_id, "--output", str(second_output)]
    )
    assert second_export.exit_code == 0
    assert second_output.read_bytes() == first_bytes

    first_verify = _invoke(
        ["--format", "json", "app", "declaration", "verify", "--id", draft_id, "--file", str(first_output)]
    )
    assert first_verify.exit_code == 0
    first_verify_payload = json.loads(first_verify.output)
    assert first_verify_payload["verdict"]["verdict"] == "match"
    assert first_verify_payload["verdict"]["mismatched_casillas"] == []

    second_verify = _invoke(
        ["--format", "json", "app", "declaration", "verify", "--id", draft_id, "--file", str(second_output)]
    )
    assert second_verify.exit_code == 0
    second_verify_payload = json.loads(second_verify.output)
    assert second_verify_payload["verdict"]["verdict"] == "match"
    assert second_verify_payload["verdict"]["mismatched_casillas"] == []
    assert second_verify_payload["verdict"]["file_sha256"] == first_verify_payload["verdict"]["file_sha256"]


def test_app_declaration_status_filter_reports_match_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from aeat.application.user_cli import state_repository, update_declaration_pointer

    _isolate(monkeypatch, tmp_path)
    state_repository().update(
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


def test_app_declaration_calculate_requires_profile_tax_id(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _isolate(monkeypatch, tmp_path)
    assert _invoke(["setup", "init", "--name", "operator", "--activity", "design"]).exit_code == 0
    modelo = _registry_modelo_calculable_without_cli_sources()
    result = _invoke(["app", "declaration", "calculate", "--period", "2026Q1", "--modelo", modelo])
    assert result.exit_code == 2
    assert "tax.id" in result.output


def test_app_declaration_calculate_refuses_missing_registry_inputs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _isolate(monkeypatch, tmp_path)
    assert (
        _invoke(["setup", "init", "--name", "operator", "--tax-id", "12345678Z", "--activity", "design"]).exit_code == 0
    )
    modelo = _registry_modelo_requiring_cli_sources()
    result = _invoke(["app", "declaration", "calculate", "--period", "2026Q1", "--modelo", modelo])
    assert result.exit_code == 2
    assert "registry calculation failed" in result.output


def test_app_declaration_verify_rejects_missing_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _isolate(monkeypatch, tmp_path)
    result = _invoke(["app", "declaration", "verify", "--id", "fictional", "--file", str(tmp_path / "missing.bin")])
    assert result.exit_code != 0
