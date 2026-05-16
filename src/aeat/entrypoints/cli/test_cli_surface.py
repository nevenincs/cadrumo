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
from typing import cast

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


def _run_ledger_cli_json(args: list[str]) -> dict[str, object]:
    """Invoke the CLI with ``--format json`` prefixed, assert exit-0, return parsed JSON."""
    result = _invoke(["--format", "json", *args])
    assert result.exit_code == 0, result.output
    return cast(dict[str, object], json.loads(result.output))


def _ledger_add_manual_transaction() -> dict[str, object]:
    """Create the seed manual transaction the rest of the workflow operates on."""
    payload = _run_ledger_cli_json(
        [
            "app", "ledger", "add",
            "--date", "2026-05-02",
            "--amount", "-121.00",
            "--direction", "OUTGOING",
            "--description", "cash office supplies",
            "--counterparty", "Proveedor SL",
            "--classification", "BUSINESS",
            "--category-id", "office-supplies",
            "--taxable-base", "100.00",
            "--iva-rate", "0.21",
            "--iva-amount", "21.00",
            "--idempotency-key", "cash-office-2026-05-02",
        ]
    )
    assert payload["bucket_id"] == "operator"
    assert len(cast(str, payload["transaction_id"])) == 64
    transaction = cast(dict[str, object], payload["transaction"])
    assert transaction["business_classification"] == "BUSINESS"
    assert transaction["taxable_base"] == "100"
    assert transaction["iva_rate"] == "0.21"
    assert payload["bucket_event_ids"]
    return payload


def _ledger_list_and_view(transaction_id: str) -> None:
    """The list verb returns the seed row, the view verb returns its full record."""
    listed = _run_ledger_cli_json(["app", "ledger", "list"])
    assert listed["bucket_id"] == "operator"
    rows = cast(list[dict[str, object]], listed["rows"])
    assert [row["transaction_id"] for row in rows] == [transaction_id]
    assert rows[0]["review_status"] == "reviewed"

    read = _run_ledger_cli_json(["app", "ledger", "view", transaction_id])
    assert read["bucket_id"] == "operator"
    assert read["transaction_id"] == transaction_id
    assert read["review_status"] == "reviewed"
    transaction = cast(dict[str, object], read["transaction"])
    assert transaction["description"] == "cash office supplies"


def _ledger_update_transaction(transaction_id: str) -> dict[str, object]:
    """Update the seed transaction's amount + description; assert the diff."""
    edited = _run_ledger_cli_json(
        [
            "app", "ledger", "update",
            "--id", transaction_id,
            "--amount", "-121.50",
            "--direction", "OUTGOING",
            "--description", "cash office supplies corrected",
        ]
    )
    transaction = cast(dict[str, object], edited["transaction"])
    assert Decimal(cast(str, transaction["amount"])) == Decimal("-121.50")
    assert transaction["description"] == "cash office supplies corrected"
    assert edited["bucket_event_ids"]
    return edited


def _ledger_classify_transaction(transaction_id: str) -> dict[str, object]:
    """Re-classify the updated transaction; verify BUSINESS + new category id."""
    classified = _run_ledger_cli_json(
        [
            "app", "ledger", "classify",
            "--id", transaction_id,
            "--classification", "BUSINESS",
            "--category-id", "office-supplies-adjusted",
            "--taxable-base", "100.00",
            "--iva-rate", "0.21",
            "--iva-amount", "21.00",
        ]
    )
    transaction = cast(dict[str, object], classified["transaction"])
    assert transaction["business_classification"] == "BUSINESS"
    assert transaction["category_id"] == "office-supplies-adjusted"
    assert classified["review_status"] == "reviewed"
    return classified


def _seed_usage_ratio_for_telefonia(bucket_id: str) -> None:
    """Persist a usage-ratio profile so the next allocate verb can resolve TELEFONIA_MOVIL."""
    from aeat.domain.categories import SpendingCategory
    from aeat.domain.usage_ratios import UsageRatioProfile, save_usage_ratios

    save_usage_ratios(
        UsageRatioProfile(ratios={SpendingCategory.TELEFONIA_MOVIL: Decimal("0.60")}),
        bucket_id=bucket_id,
    )


