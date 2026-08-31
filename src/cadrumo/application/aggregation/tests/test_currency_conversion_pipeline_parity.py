"""Parity: every ledger aggregation pipeline reads a converted EUR figure.

Real defect, reproduced against production code: ``is_non_eur_without_conversion``
returns ``False`` for a foreign-currency row whose conversion was already applied
at import (``value_in_eur`` populated) -- correctly, that row is eligible. Three
callers then read ``transaction.raw.amount`` (or ``taxable_base`` /
``iva_amount``, both denominated in the row's NATIVE currency -- see
``domain.transactions.tests.test_gross_invariant``) instead of the converted
EUR figure, so a converted USD row entered a filed casilla at its native
magnitude instead of its EUR equivalent.

This module builds ONE converted USD transaction (``fx_rate``/``value_in_eur``
populated exactly as import populates them) and pushes it through the real
production classification function for every pipeline that gates on
``is_non_eur_without_conversion``:

- ``_renta_ledger._classify_renta_transaction`` (M100 first-slice expense) --
  PARTIALLY correct until this module's own coverage gap was found and
  closed. ``gross_amount`` always read ``effective_eur_amount`` correctly, but
  the ``taxable_base``/``iva_amount`` fallback (``_taxable_base_for`` /
  ``_iva_amount_for``, reached whenever a row carries no linked invoice
  evidence) fell back to the raw native fields, and ``_deductible_basis_amount``
  (domain/renta/_ledger_expenses.py) PREFERS that native ``taxable_base`` over
  the correctly-converted ``gross_amount`` whenever it is set -- the common
  case. The first version of this test module only ever built a transaction
  with no ``taxable_base``, so it exercised only the one path that was already
  correct and passed for the wrong reason. It now covers the taxable_base
  fallback explicitly (see
  ``test_renta_ledger_m100_expense_taxable_base_fallback_is_converted``) and the
  linked-invoice-evidence path (see
  ``test_renta_ledger_m100_expense_linked_invoice_evidence_is_converted``),
  which had the same native-read defect one level up: it read
  ``invoice.base_total``/``invoice.iva_total`` (native) instead of the
  ``invoice.base_total_eur``/``invoice.iva_total_eur`` properties that already
  exist on ``Invoice`` for exactly this purpose (and are used correctly in
  ``_invoice_retencion.py``). Both are fixed here.
- ``_iva_transaction._substrate_admission_issue`` (IVA ledger) -- already
  correct, refuses a converted row outright because its tax substrate
  (``taxable_base``/``iva_amount``) stays native-currency; this is a
  defensible POLICY, not the bug, and this module does not weaken it.
- ``_renta_income_ledger._classify_income_transaction`` (M130 casilla 01) --
  fixed here.
- ``_renta_gasto_ledger._classify_gasto_transaction`` (M130 casilla 02) --
  fixed here.
- ``_impatriado_income_ledger._classify_impatriado_income_transaction``
  (impatriado base) -- fixed here.

A wider sweep of ``application/`` for the same SHAPE -- any native-currency
read for a EUR-denominated purpose, not just these five sites -- found two
more, on the Invoice/InvoiceLine side rather than Transaction:

- ``_modelo_bindings.py`` (M303 general IVA screen,
  ``_screened_invoice_line_observations`` and its dispatch tree) built every
  ``IvaLedgerObservation`` straight from ``line.subtotal``/``line.iva_amount``
  -- native to ``invoice.currency`` -- with NO currency check anywhere in the
  file. Fixed here (see
  ``test_modelo_bindings_iva_screen_converts_invoice_line_amounts``).
- ``_oss_ioss.py`` (M369 OSS/IOSS, ``_candidate_for_invoice_line``) had the
  identical defect. OSS/IOSS is cross-border EU B2C by definition, where
  invoicing in the destination Member State's own currency is the ORDINARY
  case, making this the highest-probability trigger of the whole class. Fixed
  here (see ``test_oss_ioss_candidate_converts_invoice_line_amounts``).

Neither ``InvoiceLine`` nor its consumers had an EUR-safe accessor to route
through (unlike ``Invoice``, which already carries six: ``base_total_eur``,
``iva_total_eur``, ``grand_total_eur``, ``retention_amount_eur``,
``recargo_amount_eur``, ``suplido_amount_eur``), so
:meth:`~domain.invoices.Invoice.line_amount_eur` was added as the LINE-level
mirror of that exact mechanism (same ``fx_rate`` multiplier, delegating to the
same private ``_in_eur`` helper the six invoice-level properties already use)
before fixing either call site.

Anti-tautology: every WRONG-then-fixed assertion below encodes the CONVERTED
figure, never the native one, so a regression that reverts to
``raw.amount``/``taxable_base``/``line.subtotal`` un-converted reproduces the
exact wrong figure this module was written to catch. Confirmed for all seven
fixed sites by temporarily reverting the production fixes (``git stash`` where
the shared worktree's git index was free, a lock-free swap to the committed
HEAD content where it was contended) and re-running: every FIXED test below
failed for the predicted reason -- the three currency-predicate sites on the
exact wrong 1000.00, the taxable_base fallback on native 826.45 instead of
743.8050, the linked invoice-evidence path on a false AMOUNT_MISMATCH
over-refusal (comparing a converted 1089.00 EUR transaction amount against a
native 1210.00 invoice total), and the two invoice-line sites on native
1000.00/210.00 instead of converted 900.00/189.00 -- while the comparator
tests stayed green throughout.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core.period import Period
from ....core.resources._registry import resources
from ....domain.categories.spending_category import SpendingCategory
from ....domain.invoices.enums import IvaRate, PaymentStatus
from ....domain.invoices.models import Invoice, InvoiceCatalogue, InvoiceLine
from ....domain.iva.classification import InvoiceKind, TransactionKind
from ....domain.iva.oss import OssIossRegime
from ....domain.iva.schema import IvaCashAccountingTreatment, IvaRateKind
from ....domain.renta._ledger_expenses import RentaDeductibilityContext, RentaDeductibleExpenseObservation
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from .._impatriado_income_ledger import (
    ImpatriadoIncomeLedgerAggregationIssue,
    _classify_impatriado_income_transaction,
)
from .._iva_ledger import IvaLedgerAggregationIssueReason
from .._iva_transaction import _substrate_admission_issue
from .._modelo_bindings_invoice_iva import _screened_invoice_line_observations
from .._oss_ioss import _candidate_for_invoice_line
from .._renta_gasto_ledger import RentaGastoLedgerAggregationIssue, _classify_gasto_transaction
from .._renta_income_ledger import RentaIncomeLedgerAggregationIssue, _classify_income_transaction
from .._renta_ledger import RentaLedgerAggregationIssue, _classify_renta_transaction

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2026, 4, 6, 12, 0, tzinfo=UTC)

# USD converted at 0.90: fx_rate/value_in_eur populated exactly as
# CurrencyNormalizationService populates them at import (see test_fx_conversion.py).
_NATIVE_AMOUNT = Decimal("1000.00")
_FX_RATE = Decimal("0.90")
_CONVERTED_EUR = Decimal("900.00")


def _raw(*, direction_label: str) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=f"row-parity-{direction_label}",
        booked_date=date(2025, 2, 10),
        value_date=date(2025, 2, 10),
        amount=_NATIVE_AMOUNT,
        currency="USD",
        counterparty="US Client Inc",
        description="Converted USD row",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="f" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=_NOW,
            provider_name="manual",
        ),
        raw_fields={"Concepto": "Converted USD row"},
    )


def _converted_transaction(
    *,
    direction: TransactionDirection,
    category_id: str | None = None,
    taxable_base: Decimal | None = None,
    iva_amount: Decimal | None = None,
    irpf_category: str | None = None,
) -> Transaction:
    payload: dict[str, object] = {
        "raw": _raw(direction_label=direction.value),
        "direction": direction,
        "group_label": None,
        "source_jurisdiction": "ES",
        "business_classification": BusinessClassification.BUSINESS,
        "fx_rate": _FX_RATE,
        "value_in_eur": _CONVERTED_EUR,
        "rate_source": "ecb_reference",
        "rate_date": "2025-02-10",
    }
    if category_id is not None:
        payload["category_id"] = category_id
    if taxable_base is not None:
        payload["taxable_base"] = taxable_base
    if iva_amount is not None:
        payload["iva_amount"] = iva_amount
    if irpf_category is not None:
        payload["irpf_category"] = irpf_category
    return Transaction.model_validate(payload)


def test_renta_ledger_m100_expense_reads_converted_eur_amount() -> None:
    """Already-correct comparator: gross_amount is the converted 900.00, not 1000.00."""
    tx = _converted_transaction(
        direction=TransactionDirection.OUTGOING,
        category_id=SpendingCategory.CUOTAS_AUTONOMOS_SS.value,
    )
    result = _classify_renta_transaction(
        tx,
        invoices=InvoiceCatalogue(),
        bucket_id="parity-bucket",
        resolved_period=Period.from_year_and_code(2025, "0A"),
        resolved_profile_year=2025,
        profiles=resources().category_profiles.get(2025),
        region_overrides={},
        context=RentaDeductibilityContext(profile_year=2025),
        activity_key="activity-1",
    )
    assert isinstance(result, RentaDeductibleExpenseObservation), result
    assert result.gross_amount == _CONVERTED_EUR
    assert result.gross_amount != _NATIVE_AMOUNT


def test_renta_ledger_m100_expense_taxable_base_fallback_is_converted() -> None:
    """FIXED: the taxable_base fallback (no linked invoice) is EUR-converted.

    This is the coverage gap the original comparator test missed: without a
    ``taxable_base`` on the transaction, ``_deductible_basis_amount`` falls
    back to the already-correct ``gross_amount`` and the bug never surfaces.
    Setting one exercises ``_taxable_base_for``'s native fallback, which
    ``_deductible_basis_amount`` PREFERS over gross_amount -- so this is the
    common case, not an edge case.
    """
    tx = _converted_transaction(
        direction=TransactionDirection.OUTGOING,
        category_id=SpendingCategory.CUOTAS_AUTONOMOS_SS.value,
        taxable_base=Decimal("826.45"),
    )
    result = _classify_renta_transaction(
        tx,
        invoices=InvoiceCatalogue(),
        bucket_id="parity-bucket",
        resolved_period=Period.from_year_and_code(2025, "0A"),
        resolved_profile_year=2025,
        profiles=resources().category_profiles.get(2025),
        region_overrides={},
        context=RentaDeductibilityContext(profile_year=2025),
        activity_key="activity-1",
    )
    assert isinstance(result, RentaDeductibleExpenseObservation), result
    # CUOTAS_AUTONOMOS_SS is FULL_DEDUCTIBLE, so deductible_amount == the basis exactly.
    assert result.deductible_amount == Decimal("826.45") * _FX_RATE
    assert result.deductible_amount != Decimal("826.45")


def test_renta_ledger_m100_expense_linked_invoice_evidence_is_converted() -> None:
    """FIXED: a linked foreign-currency invoice's totals are EUR-converted.

    Before the fix, ``_purchase_invoice_evidence_payload`` compared the
    caller's already-converted transaction amount against the invoice's
    NATIVE ``grand_total`` -- a legitimate matched pair mismatches under that
    comparison, so the evidence is over-refused (AMOUNT_MISMATCH) rather than
    silently mis-computed. And even a matched invoice fed native
    ``base_total``/``iva_total`` downstream instead of the ``_eur``
    properties that already exist on ``Invoice`` for this purpose.
    """
    tx_provisional = _converted_transaction(
        direction=TransactionDirection.OUTGOING,
        category_id=SpendingCategory.CUOTAS_AUTONOMOS_SS.value,
    )
    # A separate native amount from the module-level fixture (this test builds
    # its own linked invoice pair), so transaction_id is dropped and re-derived
    # from the mutated raw rather than carrying the stale hash forward.
    dumped = tx_provisional.model_dump(mode="python")
    dumped.pop("transaction_id")
    dumped["raw"] = {**tx_provisional.raw.model_dump(mode="python"), "amount": Decimal("1210.00")}
    dumped["value_in_eur"] = Decimal("1089.00")
    tx_provisional = Transaction.model_validate(dumped)
    tx_id = tx_provisional.transaction_id
    base_total_native = Decimal("1000.00")
    iva_total_native = Decimal("210.00")
    line = InvoiceLine(
        description="Asesoria fiscal",
        quantity=Decimal("1"),
        unit_price=base_total_native,
        subtotal=base_total_native,
        iva_rate=IvaRate.RATE_21,
        iva_amount=iva_total_native,
    )
    invoice = Invoice.model_validate(
        {
            "bucket_id": "parity-bucket",
            "kind": InvoiceKind.RECEIVED,
            "invoice_number": "INV-USD-PARITY-1",
            "issued_at": date(2025, 2, 10),
            "counterparty_name": "Proveedor SL",
            "counterparty_tax_id": "B12345674",
            "counterparty_country": "ES",
            "base_total": base_total_native,
            "iva_total": iva_total_native,
            "grand_total": Decimal("1210.00"),
            "currency": "USD",
            "fx_rate": _FX_RATE,
            "fx_rate_date": date(2025, 2, 10),
            "fx_rate_source": "ecb_reference",
            "lines": (line,),
            "payment_status": PaymentStatus.PAID,
            "linked_transaction_ids": (tx_id,),
        },
    )
    invoices = InvoiceCatalogue.from_invoices((invoice,))
    tx = Transaction.model_validate(
        {**tx_provisional.model_dump(mode="python"), "purchase_invoice_evidence_id": invoice.invoice_id},
    )
    result = _classify_renta_transaction(
        tx,
        invoices=invoices,
        bucket_id="parity-bucket",
        resolved_period=Period.from_year_and_code(2025, "0A"),
        resolved_profile_year=2025,
        profiles=resources().category_profiles.get(2025),
        region_overrides={},
        context=RentaDeductibilityContext(profile_year=2025),
        activity_key="activity-1",
    )
    assert not isinstance(result, RentaLedgerAggregationIssue), result
    assert isinstance(result, RentaDeductibleExpenseObservation), result
    assert result.taxable_base == base_total_native * _FX_RATE
    assert result.iva_amount == iva_total_native * _FX_RATE
    assert result.taxable_base != base_total_native


def test_iva_ledger_refuses_converted_row_rather_than_reading_native_substrate() -> None:
    """Already-correct comparator: IVA refuses converted rows outright (defensible policy).

    Not the same bug: the tax substrate (taxable_base/iva_amount) stays
    native-currency even after conversion, so IVA correctly has no EUR figure
    to trust and refuses rather than silently mis-reading it.
    """
    tx = _converted_transaction(
        direction=TransactionDirection.OUTGOING,
        taxable_base=Decimal("826.45"),
        iva_amount=Decimal("173.55"),
    )
    issue = _substrate_admission_issue(
        tx,
        resolved_period=Period.from_year_and_code(2025, "1T"),
        operation_date=date(2025, 2, 10),
        cash_treatment=IvaCashAccountingTreatment.NONE,
    )
    assert issue is not None
    assert issue.reason is IvaLedgerAggregationIssueReason.MISSING_EUR_TAX_SUBSTRATE


def test_renta_income_ledger_reads_converted_eur_amount() -> None:
    """FIXED: gross_amount is the converted 900.00, not the native 1000.00."""
    tx = _converted_transaction(
        direction=TransactionDirection.INCOMING,
        irpf_category="actividad_economica",
    )
    result = _classify_income_transaction(
        tx,
        invoices=InvoiceCatalogue(),
        bucket_id="parity-bucket",
        cumulative_start=date(2025, 1, 1),
        cumulative_end=date(2025, 3, 31),
    )
    assert not isinstance(result, RentaIncomeLedgerAggregationIssue), result
    assert result is not None
    assert result.gross_amount == _CONVERTED_EUR
    assert result.gross_amount != _NATIVE_AMOUNT


def test_renta_gasto_ledger_reads_converted_eur_substrate() -> None:
    """FIXED: deductible_amount derives from the EUR-converted substrate."""
    tx = _converted_transaction(
        direction=TransactionDirection.OUTGOING,
        taxable_base=Decimal("826.45"),
        iva_amount=Decimal("173.55"),
        irpf_category="actividad_economica",
    )
    result = _classify_gasto_transaction(
        tx,
        cumulative_start=date(2025, 1, 1),
        cumulative_end=date(2025, 3, 31),
    )
    assert not isinstance(result, RentaGastoLedgerAggregationIssue), result
    assert result is not None
    # 826.45 * 0.90 == 743.8050; the un-fixed native sum (826.45+173.55=1000.00) is refused.
    assert result.deductible_amount == Decimal("826.45") * _FX_RATE
    assert result.deductible_amount != Decimal("1000.00")


def test_impatriado_income_ledger_reads_converted_eur_amount() -> None:
    """FIXED: gross_amount is the converted 900.00, not the native 1000.00."""
    tx = _converted_transaction(
        direction=TransactionDirection.INCOMING,
        irpf_category="actividad_economica",
    )
    result = _classify_impatriado_income_transaction(
        tx,
        window_start=date(2025, 1, 1),
        window_end=date(2025, 12, 31),
    )
    assert not isinstance(result, ImpatriadoIncomeLedgerAggregationIssue), result
    assert result is not None
    assert result.gross_amount == _CONVERTED_EUR
    assert result.gross_amount != _NATIVE_AMOUNT


def _converted_usd_invoice(
    *,
    kind: InvoiceKind,
    counterparty_country: str,
    counterparty_tax_id: str,
    base_total: Decimal,
    iva_total: Decimal,
    oss_ioss_regime: OssIossRegime | None = None,
    oss_transaction_kind: TransactionKind | None = None,
    oss_rate_kind: IvaRateKind | None = None,
) -> tuple[Invoice, InvoiceLine]:
    line = InvoiceLine(
        description="Servicio",
        quantity=Decimal("1"),
        unit_price=base_total,
        subtotal=base_total,
        iva_rate=IvaRate.RATE_21,
        iva_amount=iva_total,
        oss_rate_kind=oss_rate_kind,
    )
    invoice = Invoice.model_validate(
        {
            "bucket_id": "parity-bucket",
            "kind": kind,
            "invoice_number": "INV-LINE-EUR-PARITY-1",
            "issued_at": date(2025, 2, 10),
            "counterparty_name": "Counterparty",
            "counterparty_tax_id": counterparty_tax_id,
            "counterparty_country": counterparty_country,
            "base_total": base_total,
            "iva_total": iva_total,
            "grand_total": base_total + iva_total,
            "currency": "USD",
            "fx_rate": _FX_RATE,
            "fx_rate_date": date(2025, 2, 10),
            "fx_rate_source": "ecb_reference",
            "lines": (line,),
            "payment_status": PaymentStatus.PAID,
            "oss_ioss_regime": oss_ioss_regime,
            "oss_transaction_kind": oss_transaction_kind,
        },
    )
    return invoice, line


def test_modelo_bindings_iva_screen_converts_invoice_line_amounts() -> None:
    """FIXED: the M303 general IVA screen reads EUR, not native invoice-line amounts.

    ``_modelo_bindings.py`` built every ``IvaLedgerObservation`` straight from
    ``line.subtotal``/``line.iva_amount`` with no currency check anywhere in
    the file, feeding M303's IVA aggregation at the invoice's native
    magnitude.
    """
    base_total_native = Decimal("1000.00")
    iva_total_native = Decimal("210.00")
    invoice, _line = _converted_usd_invoice(
        kind=InvoiceKind.ISSUED,
        counterparty_country="ES",
        counterparty_tax_id="B12345674",
        base_total=base_total_native,
        iva_total=iva_total_native,
    )
    observations = _screened_invoice_line_observations(
        invoice,
        devengo_date=date(2025, 2, 10),
        deduction_authority=None,
    )
    assert len(observations) == 1
    observation = observations[0]
    assert observation.base_amount == base_total_native * _FX_RATE
    assert observation.iva_amount == iva_total_native * _FX_RATE
    assert observation.base_amount != base_total_native


def test_oss_ioss_candidate_converts_invoice_line_amounts() -> None:
    """FIXED: an OSS/IOSS candidate is EUR, not the invoice's native magnitude.

    OSS/IOSS is cross-border EU B2C by definition, where invoicing in the
    destination Member State's own currency is the ORDINARY case -- the
    highest-probability trigger of the whole native-read defect class.
    """
    base_total_native = Decimal("1000.00")
    iva_total_native = Decimal("210.00")
    invoice, line = _converted_usd_invoice(
        kind=InvoiceKind.ISSUED,
        counterparty_country="PL",
        counterparty_tax_id="PL1234567890",
        base_total=base_total_native,
        iva_total=iva_total_native,
        oss_ioss_regime=OssIossRegime.UNION_SCHEME,
        oss_transaction_kind=TransactionKind.OSS_UNION_SERVICES,
        oss_rate_kind=IvaRateKind.GENERAL,
    )
    candidate = _candidate_for_invoice_line(invoice, line, line_index=1, devengo_date=date(2025, 2, 10))
    assert candidate is not None
    assert candidate.base_amount == base_total_native * _FX_RATE
    assert candidate.iva_amount == iva_total_native * _FX_RATE
    assert candidate.base_amount != base_total_native
