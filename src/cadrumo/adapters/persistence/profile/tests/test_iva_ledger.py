"""Tests for bucket-local IVA ledger observation projection."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

import cadrumo.application.aggregation.iva_ledger as iva_ledger
from cadrumo.adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile, isolated_two_bucket_runtime
from cadrumo.application.aggregation.errors import (
    AggregationValidationError,
)
from cadrumo.application.aggregation.iva_ledger import (
    IvaLedgerAggregation,
    IvaLedgerAggregationIssueReason,
    aggregate_iva_ledger_observations_from_repositories,
)
from cadrumo.core.aggregation import BindingAggregation, BindingAggregationOp
from cadrumo.core.iva_deduction_fact import IvaDeductionEvidenceAuthority, IvaDeductionFactKind
from cadrumo.core.period import Period
from cadrumo.core.prorrata_exclusions import Art104TresExclusion
from cadrumo.domain.bienes_inversion.register import BienesInversionIvaRegister
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority as _indexed_authority_for_test
from cadrumo.domain.calculations.registry.schema import BindingDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_references import PeriodSelector
from cadrumo.domain.iva.deduction_facts import IvaDeductionClassificationProvenance
from cadrumo.domain.iva.flow import IvaFlowDirection
from cadrumo.domain.iva.schema import (
    IvaCashAccountingTreatment,
    IvaCategory,
    IvaExemptionArticle,
    IvaLedgerObservationRole,
    IvaRateKind,
)
from cadrumo.domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from cadrumo.domain.transactions.models import Transaction, TransactionCatalogue
from cadrumo.domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        yield profile.repository


def _period(year: int, code: str) -> Period:
    return Period.from_year_and_code(year, code)


_TEST_ASSET_REGISTER = BienesInversionIvaRegister()


def aggregate_iva_ledger_observations(
    transactions: TransactionCatalogue,
    *,
    period: Period,
    operation: PinnedAuthorityOperation,
) -> IvaLedgerAggregation:
    """Exercise the public path with an explicit empty authority owned by this test profile."""
    return iva_ledger.aggregate_iva_ledger_observations(
        transactions,
        period=period,
        ledger_profile_id="test-profile",
        investment_asset_register=_TEST_ASSET_REGISTER,
        investment_asset_profile_id="test-profile",
        operation=operation,
    )


def _iva_binding(
    binding_id: str,
    *,
    categories: tuple[IvaCategory, ...],
    rate_kinds: tuple[IvaRateKind, ...],
    flow_direction: IvaFlowDirection,
) -> BindingDefinition:
    return BindingDefinition(
        id=binding_id,
        provider={
            "kind": "ledger_iva_aggregation",
            **{
                "categories": categories,
                "rate_kinds": rate_kinds,
                "flow_direction": flow_direction,
                "observation_roles": (IvaLedgerObservationRole.SETTLEMENT,),
                "cash_accounting_treatments": (
                    IvaCashAccountingTreatment("none"),
                    IvaCashAccountingTreatment("supplier_regime"),
                ),
                "fact": "iva_amount_sum",
            },
        },
        value={"data_type": "money", "channel": "decimal"},
        aggregation=BindingAggregation(op=BindingAggregationOp.SUM),
        legal_refs=("ley-37-1992:art-88",),
        source_refs=("test-iva-ledger-binding",),
    )


def _revision_with_iva_bindings(revision_id: str, *bindings: BindingDefinition) -> ModeloRevision:
    return ModeloRevision(
        id=revision_id,
        localization_key=f"test.schema.revision.{revision_id}.label",
        valid_from=date(2026, 1, 1),
        period_selector=PeriodSelector(year_from=2026, periods=("1T", "2T", "3T", "4T", "0A")),
        legal_refs=("ley-37-1992:art-88",),
        source_refs=("test-iva-ledger-binding",),
        bindings=bindings,
    )


def _modelo_303_iva_revision() -> ModeloRevision:
    return _revision_with_iva_bindings(
        "2022",
        _iva_binding(
            "modelo-303-iva-repercutido-general-cuota",
            categories=(IvaCategory("domestic_general"),),
            rate_kinds=(IvaRateKind("general"),),
            flow_direction=IvaFlowDirection._from_registry("repercutido"),
        ),
        _iva_binding(
            "modelo-303-iva-soportado-interiores-cuota",
            categories=(
                IvaCategory("domestic_general"),
                IvaCategory("domestic_reduced"),
                IvaCategory("domestic_super_reduced"),
            ),
            rate_kinds=(IvaRateKind("general"), IvaRateKind("reduced"), IvaRateKind("super_reduced")),
            flow_direction=IvaFlowDirection._from_registry("soportado"),
        ),
    )


_Q2_2023 = _period(2023, "2T")
_Q2_2026 = _period(2026, "2T")
# Before Ley 41/1994 art. 78.Segundo took effect on 1 January 1995, so genuinely
# outside the rate table's coverage: no ES window of any tier reaches back past
# it.
#
# This probe has now moved TWICE, each time because the table gained real
# coverage rather than because the distinction weakened. 2T 2023 served first,
# until the general and reduced windows were corrected back to 2012; 2T 2012
# served next, until the super-reducido window was corrected back to 1995 and
# began covering the date the probe relied on being uncovered.
#
# The lesson is in the pattern, not the dates: a probe anchored to where the
# data currently STOPS will be falsified every time the data is corrected, and
# it fails by reporting the wrong reason rather than by looking wrong. Anchor it
# to the earliest provision the table can ever cite, which is what this is.
_Q2_1994 = _period(1994, "2T")
_BUCKET_ID = "14141414-1414-4414-8414-141414141414"
_OTHER_BUCKET_ID = "15151515-1515-4515-8515-151515151515"


def _raw_transaction(
    provider_id: str,
    *,
    booked_date: date = date(2026, 4, 5),
    value_date: date | None = date(2026, 4, 5),
    amount: Decimal = Decimal("121.00"),
    currency: str = "EUR",
) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=booked_date,
        value_date=value_date,
        amount=amount,
        currency=currency,
        counterparty="Cliente o proveedor",
        description=f"ledger row {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="b" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(2026, 4, 6, 12, 0, tzinfo=UTC),
            provider_name="manual-ledger",
        ),
        raw_fields={"source_kind": "ledger_transaction"},
    )


def _transaction(
    provider_id: str,
    *,
    amount: Decimal | None = None,
    direction: TransactionDirection = TransactionDirection.OUTGOING,
    business_classification: BusinessClassification = BusinessClassification.BUSINESS,
    business_pct: Decimal | None = None,
    booked_date: date = date(2026, 4, 5),
    value_date: date | None = date(2026, 4, 5),
    currency: str = "EUR",
    taxable_base: Decimal | None = Decimal("100.00"),
    iva_rate: Decimal | None = Decimal("0.21"),
    iva_amount: Decimal | None = Decimal("21.00"),
    prorrata_reference: str | None = None,
    lifecycle_state: TransactionLifecycleState = TransactionLifecycleState.ACTIVE,
    fx_rate: Decimal | None = None,
    value_in_eur: Decimal | None = None,
    iva_category: IvaCategory | None = None,
    exemption_article: IvaExemptionArticle | None = None,
    art_104_tres_exclusion: Art104TresExclusion | None = None,
) -> Transaction:
    # Keep the gross consistent with base + iva (the Transaction
    # gross == taxable_base + iva_amount invariant). When the caller does not
    # pin an explicit amount and both tax fields are present, derive the
    # IVA-inclusive gross magnitude from them; flow is carried by ``direction``.
    if amount is None:
        amount = taxable_base + iva_amount if taxable_base is not None and iva_amount is not None else Decimal("121.00")
    carries_input_iva = (
        direction is TransactionDirection.OUTGOING
        and taxable_base is not None
        and iva_rate is not None
        and iva_amount is not None
    )
    return Transaction.model_validate(
        {
            "raw": _raw_transaction(
                provider_id,
                booked_date=booked_date,
                value_date=value_date,
                amount=amount,
                currency=currency,
            ),
            "direction": direction,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": business_classification,
            "business_pct": business_pct,
            "taxable_base": taxable_base,
            "iva_rate": iva_rate,
            "iva_amount": iva_amount,
            "iva_category": iva_category,
            "deduction_fact_kind": (
                IvaDeductionFactKind._from_registry("domestic_current") if carries_input_iva else None
            ),
            "deduction_provenance": (
                IvaDeductionClassificationProvenance(
                    authority=IvaDeductionEvidenceAuthority._from_registry("invoice_evidence"),
                    source_locator=f"test-invoice:{provider_id}",
                    evidence_digest="a" * 64,
                )
                if carries_input_iva
                else None
            ),
            "exemption_article": exemption_article,
            "art_104_tres_exclusion": art_104_tres_exclusion,
            "prorrata_reference": prorrata_reference,
            "lifecycle_state": lifecycle_state,
            "fx_rate": fx_rate,
            "value_in_eur": value_in_eur,
            "classified_at": datetime(2026, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def test_repository_backed_projection_rejects_bucket_mismatch_before_loading(
    secure_objects: SecureObjectRepository,
) -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test, pytest.raises(AggregationValidationError, match="bucket_mismatch"):
        aggregate_iva_ledger_observations_from_repositories(
            bucket_id=_BUCKET_ID,
            period=_Q2_2026,
            prorrata_register_repository=ProrrataRegisterRepository(
                bucket_id=_BUCKET_ID,
                objects=secure_objects,
            ),
            transaction_repository=TransactionCatalogueRepository(
                bucket_id=_OTHER_BUCKET_ID,
                objects=secure_objects,
            ),
            investment_asset_register=_TEST_ASSET_REGISTER,
            investment_asset_profile_id=_BUCKET_ID,
            operation=_authority_operation_for_test,
        )


def test_repository_backed_projection_refuses_a_real_foreign_prorrata_repository_before_loading(
    tmp_path: Path,
) -> None:
    """IVA aggregation never combines a primary ledger with another bucket's register."""
    with _indexed_authority_for_test().operation() as _authority_operation_for_test, isolated_two_bucket_runtime(tmp_path=tmp_path) as runtime:
        TransactionCatalogueRepository(bucket_id=runtime.primary.bucket_id).save(
            TransactionCatalogue.from_transactions((_transaction("primary-ledger-row"),))
        )
        foreign_prorrata_repository = ProrrataRegisterRepository(
            bucket_id=runtime.secondary.bucket_id,
            objects=runtime.secondary.repository,
        )

        assert foreign_prorrata_repository.bucket_id == runtime.secondary.bucket_id
        with pytest.raises(AggregationValidationError, match="bucket_mismatch"):
            aggregate_iva_ledger_observations_from_repositories(
                bucket_id=runtime.primary.bucket_id,
                period=_Q2_2026,
                prorrata_register_repository=foreign_prorrata_repository,
                transaction_repository=TransactionCatalogueRepository(bucket_id=runtime.primary.bucket_id),
                operation=_authority_operation_for_test,
            )


