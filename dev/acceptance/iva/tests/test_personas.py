"""The IVA persona oracle is internally consistent, matches the AEAT worked example and cites real texts."""

from __future__ import annotations

import ast
import itertools
import re
import sys
import tomllib
from dataclasses import fields
from decimal import Decimal
from functools import cache
from pathlib import Path

import pdfplumber
import pytest

from .. import personas
from ..personas import (
    FIGURE_CITATIONS,
    PERSONA_A_QUARTERS,
    PRIOR_YEAR,
    LastPeriodElection,
    Modelo303Quarter,
    Modelo390Year,
    QuarterCuotas,
    cuota_from_base,
    persona_a_outcome,
    persona_a_override_amounts,
    persona_b_expectation,
    run_year,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_DATA = Path(__file__).resolve().parents[4] / "src" / "cadrumo" / "_data"
_LEGAL_TABLES = _DATA / "registry" / "aeat" / "legal"


def _d(text: str) -> Decimal:
    return Decimal(text)


@cache
def _registry_tables() -> dict[str, dict[str, dict[str, object]]]:
    merged: dict[str, dict[str, dict[str, object]]] = {"legal": {}, "sources": {}}
    for path in sorted(_LEGAL_TABLES.glob("*.toml")):
        with path.open("rb") as handle:
            document = tomllib.load(handle)
        for table in merged:
            merged[table].update(document.get(table, {}))
    return merged


def _normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text)


@cache
def _corpus_text(relative: str) -> str:
    path = _DATA / relative
    extracted = path.with_name(path.name + ".extracted.md")
    if extracted.is_file():
        return _normalized(extracted.read_text(encoding="utf-8"))
    with pdfplumber.open(path) as pdf:
        return _normalized(" ".join(page.extract_text() or "" for page in pdf.pages))


def _all_citations() -> list[personas.Citation]:
    seen: dict[tuple[str, str, str], personas.Citation] = {}
    for citations in FIGURE_CITATIONS.values():
        for citation in citations:
            seen[(citation.source_id, citation.locator, citation.quote)] = citation
    return list(seen.values())


# ---- relations every quarter must satisfy, whatever the inputs -------------------------------------------------


def _check_quarter_relations(row: Modelo303Quarter) -> None:
    assert row.box_46 == row.box_27 - row.box_45
    assert row.box_64 == row.box_46
    assert row.box_87 == row.box_110 - row.box_78
    assert row.box_69 == row.box_64 - row.box_78
    assert Decimal(0) <= row.box_78 <= row.box_110
    assert row.box_78 <= max(row.box_64, Decimal(0))
    # The maximum is applied: either the whole positive result or the whole balance.
    assert row.box_78 == min(row.box_110, max(row.box_64, Decimal(0)))


def test_persona_a_quarters_satisfy_the_printed_relations() -> None:
    outcome = persona_a_outcome()
    assert tuple(row.quarter for row in outcome.quarters) == tuple(q.quarter for q in PERSONA_A_QUARTERS)
    for row in outcome.quarters:
        _check_quarter_relations(row)


def test_persona_a_balance_flows_from_quarter_to_quarter() -> None:
    rows = persona_a_outcome().quarters
    assert rows[0].box_110 == Decimal(0)
    for previous, current in itertools.pairwise(rows):
        generated = max(-previous.box_69, Decimal(0))
        assert current.box_110 == previous.box_87 + generated
        assert previous.credit_at_end == previous.box_87 + generated


def test_persona_a_credit_is_conserved() -> None:
    outcome = persona_a_outcome()
    generated = sum((lot.generated for lot in outcome.wallet), Decimal(0))
    applied = sum((row.box_78 for row in outcome.quarters), Decimal(0))
    assert outcome.quarters[-1].credit_at_end == generated - applied
    assert outcome.quarters[-1].credit_at_end == sum((lot.remaining for lot in outcome.wallet), Decimal(0))


