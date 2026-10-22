"""A catalogue decode answers each registry question once and still validates every invoice alike.

Decoding a catalogue shares one validation pass across its invoices, so a rate
or vocabulary answer given for one invoice is reused for the next invoice that
asks the identical question. These tests hold the decode to what each invoice
validates to on its own: the same values, the same JSON and the same set
fields, and the same refusal, including at the dates where a rate enters or
leaves force and after the same rate was already accepted on another date.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Final

import pytest
from pydantic import ValidationError

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority as _indexed_authority_for_test

from .. import models
from ..enums import IvaRate
from ..models import Invoice, InvoiceCatalogue
from .invoice_catalogue_seed import (
    CENT,
    SLOT_FRACTIONS,
    TRANSITIONAL_WINDOWS,
    SeedCase,
    fields_set,
    seed_payload,
    seed_payloads,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(autouse=True)
def _authority_operation() -> Iterator[None]:
    """Validate invoices under the generation-pinned authority production uses."""
    with _indexed_authority_for_test().operation():
        yield


def _decode_alone(payload: Mapping[str, object]) -> Invoice:
    return Invoice.model_validate_json(json.dumps(payload))


def _catalogue_json(payloads: list[dict[str, object]]) -> str:
    entries = {_decode_alone(payload).invoice_id: payload for payload in payloads}
    assert len(entries) == len(payloads), "seeded invoices must not collide on identity"
    return json.dumps({"invoices": entries})


def _first_message(error: ValidationError) -> str:
    return str(error.errors()[0]["msg"])


def test_the_seed_reaches_every_slot_and_every_window_edge() -> None:
    """The identity below means nothing unless the seed exercises what changed."""
    payloads = seed_payloads()
    seen = {
        (str(line.iva_rate), invoice.operation_date or invoice.issued_at)
        for invoice in (_decode_alone(payload) for payload in payloads)
        for line in invoice.lines
    }
    assert {slot for slot, _on in seen} == set(SLOT_FRACTIONS)
    for slot, (start, end) in TRANSITIONAL_WINDOWS.items():
        assert (slot, start) in seen
        assert (slot, end) in seen
    assert len(payloads) > 50


def test_a_catalogue_decodes_each_invoice_to_what_it_validates_to_alone() -> None:
    """One shared pass yields the same values, JSON and set fields as one pass per invoice."""
    payloads = seed_payloads()
    catalogue = InvoiceCatalogue.model_validate_json(_catalogue_json(payloads))

    assert len(catalogue) == len(payloads)
    for payload in payloads:
        alone = _decode_alone(payload)
        decoded = catalogue.get(alone.invoice_id)
        assert decoded is not None
        assert decoded == alone
        assert decoded.model_dump_json() == alone.model_dump_json()
        assert fields_set(decoded) == fields_set(alone)


def test_the_catalogue_round_trips_through_its_own_json() -> None:
    """Re-decoding the dumped catalogue reproduces it exactly."""
    catalogue = InvoiceCatalogue.model_validate_json(_catalogue_json(seed_payloads()))
    again = InvoiceCatalogue.model_validate_json(catalogue.model_dump_json())

    assert again == catalogue
    assert again.model_dump_json() == catalogue.model_dump_json()


def test_each_line_carries_the_statutory_fraction_of_its_devengo_date() -> None:
    """Every decoded cuota is the slot's own statutory fraction of the line's base."""
    catalogue = InvoiceCatalogue.model_validate_json(_catalogue_json(seed_payloads()))

    for invoice in catalogue.values():
        for line in invoice.lines:
            fraction = SLOT_FRACTIONS[str(line.iva_rate)]
            expected = Decimal("0") if fraction is None else (line.subtotal * fraction).quantize(CENT, ROUND_HALF_UP)
            assert line.iva_amount == expected


_OUT_OF_WINDOW: Final = (
    ("RATE_5", date(2023, 1, 1), date(2022, 12, 31)),
    ("RATE_5", date(2024, 9, 30), date(2024, 10, 1)),
    ("RATE_2", date(2024, 10, 1), date(2024, 9, 30)),
    ("RATE_2", date(2024, 12, 31), date(2025, 1, 1)),
    ("RATE_7.5", date(2024, 12, 31), date(2025, 1, 1)),
)


@pytest.mark.parametrize(("slot", "accepted_on", "refused_on"), _OUT_OF_WINDOW)
def test_a_rate_accepted_on_one_date_is_still_refused_the_day_it_is_not_in_force(
    slot: str, accepted_on: date, refused_on: date
) -> None:
    """An answer given for the in-force day is never reused for the day either side of the window."""
    accepted = seed_payload(SeedCase(1, accepted_on, (slot,)))
    refused = seed_payload(SeedCase(2, refused_on, (slot,)))
    with pytest.raises(ValidationError) as alone:
        _decode_alone(refused)
    expected = f"line rate {slot} was not in force on {refused_on.isoformat()}"
    assert expected in _first_message(alone.value)

    entries = {_decode_alone(accepted).invoice_id: accepted, "f" * 64: refused}
    with pytest.raises(ValidationError) as in_catalogue:
        InvoiceCatalogue.model_validate_json(json.dumps({"invoices": entries}))

    assert _first_message(in_catalogue.value) == _first_message(alone.value)


def test_an_operation_date_outside_the_window_is_refused_though_the_issue_date_differs() -> None:
    """The devengo is the operation date, and the pass keys its answer by that date."""
    inside = seed_payload(SeedCase(1, date(2024, 12, 31), ("RATE_2",), issued_offset=2))
    outside = seed_payload(SeedCase(2, date(2025, 1, 1), ("RATE_2",), issued_offset=1))
    entries = {_decode_alone(inside).invoice_id: inside, "f" * 64: outside}

    with pytest.raises(ValidationError) as caught:
        InvoiceCatalogue.model_validate_json(json.dumps({"invoices": entries}))

    assert "line rate RATE_2 was not in force on 2025-01-01" in _first_message(caught.value)


def test_a_cuota_at_the_wrong_rate_is_refused_after_the_same_rate_was_accepted() -> None:
    """A memoised rate still meets each line's own arithmetic."""
    accepted = seed_payload(SeedCase(1, date(2024, 11, 15), ("RATE_7.5",)))
    wrong = seed_payload(SeedCase(2, date(2024, 11, 15), ("RATE_7.5",)))
    wrong_lines = wrong["lines"]
    assert isinstance(wrong_lines, list)
    wrong_line = dict(wrong_lines[0])
    wrong_line["iva_amount"] = str(Decimal(str(wrong_line["subtotal"])) * Decimal("0.10"))
    wrong["lines"] = [wrong_line]
    wrong["iva_total"] = wrong_line["iva_amount"]
    wrong["grand_total"] = str(Decimal(str(wrong["base_total"])) + Decimal(str(wrong_line["iva_amount"])))
    entries = {_decode_alone(accepted).invoice_id: accepted, "f" * 64: wrong}

    with pytest.raises(ValidationError) as caught:
        InvoiceCatalogue.model_validate_json(json.dumps({"invoices": entries}))

    assert "iva_amount must equal subtotal * iva_rate within 1 cent" in _first_message(caught.value)


