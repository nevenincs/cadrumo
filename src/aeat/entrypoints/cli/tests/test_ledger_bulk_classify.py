"""CLI surface tests for bulk classify (--from-csv) and rule engine (rule add/apply/list)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from ....application.user_profile._orchestration import profile_create_storage_span
from ....application.user_profile._testing import register_minimal_profile
from ....application.workflow._persistence import workflow_state_repository
from ....core.config import override_settings
from ....tests.secure_sql import isolated_profile_storage_root
from .. import app

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_RUNNER = CliRunner()


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        override_settings(aeat_local_storage_root=tmp_path, aeat_output_language="en"),
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span("default"),
    ):
        workflow_state_repository().update(lambda state: register_minimal_profile(state, profile_id="default"))
        yield


def _import_two_transactions(tmp_path: Path) -> tuple[str, str]:
    """Import two CSV rows and return their transaction ids (sorted by date)."""
    csv_content = (
        "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID\n"
        "2026-04-01,Acme SL,INV-001,100.00,EUR,bulk-001\n"
        "2026-04-02,Widgets SA,INV-002,200.00,EUR,bulk-002\n"
    )
    csv_path = tmp_path / "import.csv"
    csv_path.write_text(csv_content, encoding="utf-8")

    result = _RUNNER.invoke(app, ["app", "ledger", "import", str(csv_path), "--provider", "csv"])
    assert result.exit_code == 0, result.output

    listed = _RUNNER.invoke(app, ["--format", "json", "app", "ledger", "list"])
    assert listed.exit_code == 0, listed.output
    payload = json.loads(listed.output)
    rows = payload.get("result", payload).get("rows", [])
    assert len(rows) >= 2, listed.output
    rows_sorted = sorted(rows, key=lambda r: (r.get("date", ""), r.get("transaction_id", "")))
    return rows_sorted[0]["transaction_id"], rows_sorted[1]["transaction_id"]


def _list_transactions() -> list[dict[str, Any]]:
    listed = _RUNNER.invoke(app, ["--format", "json", "app", "ledger", "list"])
    assert listed.exit_code == 0, listed.output
    payload = json.loads(listed.output)
    return payload.get("result", payload).get("rows", [])


# ---------------------------------------------------------------------------
# --from-csv tests
# ---------------------------------------------------------------------------


def test_classify_from_csv_applies_all_valid_rows(tmp_path: Path) -> None:
    tx1, tx2 = _import_two_transactions(tmp_path)

    csv_content = f"transaction_id,classification\n{tx1},BUSINESS\n{tx2},PERSONAL\n"
    csv_file = tmp_path / "classify.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    result = _RUNNER.invoke(app, ["app", "ledger", "classify", "--from-csv", str(csv_file)])
    assert result.exit_code == 0, result.output

    by_id = {r["transaction_id"]: r for r in _list_transactions()}
    assert by_id[tx1]["business_classification"] == "BUSINESS"
    assert by_id[tx2]["business_classification"] == "PERSONAL"


def test_classify_from_csv_partial_failure_applies_valid_rows(tmp_path: Path) -> None:
    tx1, _tx2 = _import_two_transactions(tmp_path)

    csv_content = f"transaction_id,classification\n{tx1},BUSINESS\ndeadbeef,PERSONAL\n"
    csv_file = tmp_path / "partial.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    result = _RUNNER.invoke(
        app,
        ["--format", "json", "app", "ledger", "classify", "--from-csv", str(csv_file)],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)["result"]
    assert payload["applied"] >= 1
    assert payload["failures"]  # at least one failure for unknown id


def test_classify_from_csv_rejects_pipeline_managed_state(tmp_path: Path) -> None:
    """A bulk row naming a pipeline-managed state reds (mirrors the single-classify guard).

    ``SKIPPED_BY_RULE`` / ``FAILED_VALIDATION`` / ``PROCESSED_UNCLASSIFIED`` are
    produced by the pipeline, never assigned by hand. The valid BUSINESS row
    still applies (partial-success); the system-state row lands in ``failures``.
    """
    tx1, tx2 = _import_two_transactions(tmp_path)

    csv_content = f"transaction_id,classification\n{tx1},BUSINESS\n{tx2},SKIPPED_BY_RULE\n"
    csv_file = tmp_path / "system_state.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    result = _RUNNER.invoke(
        app,
        ["--format", "json", "app", "ledger", "classify", "--from-csv", str(csv_file)],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)["result"]
    assert payload["applied"] == 1, payload
    failure_ids = {f["transaction_id"] for f in payload["failures"]}
    assert tx2 in failure_ids, payload
    assert any("set automatically by aeat" in f["reason"] for f in payload["failures"]), payload


def test_classify_from_csv_rejects_unknown_column(tmp_path: Path) -> None:
    tx1, _ = _import_two_transactions(tmp_path)

    csv_content = f"transaction_id,classification,unknown_field\n{tx1},BUSINESS,foo\n"
    csv_file = tmp_path / "badcol.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    result = _RUNNER.invoke(app, ["app", "ledger", "classify", "--from-csv", str(csv_file)])
    assert result.exit_code != 0


def test_classify_from_csv_exclusive_with_id(tmp_path: Path) -> None:
    tx1, _ = _import_two_transactions(tmp_path)
    csv_file = tmp_path / "x.csv"
    csv_file.write_text(f"transaction_id,classification\n{tx1},BUSINESS\n", encoding="utf-8")

    result = _RUNNER.invoke(
        app,
        ["app", "ledger", "classify", "--from-csv", str(csv_file), tx1, "--classification", "BUSINESS"],
    )
    assert result.exit_code != 0


def test_classify_from_csv_not_found_raises(tmp_path: Path) -> None:
    result = _RUNNER.invoke(
        app,
        ["app", "ledger", "classify", "--from-csv", str(tmp_path / "nosuchfile.csv")],
    )
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# rule add / list tests
# ---------------------------------------------------------------------------


def test_rule_add_then_list_shows_rule() -> None:
    add_result = _RUNNER.invoke(
        app,
        ["app", "ledger", "rule", "add", "--description-pattern", "acme", "--classification", "BUSINESS"],
    )
    assert add_result.exit_code == 0, add_result.output
    assert "BUSINESS" in add_result.output

    list_result = _RUNNER.invoke(app, ["--format", "json", "app", "ledger", "rule", "list"])
    assert list_result.exit_code == 0, list_result.output
    envelope = json.loads(list_result.output)
    assert envelope["command"] == "ledger.rule.list"
    payload = envelope["result"]
    assert len(payload["rules"]) == 1
    assert payload["rules"][0]["description_pattern"] == "acme"
    assert payload["rules"][0]["classification"] == "BUSINESS"


def test_rule_add_idempotent_same_pattern() -> None:
    args = ["app", "ledger", "rule", "add", "--description-pattern", "acme", "--classification", "BUSINESS"]
    first = _RUNNER.invoke(app, args)
    second = _RUNNER.invoke(app, args)
    assert first.exit_code == 0, first.output
    assert second.exit_code == 0, second.output

    list_result = _RUNNER.invoke(app, ["--format", "json", "app", "ledger", "rule", "list"])
    payload = json.loads(list_result.output)["result"]
    # idempotent: same content-addressed id → still exactly one rule
    assert len(payload["rules"]) == 1


def test_rule_add_invalid_regex_rejected() -> None:
    result = _RUNNER.invoke(
        app,
        ["app", "ledger", "rule", "add", "--description-pattern", "[invalid", "--classification", "BUSINESS"],
    )
    assert result.exit_code != 0


@pytest.mark.parametrize("pattern", ["", "   "])
def test_rule_add_empty_or_whitespace_pattern_rejected_cleanly(pattern: str) -> None:
    """``rule add`` with an empty/whitespace pattern is refused with a clean message.

    The empty string trips the model's ``min_length=1`` as a raw pydantic
    ``ValidationError`` (not a ``ValueError``); without the boundary guard it
    leaked the pydantic repr/URL. A whitespace-only pattern matches nothing
    useful. Both must surface the instructive refusal, never a pydantic dump.
    """
    result = _RUNNER.invoke(
        app,
        ["app", "ledger", "rule", "add", "--description-pattern", pattern, "--classification", "BUSINESS"],
    )
    assert result.exit_code != 0, result.output
    combined = result.output or ""
    assert "pydantic.dev" not in combined, combined
    assert "input_value" not in combined, combined
    assert "--description-pattern" in combined, combined


def test_rule_list_empty() -> None:
    list_result = _RUNNER.invoke(app, ["--format", "json", "app", "ledger", "rule", "list"])
    assert list_result.exit_code == 0, list_result.output
    payload = json.loads(list_result.output)["result"]
    assert payload["rules"] == []


# ---------------------------------------------------------------------------
# rule apply tests
# ---------------------------------------------------------------------------


def test_rule_apply_classifies_not_yet_processed_transactions(tmp_path: Path) -> None:
    tx1, tx2 = _import_two_transactions(tmp_path)

    # The imported CSV uses "Payment reference" as description: INV-001, INV-002
    _RUNNER.invoke(
        app,
        ["app", "ledger", "rule", "add", "--description-pattern", "INV-001", "--classification", "BUSINESS"],
    )
    _RUNNER.invoke(
        app,
        ["app", "ledger", "rule", "add", "--description-pattern", "INV-002", "--classification", "PERSONAL"],
    )

    apply_result = _RUNNER.invoke(app, ["--format", "json", "app", "ledger", "rule", "apply"])
    assert apply_result.exit_code == 0, apply_result.output
    payload = json.loads(apply_result.output)["result"]
    assert payload["matched"] == 2

    by_id = {r["transaction_id"]: r for r in _list_transactions()}
    assert by_id[tx1]["business_classification"] == "BUSINESS"
    assert by_id[tx2]["business_classification"] == "PERSONAL"
    # provenance starts with "rule:"
    assert by_id[tx1].get("classified_by", "").startswith("rule:")
    assert by_id[tx2].get("classified_by", "").startswith("rule:")


def test_rule_apply_skips_already_classified_without_reaffirm(tmp_path: Path) -> None:
    tx1, _tx2 = _import_two_transactions(tmp_path)

    # Manually classify tx1
    _RUNNER.invoke(app, ["app", "ledger", "classify", tx1, "--classification", "PERSONAL"])

    _RUNNER.invoke(
        app,
        ["app", "ledger", "rule", "add", "--description-pattern", "INV-001", "--classification", "BUSINESS"],
    )
    _RUNNER.invoke(
        app,
        ["app", "ledger", "rule", "add", "--description-pattern", "INV-002", "--classification", "BUSINESS"],
    )

    apply_result = _RUNNER.invoke(app, ["--format", "json", "app", "ledger", "rule", "apply"])
    assert apply_result.exit_code == 0, apply_result.output
    payload = json.loads(apply_result.output)["result"]

    # tx1 was manually classified → skipped; tx2 is NOT_YET_PROCESSED → matched
    assert payload["skipped_already_classified"] >= 1
    assert payload["matched"] >= 1

    by_id = {r["transaction_id"]: r for r in _list_transactions()}
    # tx1 preserved as PERSONAL (manual wins without --reaffirm)
    assert by_id[tx1]["business_classification"] == "PERSONAL"


def test_rule_apply_dry_run_does_not_mutate(tmp_path: Path) -> None:
    _import_two_transactions(tmp_path)
    _RUNNER.invoke(
        app,
        ["app", "ledger", "rule", "add", "--description-pattern", "INV-001", "--classification", "BUSINESS"],
    )

    dry_result = _RUNNER.invoke(app, ["--format", "json", "app", "ledger", "rule", "apply", "--dry-run"])
    assert dry_result.exit_code == 0, dry_result.output
    payload = json.loads(dry_result.output)["result"]
    assert payload["dry_run"] is True
    assert payload["count"] >= 1

    # Confirm no mutation: transactions still NOT_YET_PROCESSED
    for row in _list_transactions():
        assert row["business_classification"] == "NOT_YET_PROCESSED"


def test_rule_priority_order_first_match_wins(tmp_path: Path) -> None:
    tx1, _ = _import_two_transactions(tmp_path)

    # Two rules both match "INV-001"; priority 1 (BUSINESS) should win over priority 100 (PERSONAL)
    _RUNNER.invoke(
        app,
        [
            "app",
            "ledger",
            "rule",
            "add",
            "--description-pattern",
            "INV",
            "--classification",
            "PERSONAL",
            "--priority",
            "100",
        ],
    )
    _RUNNER.invoke(
        app,
        [
            "app",
            "ledger",
            "rule",
            "add",
            "--description-pattern",
            "INV-001",
            "--classification",
            "BUSINESS",
            "--priority",
            "1",
        ],
    )

    apply_result = _RUNNER.invoke(app, ["app", "ledger", "rule", "apply"])
    assert apply_result.exit_code == 0, apply_result.output

    by_id = {r["transaction_id"]: r for r in _list_transactions()}
    # Priority 1 rule (BUSINESS) should have fired before priority 100 rule (PERSONAL)
    assert by_id[tx1]["business_classification"] == "BUSINESS"


def test_classify_from_csv_persists_iva_facts(tmp_path: Path) -> None:
    """Bulk --from-csv supplies the same IVA facts single-classify supplies.

    Drives the real bulk-CSV classify against the live ledger backend and
    asserts the persisted transaction carries the supplied
    ``taxable_base``/``iva_rate``/``iva_amount`` with strict equality. A
    classification-only row (no IVA columns) on the same batch must still
    classify with the IVA facts absent (zero regression).
    """
    tx1, tx2 = _import_two_transactions(tmp_path)

    csv_file = tmp_path / "iva.csv"
    # tx1 (gross 100.00 EUR) carries the IVA facts; the base + iva_amount must
    # equal the gross to the cent (the same domain invariant single-classify
    # enforces): 82.64 + 17.36 = 100.00. tx2 is classification-only (blank IVA
    # cells) and must behave exactly as a row without the columns at all.
    csv_file.write_text(
        "transaction_id,classification,taxable_base,iva_rate,iva_amount\n"
        f"{tx1},BUSINESS,82.64,0.21,17.36\n"
        f"{tx2},PERSONAL,,,\n",
        encoding="utf-8",
    )

    result = _RUNNER.invoke(
        app,
        ["--format", "json", "app", "ledger", "classify", "--from-csv", str(csv_file)],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)["result"]
    assert payload["applied"] == 2, payload
    assert not payload["failures"], payload

    by_id = {r["transaction_id"]: r for r in _list_transactions()}

    # tx1: the supplied IVA facts persisted, strict string equality.
    assert by_id[tx1]["business_classification"] == "BUSINESS"
    assert by_id[tx1]["taxable_base"] == "82.64"
    assert by_id[tx1]["iva_rate"] == "0.21"
    assert by_id[tx1]["iva_amount"] == "17.36"

    # tx2: classification-only row, IVA facts remain absent (no regression).
    assert by_id[tx2]["business_classification"] == "PERSONAL"
    assert by_id[tx2]["taxable_base"] is None
    assert by_id[tx2]["iva_rate"] is None
    assert by_id[tx2]["iva_amount"] is None


def test_classify_from_csv_iva_facts_match_single_classify(tmp_path: Path) -> None:
    """Bulk and single-id mode persist the supplied IVA facts via the same write path.

    tx1 (gross 100.00) is classified through the single positional-id surface and
    tx2 (gross 200.00) through the bulk ``--from-csv`` surface; each row's
    ``taxable_base + iva_amount`` equals its own gross (the shared domain
    invariant). Both surfaces must persist exactly the supplied values,
    proving the bulk path reuses the single-classify primitive rather than a
    parallel write path.
    """
    tx1, tx2 = _import_two_transactions(tmp_path)

    # Single-classify tx1 (gross 100.00) with IVA facts via positional-id mode.
    single = _RUNNER.invoke(
        app,
        [
            "app",
            "ledger",
            "classify",
            tx1,
            "--classification",
            "BUSINESS",
            "--taxable-base",
            "82.64",
            "--iva-rate",
            "0.21",
            "--iva-amount",
            "17.36",
        ],
    )
    assert single.exit_code == 0, single.output

    # Bulk-classify tx2 (gross 200.00) with IVA facts via --from-csv.
    csv_file = tmp_path / "bulk_iva.csv"
    csv_file.write_text(
        f"transaction_id,classification,taxable_base,iva_rate,iva_amount\n{tx2},BUSINESS,165.29,0.21,34.71\n",
        encoding="utf-8",
    )
    bulk = _RUNNER.invoke(app, ["app", "ledger", "classify", "--from-csv", str(csv_file)])
    assert bulk.exit_code == 0, bulk.output

    by_id = {r["transaction_id"]: r for r in _list_transactions()}
    # Single-classify persisted exactly what was supplied for tx1.
    assert by_id[tx1]["taxable_base"] == "82.64"
    assert by_id[tx1]["iva_rate"] == "0.21"
    assert by_id[tx1]["iva_amount"] == "17.36"
    # Bulk classify persisted exactly what was supplied for tx2.
    assert by_id[tx2]["taxable_base"] == "165.29"
    assert by_id[tx2]["iva_rate"] == "0.21"
    assert by_id[tx2]["iva_amount"] == "34.71"
    # The IVA rate carried identically across both surfaces.
    assert by_id[tx1]["iva_rate"] == by_id[tx2]["iva_rate"]


def test_classify_from_csv_rejects_malformed_iva_fact(tmp_path: Path) -> None:
    """A malformed IVA-fact Decimal reds the row, not a silent coercion."""
    tx1, tx2 = _import_two_transactions(tmp_path)
    csv_file = tmp_path / "bad_iva.csv"
    # tx1 carries a malformed taxable_base (reds the row); tx2 (gross 200.00)
    # carries a valid IVA set that satisfies the gross-equality invariant.
    csv_file.write_text(
        "transaction_id,classification,taxable_base,iva_rate,iva_amount\n"
        f"{tx1},BUSINESS,not-a-number,0.21,17.36\n"
        f"{tx2},BUSINESS,165.29,0.21,34.71\n",
        encoding="utf-8",
    )
    result = _RUNNER.invoke(
        app,
        ["--format", "json", "app", "ledger", "classify", "--from-csv", str(csv_file)],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)["result"]
    # The malformed row failed; the valid row applied (partial-success).
    assert payload["failures"], payload
    assert payload["applied"] == 1, payload
    by_id = {r["transaction_id"]: r for r in _list_transactions()}
    assert by_id[tx2]["taxable_base"] == "165.29"


def test_classify_from_csv_accepts_business_pct_for_mixed(tmp_path: Path) -> None:
    """MIXED rows classify in bulk via --from-csv with a business_pct column."""
    tx1, _tx2 = _import_two_transactions(tmp_path)
    csv_file = tmp_path / "mixed.csv"
    csv_file.write_text(
        f"transaction_id,classification,category_id,business_pct\n{tx1},MIXED,telefonia_movil,0.50\n",
        encoding="utf-8",
    )
    result = _RUNNER.invoke(app, ["--format", "json", "app", "ledger", "classify", "--from-csv", str(csv_file)])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["result"]["applied"] == 1
    row = {r["transaction_id"]: r for r in _list_transactions()}[tx1]
    assert row["business_classification"] == "MIXED"
    assert row["business_pct"] is not None and row["business_pct"].startswith("0.5")