def test_persona_a_hand_derived_chain() -> None:
    # Hand arithmetic from the persona invoices at 21 %: devengada 210, 315, 420, 210 and deducible 630, 105,
    # 105, 420. The first quarter ends 420 in credit; the second applies 210 and leaves 210; the third applies
    # the remaining 210 against a result of 315 and pays 105; the fourth ends 210 in credit.
    rows = persona_a_outcome().quarters
    assert [row.credit_at_end for row in rows] == [_d("420.00"), _d("210.00"), _d("0.00"), _d("210.00")]
    assert [row.box_69 for row in rows] == [_d("-420.00"), _d("0.00"), _d("105.00"), _d("-210.00")]


def test_persona_a_override_amounts_are_the_balances_entering_the_carried_quarters() -> None:
    amounts = persona_a_override_amounts()
    assert amounts == {"2T": _d("420.00"), "3T": _d("210.00")}


def test_persona_a_annual_summary_follows_the_printed_identities() -> None:
    outcome = persona_a_outcome()
    annual = outcome.annual
    assert annual.box_47 == sum((row.box_27 for row in outcome.quarters), Decimal(0))
    assert annual.box_64 == sum((row.box_45 for row in outcome.quarters), Decimal(0))
    assert annual.box_65 == annual.box_47 - annual.box_64
    assert annual.box_84 == annual.box_65
    assert annual.box_86 == annual.box_84 - annual.box_85
    # The year's periodic results add up to the annual result once what the wallet applied is put back.
    assert annual.box_65 == sum((row.box_69 + row.box_78 for row in outcome.quarters), Decimal(0))
    assert annual.box_95 == _d("105.00")
    assert annual.box_97 == _d("210.00")
    assert annual.box_98 == _d("0.00")
    # Nothing came from a previous year, and the first-quarter credit was fully applied inside the year.
    assert annual.box_85 == _d("0.00")
    assert annual.box_662 == _d("0.00")


def test_persona_a_wallet_after_the_last_quarter_is_one_open_lot() -> None:
    wallet = persona_a_outcome().wallet
    assert [(lot.origin, lot.generated, lot.remaining) for lot in wallet] == [
        ("1T", _d("420.00"), _d("0.00")),
        ("4T", _d("210.00"), _d("210.00")),
    ]
    assert wallet[0].applied == (("2T", _d("210.00")), ("3T", _d("210.00")))


def test_refund_election_leaves_no_last_quarter_balance() -> None:
    cuotas = tuple(QuarterCuotas(q.quarter, q.cuota_devengada, q.cuota_deducible) for q in PERSONA_A_QUARTERS)
    refunded = run_year(cuotas, last_period_election=LastPeriodElection.DEVOLVER)
    assert refunded.annual.box_97 == _d("0.00")
    assert refunded.annual.box_98 == _d("210.00")
    assert [lot.origin for lot in refunded.wallet] == ["1T"]
    assert refunded.quarters[-1].credit_at_end == _d("0.00")


def test_prior_year_credit_is_reported_in_casilla_85_and_not_in_662() -> None:
    outcome = run_year(
        (QuarterCuotas("1T", _d("100.00"), _d("0.00")), QuarterCuotas("2T", _d("0.00"), _d("40.00"))),
        opening_prior_year_credit=_d("30.00"),
    )
    assert outcome.quarters[0].box_110 == _d("30.00")
    assert outcome.quarters[0].box_78 == _d("30.00")
    assert outcome.annual.box_85 == _d("30.00")
    assert outcome.annual.box_662 == _d("0.00")
    assert outcome.annual.box_86 == outcome.annual.box_84 - _d("30.00")
    assert [lot.origin for lot in outcome.wallet] == [PRIOR_YEAR, "2T"]


def test_oldest_lot_is_consumed_first() -> None:
    outcome = run_year(
        (
            QuarterCuotas("1T", _d("0.00"), _d("100.00")),
            QuarterCuotas("2T", _d("0.00"), _d("50.00")),
            QuarterCuotas("3T", _d("120.00"), _d("0.00")),
        )
    )
    first, second = outcome.wallet
    assert (first.origin, first.remaining) == ("1T", _d("0.00"))
    assert (second.origin, second.remaining) == ("2T", _d("30.00"))


