"""Which movement settles which invoice: the flow, currency and amount a link needs, and the ranking.

Every expected value is worked out by hand from the rule as written, not read back from a run. The
scenarios the window's stand-in is asked about are run through the live rule at the end.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Final, cast

import pytest

from ...calculations.registry.authority import bundled_indexed_authority
from ...transactions.classification_effects import takes_changes, takes_invoice
from ...transactions.enums import TransactionDirection, TransactionLifecycleState
from ...transactions.models import Transaction, TransactionCatalogue
from ..catalogue import InvoiceCatalogue
from ..payment_matching import (
    EARLY_RANK_GAP_DAYS,
    PICK_HORIZON_DAYS,
    PaymentSuggestion,
    can_take_invoice,
    invoice_choices,
    link_differences,
    movement_choices,
    suggest_payments,
)
from ..service import (
    INVOICE_MATCH_TOLERANCE,
    counterparties_overlap,
    invoice_settlement,
    suggest_reconciliations,
)
from .payment_matching_support import build_invoice, build_movement, day, movement_names, recorded_scenario

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_QUESTIONS: Final = (
    Path(__file__).resolve().parents[5] / "dev/fixtures/ledger-recording-questions/ledgerInvoiceMatch.json"
)


@pytest.fixture(autouse=True)
def _authority_operation() -> Iterator[None]:
    with bundled_indexed_authority().operation():
        yield


def _suggested(found: tuple[PaymentSuggestion, ...], names: Mapping[str, str]) -> list[tuple[str, str]]:
    return [(names[one.pair.transaction.transaction_id], one.pair.invoice.invoice_number) for one in found]


def test_a_candidate_settles_the_total_less_its_retencion_on_the_invoices_flow_and_currency_to_the_cent() -> None:
    # 1500.00 + 315.00 IVA = 1815.00, less 225.00 retained: the transfer is 1590.00.
    withheld = build_invoice("F-1", kind="issued", base="1500.00", retention="225.00")
    assert invoice_settlement(withheld) == Decimal("1590.00")
    rows = {
        "paid": build_movement("paid", amount="1590.00", direction="INCOMING"),
        "cent": build_movement("cent", amount="1590.01", direction="INCOMING"),
        "under": build_movement("under", amount="1589.99", direction="INCOMING"),
        "off": build_movement("off", amount="1590.02", direction="INCOMING"),
        "gross": build_movement("gross", amount="1815.00", direction="INCOMING"),
        "wrong_way": build_movement("wrong_way", amount="1590.00", direction="OUTGOING"),
        "foreign": build_movement("foreign", amount="1590.00", direction="INCOMING", currency="USD"),
        "transfer": build_movement("transfer", amount="1590.00", direction="INTERNAL_TRANSFER"),
    }
    pairs = {name for name, row in rows.items() if suggest_payments([row], [withheld])}
    assert pairs == {"paid", "cent", "under"}


def test_the_link_tolerance_is_the_one_the_link_suggestion_uses() -> None:
    assert Decimal("0.01") == INVOICE_MATCH_TOLERANCE


def test_already_linked_invoices_and_movements_are_never_suggested() -> None:
    linked = build_invoice("L-1", linked=("b" * 64,))
    open_one = build_invoice("L-2")
    cites = build_movement("cites", invoice_id="a" * 64)
    free = build_movement("free")
    archived = build_movement("gone", state=TransactionLifecycleState.ARCHIVED)
    found = suggest_payments([cites, free, archived], [linked, open_one])
    assert _suggested(found, movement_names(cites, free, archived)) == [("free", "L-2")]


def test_the_number_in_the_description_outranks_the_gap_the_gap_the_counterparty_the_counterparty_the_amount() -> None:
    row = build_movement("m", on="2026-10-10", description="PAGO FRA PT-0412 TRAZO", counterparty="Otra Empresa")
    numbered = build_invoice("PT-0412", issued="2026-08-01")
    close = build_invoice("PT-0999", issued="2026-10-09", party="Otra Empresa SL")
    found = suggest_payments([row], [close, numbered])
    assert [one.pair.invoice.invoice_number for one in found] == ["PT-0412"]
    best = found[0]
    assert (best.ambiguous, best.pair.number, best.pair.counterparty, best.pair.gap) == (False, True, False, 70)
    assert [other.invoice.invoice_number for other in best.others] == ["PT-0999"]
    assert best.others[0].gap == 1
    assert best.others[0].counterparty is True

    # Without a number the shorter gap wins over the counterparty.
    plain = build_movement("p", on="2026-10-10", counterparty="Papeleria Trazo")
    same_party = build_invoice("A-1", issued="2026-09-01")
    nearer = build_invoice("B-1", issued="2026-10-08", party="Nadie SA")
    assert suggest_payments([plain], [same_party, nearer])[0].pair.invoice.invoice_number == "B-1"

    # With equal numbers and gaps, the counterparty wins over the amount.
    twin_row = build_movement("t", on="2026-10-10", amount="36.30", counterparty="Papeleria Trazo")
    right_party = build_invoice("C-1", issued="2026-10-08")
    other_party = build_invoice("C-2", issued="2026-10-08", party="Nadie SA")
    assert suggest_payments([twin_row], [other_party, right_party])[0].pair.invoice.invoice_number == "C-1"

    # With nothing else apart, the nearer amount wins.
    cents = build_movement("c", on="2026-10-10", amount="36.31")
    exact = build_invoice("D-1", issued="2026-10-08")
    off = build_invoice("D-2", issued="2026-10-08", base="30.01")
    assert off.grand_total == Decimal("36.31") and exact.grand_total == Decimal("36.30")
    assert suggest_payments([cents], [exact, off])[0].pair.invoice.invoice_number == "D-2"


def test_a_payment_up_to_three_days_before_the_invoice_ranks_by_its_gap_and_earlier_ranks_last() -> None:
    assert EARLY_RANK_GAP_DAYS == 3
    row = build_movement("p", on="2026-10-10")
    # Gaps: -3 (ranks 3), -4 (ranks after everything made after issue), +9 (ranks 9).
    three_before = build_invoice("E-3", issued="2026-10-13")
    four_before = build_invoice("E-4", issued="2026-10-14")
    nine_after = build_invoice("E-9", issued="2026-10-01")
    assert suggest_payments([row], [four_before, nine_after])[0].pair.invoice.invoice_number == "E-9"
    assert suggest_payments([row], [nine_after, three_before])[0].pair.invoice.invoice_number == "E-3"
    assert suggest_payments([row], [four_before, three_before])[0].pair.gap == -3


def test_each_invoice_is_offered_one_movement_and_each_movement_gets_one_invoice() -> None:
    first = build_movement("first", on="2026-10-03", counterparty="Papeleria Trazo")
    second = build_movement("second", on="2026-10-20", counterparty="Papeleria Trazo")
    only = build_invoice("ONE-1", issued="2026-10-02")
    found = suggest_payments([first, second], [only])
    assert _suggested(found, movement_names(first, second)) == [("first", "ONE-1")]
    assert [other.invoice.invoice_number for other in found[0].others] == []


def test_equal_candidates_are_ambiguous_tied_invoices_for_one_movement_and_tied_movements_for_one_invoice() -> None:
    row = build_movement("row", on="2026-10-06", counterparty="Arroyo")
    left = build_invoice("AA-118", party="Arroyo Asesores")
    right = build_invoice("AA-119", party="Arroyo Asesores")
    found = suggest_payments([row], [left, right])
    assert [one.ambiguous for one in found] == [True]
    # Equal ranks fall to the lower invoice_id; the other candidate is the tie.
    lower, higher = sorted((left, right), key=lambda invoice: invoice.invoice_id)
    assert found[0].pair.invoice.invoice_number == lower.invoice_number
    assert [tie.invoice.invoice_number for tie in found[0].ties] == [higher.invoice_number]

    a = build_movement("a", on="2026-10-12", direction="INCOMING")
    b = build_movement("b", on="2026-10-12", direction="INCOMING")
    issued = build_invoice("N-5", kind="issued", issued="2026-10-09")
    names = movement_names(a, b)
    both = suggest_payments([a, b], [issued])
    assert sorted(_suggested(both, names)) == [("a", "N-5"), ("b", "N-5")]
    for one in both:
        rival = "b" if names[one.pair.transaction.transaction_id] == "a" else "a"
        assert one.ambiguous is True
        assert [names[tie.transaction.transaction_id] for tie in one.ties] == [rival]


def test_staging_a_link_withdraws_every_suggestion_that_uses_the_same_invoice_or_movement() -> None:
    a = build_movement("a", on="2026-10-12", direction="INCOMING")
    b = build_movement("b", on="2026-10-12", direction="INCOMING")
    issued = build_invoice("N-5", kind="issued", issued="2026-10-09")
    other = build_invoice("N-6", kind="issued", issued="2026-09-01")
    found = suggest_payments([a, b], [issued, other], staged={a.transaction_id: issued.invoice_id})
    # The rival takes the other invoice; the staged one is offered to no one.
    assert _suggested(found, movement_names(a, b)) == [("b", "N-6")]
    assert found[0].others == ()


def test_suggestions_run_newest_movement_first() -> None:
    old = build_movement("old", on="2026-10-02")
    new = build_movement("new", on="2026-10-20", amount="12.10")
    small = build_invoice("S-1", base="10.00")
    big = build_invoice("S-2")
    found = suggest_payments([old, new], [small, big])
    assert _suggested(found, movement_names(old, new)) == [("new", "S-1"), ("old", "S-2")]


def test_a_value_date_is_the_day_a_movement_counts_for() -> None:
    booked = build_movement("v", on="2026-10-02")
    valued = booked.model_copy(update={"raw": booked.raw.model_copy(update={"value_date": date(2026, 10, 9)})})
    assert suggest_payments([valued], [build_invoice("V-1")])[0].pair.gap == 8


def test_the_number_must_be_long_enough_to_tell_from_other_digits() -> None:
    short = build_movement("s", description="PAGO F-12 GRACIAS")
    long = build_movement("l", description="PAGO fra. ab/1234 gracias")
    assert suggest_payments([short], [build_invoice("F-12")])[0].pair.number is False
    assert suggest_payments([long], [build_invoice("AB-1234")])[0].pair.number is True


def test_a_name_inside_the_other_is_the_same_party_as_the_link_suggestion_reads_it() -> None:
    row = build_movement("r", counterparty="PAPELERIA TRAZO")
    invoice = build_invoice("P-1")
    assert suggest_payments([row], [invoice])[0].pair.counterparty is True
    assert suggest_payments([build_movement("q", counterparty="Otra")], [invoice])[0].pair.counterparty is False
    assert suggest_payments([build_movement("n", counterparty=None)], [invoice])[0].pair.counterparty is False


def test_the_picker_sorts_invoices_by_whether_they_settle_and_shows_what_is_staged_or_linked() -> None:
    row = build_movement("row")
    settles_it = build_invoice("S-1", issued="2026-10-04")
    elsewhere = build_invoice("S-2", issued="2026-10-03", linked=("c" * 64,))
    taken_by = build_invoice("S-3", issued="2026-10-02")
    different = build_invoice("O-1", issued="2026-10-05", base="81.82")
    issued = build_invoice("I-1", kind="issued")
    choices = invoice_choices(
        row,
        [settles_it, elsewhere, taken_by, different, issued],
        staged={"d" * 64: taken_by.invoice_id},
    )
    # Newest first; the issued invoice is of the other flow.
    assert [(c.invoice.invoice_number, c.settles) for c in choices] == [
        ("O-1", False),
        ("S-1", True),
        ("S-2", True),
        ("S-3", True),
    ]
    by_number = {choice.invoice.invoice_number: choice for choice in choices}
    assert (by_number["S-2"].linked, by_number["S-3"].staged_for, by_number["S-1"].staged_for) == (1, "d" * 64, None)
    # An invoice staged for this very movement is not shown as taken.
    own = invoice_choices(row, [taken_by], staged={row.transaction_id: taken_by.invoice_id})
    assert own[0].staged_for is None


def test_an_invoice_no_movement_settles_is_offered_the_open_movements_near_its_day() -> None:
    assert PICK_HORIZON_DAYS == 10
    ticket = build_invoice("T-1", issued="2026-10-15", base="48.26")
    assert ticket.grand_total == Decimal("58.39")

    def row(name: str, offset: int, amount: str = "58.39", **facts: Any) -> Transaction:
        return build_movement(name, amount=amount, on=day(offset, date(2026, 10, 15)), **facts)

    near = row("near", 2, "58.40")
    exact = row("exact", PICK_HORIZON_DAYS)
    before = row("before", -9)
    edge_before = row("edge_before", -PICK_HORIZON_DAYS, "20.00")
    far = row("far", 1, "12.00")
    late = row("late", PICK_HORIZON_DAYS + 1)
    early = row("early", -PICK_HORIZON_DAYS - 1)
    income = row("income", 0, direction="INCOMING")
    linked = row("linked", 0, invoice_id="a" * 64)
    staged = row("staged", 0)
    foreign = row("foreign", 0, currency="USD")
    archived = row("archived", 0, state=TransactionLifecycleState.ARCHIVED)
    everything = (near, exact, before, edge_before, far, late, early, income, linked, staged, foreign, archived)
    offered = movement_choices(ticket, everything, staged={staged.transaction_id})
    names = movement_names(*everything)
    # Those that settle come first, the nearer day first among equal amounts; the others by nearest amount.
    assert [(names[c.transaction.transaction_id], c.settles) for c in offered] == [
        ("before", True),
        ("exact", True),
        ("near", True),
        ("edge_before", False),
        ("far", False),
    ]


def test_movements_that_settle_the_same_are_offered_nearest_amount_then_nearest_day() -> None:
    ticket = build_invoice("T-2", issued="2026-10-15", base="48.26")
    exact_far = build_movement("exact_far", amount="58.39", on="2026-10-25")
    cent_near = build_movement("cent_near", amount="58.40", on="2026-10-16")
    exact_near = build_movement("exact_near", amount="58.39", on="2026-10-16")
    names = movement_names(exact_far, cent_near, exact_near)
    offered = movement_choices(ticket, [exact_far, cent_near, exact_near])
    assert [names[c.transaction.transaction_id] for c in offered] == ["exact_near", "exact_far", "cent_near"]


def test_what_the_window_may_offer_is_what_the_link_writer_takes() -> None:
    movement = build_movement("w")
    for state in TransactionLifecycleState:
        for direction in TransactionDirection:
            row = movement.model_copy(update={"lifecycle_state": state, "direction": direction})
            assert can_take_invoice(row) is (takes_changes(state) and takes_invoice(direction))
    # An internal transfer or a retired row can never be offered, whatever its amount.
    transfer = build_movement("t", direction="INTERNAL_TRANSFER")
    assert suggest_payments([transfer], [build_invoice("X-1")]) == ()
    assert movement_choices(build_invoice("X-1"), [transfer]) == ()


def test_the_suggestions_agree_with_the_link_suggestion_on_amount_and_counterparty() -> None:
    invoices = [
        build_invoice("R-1", issued="2026-10-01"),
        build_invoice("R-2", issued="2026-10-05", base="100.00", party="Otra Empresa SL"),
        build_invoice("R-3", kind="issued", issued="2026-10-06", base="1500.00", retention="225.00"),
    ]
    rows = [
        build_movement("m1", amount="36.30", counterparty="papeleria trazo sl"),
        build_movement("m2", amount="121.00", counterparty="Algo Distinto"),
        build_movement("m3", amount="121.00", counterparty="otra empresa"),
        build_movement("m4", amount="1590.00", direction="INCOMING", counterparty="Beta"),
        build_movement("m5", amount="999.00"),
    ]
    names = movement_names(*rows)
    read = suggest_reconciliations(
        InvoiceCatalogue.model_validate({"invoices": {invoice.invoice_id: invoice for invoice in invoices}}),
        TransactionCatalogue.from_transactions(rows),
    )
    # Every candidate pair the link suggestion proposes is weighed here, with the same counterparty reading.
    pairs = {(item.transaction_id, item.invoice_id): item.counterparty_match for item in read}
    for invoice in invoices:
        for row in rows:
            weighed = suggest_payments([row], [invoice])
            if (row.transaction_id, invoice.invoice_id) in pairs:
                assert [one.pair.counterparty for one in weighed] == [
                    pairs[(row.transaction_id, invoice.invoice_id)]
                ], (
                    names[row.transaction_id],
                    invoice.invoice_number,
                )
            else:
                assert weighed == ()


def test_like_the_link_suggestion_a_movement_in_another_currency_is_never_a_candidate() -> None:
    invoice = build_invoice("U-1")
    dollars = build_movement("usd", amount="36.30", currency="USD")
    euros = build_movement("eur", amount="36.30", currency="EUR")
    read = suggest_reconciliations(
        InvoiceCatalogue.model_validate({"invoices": {invoice.invoice_id: invoice}}),
        TransactionCatalogue.from_transactions([dollars, euros]),
    )
    assert [item.transaction_id for item in read] == [euros.transaction_id]
    assert suggest_payments([dollars], [invoice]) == ()


@pytest.mark.parametrize("bare", ("S.L.", "s.l.", "SL", "S. L.", "S.L.U.", "SA", "S.A.", "Sociedad Anónima", " sl "))
def test_a_name_that_is_only_a_legal_form_overlaps_no_party(bare: str) -> None:
    assert not counterparties_overlap("Acme S.L.", bare)
    assert not counterparties_overlap("Casa Pepe", bare)
    assert not counterparties_overlap(bare, "Acme S.L.")


@pytest.mark.parametrize(
    ("invoice_name", "movement_name", "overlaps"),
    (
        ("Acme S.L.", "ACME", True),
        ("Acme", "acme s.l. madrid", True),
        ("Acme S.L.", "Beta S.L.", False),
        ("Acme S.L.", None, False),
        ("Acme S.L.", "   ", False),
        ("   ", "Acme", False),
    ),
)
def test_a_name_that_tells_a_party_apart_still_overlaps_either_way(
    invoice_name: str, movement_name: str | None, overlaps: bool
) -> None:
    assert counterparties_overlap(invoice_name, movement_name) is overlaps


def test_a_bare_legal_form_gives_the_link_suggestion_no_counterparty_boost() -> None:
    invoice = build_invoice("U-2", party="Acme S.L.")
    bare = build_movement("bare", amount="36.30", counterparty="S.L.")
    named = build_movement("named", amount="36.30", counterparty="acme")
    read = suggest_reconciliations(
        InvoiceCatalogue.model_validate({"invoices": {invoice.invoice_id: invoice}}),
        TransactionCatalogue.from_transactions([bare, named]),
    )
    by_row = {item.transaction_id: item for item in read}
    assert by_row[bare.transaction_id].counterparty_match is False
    assert by_row[named.transaction_id].counterparty_match is True
    assert by_row[named.transaction_id].score > by_row[bare.transaction_id].score


def test_a_link_reads_the_amount_against_what_the_invoice_settles_for_not_its_total() -> None:
    invoice = build_invoice("R-1", kind="issued", base="1500.00", retention="225.00")
    assert invoice_settlement(invoice) == Decimal("1590.00")
    net = build_movement("net", amount="1590.00", direction="INCOMING", counterparty="Trazo")
    gross = build_movement("gross", amount="1815.00", direction="INCOMING", counterparty="Trazo")
    assert link_differences(net, invoice) == ()
    (found,) = link_differences(gross, invoice)
    assert (found.kind, found.difference) == ("amount", Decimal("225.00"))


def test_a_link_tolerates_the_cent_the_suggestion_does_and_no_more() -> None:
    invoice = build_invoice("T-1")
    assert link_differences(build_movement("a", amount="36.31"), invoice) == ()
    assert link_differences(build_movement("b", amount="36.29"), invoice) == ()
    (found,) = link_differences(build_movement("c", amount="36.32"), invoice)
    assert (found.kind, found.difference) == ("amount", Decimal("0.02"))


def test_a_link_in_two_currencies_states_them_and_no_amount_difference() -> None:
    (found,) = link_differences(build_movement("usd", amount="999.00", currency="USD"), build_invoice("C-1"))
    assert (found.kind, found.movement_currency, found.invoice_currency, found.difference) == (
        "currency",
        "USD",
        "EUR",
        None,
    )


def test_a_link_judges_the_movements_own_counterparty_and_never_its_description() -> None:
    invoice = build_invoice("D-1")
    described = build_movement("described", description="PAPELERIA TRAZO SL FACTURA", counterparty=None)
    assert link_differences(described, invoice) == ()
    other = build_movement("other", description="PAPELERIA TRAZO SL", counterparty="Imprenta Turia")
    assert [found.kind for found in link_differences(other, invoice)] == ["counterparty"]
    blank = build_movement("blank", counterparty="   ")
    assert link_differences(blank, invoice) == ()
    assert link_differences(build_movement("tidy", counterparty="papeleria trazo"), invoice) == ()


def test_a_link_counts_the_other_movements_holding_the_invoice_and_not_itself() -> None:
    row = build_movement("own", counterparty="Trazo")
    others = tuple(f"{digit}" * 64 for digit in "bc")
    held = build_invoice("H-1", linked=(row.transaction_id, *others))
    (found,) = link_differences(row, held)
    assert (found.kind, found.count) == ("linked_elsewhere", 2)
    assert link_differences(row, build_invoice("H-2", linked=(row.transaction_id,))) == ()


# -- the scenarios the window's stand-in is asked about --------------------------------------------


_ASKED: Final = json.loads(_QUESTIONS.read_text(encoding="utf-8"))

#: Equal ranks fall to the lower invoice_id, so the tied pair's suggestion is whichever of the two sorts first.
def _lower_tied_invoice() -> str:
    tied = (build_invoice(number, party="Arroyo Asesores") for number in ("AA-118", "AA-119"))
    return min(tied, key=lambda invoice: invoice.invoice_id).invoice_number

#: The (movement, invoice) pairs each committed scenario must suggest, in order, worked from the rule its name states.
_SUGGESTED: Final[dict[str, list[tuple[str, str]]]] = {
    "a retencion invoice is settled by the net transfer within a cent, on its flow and currency": [("paid", "F-1")],
    "linked invoices, cited movements and retired movements are never suggested": [("free", "L-2")],
    "the number in the description outranks the gap": [("m", "PT-0412")],
    "without a number the shorter gap outranks the counterparty": [("p", "B-1")],
    "a payment more than three days before the invoice ranks after every payment made after it": [("p", "D-1")],
    "a payment three days before the invoice still ranks by its gap": [("p", "E-3")],
    "the nearer amount wins among otherwise equal candidates": [("c", "D-2")],
    "each invoice is offered to one movement": [("first", "ONE-1")],
    "tied invoices for one movement are ambiguous": [("row", "")],  # resolved from the invoice ids in the test
    "tied movements for one invoice point at each other": [("a", "N-5"), ("b", "N-5")],
    "a staged link withdraws every suggestion that uses its invoice or movement": [("b", "N-6")],
    "a movement is offered the invoices of its flow, those that settle it first by day": [("row", "S-1")],
    "an invoice no movement settles is offered the open movements near its day": [],
    "nothing to match": [],
    "a bare legal form names no counterparty, so it does not lift a candidate": [("bare", "F-1"), ("named", "F-2")],
    "a link states where its sides differ: the settlement within a cent, a shared currency, the movement's own counterparty, other holders": [],
}

_RETENCION, _OPEN_NEAR = 0, 12
#: What the focused scenarios offer the other side, as (name, settles) in the offered order: a 1500.00 base under a
#: retention of 225.00 and 21% IVA is settled by 1590.00 within a cent, and 48.26 with 21% IVA is 58.39, which is
#: settled by that amount, a cent either way, and by nothing further off.
_MOVEMENT_CHOICES: Final = {
    _RETENCION: [("paid", True), ("off", False), ("gross", False)],
    _OPEN_NEAR: [
        ("before", True),
        ("exact", True),
        ("near", True),
        ("edge_before", False),
        ("far", False),
    ],
}
_TOTALS: Final = {_RETENCION: {"F-1": ("1815.00", "1590.00")}}


def test_the_committed_scenarios_are_the_ones_the_expectations_state() -> None:
    assert [scenario["name"] for scenario in _ASKED["scenarios"]] == list(_SUGGESTED)


@pytest.mark.parametrize("scenario", _ASKED["scenarios"], ids=lambda scenario: cast(str, scenario["name"]))
def test_every_committed_scenario_is_answered_as_its_rule_says(scenario: dict[str, Any]) -> None:
    answer = recorded_scenario(scenario)["answer"]

    expected = [
        (movement, _lower_tied_invoice() if not invoice else invoice) for movement, invoice in _SUGGESTED[scenario["name"]]
    ]
    assert [(found["movement"], found["invoice"]) for found in answer["suggestions"]] == expected


@pytest.mark.parametrize("at", sorted(_MOVEMENT_CHOICES))
def test_a_focused_scenario_offers_the_movements_that_settle_first(at: int) -> None:
    answer = recorded_scenario(_ASKED["scenarios"][at])["answer"]

    assert [(item["movement"], item["settles"]) for item in answer["movement_choices"]] == _MOVEMENT_CHOICES[at]


def test_a_focused_movement_is_offered_the_invoices_of_its_flow_that_settle_it_first() -> None:
    scenario = next(item for item in _ASKED["scenarios"] if item.get("focus") == {"movement": "row"})

    answer = recorded_scenario(scenario)["answer"]

    assert [(item["invoice"], item["settles"]) for item in answer["invoice_choices"]] == [
        ("O-1", False),
        ("S-1", True),
        ("S-2", True),
        ("S-3", True),
    ]


@pytest.mark.parametrize("at", sorted(_TOTALS))
def test_a_retention_invoice_totals_and_settles_as_its_figures_say(at: int) -> None:
    recorded = recorded_scenario(_ASKED["scenarios"][at])

    for number, (total, settlement) in _TOTALS[at].items():
        assert (recorded["totals"][number], recorded["settlements"][number]) == (total, settlement)
