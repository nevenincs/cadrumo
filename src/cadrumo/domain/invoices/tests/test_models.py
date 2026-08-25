"""Unit tests for invoice and invoice-line models."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core.identity import IdentityError
from ...iva import EUMemberState, InvoiceKind, IvaRateKind, OssIossRegime, TransactionKind
from .._enums import (
    IvaRate,
    PaymentStatus,
    iva_rate_percentage,
    iva_rate_slot_percentage,
    numeric_iva_rate_percentages,
)
from ..errors import InvoiceValidationError
from .._models import (
    Invoice,
    InvoiceCatalogue,
    InvoiceLine,
    _normalise_invoice_monetary_fields,
    derive_invoice_id,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _valid_line(
    *,
    description: str = "Consultoría mensual",
    quantity: str = "1",
    unit_price: str = "100.00",
    iva_rate: IvaRate = IvaRate.RATE_21,
) -> InvoiceLine:
    quantity_dec = Decimal(quantity)
    unit_price_dec = Decimal(unit_price)
    subtotal = quantity_dec * unit_price_dec
    # The undated helper, matching what InvoiceLine's own arithmetic validator
    # uses: a transitional-rate line must be buildable here without the fixture
    # having to know which statutory window the rate belonged to.
    rate = iva_rate_slot_percentage(iva_rate)
    iva_amount = Decimal("0") if rate is None else (subtotal * rate)
    return InvoiceLine(
        description=description,
        quantity=quantity_dec,
        unit_price=unit_price_dec,
        subtotal=subtotal,
        iva_rate=iva_rate,
        iva_amount=iva_amount,
    )


def _valid_invoice(
    *,
    kind: InvoiceKind = InvoiceKind.ISSUED,
    invoice_number: str = "INV-001",
    issued_at: date = date(2026, 4, 1),
    counterparty_name: str = "Cliente SL",
    counterparty_tax_id: str = "B12345674",
    counterparty_country: str = "ES",
    currency: str = "EUR",
    lines: tuple[InvoiceLine, ...] | None = None,
    payment_status: PaymentStatus = PaymentStatus.PAID,
    linked_transaction_ids: tuple[str, ...] = (),
) -> Invoice:
    chosen_lines = lines if lines is not None else (_valid_line(),)
    base = sum((line.subtotal for line in chosen_lines), start=Decimal("0"))
    iva = sum((line.iva_amount for line in chosen_lines), start=Decimal("0"))
    grand = base + iva
    return Invoice.model_validate(
        {
            "kind": kind,
            "invoice_number": invoice_number,
            "issued_at": issued_at,
            "counterparty_name": counterparty_name,
            "counterparty_tax_id": counterparty_tax_id,
            "counterparty_country": counterparty_country,
            "base_total": base,
            "iva_total": iva,
            "grand_total": grand,
            "currency": currency,
            "lines": chosen_lines,
            "payment_status": payment_status,
            "linked_transaction_ids": linked_transaction_ids,
        },
    )


def test_invoice_accepts_a_transitional_food_rate_inside_its_window() -> None:
    """A November 2024 sale at 2 % is recordable as an invoice, not just as a ledger row.

    RD-ley 4/2024 art. 1 put certain foodstuffs at 2 % while the rest of the
    super-reducido tier stayed at 4 %. The ledger accepted such a row while the
    invoice path refused it, so the evidence-bearing surface was the one that
    could not record a legal sale. This is that asymmetry closed.
    """
    invoice = _valid_invoice(
        issued_at=date(2024, 11, 15),
        lines=(_valid_line(iva_rate=IvaRate.RATE_2),),
    )

    assert invoice.lines[0].iva_rate is IvaRate.RATE_2
    assert invoice.iva_total == Decimal("2.00")


def test_invoice_refuses_a_transitional_food_rate_outside_its_window() -> None:
    """The same 2 % line on a 2025 invoice is refused rather than silently re-rated.

    The window is what makes the transitional slots safe to carry. Without this
    check the slot would resolve on any date, letting a 2025 invoice claim a
    rate the statute had already withdrawn -- and the pre-fix implementation
    was worse still, silently returning the tier's ordinary 4 % for a line the
    operator marked 2 %.
    """
    with pytest.raises(ValidationError, match=r"was not in force"):
        _valid_invoice(
            issued_at=date(2025, 6, 1),
            lines=(_valid_line(iva_rate=IvaRate.RATE_2),),
        )


def test_invoice_id_is_64_char_lowercase_hex_and_stable() -> None:
    """Invoice ID must be derived and stable across equivalent re-construction."""
    first = _valid_invoice()
    second = _valid_invoice()
    assert first.invoice_id == second.invoice_id
    assert len(first.invoice_id) == 64
    assert all(ch in "0123456789abcdef" for ch in first.invoice_id)


def test_invoice_is_frozen_and_rejects_mutation() -> None:
    """Invoice models must be frozen."""
    invoice = _valid_invoice()
    with pytest.raises(ValidationError, match=r"frozen"):
        invoice.notes = "mutated"


def test_invoice_line_accepts_one_cent_rounding() -> None:
    """Line-level rounding within 1 cent must pass the subtotal/iva checks."""
    line = InvoiceLine.model_validate(
        {
            "description": "Rounded line",
            "quantity": Decimal("3"),
            "unit_price": Decimal("0.333"),
            "subtotal": Decimal("1.00"),
            "iva_rate": IvaRate.RATE_21,
            "iva_amount": Decimal("0.21"),
        },
    )
    assert line.subtotal == Decimal("1.00")


def test_invoice_line_rejects_larger_rounding_drift() -> None:
    """Drift beyond 1 cent on a line must fail validation."""
    with pytest.raises(ValidationError, match=r"subtotal must equal quantity \* unit_price"):
        InvoiceLine.model_validate(
            {
                "description": "Bad line",
                "quantity": Decimal("1"),
                "unit_price": Decimal("100.00"),
                "subtotal": Decimal("50.00"),
                "iva_rate": IvaRate.RATE_21,
                "iva_amount": Decimal("10.50"),
            },
        )


def test_invoice_counterparty_eu_member_state_accessor() -> None:
    """Counterparty country is normalized and exposed as a typed EU member when applicable."""
    cases = (
        ("DE", "DE123456789", "DE", EUMemberState.DE, True),
        ("US", "US123456789", "US", None, False),
        ("fr", "FR12345678901", "FR", EUMemberState.FR, True),
    )
    for raw_country, tax_id, stored_country, expected_state, expected_is_member in cases:
        invoice = _valid_invoice(
            counterparty_country=raw_country,
            counterparty_tax_id=tax_id,
        )

        assert invoice.counterparty_country == stored_country
        assert invoice.counterparty_eu_member_state is expected_state
        assert invoice.counterparty_is_eu_member is expected_is_member


def test_invoice_iva_category_is_typed_as_iva_category_substrate_enum() -> None:
    """Invoice.iva_category is now strongly-typed IvaCategory | None
    instead of free-form str | None. Pydantic coerces string inputs
    (the historical persistence shape) into IvaCategory members and
    serializes them back to their string values, so existing
    serialization round-trips remain valid."""
    from ...iva import IvaCategory

    invoice = _valid_invoice()
    assert invoice.iva_category is None

    invoice = Invoice.model_validate(
        {
            **invoice.model_dump(mode="python"),
            "iva_category": "domestic_general",
        },
    )
    assert invoice.iva_category is IvaCategory.DOMESTIC_GENERAL

    json_dump = invoice.model_dump(mode="json")
    assert json_dump["iva_category"] == "domestic_general"


def test_invoice_iva_category_rejects_unknown_string() -> None:
    """An unknown iva_category string must fail validation now that the
    field is typed against the closed IvaCategory enum."""
    invoice = _valid_invoice()

    with pytest.raises(ValidationError, match=r"iva_category must be an IvaCategory"):
        Invoice.model_validate(
            {
                **invoice.model_dump(mode="python"),
                "iva_category": "bogus-category",
            },
        )


def test_invoice_accepts_oss_axes_and_destination_rate_line() -> None:
    """OSS invoice lines carry destination-rate IVA through the explicit OSS rate tier."""
    line = InvoiceLine(
        description="OSS service to Germany",
        quantity=Decimal("1"),
        unit_price=Decimal("100"),
        subtotal=Decimal("100"),
        iva_rate=IvaRate.RATE_21,
        oss_rate_kind=IvaRateKind.GENERAL,
        iva_amount=Decimal("19"),
    )
    invoice = Invoice.model_validate(
        {
            "kind": InvoiceKind.ISSUED,
            "invoice_number": "OSS-DE-001",
            "issued_at": date(2026, 4, 1),
            "counterparty_name": "DE consumer",
            "counterparty_tax_id": "DE123456789",
            "counterparty_country": "DE",
            "base_total": Decimal("100"),
            "iva_total": Decimal("19"),
            "grand_total": Decimal("119"),
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PAID,
            "oss_ioss_regime": OssIossRegime.UNION_SCHEME,
            "oss_transaction_kind": TransactionKind.OSS_UNION_SERVICES,
        },
    )

    assert invoice.oss_ioss_regime is OssIossRegime.UNION_SCHEME
    assert invoice.oss_transaction_kind is TransactionKind.OSS_UNION_SERVICES
    assert invoice.lines[0].oss_rate_kind is IvaRateKind.GENERAL
    assert invoice.iva_total == Decimal("19")


def test_invoice_rejects_incomplete_oss_axes() -> None:
    """OSS regime and transaction-kind axes must travel together."""
    with pytest.raises(ValidationError, match=r"oss_ioss_regime and oss_transaction_kind"):
        Invoice.model_validate(
            {
                **_valid_invoice(
                    counterparty_country="DE",
                    counterparty_tax_id="DE123456789",
                ).model_dump(mode="python"),
                "oss_ioss_regime": OssIossRegime.UNION_SCHEME,
            },
        )


def test_invoice_rejects_oss_line_rate_without_invoice_oss_axes() -> None:
    """A destination-rate line cannot bypass domestic validation on a non-OSS invoice."""
    line = InvoiceLine(
        description="OSS line without invoice axes",
        quantity=Decimal("1"),
        unit_price=Decimal("100"),
        subtotal=Decimal("100"),
        iva_rate=IvaRate.RATE_21,
        oss_rate_kind=IvaRateKind.GENERAL,
        iva_amount=Decimal("19"),
    )

    with pytest.raises(ValidationError, match=r"oss_rate_kind requires invoice-level OSS/IOSS axes"):
        _valid_invoice(
            invoice_number="NOT-OSS-001",
            counterparty_country="DE",
            counterparty_tax_id="DE123456789",
            lines=(line,),
        )


def test_invoice_rejects_invalid_core_fields() -> None:
    """Invalid core field input must stay inside the pydantic validation boundary."""
    cases = (
        ("issued_at", "not-a-date", r"not-a-date.*not a valid ISO-8601 date"),
        ("kind", "bogus-kind", r"kind must be an InvoiceKind"),
    )
    for field, value, match in cases:
        payload = {
            "kind": InvoiceKind.ISSUED,
            "invoice_number": "INV-001",
            "issued_at": date(2026, 4, 1),
            "counterparty_name": "Cliente SL",
            "counterparty_tax_id": "B12345674",
            "counterparty_country": "ES",
            "base_total": Decimal("100"),
            "iva_total": Decimal("21"),
            "grand_total": Decimal("121"),
            "currency": "EUR",
            "lines": (_valid_line(),),
            "payment_status": PaymentStatus.PAID,
        }
        payload[field] = value

        with pytest.raises(ValidationError, match=match):
            Invoice.model_validate(payload)


def test_iva_rate_percentage_is_resolved_against_centralized_iva_substrate() -> None:
    """iva_rate_percentage must derive its values from registry/aeat/iva/rates.toml.

    The helper carries no hardcoded ``RATE_21 -> 0.21`` literal; every
    numeric slot is resolved against :func:`cadrumo.domain.iva.lookup_rate`
    for Spain at a given date.
    """
    from ...iva import EUMemberState, IvaRateKind, lookup_rate

    sample_date = date(2025, 6, 15)

    assert iva_rate_percentage(IvaRate.RATE_0, on_date=sample_date) == Decimal("0")
    assert iva_rate_percentage(IvaRate.EXEMPT, on_date=sample_date) is None
    assert iva_rate_percentage(IvaRate.NOT_SUBJECT, on_date=sample_date) is None

    for slot, kind in [
        (IvaRate.RATE_4, IvaRateKind.SUPER_REDUCED),
        (IvaRate.RATE_10, IvaRateKind.REDUCED),
        (IvaRate.RATE_21, IvaRateKind.GENERAL),
    ]:
        substrate_rate = lookup_rate(EUMemberState.ES, kind, sample_date)
        expected = substrate_rate.pct / Decimal("100")
        assert iva_rate_percentage(slot, on_date=sample_date) == expected


def test_invoice_exempt_lines_require_zero_iva() -> None:
    """EXEMPT and NOT_SUBJECT lines must carry iva_amount == 0 exactly."""
    with pytest.raises(ValidationError, match=r"iva_amount must be zero for EXEMPT / NOT_SUBJECT"):
        InvoiceLine.model_validate(
            {
                "description": "Exempt with iva",
                "quantity": Decimal("1"),
                "unit_price": Decimal("10"),
                "subtotal": Decimal("10"),
                "iva_rate": IvaRate.EXEMPT,
                "iva_amount": Decimal("0.01"),
            },
        )


def test_invoice_requires_exact_invoice_level_totals() -> None:
    """Invoice-level totals must equal the line sums exactly (no tolerance)."""
    line = _valid_line(quantity="1", unit_price="100.00")
    with pytest.raises(ValidationError, match=r"base_total must equal the exact sum of line subtotals"):
        Invoice.model_validate(
            {
                "kind": InvoiceKind.ISSUED,
                "invoice_number": "INV-001",
                "issued_at": date(2026, 4, 1),
                "counterparty_name": "Cliente SL",
                "counterparty_tax_id": "B12345674",
                "counterparty_country": "ES",
                "base_total": Decimal("100.01"),
                "iva_total": Decimal("21.00"),
                "grand_total": Decimal("121.01"),
                "currency": "EUR",
                "lines": (line,),
                "payment_status": PaymentStatus.PAID,
            },
        )


def test_invoice_rejects_accumulated_line_drift() -> None:
    """Per-line 1-cent drift that accumulates at the invoice level is rejected."""
    line_a = InvoiceLine.model_validate(
        {
            "description": "Line a",
            "quantity": Decimal("1"),
            "unit_price": Decimal("100.00"),
            "subtotal": Decimal("100.01"),
            "iva_rate": IvaRate.RATE_21,
            "iva_amount": Decimal("21.00"),
        },
    )
    line_b = InvoiceLine.model_validate(
        {
            "description": "Line b",
            "quantity": Decimal("1"),
            "unit_price": Decimal("100.00"),
            "subtotal": Decimal("100.01"),
            "iva_rate": IvaRate.RATE_21,
            "iva_amount": Decimal("21.00"),
        },
    )
    # line subtotal sum is 200.02 but we declare base_total as 200.00 → >1-cent drift.
    with pytest.raises(ValidationError, match=r"base_total must equal the exact sum of line subtotals"):
        Invoice.model_validate(
            {
                "kind": InvoiceKind.ISSUED,
                "invoice_number": "INV-001",
                "issued_at": date(2026, 4, 1),
                "counterparty_name": "Cliente SL",
                "counterparty_tax_id": "B12345674",
                "counterparty_country": "ES",
                "base_total": Decimal("200.00"),
                "iva_total": Decimal("42.00"),
                "grand_total": Decimal("242.00"),
                "currency": "EUR",
                "lines": (line_a, line_b),
                "payment_status": PaymentStatus.PAID,
            },
        )


def test_invoice_exempt_invoice_enforces_zero_iva_total() -> None:
    """An invoice with only EXEMPT / NOT_SUBJECT lines must have iva_total == 0."""
    exempt_line = InvoiceLine.model_validate(
        {
            "description": "Exempt service",
            "quantity": Decimal("1"),
            "unit_price": Decimal("50"),
            "subtotal": Decimal("50"),
            "iva_rate": IvaRate.EXEMPT,
            "iva_amount": Decimal("0"),
        },
    )
    invoice = _valid_invoice(lines=(exempt_line,))
    assert invoice.iva_total == Decimal("0")
    assert invoice.grand_total == invoice.base_total


def test_invoice_validates_spanish_tax_id_for_es_country() -> None:
    """ES counterparties must pass NIF/NIE/CIF validation."""
    # "INVALID" has 7 chars → tax-id shape gate rejects it before any
    # checksum runs. IdentityError inherits from ValueError, so pydantic
    # wraps the raise into ValidationError at the model boundary. Pin the
    # wrapping class and the wrapped IdentityError's localisation key (never
    # rendered prose) so the operator-facing message stays localisable.
    with pytest.raises(ValidationError) as excinfo:
        _valid_invoice(counterparty_country="ES", counterparty_tax_id="INVALID")
    error_detail = excinfo.value.errors()[0]
    assert "ctx" in error_detail
    wrapped = error_detail["ctx"]["error"]
    assert isinstance(wrapped, IdentityError)
    assert wrapped.translated_message == "errors.identity.tax_id_invalid_length"


def test_invoice_validates_iva_prefix_for_non_es_country() -> None:
    """Non-ES counterparties must carry a NIF-IVA matching their country format."""
    invoice = _valid_invoice(counterparty_country="DE", counterparty_tax_id="DE123456789")
    assert invoice.counterparty_tax_id == "DE123456789"


def test_invoice_rejects_invalid_non_es_iva_prefix() -> None:
    """Non-ES counterparties reject NIF-IVA values that do not match their country."""
    cases = (
        ("DE", "123456789", r"is not a valid Germany NIF-IVA"),
        ("US", "123456789", r"IVA number must start with the counterparty country ISO-2 prefix"),
    )
    for country, tax_id, match in cases:
        with pytest.raises(ValidationError, match=match):
            _valid_invoice(counterparty_country=country, counterparty_tax_id=tax_id)


def test_invoice_linked_transaction_ids_are_deduplicated_and_hex_validated() -> None:
    """Linked transaction IDs must be 64-char lowercase hex and deduplicated."""
    hex_a = "a" * 64
    hex_b = "b" * 64
    invoice = _valid_invoice(linked_transaction_ids=(hex_a, hex_b, hex_a))
    assert invoice.linked_transaction_ids == (hex_a, hex_b)
    with pytest.raises(
        ValidationError,
        match=r"each linked_transaction_id must be a 64-character lowercase hex digest",
    ):
        _valid_invoice(linked_transaction_ids=("not-hex",))


def test_invoice_rejects_caller_supplied_invoice_id_mismatch() -> None:
    """A caller-supplied ``invoice_id`` must match the derived digest."""
    invoice = _valid_invoice()
    with pytest.raises(ValidationError, match=r"invoice_id must match the stable hash derived"):
        Invoice.model_validate(
            {
                "invoice_id": "0" * 64,
                **{key: value for key, value in invoice.model_dump(mode="python").items() if key != "invoice_id"},
            },
        )


def test_derive_invoice_id_is_stable_over_equivalent_decimals() -> None:
    """Derivation must be invariant under equivalent Decimal forms."""
    first = derive_invoice_id(
        kind=InvoiceKind.ISSUED,
        invoice_number="INV-001",
        issued_at=date(2026, 4, 1),
        counterparty_tax_id="B12345674",
        currency="EUR",
        grand_total=Decimal("121.00"),
    )
    second = derive_invoice_id(
        kind=InvoiceKind.ISSUED,
        invoice_number="INV-001",
        issued_at=date(2026, 4, 1),
        counterparty_tax_id="B12345674",
        currency="EUR",
        grand_total=Decimal("121"),
    )
    assert first == second


def test_invoice_number_is_uppercased_for_identity() -> None:
    """Invoice number casing must not yield distinct identities."""
    lower = _valid_invoice(invoice_number="inv-001")
    upper = _valid_invoice(invoice_number="INV-001")
    assert lower.invoice_id == upper.invoice_id
    assert lower.invoice_number == "INV-001"


def test_catalogue_rejects_duplicate_invoice_ids_on_construction() -> None:
    """Duplicate logical IDs must be rejected when building a catalogue."""
    invoice = _valid_invoice()
    with pytest.raises(ValidationError, match=r"duplicate invoice_id"):
        InvoiceCatalogue.from_invoices([invoice, invoice])


def test_catalogue_iteration_yields_invoices() -> None:
    """Iteration yields invoices, not model fields."""
    first = _valid_invoice(invoice_number="INV-001")
    second = _valid_invoice(invoice_number="INV-002")
    catalogue = InvoiceCatalogue.from_invoices([first, second])
    assert [invoice.invoice_id for invoice in catalogue] == [first.invoice_id, second.invoice_id]
    assert first.invoice_id in catalogue
    assert len(catalogue) == 2


# ---------------------------------------------------------------------------
# numeric_iva_rate_percentages helper
# ---------------------------------------------------------------------------


def test_numeric_iva_rate_percentages_tracks_rate_members_only() -> None:
    """The helper returns canonical percentages for ``RATE_*`` enum members only.

    Derivation test: if a new ``RATE_<n>`` slot is added to
    :class:`IvaRate` the helper must pick it up without code changes.
    """
    result = numeric_iva_rate_percentages()
    rate_members = [m for m in IvaRate if m.value.startswith("RATE_")]

    # One percentage per RATE_ member, and nothing else. Pinning the literal set
    # here would contradict this test's own premise: it claims a new slot is
    # picked up without code changes, and a hardcoded set makes every new slot a
    # code change. It did exactly that when the transitional food rates landed.
    assert len(result) == len(rate_members)
    assert len(result) < len(IvaRate)
    assert [m for m in IvaRate if not m.value.startswith("RATE_")] == [IvaRate.EXEMPT, IvaRate.NOT_SUBJECT]

    # Anchors, so the length check above cannot pass over a set of the right
    # size but the wrong values -- the standing LIVA tiers must always resolve.
    assert {Decimal("0"), Decimal("4"), Decimal("10"), Decimal("21")} <= result

    # And the parse is by value, not by member name: RATE_7_5 names a slot whose
    # percentage is seven and a half, not seventy-five.
    if hasattr(IvaRate, "RATE_7_5"):
        assert Decimal("7.5") in result
        assert Decimal("75") not in result


@pytest.mark.parametrize(
    "field",
    (
        pytest.param("retention_rate", id="retention-rate"),
        pytest.param("retention_amount", id="retention-amount"),
        pytest.param("fx_rate", id="fx-rate"),
    ),
)
def test_optional_monetary_field_refuses_an_unreadable_value(field: str) -> None:
    """A present-but-unparseable optional amount must refuse, not become absent.

    These three are ``Decimal | None``, and that optionality is exactly what
    made the failure silent: ``coerce_decimal`` returns ``None`` for an absent
    value AND for an unreadable one, so writing its result back unchecked
    recorded "the taxpayer did not have one" for a value that could not be read.
    The required totals in the same function coerce to ``None`` identically and
    were refused only because pydantic rejects ``None`` for a required field.
    """
    with pytest.raises(InvoiceValidationError) as caught:
        _normalise_invoice_monetary_fields({field: "not-a-number"})

    message = str(caught.value)
    assert field in message, "the refusal must name the field"
    assert "not-a-number" in message, "and echo what could not be read"


@pytest.mark.parametrize(
    ("raw", "expected"),
    (
        pytest.param(None, None, id="absent-stays-absent"),
        pytest.param("0.15", Decimal("0.15"), id="plain-rate"),
        pytest.param(Decimal("1.0925"), Decimal("1.0925"), id="already-decimal"),
        pytest.param("0", Decimal("0"), id="zero"),
    ),
)
def test_optional_monetary_field_still_accepts_what_it_should(raw: object, expected: object) -> None:
    """The refusal is narrow: absent stays absent and every readable value parses.

    ``None`` is the case that must keep working — a taxpayer with no retención
    is not an error, and conflating that with an unreadable value in the other
    direction would be just as wrong as the defect this replaces.
    """
    assert _normalise_invoice_monetary_fields({"retention_rate": raw}) == {"retention_rate": expected}


def test_refusal_bounds_what_it_quotes_back() -> None:
    """The echo is bounded, because a mis-mapped column can put anything here.

    Echoing the value is what lets an operator find the offending cell, and these
    fields are numeric by declared purpose, so what lands here is normally a short
    malformed number. The bound covers the accident: an import that maps an address
    column onto ``fx_rate`` would otherwise put the whole cell into an error
    message, and nothing on the error path redacts a message body. A value long
    enough to be truncated was never a number, so the operator loses nothing.
    """
    overlong = "x" * 500

    with pytest.raises(InvoiceValidationError) as caught:
        _normalise_invoice_monetary_fields({"fx_rate": overlong})

    message = str(caught.value)
    assert overlong not in message, "the full value must not reach the message"
    assert "(502 chars)" in message, "and the operator is told how much was withheld"
    assert len(message) < 250, f"the message stays readable; got {len(message)} chars"
