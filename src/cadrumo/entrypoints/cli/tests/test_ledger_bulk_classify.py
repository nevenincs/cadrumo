"""CLI surface tests for bulk classify (--file) and rule engine (rule add/apply/list)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from ....tests.cli_runner import invoke_cached_cli
from .._ledger_rule_payloads import ClassificationRulePayload, RuleApplyAppliedPayload, RuleApplyMatchPayload
from ._isolated_profile_storage_fixtures import llm_profile_isolated_backend

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]
__all__ = ["llm_profile_isolated_backend"]


def _import_two_transactions(tmp_path: Path) -> tuple[str, str]:
    """Import two CSV rows and return their transaction ids (sorted by date)."""
    csv_content = (
        "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID\n"
        "2026-04-01,Acme SL,INV-001,100.00,EUR,bulk-001\n"
        "2026-04-02,Widgets SA,INV-002,200.00,EUR,bulk-002\n"
    )
    csv_path = tmp_path / "import.csv"
    csv_path.write_text(csv_content, encoding="utf-8")

    result = invoke_cached_cli(["app", "ledger", "import", "--file", str(csv_path), "--provider", "csv"])
    assert result.exit_code == 0, result.output

    listed = invoke_cached_cli(["--format", "json", "app", "ledger", "list"])
    assert listed.exit_code == 0, listed.output
    payload = json.loads(listed.output)
    assert isinstance(payload, dict), listed.output
    result = payload.get("result", payload)
    assert isinstance(result, dict), listed.output
    raw_rows = result.get("rows", [])
    assert isinstance(raw_rows, list), listed.output
    rows: list[dict[str, object]] = []
    for raw_row in raw_rows:
        assert isinstance(raw_row, dict), listed.output
        rows.append({str(key): value for key, value in raw_row.items()})
    assert len(rows) >= 2, listed.output
    rows_sorted = sorted(
        rows,
        key=lambda row: (
            row.get("date") if isinstance(row.get("date"), str) else "",
            row.get("transaction_id") if isinstance(row.get("transaction_id"), str) else "",
        ),
    )
    first_id = rows_sorted[0].get("transaction_id")
    second_id = rows_sorted[1].get("transaction_id")
    assert isinstance(first_id, str) and isinstance(second_id, str), listed.output
    return first_id, second_id


def _list_transactions() -> list[dict[str, Any]]:
    listed = invoke_cached_cli(["--format", "json", "app", "ledger", "list"])
    assert listed.exit_code == 0, listed.output
    payload = json.loads(listed.output)
    return payload.get("result", payload).get("rows", [])


def _stored_transaction(transaction_id: str) -> Any:
    from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
    from ....core.bucket_pointer import resolve_active_bucket_id

    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None
    return TransactionCatalogueRepository(bucket_id=bucket_id).load().transactions[transaction_id]


def _classify_with_tax_facts(transaction_id: str) -> None:
    result = invoke_cached_cli(
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
            "82.64",
            "--iva-rate",
            "0.21",
            "--iva-amount",
            "17.36",
            "--iva-category",
            "domestic_general",
            "--irpf-category",
            "actividades_economicas_directa_simplificada",
        ],
    )
    assert result.exit_code == 0, result.output


def _import_many_transactions(tmp_path: Path, *, count: int) -> list[str]:
    lines = ["Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID"]
    for idx in range(1, count + 1):
        lines.append(f"2026-05-{idx:02d},Vendor {idx},INV-{idx:03d},{idx}.00,EUR,many-{idx:03d}")
    csv_path = tmp_path / "many.csv"
    csv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = invoke_cached_cli(["app", "ledger", "import", "--file", str(csv_path), "--provider", "csv"])
    assert result.exit_code == 0, result.output
    return [row["transaction_id"] for row in _list_transactions()]


# ---------------------------------------------------------------------------
# --file tests
# ---------------------------------------------------------------------------


def test_classify_from_csv_applies_all_valid_rows(tmp_path: Path) -> None:
    tx1, tx2 = _import_two_transactions(tmp_path)

    csv_content = f"transaction_id,classification\n{tx1},BUSINESS\n{tx2},PERSONAL\n"
    csv_file = tmp_path / "classify.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    result = invoke_cached_cli(["app", "ledger", "classify", "--file", str(csv_file)])
    assert result.exit_code == 0, result.output

    by_id = {r["transaction_id"]: r for r in _list_transactions()}
    assert by_id[tx1]["business_classification"] == "BUSINESS"
    assert by_id[tx2]["business_classification"] == "PERSONAL"


def test_classify_from_csv_partial_failure_applies_valid_rows(tmp_path: Path) -> None:
    tx1, _tx2 = _import_two_transactions(tmp_path)

    csv_content = f"transaction_id,classification\n{tx1},BUSINESS\ndeadbeef,PERSONAL\n"
    csv_file = tmp_path / "partial.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    result = invoke_cached_cli(
        ["--format", "json", "app", "ledger", "classify", "--file", str(csv_file)],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)["result"]
    assert payload["applied"] >= 1
    assert payload["failures"]  # at least one failure for unknown id


def test_classify_from_csv_all_failed_exits_nonzero(tmp_path: Path) -> None:
    _import_two_transactions(tmp_path)

    csv_content = "transaction_id,classification\nmissing-short,BUSINESS\nmissing-long,PERSONAL\n"
    csv_file = tmp_path / "all_failed.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    result = invoke_cached_cli(
        ["--format", "json", "app", "ledger", "classify", "--file", str(csv_file)],
    )
    assert result.exit_code != 0, result.output
    envelope = json.loads(result.output)
    payload = envelope["result"]
    assert envelope["status"] == "warning", envelope
    assert envelope["notices"][0]["code"] == "ledger.classify.bulk_all_failed", envelope
    assert payload["total"] == 2, payload
    assert payload["applied"] == 0, payload
    assert len(payload["failures"]) == 2, payload


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

    result = invoke_cached_cli(
        ["--format", "json", "app", "ledger", "classify", "--file", str(csv_file)],
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

    result = invoke_cached_cli(["app", "ledger", "classify", "--file", str(csv_file)])
    assert result.exit_code != 0


def test_classify_from_csv_accepts_iva_category_column(tmp_path: Path) -> None:
    """Bulk CSV accepts the same IVA category field as single-row classify."""
    from ....domain.iva.schema import IvaCategory

    tx1, _tx2 = _import_two_transactions(tmp_path)
    csv_file = tmp_path / "iva_category.csv"
    csv_file.write_text(
        f"transaction_id,classification,iva_category\n{tx1},BUSINESS,domestic_general\n",
        encoding="utf-8",
    )

    result = invoke_cached_cli(
        ["--format", "json", "app", "ledger", "classify", "--file", str(csv_file)],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)["result"]
    assert payload["applied"] == 1, payload
    assert payload["failures"] == [], payload
    assert _stored_transaction(tx1).iva_category is IvaCategory.DOMESTIC_GENERAL


def test_classify_from_csv_accepts_irpf_category_column(tmp_path: Path) -> None:
    """Bulk CSV accepts the same IRPF category field as single-row classify."""
    tx1, _tx2 = _import_two_transactions(tmp_path)
    csv_file = tmp_path / "irpf_category.csv"
    csv_file.write_text(
        f"transaction_id,classification,irpf_category\n{tx1},BUSINESS,actividades_economicas_directa_simplificada\n",
        encoding="utf-8",
    )

    result = invoke_cached_cli(
        ["--format", "json", "app", "ledger", "classify", "--file", str(csv_file)],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)["result"]
    assert payload["applied"] == 1, payload
    assert payload["failures"] == [], payload
    assert _stored_transaction(tx1).irpf_category == "actividades_economicas_directa_simplificada"


def test_classify_from_csv_accepts_display_id_prefix(tmp_path: Path) -> None:
    """Bulk CSV resolves transaction ids like single-row classify does."""
    tx1, _tx2 = _import_two_transactions(tmp_path)
    by_id = {row["transaction_id"]: row for row in _list_transactions()}
    display_id = by_id[tx1]["display_id"]
    csv_file = tmp_path / "short_id.csv"
    csv_file.write_text(f"transaction_id,classification\n{display_id},BUSINESS\n", encoding="utf-8")

    result = invoke_cached_cli(
        ["--format", "json", "app", "ledger", "classify", "--file", str(csv_file)],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)["result"]
    assert payload["applied"] == 1, payload
    assert payload["failures"] == [], payload
    by_id = {row["transaction_id"]: row for row in _list_transactions()}
    assert by_id[tx1]["business_classification"] == "BUSINESS"


def test_classify_from_csv_ambiguous_prefix_is_row_failure(tmp_path: Path) -> None:
    """An ambiguous short id fails that row while other valid rows apply."""
    transaction_ids = _import_many_transactions(tmp_path, count=17)
    by_initial: dict[str, list[str]] = {}
    for transaction_id in transaction_ids:
        by_initial.setdefault(transaction_id[0], []).append(transaction_id)
    ambiguous_prefix, ambiguous_matches = next(
        (prefix, matches) for prefix, matches in by_initial.items() if len(matches) > 1
    )
    valid_id = ambiguous_matches[0]
    csv_file = tmp_path / "ambiguous_prefix.csv"
    csv_file.write_text(
        f"transaction_id,classification\n{valid_id},BUSINESS\n{ambiguous_prefix},PERSONAL\n",
        encoding="utf-8",
    )

    result = invoke_cached_cli(
        ["--format", "json", "app", "ledger", "classify", "--file", str(csv_file)],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)["result"]
    assert payload["applied"] == 1, payload
    assert len(payload["failures"]) == 1, payload
    assert payload["failures"][0]["transaction_id"] == ambiguous_prefix, payload
    assert "matches" in payload["failures"][0]["reason"], payload
    by_id = {row["transaction_id"]: row for row in _list_transactions()}
    assert by_id[valid_id]["business_classification"] == "BUSINESS"


def test_classify_from_csv_exclusive_with_id(tmp_path: Path) -> None:
    tx1, _ = _import_two_transactions(tmp_path)
    csv_file = tmp_path / "x.csv"
    csv_file.write_text(f"transaction_id,classification\n{tx1},BUSINESS\n", encoding="utf-8")

    result = invoke_cached_cli(
        ["app", "ledger", "classify", "--file", str(csv_file), tx1, "--classification", "BUSINESS"],
    )
    assert result.exit_code != 0


def test_classify_from_csv_not_found_raises(tmp_path: Path) -> None:
    result = invoke_cached_cli(
        ["app", "ledger", "classify", "--file", str(tmp_path / "nosuchfile.csv")],
    )
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# rule add / list tests
# ---------------------------------------------------------------------------


def test_rule_add_then_list_shows_rule() -> None:
    add_result = invoke_cached_cli(
        ["app", "ledger", "rule", "add", "--description-pattern", "acme", "--classification", "BUSINESS"],
    )
    assert add_result.exit_code == 0, add_result.output
    assert "BUSINESS" in add_result.output

    list_result = invoke_cached_cli(["--format", "json", "app", "ledger", "rule", "list"])
    assert list_result.exit_code == 0, list_result.output
    envelope = json.loads(list_result.output)
    assert envelope["command"] == "ledger.rule.list"
    payload = envelope["result"]
    assert len(payload["rules"]) == 1
    assert payload["rules"][0]["description_pattern"] == "acme"
    assert payload["rules"][0]["classification"] == "BUSINESS"


def test_rule_add_idempotent_same_pattern() -> None:
    args = ["app", "ledger", "rule", "add", "--description-pattern", "acme", "--classification", "BUSINESS"]
    first = invoke_cached_cli(args)
    second = invoke_cached_cli(args)
    assert first.exit_code == 0, first.output
    assert second.exit_code == 0, second.output

    list_result = invoke_cached_cli(["--format", "json", "app", "ledger", "rule", "list"])
    payload = json.loads(list_result.output)["result"]
    # idempotent: same content-addressed id → still exactly one rule
    assert len(payload["rules"]) == 1


def test_rule_add_invalid_regex_rejected() -> None:
    result = invoke_cached_cli(
        ["app", "ledger", "rule", "add", "--description-pattern", "[invalid", "--classification", "BUSINESS"],
    )
    assert result.exit_code != 0


@pytest.mark.parametrize(
    "payload",
    (
        {
            "rule_id": "not-a-digest",
            "description_pattern": "acme",
            "classification": "BUSINESS",
            "priority": 1,
            "actor": "operator",
            "created_at": "2026-08-01T12:00:00Z",
        },
        {
            "rule_id": "a" * 64,
            "description_pattern": "[invalid",
            "classification": "BUSINESS",
            "priority": 1,
            "actor": "operator",
            "created_at": "2026-08-01T12:00:00Z",
        },
    ),
)
def test_rule_payload_refuses_noncanonical_rule_contract(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ClassificationRulePayload.model_validate(payload)


@pytest.mark.parametrize("payload_type", (RuleApplyMatchPayload, RuleApplyAppliedPayload))
def test_rule_apply_payload_refuses_malformed_rule_identity(
    payload_type: type[RuleApplyMatchPayload | RuleApplyAppliedPayload],
) -> None:
    payload: dict[str, object] = {
        "transaction_id": "transaction-1",
        "matched_rule_id": "not-a-digest",
        "classification": "BUSINESS",
    }
    if payload_type is RuleApplyMatchPayload:
        payload["description"] = "Acme invoice"
    with pytest.raises(ValidationError):
        payload_type.model_validate(payload)


@pytest.mark.parametrize("pattern", ["", "   "])
def test_rule_add_empty_or_whitespace_pattern_rejected_cleanly(pattern: str) -> None:
    """``rule add`` with an empty/whitespace pattern is refused with a clean message.

    The empty string trips the model's ``min_length=1`` as a raw pydantic
    ``ValidationError`` (not a ``ValueError``); without the boundary guard it
    leaked the pydantic repr/URL. A whitespace-only pattern matches nothing
    useful. Both must surface the instructive refusal, never a pydantic dump.
    """
    result = invoke_cached_cli(
        ["app", "ledger", "rule", "add", "--description-pattern", pattern, "--classification", "BUSINESS"],
    )
    assert result.exit_code != 0, result.output
    combined = result.output or ""
    assert "pydantic.dev" not in combined, combined
    assert "input_value" not in combined, combined
    assert "--description-pattern" in combined, combined


def test_rule_list_empty() -> None:
    list_result = invoke_cached_cli(["--format", "json", "app", "ledger", "rule", "list"])
    assert list_result.exit_code == 0, list_result.output
    payload = json.loads(list_result.output)["result"]
    assert payload["rules"] == []


# ---------------------------------------------------------------------------
# rule apply tests
# ---------------------------------------------------------------------------


def test_rule_apply_classifies_not_yet_processed_transactions(tmp_path: Path) -> None:
    tx1, tx2 = _import_two_transactions(tmp_path)

    # The imported CSV uses "Payment reference" as description: INV-001, INV-002
    invoke_cached_cli(
        ["app", "ledger", "rule", "add", "--description-pattern", "INV-001", "--classification", "BUSINESS"],
    )
    invoke_cached_cli(
        ["app", "ledger", "rule", "add", "--description-pattern", "INV-002", "--classification", "PERSONAL"],
    )

    apply_result = invoke_cached_cli(["--format", "json", "app", "ledger", "rule", "apply"])
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
    invoke_cached_cli(["app", "ledger", "classify", tx1, "--classification", "PERSONAL"])

    invoke_cached_cli(
        ["app", "ledger", "rule", "add", "--description-pattern", "INV-001", "--classification", "BUSINESS"],
    )
    invoke_cached_cli(
        ["app", "ledger", "rule", "add", "--description-pattern", "INV-002", "--classification", "BUSINESS"],
    )

    apply_result = invoke_cached_cli(["--format", "json", "app", "ledger", "rule", "apply"])
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
    invoke_cached_cli(
        ["app", "ledger", "rule", "add", "--description-pattern", "INV-001", "--classification", "BUSINESS"],
    )

    dry_result = invoke_cached_cli(["--format", "json", "app", "ledger", "rule", "apply", "--dry-run"])
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
    invoke_cached_cli(
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
    invoke_cached_cli(
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

    apply_result = invoke_cached_cli(["app", "ledger", "rule", "apply"])
    assert apply_result.exit_code == 0, apply_result.output

    by_id = {r["transaction_id"]: r for r in _list_transactions()}
    # Priority 1 rule (BUSINESS) should have fired before priority 100 rule (PERSONAL)
    assert by_id[tx1]["business_classification"] == "BUSINESS"


def test_classify_from_csv_persists_iva_facts(tmp_path: Path) -> None:
    """Bulk --file supplies the same IVA facts single-classify supplies.

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

    result = invoke_cached_cli(
        ["--format", "json", "app", "ledger", "classify", "--file", str(csv_file)],
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


def test_classify_from_csv_preserves_existing_tax_facts_when_columns_omitted(tmp_path: Path) -> None:
    """Partial classification CSV rows must not clear facts they do not mention."""
    tx1, _tx2 = _import_two_transactions(tmp_path)
    _classify_with_tax_facts(tx1)

    csv_file = tmp_path / "classification_only.csv"
    csv_file.write_text(
        f"transaction_id,classification,category_id\n{tx1},BUSINESS,material_oficina\n",
        encoding="utf-8",
    )

    result = invoke_cached_cli(
        ["--format", "json", "app", "ledger", "classify", "--file", str(csv_file)],
    )

    assert result.exit_code == 0, result.output
    row = {r["transaction_id"]: r for r in _list_transactions()}[tx1]
    assert row["business_classification"] == "BUSINESS"
    assert row["category_id"] == "material_oficina"
    assert row["taxable_base"] == "82.64"
    assert row["iva_rate"] == "0.21"
    assert row["iva_amount"] == "17.36"
    assert row["iva_category"] == "domestic_general"
    assert row["irpf_category"] == "actividades_economicas_directa_simplificada"


def test_classify_from_csv_blank_optional_tax_cells_preserve_existing_values(tmp_path: Path) -> None:
    """Blank optional CSV cells behave as omitted cells, not destructive clears."""
    tx1, _tx2 = _import_two_transactions(tmp_path)
    _classify_with_tax_facts(tx1)

    csv_file = tmp_path / "blank_tax_cells.csv"
    csv_file.write_text(
        "transaction_id,classification,category_id,taxable_base,iva_rate,iva_amount,iva_category,irpf_category\n"
        f"{tx1},BUSINESS,material_oficina,,,,,\n",
        encoding="utf-8",
    )

    result = invoke_cached_cli(
        ["--format", "json", "app", "ledger", "classify", "--file", str(csv_file)],
    )

    assert result.exit_code == 0, result.output
    row = {r["transaction_id"]: r for r in _list_transactions()}[tx1]
    assert row["business_classification"] == "BUSINESS"
    assert row["category_id"] == "material_oficina"
    assert row["taxable_base"] == "82.64"
    assert row["iva_rate"] == "0.21"
    assert row["iva_amount"] == "17.36"
    assert row["iva_category"] == "domestic_general"
    assert row["irpf_category"] == "actividades_economicas_directa_simplificada"


def test_classify_from_csv_iva_facts_match_single_classify(tmp_path: Path) -> None:
    """Bulk and single-id mode persist the supplied IVA facts via the same write path.

    tx1 (gross 100.00) is classified through the single positional-id surface and
    tx2 (gross 200.00) through the bulk ``--file`` surface; each row's
    ``taxable_base + iva_amount`` equals its own gross (the shared domain
    invariant). Both surfaces must persist exactly the supplied values,
    proving the bulk path reuses the single-classify primitive rather than a
    parallel write path.
    """
    tx1, tx2 = _import_two_transactions(tmp_path)

    # Single-classify tx1 (gross 100.00) with IVA facts via positional-id mode.
    single = invoke_cached_cli(
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

    # Bulk-classify tx2 (gross 200.00) with IVA facts via --file.
    csv_file = tmp_path / "bulk_iva.csv"
    csv_file.write_text(
        f"transaction_id,classification,taxable_base,iva_rate,iva_amount\n{tx2},BUSINESS,165.29,0.21,34.71\n",
        encoding="utf-8",
    )
    bulk = invoke_cached_cli(["app", "ledger", "classify", "--file", str(csv_file)])
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
    result = invoke_cached_cli(
        ["--format", "json", "app", "ledger", "classify", "--file", str(csv_file)],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)["result"]
    # The malformed row failed; the valid row applied (partial-success).
    assert payload["failures"], payload
    assert payload["applied"] == 1, payload
    by_id = {r["transaction_id"]: r for r in _list_transactions()}
    assert by_id[tx2]["taxable_base"] == "165.29"


def test_classify_from_csv_surplus_cells_are_row_failure(tmp_path: Path) -> None:
    """A row with more cells than headers fails that row without aborting the batch."""
    tx1, tx2 = _import_two_transactions(tmp_path)
    csv_file = tmp_path / "surplus_cells.csv"
    csv_file.write_text(
        f"transaction_id,classification\n{tx1},BUSINESS,unexpected-extra-cell\n{tx2},BUSINESS\n",
        encoding="utf-8",
    )

    result = invoke_cached_cli(
        ["--format", "json", "app", "ledger", "classify", "--file", str(csv_file)],
    )

    assert result.exit_code == 0, result.output
    assert "AttributeError" not in result.output
    assert "strip" not in result.output
    payload = json.loads(result.output)["result"]
    assert payload["applied"] == 1, payload
    assert len(payload["failures"]) == 1, payload
    assert payload["failures"][0]["transaction_id"] == tx1, payload
    assert "more cells than header columns" in payload["failures"][0]["reason"], payload
    by_id = {row["transaction_id"]: row for row in _list_transactions()}
    assert by_id[tx1]["business_classification"] == "NOT_YET_PROCESSED"
    assert by_id[tx2]["business_classification"] == "BUSINESS"


def test_classify_from_csv_accepts_business_pct_for_mixed(tmp_path: Path) -> None:
    """MIXED rows classify in bulk via --file with a business_pct column."""
    tx1, _tx2 = _import_two_transactions(tmp_path)
    csv_file = tmp_path / "mixed.csv"
    csv_file.write_text(
        f"transaction_id,classification,category_id,business_pct\n{tx1},MIXED,telefonia_movil,0.50\n",
        encoding="utf-8",
    )
    result = invoke_cached_cli(["--format", "json", "app", "ledger", "classify", "--file", str(csv_file)])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["result"]["applied"] == 1
    row = {r["transaction_id"]: r for r in _list_transactions()}[tx1]
    assert row["business_classification"] == "MIXED"
    assert row["business_pct"] is not None and row["business_pct"].startswith("0.5")


def test_classify_from_csv_accepts_usage_ratio_id_for_mixed(tmp_path: Path) -> None:
    """Bulk CSV can carry the proportionality reference needed by mixed rows."""
    tx1, _tx2 = _import_two_transactions(tmp_path)

    ratio = invoke_cached_cli(["app", "ledger", "ratios", "set", "telefonia_movil", "0.50"])
    assert ratio.exit_code == 0, ratio.output

    csv_file = tmp_path / "mixed_with_ratio.csv"
    csv_file.write_text(
        "transaction_id,classification,category_id,business_pct,usage_ratio_id\n"
        f"{tx1},MIXED,telefonia_movil,0.50,telefonia_movil\n",
        encoding="utf-8",
    )

    result = invoke_cached_cli(["--format", "json", "app", "ledger", "classify", "--file", str(csv_file)])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)["result"]
    assert payload["applied"] == 1, payload
    assert payload["failures"] == [], payload

    row = {r["transaction_id"]: r for r in _list_transactions()}[tx1]
    assert row["business_classification"] == "MIXED"
    assert row["business_pct"] is not None and row["business_pct"].startswith("0.5")
    assert row["usage_ratio_id"] == "telefonia_movil"

    stored = _stored_transaction(tx1)
    assert stored.usage_ratio_id == "telefonia_movil"
    assert stored.classification_reason == "aeat app ledger classify --file"
    assert stored.edit_lineage[-1].source_command == "aeat app ledger classify --file"


def test_classify_from_csv_rejects_unknown_usage_ratio_id(tmp_path: Path) -> None:
    """Bulk CSV uses the shared usage-ratio validator before persisting a mixed row."""
    tx1, _tx2 = _import_two_transactions(tmp_path)
    csv_file = tmp_path / "mixed_unknown_ratio.csv"
    csv_file.write_text(
        "transaction_id,classification,category_id,business_pct,usage_ratio_id\n"
        f"{tx1},MIXED,telefonia_movil,0.50,telefonia_movil\n",
        encoding="utf-8",
    )

    result = invoke_cached_cli(["--format", "json", "app", "ledger", "classify", "--file", str(csv_file)])
    assert result.exit_code != 0, result.output
    payload = json.loads(result.output)["result"]
    assert payload["applied"] == 0, payload
    assert payload["failures"][0]["transaction_id"] == tx1, payload
    assert "usage_ratio_id" in payload["failures"][0]["reason"], payload

    stored = _stored_transaction(tx1)
    assert stored.business_classification == "NOT_YET_PROCESSED"
    assert stored.usage_ratio_id is None
    assert stored.edit_lineage == ()
