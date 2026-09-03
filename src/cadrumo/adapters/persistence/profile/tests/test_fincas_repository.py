"""Round-trip CRUD tests for the rental-register repositories.

These concrete repositories live in the persistence adapter
(:mod:`cadrumo.adapters.persistence.profile.fincas`); they satisfy the
read-side ports declared in :mod:`cadrumo.domain.fincas.repository_ports`.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy.engine import Engine

from ._fincas_engine_fixture import engine

__all__ = ["engine"]

from .....domain.fincas.enums import ExpenseCategory, TitularContribuyente, TitularidadRegime, UseType
from .....domain.fincas.models import (
    Arrendamiento,
    Finca,
    FincaAmortizacionLedgerEntry,
    FincaGasto,
    FincaRendimientoRecord,
)
from .....domain.fincas.titularidad import Titularidad
from ...storage.errors import RepositoryError
from ...storage.sql.session import session_scope
from ..fincas import (
    ArrendamientoRepository,
    FincaAmortizacionLedgerRepository,
    FincaGastoRepository,
    FincaRendimientoRepository,
    FincaRepository,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def _sample_finca(identifier: str = "calle-mayor-12-3a") -> Finca:
    return Finca(
        identifier=identifier,
        address="Calle Mayor 12, 3.º A, 28013 Madrid",
        valor_catastral_total=Decimal("180000.00"),
        valor_catastral_construccion=Decimal("120000.00"),
        valor_catastral_revision_year=2018,
        coste_adquisicion=Decimal("250000.00"),
        coste_adquisicion_construccion=Decimal("166666.67"),
        acquisition_date=date(2010, 5, 14),
        use_type=UseType.VIVIENDA_ARRENDADA,
        titularidad=Titularidad(
            regime=TitularidadRegime.PLENO_DOMINIO,
            contribuyente=TitularContribuyente.PRIMER_DECLARANTE,
            porcentaje_propiedad=Decimal("100.00"),
        ),
        is_stressed_area=True,
    )


def test_finca_repository_round_trip(engine: Engine) -> None:
    with session_scope(engine) as session:
        repo = FincaRepository(session)
        created = repo.upsert(_sample_finca())
        assert created.id is not None
        assert created.address.startswith("Calle Mayor")
        assert created.use_type is UseType.VIVIENDA_ARRENDADA
        assert created.is_stressed_area is True

        assert repo.list_all() == [created]
        assert repo.get_by_identifier("calle-mayor-12-3a") == created

        updated = repo.upsert(
            Finca(
                id=created.id,
                identifier=created.identifier,
                address="Calle Mayor 12, 3.º A, 28013 Madrid (renovado)",
                valor_catastral_total=created.valor_catastral_total,
                valor_catastral_construccion=created.valor_catastral_construccion,
                valor_catastral_revision_year=created.valor_catastral_revision_year,
                coste_adquisicion=created.coste_adquisicion,
                coste_adquisicion_construccion=created.coste_adquisicion_construccion,
                acquisition_date=created.acquisition_date,
                use_type=created.use_type,
                titularidad=Titularidad(
                    regime=TitularidadRegime.PLENO_DOMINIO,
                    contribuyente=TitularContribuyente.PRIMER_DECLARANTE,
                    porcentaje_propiedad=Decimal("100.00"),
                ),
                is_stressed_area=False,
            ),
        )
        assert updated.address.endswith("(renovado)")
        assert updated.is_stressed_area is False

        repo.delete(created.id)
        with pytest.raises(RepositoryError):
            repo.get(created.id)


def test_finca_construction_basis_validation_rejects_inverted_split(tmp_path: Path) -> None:
    """coste_adquisicion_construccion must not exceed coste_adquisicion."""
    with pytest.raises(ValueError, match="coste_adquisicion_construccion"):
        Finca(
            identifier="bad-finca",
            address="X",
            valor_catastral_total=Decimal("100"),
            valor_catastral_construccion=Decimal("60"),
            coste_adquisicion=Decimal("100"),
            coste_adquisicion_construccion=Decimal("150"),
            acquisition_date=date(2020, 1, 1),
            use_type=UseType.VIVIENDA_ARRENDADA,
            titularidad=Titularidad(
                regime=TitularidadRegime.PLENO_DOMINIO,
                contribuyente=TitularContribuyente.PRIMER_DECLARANTE,
                porcentaje_propiedad=Decimal("100.00"),
            ),
        )


def test_contract_repository_round_trip(engine: Engine) -> None:
    with session_scope(engine) as session:
        finca_repo = FincaRepository(session)
        finca = finca_repo.upsert(_sample_finca())
        contract_repo = ArrendamientoRepository(session)
        assert finca.id is not None
        contract = contract_repo.upsert(
            Arrendamiento(
                finca_id=finca.id,
                contract_celebration_date=date(2024, 6, 1),
                tenant_count=2,
                qualifying_co_tenant_count=1,
                tenant_min_age=30,
                tenant_max_age=42,
                initial_rent=Decimal("950.00"),
                is_first_rental=True,
            ),
        )
        assert contract.id is not None
        assert contract.qualifying_co_tenant_count == 1

        listed = contract_repo.list_for_finca(finca.id)
        assert listed == [contract]

        terminated = contract_repo.upsert(
            Arrendamiento(
                id=contract.id,
                finca_id=finca.id,
                contract_celebration_date=contract.contract_celebration_date,
                contract_termination_date=date(2025, 12, 31),
                tenant_count=contract.tenant_count,
                qualifying_co_tenant_count=contract.qualifying_co_tenant_count,
                tenant_min_age=contract.tenant_min_age,
                tenant_max_age=contract.tenant_max_age,
                initial_rent=contract.initial_rent,
                is_first_rental=contract.is_first_rental,
            ),
        )
        assert terminated.contract_termination_date == date(2025, 12, 31)


def test_contract_validation_rejects_termination_before_celebration() -> None:
    with pytest.raises(ValueError, match="contract_termination_date"):
        Arrendamiento(
            finca_id=1,
            contract_celebration_date=date(2024, 6, 1),
            contract_termination_date=date(2024, 5, 31),
            tenant_count=1,
            initial_rent=Decimal("500.00"),
        )


def test_contract_validation_rejects_qualifying_share_overflow() -> None:
    with pytest.raises(ValueError, match="qualifying_co_tenant_count"):
        Arrendamiento(
            finca_id=1,
            contract_celebration_date=date(2024, 6, 1),
            tenant_count=2,
            qualifying_co_tenant_count=3,
            initial_rent=Decimal("500.00"),
        )


def test_income_repository_unique_per_period(engine: Engine) -> None:
    with session_scope(engine) as session:
        finca_repo = FincaRepository(session)
        contract_repo = ArrendamientoRepository(session)
        income_repo = FincaRendimientoRepository(session)
        finca = finca_repo.upsert(_sample_finca())
        assert finca.id is not None
        contract = contract_repo.upsert(
            Arrendamiento(
                finca_id=finca.id,
                contract_celebration_date=date(2024, 1, 1),
                tenant_count=1,
                initial_rent=Decimal("1000.00"),
            ),
        )
        assert contract.id is not None
        first = income_repo.upsert(
            FincaRendimientoRecord(
                contract_id=contract.id,
                period_year=2025,
                gross_rent_received=Decimal("12000.00"),
                dias_alquilados=365,
            ),
        )
        assert first.id is not None

        updated = income_repo.upsert(
            FincaRendimientoRecord(
                contract_id=contract.id,
                period_year=2025,
                gross_rent_received=Decimal("13200.00"),
                dias_alquilados=365,
            ),
        )
        assert updated.id == first.id
        assert updated.gross_rent_received == Decimal("13200.00")
        assert income_repo.list_for_period(2025) == [updated]


def test_expense_repository_multiple_categories(engine: Engine) -> None:
    with session_scope(engine) as session:
        finca_repo = FincaRepository(session)
        expense_repo = FincaGastoRepository(session)
        finca = finca_repo.upsert(_sample_finca())
        assert finca.id is not None
        expense_repo.add(
            FincaGasto(
                finca_id=finca.id,
                period_year=2025,
                category=ExpenseCategory.IBI_TRIBUTOS_NO_ESTATALES,
                amount=Decimal("420.00"),
            ),
        )
        expense_repo.add(
            FincaGasto(
                finca_id=finca.id,
                period_year=2025,
                category=ExpenseCategory.COMUNIDAD,
                amount=Decimal("780.00"),
            ),
        )
        listed = expense_repo.list_for_finca_period(finca.id, 2025)
        assert {e.category for e in listed} == {
            ExpenseCategory.IBI_TRIBUTOS_NO_ESTATALES,
            ExpenseCategory.COMUNIDAD,
        }


def test_amortization_ledger_repository_unique_per_finca_period(engine: Engine) -> None:
    with session_scope(engine) as session:
        finca_repo = FincaRepository(session)
        ledger_repo = FincaAmortizacionLedgerRepository(session)
        finca = finca_repo.upsert(_sample_finca())
        assert finca.id is not None
        entry_a = ledger_repo.upsert(
            FincaAmortizacionLedgerEntry(
                finca_id=finca.id,
                period_year=2024,
                dias_alquilados=365,
                basis_used=Decimal("166666.67"),
                amortization_amount=Decimal("5000.00"),
                cumulative_amortization_through_year=Decimal("5000.00"),
            ),
        )
        entry_b = ledger_repo.upsert(
            FincaAmortizacionLedgerEntry(
                finca_id=finca.id,
                period_year=2025,
                dias_alquilados=365,
                basis_used=Decimal("166666.67"),
                amortization_amount=Decimal("5000.00"),
                cumulative_amortization_through_year=Decimal("10000.00"),
            ),
        )
        assert entry_a.id != entry_b.id

        re_2024 = ledger_repo.upsert(
            FincaAmortizacionLedgerEntry(
                finca_id=finca.id,
                period_year=2024,
                dias_alquilados=180,
                basis_used=Decimal("166666.67"),
                amortization_amount=Decimal("2500.00"),
                cumulative_amortization_through_year=Decimal("2500.00"),
            ),
        )
        assert re_2024.id == entry_a.id
        assert re_2024.amortization_amount == Decimal("2500.00")

        assert ledger_repo.list_for_finca(finca.id) == [re_2024, entry_b]
