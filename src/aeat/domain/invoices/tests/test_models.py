"""Unit tests for invoice and invoice-line models."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ...iva import InvoiceKind, IvaRateKind, OssIossRegime, TransactionKind
from .._enums import IvaRate, PaymentStatus, iva_rate_percentage, numeric_iva_rate_percentages
from .._models import Invoice, InvoiceCatalogue, InvoiceLine, derive_invoice_id

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
    rate = iva_rate_percentage(iva_rate)
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


def test_invoice_counterparty_eu_member_state_returns_typed_enum_for_eu_country() -> None:
    """Promote the str counterparty_country into the substrate-typed
    EUMemberState through the typed accessor — downstream consumers
    (OSS / IOSS / intra-community routing) work against the closed enum
    rather than a raw 2-letter string."""
    from ...iva import EUMemberState

    invoice = _valid_invoice(
        counterparty_country="DE",
        counterparty_tax_id="DE123456789",
    )
    assert invoice.counterparty_country == "DE"
    assert invoice.counterparty_eu_member_state is EUMemberState.DE
    assert invoice.counterparty_is_eu_member is True


def test_invoice_counterparty_eu_member_state_returns_none_for_non_eu_country() -> None:
    """Non-EU counterparties resolve to None — Modelo 369 OSS bindings
    and intra-community classifiers gate on
    counterparty_is_eu_member to skip non-EU lines."""
    invoice = _valid_invoice(
        counterparty_country="US",
        counterparty_tax_id="US123456789",
    )
    assert invoice.counterparty_country == "US"
    assert invoice.counterparty_eu_member_state is None
    assert invoice.counterparty_is_eu_member is False


def test_invoice_iva_classification_for_line_returns_substrate_typed_record() -> None:
    """Invoice.iva_classification_for_line(line) returns the canonical
    substrate-grounded triple (IvaCategory + IvaRateKind +
    IvaFlowDirection) bundled in IvaInvoiceClassification — the typed
    record downstream filing surfaces consume."""
    from ...iva import (
        IvaCategory,
        IvaFlowDirection,
        IvaRateKind,
        IvaSettlementSide,
    )
    from .. import IvaInvoiceClassification

    line = _valid_line(iva_rate=IvaRate.RATE_21)
    invoice = _valid_invoice(lines=(line,))

    classification = invoice.iva_classification_for_line(line)
    assert isinstance(classification, IvaInvoiceClassification)
    assert classification.category is IvaCategory.DOMESTIC_GENERAL_21
    assert classification.rate_kind is IvaRateKind.GENERAL
    assert classification.flow_direction is IvaFlowDirection.REPERCUTIDO
    assert classification.settlement_sides == frozenset({IvaSettlementSide.DEVENGADA})


def test_invoice_iva_classification_received_invoice_resolves_to_soportado() -> None:
    """A received invoice routes lines to SOPORTADO (input IVA / cuotas
    deducibles per LIVA art 92), regardless of rate slot."""
    from ...iva import IvaFlowDirection, IvaSettlementSide

    line = _valid_line(iva_rate=IvaRate.RATE_10)
    invoice = _valid_invoice(
        kind=InvoiceKind.RECEIVED,
        invoice_number="BILL-001",
        counterparty_name="Proveedor SL",
        lines=(line,),
    )

    classification = invoice.iva_classification_for_line(line)
    assert classification.flow_direction is IvaFlowDirection.SOPORTADO
    assert classification.settlement_sides == frozenset({IvaSettlementSide.DEDUCIBLE})


def test_invoice_counterparty_eu_member_state_handles_lowercase_input_via_uppercase_storage() -> None:
    """counterparty_country normalises to uppercase at validation time
    (validate_country_code). The eu_member_state accessor lowercases
    again for substrate enum lookup. Round-trip works regardless of
    input case."""
    from ...iva import EUMemberState

    invoice = _valid_invoice(
        counterparty_country="fr",  # input lowercase
        counterparty_tax_id="FR12345678901",
    )
    assert invoice.counterparty_country == "FR"  # stored uppercase
    assert invoice.counterparty_eu_member_state is EUMemberState.FR


def test_invoice_iva_category_is_typed_as_iva_category_substrate_enum() -> None:
    """Invoice.iva_category is now strongly-typed IvaCategory | None
    instead of free-form str | None. Pydantic coerces string inputs
    (the historical persistence shape) into IvaCategory members and
    serializes them back to their string values, so existing
    serialization round-trips remain valid."""
    from ...iva import IvaCategory

    invoice = _valid_invoice()
    # Default value is None
    assert invoice.iva_category is None

    # String input coerces to IvaCategory
    invoice = Invoice.model_validate(
        {
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
            "iva_category": "domestic_general_21",  # string input
        },
    )
    assert invoice.iva_category is IvaCategory.DOMESTIC_GENERAL_21
    # JSON round-trip preserves the enum value as its string form
    json_dump = invoice.model_dump(mode="json")
    assert json_dump["iva_category"] == "domestic_general_21"


def test_invoice_iva_category_rejects_unknown_string() -> None:
    """An unknown iva_category string must fail validation now that the
    field is typed against the closed IvaCategory enum."""
    with pytest.raises(ValidationError, match=r"iva_category must be an IvaCategory"):
        Invoice.model_validate(
            {
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


def test_invoice_rejects_invalid_issued_at_without_typeerror_escape() -> None:
    """Invalid date input must stay inside the pydantic validation boundary."""
    with pytest.raises(ValidationError, match=r"not-a-date.*not a valid ISO-8601 date"):
        Invoice.model_validate(
            {
                "kind": InvoiceKind.ISSUED,
                "invoice_number": "INV-001",
                "issued_at": "not-a-date",
                "counterparty_name": "Cliente SL",
                "counterparty_tax_id": "B12345674",
                "counterparty_country": "ES",
                "base_total": Decimal("100"),
                "iva_total": Decimal("21"),
                "grand_total": Decimal("121"),
                "currency": "EUR",
                "lines": (_valid_line(),),
                "payment_status": PaymentStatus.PAID,
            },
        )


def test_invoice_rejects_unknown_kind_with_domain_validation_message() -> None:
    """Unknown invoice kind strings must fail as invoice-domain validation."""
    with pytest.raises(ValidationError, match=r"kind must be an InvoiceKind"):
        Invoice.model_validate(
            {
                "kind": "bogus-kind",
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
            },
        )


def test_iva_rate_percentage_is_resolved_against_centralized_iva_substrate() -> None:
    """iva_rate_percentage must derive its values from registry/aeat/iva/rates.toml.

    The helper carries no hardcoded ``RATE_21 -> 0.21`` literal; every
    numeric slot is resolved against :func:`aeat.domain.iva.lookup_rate`
    for Spain at a given date.
    """
    from ...iva import EUMemberState, IvaRateKind, lookup_rate
    from .._enums import iva_rate_percentage

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
    # wraps the raise into ValidationError at the model boundary. Pin
    # both the wrapping class and the underlying message substring so the
    # contract surface is stable.
    with pytest.raises(ValidationError, match=r"tax identifier must be 9 characters long"):
        _valid_invoice(counterparty_country="ES", counterparty_tax_id="INVALID")


def test_invoice_validates_iva_prefix_for_non_es_country() -> None:
    """Non-ES counterparties must carry a IVA number with the country prefix."""
    invoice = _valid_invoice(counterparty_country="DE", counterparty_tax_id="DE123456789")
    assert invoice.counterparty_tax_id == "DE123456789"
    with pytest.raises(ValidationError, match=r"IVA number must start with the counterparty country ISO-2 prefix"):
        _valid_invoice(counterparty_country="DE", counterparty_tax_id="123456789")


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


def test_numeric_iva_rate_percentages_value() -> None:
    """The helper returns exactly the four canonical integer percentages.

    This literal set is the external anchor — ``{0, 4, 10, 21}`` as
    ``Decimal`` — grounded in the LIVA art. 90/91 slot taxonomy.
    """
    assert numeric_iva_rate_percentages() == frozenset({Decimal("0"), Decimal("4"), Decimal("10"), Decimal("21")})


def test_numeric_iva_rate_percentages_cardinality_tracks_rate_members() -> None:
    """The set cardinality equals the count of ``RATE_*`` enum members.

    Derivation test: if a new ``RATE_<n>`` slot is added to
    :class:`IvaRate` the helper must pick it up without code changes.
    """
    rate_members = [m for m in IvaRate if m.value.startswith("RATE_")]
    assert len(numeric_iva_rate_percentages()) == len(rate_members)


def test_numeric_iva_rate_percentages_excludes_exempt_and_not_subject() -> None:
    """EXEMPT and NOT_SUBJECT must not contribute a percentage to the set."""
    result = numeric_iva_rate_percentages()
    # These two members carry no numeric percentage; they must not appear.
    assert IvaRate.EXEMPT not in {str(p) for p in result}
    assert IvaRate.NOT_SUBJECT not in {str(p) for p in result}
    # Structural check: the non-RATE_ members must not widen the set.
    non_rate_count = sum(1 for m in IvaRate if not m.value.startswith("RATE_"))
    rate_count = sum(1 for m in IvaRate if m.value.startswith("RATE_"))
    assert len(result) == rate_count
    assert len(result) < len(IvaRate)
    assert non_rate_count > 0  # guards against the guard itself becoming vacuous
