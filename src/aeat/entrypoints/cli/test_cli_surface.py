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
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from aeat.tests.cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


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
    return invoke_cached_cli(args)


def _create_manual_ledger_row(description: str, *, amount: str = "-25.00", key: str) -> dict[str, object]:
    result = _invoke(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "add",
            "--date",
            "2026-05-03",
            "--amount",
            amount,
            "--direction",
            "OUTGOING",
            "--description",
            description,
            "--idempotency-key",
            key,
        ]
    )
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


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
    for retired_command in ("aeat app invoice", "aeat app declaration", "aeat app archive"):
        assert retired_command not in result.output
    for plural_namespace in ("workspaces", "audits"):
        assert plural_namespace not in result.output


def test_top_level_auth_is_not_user_facing() -> None:
    result = _invoke(["auth", "--help"])
    assert result.exit_code != 0


def test_retired_invoice_declaration_and_archive_surfaces_are_not_user_facing() -> None:
    for command in (["app", "invoice"], ["app", "declaration"], ["app", "archive"]):
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


def test_app_ledger_create_manual_transaction_persists_in_active_bucket(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _isolate(monkeypatch, tmp_path)
    init = _invoke(
        ["config", "init", "--quiet", "--profile", "operator", "--tax-id", "12345678Z", "--activity", "Test"]
    )
    assert init.exit_code == 0, init.output

    created = _invoke(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "add",
            "--date",
            "2026-05-02",
            "--amount",
            "-121.00",
            "--direction",
            "OUTGOING",
            "--description",
            "cash office supplies",
            "--counterparty",
            "Proveedor SL",
            "--classification",
            "BUSINESS",
            "--category-id",
            "office-supplies",
            "--taxable-base",
            "100.00",
            "--iva-rate",
            "0.21",
            "--iva-amount",
            "21.00",
            "--idempotency-key",
            "cash-office-2026-05-02",
        ]
    )

    assert created.exit_code == 0, created.output
    payload = json.loads(created.output)
    assert payload["bucket_id"] == "operator"
    assert len(payload["transaction_id"]) == 64
    assert payload["transaction"]["business_classification"] == "BUSINESS"
    assert payload["transaction"]["taxable_base"] == "100"
    assert payload["transaction"]["iva_rate"] == "0.21"
    assert payload["bucket_event_ids"]

    listed = _invoke(["--format", "json", "app", "ledger", "list"])
    assert listed.exit_code == 0, listed.output
    listed_payload = json.loads(listed.output)
    assert listed_payload["bucket_id"] == "operator"
    assert [row["transaction_id"] for row in listed_payload["rows"]] == [payload["transaction_id"]]
    assert listed_payload["rows"][0]["review_status"] == "reviewed"

    read = _invoke(["--format", "json", "app", "ledger", "view", payload["transaction_id"]])
    assert read.exit_code == 0, read.output
    read_payload = json.loads(read.output)
    assert read_payload["bucket_id"] == "operator"
    assert read_payload["transaction_id"] == payload["transaction_id"]
    assert read_payload["review_status"] == "reviewed"
    assert read_payload["transaction"]["description"] == "cash office supplies"

    edited = _invoke(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "update",
            "--id",
            payload["transaction_id"],
            "--amount",
            "-121.50",
            "--direction",
            "OUTGOING",
            "--description",
            "cash office supplies corrected",
        ]
    )
    assert edited.exit_code == 0, edited.output
    edited_payload = json.loads(edited.output)
    assert Decimal(edited_payload["transaction"]["amount"]) == Decimal("-121.50")
    assert edited_payload["transaction"]["description"] == "cash office supplies corrected"
    assert edited_payload["bucket_event_ids"]

    classified = _invoke(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "classify",
            "--id",
            edited_payload["transaction_id"],
            "--classification",
            "BUSINESS",
            "--category-id",
            "office-supplies-adjusted",
            "--taxable-base",
            "100.00",
            "--iva-rate",
            "0.21",
            "--iva-amount",
            "21.00",
        ]
    )
    assert classified.exit_code == 0, classified.output
    classified_payload = json.loads(classified.output)
    assert classified_payload["transaction"]["business_classification"] == "BUSINESS"
    assert classified_payload["transaction"]["category_id"] == "office-supplies-adjusted"
    assert classified_payload["review_status"] == "reviewed"

    from aeat.domain.categories import SpendingCategory
    from aeat.domain.usage_ratios import UsageRatioProfile, save_usage_ratios

    save_usage_ratios(
        UsageRatioProfile(ratios={SpendingCategory.TELEFONIA_MOVIL: Decimal("0.60")}),
        bucket_id="operator",
    )
    allocated = _invoke(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "allocate",
            "--id",
            classified_payload["transaction_id"],
            "--business-pct",
            "0.60",
            "--category-id",
            "telefonia_movil",
            "--usage-ratio-id",
            "telefonia_movil",
        ]
    )
    assert allocated.exit_code == 0, allocated.output
    allocated_payload = json.loads(allocated.output)
    assert allocated_payload["transaction"]["business_classification"] == "MIXED"
    assert Decimal(allocated_payload["transaction"]["business_pct"]) == Decimal("0.60")
    assert allocated_payload["transaction"]["usage_ratio_id"] == "telefonia_movil"

    status = _invoke(["--format", "json", "app", "ledger", "status", "--period", "2026-05"])
    assert status.exit_code == 0, status.output
    status_payload = json.loads(status.output)
    assert status_payload["bucket_id"] == "operator"
    assert status_payload["total_count"] == 1
    assert status_payload["active_count"] == 1
    assert status_payload["reviewed_count"] == 1
    assert status_payload["pending_review_count"] == 0
    assert status_payload["checked_transaction_count"] == 1
    assert status_payload["readiness_issue_count"] == 0
    assert status_payload["ready"] is True

    tracked = _invoke(["--format", "json", "app", "ledger", "track", allocated_payload["transaction_id"]])
    assert tracked.exit_code == 0, tracked.output
    tracked_payload = json.loads(tracked.output)
    assert tracked_payload["bucket_id"] == "operator"
    assert tracked_payload["transaction"]["transaction_id"] == allocated_payload["transaction_id"]
    assert tracked_payload["tracking"]["created_event_id"] == payload["bucket_event_ids"][0]
    assert tracked_payload["tracking"]["edit_lineage"]
    assert tracked_payload["tracking"]["lifecycle_lineage"] == []

    reviewed = _invoke(["--format", "json", "app", "ledger", "review", "--id", allocated_payload["transaction_id"]])
    assert reviewed.exit_code == 0, reviewed.output
    reviewed_payload = json.loads(reviewed.output)
    assert reviewed_payload["id"] == allocated_payload["transaction_id"]
    assert reviewed_payload["description"] == "cash office supplies corrected"
    assert reviewed_payload["review_status"] == "reviewed"

    filtered_out = _invoke(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "review",
            "--id",
            allocated_payload["transaction_id"],
            "--filter",
            "period=2026-06",
        ]
    )
    assert filtered_out.exit_code == 0, filtered_out.output
    assert json.loads(filtered_out.output) == {
        "rows": [],
        "filters": ["period=2026-06", f"id={allocated_payload['transaction_id']}"],
    }


