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
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Final

import pytest
from pydantic import BaseModel, ValidationError

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority as _indexed_authority_for_test

from .. import models
from ..enums import IvaRate
from ..models import Invoice, InvoiceCatalogue

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(autouse=True)
def _authority_operation() -> Iterator[None]:
    """Validate invoices under the generation-pinned authority production uses."""
    with _indexed_authority_for_test().operation():
        yield


_CENT: Final = Decimal("0.01")

#: The fraction each slot carries, written out from the statute rather than read
#: from the registry, so a registry answer reused on the wrong date shows up as
#: an arithmetic refusal instead of agreeing with itself.
_SLOT_FRACTIONS: Final[Mapping[str, Decimal | None]] = {
    "RATE_0": Decimal("0"),
    "RATE_2": Decimal("0.02"),
    "RATE_4": Decimal("0.04"),
    "RATE_5": Decimal("0.05"),
    "RATE_7.5": Decimal("0.075"),
    "RATE_10": Decimal("0.10"),
    "RATE_21": Decimal("0.21"),
    "EXEMPT": None,
    "NOT_SUBJECT": None,
}

#: The transitional slots and the devengo dates they were in force: RD-ley
#: 20/2022 put the 5 % food rate in force for 2023 until RD-ley 4/2024 replaced
#: it with the 2 % and 7.5 % rates for the last quarter of 2024.
_TRANSITIONAL_WINDOWS: Final[Mapping[str, tuple[date, date]]] = {
    "RATE_5": (date(2023, 1, 1), date(2024, 9, 30)),
    "RATE_2": (date(2024, 10, 1), date(2024, 12, 31)),
    "RATE_7.5": (date(2024, 10, 1), date(2024, 12, 31)),
}

#: Every date on which a transitional slot enters or leaves force, with the
#: days either side, and a spread across the supported years.
_DEVENGO_DATES: Final = (
    date(2022, 1, 3),
    date(2022, 12, 31),
    date(2023, 1, 1),
    date(2023, 6, 15),
    date(2024, 9, 30),
    date(2024, 10, 1),
    date(2024, 11, 15),
    date(2024, 12, 31),
    date(2025, 1, 1),
    date(2025, 7, 7),
    date(2026, 3, 3),
)

_COUNTERPARTIES: Final = (
    ("B12345674", "ES"),
    ("DE123456789", "DE"),
    ("FR12345678901", "FR"),
    ("IT12345678901", "IT"),
)

_LINKED_ID: Final = "ab" * 32


def _in_force(slot: str, on: date) -> bool:
    window = _TRANSITIONAL_WINDOWS.get(slot)
    return window is None or window[0] <= on <= window[1]


def _line(slot: str, base: Decimal, index: int) -> dict[str, object]:
    fraction = _SLOT_FRACTIONS[slot]
    iva = Decimal("0") if fraction is None else (base * fraction).quantize(_CENT, rounding=ROUND_HALF_UP)
    return {
        "description": f"Linea {index} {slot}",
        "quantity": "1",
        "unit_price": str(base),
        "subtotal": str(base),
        "iva_rate": slot,
        "iva_amount": str(iva),
    }


@dataclass(frozen=True)
class _Case:
    """One seeded invoice: its devengo date, line slots and the facts that vary."""

    index: int
    devengo: date
    slots: tuple[str, ...]
    issued_offset: int = 0
    kind: str = "issued"
    counterparty: tuple[str | None, str] = ("B12345674", "ES")
    extra: Mapping[str, object] = field(default_factory=dict)


def _payload(case: _Case) -> dict[str, object]:
    """A JSON-native invoice payload whose figures are computed from the statute table."""
    index, devengo, issued_offset, extra = case.index, case.devengo, case.issued_offset, case.extra
    lines = [
        _line(slot, Decimal(100 + 37 * index + 11 * position) / 4, position) for position, slot in enumerate(case.slots)
    ]
    base = sum((Decimal(str(line["subtotal"])) for line in lines), start=Decimal("0"))
    iva = sum((Decimal(str(line["iva_amount"])) for line in lines), start=Decimal("0"))
    tax_id, country = case.counterparty
    payload: dict[str, object] = {
        "kind": case.kind,
        "invoice_number": f"pass-{index:04d}",
        "issued_at": (devengo + timedelta(days=issued_offset)).isoformat(),
        "counterparty_name": f"Contraparte {index % 7}",
        "counterparty_tax_id": tax_id,
        "counterparty_country": country,
        "base_total": str(base),
        "iva_total": str(iva),
        "grand_total": str(base + iva),
        "currency": "EUR",
        "lines": lines,
        "payment_status": "PAID",
    }
    if issued_offset:
        payload["operation_date"] = devengo.isoformat()
        payload["operation_date_role"] = "OPERATION_PERFORMED"
    if extra:
        payload.update(extra)
        if "recargo_amount" in extra or "suplido_amount" in extra:
            surcharge = Decimal(str(extra.get("recargo_amount", "0"))) + Decimal(str(extra.get("suplido_amount", "0")))
            payload["grand_total"] = str(base + iva + surcharge)
    return payload


