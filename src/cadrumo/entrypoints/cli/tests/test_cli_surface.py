"""Integration tests for the user-facing ``cadrumo`` CLI.

These tests assert that every command namespace exists, that the thin
transport handlers route into the application layer, and that the
JSON envelope matches the typed records the backend exposes. They
do NOT exercise live AEAT, certificate auth, or any network surface.

Each test isolates storage state through ``isolated_profile_storage_root``
which provisions a real file-backend storage root per test without a
pre-existing active profile.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import pytest

from ....core.config import override_settings
from ....core.redaction.rules import CLI_BUCKET_ID_PLACEHOLDER, CLI_PROFILE_ID_PLACEHOLDER
from ....tests.cli_runner import invoke_cached_cli
from ._cli_json_support import _json_object
from ._cli_surface_support import (
    _active_bucket_id,
    _invoke,
    _json,
    create_cli_surface_profile,
)
from ._strict_cli_fixture_support import cli_surface_isolated_backend

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

__all__ = ["cli_surface_isolated_backend"]


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


def test_app_overview_status_bare_renders_counts() -> None:
    result = _invoke(["--format", "json", "app", "overview", "status"])
    assert result.exit_code == 0
    payload = _json(result)
    assert payload["transactions"] == 0
    assert payload["invoices"] == 0
    assert payload["drafts"] == 0


def test_app_ledger_import_dry_run_does_not_persist(tmp_path: Path) -> None:
    create_cli_surface_profile()
    statement = tmp_path / "n26.csv"
    statement.write_text(
        "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID\n"
        "2026-04-15,Client SL,Invoice 1,121.00,EUR,n26-001\n",
        encoding="utf-8",
    )
    dry = _invoke(
        ["--format", "json", "app", "ledger", "import", "--file", str(statement), "--provider", "csv", "--dry-run"]
    )
    assert dry.exit_code == 0
    result = _json(dry)
    assert result["dry_run"] is True
    # The dry run previews what a real import would add - one row here -
    # but persists nothing: the overview still reports zero transactions.
    assert result["imported"] == 1
    after = _invoke(["--format", "json", "app", "overview", "status"])
    assert _json(after)["transactions"] == 0


def _run_ledger_cli_json(args: list[str]) -> dict[str, Any]:
    """Invoke the CLI with ``--format json`` prefixed, assert exit-0, return parsed JSON."""
    result = _invoke(["--format", "json", *args])
    assert result.exit_code == 0, result.output
    return _json(result)


def _ledger_add_manual_transaction(bucket_id: str) -> dict[str, Any]:
    """Create the seed manual transaction the rest of the workflow operates on."""
    payload = _run_ledger_cli_json(
        [
            "app",
            "ledger",
            "add",
            "--date",
            "2026-05-02",
            "--amount",
            "121.00",
            "--direction",
            "OUTGOING",
            "--description",
            "cash office supplies",
            "--counterparty",
            "Proveedor SL",
            "--classification",
            "BUSINESS",
            "--category-id",
            "material_oficina",
            "--taxable-base",
            "100.00",
            "--iva-rate",
            "0.21",
            "--iva-amount",
            "21.00",
            "--idempotency-key",
            "cash-office-2026-05-02",
        ],
    )
    assert bucket_id not in json.dumps(payload, sort_keys=True)
    assert payload["bucket_id"] == CLI_BUCKET_ID_PLACEHOLDER
    assert len(cast(str, payload["transaction_id"])) == 64
    transaction = cast(dict[str, object], payload["transaction"])
    assert transaction["business_classification"] == "BUSINESS"
    assert transaction["taxable_base"] == "100"
    assert transaction["iva_rate"] == "0.21"
    assert payload["bucket_event_ids"]
    return payload


def _ledger_list_and_view(transaction_id: str, *, bucket_id: str) -> None:
    """The list verb returns the seed row, the view verb returns its full record."""
    listed = _run_ledger_cli_json(["app", "ledger", "list"])
    assert bucket_id not in json.dumps(listed, sort_keys=True)
    assert listed["bucket_id"] == CLI_BUCKET_ID_PLACEHOLDER
    rows = cast(list[dict[str, object]], listed["rows"])
    assert [row["transaction_id"] for row in rows] == [transaction_id]
    assert rows[0]["review_status"] == "reviewed"

    read = _run_ledger_cli_json(["app", "ledger", "view", transaction_id])
    assert bucket_id not in json.dumps(read, sort_keys=True)
    assert read["bucket_id"] == CLI_BUCKET_ID_PLACEHOLDER
    assert read["transaction_id"] == transaction_id
    assert read["review_status"] == "reviewed"
    transaction = cast(dict[str, object], read["transaction"])
    assert transaction["description"] == "cash office supplies"


def _ledger_update_transaction(transaction_id: str) -> dict[str, object]:
    """Update the seed transaction's amount + description; assert the diff."""
    edited = _run_ledger_cli_json(
        [
            "app",
            "ledger",
            "update",
            transaction_id,
            "--amount",
            "121.50",
            "--taxable-base",
            "100.41",
            "--iva-amount",
            "21.09",
            "--direction",
            "OUTGOING",
            "--description",
            "cash office supplies corrected",
        ],
    )
    transaction = cast(dict[str, object], edited["transaction"])
    assert Decimal(cast(str, transaction["amount"])) == Decimal("121.50")
    assert transaction["description"] == "cash office supplies corrected"
    assert edited["bucket_event_ids"]
    return _json_object(edited)