def test_app_ledger_lifecycle_attach_remove_reset_and_export_use_backend_bucket(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _isolate(monkeypatch, tmp_path)
    init = _invoke(
        ["config", "init", "--quiet", "--profile", "operator", "--tax-id", "12345678Z", "--activity", "Test"]
    )
    assert init.exit_code == 0, init.output

    from aeat.domain.invoices import (
        Invoice,
        InvoiceCatalogue,
        InvoiceCatalogueRepository,
        InvoiceKind,
        InvoiceLine,
        IvaRate,
        PaymentStatus,
    )

    purchase_line = InvoiceLine(
        description="Material oficina",
        quantity=Decimal("1"),
        unit_price=Decimal("100.00"),
        subtotal=Decimal("100.00"),
        iva_rate=IvaRate.RATE_21,
        iva_amount=Decimal("21.00"),
    )
    purchase_evidence = Invoice.model_validate(
        {
            "kind": InvoiceKind.RECEIVED,
            "bucket_id": "operator",
            "invoice_number": "P-2026-CLI-001",
            "issued_at": date(2026, 5, 3),
            "counterparty_name": "Proveedor SL",
            "counterparty_tax_id": "B12345674",
            "counterparty_country": "ES",
            "base_total": Decimal("100.00"),
            "iva_total": Decimal("21.00"),
            "grand_total": Decimal("121.00"),
            "currency": "EUR",
            "lines": (purchase_line,),
            "payment_status": PaymentStatus.PAID,
        }
    )
    InvoiceCatalogueRepository().save(InvoiceCatalogue.from_invoices((purchase_evidence,)))

    attach_row = _create_manual_ledger_row("attach evidence row", amount="-121.00", key="cli-attach-row")
    attached = _invoke(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "attach",
            "--id",
            str(attach_row["transaction_id"]),
            "--purchase-invoice-evidence-id",
            purchase_evidence.invoice_id,
        ]
    )
    assert attached.exit_code == 0, attached.output
    attached_payload = json.loads(attached.output)
    assert attached_payload["transaction"]["purchase_invoice_evidence_id"] == purchase_evidence.invoice_id
    assert attached_payload["bucket_event_ids"]

    archive_row = _create_manual_ledger_row("archive row", key="cli-archive-row")
    archived = _invoke(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "archive",
            "--id",
            str(archive_row["transaction_id"]),
            "--reason",
            "wrong account",
            "--yes",
        ]
    )
    assert archived.exit_code == 0, archived.output
    assert json.loads(archived.output)["transaction"]["lifecycle_state"] == "ARCHIVED"

    stash_row = _create_manual_ledger_row("stash row", key="cli-stash-row")
    stashed = _invoke(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "stash",
            "--id",
            str(stash_row["transaction_id"]),
            "--reason",
            "needs review",
            "--yes",
        ]
    )
    assert stashed.exit_code == 0, stashed.output
    assert json.loads(stashed.output)["transaction"]["lifecycle_state"] == "STASHED"

    remove_row = _create_manual_ledger_row("remove row", key="cli-remove-row")
    dry_remove = _invoke(
        ["--format", "json", "app", "ledger", "remove", "--id", str(remove_row["transaction_id"]), "--dry-run"]
    )
    assert dry_remove.exit_code == 0, dry_remove.output
    assert json.loads(dry_remove.output)["dry_run"] is True
    refused_remove = _invoke(["--format", "json", "app", "ledger", "remove", "--id", str(remove_row["transaction_id"])])
    assert refused_remove.exit_code != 0
    removed = _invoke(
        ["--format", "json", "app", "ledger", "remove", "--id", str(remove_row["transaction_id"]), "--yes"]
    )
    assert removed.exit_code == 0, removed.output
    assert json.loads(removed.output)["removed"] is True

    export_path = tmp_path / "ledger-export.jsonl"
    exported = _invoke(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "export",
            "--output",
            str(export_path),
            "--export-format",
            "jsonl",
            "--include-inactive",
        ]
    )
    assert exported.exit_code == 0, exported.output
    export_payload = json.loads(exported.output)
    assert export_payload["bucket_id"] == "operator"
    assert export_payload["row_count"] == 3
    assert export_path.read_text(encoding="utf-8").count("\n") == 3

    dry_reset = _invoke(["--format", "json", "app", "ledger", "reset", "--dry-run"])
    assert dry_reset.exit_code == 0, dry_reset.output
    assert json.loads(dry_reset.output)["dry_run"] is True
    refused_reset = _invoke(["--format", "json", "app", "ledger", "reset", "--reason", "test cleanup"])
    assert refused_reset.exit_code != 0
    reset = _invoke(["--format", "json", "app", "ledger", "reset", "--reason", "test cleanup", "--yes"])
    assert reset.exit_code == 0, reset.output
    reset_payload = json.loads(reset.output)
    assert reset_payload["reset"] is True
    assert len(reset_payload["removed_transaction_ids"]) == 3


