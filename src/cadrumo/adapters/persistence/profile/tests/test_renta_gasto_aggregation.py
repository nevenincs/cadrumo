"""Repository-backed regression tests for M130 deductible-expense aggregation.

These tests exercise the persistence boundary explicitly: real profile-backed
transaction and prorrata repositories feed the application aggregation and
resolver services through an isolated encrypted runtime.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from dev.registry.tests.profile_schema_support import (
    profile_creation_context_for_test as _profile_creation_context_for_test,
)

from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
from cadrumo.adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.aggregation.renta_gasto_ledger import (
    aggregate_renta_gasto_ledger,
    aggregate_renta_gasto_ledger_from_repositories,
)
from cadrumo.application.aggregation.renta_ledger import aggregate_renta_ledger_expenses_from_repositories
from cadrumo.application.invoices.catalogue_reads_ports import InvoiceCatalogueReadPorts
from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.period import Period
from cadrumo.core.prorrata_register import ProrrataProvisionalProvenance, ProrrataRegisterRegime
from cadrumo.domain.prorrata_register.register import ProrrataRegisterEntry
from cadrumo.domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from cadrumo.domain.transactions.models import Transaction, TransactionCatalogue
from cadrumo.domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from cadrumo.domain.user_profile.values import create_user_profile_record as _create_profile_record_for_test

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


SECURE_OBJECTS_BUCKET_ID = "78804f92-b6f7-4daf-9ddf-a8ce3829dbb1"
_Q1_2024 = Period.from_year_and_code(2025, "1T")
_Q2_2024 = Period.from_year_and_code(2025, "2T")
_M130_GASTOS_CASILLA: CasillaId = validated_casilla_id("02")


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=SECURE_OBJECTS_BUCKET_ID) as profile:
        yield profile.repository


def _prior_m303_snapshot_ref():
    return published_authority_operation().snapshot("303", filing_year=2024, period="4T").snapshot_ref


def _raw_transaction(
    provider_id: str,
    *,
    booked_date: date,
    value_date: date | None,
    amount: Decimal = Decimal("1000.00"),
    currency: str = "EUR",
) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=booked_date,
        value_date=value_date,
        amount=amount,
        currency=currency,
        counterparty="Proveedor SA",
        description=f"gasto row {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="b" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2025, 4, 6, 12, 0, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={"Concepto": provider_id},
    )


def _gasto_transaction(
    provider_id: str,
    *,
    value_date: date,
    amount: Decimal = Decimal("1000.00"),
    currency: str = "EUR",
    taxable_base: Decimal | None = None,
    iva_amount: Decimal | None = None,
    irpf_category: str | None = None,
    business_classification: BusinessClassification = BusinessClassification.BUSINESS,
    business_pct: Decimal | None = None,
    direction: TransactionDirection = TransactionDirection.OUTGOING,
    lifecycle_state: TransactionLifecycleState = TransactionLifecycleState.ACTIVE,
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": _raw_transaction(
                provider_id,
                booked_date=value_date,
                value_date=value_date,
                amount=amount,
                currency=currency,
            ),
            "direction": direction,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": business_classification,
            "business_pct": business_pct,
            "purchase_invoice_evidence_id": None,
            "category_id": "asesoria_fiscal",
            "taxable_base": taxable_base,
            "iva_rate": None,
            "iva_amount": iva_amount,
            "irpf_category": irpf_category,
            "lifecycle_state": lifecycle_state,
            "classified_at": datetime(2025, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def test_repository_backed_aggregation_emits_casilla_02_sum(
    secure_objects: SecureObjectRepository,
) -> None:
    """Full path: persist -> load from repo -> aggregate -> correct casilla 02 value."""
    q1_a_base, q1_b_base, q2_base = Decimal("120.00"), Decimal("80.00"), Decimal("300.00")
    q1_a = _gasto_transaction("q1-a", value_date=date(2025, 2, 1), taxable_base=q1_a_base)
    q1_b = _gasto_transaction("q1-b", value_date=date(2025, 3, 15), taxable_base=q1_b_base)
    q2_only = _gasto_transaction("q2-only", value_date=date(2025, 5, 10), taxable_base=q2_base)

    tx_repo = TransactionCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects)
    tx_repo.save(TransactionCatalogue.from_transactions((q1_a, q1_b, q2_only)))

    result_q1 = aggregate_renta_gasto_ledger_from_repositories(
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_Q1_2024,
        modelo="130",
        target_casilla_id=_M130_GASTOS_CASILLA,
        accept_activity_marker=True,
        transaction_repository=TransactionCatalogueRepository(
            bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
        ),
        prorrata_register_repository=ProrrataRegisterRepository(
            bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
        ),
    )
    assert result_q1.casilla_aggregation.casilla_values[_M130_GASTOS_CASILLA] == sum(
        (q1_a_base, q1_b_base),
        Decimal("0"),
    )
    assert {o.transaction_id for o in result_q1.observations} == {q1_a.transaction_id, q1_b.transaction_id}
    assert result_q1.issues == ()
    assert result_q1.out_of_window_summary is not None
    assert result_q1.out_of_window_summary.count == 1
    assert result_q1.out_of_window_summary.min_filing_date == date(2025, 5, 10)
    assert result_q1.out_of_window_summary.max_filing_date == date(2025, 5, 10)

    result_q2 = aggregate_renta_gasto_ledger_from_repositories(
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_Q2_2024,
        modelo="130",
        target_casilla_id=_M130_GASTOS_CASILLA,
        accept_activity_marker=True,
        transaction_repository=TransactionCatalogueRepository(
            bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
        ),
        prorrata_register_repository=ProrrataRegisterRepository(
            bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
        ),
    )
    expected_q2 = sum((q1_a_base, q1_b_base, q2_base), Decimal("0"))
    assert result_q2.out_of_window_summary is None
    assert result_q2.casilla_aggregation.casilla_values[_M130_GASTOS_CASILLA] == expected_q2


def test_repository_backed_aggregation_summarizes_previously_silent_out_of_window_rows(
    secure_objects: SecureObjectRepository,
) -> None:
    """Out-of-window rows surface as one compact period-exclusion summary."""
    in_window = _gasto_transaction("row-in-window", value_date=date(2025, 2, 1), taxable_base=Decimal("50.00"))
    wrong_direction_out_of_window = _gasto_transaction(
        "row-wrong-direction-out-of-window",
        value_date=date(2025, 5, 10),
        taxable_base=Decimal("90.00"),
        direction=TransactionDirection.INCOMING,
    )
    tx_repo = TransactionCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects)
    tx_repo.save(TransactionCatalogue.from_transactions((in_window, wrong_direction_out_of_window)))

    result = aggregate_renta_gasto_ledger_from_repositories(
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_Q1_2024,
        modelo="130",
        target_casilla_id=_M130_GASTOS_CASILLA,
        accept_activity_marker=True,
        transaction_repository=TransactionCatalogueRepository(
            bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
        ),
        prorrata_register_repository=ProrrataRegisterRepository(
            bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
        ),
    )

    assert {o.transaction_id for o in result.observations} == {in_window.transaction_id}
    assert result.issues == ()
    assert result.out_of_window_summary is not None
    assert result.out_of_window_summary.count == 1
    assert result.out_of_window_summary.min_filing_date == date(2025, 5, 10)
    assert result.out_of_window_summary.max_filing_date == date(2025, 5, 10)


def test_repository_backed_aggregation_partition_matches_full_scan(
    secure_objects: SecureObjectRepository,
) -> None:
    """The partitioned result matches the full-scan result for declared values."""
    q1_row = _gasto_transaction("row-q1", value_date=date(2025, 2, 1), taxable_base=Decimal("50.00"))
    q3_row = _gasto_transaction("row-q3", value_date=date(2025, 8, 1), taxable_base=Decimal("70.00"))
    wrong_direction_q3_row = _gasto_transaction(
        "row-q3-wrong-direction",
        value_date=date(2025, 9, 1),
        taxable_base=Decimal("30.00"),
        direction=TransactionDirection.INCOMING,
    )
    catalogue = TransactionCatalogue.from_transactions((q1_row, q3_row, wrong_direction_q3_row))
    tx_repo = TransactionCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects)
    tx_repo.save(catalogue)

    partitioned = aggregate_renta_gasto_ledger_from_repositories(
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_Q1_2024,
        modelo="130",
        target_casilla_id=_M130_GASTOS_CASILLA,
        accept_activity_marker=True,
        transaction_repository=TransactionCatalogueRepository(
            bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
        ),
        prorrata_register_repository=ProrrataRegisterRepository(
            bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
        ),
    )
    full_scan = aggregate_renta_gasto_ledger(
        catalogue,
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_Q1_2024,
        modelo="130",
        target_casilla_id=_M130_GASTOS_CASILLA,
        accept_activity_marker=True,
    )

    assert set(partitioned.observations) == set(full_scan.observations)
    assert partitioned.casilla_aggregation.casilla_values == full_scan.casilla_aggregation.casilla_values
    assert set(partitioned.casilla_aggregation.provenance) == set(full_scan.casilla_aggregation.provenance)
    assert {o.transaction_id for o in partitioned.observations} == {q1_row.transaction_id}
    assert partitioned.issues == ()
    assert partitioned.out_of_window_summary is not None
    assert partitioned.out_of_window_summary.count == 2
    assert partitioned.out_of_window_summary.min_filing_date == date(2025, 8, 1)
    assert partitioned.out_of_window_summary.max_filing_date == date(2025, 9, 1)
    full_scan_issue_ids = {i.transaction_id for i in full_scan.issues}
    assert full_scan_issue_ids == {q3_row.transaction_id}
    assert wrong_direction_q3_row.transaction_id not in full_scan_issue_ids


def _profile_with_iva_regime(*iva_facts: UserProfileFact) -> UserProfileRecord:
    """Build a user-profile record from explicitly supplied IVA facts."""
    return _create_profile_record_for_test(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id="44444444-4444-4444-8444-444444444444",
        facts=(UserProfileFact(path="identity.tax_id", value="X1234567L"), *iva_facts),
        context=_profile_creation_context_for_test(),
    )


def test_repository_wrapper_exento_iva_regime_joins_the_full_iva_to_the_quarterly_gasto(
    secure_objects: SecureObjectRepository,
) -> None:
    """An EXENTO taxpayer's non-deductible input IVA joins the M130 gasto end to end."""
    row = _gasto_transaction(
        "row-exento",
        value_date=date(2025, 2, 1),
        amount=Decimal("9600.00"),
        taxable_base=Decimal("8000.00"),
        iva_amount=Decimal("1600.00"),
    )
    TransactionCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects).save(
        TransactionCatalogue.from_transactions((row,)),
    )

    def _run(profile_record: UserProfileRecord | None) -> Decimal:
        result = aggregate_renta_gasto_ledger_from_repositories(
            bucket_id=SECURE_OBJECTS_BUCKET_ID,
            period=_Q1_2024,
            modelo="130",
            target_casilla_id=_M130_GASTOS_CASILLA,
            accept_activity_marker=True,
            transaction_repository=TransactionCatalogueRepository(
                bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
            ),
            profile_record=profile_record,
            prorrata_register_repository=ProrrataRegisterRepository(
                bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
            ),
        )
        assert result.issues == ()
        return result.casilla_aggregation.casilla_values[_M130_GASTOS_CASILLA]

    exento_total = _run(
        _profile_with_iva_regime(
            UserProfileFact(path="iva.regime", value="EXENTO"),
            UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
            UserProfileFact(path="iva.m303_regime_composition", value="general"),
            UserProfileFact(path="iva.redeme_enrolled", value=False),
            UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
            UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
            UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
        ),
    )
    assert exento_total == Decimal("9600.00")
    general_total = _run(_profile_with_iva_regime())
    assert general_total == Decimal("8000.00")