def test_repository_backed_projection_loads_persisted_bucket_catalogue(secure_objects: SecureObjectRepository) -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        transaction = _transaction("row-repository")
        repository = TransactionCatalogueRepository(
            bucket_id=_BUCKET_ID,
            objects=secure_objects,
        )
        repository.save(TransactionCatalogue.from_transactions((transaction,)))

        result = aggregate_iva_ledger_observations_from_repositories(
            bucket_id=_BUCKET_ID,
            period=_Q2_2026,
            prorrata_register_repository=ProrrataRegisterRepository(bucket_id=_BUCKET_ID, objects=secure_objects),
            transaction_repository=TransactionCatalogueRepository(
                bucket_id=_BUCKET_ID,
                objects=secure_objects,
            ),
            investment_asset_register=_TEST_ASSET_REGISTER,
            investment_asset_profile_id=_BUCKET_ID,
            operation=_authority_operation_for_test,
        )

        assert result.issues == ()
        assert result.observations[0].ledger_id == transaction.transaction_id


def test_repository_backed_projection_reports_out_of_period_catalogue_transactions(
    secure_objects: SecureObjectRepository,
) -> None:
    """A catalogue transaction outside the requested quarter must surface as a summary.

    Regression test: the repository-backed entry point must NOT
    silently drop out-of-window rows. The compact summary keeps the operator
    visibility signal without allocating one row-level issue per excluded
    plaintext index entry.
    """
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        in_period = _transaction("row-in-period", value_date=date(2026, 4, 5))
        out_of_period = _transaction("row-out-of-period", value_date=date(2026, 7, 10))
        repository = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
        repository.save(TransactionCatalogue.from_transactions((in_period, out_of_period)))

        result = aggregate_iva_ledger_observations_from_repositories(
            bucket_id=_BUCKET_ID,
            period=_Q2_2026,
            prorrata_register_repository=ProrrataRegisterRepository(bucket_id=_BUCKET_ID, objects=secure_objects),
            transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects),
            investment_asset_register=_TEST_ASSET_REGISTER,
            investment_asset_profile_id=_BUCKET_ID,
            operation=_authority_operation_for_test,
        )

        assert {o.ledger_id for o in result.observations} == {in_period.transaction_id}
        assert result.issues == ()
        assert result.out_of_window_summary is not None
        assert result.out_of_window_summary.count == 1
        assert result.out_of_window_summary.min_filing_date == date(2026, 7, 10)
        assert result.out_of_window_summary.max_filing_date == date(2026, 7, 10)


