"""Rental aggregate tests using the persisted register repositories."""

from __future__ import annotations

import secrets
from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from aeat.adapters.persistence.storage import (
    EphemeralMasterKeyProvider,
    create_engine_from_settings,
    session_scope,
)
from aeat.adapters.persistence.storage.crypto._crypto import KEY_SIZE
from aeat.adapters.persistence.storage.sql._orm import Base
from aeat.core.config import Settings
from aeat.domain.rental import (
    ExpenseCategory,
    RentalAmortizationLedgerRepository,
    RentalContract,
    RentalContractRepository,
    RentalExpense,
    RentalExpenseRepository,
    RentalFinca,
    RentalFincaRepository,
    RentalIncomeRecord,
    RentalIncomeRepository,
    UseType,
    compute_rental_aggregates,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


@pytest.fixture(autouse=True)
def _patch_master_key() -> Iterator[None]:
    with EphemeralMasterKeyProvider(key=secrets.token_bytes(KEY_SIZE)):
        yield


def _engine(tmp_path: Path):
    settings = Settings(aeat_database_url=f"sqlite:///{(tmp_path / 'rental-aggregates.db').as_posix()}")
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(engine)
    return engine


def test_rental_aggregates_are_derived_from_persisted_register(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    try:
        with session_scope(engine) as session:
            finca_repo = RentalFincaRepository(session)
            contract_repo = RentalContractRepository(session)
            income_repo = RentalIncomeRepository(session)
            expense_repo = RentalExpenseRepository(session)
            ledger_repo = RentalAmortizationLedgerRepository(session)

            let_finca = finca_repo.upsert(
                RentalFinca(
                    identifier="let-finca",
                    address="Calle Mayor 12, Madrid",
                    valor_catastral_total=Decimal("180000.00"),
                    valor_catastral_construccion=Decimal("120000.00"),
                    valor_catastral_revision_year=2018,
                    coste_adquisicion=Decimal("250000.00"),
                    coste_adquisicion_construccion=Decimal("166666.67"),
                    acquisition_date=date(2010, 5, 14),
                    use_type=UseType.VIVIENDA_ARRENDADA,
                    is_stressed_area=True,
                ),
            )
            non_let_finca = finca_repo.upsert(
                RentalFinca(
                    identifier="non-let-finca",
                    address="Calle Serrano 1, Madrid",
                    valor_catastral_total=Decimal("100000.00"),
                    valor_catastral_construccion=Decimal("70000.00"),
                    valor_catastral_revision_year=2000,
                    coste_adquisicion=Decimal("130000.00"),
                    coste_adquisicion_construccion=Decimal("91000.00"),
                    acquisition_date=date(2016, 1, 1),
                    use_type=UseType.VIVIENDA_DESOCUPADA,
                ),
            )
            assert let_finca.id is not None
            assert non_let_finca.id is not None

            contract = contract_repo.upsert(
                RentalContract(
                    finca_id=let_finca.id,
                    contract_celebration_date=date(2022, 9, 1),
                    tenant_count=1,
                    initial_rent=Decimal("1000.00"),
                ),
            )
            assert contract.id is not None
            gross_rent = Decimal("12000.00")
            financiacion = Decimal("1000.00")
            reparacion = Decimal("500.00")
            ibi = Decimal("500.00")
            income_repo.upsert(
                RentalIncomeRecord(
                    contract_id=contract.id,
                    period_year=2025,
                    gross_rent_received=gross_rent,
                    dias_alquilados=365,
                ),
            )
            expense_repo.add(
                RentalExpense(
                    finca_id=let_finca.id,
                    period_year=2025,
                    category=ExpenseCategory.FINANCIACION_INTERESES,
                    amount=financiacion,
                ),
            )
            expense_repo.add(
                RentalExpense(
                    finca_id=let_finca.id,
                    period_year=2025,
                    category=ExpenseCategory.CONSERVACION_REPARACION,
                    amount=reparacion,
                ),
            )
            expense_repo.add(
                RentalExpense(
                    finca_id=let_finca.id,
                    period_year=2025,
                    category=ExpenseCategory.IBI_TRIBUTOS_NO_ESTATALES,
                    amount=ibi,
                ),
            )

            aggregates = compute_rental_aggregates(
                period_year=2025,
                finca_repo=finca_repo,
                contract_repo=contract_repo,
                income_repo=income_repo,
                expense_repo=expense_repo,
                ledger_repo=ledger_repo,
            )

            expected_amortizacion = Decimal("5000.00")
            expected_reduccion = Decimal("3000.00")
            expected_imputacion = Decimal("2000.00")
            assert aggregates.ingresos_integros == gross_rent
            assert aggregates.gastos_deducibles == financiacion + reparacion + ibi
            assert aggregates.amortizacion == expected_amortizacion
            assert aggregates.reduccion_arrendamiento_vivienda == expected_reduccion
            assert aggregates.imputacion_rentas_inmobiliarias == expected_imputacion
            assert set(aggregates.per_finca_attribution) == {let_finca.id, non_let_finca.id}
            assert set(aggregates.per_contract_tier) == {contract.id}
    finally:
        engine.dispose()