def test_app_ledger_import_reimport_review_round_trips_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _isolate(monkeypatch, tmp_path)
    init = _invoke(["config", "init", "--quiet", "--tax-id", "12345678Z", "--activity", "Test"])
    assert init.exit_code == 0
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

    reviewed = _invoke(["--format", "json", "app", "ledger", "review", "--id", vendor_id])
    assert reviewed.exit_code == 0, reviewed.output
    reviewed_payload = json.loads(reviewed.output)
    assert reviewed_payload["id"] == vendor_id
    assert reviewed_payload["description"] == "Subscription"


def test_app_ledger_review_filter_rejects_unknown_key(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _isolate(monkeypatch, tmp_path)
    result = _invoke(["app", "ledger", "review", "--filter", "kind=received"])
    assert result.exit_code != 0


def test_legacy_ledger_ratio_aliases_are_not_registered(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _isolate(monkeypatch, tmp_path)
    # `split` was the deleted single-row allocation knob (see
    # 2026-05-14 ledger-transaction-lifecycle ADR); the new `split` verb
    # is the true N-way row splitter and is intentionally registered.
    # Only legacy ratio aliases must remain refused.
    for command in ("set-ratio",):
        result = _invoke(["app", "ledger", command, "--help"])
        assert result.exit_code != 0
