"""Tests for the reusable IVA classification record."""

from __future__ import annotations

import pytest

from aeat.domain.invoices._enums import InvoiceKind, IvaRate
from aeat.domain.invoices._iva_classification import (
    IvaInvoiceClassification,
    classify_invoice_line_for_iva,
)
from aeat.domain.vat import (
    IvaFlowDirection,
    IvaSettlementSide,
    VATCategory,
    VATRateKind,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


@pytest.mark.parametrize(
    ("iva_rate", "expected_category", "expected_kind"),
    [
        (IvaRate.RATE_0, VATCategory.DOMESTIC_ZERO, VATRateKind.ZERO),
        (IvaRate.RATE_4, VATCategory.DOMESTIC_SUPER_REDUCED_4, VATRateKind.SUPER_REDUCED),
        (IvaRate.RATE_10, VATCategory.DOMESTIC_REDUCED_10, VATRateKind.REDUCED),
        (IvaRate.RATE_21, VATCategory.DOMESTIC_GENERAL_21, VATRateKind.GENERAL),
        (IvaRate.EXEMPT, VATCategory.DOMESTIC_EXEMPT, VATRateKind.EXEMPT),
    ],
)
def test_classify_issued_invoice_at_each_rate_slot_resolves_to_repercutido(
    iva_rate: IvaRate, expected_category: VATCategory, expected_kind: VATRateKind
) -> None:
    classification = classify_invoice_line_for_iva(
        iva_rate=iva_rate, invoice_kind=InvoiceKind.ISSUED
    )
    assert classification.category is expected_category
    assert classification.rate_kind is expected_kind
    assert classification.flow_direction is IvaFlowDirection.REPERCUTIDO
    assert classification.settlement_sides == frozenset({IvaSettlementSide.DEVENGADA})


@pytest.mark.parametrize(
    "iva_rate",
    [IvaRate.RATE_0, IvaRate.RATE_4, IvaRate.RATE_10, IvaRate.RATE_21, IvaRate.EXEMPT],
)
def test_classify_received_invoice_resolves_to_soportado(iva_rate: IvaRate) -> None:
    classification = classify_invoice_line_for_iva(
        iva_rate=iva_rate, invoice_kind=InvoiceKind.RECEIVED
    )
    assert classification.flow_direction is IvaFlowDirection.SOPORTADO
    assert classification.settlement_sides == frozenset({IvaSettlementSide.DEDUCIBLE})


def test_classify_invoice_rejects_not_subject_rate() -> None:
    """NOT_SUBJECT operations are out of scope of IVA — the standard-case
    helper rejects them so callers explicitly handle them via
    VATCategory.OPERACION_NO_SUJETA."""
    with pytest.raises(ValueError, match="NOT_SUBJECT"):
        classify_invoice_line_for_iva(
            iva_rate=IvaRate.NOT_SUBJECT, invoice_kind=InvoiceKind.ISSUED
        )


def test_classification_record_contributes_to_devengada_for_repercutido() -> None:
    classification = classify_invoice_line_for_iva(
        iva_rate=IvaRate.RATE_21, invoice_kind=InvoiceKind.ISSUED
    )
    assert classification.contributes_to_devengada is True
    assert classification.contributes_to_deducible is False
    assert classification.is_reverse_charge is False


def test_classification_record_contributes_to_deducible_for_soportado() -> None:
    classification = classify_invoice_line_for_iva(
        iva_rate=IvaRate.RATE_21, invoice_kind=InvoiceKind.RECEIVED
    )
    assert classification.contributes_to_devengada is False
    assert classification.contributes_to_deducible is True
    assert classification.is_reverse_charge is False


def test_classification_record_contributes_to_both_sides_for_autorepercutido() -> None:
    """Reverse-charge operations contribute to BOTH cornerstones on the
    same operation (LIVA art 84.Uno.2). Callers construct the record
    directly for these cases."""
    classification = IvaInvoiceClassification(
        category=VATCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
        rate_kind=VATRateKind.GENERAL,
        flow_direction=IvaFlowDirection.AUTOREPERCUTIDO,
        settlement_sides=frozenset(
            {IvaSettlementSide.DEVENGADA, IvaSettlementSide.DEDUCIBLE}
        ),
    )
    assert classification.contributes_to_devengada is True
    assert classification.contributes_to_deducible is True
    assert classification.is_reverse_charge is True


def test_classification_record_validates_settlement_sides_against_flow() -> None:
    """Constructor must reject inconsistent (flow_direction,
    settlement_sides) pairs — guards against drift between the two
    fields."""
    with pytest.raises(ValueError, match="does not match flow_direction"):
        IvaInvoiceClassification(
            category=VATCategory.DOMESTIC_GENERAL_21,
            rate_kind=VATRateKind.GENERAL,
            flow_direction=IvaFlowDirection.REPERCUTIDO,
            settlement_sides=frozenset(
                {IvaSettlementSide.DEDUCIBLE}  # ← doesn't match REPERCUTIDO
            ),
        )


def test_classification_record_is_frozen() -> None:
    classification = classify_invoice_line_for_iva(
        iva_rate=IvaRate.RATE_21, invoice_kind=InvoiceKind.ISSUED
    )
    with pytest.raises(Exception):  # noqa: PT011 — pydantic frozen-mutation error
        classification.flow_direction = IvaFlowDirection.SOPORTADO  # type: ignore[misc]


def test_classification_for_reverse_charge_category_with_inconsistent_flow_rejected() -> None:
    """Even if the VATCategory says reverse-charge, the constructor
    only accepts AUTOREPERCUTIDO when settlement_sides has both — the
    cross-check is on (flow, sides), not on category."""
    with pytest.raises(ValueError, match="does not match flow_direction"):
        IvaInvoiceClassification(
            category=VATCategory.DOMESTIC_REVERSE_CHARGE,
            rate_kind=VATRateKind.GENERAL,
            flow_direction=IvaFlowDirection.AUTOREPERCUTIDO,
            settlement_sides=frozenset({IvaSettlementSide.DEVENGADA}),  # missing deducible
        )
