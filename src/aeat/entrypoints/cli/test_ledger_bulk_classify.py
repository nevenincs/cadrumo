"""CLI surface tests for bulk classify (--from-csv) and rule engine (rule add/apply/list)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aeat.adapters.persistence.storage.sql.engine import dispose_engine
from aeat.application.user_profile._orchestration import profile_create_storage_span
from aeat.application.user_profile._testing import register_minimal_profile
from aeat.application.workflow._persistence import workflow_state_repository
from aeat.entrypoints.cli import app
from aeat.tests.secure_sql import isolated_profile_storage_root

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_RUNNER = CliRunner()


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("AEAT_LOCAL_STORAGE_ROOT", str(tmp_path))
    monkeypatch.setenv("AEAT_OUTPUT_LANGUAGE", "en")
    dispose_engine()
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span("default"),
    ):
        try:
            workflow_state_repository().update(lambda state: register_minimal_profile(state, profile_id="default"))
            yield
        finally:
            dispose_engine()


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
    rows = payload if isinstance(payload, list) else payload.get("transactions", payload.get("rows", []))
    assert len(rows) >= 2, listed.output
    rows_sorted = sorted(rows, key=lambda r: (r.get("date", ""), r.get("transaction_id", "")))
    return rows_sorted[0]["transaction_id"], rows_sorted[1]["transaction_id"]


def _list_transactions() -> list[dict]:
    listed = _RUNNER.invoke(app, ["--format", "json", "app", "ledger", "list"])
    assert listed.exit_code == 0, listed.output
    payload = json.loads(listed.output)
    return payload if isinstance(payload, list) else payload.get("transactions", payload.get("rows", []))


# ---------------------------------------------------------------------------
# --from-csv tests
# ---------------------------------------------------------------------------


def test_classify_from_csv_applies_all_valid_rows(tmp_path: Path) -> None:
    tx1, tx2 = _import_two_transactions(tmp_path)

    csv_content = f"transaction_id,classification\n{tx1},BUSINESS\n{tx2},PERSONAL\n"
    csv_file = tmp_path / "classify.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    result = _RUNNER.invoke(
        app, ["app", "ledger", "classify", "--from-csv", str(csv_file)]
    )
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
    payload = json.loads(result.output)
    assert payload["applied"] >= 1
    assert payload["failures"]  # at least one failure for unknown id


def test_classify_from_csv_rejects_unknown_column(tmp_path: Path) -> None:
    tx1, _ = _import_two_transactions(tmp_path)

    csv_content = f"transaction_id,classification,unknown_field\n{tx1},BUSINESS,foo\n"
    csv_file = tmp_path / "badcol.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    result = _RUNNER.invoke(
        app, ["app", "ledger", "classify", "--from-csv", str(csv_file)]
    )
    assert result.exit_code != 0


def test_classify_from_csv_exclusive_with_id(tmp_path: Path) -> None:
    tx1, _ = _import_two_transactions(tmp_path)
    csv_file = tmp_path / "x.csv"
    csv_file.write_text(f"transaction_id,classification\n{tx1},BUSINESS\n", encoding="utf-8")

    result = _RUNNER.invoke(
        app,
        ["app", "ledger", "classify", "--from-csv", str(csv_file), "--id", tx1, "--classification", "BUSINESS"],
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
    payload = json.loads(list_result.output)
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
    payload = json.loads(list_result.output)
    # idempotent: same content-addressed id → still exactly one rule
    assert len(payload["rules"]) == 1


def test_rule_add_invalid_regex_rejected() -> None:
    result = _RUNNER.invoke(
        app,
        ["app", "ledger", "rule", "add", "--description-pattern", "[invalid", "--classification", "BUSINESS"],
    )
    assert result.exit_code != 0


def test_rule_list_empty() -> None:
    list_result = _RUNNER.invoke(app, ["--format", "json", "app", "ledger", "rule", "list"])
    assert list_result.exit_code == 0, list_result.output
    payload = json.loads(list_result.output)
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
    payload = json.loads(apply_result.output)
    assert payload["matched"] == 2

    by_id = {r["transaction_id"]: r for r in _list_transactions()}
    assert by_id[tx1]["business_classification"] == "BUSINESS"
    assert by_id[tx2]["business_classification"] == "PERSONAL"
    # provenance starts with "rule:"
    assert by_id[tx1].get("classified_by", "").startswith("rule:")
    assert by_id[tx2].get("classified_by", "").startswith("rule:")


def test_rule_apply_skips_already_classified_without_reaffirm(tmp_path: Path) -> None:
    tx1, tx2 = _import_two_transactions(tmp_path)

    # Manually classify tx1
    _RUNNER.invoke(
        app, ["app", "ledger", "classify", "--id", tx1, "--classification", "PERSONAL"]
    )

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
    payload = json.loads(apply_result.output)

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
    payload = json.loads(dry_result.output)
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
            "app", "ledger", "rule", "add",
            "--description-pattern", "INV",
            "--classification", "PERSONAL",
            "--priority", "100",
        ],
    )
    _RUNNER.invoke(
        app,
        [
            "app", "ledger", "rule", "add",
            "--description-pattern", "INV-001",
            "--classification", "BUSINESS",
            "--priority", "1",
        ],
    )

    apply_result = _RUNNER.invoke(app, ["app", "ledger", "rule", "apply"])
    assert apply_result.exit_code == 0, apply_result.output

    by_id = {r["transaction_id"]: r for r in _list_transactions()}
    # Priority 1 rule (BUSINESS) should have fired before priority 100 rule (PERSONAL)
    assert by_id[tx1]["business_classification"] == "BUSINESS"