def _ledger_classify_transaction(transaction_id: str) -> dict[str, object]:
    """Re-classify the updated transaction; verify BUSINESS + new category id."""
    classified = _run_ledger_cli_json(
        [
            "app",
            "ledger",
            "classify",
            transaction_id,
            "--classification",
            "BUSINESS",
            "--category-id",
            "software_suscripcion",
            "--taxable-base",
            "100.41",
            "--iva-rate",
            "0.21",
            "--iva-amount",
            "21.09",
        ],
    )
    transaction = cast(dict[str, object], classified["transaction"])
    assert transaction["business_classification"] == "BUSINESS"
    assert transaction["category_id"] == "software_suscripcion"
    assert classified["review_status"] == "reviewed"
    return _json_object(classified)


def _seed_usage_ratio_for_telefonia(bucket_id: str) -> None:
    """Persist a usage-ratio profile so the next allocate verb can resolve TELEFONIA_MOVIL."""
    from ....adapters.persistence.profile.usage_ratios import save_usage_ratios
    from ....domain.categories.spending_category import SpendingCategory
    from ....domain.usage_ratios.model import UsageRatioProfile

    save_usage_ratios(
        UsageRatioProfile(ratios={SpendingCategory.TELEFONIA_MOVIL: Decimal("0.60")}),
        bucket_id=bucket_id,
    )


def _ledger_allocate_transaction(transaction_id: str) -> dict[str, object]:
    """Allocate a usage ratio to the transaction; verify MIXED classification + pct."""
    allocated = _run_ledger_cli_json(
        [
            "app",
            "ledger",
            "allocate",
            transaction_id,
            "--business-pct",
            "0.60",
            "--category-id",
            "telefonia_movil",
            "--usage-ratio-id",
            "telefonia_movil",
        ],
    )
    transaction = cast(dict[str, object], allocated["transaction"])
    assert transaction["business_classification"] == "MIXED"
    assert Decimal(cast(str, transaction["business_pct"])) == Decimal("0.60")
    assert transaction["usage_ratio_id"] == "telefonia_movil"
    return _json_object(allocated)


def _assert_ledger_status_one_ready_row(bucket_id: str) -> None:
    """After one reviewed transaction the status verb reports a single ready row."""
    status = _run_ledger_cli_json(["app", "ledger", "status", "--period", "05", "--year", "2026"])
    assert bucket_id not in json.dumps(status, sort_keys=True)
    assert status["bucket_id"] == CLI_BUCKET_ID_PLACEHOLDER
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
    bucket_id: str,
) -> None:
    """The track verb returns the transaction body plus its lineage triple."""
    tracked = _run_ledger_cli_json(["app", "ledger", "track", transaction_id])
    assert bucket_id not in json.dumps(tracked, sort_keys=True)
    assert tracked["bucket_id"] == CLI_BUCKET_ID_PLACEHOLDER
    transaction = cast(dict[str, object], tracked["transaction"])
    assert transaction["transaction_id"] == transaction_id
    tracking = cast(dict[str, object], tracked["tracking"])
    assert tracking["created_event_id"] == expected_created_event_id
    assert tracking["edit_lineage"]
    assert tracking["lifecycle_lineage"] == []