def test_repository_wrapper_general_prorrata_register_joins_the_non_deductible_share_quarterly(
    secure_objects: SecureObjectRepository,
) -> None:
    """A GENERAL-prorrata register entry joins the non-recoverable IVA share into M130."""
    row = _gasto_transaction(
        "row-prorrata",
        value_date=date(2025, 2, 1),
        amount=Decimal("1210.00"),
        taxable_base=Decimal("1000.00"),
        iva_amount=Decimal("210.00"),
    )
    TransactionCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects).save(
        TransactionCatalogue.from_transactions((row,)),
    )
    ProrrataRegisterRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects).upsert_entry(
        ProrrataRegisterEntry(
            ejercicio=2025,
            regime=ProrrataRegisterRegime.from_registry("general"),
            especial_transition=None,
            provisional_percentage=Decimal("70"),
            provisional_provenance=ProrrataProvisionalProvenance.from_registry("carried_prior_definitiva"),
            source_registry_snapshot_refs=(_prior_m303_snapshot_ref(),),
        ),
    )

    result = aggregate_renta_gasto_ledger_from_repositories(
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_Q1_2024,
        modelo="130",
        target_casilla_id=_M130_GASTOS_CASILLA,
        accept_activity_marker=True,
        transaction_repository=TransactionCatalogueRepository(
            bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
        ),
        prorrata_register_repository=ProrrataRegisterRepository(
            bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
        ),
    )

    assert result.issues == ()
    assert result.casilla_aggregation.casilla_values[_M130_GASTOS_CASILLA] == Decimal("1063.00")