def _variant(index: int, base_total: Decimal, iva_total: Decimal) -> Mapping[str, object]:
    """Rotate optional facts across the seed so each validator sees varied input."""
    retention = (base_total * Decimal("0.15")).quantize(_CENT, rounding=ROUND_HALF_UP)
    variants: tuple[Mapping[str, object], ...] = (
        {},
        {"notes": "  revisada  ", "linked_transaction_ids": [_LINKED_ID.upper(), _LINKED_ID]},
        {"retention_rate": "0.15", "retention_amount": str(retention)},
        {"recargo_amount": str((iva_total / 4).quantize(_CENT)), "suplido_amount": "12.30"},
        {"invoice_class": "RECTIFICATIVA", "series": "R", "rectifies_invoice_number": f"pass-{index - 1:04d}"},
        {
            "currency": "USD",
            "fx_rate": "0.9137",
            "fx_rate_date": "2024-01-02",
            "fx_rate_source": "ECB",
            "fx_rate_observation_date": "2023-12-29",
        },
        {"created_at": "2025-02-03T10:11:12+00:00", "updated_at": "2025-02-04T09:00:00+00:00"},
    )
    return variants[index % len(variants)]


def _seed() -> list[dict[str, object]]:
    payloads: list[dict[str, object]] = []
    index = 0
    for devengo in _DEVENGO_DATES:
        in_force = [slot for slot in _SLOT_FRACTIONS if _in_force(slot, devengo)]
        for rotation in range(len(in_force)):
            slots = tuple(in_force[(rotation + step) % len(in_force)] for step in range(1 + rotation % 3))
            draft = _payload(_Case(index, devengo, slots))
            iva_total = Decimal(str(draft["iva_total"]))
            extra = dict(_variant(index, Decimal(str(draft["base_total"])), iva_total))
            if iva_total == 0:
                # Recargo rides on a cuota (LIVA art. 161); a supply bearing none bears none.
                extra.pop("recargo_amount", None)
            case = _Case(
                index,
                devengo,
                slots,
                issued_offset=3 if index % 5 == 0 else 0,
                kind="received" if index % 2 else "issued",
                counterparty=_COUNTERPARTIES[index % len(_COUNTERPARTIES)],
                extra=extra,
            )
            payloads.append(_payload(case))
            index += 1
    # A simplified invoice may omit its recipient's tax id on the issued side.
    payloads.append(
        _payload(
            _Case(
                index,
                date(2024, 12, 31),
                ("RATE_2", "RATE_21"),
                counterparty=(None, "ES"),
                extra={"invoice_class": "SIMPLIFICADA"},
            )
        )
    )
    # The devengo is the operation date: a 2 % line issued after the window
    # closed is still in force when the operation happened inside it.
    payloads.append(_payload(_Case(index + 1, date(2024, 12, 31), ("RATE_2",), issued_offset=2)))
    return payloads


def _decode_alone(payload: Mapping[str, object]) -> Invoice:
    return Invoice.model_validate_json(json.dumps(payload))


def _catalogue_json(payloads: list[dict[str, object]]) -> str:
    entries = {_decode_alone(payload).invoice_id: payload for payload in payloads}
    assert len(entries) == len(payloads), "seeded invoices must not collide on identity"
    return json.dumps({"invoices": entries})


def _fields_set(model: BaseModel) -> object:
    """The set fields of ``model`` and of every nested model, recursively."""
    nested: dict[str, object] = {}
    for name in sorted(model.model_fields_set):
        value = getattr(model, name)
        if isinstance(value, BaseModel):
            nested[name] = _fields_set(value)
        elif isinstance(value, tuple) and any(isinstance(item, BaseModel) for item in value):
            nested[name] = tuple(_fields_set(item) if isinstance(item, BaseModel) else item for item in value)
        else:
            nested[name] = None
    return nested


def _first_message(error: ValidationError) -> str:
    return str(error.errors()[0]["msg"])


def test_the_seed_reaches_every_slot_and_every_window_edge() -> None:
    """The identity below means nothing unless the seed exercises what changed."""
    payloads = _seed()
    seen = {
        (str(line.iva_rate), invoice.operation_date or invoice.issued_at)
        for invoice in (_decode_alone(payload) for payload in payloads)
        for line in invoice.lines
    }
    assert {slot for slot, _on in seen} == set(_SLOT_FRACTIONS)
    for slot, (start, end) in _TRANSITIONAL_WINDOWS.items():
        assert (slot, start) in seen
        assert (slot, end) in seen
    assert len(payloads) > 50