def _assert_ledger_review_returns_transaction(transaction_id: str) -> None:
    """The review verb returns the transaction by id with the post-update description."""
    reviewed = _run_ledger_cli_json(["app", "ledger", "review", transaction_id])
    assert reviewed["id"] == transaction_id
    assert reviewed["description"] == "cash office supplies corrected"
    assert reviewed["review_status"] == "reviewed"


def _assert_ledger_review_filtered_by_period_returns_empty(transaction_id: str) -> None:
    """Review with a period filter that doesn't match returns an empty rows list."""
    filtered_out = _run_ledger_cli_json(
        ["app", "ledger", "review", transaction_id, "--filter", "period=06", "--filter", "year=2026"],
    )
    assert filtered_out["rows"] == []
    assert filtered_out["filters"] == ["period=2026 06", f"id={transaction_id}"]


def test_app_ledger_create_manual_transaction_persists_in_active_bucket() -> None:
    """End-to-end ledger CLI flow: add → list/view → update → classify → allocate → status → track → review.

    Each step is a small helper that owns its CLI invocation, JSON
    parsing, and the assertions specific to that step. The test body
    reads as a linear narrative of the workflow with the
    transaction-id and intermediate payloads threaded through.
    """
    create_cli_surface_profile()
    bucket_id = _active_bucket_id()

    created = _ledger_add_manual_transaction(bucket_id)
    transaction_id = cast(str, created["transaction_id"])
    created_event_id = cast(list[str], created["bucket_event_ids"])[0]

    _ledger_list_and_view(transaction_id, bucket_id=bucket_id)
    # Each downstream verb may rewrite the transaction id because the
    # ledger row is content-addressed (changing amount/category changes
    # the SHA). Re-thread the new id between steps so the verb chain
    # tracks the same logical row.
    edited = _ledger_update_transaction(transaction_id)
    transaction_id = cast(str, edited["transaction_id"])
    classified = _ledger_classify_transaction(transaction_id)
    transaction_id = cast(str, classified["transaction_id"])
    _seed_usage_ratio_for_telefonia(bucket_id=bucket_id)
    allocated = _ledger_allocate_transaction(transaction_id)
    transaction_id = cast(str, allocated["transaction_id"])
    _assert_ledger_status_one_ready_row(bucket_id)
    _assert_ledger_track_returns_lineage(
        transaction_id,
        expected_created_event_id=created_event_id,
        bucket_id=bucket_id,
    )
    _assert_ledger_review_returns_transaction(transaction_id)
    _assert_ledger_review_filtered_by_period_returns_empty(transaction_id)


def test_app_ledger_list_reveal_identifiers_opt_in_surfaces_real_bucket_id() -> None:
    """Default ledger list JSON redacts ``bucket_id``; the reveal opt-out shows the real UUID.

    Multi-client gestors must be able to disambiguate which bucket a command
    addressed. The ``CADRUMO_CLI_REVEAL_IDENTIFIERS`` opt-out un-redacts the
    profile/bucket identifier surfaces while the paste-safe placeholder stays
    the default.
    """
    create_cli_surface_profile()
    bucket_id = _active_bucket_id()
    _ledger_add_manual_transaction(bucket_id)

    default_listed = _run_ledger_cli_json(["app", "ledger", "list"])
    assert default_listed["bucket_id"] == CLI_BUCKET_ID_PLACEHOLDER
    assert bucket_id not in json.dumps(default_listed, sort_keys=True)

    with override_settings(cadrumo_cli_reveal_identifiers=True):
        revealed = invoke_cached_cli(["--format", "json", "app", "ledger", "list"])
    assert revealed.exit_code == 0, revealed.output
    revealed_payload = _json(revealed)
    assert revealed_payload["bucket_id"] == bucket_id
    assert revealed_payload["bucket_id"] != CLI_BUCKET_ID_PLACEHOLDER


def test_config_profile_view_reveal_identifiers_opt_in_surfaces_real_profile_id() -> None:
    """Default ``config profile view`` JSON redacts ``profile_id``; the opt-out reveals it.

    ``config profile view`` is the profile inspection surface. The
    centralised-output-redaction policy rewrites the ``profile_id`` field to the
    paste-safe ``<profile-id>`` placeholder by default; the
    ``CADRUMO_CLI_REVEAL_IDENTIFIERS`` opt-out un-redacts the opaque profile UUID so
    a multi-client gestor's automation can key on the addressed profile.
    """
    create_cli_surface_profile()
    profile_id = _active_bucket_id()

    default_shown = _run_ledger_cli_json(["config", "profile", "view"])
    assert default_shown["profile_id"] == CLI_PROFILE_ID_PLACEHOLDER
    assert profile_id not in json.dumps(default_shown, sort_keys=True)

    with override_settings(cadrumo_cli_reveal_identifiers=True):
        revealed = invoke_cached_cli(["--format", "json", "config", "profile", "view"])
    assert revealed.exit_code == 0, revealed.output
    revealed_payload = _json(revealed)
    assert revealed_payload["profile_id"] == profile_id
    assert revealed_payload["profile_id"] != CLI_PROFILE_ID_PLACEHOLDER