def test_repository_wrapper_ninguna_prorrata_regime_is_byte_identical_to_absent_entry_quarterly(
    secure_objects: SecureObjectRepository,
) -> None:
    """A NINGUNA regime entry changes nothing for M130 either."""
    row = _gasto_transaction(
        "row-ninguna",
        value_date=date(2025, 2, 1),
        amount=Decimal("1210.00"),
        taxable_base=Decimal("1000.00"),
        iva_amount=Decimal("210.00"),
    )
    TransactionCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects).save(
        TransactionCatalogue.from_transactions((row,)),
    )
    ProrrataRegisterRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects).upsert_entry(
        ProrrataRegisterEntry(
            ejercicio=2025,
            regime=ProrrataRegisterRegime.from_registry("ninguna"),
            especial_transition=None,
            source_registry_snapshot_refs=(),
        ),
    )

    result = aggregate_renta_gasto_ledger_from_repositories(
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_Q1_2024,
        modelo="130",
        target_casilla_id=_M130_GASTOS_CASILLA,
        accept_activity_marker=True,
        transaction_repository=TransactionCatalogueRepository(
            bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
        ),
        prorrata_register_repository=ProrrataRegisterRepository(
            bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
        ),
    )

    assert result.issues == ()
    assert result.casilla_aggregation.casilla_values[_M130_GASTOS_CASILLA] == Decimal("1000.00")


