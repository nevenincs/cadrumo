from __future__ import annotations

from typing import Any

import pytest

from ._ledger_corpus_support import (
    _find,
    _import_bbva,
    _import_corpus,
    _invoke,
    _list_payload,
    _list_rows,
    _set_group,
)
from ._ledger_corpus_support import _isolated_backend as _isolated_backend

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_review_renders_corpus() -> None:
    _import_corpus()
    result = _invoke(["app", "ledger", "review"])
    assert result.exit_code == 0, result.output


def test_operator_can_filter_income_vs_expense() -> None:
    _import_corpus()
    rows = _list_rows()
    incoming = [row for row in rows if row.get("direction") == "INCOMING"]
    outgoing = [row for row in rows if row.get("direction") == "OUTGOING"]
    assert incoming and outgoing, (len(incoming), len(outgoing))
    assert all(row.get("business_classification") == "NOT_YET_PROCESSED" for row in rows)
    transfer_candidates = [
        row
        for row in rows
        if any(token in row["description"] for token in ("Transferencia", "Traspaso", "Top-Up", "Exchange"))
    ]
    assert transfer_candidates, "corpus must carry transfer candidates to reclassify"


def test_status_reports_active_ledger() -> None:
    _import_corpus()
    result = _invoke(["app", "ledger", "status"])
    assert result.exit_code == 0, result.output


def test_review_filter_by_period_and_status() -> None:
    _import_bbva()
    by_period = _invoke(["app", "ledger", "review", "--filter", "period=1T", "--filter", "year=2025"])
    assert by_period.exit_code == 0, by_period.output
    by_status = _invoke(["app", "ledger", "review", "--filter", "status=pending"])
    assert by_status.exit_code == 0, by_status.output


def test_preflight_and_check_surface_missing_facts() -> None:
    _import_bbva()
    preflight = _invoke(["app", "ledger", "preflight", "--period", "1T", "--year", "2025"])
    assert preflight.exit_code == 0, preflight.output
    check = _invoke(["app", "ledger", "check"])
    assert check.exit_code == 0, check.output


def test_list_paging_is_honest_and_never_silently_caps() -> None:
    _import_bbva()
    full = _list_payload()
    total = full["total"]
    assert total > 20, "fixture should carry enough rows to page"
    assert full["truncated"] is False
    assert full["shown"] == total
    assert len(full["rows"]) == total

    page = _list_payload("--limit", "10")
    assert page["total"] == total
    assert page["shown"] == 10
    assert len(page["rows"]) == 10
    assert page["truncated"] is True
    assert page["rows"] == full["rows"][:10]

    nxt = _list_payload("--limit", "10", "--offset", "10")
    assert nxt["offset"] == 10
    assert nxt["rows"] == full["rows"][10:20]
    assert nxt["truncated"] is True

    seen: list[dict[str, Any]] = []
    off = 0
    while off < total:
        win = _list_payload("--limit", "25", "--offset", str(off))
        seen.extend(win["rows"])
        off += 25
    assert seen == full["rows"]

    last_off = (total // 25) * 25
    tail = _list_payload("--limit", "25", "--offset", str(last_off))
    assert tail["shown"] == total - last_off


def test_list_truncation_footer_states_the_full_total() -> None:
    _import_bbva()
    total = _list_payload()["total"]
    listed = _invoke(["app", "ledger", "list", "--limit", "5"])
    assert listed.exit_code == 0, listed.output
    assert str(total) in listed.output
    assert "1-5" in listed.output


def test_group_label_assign_filter_and_grouped_display() -> None:
    _import_bbva()
    rows = _list_rows()
    a = _find(rows, "Material oficina Papeleria Gomez")
    b = _find(rows, "Comida de trabajo Restaurante El Olivo")
    _set_group(a["transaction_id"], "Proyecto Acme")
    _set_group(b["transaction_id"], "Proyecto Acme")

    filtered = _list_payload("--group", "Proyecto Acme")
    ids = {row["transaction_id"] for row in filtered["rows"]}
    assert ids == {a["transaction_id"], b["transaction_id"]}
    assert all(row["group_label"] == "Proyecto Acme" for row in filtered["rows"])

    full = _list_payload()
    labels = {row["group_label"] for row in full["rows"]}
    assert "Proyecto Acme" in labels and None in labels

    grouped = _invoke(["app", "ledger", "list", "--by-group"])
    assert grouped.exit_code == 0, grouped.output
    assert "# Proyecto Acme" in grouped.output


def test_unrelated_update_preserves_group_label() -> None:
    _import_bbva()
    rows = _list_rows()
    row = _find(rows, "Material oficina Papeleria Gomez")
    _set_group(row["transaction_id"], "Q1 viajes")

    res = _invoke(["app", "ledger", "update", row["transaction_id"], "--notes", "revisado"])
    assert res.exit_code == 0, res.output
    after = {listed["transaction_id"]: listed for listed in _list_rows()}[row["transaction_id"]]
    assert after["group_label"] == "Q1 viajes"

    cleared = _invoke(["app", "ledger", "update", row["transaction_id"], "--group", ""])
    assert cleared.exit_code == 0, cleared.output
    final = {listed["transaction_id"]: listed for listed in _list_rows()}[row["transaction_id"]]
    assert final["group_label"] is None
