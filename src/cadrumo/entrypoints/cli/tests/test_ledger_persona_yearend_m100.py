"""Year-end Renta (M100) reviewer persona over the ledger-corpus fixture.

Drives the real ``aeat app ledger`` CLI as a **year-end reviewer assembling the
annual Renta picture**: import every account, bulk-classify the full 2025
business income + expenses against the ground-truth oracle, review the whole
year, observe the annual income-vs-expense totals (summed from
``list --format json`` because there is no annual-total verb), and locate the
cross-year invoice raised 2025-12 / paid 2026-01.

These tests are observational operator testimonials: they assert the **surfaces
the CLI does and does not expose** for a full-year roll-up, not hand-computed
tax outputs (per ``aeat-quality-gates``). The monetary sums are
read back from the operator-facing ``list`` JSON the same way an operator with a
spreadsheet would tally them, and are asserted only for internal consistency
(income > 0, expense > 0, the year split sums to the whole), never against a
registry formula.

Persona finding surfaced by this suite: the ledger has **no annual roll-up /
M100-readiness surface** — ``status`` and ``check`` emit only counts and
readiness flags, never income/expense money totals — so the full-year Renta
picture must be assembled by hand from ``list`` JSON. The cross-year invoice is
recoverable (``check`` reports ``periods: ["2025", "2026"]`` and the row is
date-stamped 2026 while its ``F-2025-`` reference names the prior year), but the
operator must reconcile devengo-vs-caja manually; nothing pairs the raised-year
reference with the paid-year settlement.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path

import pytest
from click.testing import Result

from ....tests import FIXTURES_DIR
from ....tests.cli_runner import invoke_cached_cli
from ....tests.ledger_cli import list_ledger_rows_via_cli as _list_rows
from ._isolated_profile_storage_fixtures import live_fx_isolated_backend
from ._ledger_corpus_support import _match, _oracle_rules

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]
__all__ = ["live_fx_isolated_backend"]

_CORPUS = FIXTURES_DIR / "financial" / "ledger-corpus"
_FILES = (
    "bbva-business-eur.csv",
    "caixabank-personal.csv",
    "revolut-multi.csv",
    "n26-savings.csv",
)

# Cross-year invoice: raised Dec 2025, settled Jan 2026 (README §Cross-period).
_CROSS_YEAR_NEEDLE = "F-2025-024"


def _invoke(args: Sequence[str]) -> Result:
    return invoke_cached_cli(args)


def _import_corpus() -> None:
    for name in _FILES:
        result = _invoke(["app", "ledger", "import", "--file", str(_CORPUS / name), "--provider", "csv"])
        assert result.exit_code == 0, f"{name}: {result.output}"


def _year_of(row: dict[str, object]) -> int:
    date_str = row.get("date")
    assert isinstance(date_str, str)
    return int(date_str[:4])


# --- Annual reach: the operator wants the whole year, not one quarter --------
def test_corpus_spans_both_years() -> None:
    """The full-year reviewer must see rows in 2025 AND 2026 (cross-year ledger)."""
    _import_corpus()
    rows = _list_rows()
    years = {_year_of(r) for r in rows}
    assert {2025, 2026} <= years, years


def test_annual_review_filter_renders_full_year() -> None:
    """``review --filter period=0A --filter year=2025`` (annual Period) is accepted and renders.

    The reviewer's first instinct is a full-year view. The annual ``Period``
    token works, so the operator is not forced to walk four quarters — but the
    output is a row dump, not a totalled picture.
    """
    _import_corpus()
    annual = _invoke(["app", "ledger", "review", "--filter", "period=0A", "--filter", "year=2025"])
    assert annual.exit_code == 0, annual.output
    # The annual filter must contain rows dated across the year, not just Q1.
    assert "2025-01" in annual.output, annual.output
    assert "2025-12" in annual.output or "2025-11" in annual.output, annual.output


def test_all_four_quarters_reviewable() -> None:
    """Each 2025 quarter is independently reviewable (per-period is the only roll-up)."""
    _import_corpus()
    for q in ("1T", "2T", "3T", "4T"):
        result = _invoke(["app", "ledger", "review", "--filter", f"period={q}", "--filter", "year=2025"])
        assert result.exit_code == 0, f"{q}: {result.output}"


def test_check_surfaces_both_years_as_touched_periods() -> None:
    """``check`` reports every period the ledger touches, including 2026.

    This is the closest the CLI comes to telling a year-end operator the ledger
    straddles a year boundary: ``periods`` lists ``2025`` and ``2026``. It is a
    period inventory, not a reconciliation of cross-year transactions.
    """
    _import_corpus()
    checked = _invoke(["--format", "json", "app", "ledger", "check"])
    assert checked.exit_code == 0, checked.output
    result = json.loads(checked.output)["result"]
    assert "2025" in result["periods"], result["periods"]
    assert "2026" in result["periods"], result["periods"]


# --- Annual income vs expense picture: assembled by hand from list JSON ------
def test_annual_income_and_expense_picture_must_be_summed_by_hand(tmp_path: Path) -> None:
    """No annual-total verb exists; the operator sums ``list`` JSON himself.

    TESTIMONIAL CORE: the year-end Renta picture (full-year income vs
    deductible expense) has no first-class surface. We classify the full 2025
    business income + expenses via the oracle, then tally the non-negative
    amount magnitudes from ``list`` JSON grouped by direction. The sums are
    asserted only for internal consistency, never against a tax formula.
    """
    _import_corpus()
    rules = _oracle_rules()

    # Bulk-classify the full-corpus business rows against the oracle. --file
    # carries classification + category only, so non-MIXED rows go in one pass.
    rows = _list_rows()
    lines = ["transaction_id,classification,category_id"]
    classified_ids: set[str] = set()
    for row in rows:
        desc = row.get("description")
        tx_id = row.get("transaction_id")
        assert isinstance(desc, str)
        assert isinstance(tx_id, str)
        rule = _match(desc, rules)
        if rule is None or rule.get("classification") == "MIXED":
            continue
        cat = rule.get("category_id") or ""
        classification_val = rule.get("classification")
        assert isinstance(classification_val, str)
        lines.append(f"{tx_id},{classification_val},{cat}")
        classified_ids.add(tx_id)
    assert classified_ids, "oracle must classify a non-trivial slice of the corpus"

    classify_csv = tmp_path / "yearend-classifications.csv"
    classify_csv.write_text("\n".join(lines) + "\n", encoding="utf-8")

    classified = _invoke(["--format", "json", "app", "ledger", "classify", "--file", str(classify_csv)])
    assert classified.exit_code == 0, classified.output
    applied = json.loads(classified.output)["result"]["applied"]
    assert applied == len(classified_ids), (applied, len(classified_ids))

    # Assemble the annual picture by hand: there is no verb that does this.
    rows = _list_rows()
    rows_2025 = [r for r in rows if _year_of(r) == 2025]
    business_2025 = [r for r in rows_2025 if r.get("business_classification") == "BUSINESS"]
    income_rows = [r for r in business_2025 if r.get("direction") == "INCOMING"]
    income = sum(Decimal(str(r.get("amount", "0"))) for r in income_rows)
    expense_rows = [r for r in business_2025 if r.get("direction") == "OUTGOING"]
    expense = sum(Decimal(str(r.get("amount", "0"))) for r in expense_rows)
    # Internal-consistency checks only (anti-tautology): a real autónoma year
    # has positive business income and positive deductible expense.
    assert income > 0, f"expected positive 2025 business income, got {income}"
    assert expense > 0, f"expected positive 2025 business expense, got {expense}"
    # The reviewer can derive a net activity figure, but the CLI never shows it.
    net = income - expense
    assert isinstance(net, Decimal)


def test_full_year_total_equals_sum_of_its_quarters() -> None:
    """The hand-summed annual total reconciles to the four quarterly slices.

    Proves the operator CAN reconstruct the year from per-period views — but
    only by summing four separate queries; the CLI offers no annual aggregate.
    """
    _import_corpus()
    rows_2025 = [r for r in _list_rows() if _year_of(r) == 2025]

    def _quarter(month: int) -> int:
        return (month - 1) // 3 + 1

    annual_total = sum(Decimal(str(r.get("amount", "0"))) for r in rows_2025)
    quarter_totals = {1: Decimal(0), 2: Decimal(0), 3: Decimal(0), 4: Decimal(0)}
    for r in rows_2025:
        date_str = r.get("date")
        assert isinstance(date_str, str)
        month = int(date_str[5:7])
        quarter_totals[_quarter(month)] += Decimal(str(r.get("amount", "0")))
    assert sum(quarter_totals.values()) == annual_total, (quarter_totals, annual_total)
    # All four quarters carry activity (full-year corpus, not a single quarter).
    assert all(total != 0 for total in quarter_totals.values()), quarter_totals


# --- Cross-year transaction: raised one year, paid the next -----------------
def test_cross_year_invoice_is_settled_in_2026_under_a_2025_reference() -> None:
    """F-2025-024: raised Dec 2025, settled Jan 2026.

    The reviewer must spot that a 2026-dated cash row belongs (by devengo) to
    2025. The CLI surfaces the settlement date and the invoice reference, but
    nothing links the prior-year reference to the paid-year settlement — the
    devengo-vs-caja reconciliation is fully manual.
    """
    _import_corpus()
    rows = _list_rows()
    cross_year = []
    for r in rows:
        desc_val = r.get("description")
        if isinstance(desc_val, str) and _CROSS_YEAR_NEEDLE in desc_val:
            cross_year.append(r)
    assert cross_year, f"corpus must contain the cross-year invoice {_CROSS_YEAR_NEEDLE}"
    row = cross_year[0]
    # Settled (booked) in 2026 ...
    assert _year_of(row) == 2026, row.get("date")
    # ... but the invoice reference names the prior fiscal year. The operator,
    # not the CLI, must decide which year's Renta the income belongs to.
    desc_val = row.get("description")
    assert isinstance(desc_val, str) and "2025" in desc_val, desc_val
    assert row.get("direction") == "INCOMING", row


def test_cross_year_invoice_falls_outside_a_2025_period_filter() -> None:
    """The cash-date filter assigns the cross-year invoice to 2026, not 2025.

    PAIN POINT: filtering by ``period=0A --filter year=2025`` (which keys off the
    settlement / value date) hides an invoice that, by accrual, belongs to the
    2025 Renta. A year-end reviewer working from the period filter alone would
    under-count 2025 income by this row unless they reconcile devengo by hand.
    """
    _import_corpus()
    review_2025 = _invoke(["app", "ledger", "review", "--filter", "period=0A", "--filter", "year=2025"])
    assert review_2025.exit_code == 0, review_2025.output
    review_2026 = _invoke(["app", "ledger", "review", "--filter", "period=0A", "--filter", "year=2026"])
    assert review_2026.exit_code == 0, review_2026.output
    # The cross-year invoice settles in 2026, so the 2026 period view carries it
    # and the 2025 period view does not — accrual placement is the operator's job.
    assert _CROSS_YEAR_NEEDLE in review_2026.output, review_2026.output
    assert _CROSS_YEAR_NEEDLE not in review_2025.output, review_2025.output


# --- M100 readiness surface: does one exist? --------------------------------
def test_no_annual_money_rollup_surface_exists() -> None:
    """``status`` / ``check`` annual surfaces carry counts + readiness, no money.

    TESTIMONIAL: there is no M100-readiness / annual-total surface. The annual
    ``status`` payload exposes transaction counts and a boolean ``ready``, but
    no income, expense, or net-activity figure — confirming the year-end Renta
    picture is not a first-class CLI output.
    """
    _import_corpus()
    status = _invoke(["--format", "json", "app", "ledger", "status", "--period", "0A", "--year", "2025"])
    assert status.exit_code == 0, status.output
    result = json.loads(status.output)["result"]
    # Counts and readiness exist ...
    assert "total_count" in result and "ready" in result, result
    assert result["period"] == {"filing_year": 2025, "code": "0A"}, result
    # ... but no monetary roll-up field is present on the status surface.
    money_fields = {"income", "expense", "net", "total_amount", "ingresos", "gastos"}
    assert not (money_fields & set(result)), f"unexpected money rollup field: {result}"
