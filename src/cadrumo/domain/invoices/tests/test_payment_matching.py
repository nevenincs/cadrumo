"""Which movement settles which invoice: the flow, currency and amount a link needs, and the ranking.

Every expected value is worked out by hand from the rule as written, not read back from a run. The
recording the window's stand-in is held to is checked against the live rule at the end.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any, Final, cast

import pytest

from ...calculations.registry.authority import bundled_indexed_authority
from ...iva.schema import InvoiceKind
from ...transactions.classification_effects import takes_changes, takes_invoice
from ...transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ...transactions.models import Transaction, TransactionCatalogue
from ...transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ..catalogue import InvoiceCatalogue
from ..enums import IvaRate, PaymentStatus
from ..models import Invoice, InvoiceLine
from ..payment_matching import (
    EARLY_PAYMENT_DAYS,
    PICK_WINDOW_DAYS,
    PaymentSuggestion,
    can_take_invoice,
    invoice_choices,
    movement_choices,
    suggest_payments,
)
from ..service import (
    INVOICE_MATCH_TOLERANCE,
    counterparties_overlap,
    invoice_settlement,
    suggest_reconciliations,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_RECORDING: Final = (
    Path(__file__).resolve().parents[5] / "native/desktop/frontend/src/dev/fixtures/ledgerInvoiceMatch.json"
)
_ISSUED: Final = date(2026, 10, 1)
_PARTY: Final = "Papeleria Trazo SL"


@pytest.fixture(autouse=True)
def _authority_operation() -> Iterator[None]:
    with bundled_indexed_authority().operation():
        yield


def _day(offset: int, origin: date = _ISSUED) -> str:
    return date.fromordinal(origin.toordinal() + offset).isoformat()


def _invoice(
    number: str,
    *,
    kind: str = "received",
    issued: str = "2026-10-01",
    party: str = _PARTY,
    base: str = "30.00",
    retention: str | None = None,
    currency: str = "EUR",
    linked: tuple[str, ...] = (),
) -> Invoice:
    """An invoice at 21 % IVA over ``base``, so its total is ``base`` plus a cuota rounded to the cent."""
    amount = Decimal(base)
    cuota = (amount * Decimal("0.21")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return Invoice.model_validate(
        {
            "kind": InvoiceKind(kind),
            "invoice_number": number,
            "issued_at": date.fromisoformat(issued),
            "counterparty_name": party,
            "counterparty_tax_id": "B92000025",
            "counterparty_country": "ES",
            "base_total": amount,
            "iva_total": cuota,
            "grand_total": amount + cuota,
            "currency": currency,
            "lines": (
                InvoiceLine.model_validate(
                    {
                        "description": "Servicios",
                        "quantity": Decimal(1),
                        "unit_price": amount,
                        "subtotal": amount,
                        "iva_rate": IvaRate.from_registry("RATE_21"),
                        "iva_amount": cuota,
                    },
                ),
            ),
            "payment_status": PaymentStatus.PENDING,
            "retention_rate": None if retention is None else Decimal("0.15"),
            "retention_amount": None if retention is None else Decimal(retention),
            "linked_transaction_ids": linked,
        },
    )


def _movement(
    name: str,
    *,
    amount: str = "36.30",
    direction: str = "OUTGOING",
    on: str = "2026-10-03",
    description: str = "TRANSFERENCIA",
    counterparty: str | None = None,
    currency: str = "EUR",
    state: TransactionLifecycleState = TransactionLifecycleState.ACTIVE,
    invoice_id: str | None = None,
) -> Transaction:
    moment = datetime(2026, 11, 1, 9, 0, tzinfo=UTC)
    raw = RawTransaction(
        provider_transaction_id=name,
        booked_date=date.fromisoformat(on),
        value_date=None,
        amount=Decimal(amount),
        currency=currency,
        counterparty=counterparty,
        description=description,
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="0" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=moment,
            provider_name="synthetic",
        ),
        raw_fields={},
    )
    stored = Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection(direction),
            "business_classification": BusinessClassification.NOT_YET_PROCESSED,
            "source_jurisdiction": "ES",
            "group_label": None,
            "created_at": moment,
            "modified_at": moment,
        }
    )
    return stored.model_copy(update={"lifecycle_state": state, "invoice_id": invoice_id})


def _names(*movements: Transaction) -> dict[str, str]:
    return {movement.transaction_id: movement.raw.provider_transaction_id for movement in movements}


def _suggested(found: tuple[PaymentSuggestion, ...], names: Mapping[str, str]) -> list[tuple[str, str]]:
    return [(names[one.pair.transaction.transaction_id], one.pair.invoice.invoice_number) for one in found]


def test_a_candidate_settles_the_total_less_its_retencion_on_the_invoices_flow_and_currency_to_the_cent() -> None:
    # 1500.00 + 315.00 IVA = 1815.00, less 225.00 retained: the transfer is 1590.00.
    withheld = _invoice("F-1", kind="issued", base="1500.00", retention="225.00")
    assert invoice_settlement(withheld) == Decimal("1590.00")
    rows = {
        "paid": _movement("paid", amount="1590.00", direction="INCOMING"),
        "cent": _movement("cent", amount="1590.01", direction="INCOMING"),
        "under": _movement("under", amount="1589.99", direction="INCOMING"),
        "off": _movement("off", amount="1590.02", direction="INCOMING"),
        "gross": _movement("gross", amount="1815.00", direction="INCOMING"),
        "wrong_way": _movement("wrong_way", amount="1590.00", direction="OUTGOING"),
        "foreign": _movement("foreign", amount="1590.00", direction="INCOMING", currency="USD"),
        "transfer": _movement("transfer", amount="1590.00", direction="INTERNAL_TRANSFER"),
    }
    pairs = {name for name, row in rows.items() if suggest_payments([row], [withheld])}
    assert pairs == {"paid", "cent", "under"}


def test_the_link_tolerance_is_the_one_the_link_suggestion_uses() -> None:
    assert Decimal("0.01") == INVOICE_MATCH_TOLERANCE


def test_already_linked_invoices_and_movements_are_never_suggested() -> None:
    linked = _invoice("L-1", linked=("b" * 64,))
    open_one = _invoice("L-2")
    cites = _movement("cites", invoice_id="a" * 64)
    free = _movement("free")
    archived = _movement("gone", state=TransactionLifecycleState.ARCHIVED)
    found = suggest_payments([cites, free, archived], [linked, open_one])
    assert _suggested(found, _names(cites, free, archived)) == [("free", "L-2")]


def test_the_number_in_the_description_outranks_the_gap_the_gap_the_counterparty_the_counterparty_the_amount() -> None:
    row = _movement("m", on="2026-10-10", description="PAGO FRA PT-0412 TRAZO", counterparty="Otra Empresa")
    numbered = _invoice("PT-0412", issued="2026-08-01")
    close = _invoice("PT-0999", issued="2026-10-09", party="Otra Empresa SL")
    found = suggest_payments([row], [close, numbered])
    assert [one.pair.invoice.invoice_number for one in found] == ["PT-0412"]
    best = found[0]
    assert (best.ambiguous, best.pair.number, best.pair.counterparty, best.pair.gap) == (False, True, False, 70)
    assert [other.invoice.invoice_number for other in best.others] == ["PT-0999"]
    assert best.others[0].gap == 1
    assert best.others[0].counterparty is True

    # Without a number the shorter gap wins over the counterparty.
    plain = _movement("p", on="2026-10-10", counterparty="Papeleria Trazo")
    same_party = _invoice("A-1", issued="2026-09-01")
    nearer = _invoice("B-1", issued="2026-10-08", party="Nadie SA")
    assert suggest_payments([plain], [same_party, nearer])[0].pair.invoice.invoice_number == "B-1"

    # With equal numbers and gaps, the counterparty wins over the amount.
    twin_row = _movement("t", on="2026-10-10", amount="36.30", counterparty="Papeleria Trazo")
    right_party = _invoice("C-1", issued="2026-10-08")
    other_party = _invoice("C-2", issued="2026-10-08", party="Nadie SA")
    assert suggest_payments([twin_row], [other_party, right_party])[0].pair.invoice.invoice_number == "C-1"

    # With nothing else apart, the nearer amount wins.
    cents = _movement("c", on="2026-10-10", amount="36.31")
    exact = _invoice("D-1", issued="2026-10-08")
    off = _invoice("D-2", issued="2026-10-08", base="30.01")
    assert off.grand_total == Decimal("36.31") and exact.grand_total == Decimal("36.30")
    assert suggest_payments([cents], [exact, off])[0].pair.invoice.invoice_number == "D-2"


def test_a_payment_up_to_three_days_before_the_invoice_ranks_by_its_gap_and_earlier_ranks_last() -> None:
    assert EARLY_PAYMENT_DAYS == 3
    row = _movement("p", on="2026-10-10")
    # Gaps: -3 (ranks 3), -4 (ranks after everything made after issue), +9 (ranks 9).
    three_before = _invoice("E-3", issued="2026-10-13")
    four_before = _invoice("E-4", issued="2026-10-14")
    nine_after = _invoice("E-9", issued="2026-10-01")
    assert suggest_payments([row], [four_before, nine_after])[0].pair.invoice.invoice_number == "E-9"
    assert suggest_payments([row], [nine_after, three_before])[0].pair.invoice.invoice_number == "E-3"
    assert suggest_payments([row], [four_before, three_before])[0].pair.gap == -3


def test_each_invoice_is_offered_one_movement_and_each_movement_gets_one_invoice() -> None:
    first = _movement("first", on="2026-10-03", counterparty="Papeleria Trazo")
    second = _movement("second", on="2026-10-20", counterparty="Papeleria Trazo")
    only = _invoice("ONE-1", issued="2026-10-02")
    found = suggest_payments([first, second], [only])
    assert _suggested(found, _names(first, second)) == [("first", "ONE-1")]
    assert [other.invoice.invoice_number for other in found[0].others] == []


def test_equal_candidates_are_ambiguous_tied_invoices_for_one_movement_and_tied_movements_for_one_invoice() -> None:
    row = _movement("row", on="2026-10-06", counterparty="Arroyo")
    left = _invoice("AA-118", party="Arroyo Asesores")
    right = _invoice("AA-119", party="Arroyo Asesores")
    found = suggest_payments([row], [left, right])
    assert [one.ambiguous for one in found] == [True]
    assert sorted(tie.invoice.invoice_number for tie in found[0].ties) == ["AA-119"]

    a = _movement("a", on="2026-10-12", direction="INCOMING")
    b = _movement("b", on="2026-10-12", direction="INCOMING")
    issued = _invoice("N-5", kind="issued", issued="2026-10-09")
    names = _names(a, b)
    both = suggest_payments([a, b], [issued])
    assert sorted(_suggested(both, names)) == [("a", "N-5"), ("b", "N-5")]
    for one in both:
        rival = "b" if names[one.pair.transaction.transaction_id] == "a" else "a"
        assert one.ambiguous is True
        assert [names[tie.transaction.transaction_id] for tie in one.ties] == [rival]


def test_staging_a_link_withdraws_every_suggestion_that_uses_the_same_invoice_or_movement() -> None:
    a = _movement("a", on="2026-10-12", direction="INCOMING")
    b = _movement("b", on="2026-10-12", direction="INCOMING")
    issued = _invoice("N-5", kind="issued", issued="2026-10-09")
    other = _invoice("N-6", kind="issued", issued="2026-09-01")
    found = suggest_payments([a, b], [issued, other], staged={a.transaction_id: issued.invoice_id})
    # The rival takes the other invoice; the staged one is offered to no one.
    assert _suggested(found, _names(a, b)) == [("b", "N-6")]
    assert found[0].others == ()


def test_suggestions_run_newest_movement_first() -> None:
    old = _movement("old", on="2026-10-02")
    new = _movement("new", on="2026-10-20", amount="12.10")
    small = _invoice("S-1", base="10.00")
    big = _invoice("S-2")
    found = suggest_payments([old, new], [small, big])
    assert _suggested(found, _names(old, new)) == [("new", "S-1"), ("old", "S-2")]


def test_a_value_date_is_the_day_a_movement_counts_for() -> None:
    booked = _movement("v", on="2026-10-02")
    valued = booked.model_copy(update={"raw": booked.raw.model_copy(update={"value_date": date(2026, 10, 9)})})
    assert suggest_payments([valued], [_invoice("V-1")])[0].pair.gap == 8


def test_the_number_must_be_long_enough_to_tell_from_other_digits() -> None:
    short = _movement("s", description="PAGO F-12 GRACIAS")
    long = _movement("l", description="PAGO fra. ab/1234 gracias")
    assert suggest_payments([short], [_invoice("F-12")])[0].pair.number is False
    assert suggest_payments([long], [_invoice("AB-1234")])[0].pair.number is True


def test_a_name_inside_the_other_is_the_same_party_as_the_link_suggestion_reads_it() -> None:
    row = _movement("r", counterparty="PAPELERIA TRAZO")
    invoice = _invoice("P-1")
    assert suggest_payments([row], [invoice])[0].pair.counterparty is True
    assert suggest_payments([_movement("q", counterparty="Otra")], [invoice])[0].pair.counterparty is False
    assert suggest_payments([_movement("n", counterparty=None)], [invoice])[0].pair.counterparty is False


def test_the_picker_sorts_invoices_by_whether_they_settle_and_shows_what_is_staged_or_linked() -> None:
    row = _movement("row")
    settles_it = _invoice("S-1", issued="2026-10-04")
    elsewhere = _invoice("S-2", issued="2026-10-03", linked=("c" * 64,))
    taken_by = _invoice("S-3", issued="2026-10-02")
    different = _invoice("O-1", issued="2026-10-05", base="81.82")
    issued = _invoice("I-1", kind="issued")
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
    assert PICK_WINDOW_DAYS == 10
    ticket = _invoice("T-1", issued="2026-10-15", base="48.26")
    assert ticket.grand_total == Decimal("58.39")

    def row(name: str, offset: int, amount: str = "58.39", **facts: Any) -> Transaction:
        return _movement(name, amount=amount, on=_day(offset, date(2026, 10, 15)), **facts)

    near = row("near", 2, "58.40")
    exact = row("exact", PICK_WINDOW_DAYS)
    before = row("before", -9)
    edge_before = row("edge_before", -PICK_WINDOW_DAYS, "20.00")
    far = row("far", 1, "12.00")
    late = row("late", PICK_WINDOW_DAYS + 1)
    early = row("early", -PICK_WINDOW_DAYS - 1)
    income = row("income", 0, direction="INCOMING")
    linked = row("linked", 0, invoice_id="a" * 64)
    staged = row("staged", 0)
    foreign = row("foreign", 0, currency="USD")
    archived = row("archived", 0, state=TransactionLifecycleState.ARCHIVED)
    everything = (near, exact, before, edge_before, far, late, early, income, linked, staged, foreign, archived)
    offered = movement_choices(ticket, everything, staged={staged.transaction_id})
    names = _names(*everything)
    # Those that settle come first, the nearer day first among equal amounts; the others by nearest amount.
    assert [(names[c.transaction.transaction_id], c.settles) for c in offered] == [
        ("before", True),
        ("exact", True),
        ("near", True),
        ("edge_before", False),
        ("far", False),
    ]


def test_movements_that_settle_the_same_are_offered_nearest_amount_then_nearest_day() -> None:
    ticket = _invoice("T-2", issued="2026-10-15", base="48.26")
    exact_far = _movement("exact_far", amount="58.39", on="2026-10-25")
    cent_near = _movement("cent_near", amount="58.40", on="2026-10-16")
    exact_near = _movement("exact_near", amount="58.39", on="2026-10-16")
    names = _names(exact_far, cent_near, exact_near)
    offered = movement_choices(ticket, [exact_far, cent_near, exact_near])
    assert [names[c.transaction.transaction_id] for c in offered] == ["exact_near", "exact_far", "cent_near"]


def test_what_the_window_may_offer_is_what_the_link_writer_takes() -> None:
    movement = _movement("w")
    for state in TransactionLifecycleState:
        for direction in TransactionDirection:
            row = movement.model_copy(update={"lifecycle_state": state, "direction": direction})
            assert can_take_invoice(row) is (takes_changes(state) and takes_invoice(direction))
    # An internal transfer or a retired row can never be offered, whatever its amount.
    transfer = _movement("t", direction="INTERNAL_TRANSFER")
    assert suggest_payments([transfer], [_invoice("X-1")]) == ()
    assert movement_choices(_invoice("X-1"), [transfer]) == ()


def test_the_suggestions_agree_with_the_link_suggestion_on_amount_and_counterparty() -> None:
    invoices = [
        _invoice("R-1", issued="2026-10-01"),
        _invoice("R-2", issued="2026-10-05", base="100.00", party="Otra Empresa SL"),
        _invoice("R-3", kind="issued", issued="2026-10-06", base="1500.00", retention="225.00"),
    ]
    rows = [
        _movement("m1", amount="36.30", counterparty="papeleria trazo sl"),
        _movement("m2", amount="121.00", counterparty="Algo Distinto"),
        _movement("m3", amount="121.00", counterparty="otra empresa"),
        _movement("m4", amount="1590.00", direction="INCOMING", counterparty="Beta"),
        _movement("m5", amount="999.00"),
    ]
    names = _names(*rows)
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
    invoice = _invoice("U-1")
    dollars = _movement("usd", amount="36.30", currency="USD")
    euros = _movement("eur", amount="36.30", currency="EUR")
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
    invoice = _invoice("U-2", party="Acme S.L.")
    bare = _movement("bare", amount="36.30", counterparty="S.L.")
    named = _movement("named", amount="36.30", counterparty="acme")
    read = suggest_reconciliations(
        InvoiceCatalogue.model_validate({"invoices": {invoice.invoice_id: invoice}}),
        TransactionCatalogue.from_transactions([bare, named]),
    )
    by_row = {item.transaction_id: item for item in read}
    assert by_row[bare.transaction_id].counterparty_match is False
    assert by_row[named.transaction_id].counterparty_match is True
    assert by_row[named.transaction_id].score > by_row[bare.transaction_id].score


# -- the recording the window's stand-in is held to -------------------------------------------------


def _scenario_answer(scenario: Mapping[str, Any]) -> dict[str, Any]:
    invoices = {
        entry["number"]: _invoice(
            entry["number"],
            **{key: value for key, value in entry.items() if key not in {"number", "linked"}},
            linked=("b" * 64,) if entry.get("linked") else (),
        )
        for entry in scenario["invoices"]
    }
    movements = {
        entry["name"]: _movement(
            entry["name"],
            **{key: value for key, value in entry.items() if key not in {"name", "state", "cited"}},
            state=TransactionLifecycleState(entry.get("state", "ACTIVE")),
            invoice_id="a" * 64 if entry.get("cited") else None,
        )
        for entry in scenario["movements"]
    }
    names = _names(*movements.values())
    numbers = {invoice.invoice_id: number for number, invoice in invoices.items()}
    staged = {movements[name].transaction_id: invoices[number].invoice_id for name, number in scenario["staged"]}
    focus = scenario.get("focus", {})
    weighed = [invoice for number, invoice in invoices.items() if focus.get("invoice") in (None, number)]
    found = suggest_payments(movements.values(), weighed, staged=staged)
    wanted = movements[focus["movement"]].transaction_id if "movement" in focus else None

    def pair(one: Any) -> dict[str, Any]:
        return {
            "movement": names[one.transaction.transaction_id],
            "invoice": numbers[one.invoice.invoice_id],
            "number": one.number,
            "gap": one.gap,
            "counterparty": one.counterparty,
        }

    answer: dict[str, Any] = {
        "suggestions": [
            {
                **pair(one.pair),
                "ambiguous": one.ambiguous,
                "ties": [pair(tie) for tie in one.ties],
                "others": [pair(other) for other in one.others],
            }
            for one in found
            if wanted in (None, one.pair.transaction.transaction_id)
        ],
        "invoice_choices": None,
        "movement_choices": None,
    }
    if "movement" in focus:
        answer["invoice_choices"] = [
            {
                "invoice": numbers[choice.invoice.invoice_id],
                "settles": choice.settles,
                "staged_for": None if choice.staged_for is None else names[choice.staged_for],
                "linked": choice.linked,
            }
            for choice in invoice_choices(movements[focus["movement"]], invoices.values(), staged=staged)
        ]
    if "invoice" in focus:
        answer["movement_choices"] = [
            {"movement": names[choice.transaction.transaction_id], "settles": choice.settles}
            for choice in movement_choices(invoices[focus["invoice"]], movements.values(), staged=frozenset(staged))
        ]
    return answer


_RECORDED: Final = json.loads(_RECORDING.read_text(encoding="utf-8"))


@pytest.mark.parametrize("scenario", _RECORDED["scenarios"], ids=lambda scenario: cast(str, scenario["name"]))
def test_every_recorded_answer_is_the_rules(scenario: dict[str, Any]) -> None:
    assert _scenario_answer(scenario) == scenario["answer"]