def test_app_modelo_filing_record_list_text_header_is_well_formed() -> None:
    """The ``filing-record list`` text column header survives the identifier redactor.

    The tab-delimited header places ``bucket_id`` immediately before the
    ``modelo`` column name. The ``label<TAB>value`` redaction heuristic must not
    rewrite the next column name into a ``<bucket-id>`` placeholder: a column
    header carries field names, never identifier values. The header row must pass
    through verbatim so automation can parse the columns.
    """
    create_cli_surface_profile()

    listed = _invoke(["app", "modelo", "filing-record", "list"])
    assert listed.exit_code == 0, listed.output

    header_line = "filing_record_id\tbucket_id\tmodelo\tyear\tperiod\tstatus\tfiled_at\tfiled_by"
    assert header_line in listed.output
    # The corruption symptom was ``bucket_id<TAB><bucket-id>`` replacing the
    # ``modelo`` column name; the well-formed header keeps every column name.
    assert "\tbucket_id\tmodelo\t" in listed.output
    assert f"bucket_id\t{CLI_BUCKET_ID_PLACEHOLDER}" not in listed.output


def test_app_modelo_filing_record_list_accepts_modelo_filter() -> None:
    create_cli_surface_profile()

    text_result = _invoke(["app", "modelo", "filing-record", "list", "--modelo", "303"])
    assert text_result.exit_code == 0, text_result.output
    assert "modelo_filter\t303" in text_result.output

    json_result = _invoke(["--format", "json", "app", "modelo", "filing-record", "list", "--modelo", "303"])
    assert json_result.exit_code == 0, json_result.output
    payload = _json(json_result)
    assert payload["modelo_filter"] == "303"
    assert payload["record_count"] == 0


def test_app_ledger_import_reimport_review_round_trips_state(tmp_path: Path) -> None:
    create_cli_surface_profile()
    statement = tmp_path / "n26.csv"
    statement.write_text(
        "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID\n"
        "2026-04-15,Client SL,Invoice 1,121.00,EUR,n26-001\n"
        "2026-04-16,SaaS Vendor,Subscription,-48.40,EUR,n26-002\n",
        encoding="utf-8",
    )
    imported = _invoke(["--format", "json", "app", "ledger", "import", "--file", str(statement), "--provider", "csv"])
    assert imported.exit_code == 0
    imported_payload = _json(imported)
    assert imported_payload["rows"] == 2
    assert imported_payload["imported"] == 2
    assert imported_payload["skipped"] == 0

    repeated = _invoke(["--format", "json", "app", "ledger", "import", "--file", str(statement), "--provider", "csv"])
    assert repeated.exit_code == 0
    repeated_payload = _json(repeated)
    assert repeated_payload["rows"] == 2
    assert repeated_payload["imported"] == 0
    assert repeated_payload["skipped"] == 2

    review = _invoke(["--format", "json", "app", "ledger", "review"])
    assert review.exit_code == 0
    payload = _json(review)
    rows_by_description = {row["description"]: row for row in payload["rows"]}
    assert set(rows_by_description) == {"Invoice 1", "Subscription"}
    assert {row["status"] for row in payload["rows"]} == {"pending"}
    vendor_id = rows_by_description["Subscription"]["id"]

    reviewed = _invoke(["--format", "json", "app", "ledger", "review", vendor_id])
    assert reviewed.exit_code == 0, reviewed.output
    reviewed_payload = _json(reviewed)
    assert reviewed_payload["id"] == vendor_id
    assert reviewed_payload["description"] == "Subscription"


def test_app_ledger_review_filter_rejects_unknown_key() -> None:
    result = _invoke(["app", "ledger", "review", "--filter", "kind=received"])
    assert result.exit_code != 0


def test_set_ratio_is_not_a_ledger_verb() -> None:
    for command in ("set-ratio",):
        result = _invoke(["app", "ledger", command, "--help"])
        assert result.exit_code != 0
