"""Real-behaviour tests for source mesh enrollment in modelo calculation."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import Period
from ....domain.calculations.registry import CasillaId
from ....domain.invoices import InvoiceCatalogueRepository
from ....domain.iva import EUMemberState, IvaCategory
from ....domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from ....domain.modelos._repository import WorkUnitCatalogueRepository
from ....domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionCatalogueRepository,
    TransactionDirection,
    TransactionLifecycleState,
)
from ....domain.user_profile import UserProfileFact, UserProfileRecord
from ....tests.secure_sql import isolated_runtime_profile
from ...user_profile import UserProfileLifecycleRepository
from .. import (
    ModeloAggregationBindingError,
    calculate_modelo_revision_from_bucket_aggregation,
    create_work_unit,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_T0 = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)
_T1 = datetime(2026, 1, 10, 11, 0, tzinfo=UTC)
_READY_PROFILE_FACTS = (
    UserProfileFact(path="identity.tax_id", value="12345678Z"),
    UserProfileFact(path="identity.name", value="Ready"),
    UserProfileFact(path="identity.surnames", value="Operator"),
    UserProfileFact(path="activities.description", value="source mesh"),
    UserProfileFact(path="tax_residence.ccaa", value="madrid"),
    UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
    UserProfileFact(path="iva.regime", value="GENERAL"),
    UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
    UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
    UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
    UserProfileFact(path="censo.activity_start_date", value=date(2020, 1, 1)),
    UserProfileFact(path="renta_taxpayer.birth_date", value=date(1980, 3, 15)),
    UserProfileFact(path="renta_taxpayer.sex", value="varon"),
    UserProfileFact(path="renta_taxpayer.marital_status", value="soltero"),
    UserProfileFact(path="renta_taxpayer.marriage_full_year", value=Decimal("0")),
    UserProfileFact(path="renta_taxpayer.marriage_month_start", value=Decimal("0")),
    UserProfileFact(path="renta_taxpayer.marriage_month_end", value=Decimal("0")),
    UserProfileFact(path="filing_export.declaration_type", value="1"),
    UserProfileFact(path="renta_family.minor_children_in_unit", value=Decimal("0")),
    UserProfileFact(path="renta_family.descendientes_count", value=Decimal("0")),
    UserProfileFact(path="renta_family.descendants_eu_eea_deduction", value=Decimal("0")),
)


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="bucket-a") as profile:
        UserProfileLifecycleRepository(bucket_id="bucket-a", objects=profile.repository).save(
            UserProfileRecord(
                profile_id="bucket-a",
                display_name="Source mesh ready profile",
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
        TransactionCatalogueRepository(bucket_id="bucket-a", objects=objects),
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
        bucket_id="bucket-a",
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
        transaction_id=provider_id,
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


def _intracom_ledger_transaction(provider_id: str) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": _raw_transaction(provider_id, booked_date=date(2026, 2, 10), amount=Decimal("1000.00")),
            "direction": TransactionDirection.INCOMING,
            "business_classification": BusinessClassification.BUSINESS,
            "category_id": "intracom_supply",
            "taxable_base": Decimal("1000.00"),
            "iva_rate": Decimal("0"),
            "iva_amount": Decimal("0"),
            "iva_category": IvaCategory.INTRA_COMMUNITY_SUPPLY,
            "counterparty_eu_member_state": EUMemberState.DE,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": datetime(2026, 2, 11, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


@pytest.mark.parametrize(
    ("modelo", "filing_year", "period", "revision_id", "binding_id"),
    [
        ("303", 2026, "1T", "2023-y-siguientes", "modelo-303-iva-repercutido-general-cuota"),
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
    assert intracom_sale.transaction_id in exc_info.value.context["sample_transaction_ids"]
    assert exc_info.value.suggestion == "aeat app ledger invoice add --help"
    assert cr_repo.load().revisions == {}


@pytest.mark.parametrize(
    ("modelo", "filing_year", "period", "revision_id", "casilla_id"),
    [
        ("303", 2026, "1T", "2023-y-siguientes", "iva.repercutido.general"),
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
