"""Rental aggregate tests using the persisted register repositories."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy.engine import Engine

from ....adapters.persistence.profile.fincas import (
    ArrendamientoRepository,
    FincaAmortizacionLedgerRepository,
    FincaGastoRepository,
    FincaRendimientoRepository,
    FincaRepository,
)
from ....adapters.persistence.storage.sql.engine import get_engine
from ....adapters.persistence.storage.sql.session import session_scope
from ....tests.secure_sql import isolated_runtime_profile
from ..aggregates import compute_finca_aggregates
from ..enums import ExpenseCategory, ReduccionTier, TitularContribuyente, TitularidadRegime, UseType
from ..models import Arrendamiento, Finca, FincaGasto, FincaRendimientoRecord
from ..titularidad import Titularidad

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(autouse=True)
def engine(tmp_path: Path) -> Iterator[Engine]:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        yield get_engine(profile.settings)


def test_rental_aggregates_are_derived_from_persisted_register(engine: Engine) -> None:
    with session_scope(engine) as session:
        finca_repo = FincaRepository(session)
        contract_repo = ArrendamientoRepository(session)
        income_repo = FincaRendimientoRepository(session)
        expense_repo = FincaGastoRepository(session)
        ledger_repo = FincaAmortizacionLedgerRepository(session)

        let_finca = finca_repo.upsert(
            Finca(
                identifier="let-finca",
                address="Calle Mayor 12, Madrid",
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
            ),
        )
        non_let_finca = finca_repo.upsert(
            Finca(
                identifier="non-let-finca",
                address="Calle Serrano 1, Madrid",
                valor_catastral_total=Decimal("100000.00"),
                valor_catastral_construccion=Decimal("70000.00"),
                valor_catastral_revision_year=2000,
                coste_adquisicion=Decimal("130000.00"),
                coste_adquisicion_construccion=Decimal("91000.00"),
                acquisition_date=date(2016, 1, 1),
                use_type=UseType.VIVIENDA_DESOCUPADA,
                titularidad=Titularidad(
                    regime=TitularidadRegime.PLENO_DOMINIO,
                    contribuyente=TitularContribuyente.PRIMER_DECLARANTE,
                    porcentaje_propiedad=Decimal("100.00"),
                ),
            ),
        )
        assert let_finca.id is not None
        assert non_let_finca.id is not None

        contract = contract_repo.upsert(
            Arrendamiento(
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
            FincaRendimientoRecord(
                contract_id=contract.id,
                period_year=2025,
                gross_rent_received=gross_rent,
                dias_alquilados=365,
            ),
        )
        expense_repo.add(
            FincaGasto(
                finca_id=let_finca.id,
                period_year=2025,
                category=ExpenseCategory.FINANCIACION_INTERESES,
                amount=financiacion,
            ),
        )
        expense_repo.add(
            FincaGasto(
                finca_id=let_finca.id,
                period_year=2025,
                category=ExpenseCategory.CONSERVACION_REPARACION,
                amount=reparacion,
            ),
        )
        expense_repo.add(
            FincaGasto(
                finca_id=let_finca.id,
                period_year=2025,
                category=ExpenseCategory.IBI_TRIBUTOS_NO_ESTATALES,
                amount=ibi,
            ),
        )

        aggregates = compute_finca_aggregates(
            period_year=2025,
            finca_repo=finca_repo,
            contract_repo=contract_repo,
            income_repo=income_repo,
            expense_repo=expense_repo,
            ledger_repo=ledger_repo,
        )

        assert aggregates.ingresos_integros == gross_rent
        assert aggregates.gastos_deducibles == financiacion + reparacion + ibi

        # Structural wiring: both fincas appear in attribution; the single
        # contract appears in the tier map.
        assert set(aggregates.per_finca_attribution) == {let_finca.id, non_let_finca.id}
        assert set(aggregates.per_contract_tier) == {contract.id}

        # Amortisation wires to the let finca only; the non-let finca is
        # not arrendable so must carry zero amortisation.
        let_attr = aggregates.per_finca_attribution[let_finca.id]
        non_let_attr = aggregates.per_finca_attribution[non_let_finca.id]
        assert let_attr.amortizacion > Decimal("0"), "let finca must carry non-zero amortisation"
        assert non_let_attr.amortizacion == Decimal("0.00"), "non-let finca must carry zero amortisation"
        assert aggregates.amortizacion == let_attr.amortizacion

        # Reducción attribution: the contract tier carries the reducción
        # amount and it equals the per-finca attribution total.
        contract_tier = aggregates.per_contract_tier[contract.id]
        assert contract_tier.reduccion_amount >= Decimal("0")
        assert aggregates.reduccion_arrendamiento_vivienda == contract_tier.reduccion_amount

        # Imputación wires to the non-let finca only; the arrendada finca
        # is not subject to art. 85.
        assert non_let_attr.imputacion > Decimal("0"), "non-let VIVIENDA_DESOCUPADA must carry imputación"
        assert let_attr.imputacion == Decimal("0.00"), "arrendada finca must carry zero imputación"
        assert aggregates.imputacion_rentas_inmobiliarias == non_let_attr.imputacion


@pytest.mark.parametrize("use_type", [UseType.LOCAL_COMERCIAL, UseType.VIVIENDA_TURISTICA])
def test_rental_aggregates_non_reduccion_use_types_earn_income_with_zero_reduction(
    engine: Engine,
    use_type: UseType,
) -> None:
    """LOCAL_COMERCIAL / VIVIENDA_TURISTICA fincas earn rendimiento/gastos/
    amortización like any active finca, but art. 23.2 LIRPF does not apply to
    them at all: the aggregate must not raise (the reducción resolver refuses
    non-VIVIENDA_ARRENDADA use types by design) and must attribute an explicit
    zero, non-qualifying reducción rather than skipping the contract."""
    with session_scope(engine) as session:
        finca_repo = FincaRepository(session)
        contract_repo = ArrendamientoRepository(session)
        income_repo = FincaRendimientoRepository(session)
        expense_repo = FincaGastoRepository(session)
        ledger_repo = FincaAmortizacionLedgerRepository(session)

        finca = finca_repo.upsert(
            Finca(
                identifier=f"{use_type.value}-finca",
                address="Calle Alcala 50, Madrid",
                valor_catastral_total=Decimal("200000.00"),
                valor_catastral_construccion=Decimal("140000.00"),
                valor_catastral_revision_year=2019,
                coste_adquisicion=Decimal("300000.00"),
                coste_adquisicion_construccion=Decimal("210000.00"),
                acquisition_date=date(2015, 1, 1),
                use_type=use_type,
                titularidad=Titularidad(
                    regime=TitularidadRegime.PLENO_DOMINIO,
                    contribuyente=TitularContribuyente.PRIMER_DECLARANTE,
                    porcentaje_propiedad=Decimal("100.00"),
                ),
            ),
        )
        assert finca.id is not None

        contract = contract_repo.upsert(
            Arrendamiento(
                finca_id=finca.id,
                contract_celebration_date=date(2022, 9, 1),
                tenant_count=1,
                initial_rent=Decimal("2000.00"),
            ),
        )
        assert contract.id is not None
        gross_rent = Decimal("24000.00")
        income_repo.upsert(
            FincaRendimientoRecord(
                contract_id=contract.id,
                period_year=2025,
                gross_rent_received=gross_rent,
                dias_alquilados=365,
            ),
        )

        aggregates = compute_finca_aggregates(
            period_year=2025,
            finca_repo=finca_repo,
            contract_repo=contract_repo,
            income_repo=income_repo,
            expense_repo=expense_repo,
            ledger_repo=ledger_repo,
        )

        assert aggregates.ingresos_integros == gross_rent
        finca_attr = aggregates.per_finca_attribution[finca.id]
        assert finca_attr.ingresos == gross_rent
        assert finca_attr.amortizacion > Decimal("0"), "an active let finca still accrues amortisation"

        contract_tier = aggregates.per_contract_tier[contract.id]
        assert contract_tier.tier.tier is ReduccionTier.NOT_APPLICABLE
        assert contract_tier.reduccion_amount == Decimal("0.00")
        assert aggregates.reduccion_arrendamiento_vivienda == Decimal("0.00")
