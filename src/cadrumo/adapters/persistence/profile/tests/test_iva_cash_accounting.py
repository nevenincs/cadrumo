"""Profile-persistence parity coverage for IVA cash-accounting projection."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.aggregation.iva_ledger import (
    IvaLedgerAggregation,
    aggregate_iva_ledger_observations,
    aggregate_iva_ledger_observations_from_repositories,
)
from cadrumo.core.iva_deduction_fact import IvaDeductionEvidenceAuthority, IvaDeductionFactKind
from cadrumo.core.period import Period
from cadrumo.domain.bienes_inversion.register import BienesInversionIvaRegister
from cadrumo.domain.calculations.registry.authority import (
    PinnedAuthorityOperation,
)
from cadrumo.domain.calculations.registry.authority import (
    bundled_indexed_authority as _indexed_authority_for_test,
)
from cadrumo.domain.iva.deduction_facts import IvaDeductionClassificationProvenance
from cadrumo.domain.iva.schema import IvaCashAccountingPaymentEvidence, IvaCashAccountingTreatment, IvaCategory
from cadrumo.domain.transactions.enums import BusinessClassification, TransactionDirection
from cadrumo.domain.transactions.models import Transaction, TransactionCatalogue
from cadrumo.domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]

_Q1_2026 = Period.from_year_and_code(2026, "1T")
_PARITY_BUCKET_ID = "5c5c5c5c-5c5c-4c5c-8c5c-5c5c5c5c5c5c"


def _raw(provider_id: str, *, booked_date: date, amount: Decimal) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=booked_date,
        value_date=booked_date,
        amount=amount,
        currency="EUR",
        counterparty="Cliente criterio caja",
        description=f"cash-accounting {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="d" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(2026, 4, 1, 10, 0, tzinfo=UTC),
            provider_name="manual-ledger",
        ),
        raw_fields={"source_kind": "ledger_transaction"},
    )


def _transaction(
    provider_id: str,
    *,
    direction: TransactionDirection,
    booked_date: date,
    taxable_base: Decimal,
    iva_amount: Decimal,
    cash_accounting_treatment: IvaCashAccountingTreatment = IvaCashAccountingTreatment("none"),
    operation_date: date | None = None,
    cash_accounting_payment_evidence: tuple[IvaCashAccountingPaymentEvidence, ...] = (),
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": _raw(provider_id, booked_date=booked_date, amount=taxable_base + iva_amount),
            "direction": direction,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "taxable_base": taxable_base,
            "iva_rate": Decimal("0.21"),
            "iva_amount": iva_amount,
            "iva_category": IvaCategory("domestic_general"),
            "deduction_fact_kind": IvaDeductionFactKind._from_registry("domestic_current")
            if direction is TransactionDirection.OUTGOING
            else None,
            "deduction_provenance": IvaDeductionClassificationProvenance(
                authority=IvaDeductionEvidenceAuthority._from_registry("invoice_evidence"),
                source_locator=f"invoice:{provider_id}",
                evidence_digest="a" * 64,
            )
            if direction is TransactionDirection.OUTGOING
            else None,
            "cash_accounting_treatment": cash_accounting_treatment,
            "operation_date": operation_date,
            "cash_accounting_payment_evidence": cash_accounting_payment_evidence,
            "classified_at": datetime(2026, 4, 1, 10, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


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
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        cash_purchase = _transaction(
            "cross-quarter-devengo",
            direction=TransactionDirection.OUTGOING,
            booked_date=date(2026, 4, 15),
            taxable_base=Decimal("1000.00"),
            iva_amount=Decimal("210.00"),
            cash_accounting_treatment=IvaCashAccountingTreatment("supplier_regime"),
            operation_date=date(2026, 3, 20),
            cash_accounting_payment_evidence=(
                IvaCashAccountingPaymentEvidence(
                    payment_date=date(2026, 4, 15),
                    taxable_base=Decimal("1000.00"),
                    iva_amount=Decimal("210.00"),
                ),
            ),
        )
        catalogue = TransactionCatalogue.from_transactions((cash_purchase,))
        pure = _pure_projection(catalogue, period=_Q1_2026, operation=operation)

        with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PARITY_BUCKET_ID) as profile:
            TransactionCatalogueRepository(bucket_id=profile.bucket_id).save(catalogue)
            repository_backed = aggregate_iva_ledger_observations_from_repositories(
                bucket_id=profile.bucket_id,
                period=_Q1_2026,
                prorrata_register_repository=ProrrataRegisterRepository(bucket_id=profile.bucket_id),
                transaction_repository=TransactionCatalogueRepository(bucket_id=profile.bucket_id),
                operation=_authority_operation_for_test,
            )

        assert pure.observations != ()
        assert tuple(repository_backed.observations) == tuple(pure.observations)
        assert repository_backed.issues == pure.issues
