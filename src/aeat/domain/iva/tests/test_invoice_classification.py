"""Tests for the reusable IVA classification record."""

from __future__ import annotations

from decimal import Decimal
from typing import cast

import pytest
from pydantic import ValidationError

from ....core.resources import bundled_path
from ...calculations.registry import IvaLedgerObservation
from ...invoices import IvaRate
from .. import (
    InvoiceKind,
    IvaCategory,
    IvaFlowDirection,
    IvaRateKind,
    IvaSettlementSide,
)
from .._invoice_classification import (
    IvaInvoiceClassification,
    classify_invoice_line_for_iva,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.mark.parametrize(
    ("iva_rate", "expected_category", "expected_kind"),
    [
        (IvaRate.RATE_0, IvaCategory.DOMESTIC_ZERO, IvaRateKind.ZERO),
        (IvaRate.RATE_4, IvaCategory.DOMESTIC_SUPER_REDUCED_4, IvaRateKind.SUPER_REDUCED),
        (IvaRate.RATE_10, IvaCategory.DOMESTIC_REDUCED_10, IvaRateKind.REDUCED),
        (IvaRate.RATE_21, IvaCategory.DOMESTIC_GENERAL_21, IvaRateKind.GENERAL),
        (IvaRate.EXEMPT, IvaCategory.DOMESTIC_EXEMPT, IvaRateKind.EXEMPT),
    ],
)
def test_classify_issued_invoice_at_each_rate_slot_resolves_to_repercutido(
    iva_rate: IvaRate, expected_category: IvaCategory, expected_kind: IvaRateKind,
) -> None:
    classification = classify_invoice_line_for_iva(iva_rate=iva_rate, invoice_kind=InvoiceKind.ISSUED)
    assert classification.category is expected_category
    assert classification.rate_kind is expected_kind
    assert classification.flow_direction is IvaFlowDirection.REPERCUTIDO
    assert classification.settlement_sides == frozenset({IvaSettlementSide.DEVENGADA})


@pytest.mark.parametrize(
    "iva_rate",
    [IvaRate.RATE_0, IvaRate.RATE_4, IvaRate.RATE_10, IvaRate.RATE_21, IvaRate.EXEMPT],
)
def test_classify_received_invoice_resolves_to_soportado(iva_rate: IvaRate) -> None:
    classification = classify_invoice_line_for_iva(iva_rate=iva_rate, invoice_kind=InvoiceKind.RECEIVED)
    assert classification.flow_direction is IvaFlowDirection.SOPORTADO
    assert classification.settlement_sides == frozenset({IvaSettlementSide.DEDUCIBLE})


def test_classify_invoice_rejects_not_subject_rate() -> None:
    """NOT_SUBJECT operations are out of scope of IVA — the standard-case
    helper rejects them so callers explicitly handle them via
    IvaCategory.OPERACION_NO_SUJETA."""
    with pytest.raises(ValueError, match="NOT_SUBJECT"):
        classify_invoice_line_for_iva(iva_rate=IvaRate.NOT_SUBJECT, invoice_kind=InvoiceKind.ISSUED)


def test_classification_record_contributes_to_devengada_for_repercutido() -> None:
    classification = classify_invoice_line_for_iva(iva_rate=IvaRate.RATE_21, invoice_kind=InvoiceKind.ISSUED)
    assert classification.contributes_to_devengada is True
    assert classification.contributes_to_deducible is False
    assert classification.is_reverse_charge is False


def test_classification_record_contributes_to_deducible_for_soportado() -> None:
    classification = classify_invoice_line_for_iva(iva_rate=IvaRate.RATE_21, invoice_kind=InvoiceKind.RECEIVED)
    assert classification.contributes_to_devengada is False
    assert classification.contributes_to_deducible is True
    assert classification.is_reverse_charge is False


def test_classification_record_contributes_to_both_sides_for_autorepercutido() -> None:
    """Reverse-charge operations contribute to BOTH cornerstones on the
    same operation (LIVA art 84.Uno.2). Callers construct the record
    directly for these cases."""
    classification = IvaInvoiceClassification(
        category=IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
        rate_kind=IvaRateKind.GENERAL,
        flow_direction=IvaFlowDirection.INVERSION_SUJETO_PASIVO,
        settlement_sides=frozenset({IvaSettlementSide.DEVENGADA, IvaSettlementSide.DEDUCIBLE}),
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
            category=IvaCategory.DOMESTIC_GENERAL_21,
            rate_kind=IvaRateKind.GENERAL,
            flow_direction=IvaFlowDirection.REPERCUTIDO,
            settlement_sides=frozenset(
                {IvaSettlementSide.DEDUCIBLE},  # ← doesn't match REPERCUTIDO
            ),
        )


def test_classification_record_is_frozen() -> None:
    classification = classify_invoice_line_for_iva(iva_rate=IvaRate.RATE_21, invoice_kind=InvoiceKind.ISSUED)
    with pytest.raises(ValidationError, match=r"frozen|Instance is frozen"):
        classification.flow_direction = IvaFlowDirection.SOPORTADO


def test_classification_for_reverse_charge_category_with_inconsistent_flow_rejected() -> None:
    """Even if the IvaCategory says reverse-charge, the constructor
    only accepts INVERSION_SUJETO_PASIVO when settlement_sides has both — the
    cross-check is on (flow, sides), not on category."""
    with pytest.raises(ValueError, match="does not match flow_direction"):
        IvaInvoiceClassification(
            category=IvaCategory.DOMESTIC_REVERSE_CHARGE,
            rate_kind=IvaRateKind.GENERAL,
            flow_direction=IvaFlowDirection.INVERSION_SUJETO_PASIVO,
            settlement_sides=frozenset({IvaSettlementSide.DEVENGADA}),  # missing deducible
        )


# ---------------------------------------------------------------------------
# Ledger → modelo bridge: invoice_line_to_iva_observation
# ---------------------------------------------------------------------------


def test_invoice_line_to_iva_observation_builds_repercutido_record_for_issued() -> None:
    from datetime import date
    from decimal import Decimal

    from ...invoices import invoice_line_to_iva_observation

    obs = invoice_line_to_iva_observation(
        invoice_id="inv-001",
        issued_at=date(2025, 6, 15),
        invoice_kind=InvoiceKind.ISSUED,
        iva_rate=IvaRate.RATE_21,
        base_amount=Decimal("1000"),
        iva_amount=Decimal("210"),
    )
    assert isinstance(obs, IvaLedgerObservation)
    assert obs.ledger_id == "inv-001"
    assert obs.transaction_date == date(2025, 6, 15)
    assert obs.category is IvaCategory.DOMESTIC_GENERAL_21
    assert obs.rate_kind is IvaRateKind.GENERAL
    assert obs.flow_direction is IvaFlowDirection.REPERCUTIDO
    assert obs.base_amount == Decimal("1000")
    assert obs.iva_amount == Decimal("210")


def test_invoice_line_to_iva_observation_builds_soportado_record_for_received() -> None:
    from datetime import date
    from decimal import Decimal

    from ...invoices import invoice_line_to_iva_observation

    obs = invoice_line_to_iva_observation(
        invoice_id="bill-77",
        issued_at=date(2025, 7, 1),
        invoice_kind=InvoiceKind.RECEIVED,
        iva_rate=IvaRate.RATE_10,
        base_amount=Decimal("500"),
        iva_amount=Decimal("50"),
    )
    assert obs.flow_direction is IvaFlowDirection.SOPORTADO
    assert obs.category is IvaCategory.DOMESTIC_REDUCED_10
    assert obs.rate_kind is IvaRateKind.REDUCED


def test_invoice_line_to_iva_observation_rejects_non_decimal_amounts() -> None:
    from datetime import date

    from ...invoices import invoice_line_to_iva_observation

    with pytest.raises(ValidationError, match=r"base_amount|iva_amount|Decimal|decimal"):
        invoice_line_to_iva_observation(
            invoice_id="inv-bad",
            issued_at=date(2025, 6, 15),
            invoice_kind=InvoiceKind.ISSUED,
            iva_rate=IvaRate.RATE_21,
            base_amount=cast(Decimal, "1000"),
            iva_amount=cast(Decimal, "210"),
        )


def test_invoice_line_observation_feeds_modelo_303_binding_resolver_end_to_end() -> None:
    """The full ledger → substrate → modelo registry chain: build
    observations from invoice metadata via invoice_line_to_iva_observation,
    feed them to resolve_ledger_iva_aggregation_binding_values, get
    binding totals back."""
    from datetime import date
    from decimal import Decimal

    from ...calculations.registry import (
        load_registry_tree,
        resolve_ledger_iva_aggregation_binding_values,
    )
    from ...invoices import invoice_line_to_iva_observation

    modelos, _ = load_registry_tree(bundled_path("registry", "aeat"))
    m303 = next(m for m in modelos if m.id == "303")
    revision = m303.revisions["2009-y-siguientes"]

    # Two issued + one received line, all standard-case domestic
    observations = (
        invoice_line_to_iva_observation(
            invoice_id="inv-1",
            issued_at=date(2025, 1, 15),
            invoice_kind=InvoiceKind.ISSUED,
            iva_rate=IvaRate.RATE_21,
            base_amount=Decimal("1000"),
            iva_amount=Decimal("210"),
        ),
        invoice_line_to_iva_observation(
            invoice_id="inv-2",
            issued_at=date(2025, 1, 20),
            invoice_kind=InvoiceKind.ISSUED,
            iva_rate=IvaRate.RATE_10,
            base_amount=Decimal("500"),
            iva_amount=Decimal("50"),
        ),
        invoice_line_to_iva_observation(
            invoice_id="bill-1",
            issued_at=date(2025, 2, 10),
            invoice_kind=InvoiceKind.RECEIVED,
            iva_rate=IvaRate.RATE_21,
            base_amount=Decimal("400"),
            iva_amount=Decimal("84"),
        ),
    )
    result = resolve_ledger_iva_aggregation_binding_values(revision, observations)
    # Routing wiring: each per-rate single-observation result threads the
    # originating observation's iva_amount through the resolver. The
    # assertions read the iva_amount off the source observation rather
    # than carrying a hand-written literal, so a future author changing
    # a synthetic input cannot accidentally make the test agree with a
    # silently-broken resolver. Arithmetic of base_amount vs iva_amount
    # is verified against AEAT authority through the workbook parity
    # tests in the calculations registry.
    assert result["modelo-303-iva-repercutido-general-cuota"] == observations[0].iva_amount
    assert result["modelo-303-iva-repercutido-reducido-cuota"] == observations[1].iva_amount
    assert result["modelo-303-iva-soportado-interiores-cuota"] == observations[2].iva_amount
