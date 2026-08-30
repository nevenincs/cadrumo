from __future__ import annotations

import json
from pathlib import Path

import pytest

from ._isolated_profile_storage_fixtures import live_fx_isolated_backend
from ._ledger_corpus_support import (
    _active_repo,
    _find,
    _import_bbva,
    _import_corpus,
    _invoke,
    _list_rows,
    _match,
    _oracle_rules,
)

__all__ = ["live_fx_isolated_backend"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_bulk_classify_from_oracle_resolved_at_runtime(tmp_path: Path) -> None:
    _import_corpus()
    rules = _oracle_rules()
    rows = _list_rows()
    lines = ["transaction_id,classification,category_id"]
    expected: dict[str, str] = {}
    for row in rows:
        tx_id = row["transaction_id"]
        assert isinstance(tx_id, str)
        rule = _match(row["description"], rules)
        if rule is None or rule["classification"] == "MIXED":
            continue
        classification = rule["classification"]
        assert isinstance(classification, str)
        cat_raw = rule.get("category_id")
        cat = cat_raw if isinstance(cat_raw, str) else ""
        lines.append(f"{tx_id},{classification},{cat}")
        expected[tx_id] = classification
        if len(expected) >= 12:
            break
    assert len(expected) == 12

    classify_csv = tmp_path / "classify.csv"
    classify_csv.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = _invoke(["--format", "json", "app", "ledger", "classify", "--file", str(classify_csv)])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)["result"]
    assert payload["applied"] == 12, payload

    by_id = {row["transaction_id"]: row for row in _list_rows()}
    for tx_id, classification in expected.items():
        assert by_id[tx_id]["business_classification"] == classification


def test_single_classify_intracommunity_with_eu_state() -> None:
    from ....domain.iva import EUMemberState, IvaCategory
    from ....domain.transactions.enums import BusinessClassification

    _import_corpus()
    rows = _list_rows()
    de_rows = [row for row in rows if "cliente DE GmbH intracom" in row["description"]]
    assert de_rows, "corpus must contain a DE intracommunity client invoice"
    tx = de_rows[0]["transaction_id"]
    result = _invoke(
        [
            "app",
            "ledger",
            "classify",
            tx,
            "--classification",
            "BUSINESS",
            "--iva-category",
            "intra_community_supply",
            "--counterparty-country",
            "DE",
        ],
    )
    assert result.exit_code == 0, result.output
    txn = _active_repo().load().get(tx)
    assert txn is not None
    assert txn.business_classification is BusinessClassification.BUSINESS
    assert txn.iva_category is IvaCategory.INTRA_COMMUNITY_SUPPLY
    assert txn.counterparty_country == "DE"
    assert txn.counterparty_eu_member_state is EUMemberState.DE


def test_allocate_records_business_proportion() -> None:
    from decimal import Decimal

    from ....domain.transactions.enums import BusinessClassification

    _import_bbva()
    internet = _find(_list_rows(), "Factura internet fibra oficina enero")
    tx = internet["transaction_id"]
    result = _invoke(
        [
            "app",
            "ledger",
            "allocate",
            tx,
            "--business-pct",
            "0.30",
            "--category-id",
            "suministros_home_office_internet",
        ],
    )
    assert result.exit_code == 0, result.output
    txn = _active_repo().load().get(tx)
    assert txn is not None
    assert txn.business_classification is BusinessClassification.MIXED
    assert txn.business_pct == Decimal("0.30")
    assert txn.category_id == "suministros_home_office_internet"


def test_ratios_eligible_set_list_validate() -> None:
    _import_bbva()
    eligible = _invoke(["--format", "json", "app", "ledger", "ratios", "eligible"])
    assert eligible.exit_code == 0, eligible.output
    blob = json.dumps(json.loads(eligible.output))
    category = "telefonia_movil" if "telefonia_movil" in blob else "vehiculo_combustible"
    setr = _invoke(["app", "ledger", "ratios", "set", category, "0.50"])
    assert setr.exit_code == 0, setr.output
    listed = _invoke(["app", "ledger", "ratios", "list"])
    assert listed.exit_code == 0 and category in listed.output, listed.output
    validate = _invoke(["app", "ledger", "ratios", "validate"])
    assert validate.exit_code == 0, validate.output


def test_transfer_row_reclassified_to_internal_transfer_and_locked_out_of_tax() -> None:
    _import_bbva()
    rows = _list_rows()
    transfer = _find(rows, "Transferencia a cuenta personal CaixaBank")
    tx = transfer["transaction_id"]
    assert transfer["direction"] == "OUTGOING"
    assert transfer["business_classification"] == "NOT_YET_PROCESSED"

    reclass = _invoke(["app", "ledger", "update", tx, "--direction", "INTERNAL_TRANSFER"])
    assert reclass.exit_code == 0, reclass.output
    after = {row["transaction_id"]: row for row in _list_rows()}[tx]
    assert after["direction"] == "INTERNAL_TRANSFER"

    refused = _invoke(["app", "ledger", "update", tx, "--classification", "BUSINESS"])
    assert refused.exit_code != 0, refused.output
    assert after["business_classification"] != "BUSINESS"