def _ledger_allocate_transaction(transaction_id: str) -> dict[str, object]:
    """Allocate a usage ratio to the transaction; verify MIXED classification + pct."""
    allocated = _run_ledger_cli_json(
        [
            "app", "ledger", "allocate",
            "--id", transaction_id,
            "--business-pct", "0.60",
            "--category-id", "telefonia_movil",
            "--usage-ratio-id", "telefonia_movil",
        ]
    )
    transaction = cast(dict[str, object], allocated["transaction"])
    assert transaction["business_classification"] == "MIXED"
    assert Decimal(cast(str, transaction["business_pct"])) == Decimal("0.60")
    assert transaction["usage_ratio_id"] == "telefonia_movil"
    return allocated


def _assert_ledger_status_one_ready_row() -> None:
    """After one reviewed transaction the status verb reports a single ready row."""
    status = _run_ledger_cli_json(["app", "ledger", "status", "--period", "2026-05"])
    assert status["bucket_id"] == "operator"
    assert status["total_count"] == 1
    assert status["active_count"] == 1
    assert status["reviewed_count"] == 1
    assert status["pending_review_count"] == 0
    assert status["checked_transaction_count"] == 1
    assert status["readiness_issue_count"] == 0
    assert status["ready"] is True


def _assert_ledger_track_returns_lineage(
    transaction_id: str,
    *,
    expected_created_event_id: str,
) -> None:
    """The track verb returns the transaction body plus its lineage triple."""
    tracked = _run_ledger_cli_json(["app", "ledger", "track", transaction_id])
    assert tracked["bucket_id"] == "operator"
    transaction = cast(dict[str, object], tracked["transaction"])
    assert transaction["transaction_id"] == transaction_id
    tracking = cast(dict[str, object], tracked["tracking"])
    assert tracking["created_event_id"] == expected_created_event_id
    assert tracking["edit_lineage"]
    assert tracking["lifecycle_lineage"] == []


def _assert_ledger_review_returns_transaction(transaction_id: str) -> None:
    """The review verb returns the transaction by id with the post-update description."""
    reviewed = _run_ledger_cli_json(["app", "ledger", "review", "--id", transaction_id])
    assert reviewed["id"] == transaction_id
    assert reviewed["description"] == "cash office supplies corrected"
    assert reviewed["review_status"] == "reviewed"


def _assert_ledger_review_filtered_by_period_returns_empty(transaction_id: str) -> None:
    """Review with a period filter that doesn't match returns an empty rows list."""
    filtered_out = _run_ledger_cli_json(
        ["app", "ledger", "review", "--id", transaction_id, "--filter", "period=2026-06"]
    )
    assert filtered_out == {"rows": [], "filters": ["period=2026-06", f"id={transaction_id}"]}


def test_app_ledger_create_manual_transaction_persists_in_active_bucket(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """End-to-end ledger CLI flow: add → list/view → update → classify → allocate → status → track → review.

    Each step is a small helper that owns its CLI invocation, JSON
    parsing, and the assertions specific to that step. The test body
    reads as a linear narrative of the workflow with the
    transaction-id and intermediate payloads threaded through.
    """
    _isolate(monkeypatch, tmp_path)
    init = _invoke(
        ["config", "init", "--quiet", "--profile", "operator", "--tax-id", "12345678Z", "--activity", "Test"]
    )
    assert init.exit_code == 0, init.output

    created = _ledger_add_manual_transaction()
    transaction_id = cast(str, created["transaction_id"])
    created_event_id = cast(list[str], created["bucket_event_ids"])[0]

    _ledger_list_and_view(transaction_id)
    # Each downstream verb may rewrite the transaction id because the
    # ledger row is content-addressed (changing amount/category changes
    # the SHA). Re-thread the new id between steps so the verb chain
    # tracks the same logical row.
    edited = _ledger_update_transaction(transaction_id)
    transaction_id = cast(str, edited["transaction_id"])
    classified = _ledger_classify_transaction(transaction_id)
    transaction_id = cast(str, classified["transaction_id"])
    _seed_usage_ratio_for_telefonia(bucket_id="operator")
    allocated = _ledger_allocate_transaction(transaction_id)
    transaction_id = cast(str, allocated["transaction_id"])
    _assert_ledger_status_one_ready_row()
    _assert_ledger_track_returns_lineage(transaction_id, expected_created_event_id=created_event_id)
    _assert_ledger_review_returns_transaction(transaction_id)
    _assert_ledger_review_filtered_by_period_returns_empty(transaction_id)


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