def test_a_catalogue_decodes_each_invoice_to_what_it_validates_to_alone() -> None:
    """One shared pass yields the same values, JSON and set fields as one pass per invoice."""
    payloads = _seed()
    catalogue = InvoiceCatalogue.model_validate_json(_catalogue_json(payloads))

    assert len(catalogue) == len(payloads)
    for payload in payloads:
        alone = _decode_alone(payload)
        decoded = catalogue.get(alone.invoice_id)
        assert decoded is not None
        assert decoded == alone
        assert decoded.model_dump_json() == alone.model_dump_json()
        assert _fields_set(decoded) == _fields_set(alone)


def test_the_catalogue_round_trips_through_its_own_json() -> None:
    """Re-decoding the dumped catalogue reproduces it exactly."""
    catalogue = InvoiceCatalogue.model_validate_json(_catalogue_json(_seed()))
    again = InvoiceCatalogue.model_validate_json(catalogue.model_dump_json())

    assert again == catalogue
    assert again.model_dump_json() == catalogue.model_dump_json()


def test_each_line_carries_the_statutory_fraction_of_its_devengo_date() -> None:
    """Every decoded cuota is the slot's own statutory fraction of the line's base."""
    catalogue = InvoiceCatalogue.model_validate_json(_catalogue_json(_seed()))

    for invoice in catalogue.values():
        for line in invoice.lines:
            fraction = _SLOT_FRACTIONS[str(line.iva_rate)]
            expected = Decimal("0") if fraction is None else (line.subtotal * fraction).quantize(_CENT, ROUND_HALF_UP)
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
    accepted = _payload(_Case(1, accepted_on, (slot,)))
    refused = _payload(_Case(2, refused_on, (slot,)))
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
    inside = _payload(_Case(1, date(2024, 12, 31), ("RATE_2",), issued_offset=2))
    outside = _payload(_Case(2, date(2025, 1, 1), ("RATE_2",), issued_offset=1))
    entries = {_decode_alone(inside).invoice_id: inside, "f" * 64: outside}

    with pytest.raises(ValidationError) as caught:
        InvoiceCatalogue.model_validate_json(json.dumps({"invoices": entries}))

    assert "line rate RATE_2 was not in force on 2025-01-01" in _first_message(caught.value)


def test_a_cuota_at_the_wrong_rate_is_refused_after_the_same_rate_was_accepted() -> None:
    """A memoised rate still meets each line's own arithmetic."""
    accepted = _payload(_Case(1, date(2024, 11, 15), ("RATE_7.5",)))
    wrong = _payload(_Case(2, date(2024, 11, 15), ("RATE_7.5",)))
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
    valid = _payload(_Case(1, date(2025, 7, 7), ("RATE_21",)))
    invalid = _payload(_Case(2, date(2025, 7, 7), ("RATE_21",), counterparty=("B12345670", "ES")))
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
    allowed = _payload(_Case(1, date(2025, 7, 7), ("RATE_21",), counterparty=(None, "ES")))
    allowed["invoice_class"] = "SIMPLIFICADA"
    refused = _payload(_Case(2, date(2025, 7, 7), ("EXEMPT",), counterparty=(None, "ES")))
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
    payload = _payload(_Case(1, date(2025, 7, 7), ("RATE_21",)))
    invoice_id = _decode_alone(payload).invoice_id

    with pytest.raises(ValidationError, match=f"does not match invoice_id '{invoice_id}'"):
        InvoiceCatalogue.model_validate_json(json.dumps({"invoices": {"0" * 64: payload}}))


def test_a_stored_invoice_id_that_is_not_derived_from_its_content_is_refused() -> None:
    """The derived identity is recomputed for every invoice the pass decodes."""
    payload = _payload(_Case(1, date(2025, 7, 7), ("RATE_21",)))
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
    Invoice.model_validate_json(json.dumps(_payload(_Case(1, on, ("RATE_21", "RATE_21", "RATE_10")))))
    assert sorted(asked) == [("RATE_10", on), ("RATE_21", on)]

    asked.clear()
    payloads = [_payload(_Case(index, on, ("RATE_21",))) for index in range(1, 4)]
    entries = {Invoice.model_validate_json(json.dumps(payload)).invoice_id: payload for payload in payloads}
    asked.clear()
    InvoiceCatalogue.model_validate_json(json.dumps({"invoices": entries}))
    assert asked == [("RATE_21", on)]