def test_repository_backed_projection_summarizes_previously_silent_out_of_window_rows(
    secure_objects: SecureObjectRepository,
) -> None:
    """Out-of-window rows surface as one compact period-exclusion summary.

    Reviewed-excluded and archived rows are ignored before the in-window IVA
    classifier runs. When those rows fall outside the requested window, the
    repository-backed partition reports their count and date span instead of
    dropping them before aggregation.
    """
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        in_period = _transaction("row-in-period", value_date=date(2026, 4, 5))
        excluded_out_of_period = _transaction(
            "row-excluded-out-of-period",
            value_date=date(2026, 7, 1),
            business_classification=BusinessClassification.REVIEWED_EXCLUDED,
        )
        archived_out_of_period = _transaction(
            "row-archived-out-of-period",
            value_date=date(2026, 7, 2),
            lifecycle_state=TransactionLifecycleState.ARCHIVED,
        )
        repository = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
        repository.save(
            TransactionCatalogue.from_transactions((in_period, excluded_out_of_period, archived_out_of_period)),
        )

        result = aggregate_iva_ledger_observations_from_repositories(
            bucket_id=_BUCKET_ID,
            period=_Q2_2026,
            prorrata_register_repository=ProrrataRegisterRepository(bucket_id=_BUCKET_ID, objects=secure_objects),
            transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects),
            investment_asset_register=_TEST_ASSET_REGISTER,
            investment_asset_profile_id=_BUCKET_ID,
            operation=_authority_operation_for_test,
        )

        assert {o.ledger_id for o in result.observations} == {in_period.transaction_id}
        assert result.issues == ()
        assert result.out_of_window_summary is not None
        assert result.out_of_window_summary.count == 2
        assert result.out_of_window_summary.min_filing_date == date(2026, 7, 1)
        assert result.out_of_window_summary.max_filing_date == date(2026, 7, 2)


