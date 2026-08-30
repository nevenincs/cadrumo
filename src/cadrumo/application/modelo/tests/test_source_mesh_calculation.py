"""Real-behaviour tests for source mesh enrollment in modelo calculation."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import Period
from ....core.casilla_id import CasillaId
from ....domain.iva.schema import IvaCategory
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.secure_sql import isolated_runtime_profile
from .._action_errors import ModeloAggregationBindingError
from .._calculation_actions import calculate_modelo_revision_from_bucket_aggregation
from ..work_lifecycle import create_work_unit

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_T0 = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)
_T1 = datetime(2026, 1, 10, 11, 0, tzinfo=UTC)
_BUCKET = "44444444-4444-4444-8444-444444444444"
_READY_PROFILE_FACTS = (
    UserProfileFact(path="identity.tax_id", value="12345678Z"),
    UserProfileFact(path="identity.name", value="Ready"),
    UserProfileFact(path="identity.surnames", value="Operator"),
    UserProfileFact(path="activities.description", value="source mesh"),
    UserProfileFact(path="tax_residence.ccaa", value="madrid"),
    UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
    UserProfileFact(path="iva.regime", value="GENERAL"),
    UserProfileFact(path="iva.m303_regime_composition", value="general"),
    UserProfileFact(path="iva.redeme_enrolled", value=False),
    UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
    UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
    UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
    UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
    UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
    UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
    UserProfileFact(path="censo.activity_start_date", value=date(2020, 1, 1)),
    UserProfileFact(path="renta_taxpayer.birth_date", value=date(1980, 3, 15)),
    UserProfileFact(path="renta_taxpayer.sex", value="H"),
    UserProfileFact(path="renta_taxpayer.marital_status", value="1"),
    UserProfileFact(path="renta_taxpayer.marriage_full_year", value=Decimal("0")),
    UserProfileFact(path="renta_taxpayer.marriage_month_start", value=Decimal("0")),
    UserProfileFact(path="renta_taxpayer.marriage_month_end", value=Decimal("0")),
    UserProfileFact(path="renta_filing.declaration_type", value="1"),
    UserProfileFact(path="renta_family.minor_children_in_unit", value=False),
    UserProfileFact(path="renta_family.descendientes_count", value=Decimal("0")),
    UserProfileFact(path="renta_family.descendants_eu_eea_deduction", value=False),
)


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile:
        seed_test_profile_record(
            UserProfileRecord(
                setup_state=ProfileSetupState.COMPLETE,
                profile_id=_BUCKET,
                facts=_READY_PROFILE_FACTS,
                created_at=_T0,
                updated_at=_T0,
            ),
        )
        yield profile.repository


def _repositories(objects: SecureObjectRepository):
    return (
        WorkUnitCatalogueRepository(objects=objects),
        CalculationRevisionCatalogueRepository(objects=objects),
        TransactionCatalogueRepository(bucket_id=_BUCKET, objects=objects),
        InvoiceCatalogueRepository(objects=objects),
    )


def _seed_work_unit(
    work_unit_repository: WorkUnitCatalogueRepository,
    *,
    modelo: str,
    filing_year: int,
    period: str,
    revision_id: str,
):
    return create_work_unit(
        bucket_id=_BUCKET,
        modelo=modelo,
        filing_year=filing_year,
        period=Period.from_year_and_code(filing_year, period),
        revision_id=revision_id,
        repository=work_unit_repository,
        clock=_T0,
    )


def _raw_transaction(
    provider_id: str,
    *,
    booked_date: date,
    amount: Decimal,
) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=booked_date,
        value_date=booked_date,
        amount=amount,
        currency="EUR",
        counterparty="EU GmbH",
        description=f"M349 source mesh {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="3" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(2026, 2, 11, 12, 0, tzinfo=UTC),
            provider_name="manual-ledger",
        ),
        raw_fields={"source_kind": "ledger_transaction"},
    )


def _intracom_ledger_transaction(provider_id: str, *, booked_date: date = date(2026, 2, 10)) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": _raw_transaction(provider_id, booked_date=booked_date, amount=Decimal("1000.00")),
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "business_classification": BusinessClassification.BUSINESS,
            "source_jurisdiction": "ES",
            "category_id": "intracom_supply",
            "taxable_base": Decimal("1000.00"),
            "iva_rate": Decimal("0"),
            "iva_amount": Decimal("0"),
            "iva_category": IvaCategory.INTRA_COMMUNITY_SUPPLY,
            "counterparty_country": "DE",
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": datetime(2026, 2, 11, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


@pytest.mark.parametrize(
    ("modelo", "filing_year", "period", "revision_id", "binding_id"),
    [
        ("303", 2026, "1T", "2026-y-siguientes", "modelo-303-iva-repercutido-general-cuota"),
        ("100", 2025, "0A", "2025", "renta-2025-ledger-expense-0199-deductible"),
    ],
)
def test_bucket_calculation_rejects_source_owned_binding_overrides(
    secure_objects: SecureObjectRepository,
    modelo: str,
    filing_year: int,
    period: str,
    revision_id: str,
    binding_id: str,
) -> None:
    wu_repo, cr_repo, tx_repo, invoice_repo = _repositories(secure_objects)
    work_unit = _seed_work_unit(
        wu_repo,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        revision_id=revision_id,
    )

    with pytest.raises(ModeloAggregationBindingError) as excinfo:
        calculate_modelo_revision_from_bucket_aggregation(
            work_unit.work_unit_id,
            actor="operator-A",
            binding_values={binding_id: Decimal("99.00")},
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            transaction_repository=tx_repo,
            invoice_repository=invoice_repo,
            clock=_T1,
        )
    assert excinfo.value.translated_message == "errors.error.error_modelo_aggregation_binding"

    assert cr_repo.load().revisions == {}


def test_modelo_349_refuses_intracom_ledger_rows_without_operator_rows(
    secure_objects: SecureObjectRepository,
) -> None:
    wu_repo, cr_repo, tx_repo, invoice_repo = _repositories(secure_objects)
    work_unit = _seed_work_unit(
        wu_repo,
        modelo="349",
        filing_year=2026,
        period="1T",
        revision_id="2020-y-siguientes",
    )
    intracom_sale = _intracom_ledger_transaction("intracom-sale-de")
    tx_repo.save(TransactionCatalogue.from_transactions((intracom_sale,)))

    with pytest.raises(ModeloAggregationBindingError) as exc_info:
        calculate_modelo_revision_from_bucket_aggregation(
            work_unit.work_unit_id,
            actor="operator-A",
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            transaction_repository=tx_repo,
            invoice_repository=invoice_repo,
            clock=_T1,
        )

    assert "no declarable operator rows" in str(exc_info.value)
    assert exc_info.value.context is not None
    assert exc_info.value.context["modelo"] == "349"
    assert exc_info.value.context["period"] == "1T"
    assert exc_info.value.context["transaction_count"] == 1
    sample_transaction_ids = exc_info.value.context["sample_transaction_ids"]
    assert isinstance(sample_transaction_ids, tuple)
    assert intracom_sale.transaction_id in sample_transaction_ids
    failure = exc_info.value.precondition_failure
    assert failure is not None
    assert failure.scenario_id == ("modelo.work.calculate.m349.operator_rows.intracom_ledger_without_operator_rows")
    assert failure.verdict.no_recovery_outcome is not None
    assert cr_repo.load().revisions == {}


def test_modelo_349_monthly_refuses_midmonth_intracom_ledger_rows_without_operator_rows(
    secure_objects: SecureObjectRepository,
) -> None:
    """A March 20 raw intracom row remains inside the March monthly period and fails closed."""
    wu_repo, cr_repo, tx_repo, invoice_repo = _repositories(secure_objects)
    work_unit = _seed_work_unit(
        wu_repo,
        modelo="349",
        filing_year=2026,
        period="03",
        revision_id="2020-y-siguientes",
    )
    intracom_sale = _intracom_ledger_transaction("intracom-sale-march-20", booked_date=date(2026, 3, 20))
    tx_repo.save(TransactionCatalogue.from_transactions((intracom_sale,)))

    with pytest.raises(ModeloAggregationBindingError) as exc_info:
        calculate_modelo_revision_from_bucket_aggregation(
            work_unit.work_unit_id,
            actor="operator-A",
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            transaction_repository=tx_repo,
            invoice_repository=invoice_repo,
            clock=_T1,
        )

    assert exc_info.value.context is not None
    assert exc_info.value.context["period"] == "03"
    assert exc_info.value.context["transaction_count"] == 1
    raw_sample_transaction_ids = exc_info.value.context["sample_transaction_ids"]
    assert isinstance(raw_sample_transaction_ids, tuple)
    sample_transaction_ids = tuple(value for value in raw_sample_transaction_ids if isinstance(value, str))
    assert len(sample_transaction_ids) == len(raw_sample_transaction_ids)
    assert intracom_sale.transaction_id in sample_transaction_ids
    assert cr_repo.load().revisions == {}


@pytest.mark.parametrize(
    ("modelo", "filing_year", "period", "revision_id", "casilla_id"),
    [
        ("303", 2026, "1T", "2026-y-siguientes", "iva.repercutido.general"),
        ("100", 2025, "0A", "2025", "0199"),
    ],
)
def test_bucket_calculation_rejects_source_owned_bound_casilla_overrides(
    secure_objects: SecureObjectRepository,
    modelo: str,
    filing_year: int,
    period: str,
    revision_id: str,
    casilla_id: CasillaId,
) -> None:
    wu_repo, cr_repo, tx_repo, invoice_repo = _repositories(secure_objects)
    work_unit = _seed_work_unit(
        wu_repo,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        revision_id=revision_id,
    )

    with pytest.raises(ModeloAggregationBindingError) as exc_info:
        calculate_modelo_revision_from_bucket_aggregation(
            work_unit.work_unit_id,
            actor="operator-A",
            casilla_inputs={casilla_id: Decimal("99.00")},
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            transaction_repository=tx_repo,
            invoice_repository=invoice_repo,
            clock=_T1,
        )
    assert exc_info.value.translated_message == "application.modelo.errors.caller_casilla_source_binding_conflict"
    assert exc_info.value.context is not None
    casillas = exc_info.value.context["casillas"]
    assert isinstance(casillas, (list, tuple, set, frozenset))
    assert casilla_id in casillas

    assert cr_repo.load().revisions == {}
