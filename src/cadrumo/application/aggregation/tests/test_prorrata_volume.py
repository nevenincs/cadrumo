"""Annual operation volume stays distinct from cash settlements and unresolved rights."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....core.period import Period
from ....domain.bienes_inversion.register import BienesInversionIvaRegister
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.iva_cash_accounting_vocabulary import (
    resolve_iva_cash_accounting_catalogue,
)
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.iva.schema import IvaCashAccountingPaymentEvidence
from ....domain.transactions.enums import TransactionDirection
from ....domain.transactions.models import TransactionCatalogue
from ..iva_ledger import aggregate_iva_ledger_observations
from ..prorrata_volume import project_prorrata_declared_volume_rollup
from .iva_cash_accounting_support import cash_accounting_transaction

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_YEAR = filing_year_envelope().horizon


def test_cash_payment_fragments_never_duplicate_annual_output_volume(operation: PinnedAuthorityOperation) -> None:
    treatment = resolve_iva_cash_accounting_catalogue(
        effective_date=date(_YEAR, 1, 1),
        authority=operation,
    ).require("taxpayer_regime")
    sale = cash_accounting_transaction(
        "cash-sale",
        direction=TransactionDirection.INCOMING,
        booked_date=date(_YEAR, 3, 10),
        operation_date=date(_YEAR, 2, 10),
        taxable_base=Decimal("100"),
        iva_amount=Decimal("21"),
        cash_accounting_treatment=treatment,
        cash_accounting_payment_evidence=(
            IvaCashAccountingPaymentEvidence(
                payment_date=date(_YEAR, 6, 10), taxable_base=Decimal("40"), iva_amount=Decimal("8.4")
            ),
            IvaCashAccountingPaymentEvidence(
                payment_date=date(_YEAR + 1, 2, 10), taxable_base=Decimal("60"), iva_amount=Decimal("12.6")
            ),
        ),
    )
    aggregation = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions((sale,)),
        period=Period.from_year_and_code(_YEAR, "0A"),
        ledger_profile_id="test-volume",
        investment_asset_register=BienesInversionIvaRegister(),
        investment_asset_profile_id="test-volume",
        operation=operation,
    )
    assert len(aggregation.observations) > 1
    rollup = project_prorrata_declared_volume_rollup(
        aggregation,
        declared_volume_total=Decimal("100"),
        declared_volume_con_derecho=Decimal("100"),
        operation=operation,
    )
    assert rollup.ledger_volume_total == Decimal("100")
    assert rollup.included_ledger_ids == (sale.transaction_id,)
    assert not rollup.unclassified_ledger_ids


def test_a_quarter_cannot_impersonate_complete_annual_reconciliation(operation: PinnedAuthorityOperation) -> None:
    aggregation = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions(()),
        period=Period.from_year_and_code(_YEAR, "1T"),
        ledger_profile_id="test-volume",
        investment_asset_register=BienesInversionIvaRegister(),
        investment_asset_profile_id="test-volume",
        operation=operation,
    )
    with pytest.raises(ValueError, match="complete annual"):
        project_prorrata_declared_volume_rollup(
            aggregation,
            declared_volume_total=None,
            declared_volume_con_derecho=None,
            operation=operation,
        )