# ---- the AEAT Manual practico IVA 2025 worked example (chapter 9, pp. 277-279) -----------------------------------


def test_engine_reproduces_the_aeat_manual_worked_example() -> None:
    outcome = run_year(
        (
            QuarterCuotas("1T", _d("1000"), _d("800")),
            QuarterCuotas("2T", _d("1100"), _d("500")),
            QuarterCuotas("3T", _d("0"), _d("500")),
            QuarterCuotas("4T", _d("0"), _d("200")),
        ),
        opening_prior_year_credit=_d("1000"),
    )
    assert [row.box_110 for row in outcome.quarters] == [_d("1000"), _d("800"), _d("200"), _d("700")]
    assert [row.box_78 for row in outcome.quarters] == [_d("200"), _d("600"), _d("0"), _d("0")]
    assert [row.box_87 for row in outcome.quarters] == [_d("800"), _d("200"), _d("200"), _d("700")]
    # "Al termino del ejercicio el contribuyente dispone de un saldo a compensar de 900".
    assert outcome.quarters[-1].credit_at_end == _d("900")
    assert outcome.annual.box_85 == _d("800")
    assert outcome.annual.box_95 == _d("0")
    assert outcome.annual.box_97 == _d("200")
    assert outcome.annual.box_662 == _d("500")


# ---- persona B ---------------------------------------------------------------------------------------------------


def test_persona_b_fixes_the_sale_and_leaves_the_opening_balance_unknown() -> None:
    expectation = persona_b_expectation()
    assert expectation.box_27 == expectation.sale.base * personas.GENERAL_RATE
    assert expectation.box_45 == Decimal(0)
    assert expectation.box_46 == expectation.box_27
    assert expectation.opening_balance_known is False


# ---- arithmetic guards -------------------------------------------------------------------------------------------


def test_cuota_refuses_a_base_whose_cuota_is_not_whole_cents() -> None:
    assert cuota_from_base(_d("1000.00")) == _d("210.00")
    with pytest.raises(ValueError, match="whole number of cents"):
        cuota_from_base(_d("0.01"))


# ---- citations ---------------------------------------------------------------------------------------------------


def test_every_figure_the_oracle_emits_carries_citations() -> None:
    for field in fields(Modelo303Quarter):
        if field.name.startswith("box_"):
            assert FIGURE_CITATIONS[f"303:{field.name.removeprefix('box_')}"]
    for field in fields(Modelo390Year):
        assert FIGURE_CITATIONS[f"390:{field.name.removeprefix('box_')}"]
    for key in ("303:cuota", "303:credit-at-end", "wallet"):
        assert FIGURE_CITATIONS[key]


def test_every_citation_names_a_source_the_bundled_registry_holds() -> None:
    tables = _registry_tables()
    for citation in _all_citations():
        assert citation.source_id in tables[citation.registry_table], citation.source_id
        assert citation.quote.strip()


def test_every_quote_appears_in_the_bundled_official_text() -> None:
    tables = _registry_tables()
    for citation in _all_citations():
        entry = tables[citation.registry_table][citation.source_id]
        reference = entry.get("corpus_ref") or entry.get("corpus_path")
        assert isinstance(reference, str), citation.source_id
        text = _corpus_text(reference.split("#", 1)[0])
        assert _normalized(citation.quote) in text, (citation.source_id, citation.locator, citation.quote)


# ---- independence ------------------------------------------------------------------------------------------------


def test_personas_module_imports_only_the_standard_library() -> None:
    tree = ast.parse(Path(personas.__file__).read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, "a relative import would reach outside the standard library"
            assert node.module is not None
            imported.add(node.module.split(".")[0])
    assert imported
    assert imported <= set(sys.stdlib_module_names) | {"__future__"}
