"""Real-behavior tests for the ``gross == base + iva + recargo`` invariant.

The :class:`cadrumo.domain.transactions.Transaction` model enforces, to the euro
cent, that a populated tax substrate reconstitutes the IVA-inclusive gross —
but only when **both** ``taxable_base`` and ``iva_amount`` are present. Rows
with an unset tax substrate (the common case) must validate unconditionally.

The recargo de equivalencia surcharge is *inside* that gross and the IRPF
retención is *outside* it, which is the axis most of this module turns on: the
withholding relaxations below all fire when the substrate exceeds the cash,
while a recargo row's substrate sits level with a cash movement that includes
the surcharge.

Authority: LLM ledger classification contract; LIVA art. 161 (recargo de
equivalencia); RIRPF art. 95 (retención sobre ingresos íntegros).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from ...iva import IvaCategory
from ..enums import BusinessClassification, TransactionDirection
from ..irpf_categories import ledger_irpf_category, normalize_irpf_category
from ..models import Transaction
from ..raw_transaction import RawProvenance, RawTransaction, SourceFormat

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_NOW = datetime(2026, 4, 6, 12, 0, tzinfo=UTC)


def _raw(*, amount: Decimal, currency: str = "EUR") -> RawTransaction:
    return RawTransaction(
        provider_transaction_id="row-invariant",
        booked_date=date(2025, 2, 10),
        value_date=date(2025, 2, 10),
        amount=amount,
        currency=currency,
        counterparty="Contraparte SL",
        description="Compra",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="e" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=_NOW,
            provider_name="manual",
        ),
        raw_fields={"Concepto": "Compra"},
    )


def test_all_none_tax_substrate_validates() -> None:
    """A row with no tax substrate set must validate (the common case)."""
    tx = Transaction.model_validate(
        {
            "raw": _raw(amount=Decimal("121.00")),
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
        },
    )
    assert tx.taxable_base is None
    assert tx.iva_amount is None


def test_consistent_triple_validates_against_magnitude_gross() -> None:
    """base + iva == gross magnitude to the cent is accepted (amount is non-negative)."""
    tx = Transaction.model_validate(
        {
            "raw": _raw(amount=Decimal("121.00")),
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "taxable_base": Decimal("100.00"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("21.00"),
        },
    )
    assert tx.taxable_base == Decimal("100.00")
    assert tx.iva_amount == Decimal("21.00")


def test_professional_income_net_of_irpf_withholding_validates() -> None:
    """Professional income can keep invoice base/IVA when the bank receipt is net.

    A Spanish professional invoice for 2000.00 + 420.00 IVA with 300.00 IRPF
    withheld lands as a 2120.00 bank receipt. The ledger must preserve the
    invoice substrate so IVA and Renta aggregations can read the declared base
    and cuota instead of losing those facts.
    """
    tx = Transaction.model_validate(
        {
            "raw": _raw(amount=Decimal("2120.00")),
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "taxable_base": Decimal("2000.00"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("420.00"),
            "irpf_category": "actividad_economica",
        },
    )

    assert tx.raw.amount == Decimal("2120.00")
    assert tx.taxable_base is not None
    assert tx.iva_amount is not None
    assert tx.taxable_base + tx.iva_amount == Decimal("2420.00")
    assert tx.taxable_base + tx.iva_amount > tx.raw.amount


def test_professional_service_expense_paid_net_of_irpf_withholding_validates() -> None:
    """A paid professional invoice can keep the supplier invoice base/IVA.

    Javier repro: 1000.00 base + 210.00 IVA with 150.00 IRPF withheld is paid
    as a 1060.00 bank movement. The cash amount must stay net while the row
    preserves the full invoice substrate for IVA and expense aggregation.
    """
    tx = Transaction.model_validate(
        {
            "raw": _raw(amount=Decimal("1060.00")),
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "category_id": "asesoria_fiscal",
            "taxable_base": Decimal("1000.00"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("210.00"),
            "irpf_category": "actividad_economica",
        },
    )

    assert tx.raw.amount == Decimal("1060.00")
    assert tx.category_id == "asesoria_fiscal"
    assert tx.taxable_base is not None
    assert tx.iva_amount is not None
    assert tx.taxable_base + tx.iva_amount == Decimal("1210.00")
    assert tx.taxable_base + tx.iva_amount > tx.raw.amount


def test_activity_income_base_cash_is_not_inferred_as_iva_sized_withholding() -> None:
    """A base-only cash receipt plus IVA must not become a fake M130 retention.

    Persona repro: a professional enters a 2000.00 invoice base as the bank
    movement amount and also records 420.00 IVA. That 420.00 delta is IVA-sized
    and must not be accepted as IRPF withholding for casilla 06.
    """
    with pytest.raises(ValidationError, match="inferred IRPF withholding exceeds"):
        Transaction.model_validate(
            {
                "raw": _raw(amount=Decimal("2000.00")),
                "direction": TransactionDirection.INCOMING,
                "group_label": None,
                "source_jurisdiction": "ES",
                "business_classification": BusinessClassification.BUSINESS,
                "taxable_base": Decimal("2000.00"),
                "iva_rate": Decimal("0.21"),
                "iva_amount": Decimal("420.00"),
                "irpf_category": "actividad_economica",
            },
        )


def test_professional_service_base_cash_is_not_inferred_as_iva_sized_withholding() -> None:
    """Paid professional-service cash equal to base must not become retencion."""
    with pytest.raises(ValidationError, match="inferred IRPF withholding exceeds"):
        Transaction.model_validate(
            {
                "raw": _raw(amount=Decimal("1000.00")),
                "direction": TransactionDirection.OUTGOING,
                "group_label": None,
                "source_jurisdiction": "ES",
                "business_classification": BusinessClassification.BUSINESS,
                "category_id": "asesoria_fiscal",
                "taxable_base": Decimal("1000.00"),
                "iva_rate": Decimal("0.21"),
                "iva_amount": Decimal("210.00"),
                "irpf_category": "actividad_economica",
            },
        )


def test_rent_expense_paid_net_of_withholding_validates() -> None:
    """Rent paid net of withholding keeps the supplier invoice base/IVA.

    Persona repro: local rent invoice 1000.00 + 210.00 IVA with 190.00
    withholding is paid as a 1020.00 bank movement. Modelo 303 still needs
    the full 210.00 IVA soportado substrate, so the ledger must not force the
    bank cash amount to equal base + IVA for this scoped rent withholding case.
    """
    tx = Transaction.model_validate(
        {
            "raw": _raw(amount=Decimal("1020.00")),
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "category_id": "arrendamiento_local",
            "taxable_base": Decimal("1000.00"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("210.00"),
            "irpf_category": "arrendamiento_local",
        },
    )

    assert tx.raw.amount == Decimal("1020.00")
    assert tx.category_id == "arrendamiento_local"
    assert tx.taxable_base is not None
    assert tx.iva_amount is not None
    assert tx.taxable_base + tx.iva_amount == Decimal("1210.00")
    assert tx.taxable_base + tx.iva_amount > tx.raw.amount


def test_rent_expense_paid_net_requires_irpf_category() -> None:
    """Rent expense net-cash relaxation requires an explicit withholding axis."""
    with pytest.raises(ValidationError, match=r"taxable_base \+ iva_amount") as raised:
        Transaction.model_validate(
            {
                "raw": _raw(amount=Decimal("1020.00")),
                "direction": TransactionDirection.OUTGOING,
                "group_label": None,
                "source_jurisdiction": "ES",
                "business_classification": BusinessClassification.BUSINESS,
                "category_id": "arrendamiento_local",
                "taxable_base": Decimal("1000.00"),
                "iva_rate": Decimal("0.21"),
                "iva_amount": Decimal("210.00"),
            },
        )
    assert all(fragment not in str(raised.value).lower() for fragment in ("aeat", "irpf_category", "ledger categories"))


def test_rent_expense_paid_net_requires_rental_irpf_category() -> None:
    """An unrelated non-work IRPF tag must not relax outgoing rent gross drift."""
    with pytest.raises(ValidationError, match=r"taxable_base \+ iva_amount") as raised:
        Transaction.model_validate(
            {
                "raw": _raw(amount=Decimal("1020.00")),
                "direction": TransactionDirection.OUTGOING,
                "group_label": None,
                "source_jurisdiction": "ES",
                "business_classification": BusinessClassification.BUSINESS,
                "category_id": "arrendamiento_local",
                "taxable_base": Decimal("1000.00"),
                "iva_rate": Decimal("0.21"),
                "iva_amount": Decimal("210.00"),
                "irpf_category": "actividad_economica",
            },
        )
    assert all(fragment not in str(raised.value).lower() for fragment in ("aeat", "irpf_category", "ledger categories"))


def test_outgoing_irpf_category_does_not_relax_non_rent_expense_gross() -> None:
    """IRPF tags alone must not unlock arbitrary outgoing invoice-gross drift."""
    with pytest.raises(ValidationError, match="must equal the gross to the cent"):
        Transaction.model_validate(
            {
                "raw": _raw(amount=Decimal("1020.00")),
                "direction": TransactionDirection.OUTGOING,
                "group_label": None,
                "source_jurisdiction": "ES",
                "business_classification": BusinessClassification.BUSINESS,
                "category_id": "material_oficina",
                "taxable_base": Decimal("1000.00"),
                "iva_rate": Decimal("0.21"),
                "iva_amount": Decimal("210.00"),
                "irpf_category": "arrendamiento_local",
            },
        )


def test_activity_irpf_category_does_not_relax_non_professional_expense_gross() -> None:
    """actividad_economica is scoped to professional-service expense categories."""
    with pytest.raises(ValidationError, match="must equal the gross to the cent"):
        Transaction.model_validate(
            {
                "raw": _raw(amount=Decimal("1020.00")),
                "direction": TransactionDirection.OUTGOING,
                "group_label": None,
                "source_jurisdiction": "ES",
                "business_classification": BusinessClassification.BUSINESS,
                "category_id": "material_oficina",
                "taxable_base": Decimal("1000.00"),
                "iva_rate": Decimal("0.21"),
                "iva_amount": Decimal("210.00"),
                "irpf_category": "actividad_economica",
            },
        )


def test_invoice_gross_above_cash_without_irpf_category_is_rejected() -> None:
    """The net-cash relaxation requires an explicit IRPF category."""
    with pytest.raises(ValidationError, match=r"taxable_base \+ iva_amount") as raised:
        Transaction.model_validate(
            {
                "raw": _raw(amount=Decimal("2120.00")),
                "direction": TransactionDirection.INCOMING,
                "group_label": None,
                "source_jurisdiction": "ES",
                "business_classification": BusinessClassification.BUSINESS,
                "taxable_base": Decimal("2000.00"),
                "iva_rate": Decimal("0.21"),
                "iva_amount": Decimal("420.00"),
            },
        )
    assert all(fragment not in str(raised.value).lower() for fragment in ("aeat", "irpf_category", "ledger categories"))


def test_work_irpf_category_does_not_relax_professional_invoice_gross() -> None:
    """Salary/work tags must not unlock invoice-gross validation."""
    with pytest.raises(ValidationError, match="must equal the gross to the cent"):
        Transaction.model_validate(
            {
                "raw": _raw(amount=Decimal("2120.00")),
                "direction": TransactionDirection.INCOMING,
                "group_label": None,
                "source_jurisdiction": "ES",
                "business_classification": BusinessClassification.BUSINESS,
                "taxable_base": Decimal("2000.00"),
                "iva_rate": Decimal("0.21"),
                "iva_amount": Decimal("420.00"),
                "irpf_category": "trabajo",
            },
        )


def test_irpf_category_does_not_accept_understated_invoice_gross() -> None:
    """Withholding may explain cash below invoice gross, never invoice gross below cash."""
    with pytest.raises(ValidationError, match="must equal the gross to the cent"):
        Transaction.model_validate(
            {
                "raw": _raw(amount=Decimal("2420.00")),
                "direction": TransactionDirection.INCOMING,
                "group_label": None,
                "source_jurisdiction": "ES",
                "business_classification": BusinessClassification.BUSINESS,
                "taxable_base": Decimal("2000.00"),
                "iva_rate": Decimal("0.21"),
                "iva_amount": Decimal("300.00"),
                "irpf_category": "actividad_economica",
            },
        )


def test_drifted_triple_is_rejected() -> None:
    """A triple that does not reconstitute the gross raises ValidationError."""
    with pytest.raises(ValidationError, match="must equal the gross to the cent"):
        Transaction.model_validate(
            {
                "raw": _raw(amount=Decimal("121.00")),
                "direction": TransactionDirection.OUTGOING,
                "group_label": None,
                "source_jurisdiction": "ES",
                "business_classification": BusinessClassification.BUSINESS,
                "taxable_base": Decimal("100.00"),
                "iva_rate": Decimal("0.21"),
                "iva_amount": Decimal("25.00"),
            },
        )


def test_base_present_but_iva_absent_validates() -> None:
    """The invariant fires only when both fields are present; base-only is fine."""
    tx = Transaction.model_validate(
        {
            "raw": _raw(amount=Decimal("121.00")),
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "taxable_base": Decimal("100.00"),
        },
    )
    assert tx.taxable_base == Decimal("100.00")
    assert tx.iva_amount is None


def test_invariant_uses_native_raw_amount_not_value_in_eur() -> None:
    """For a non-EUR row the gross reference is the native raw.amount.

    The tax substrate (taxable_base / iva_amount) is denominated in the
    row's native currency; the aggregation layer carries value_in_eur as a
    separate parallel EUR projection and does not apply fx_rate to the
    base or amount. So the invariant reconstitutes the native 100.00, not
    the 110.00 EUR conversion.
    """
    tx = Transaction.model_validate(
        {
            "raw": _raw(amount=Decimal("100.00"), currency="USD"),
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "fx_rate": Decimal("1.10"),
            "value_in_eur": Decimal("110.00"),
            "rate_source": "ecb_reference",
            "rate_date": "2025-02-10",
            "taxable_base": Decimal("82.64"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("17.36"),
        },
    )
    assert tx.value_in_eur == Decimal("110.00")
    assert tx.taxable_base is not None
    assert tx.iva_amount is not None
    assert tx.taxable_base + tx.iva_amount == Decimal("100.00")


def test_invariant_against_native_amount_rejects_eur_split() -> None:
    """A triple splitting the EUR value (not the native amount) is rejected."""
    with pytest.raises(ValidationError, match="must equal the gross to the cent"):
        Transaction.model_validate(
            {
                "raw": _raw(amount=Decimal("100.00"), currency="USD"),
                "direction": TransactionDirection.OUTGOING,
                "group_label": None,
                "source_jurisdiction": "ES",
                "business_classification": BusinessClassification.BUSINESS,
                "fx_rate": Decimal("1.10"),
                "value_in_eur": Decimal("110.00"),
                "rate_source": "ecb_reference",
                "rate_date": "2025-02-10",
                # Splits the 110.00 EUR value, not the 100.00 native gross.
                "taxable_base": Decimal("90.91"),
                "iva_rate": Decimal("0.21"),
                "iva_amount": Decimal("19.09"),
            },
        )


@pytest.mark.parametrize(
    "spelling",
    ["actividad_economica", "ACTIVIDAD_ECONOMICA", "Actividad_Economica", "  actividad_economica  "],
    ids=["canonical", "upper", "mixed", "padded"],
)
def test_activity_relaxation_reads_one_normalized_token(spelling: str) -> None:
    """Case and whitespace variants of the activity token unlock the same relaxation.

    The gross invariant resolved the raw token against the closed catalogue
    while the ledger preflight stripped and lowercased before matching, so the
    two surfaces disagreed on what ``ACTIVIDAD_ECONOMICA`` named: a legitimate
    activity receipt was refused here while the preflight classified it. Both
    now normalize through one catalogue resolver.
    """
    tx = Transaction.model_validate(
        {
            "raw": _raw(amount=Decimal("2120.00")),
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "taxable_base": Decimal("2000.00"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("420.00"),
            "irpf_category": spelling,
        },
    )

    assert tx.taxable_base is not None
    assert tx.iva_amount is not None
    assert tx.taxable_base + tx.iva_amount == Decimal("2420.00")


@pytest.mark.parametrize(
    "spelling",
    ["trabajo", "TRABAJO", "Trabajo", "  trabajo  "],
    ids=["canonical", "upper", "mixed", "padded"],
)
def test_employment_token_never_relaxes_the_invariant_in_any_spelling(spelling: str) -> None:
    """No spelling of the employment token unlocks the withholding relaxation.

    ``trabajo`` carries ``net_paid_invoice=False``: a nómina receipt has no
    invoice substrate to preserve. Normalising the token must not turn an
    unrecognised spelling into an accepted one by any route.
    """
    with pytest.raises(ValidationError, match="must equal the gross to the cent"):
        Transaction.model_validate(
            {
                "raw": _raw(amount=Decimal("2120.00")),
                "direction": TransactionDirection.INCOMING,
                "group_label": None,
                "source_jurisdiction": "ES",
                "business_classification": BusinessClassification.BUSINESS,
                "taxable_base": Decimal("2000.00"),
                "iva_rate": Decimal("0.21"),
                "iva_amount": Decimal("420.00"),
                "irpf_category": spelling,
            },
        )


def test_normalization_keeps_the_catalogue_closed() -> None:
    """Normalisation folds case and whitespace only; it never invents a category."""
    assert normalize_irpf_category("  ACTIVIDAD_ECONOMICA ") == "actividad_economica"
    assert normalize_irpf_category("actividad economica") == "actividad economica"
    assert normalize_irpf_category("   ") is None
    assert normalize_irpf_category(None) is None
    assert ledger_irpf_category("actividad economica", direction=TransactionDirection.INCOMING) is None
    assert ledger_irpf_category("bogus", direction=TransactionDirection.INCOMING) is None


# --- recargo de equivalencia (LIVA art. 161): inside the gross, never beside it ---
#
# The worked figures below are one supply at the general tier: base 1000.00,
# IVA 21 % = 210.00, recargo 5.2 % = 52.00, so the money that moves is 1262.00.
# Recording the surcharge outside that movement understates the cash by exactly
# the surcharge, which is the shape these tests refuse.

_RECARGO_BASE = Decimal("1000.00")
_RECARGO_IVA = Decimal("210.00")
_RECARGO_CUOTA = Decimal("52.00")
_RECARGO_GROSS = Decimal("1262.00")
_RECARGO_GROSS_WITHOUT_SURCHARGE = Decimal("1210.00")


def test_supplier_sale_under_recargo_reconstitutes_the_cash_it_received() -> None:
    """A supplier charging recargo receives base + IVA + recargo, and may record it.

    LIVA art. 161 has the surcharge repercutido on the entrega alongside the
    cuota, so the 1262.00 that reaches the supplier's account is the truthful
    gross for the row. Before the surcharge joined the identity this exact row --
    the only honest way to record the sale -- was the one the model refused.
    """
    tx = Transaction.model_validate(
        {
            "raw": _raw(amount=_RECARGO_GROSS),
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "taxable_base": _RECARGO_BASE,
            "iva_rate": Decimal("0.21"),
            "iva_amount": _RECARGO_IVA,
            "recargo_amount": _RECARGO_CUOTA,
        },
    )

    assert tx.recargo_amount == _RECARGO_CUOTA
    assert tx.taxable_base is not None
    assert tx.iva_amount is not None
    # The third operand is optional too; without this the sum raises on None
    # instead of the assertion reporting which component was missing.
    assert tx.recargo_amount is not None
    assert tx.taxable_base + tx.iva_amount + tx.recargo_amount == tx.raw.amount


def test_minorista_purchase_under_recargo_reconstitutes_the_cash_it_paid() -> None:
    """The retailer's side of the same supply is equally recordable.

    The comerciante minorista pays IVA + RE as non-deductible acquisition cost,
    so the surcharge is inside the payment exactly as it is inside the receipt.
    The identity is direction-agnostic and this pins that both halves of one real
    operation can be entered.
    """
    tx = Transaction.model_validate(
        {
            "raw": _raw(amount=_RECARGO_GROSS),
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "taxable_base": _RECARGO_BASE,
            "iva_rate": Decimal("0.21"),
            "iva_amount": _RECARGO_IVA,
            "recargo_amount": _RECARGO_CUOTA,
            "iva_category": IvaCategory.RECARGO_EQUIVALENCIA,
        },
    )

    assert tx.recargo_amount == _RECARGO_CUOTA
    assert tx.raw.amount == _RECARGO_GROSS


def test_declared_recargo_missing_from_the_gross_is_refused() -> None:
    """A surcharge charged but absent from the cash movement is a refusal.

    This is the inverse polarity of the test above, and the pair is the point:
    the model must accept the row whose cash includes the surcharge and refuse
    the row that declares the surcharge while understating the cash by it. A
    model that accepts only the second one does not merely fail to express the
    truth -- it selects for the falsehood.
    """
    with pytest.raises(ValidationError, match="must equal the gross to the cent"):
        Transaction.model_validate(
            {
                "raw": _raw(amount=_RECARGO_GROSS_WITHOUT_SURCHARGE),
                "direction": TransactionDirection.INCOMING,
                "group_label": None,
                "source_jurisdiction": "ES",
                "business_classification": BusinessClassification.BUSINESS,
                "taxable_base": _RECARGO_BASE,
                "iva_rate": Decimal("0.21"),
                "iva_amount": _RECARGO_IVA,
                "recargo_amount": _RECARGO_CUOTA,
            },
        )


def test_recargo_and_retencion_sit_on_opposite_sides_of_the_identity() -> None:
    """One row carrying both terms is the only case that catches a side swap.

    A row carrying just one of the two balances identically whichever side that
    term is on, so every single-term case above would survive a future
    simplification that moved either one. Here a modulos supplier sells to a
    retailer under recargo with 1 % retencion withheld at source (RIRPF art.
    95.6): the surcharge raises what the operation cost to 1262.00 and the
    withholding lowers what the bank transferred to 1252.00. Moving the recargo
    to the cash side would put the substrate below the cash, which no relaxation
    covers, so the swap reddens here and nowhere else.
    """
    retencion = Decimal("10.00")
    cash = _RECARGO_GROSS - retencion

    tx = Transaction.model_validate(
        {
            "raw": _raw(amount=cash),
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "taxable_base": _RECARGO_BASE,
            "iva_rate": Decimal("0.21"),
            "iva_amount": _RECARGO_IVA,
            "recargo_amount": _RECARGO_CUOTA,
            "irpf_category": "actividad_economica",
        },
    )

    assert tx.raw.amount == cash
    assert tx.taxable_base is not None
    assert tx.iva_amount is not None
    assert tx.recargo_amount is not None
    substrate = tx.taxable_base + tx.iva_amount + tx.recargo_amount
    assert substrate == _RECARGO_GROSS
    assert substrate - tx.raw.amount == retencion


def test_cash_above_substrate_without_recargo_names_the_surcharge_option() -> None:
    """The refusal must point an operator at the field that would explain the gap.

    Cash above the declared substrate is precisely the shape an unrecorded
    surcharge produces, and it is the one direction none of the withholding
    relaxations can explain. The refusal names the recargo option rather than
    reporting a bare arithmetic mismatch the operator has to decompose.
    """
    with pytest.raises(ValidationError, match="recargo de equivalencia"):
        Transaction.model_validate(
            {
                "raw": _raw(amount=_RECARGO_GROSS),
                "direction": TransactionDirection.OUTGOING,
                "group_label": None,
                "source_jurisdiction": "ES",
                "business_classification": BusinessClassification.BUSINESS,
                "taxable_base": _RECARGO_BASE,
                "iva_rate": Decimal("0.21"),
                "iva_amount": _RECARGO_IVA,
            },
        )


def test_self_assessed_acquisition_keeps_recargo_out_of_its_gross() -> None:
    """A self-liquidated acquisition pays the base alone, surcharge included.

    On a reverse-charge acquisition the supplier repercutes neither the cuota
    nor the surcharge -- the acquirer self-liquidates both -- so neither reaches
    the cash movement. The self-assessed branch therefore stays
    ``gross == taxable_base`` even when a recargo is recorded on the row, and
    this pins that the surcharge was not folded in there by reflex when it was
    folded into the general branch.
    """
    tx = Transaction.model_validate(
        {
            "raw": _raw(amount=_RECARGO_BASE),
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "taxable_base": _RECARGO_BASE,
            "iva_rate": Decimal("0.21"),
            "iva_amount": _RECARGO_IVA,
            "recargo_amount": _RECARGO_CUOTA,
            "iva_category": IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
        },
    )

    assert tx.raw.amount == _RECARGO_BASE
    assert tx.recargo_amount == _RECARGO_CUOTA