def test_an_invalid_tax_id_is_refused_naming_its_field_once_after_a_valid_one() -> None:
    """Refusals are raised afresh per invoice, so the field prefix is never applied twice."""
    valid = seed_payload(SeedCase(1, date(2025, 7, 7), ("RATE_21",)))
    invalid = seed_payload(SeedCase(2, date(2025, 7, 7), ("RATE_21",), counterparty=("B12345670", "ES")))
    with pytest.raises(ValidationError) as alone:
        _decode_alone(invalid)
    entries = {_decode_alone(valid).invoice_id: valid, "f" * 64: invalid, "e" * 64: dict(invalid)}

    with pytest.raises(ValidationError) as in_catalogue:
        InvoiceCatalogue.model_validate_json(json.dumps({"invoices": entries}))

    message = _first_message(in_catalogue.value)
    assert message == _first_message(alone.value)
    assert message.count("counterparty_tax_id: ") == 1


def test_a_simplified_intra_community_supply_without_a_tax_id_is_refused_in_a_catalogue() -> None:
    """The applicability catalogue answered once still refuses every invoice it governs."""
    allowed = seed_payload(SeedCase(1, date(2025, 7, 7), ("RATE_21",), counterparty=(None, "ES")))
    allowed["invoice_class"] = "SIMPLIFICADA"
    refused = seed_payload(SeedCase(2, date(2025, 7, 7), ("EXEMPT",), counterparty=(None, "ES")))
    refused["invoice_class"] = "SIMPLIFICADA"
    refused["iva_category"] = "domestic_reverse_charge"
    with pytest.raises(ValidationError) as alone:
        _decode_alone(refused)
    entries = {_decode_alone(allowed).invoice_id: allowed, "f" * 64: refused}

    with pytest.raises(ValidationError) as in_catalogue:
        InvoiceCatalogue.model_validate_json(json.dumps({"invoices": entries}))

    assert _first_message(in_catalogue.value) == _first_message(alone.value)
    assert "counterparty_tax_id is required on a factura simplificada" in _first_message(alone.value)


