"""M100 Anexo C aggregator + backwards-compat shim tests (#454)."""

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
    override_master_key_provider,
    session_scope,
)
from aeat.adapters.persistence.storage.crypto._crypto import KEY_SIZE
from aeat.adapters.persistence.storage.sql._orm import Base
from aeat.core.config import Settings
from aeat.domain.rental import (
    ANEXO_C_CASILLAS,
    ExpenseCategory,
    ReduccionTier,
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
    compute_anexo_c_aggregates,
    compute_or_passthrough,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


@pytest.fixture(autouse=True)
def _patch_master_key() -> Iterator[None]:
    override_master_key_provider(EphemeralMasterKeyProvider(key=secrets.token_bytes(KEY_SIZE)))
    try:
        yield
    finally:
        override_master_key_provider(None)


def _engine(tmp_path: Path):
    settings = Settings(aeat_database_url=f"sqlite:///{(tmp_path / 'rental.db').as_posix()}")
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(engine)
    return engine


class TestEmptyRegister:
    def test_no_fincas_returns_zero_aggregates(self, tmp_path: Path) -> None:
        engine = _engine(tmp_path)
        try:
            with session_scope(engine) as session:
                aggregates = compute_anexo_c_aggregates(
                    period_year=2025,
                    finca_repo=RentalFincaRepository(session),
                    contract_repo=RentalContractRepository(session),
                    income_repo=RentalIncomeRepository(session),
                    expense_repo=RentalExpenseRepository(session),
                    ledger_repo=RentalAmortizationLedgerRepository(session),
                )
                assert aggregates.casilla_0061 == Decimal("0.00")
                assert aggregates.casilla_0066 == Decimal("0.00")
                assert aggregates.casilla_0072 == Decimal("0.00")
                assert aggregates.casilla_0078 == Decimal("0.00")
                assert aggregates.casilla_0085 == Decimal("0.00")
        finally:
            engine.dispose()


class TestPassthrough:
    def test_no_repositories_passes_through(self) -> None:
        provided = {
            "0061": Decimal("12000.00"),
            "0066": Decimal("3500.00"),
            "0072": Decimal("1500.00"),
            "0078": Decimal("3500.00"),
            "0085": Decimal("0.00"),
        }
        report = compute_or_passthrough(period_year=2025, provided_casillas=provided)
        assert report.register_used is False
        assert report.aggregates is None
        assert report.effective_casillas == provided
        assert report.overridden == {}

    def test_empty_register_passes_through(self, tmp_path: Path) -> None:
        engine = _engine(tmp_path)
        try:
            with session_scope(engine) as session:
                provided = {
                    "0061": Decimal("12000.00"),
                    "0066": Decimal("3500.00"),
                    "0072": Decimal("1500.00"),
                    "0078": Decimal("3500.00"),
                    "0085": Decimal("0.00"),
                }
                report = compute_or_passthrough(
                    period_year=2025,
                    provided_casillas=provided,
                    finca_repo=RentalFincaRepository(session),
                    contract_repo=RentalContractRepository(session),
                    income_repo=RentalIncomeRepository(session),
                    expense_repo=RentalExpenseRepository(session),
                    ledger_repo=RentalAmortizationLedgerRepository(session),
                )
                assert report.register_used is False
                assert report.effective_casillas == provided
        finally:
            engine.dispose()


class TestSingleFincaTier50:
    def test_single_finca_default_tier_aggregates(self, tmp_path: Path) -> None:
        """One finca, one contract (no zona, no rehab, no joven) → tier 50.

        Numbers chosen so the rounding is clean:
          - Coste construcción 100 000, catastral construcción 80 000 →
            basis 100 000; amortización 365/365 = 3 000.
          - Ingresos 12 000.
          - Gastos uncapped IBI 500 + COMUNIDAD 800 = 1 300.
          - Gastos capped FINANCIACION 2 200 + REPAR 0 = 2 200,
            ingresos 12 000 → no cap excess.
          - Total 0066 = 1 300 + 2 200 = 3 500.
          - 0072 = 3 000.
          - Rendimiento neto = 12 000 - 3 500 - 3 000 = 5 500.
          - Tier 50 → reducción 2 750.
          - 0078 = 2 750.
        """
        engine = _engine(tmp_path)
        try:
            with session_scope(engine) as session:
                finca_repo = RentalFincaRepository(session)
                contract_repo = RentalContractRepository(session)
                income_repo = RentalIncomeRepository(session)
                expense_repo = RentalExpenseRepository(session)
                ledger_repo = RentalAmortizationLedgerRepository(session)

                finca = finca_repo.upsert(
                    RentalFinca(
                        identifier="finca-1",
                        address="X",
                        valor_catastral_total=Decimal("120000.00"),
                        valor_catastral_construccion=Decimal("80000.00"),
                        coste_adquisicion=Decimal("180000.00"),
                        coste_adquisicion_construccion=Decimal("100000.00"),
                        acquisition_date=date(2010, 1, 1),
                        use_type=UseType.VIVIENDA_ARRENDADA,
                    ),
                )
                assert finca.id is not None
                contract = contract_repo.upsert(
                    RentalContract(
                        finca_id=finca.id,
                        contract_celebration_date=date(2024, 1, 1),
                        tenant_count=1,
                        initial_rent=Decimal("1000.00"),
                    ),
                )
                assert contract.id is not None
                income_repo.upsert(
                    RentalIncomeRecord(
                        contract_id=contract.id,
                        period_year=2025,
                        gross_rent_received=Decimal("12000.00"),
                        dias_alquilados=365,
                    ),
                )
                expense_repo.add(
                    RentalExpense(
                        finca_id=finca.id,
                        period_year=2025,
                        category=ExpenseCategory.IBI_TRIBUTOS_NO_ESTATALES,
                        amount=Decimal("500.00"),
                    ),
                )
                expense_repo.add(
                    RentalExpense(
                        finca_id=finca.id,
                        period_year=2025,
                        category=ExpenseCategory.COMUNIDAD,
                        amount=Decimal("800.00"),
                    ),
                )
                expense_repo.add(
                    RentalExpense(
                        finca_id=finca.id,
                        period_year=2025,
                        category=ExpenseCategory.FINANCIACION_INTERESES,
                        amount=Decimal("2200.00"),
                    ),
                )

                aggregates = compute_anexo_c_aggregates(
                    period_year=2025,
                    finca_repo=finca_repo,
                    contract_repo=contract_repo,
                    income_repo=income_repo,
                    expense_repo=expense_repo,
                    ledger_repo=ledger_repo,
                )
                assert aggregates.casilla_0061 == Decimal("12000.00")
                assert aggregates.casilla_0066 == Decimal("3500.00")
                assert aggregates.casilla_0072 == Decimal("3000.00")
                assert aggregates.casilla_0078 == Decimal("2750.00")
                assert aggregates.casilla_0085 == Decimal("0.00")
                # Tier attribution is 50.
                tier_attrib = next(iter(aggregates.per_contract_tier.values()))
                assert tier_attrib.tier.tier is ReduccionTier.TIER_50
                assert tier_attrib.reduccion_amount == Decimal("2750.00")
        finally:
            engine.dispose()


class TestImputacionRentasInmobiliarias:
    def test_otro_inmueble_no_afecto_rate_2pct(self, tmp_path: Path) -> None:
        """No catastral revision in last 10 years → 2 % rate."""
        engine = _engine(tmp_path)
        try:
            with session_scope(engine) as session:
                finca_repo = RentalFincaRepository(session)
                finca = finca_repo.upsert(
                    RentalFinca(
                        identifier="otro-1",
                        address="Y",
                        valor_catastral_total=Decimal("100000.00"),
                        valor_catastral_construccion=Decimal("60000.00"),
                        valor_catastral_revision_year=2010,
                        coste_adquisicion=Decimal("150000.00"),
                        coste_adquisicion_construccion=Decimal("90000.00"),
                        acquisition_date=date(2008, 1, 1),
                        use_type=UseType.OTRO_INMUEBLE_NO_AFECTO,
                    ),
                )
                assert finca.id is not None
                aggregates = compute_anexo_c_aggregates(
                    period_year=2025,
                    finca_repo=finca_repo,
                    contract_repo=RentalContractRepository(session),
                    income_repo=RentalIncomeRepository(session),
                    expense_repo=RentalExpenseRepository(session),
                    ledger_repo=RentalAmortizationLedgerRepository(session),
                )
                assert aggregates.casilla_0085 == Decimal("2000.00")
        finally:
            engine.dispose()

    def test_recent_revision_rate_1_1pct(self, tmp_path: Path) -> None:
        """Catastral revision 5 years ago → 1.1 % rate."""
        engine = _engine(tmp_path)
        try:
            with session_scope(engine) as session:
                finca_repo = RentalFincaRepository(session)
                finca = finca_repo.upsert(
                    RentalFinca(
                        identifier="otro-2",
                        address="Z",
                        valor_catastral_total=Decimal("100000.00"),
                        valor_catastral_construccion=Decimal("60000.00"),
                        valor_catastral_revision_year=2020,
                        coste_adquisicion=Decimal("150000.00"),
                        coste_adquisicion_construccion=Decimal("90000.00"),
                        acquisition_date=date(2008, 1, 1),
                        use_type=UseType.OTRO_INMUEBLE_NO_AFECTO,
                    ),
                )
                assert finca.id is not None
                aggregates = compute_anexo_c_aggregates(
                    period_year=2025,
                    finca_repo=finca_repo,
                    contract_repo=RentalContractRepository(session),
                    income_repo=RentalIncomeRepository(session),
                    expense_repo=RentalExpenseRepository(session),
                    ledger_repo=RentalAmortizationLedgerRepository(session),
                )
                assert aggregates.casilla_0085 == Decimal("1100.00")
        finally:
            engine.dispose()


class TestProviderShim:
    def test_register_overrides_supplied_aggregates(self, tmp_path: Path) -> None:
        """Caller-supplied 0061 differs from register-derived → override
        with derived; surface old value in `overridden`."""
        engine = _engine(tmp_path)
        try:
            with session_scope(engine) as session:
                finca_repo = RentalFincaRepository(session)
                contract_repo = RentalContractRepository(session)
                income_repo = RentalIncomeRepository(session)
                expense_repo = RentalExpenseRepository(session)
                ledger_repo = RentalAmortizationLedgerRepository(session)

                finca = finca_repo.upsert(
                    RentalFinca(
                        identifier="shim-1",
                        address="X",
                        valor_catastral_total=Decimal("100000.00"),
                        valor_catastral_construccion=Decimal("60000.00"),
                        coste_adquisicion=Decimal("150000.00"),
                        coste_adquisicion_construccion=Decimal("90000.00"),
                        acquisition_date=date(2010, 1, 1),
                        use_type=UseType.VIVIENDA_ARRENDADA,
                    ),
                )
                assert finca.id is not None
                contract = contract_repo.upsert(
                    RentalContract(
                        finca_id=finca.id,
                        contract_celebration_date=date(2024, 1, 1),
                        tenant_count=1,
                        initial_rent=Decimal("500.00"),
                    ),
                )
                assert contract.id is not None
                income_repo.upsert(
                    RentalIncomeRecord(
                        contract_id=contract.id,
                        period_year=2025,
                        gross_rent_received=Decimal("6000.00"),
                        dias_alquilados=365,
                    ),
                )

                # Caller-supplied 0061 is wrong (5 000 vs derived 6 000).
                provided = {
                    "0061": Decimal("5000.00"),
                    "0066": Decimal("0.00"),
                    "0072": Decimal("0.00"),
                    "0078": Decimal("0.00"),
                    "0085": Decimal("0.00"),
                }
                report = compute_or_passthrough(
                    period_year=2025,
                    provided_casillas=provided,
                    finca_repo=finca_repo,
                    contract_repo=contract_repo,
                    income_repo=income_repo,
                    expense_repo=expense_repo,
                    ledger_repo=ledger_repo,
                )
                assert report.register_used is True
                assert report.effective_casillas["0061"] == Decimal("6000.00")
                assert "0061" in report.overridden
                assert report.overridden["0061"] == (Decimal("5000.00"), Decimal("6000.00"))
        finally:
            engine.dispose()


def test_anexo_c_casillas_constant_matches_set() -> None:
    assert set(ANEXO_C_CASILLAS) == {"0061", "0066", "0072", "0078", "0085"}
