"""Unit tests for the LIRPF art. 23.1.f amortización 3 % ledger.

Exercises :func:`cadrumo.domain.fincas.compute_amortization_for_year` and
:func:`cadrumo.domain.fincas.computation_to_ledger_entry` across single-
year accruals, multi-year cumulative threading, partial / full clamp
at the cost-basis cap, and the strict-mode overflow path.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ..amortization_ledger import computation_to_ledger_entry, compute_amortization_for_year
from ..enums import TitularContribuyente, TitularidadRegime, UseType
from ..errors import AmortizationLedgerCapExceededError
from ..models import Finca, FincaRendimientoRecord
from ..titularidad import Titularidad

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _finca(
    *,
    coste_construccion: Decimal = Decimal("100000.00"),
    valor_catastral_construccion: Decimal = Decimal("80000.00"),
) -> Finca:
    return Finca(
        id=1,
        identifier="amort-test",
        address="X",
        valor_catastral_total=valor_catastral_construccion + Decimal("20000"),
        valor_catastral_construccion=valor_catastral_construccion,
        coste_adquisicion=coste_construccion + Decimal("50000"),
        coste_adquisicion_construccion=coste_construccion,
        acquisition_date=date(2020, 1, 1),
        use_type=UseType.VIVIENDA_ARRENDADA,
        titularidad=Titularidad(
            regime=TitularidadRegime.PLENO_DOMINIO,
            contribuyente=TitularContribuyente.PRIMER_DECLARANTE,
            porcentaje_propiedad=Decimal("100.00"),
        ),
    )


def _income(period_year: int, dias_alquilados: int = 365) -> FincaRendimientoRecord:
    return FincaRendimientoRecord(
        contract_id=1,
        period_year=period_year,
        gross_rent_received=Decimal("12000.00"),
        dias_alquilados=dias_alquilados,
    )


class TestSingleYearAccrual:
    def test_full_year_basis_is_max_of_coste_and_catastral(self) -> None:
        """Coste construcción 100 000 > catastral 80 000 → basis = 100 000."""
        result = compute_amortization_for_year(
            _finca(),
            _income(2025),
            cumulative_through_prior_year=Decimal("0"),
        )
        assert result.basis == Decimal("100000.00")
        # Full year (365 dias) → no clamp → gross == capped == cumulative.
        assert result.gross_amortization > Decimal("0")
        assert result.capped_amortization == result.gross_amortization
        assert result.cumulative_through_year == result.gross_amortization
        assert result.clamp_applied is False

    def test_catastral_higher_than_coste_drives_basis(self) -> None:
        """When catastral > coste construcción, BOE rule says use the greater."""
        result = compute_amortization_for_year(
            _finca(coste_construccion=Decimal("60000.00"), valor_catastral_construccion=Decimal("90000.00")),
            _income(2025),
            cumulative_through_prior_year=Decimal("0"),
        )
        assert result.basis == Decimal("90000.00")
        assert result.gross_amortization == Decimal("2700.00")
        # Cap is 60 000 (coste), gross 2 700 << cap → no clamp.
        assert result.capped_amortization == Decimal("2700.00")
        assert result.clamp_applied is False

    def test_partial_year_pro_rate_by_dias_alquilados(self) -> None:
        """180 días → partial-year accrual is strictly less than full-year."""
        full_year = compute_amortization_for_year(
            _finca(),
            _income(2025, dias_alquilados=365),
            cumulative_through_prior_year=Decimal("0"),
        )
        partial = compute_amortization_for_year(
            _finca(),
            _income(2025, dias_alquilados=180),
            cumulative_through_prior_year=Decimal("0"),
        )
        # Partial-year accrual must be strictly less than full-year and positive.
        assert Decimal("0") < partial.gross_amortization < full_year.gross_amortization
        # No clamp applies at cumulative = 0 for a low basis.
        assert partial.capped_amortization == partial.gross_amortization
        assert partial.clamp_applied is False

    def test_zero_dias_alquilados_yields_zero(self) -> None:
        result = compute_amortization_for_year(
            _finca(),
            _income(2025, dias_alquilados=0),
            cumulative_through_prior_year=Decimal("0"),
        )
        assert result.gross_amortization == Decimal("0.00")
        assert result.capped_amortization == Decimal("0.00")
        assert result.cumulative_through_year == Decimal("0.00")


class TestMultiYearAccumulation:
    def test_cumulative_threads_year_over_year(self) -> None:
        finca = _finca()
        cumulative = Decimal("0")
        for year in range(2020, 2025):
            result = compute_amortization_for_year(
                finca,
                _income(year),
                cumulative_through_prior_year=cumulative,
            )
            assert result.capped_amortization == Decimal("3000.00")
            cumulative = result.cumulative_through_year
        assert cumulative == Decimal("15000.00")

    def test_cap_clamps_final_year(self) -> None:
        """Cap = coste 10 000; basis = max(coste, catastral) = 10 000;
        gross = 10 000 * 0.03 = 300/yr; cap reached after year 33-ish.
        Set up so year-N has only 200 of cap left."""
        cap = Decimal("10000.00")
        finca = _finca(
            coste_construccion=cap,
            valor_catastral_construccion=Decimal("8000.00"),
        )
        result_year_n = compute_amortization_for_year(
            finca,
            _income(2024),
            cumulative_through_prior_year=Decimal("9700.00"),
        )
        assert result_year_n.basis == cap
        assert result_year_n.gross_amortization == Decimal("300.00")
        assert result_year_n.capped_amortization == Decimal("300.00")
        result_year_n_plus_1 = compute_amortization_for_year(
            finca,
            _income(2025),
            cumulative_through_prior_year=cap,
        )
        assert result_year_n_plus_1.gross_amortization == Decimal("300.00")
        assert result_year_n_plus_1.capped_amortization == Decimal("0.00")
        assert result_year_n_plus_1.clamp_applied is True
        assert result_year_n_plus_1.cumulative_through_year == cap

    def test_strict_mode_raises_on_cap_overflow(self) -> None:
        with pytest.raises(AmortizationLedgerCapExceededError):
            compute_amortization_for_year(
                _finca(coste_construccion=Decimal("100.00")),
                _income(2025),
                cumulative_through_prior_year=Decimal("100.00"),
                strict=True,
            )

    def test_partial_clamp_at_cap_boundary(self) -> None:
        """Cumulative 9 800 + gross 300 → clamp to 200 (cap = 10 000)."""
        cap = Decimal("10000.00")
        finca = _finca(
            coste_construccion=cap,
            valor_catastral_construccion=Decimal("8000.00"),
        )
        result = compute_amortization_for_year(
            finca,
            _income(2025),
            cumulative_through_prior_year=Decimal("9800.00"),
        )
        assert result.gross_amortization == Decimal("300.00")
        assert result.capped_amortization == Decimal("200.00")
        assert result.cumulative_through_year == cap
        assert result.clamp_applied is True


class TestLedgerEntryProjection:
    def test_round_trip_to_ledger_entry(self) -> None:
        finca = _finca()
        income = _income(2025)
        computation = compute_amortization_for_year(
            finca,
            income,
            cumulative_through_prior_year=Decimal("0"),
        )
        entry = computation_to_ledger_entry(finca_id=1, income=income, computation=computation)
        assert entry.finca_id == 1
        assert entry.period_year == 2025
        assert entry.dias_alquilados == 365
        assert entry.basis_used == Decimal("100000.00")
        assert entry.amortization_amount == Decimal("3000.00")
        assert entry.cumulative_amortization_through_year == Decimal("3000.00")