def test_a_catalogue_key_that_is_not_its_invoice_id_is_refused() -> None:
    """The key check runs on the decoded invoice after the shared pass."""
    payload = seed_payload(SeedCase(1, date(2025, 7, 7), ("RATE_21",)))
    invoice_id = _decode_alone(payload).invoice_id

    with pytest.raises(ValidationError, match=f"does not match invoice_id '{invoice_id}'"):
        InvoiceCatalogue.model_validate_json(json.dumps({"invoices": {"0" * 64: payload}}))


def test_a_stored_invoice_id_that_is_not_derived_from_its_content_is_refused() -> None:
    """The derived identity is recomputed for every invoice the pass decodes."""
    payload = seed_payload(SeedCase(1, date(2025, 7, 7), ("RATE_21",)))
    tampered = {**payload, "invoice_id": "0" * 64}

    with pytest.raises(ValidationError, match="invoice_id must match the stable hash derived"):
        InvoiceCatalogue.model_validate_json(json.dumps({"invoices": {"0" * 64: tampered}}))


def test_one_pass_encloses_every_validator_of_an_invoice_and_of_a_catalogue(monkeypatch: pytest.MonkeyPatch) -> None:
    """The line-rate and totals validators share one answer per slot and devengo date.

    The counter delegates to the real projection; it only observes how often
    the pass lets a question through.
    """
    real = models.iva_rate_percentage
    asked: list[tuple[str, date]] = []

    def counted(rate: IvaRate, on_date: date) -> Decimal | None:
        asked.append((str(rate), on_date))
        return real(rate, on_date)

    monkeypatch.setattr(models, "iva_rate_percentage", counted)
    on = date(2024, 11, 15)
    Invoice.model_validate_json(json.dumps(seed_payload(SeedCase(1, on, ("RATE_21", "RATE_21", "RATE_10")))))
    assert sorted(asked) == [("RATE_10", on), ("RATE_21", on)]

    asked.clear()
    payloads = [seed_payload(SeedCase(index, on, ("RATE_21",))) for index in range(1, 4)]
    entries = {Invoice.model_validate_json(json.dumps(payload)).invoice_id: payload for payload in payloads}
    asked.clear()
    InvoiceCatalogue.model_validate_json(json.dumps({"invoices": entries}))
    assert asked == [("RATE_21", on)]
