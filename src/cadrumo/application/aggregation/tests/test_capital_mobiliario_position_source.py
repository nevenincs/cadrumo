"""A saver's interest and dividends reach their boxes through the real resolver and the published Modelo 100.

The oracles are hand-worked at the 19 per cent rate RIRPF art. 90.1 applies to the
full consideration (art. 93.1). A payer feeding one occurrence has its withholding
read off its record; the gross is the taxpayer's share of the net cash plus that
withholding. Each refusal leaves the boxes it affects open with a blocking note
that names the payer by the name the position states.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal

import pytest

from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.binding_targets import sole_bound_casilla
from ....domain.calculations.registry.capital_mobiliario_position_bindings import (
    capital_mobiliario_position_bindings,
)
from ....domain.calculations.registry.tests.authored_editions import supported_exercises_with_projection
from ....domain.modelos.calculation_revision_sources import CalculationNoteSentence
from ....domain.transactions.enums import TransactionDirection
from ..source_mesh import CalculationSourceResolution
from .capital_mobiliario_position_support import (
    BROKER_PAYER,
    DEPOSIT,
    DEPOSIT_PAYER,
    DEPOSIT_POSITION,
    DIVIDENDS,
    EXPENSES,
    INTEREST,
    SHARES,
    YEAR,
    SavingsPosition,
    linked_row,
    payer_record,
    resolve_savings,
    savings_boxes,
)
from .ledger_source_mesh_support import m100_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture(autouse=True)
def _pinned_authority() -> Iterator[None]:
    with bundled_indexed_authority().operation():
        yield


def _notes(resolution: CalculationSourceResolution) -> dict[str, set[CalculationNoteSentence]]:
    notes: dict[str, set[CalculationNoteSentence]] = {}
    for item in resolution.diagnostics:
        assert item.reason == "unresolved_binding"
        assert item.fact is not None
        notes.setdefault(str(item.casilla_id), set()).add(item.fact.sentence)
    return notes


def _note_values(resolution: CalculationSourceResolution) -> set[tuple[tuple[str, str], ...]]:
    return {item.fact.values for item in resolution.diagnostics if item.fact is not None}


@pytest.mark.parametrize("year", supported_exercises_with_projection("100"))
def test_every_supported_year_binds_interest_dividends_and_expenses(year: int) -> None:
    revision = m100_revision(year)

    bound = {
        str(sole_bound_casilla(revision, binding.id)): provider.quantity.value
        for binding, provider in capital_mobiliario_position_bindings(revision)
        if provider.dictionary_field is None
    }

    assert bound == {INTEREST: "gross", DIVIDENDS: "gross", EXPENSES: "expenses"}


def test_no_linked_row_is_a_proven_zero_in_every_box() -> None:
    resolution = resolve_savings(())

    assert savings_boxes(resolution) == {INTEREST: Decimal(0), DIVIDENDS: Decimal(0), EXPENSES: Decimal(0)}
    assert resolution.unresolved_binding_ids == ()
    assert resolution.diagnostics == ()


def test_deposit_interest_rebuilds_the_gross_from_the_certified_withholding() -> None:
    rows = (linked_row("i1", DEPOSIT, "intereses", "200.00"), linked_row("i2", DEPOSIT, "intereses", "124.00"))

    resolution = resolve_savings(rows, records=(payer_record(DEPOSIT_PAYER, integro="400.00", retencion="76.00"),))

    assert savings_boxes(resolution) == {INTEREST: Decimal("400.00"), DIVIDENDS: Decimal(0), EXPENSES: Decimal(0)}
    assert resolution.unresolved_binding_ids == ()
    assert set(resolution.source_transaction_ids) == {str(row.transaction_id) for row in rows}


def test_cent_interest_keeps_the_certified_cents() -> None:
    rows = (linked_row("i1", DEPOSIT, "intereses", "29.97"),)

    resolution = resolve_savings(rows, records=(payer_record(DEPOSIT_PAYER, integro="37.00", retencion="7.03"),))

    assert savings_boxes(resolution)[INTEREST] == Decimal("37.00")


def test_dividends_with_custody_expense_fill_the_dividend_and_expense_boxes() -> None:
    rows = (
        linked_row("d1", SHARES, "dividendos", "1216.62"),
        linked_row("g1", SHARES, "gasto_administracion_deposito", "90.00", direction=TransactionDirection.OUTGOING),
    )

    resolution = resolve_savings(rows, records=(payer_record(BROKER_PAYER, integro="1502.00", retencion="285.38"),))

    assert savings_boxes(resolution) == {
        INTEREST: Decimal(0),
        DIVIDENDS: Decimal("1502.00"),
        EXPENSES: Decimal("90.00"),
    }


def test_one_payer_on_two_positions_splits_by_the_governed_rate() -> None:
    positions = {
        DEPOSIT: DEPOSIT_POSITION,
        SHARES: SavingsPosition("valores_negociables", DEPOSIT_PAYER, "Banco Sintetico"),
    }
    rows = (linked_row("i1", DEPOSIT, "intereses", "324.00"), linked_row("d1", SHARES, "dividendos", "810.00"))

    resolution = resolve_savings(
        rows, positions=positions, records=(payer_record(DEPOSIT_PAYER, integro="1400.00", retencion="266.00"),)
    )

    assert savings_boxes(resolution) == {
        INTEREST: Decimal("400.00"),
        DIVIDENDS: Decimal("1000.00"),
        EXPENSES: Decimal(0),
    }


def test_a_half_share_takes_half_the_cash_and_half_the_expense() -> None:
    positions = {SHARES: SavingsPosition("valores_negociables", BROKER_PAYER, "Broker Sintetico", share="50")}
    rows = (
        linked_row("d1", SHARES, "dividendos", "1620.00"),
        linked_row("g1", SHARES, "gasto_administracion_deposito", "30.00", direction=TransactionDirection.OUTGOING),
    )

    resolution = resolve_savings(
        rows, positions=positions, records=(payer_record(BROKER_PAYER, integro="1000.00", retencion="190.00"),)
    )

    assert savings_boxes(resolution) == {
        INTEREST: Decimal(0),
        DIVIDENDS: Decimal("1000.00"),
        EXPENSES: Decimal("15.00"),
    }


def test_an_attested_absence_takes_the_net_cash_as_gross() -> None:
    resolution = resolve_savings((linked_row("i1", DEPOSIT, "intereses", "12.40"),), attested=True)

    assert savings_boxes(resolution)[INTEREST] == Decimal("12.40")
    assert resolution.unresolved_binding_ids == ()


def test_rows_without_payer_evidence_leave_their_box_open() -> None:
    resolution = resolve_savings((linked_row("i1", DEPOSIT, "intereses", "324.00"),))

    boxes = savings_boxes(resolution)
    assert boxes[INTEREST] is None
    assert boxes[DIVIDENDS] == Decimal(0)
    assert _notes(resolution)[INTEREST] == {CalculationNoteSentence.CAPITAL_MOBILIARIO_PAYER_EVIDENCE_MISSING}
    assert EXPENSES in _notes(resolution)
    assert (("payer", "Banco Sintetico"),) in _note_values(resolution)


def test_a_certificate_that_disagrees_with_the_rows_names_both_figures() -> None:
    resolution = resolve_savings(
        (linked_row("i1", DEPOSIT, "intereses", "324.00"),),
        records=(payer_record(DEPOSIT_PAYER, integro="410.00", retencion="76.00"),),
    )

    assert savings_boxes(resolution)[INTEREST] is None
    assert _notes(resolution)[INTEREST] == {CalculationNoteSentence.CAPITAL_MOBILIARIO_PAYER_CHECK_MISMATCH}
    assert (("amount", "400.00"), ("compared_amount", "410.00"), ("payer", "Banco Sintetico")) in _note_values(
        resolution
    )


def test_a_foreign_position_is_not_computed() -> None:
    positions = {DEPOSIT: SavingsPosition("deposito", DEPOSIT_PAYER, "Banco Sintetico", country="PT")}

    resolution = resolve_savings(
        (linked_row("i1", DEPOSIT, "intereses", "324.00"),), positions=positions, attested=True
    )

    assert savings_boxes(resolution)[INTEREST] is None
    assert _notes(resolution)[INTEREST] == {CalculationNoteSentence.CAPITAL_MOBILIARIO_FOREIGN_SOURCE}


def test_a_row_dated_before_the_position_is_held_leaves_every_box_open() -> None:
    positions = {DEPOSIT: SavingsPosition("deposito", DEPOSIT_PAYER, "Banco Sintetico", since=date(YEAR, 9, 1))}

    resolution = resolve_savings(
        (linked_row("i1", DEPOSIT, "intereses", "324.00"),), positions=positions, attested=True
    )

    assert set(savings_boxes(resolution).values()) == {None}
    assert {sentence for notes in _notes(resolution).values() for sentence in notes} == {
        CalculationNoteSentence.CAPITAL_MOBILIARIO_POSITION_NOT_HELD
    }


def test_a_custody_expense_on_a_deposit_is_not_readable() -> None:
    resolution = resolve_savings(
        (linked_row("g1", DEPOSIT, "gasto_administracion_deposito", "9.00", direction=TransactionDirection.OUTGOING),),
        attested=True,
    )

    assert savings_boxes(resolution)[INTEREST] is None
    assert _notes(resolution)[INTEREST] == {CalculationNoteSentence.CAPITAL_MOBILIARIO_ROW_NOT_READABLE}


def test_a_payer_record_no_linked_row_shows_leaves_every_box_open() -> None:
    resolution = resolve_savings((), records=(payer_record(DEPOSIT_PAYER, integro="400.00", retencion="76.00"),))

    assert set(savings_boxes(resolution).values()) == {None}
    assert {sentence for notes in _notes(resolution).values() for sentence in notes} == {
        CalculationNoteSentence.CAPITAL_MOBILIARIO_PAYER_WITHOUT_ROWS
    }


def test_income_in_kind_leaves_its_payers_box_open() -> None:
    resolution = resolve_savings(
        (linked_row("i1", DEPOSIT, "intereses", "324.00"),),
        records=(payer_record(DEPOSIT_PAYER, integro="400.00", retencion="76.00", especie="50.00"),),
    )

    assert savings_boxes(resolution)[INTEREST] is None
    assert _notes(resolution)[INTEREST] == {CalculationNoteSentence.CAPITAL_MOBILIARIO_INCOME_IN_KIND}
