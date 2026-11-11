"""Profile-persistence parity coverage for IVA cash-accounting projection."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.aggregation.iva_ledger import (
    IvaLedgerAggregation,
    aggregate_iva_ledger_observations,
    aggregate_iva_ledger_observations_from_repositories,
)
from cadrumo.application.aggregation.tests.iva_cash_accounting_support import cash_accounting_transaction
from cadrumo.core.period import Period
from cadrumo.domain.bienes_inversion.register import BienesInversionIvaRegister
from cadrumo.domain.calculations.registry.authority import (
    PinnedAuthorityOperation,
    bundled_indexed_authority,
)
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.domain.iva.schema import IvaCashAccountingPaymentEvidence, IvaCashAccountingTreatment
from cadrumo.domain.transactions.enums import TransactionDirection
from cadrumo.domain.transactions.models import TransactionCatalogue

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]

_YEAR = filing_year_envelope().horizon

_Q1 = Period.from_year_and_code(_YEAR, "1T")
_PARITY_BUCKET_ID = "5c5c5c5c-5c5c-4c5c-8c5c-5c5c5c5c5c5c"


def _pure_projection(
    catalogue: TransactionCatalogue, *, period: Period, operation: PinnedAuthorityOperation
) -> IvaLedgerAggregation:
    return aggregate_iva_ledger_observations(
        catalogue,
        period=period,
        ledger_profile_id=_PARITY_BUCKET_ID,
        investment_asset_register=BienesInversionIvaRegister(),
        investment_asset_profile_id=_PARITY_BUCKET_ID,
        operation=operation,
    )


def test_repository_backed_projection_matches_the_pure_projection_for_a_cross_quarter_devengo(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """The persisted read path must reproduce the in-memory projection exactly.

    A supplier-regime purchase booked in Q2 carries its art. 75 devengo in Q1.
    The in-memory projection reports that Q1 cuota devengada; the
    repository-backed projection selects its candidate rows through the
    plaintext date index, so it must select on the row's eligible-date span
    rather than its filing date or it returns an empty Q1 aggregation and
    silently under-declares.
    """
    with bundled_indexed_authority().operation() as _authority_operation_for_test:
        cash_purchase = cash_accounting_transaction(
            "cross-quarter-devengo",
            direction=TransactionDirection.OUTGOING,
            booked_date=date(_YEAR, 4, 15),
            taxable_base=Decimal("1000.00"),
            iva_amount=Decimal("210.00"),
            cash_accounting_treatment=IvaCashAccountingTreatment("supplier_regime"),
            operation_date=date(_YEAR, 3, 20),
            cash_accounting_payment_evidence=(
                IvaCashAccountingPaymentEvidence(
                    payment_date=date(_YEAR, 4, 15),
                    taxable_base=Decimal("1000.00"),
                    iva_amount=Decimal("210.00"),
                ),
            ),
        )
        catalogue = TransactionCatalogue.from_transactions((cash_purchase,))
        pure = _pure_projection(catalogue, period=_Q1, operation=operation)

        with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PARITY_BUCKET_ID) as profile:
            TransactionCatalogueRepository(bucket_id=profile.bucket_id).save(catalogue)
            repository_backed = aggregate_iva_ledger_observations_from_repositories(
                bucket_id=profile.bucket_id,
                period=_Q1,
                prorrata_register_repository=ProrrataRegisterRepository(bucket_id=profile.bucket_id),
                transaction_repository=TransactionCatalogueRepository(bucket_id=profile.bucket_id),
                invoice_reader=InvoiceCatalogueRepository(bucket_id=profile.bucket_id),
                operation=_authority_operation_for_test,
            )

        assert pure.observations != ()
        assert tuple(repository_backed.observations) == tuple(pure.observations)
        assert repository_backed.issues == pure.issues
