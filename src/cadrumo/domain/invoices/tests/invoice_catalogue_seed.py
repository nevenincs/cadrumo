"""A varied synthetic invoice seed computed from the statute table.

Every line's cuota is the slot's statutory fraction of its base, written out
here rather than read from the registry, so a validator that answers with the
wrong rate shows up as an arithmetic refusal instead of agreeing with itself.
The seed reaches every rate slot, every date on which a transitional slot
enters or leaves force, and a rotation of optional facts (retención, recargo,
suplido, rectificativa, foreign currency, lifecycle stamps, linked
transactions), so a decode path that differs from full validation on any of
them diverges on at least one invoice.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Final

from pydantic import BaseModel

CENT: Final = Decimal("0.01")

SLOT_FRACTIONS: Final[Mapping[str, Decimal | None]] = {
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
"""The fraction each slot carries, written out from the statute."""

TRANSITIONAL_WINDOWS: Final[Mapping[str, tuple[date, date]]] = {
    "RATE_5": (date(2023, 1, 1), date(2024, 9, 30)),
    "RATE_2": (date(2024, 10, 1), date(2024, 12, 31)),
    "RATE_7.5": (date(2024, 10, 1), date(2024, 12, 31)),
}
"""The transitional slots and the devengo dates they were in force.

RD-ley 20/2022 put the 5 % food rate in force for 2023 until RD-ley 4/2024
replaced it with the 2 % and 7.5 % rates for the last quarter of 2024.
"""

DEVENGO_DATES: Final = (
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
"""Every date a transitional slot enters or leaves force, the days either side, and a spread."""

COUNTERPARTIES: Final = (
    ("B12345674", "ES"),
    ("DE123456789", "DE"),
    ("FR12345678901", "FR"),
    ("IT12345678901", "IT"),
)

LINKED_ID: Final = "ab" * 32


def in_force(slot: str, on: date) -> bool:
    """Return whether ``slot`` was offered on ``on`` per :data:`TRANSITIONAL_WINDOWS`."""
    window = TRANSITIONAL_WINDOWS.get(slot)
    return window is None or window[0] <= on <= window[1]


def _line(slot: str, base: Decimal, index: int) -> dict[str, object]:
    fraction = SLOT_FRACTIONS[slot]
    iva = Decimal("0") if fraction is None else (base * fraction).quantize(CENT, rounding=ROUND_HALF_UP)
    return {
        "description": f"Linea {index} {slot}",
        "quantity": "1",
        "unit_price": str(base),
        "subtotal": str(base),
        "iva_rate": slot,
        "iva_amount": str(iva),
    }


@dataclass(frozen=True)
class SeedCase:
    """One seeded invoice: its devengo date, line slots and the facts that vary."""

    index: int
    devengo: date
    slots: tuple[str, ...]
    issued_offset: int = 0
    kind: str = "issued"
    counterparty: tuple[str | None, str] = ("B12345674", "ES")
    extra: Mapping[str, object] = field(default_factory=dict)


def seed_payload(case: SeedCase) -> dict[str, object]:
    """Return a JSON-native invoice payload whose figures are computed from the statute table."""
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
    retention = (base_total * Decimal("0.15")).quantize(CENT, rounding=ROUND_HALF_UP)
    variants: tuple[Mapping[str, object], ...] = (
        {},
        {"notes": "  revisada  ", "linked_transaction_ids": [LINKED_ID.upper(), LINKED_ID]},
        {"retention_rate": "0.15", "retention_amount": str(retention)},
        {"recargo_amount": str((iva_total / 4).quantize(CENT)), "suplido_amount": "12.30"},
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


def seed_payloads() -> list[dict[str, object]]:
    """Return the full varied seed, one payload per invoice, each valid on its own."""
    payloads: list[dict[str, object]] = []
    index = 0
    for devengo in DEVENGO_DATES:
        slots_in_force = [slot for slot in SLOT_FRACTIONS if in_force(slot, devengo)]
        for rotation in range(len(slots_in_force)):
            slots = tuple(slots_in_force[(rotation + step) % len(slots_in_force)] for step in range(1 + rotation % 3))
            draft = seed_payload(SeedCase(index, devengo, slots))
            iva_total = Decimal(str(draft["iva_total"]))
            extra = dict(_variant(index, Decimal(str(draft["base_total"])), iva_total))
            if iva_total == 0:
                # Recargo rides on a cuota (LIVA art. 161); a supply bearing none bears none.
                extra.pop("recargo_amount", None)
            case = SeedCase(
                index,
                devengo,
                slots,
                issued_offset=3 if index % 5 == 0 else 0,
                kind="received" if index % 2 else "issued",
                counterparty=COUNTERPARTIES[index % len(COUNTERPARTIES)],
                extra=extra,
            )
            payloads.append(seed_payload(case))
            index += 1
    # A simplified invoice may omit its recipient's tax id on the issued side.
    payloads.append(
        seed_payload(
            SeedCase(
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
    payloads.append(seed_payload(SeedCase(index + 1, date(2024, 12, 31), ("RATE_2",), issued_offset=2)))
    return payloads


def fields_set(model: BaseModel) -> object:
    """Return the set fields of ``model`` and of every nested model, recursively."""
    nested: dict[str, object] = {}
    for name in sorted(model.model_fields_set):
        value = getattr(model, name)
        if isinstance(value, BaseModel):
            nested[name] = fields_set(value)
        elif isinstance(value, tuple) and any(isinstance(item, BaseModel) for item in value):
            nested[name] = tuple(fields_set(item) if isinstance(item, BaseModel) else item for item in value)
        else:
            nested[name] = None
    return nested
