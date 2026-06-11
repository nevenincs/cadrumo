"""Real-behaviour tests for source mesh enrollment in modelo calculation."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import Period
from ....domain.invoices import InvoiceCatalogueRepository
from ....domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from ....domain.modelos._repository import WorkUnitCatalogueRepository
from ....domain.transactions import TransactionCatalogueRepository
from ....tests.secure_sql import isolated_runtime_profile
from .. import (
    ModeloAggregationBindingError,
    calculate_modelo_revision_from_bucket_aggregation,
    create_work_unit,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_T0 = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)
_T1 = datetime(2026, 1, 10, 11, 0, tzinfo=UTC)


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="bucket-a") as profile:
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
    casilla_id: str,
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