def test_m130_and_m100_resolve_the_same_iva_deduction_ratio_for_the_same_ejercicio(
    secure_objects: SecureObjectRepository,
) -> None:
    """M130 and M100 resolve one shared IVA deduction ratio through real repositories."""
    row = _gasto_transaction(
        "row-shared",
        value_date=date(2025, 2, 1),
        amount=Decimal("1210.00"),
        taxable_base=Decimal("1000.00"),
        iva_amount=Decimal("210.00"),
    )
    TransactionCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects).save(
        TransactionCatalogue.from_transactions((row,)),
    )
    ProrrataRegisterRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects).upsert_entry(
        ProrrataRegisterEntry(
            ejercicio=2025,
            regime=ProrrataRegisterRegime.from_registry("general"),
            especial_transition=None,
            provisional_percentage=Decimal("70"),
            provisional_provenance=ProrrataProvisionalProvenance.from_registry("carried_prior_definitiva"),
            source_registry_snapshot_refs=(_prior_m303_snapshot_ref(),),
        ),
    )

    m130_result = aggregate_renta_gasto_ledger_from_repositories(
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_Q1_2024,
        modelo="130",
        target_casilla_id=_M130_GASTOS_CASILLA,
        accept_activity_marker=True,
        transaction_repository=TransactionCatalogueRepository(
            bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
        ),
        prorrata_register_repository=ProrrataRegisterRepository(
            bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
        ),
    )
    assert m130_result.issues == ()
    assert m130_result.casilla_aggregation.casilla_values[_M130_GASTOS_CASILLA] == Decimal("1063.00")

    m100_result = aggregate_renta_ledger_expenses_from_repositories(
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=Period.from_year_and_code(2025, "0A"),
        ports=InvoiceCatalogueReadPorts(
            invoice_reader=InvoiceCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects),
            transaction_reader=TransactionCatalogueRepository(
                bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
            ),
        ),
        profile_year=2025,
        prorrata_register_repository=ProrrataRegisterRepository(
            bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
        ),
    )
    assert m100_result.issues == ()
    assert m100_result.observations[0].deductible_amount == Decimal("1063.00")
