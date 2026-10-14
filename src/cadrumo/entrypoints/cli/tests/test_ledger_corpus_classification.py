from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from click.testing import Result

from ....domain.calculations.registry.authority import bundled_indexed_authority
from ...tests.ledger_corpus_support import (
    _find,
    _import_bbva,
    _import_corpus,
    _invoke,
    _match,
    _oracle_rules,
    load_active_catalogue,
)
from .ledger_cli import list_ledger_rows_via_cli as _list_rows
from .profile_world_fixtures import recorded_fx_isolated_backend

__all__ = ["recorded_fx_isolated_backend"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_bulk_classify_from_oracle_resolved_at_runtime(tmp_path: Path, invoke_cli: Callable[..., Result]) -> None:
    _import_corpus(invoke_cli=invoke_cli)
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

    result = _invoke(
        ["--format", "json", "app", "ledger", "classify", "--file", str(classify_csv)], invoke_cli=invoke_cli
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)["result"]
    assert payload["applied"] == 12, payload

    by_id = {row["transaction_id"]: row for row in _list_rows()}
    for tx_id, classification in expected.items():
        assert by_id[tx_id]["business_classification"] == classification


def test_single_classify_intracommunity_with_eu_state(invoke_cli: Callable[..., Result]) -> None:
    from ....domain.iva.schema import EUMemberState, IvaCategory
    from ....domain.transactions.enums import BusinessClassification

    _import_corpus(invoke_cli=invoke_cli)
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
        invoke_cli=invoke_cli,
    )
    assert result.exit_code == 0, result.output
    txn = load_active_catalogue().get(tx)
    assert txn is not None
    assert txn.business_classification is BusinessClassification.BUSINESS
    assert txn.iva_category == IvaCategory("intra_community_supply")
    assert txn.counterparty_country == "DE"
    # The Member State is derived from registry data, so it is read under a lease.
    with bundled_indexed_authority().operation():
        assert txn.counterparty_eu_member_state == EUMemberState.from_registry("de")


def test_allocate_records_business_proportion(invoke_cli: Callable[..., Result]) -> None:
    from decimal import Decimal

    from ....domain.transactions.enums import BusinessClassification

    _import_bbva(invoke_cli=invoke_cli)
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
        invoke_cli=invoke_cli,
    )
    assert result.exit_code == 0, result.output
    txn = load_active_catalogue().get(tx)
    assert txn is not None
    assert txn.business_classification is BusinessClassification.MIXED
    assert txn.business_pct == Decimal("0.30")
    assert txn.category_id == "suministros_home_office_internet"


def test_ratios_eligible_set_list_validate(invoke_cli: Callable[..., Result]) -> None:
    _import_bbva(invoke_cli=invoke_cli)
    eligible = _invoke(["--format", "json", "app", "ledger", "ratios", "eligible"], invoke_cli=invoke_cli)
    assert eligible.exit_code == 0, eligible.output
    blob = json.dumps(json.loads(eligible.output))
    category = "telefonia_movil" if "telefonia_movil" in blob else "vehiculo_combustible"
    setr = _invoke(["app", "ledger", "ratios", "set", category, "0.50"], invoke_cli=invoke_cli)
    assert setr.exit_code == 0, setr.output
    listed = _invoke(["app", "ledger", "ratios", "list"], invoke_cli=invoke_cli)
    assert listed.exit_code == 0 and category in listed.output, listed.output
    validate = _invoke(["app", "ledger", "ratios", "validate"], invoke_cli=invoke_cli)
    assert validate.exit_code == 0, validate.output


def test_transfer_row_reclassified_to_internal_transfer_and_locked_out_of_tax(
    invoke_cli: Callable[..., Result],
) -> None:
    _import_bbva(invoke_cli=invoke_cli)
    rows = _list_rows()
    transfer = _find(rows, "Transferencia a cuenta personal CaixaBank")
    tx = transfer["transaction_id"]
    assert transfer["direction"] == "OUTGOING"
    assert transfer["business_classification"] == "NOT_YET_PROCESSED"

    reclass = _invoke(["app", "ledger", "update", tx, "--direction", "INTERNAL_TRANSFER"], invoke_cli=invoke_cli)
    assert reclass.exit_code == 0, reclass.output
    after = {row["transaction_id"]: row for row in _list_rows()}[tx]
    assert after["direction"] == "INTERNAL_TRANSFER"

    refused = _invoke(["app", "ledger", "update", tx, "--classification", "BUSINESS"], invoke_cli=invoke_cli)
    assert refused.exit_code != 0, refused.output
    assert after["business_classification"] != "BUSINESS"
