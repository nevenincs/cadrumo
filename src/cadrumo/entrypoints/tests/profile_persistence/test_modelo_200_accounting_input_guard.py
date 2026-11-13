"""M200 refuses ledger-backed zero results without accounting-result input.

Modelo 200 currently derives base imponible from the operator's accounting
result casilla 00501, not from transaction-ledger taxable bases. These tests use
real repositories and the live calculate action to prove a legal-entity bucket
with business ledger rows cannot silently calculate a zero M200 merely because
00501 was omitted.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from ....adapters.persistence.profile.tests.ready_profile_support import seed_persona_profile
from ....adapters.persistence.profile.tests.secure_objects_fixture import secure_objects
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ....application.modelo.action_errors import ModeloAggregationInputConflictError
from ....application.modelo.calculation_bucket_actions import (
    BucketAggregationCalculationResult,
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from ....application.modelo.work_lifecycle import create_work_unit
from ....application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from ....application.tests.wizard_catalogue_fixtures import register_wizard_catalogue
from ....core.authority_grade import RegistryAuthorityGrade
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.errors.error_codes import resolve_error_message
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from .file_flow_test_support import calculation_ports_for_test
from .observation_seeding_support import save_preceding_m200_turnover

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


__all__ = ["register_wizard_catalogue", "secure_objects"]

_BUCKET_ID = "2035baea-4afe-4fe3-b502-ff084fe79153"


@pytest.fixture
def bucket_id() -> str:
    return _BUCKET_ID


_T0 = datetime(2026, 1, 14, 10, 0, tzinfo=UTC)
# The sociedad-limitada persona's turnover of the twelve months before the period.
_PRECEDING_TURNOVER = Decimal("28500.00")
_T1 = datetime(2026, 1, 14, 11, 0, tzinfo=UTC)
_M200 = "200"
_FILING_YEAR = 2025
_RESULTADO_CONTABLE: CasillaId = validated_casilla_id("DP200012:00501", surface="_RESULTADO_CONTABLE")
_BASE_IMPONIBLE: CasillaId = validated_casilla_id("DP200014:00552", surface="_BASE_IMPONIBLE")
_CUOTA_EJERCICIO: CasillaId = validated_casilla_id("DP200014B:00599", surface="_CUOTA_EJERCICIO")


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
        counterparty="Cliente o proveedor",
        description=f"M200 ledger row {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="e" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=_T0,
            provider_name="manual-ledger",
        ),
        raw_fields={"source_kind": "ledger_transaction"},
    )


def _transaction(
    provider_id: str,
    *,
    direction: TransactionDirection,
    amount: Decimal,
    taxable_base: Decimal,
    iva_amount: Decimal,
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": _raw_transaction(
                provider_id,
                booked_date=date(_FILING_YEAR, 6, 30),
                amount=amount,
            ),
            "direction": direction,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "category_id": "m200_accounting_reviewed",
            "taxable_base": taxable_base,
            "iva_rate": Decimal("0.21"),
            "iva_amount": iva_amount,
            "classified_at": _T1,
            "classified_by": "manual",
        },
    )


def _seed_reviewed_business_ledger(tx_repo: TransactionCatalogueRepository) -> None:
    tx_repo.save(
        TransactionCatalogue.from_transactions(
            (
                _transaction(
                    "beatriz-income-100000",
                    direction=TransactionDirection.INCOMING,
                    amount=Decimal("121000.00"),
                    taxable_base=Decimal("100000.00"),
                    iva_amount=Decimal("21000.00"),
                ),
                _transaction(
                    "beatriz-expense-25000",
                    direction=TransactionDirection.OUTGOING,
                    amount=Decimal("30250.00"),
                    taxable_base=Decimal("25000.00"),
                    iva_amount=Decimal("5250.00"),
                ),
                _transaction(
                    "beatriz-expense-15000",
                    direction=TransactionDirection.OUTGOING,
                    amount=Decimal("18150.00"),
                    taxable_base=Decimal("15000.00"),
                    iva_amount=Decimal("3150.00"),
                ),
            ),
        ),
    )


def _create_m200_work_unit(work_unit_repository: WorkUnitCatalogueRepository, *, operation: PinnedAuthorityOperation):
    snapshot = published_authority_operation().snapshot(
        _M200,
        filing_year=_FILING_YEAR,
        period="0A",
        grade=RegistryAuthorityGrade.CALCULATION,
    )
    return create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo=_M200,
        filing_year=_FILING_YEAR,
        period=Period.from_year_and_code(_FILING_YEAR, "0A"),
        revision_id=snapshot.revision.id,
        ports=WorkLifecyclePorts(
            work_unit_repository=work_unit_repository,
            bucket_event_repository=BucketEventHistoryRepository(),
        ),
        clock=_T0,
        operation=operation,
    )


def _calculate_m200(
    secure_objects: SecureObjectRepository,
    *,
    casilla_inputs: dict[CasillaId, Decimal] | None = None,
    operation: PinnedAuthorityOperation,
) -> tuple[BucketAggregationCalculationResult, CalculationRevisionCatalogueRepository]:
    seed_persona_profile("sociedad-limitada", bucket_id=_BUCKET_ID, at=_T0)
    # The rate reads the preceding período's turnover from its own Modelo 200, held here at the
    # persona's stated twelve-month figure, so the two agree.
    save_preceding_m200_turnover(
        CalculationObservationRepository(), filing_year=_FILING_YEAR, turnover=_PRECEDING_TURNOVER, captured_at=_T0
    )
    wu_repo = WorkUnitCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    event_repo = BucketEventHistoryRepository(objects=secure_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    invoice_repo = InvoiceCatalogueRepository(objects=secure_objects)
    _seed_reviewed_business_ledger(tx_repo)
    work_unit = _create_m200_work_unit(wu_repo, operation=operation)
    with calculation_ports_for_test(
        bucket_id=_BUCKET_ID,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=event_repo,
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
    ) as _calculation_ports_216:
        result = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            actor="operator-Beatriz",
            casilla_inputs=casilla_inputs or {},
            ports=_calculation_ports_216,
            clock=_T1,
        )
    return result, cr_repo


def test_m200_refuses_business_ledger_rows_without_accounting_result_input(
    secure_objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
    with pytest.raises(ModeloAggregationInputConflictError) as exc_info:
        _calculate_m200(secure_objects, operation=operation)

    error = exc_info.value
    # The refusal is identified by its key and structured context, not by prose.
    assert error.translated_message == "application.modelo.errors.m200_accounting_result_required"
    assert resolve_error_message(error)
    assert error.context is not None
    assert error.context["required_casilla_id"] == _RESULTADO_CONTABLE
    assert error.context["ledger_transaction_count"] == 3
    failure = error.precondition_failure
    assert failure is not None
    assert failure.scenario_id == ("modelo.work.calculate.m200.accounting_result.ledger_rows_without_accounting_result")
    assert failure.verdict.no_recovery_outcome is not None


def test_m200_uses_explicit_accounting_result_even_when_reviewed_ledger_rows_exist(
    secure_objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
    result, _cr_repo = _calculate_m200(
        secure_objects,
        casilla_inputs={_RESULTADO_CONTABLE: Decimal("60000.00")},
        operation=operation,
    )

    values = result.revision.casilla_values
    assert values[_BASE_IMPONIBLE] == Decimal("60000.00")
    # LIS DT 44a 2025 micro-empresa transitional scale: 50.000 x 21% + 10.000 x 22%
    # = 10.500 + 2.200 = 12.700.
    assert values[_CUOTA_EJERCICIO] == Decimal("12700.00")
    assert values[_CUOTA_EJERCICIO] != Decimal("0.00")