def test_repository_backed_projection_partition_matches_full_scan(
    secure_objects: SecureObjectRepository,
) -> None:
    """The partitioned result matches the full-scan result for declared values.

    The same multi-period catalogue is aggregated once through the
    repository-backed partition and once through the pure full-scan aggregator.
    In-window observations and prorrata references must match; only the
    out-of-window issue taxonomy can differ between the two paths.
    """
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        q2_row_a = _transaction("row-q2-a", value_date=date(2026, 4, 5), taxable_base=Decimal("100.00"))
        q2_row_b = _transaction("row-q2-b", value_date=date(2026, 6, 20), taxable_base=Decimal("200.00"))
        q1_row = _transaction("row-q1", value_date=date(2026, 2, 1), taxable_base=Decimal("50.00"))
        q3_row = _transaction("row-q3", value_date=date(2026, 8, 1), taxable_base=Decimal("75.00"))
        excluded_q3_row = _transaction(
            "row-q3-excluded",
            value_date=date(2026, 9, 1),
            business_classification=BusinessClassification.REVIEWED_EXCLUDED,
        )
        catalogue = TransactionCatalogue.from_transactions(
            (q2_row_a, q2_row_b, q1_row, q3_row, excluded_q3_row),
        )
        repository = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
        repository.save(catalogue)

        partitioned = aggregate_iva_ledger_observations_from_repositories(
            bucket_id=_BUCKET_ID,
            period=_Q2_2026,
            prorrata_register_repository=ProrrataRegisterRepository(bucket_id=_BUCKET_ID, objects=secure_objects),
            transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects),
            investment_asset_register=_TEST_ASSET_REGISTER,
            investment_asset_profile_id=_BUCKET_ID,
            operation=_authority_operation_for_test,
        )
        full_scan = aggregate_iva_ledger_observations(
            catalogue,
            period=_Q2_2026,
            operation=_authority_operation_for_test,
        )

        # Declared-value invariance: observations and prorrata references are
        # identical SETS between the two paths (order may differ: full-scan
        # iterates catalogue insertion order, partitioned iterates sorted ids).
        assert set(partitioned.observations) == set(full_scan.observations)
        assert set(partitioned.prorrata_references) == set(full_scan.prorrata_references)
        assert {o.ledger_id for o in partitioned.observations} == {q2_row_a.transaction_id, q2_row_b.transaction_id}

        # Permitted delta: repository-backed partitioning reports one compact
        # out-of-window summary, while full-scan refines by row after decryption.
        assert partitioned.issues == ()
        assert partitioned.out_of_window_summary is not None
        assert partitioned.out_of_window_summary.count == 3
        assert partitioned.out_of_window_summary.min_filing_date == date(2026, 2, 1)
        assert partitioned.out_of_window_summary.max_filing_date == date(2026, 9, 1)

        full_scan_ids_with_issues = {i.transaction_id for i in full_scan.issues}
        assert full_scan_ids_with_issues == {q1_row.transaction_id, q3_row.transaction_id}
        assert all(i.reason is IvaLedgerAggregationIssueReason.OUTSIDE_PERIOD for i in full_scan.issues)
        # excluded_q3_row is silently skipped by full-scan (no issue) but surfaces
        # under the partitioned path.
        assert excluded_q3_row.transaction_id not in full_scan_ids_with_issues
