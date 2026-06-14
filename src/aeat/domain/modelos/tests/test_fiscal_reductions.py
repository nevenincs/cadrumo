"""Oracle, guard, and boundary-contract tests for the fiscal-reduction formulas.

Covers the DT 12ª LIRPF plan-de-pensiones reducción and the Ley 44/2015 art. 14
SAL/SLL reserva especial dotacion, relocated from the CLI to the modelos domain.
Expected values are derived from the cited regulatory formulas with explicit
derivations (oracle), not manufactured arithmetic, per the
no-tautological-calculation-tests rule.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.errors import CoreValidationError, get_registered_error_code
from .._dt12_reduccion import compute_dt12_reduccion_plan_pensiones
from .._errors import PensionReduccionError
from .._sal_reserva_especial import compute_sal_reserva_especial_dotacion

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


class TestDt12ReduccionPlanPensiones:
    """DT 12ª LIRPF reducción oracle + anti-tautology.

    Expected values derived from LIRPF DT 12ª formula:
    pre_2007 / totales * gross_rescate * 40%.
    """

    def test_carla_oracle_shape(self) -> None:
        """9600/33000 * 60000 * 40% (LIRPF DT 12ª).

        Derivation: 9600 / 33000 * 60000 * 0.40
          = 0.29090909... * 60000 * 0.40
          = 17454.5454... * 0.40
          = 6981.8181...
          rounded HALF_UP (money-2) -> 6981.82
        """
        result = compute_dt12_reduccion_plan_pensiones(
            gross_rescate=Decimal("60000"),
            aportaciones_pre_2007=Decimal("9600"),
            aportaciones_totales=Decimal("33000"),
        )
        assert result == Decimal("6981.82")

    def test_anti_tautology_different_ratio_different_reduccion(self) -> None:
        """Changing the pre/post ratio produces a different reducción amount."""
        result_carla = compute_dt12_reduccion_plan_pensiones(
            gross_rescate=Decimal("60000"),
            aportaciones_pre_2007=Decimal("9600"),
            aportaciones_totales=Decimal("33000"),
        )
        # Halve the pre-2007 fraction -> ~half the reducción
        result_half = compute_dt12_reduccion_plan_pensiones(
            gross_rescate=Decimal("60000"),
            aportaciones_pre_2007=Decimal("4800"),
            aportaciones_totales=Decimal("33000"),
        )
        assert result_carla != result_half
        # 4800/33000 * 60000 * 0.40 = 3490.9090... -> 3490.91
        assert result_half == Decimal("3490.91")

    def test_zero_pre_2007_yields_zero_reduccion(self) -> None:
        # DT 12ª only reduces the pre-2007 share; with none, the reducción is zero.
        result = compute_dt12_reduccion_plan_pensiones(
            gross_rescate=Decimal("60000"),
            aportaciones_pre_2007=Decimal("0"),
            aportaciones_totales=Decimal("33000"),
        )
        assert result == Decimal("0.00")

    def test_zero_totales_raises(self) -> None:
        with pytest.raises(PensionReduccionError, match="aportaciones_totales must be positive"):
            compute_dt12_reduccion_plan_pensiones(
                gross_rescate=Decimal("60000"),
                aportaciones_pre_2007=Decimal("9600"),
                aportaciones_totales=Decimal("0"),
            )

    def test_negative_gross_raises(self) -> None:
        with pytest.raises(PensionReduccionError, match="gross_rescate must be non-negative"):
            compute_dt12_reduccion_plan_pensiones(
                gross_rescate=Decimal("-1"),
                aportaciones_pre_2007=Decimal("9600"),
                aportaciones_totales=Decimal("33000"),
            )


class TestSalReservaEspecialDotacion:
    """Oracle tests for the Ley 44/2015 art. 14 SAL/SLL reserva especial dotacion."""

    def test_aitor_oracle_shape_below_cap(self) -> None:
        """beneficio=120k, capital=100k, reserva=30k.

        cap = 100k * 2 = 200k (Ley 44/2015 art. 14: hasta el doble del capital)
        headroom = 200k - 30k = 170k
        dotacion_obligatoria = 120k * 10% = 12k
        dotacion = min(12k, 170k) = 12k
        """
        result = compute_sal_reserva_especial_dotacion(
            beneficio_neto=Decimal("120000"),
            reserva_dotada=Decimal("30000"),
            capital_social=Decimal("100000"),
        )
        assert result == Decimal("12000.00")

    def test_anti_tautology_next_year_cap_partial(self) -> None:
        """reserva=195k (near the 2x cap), capital=100k.

        cap = 100k * 2 = 200k (Ley 44/2015 art. 14)
        headroom = 200k - 195k = 5k
        dotacion_obligatoria = 120k * 10% = 12k
        dotacion = min(12k, 5k) = 5k  (capped by headroom)
        """
        result = compute_sal_reserva_especial_dotacion(
            beneficio_neto=Decimal("120000"),
            reserva_dotada=Decimal("195000"),
            capital_social=Decimal("100000"),
        )
        assert result == Decimal("5000.00")

    def test_cap_reached_yields_zero(self) -> None:
        """reserva=200k (at the 2x cap), capital=100k => dotacion=0."""
        result = compute_sal_reserva_especial_dotacion(
            beneficio_neto=Decimal("120000"),
            reserva_dotada=Decimal("200000"),
            capital_social=Decimal("100000"),
        )
        assert result == Decimal("0.00")

    def test_reserva_exceeds_cap_also_yields_zero(self) -> None:
        """Reserva above the 2x cap (overfunded from prior period) => dotacion=0."""
        result = compute_sal_reserva_especial_dotacion(
            beneficio_neto=Decimal("120000"),
            reserva_dotada=Decimal("210000"),
            capital_social=Decimal("100000"),
        )
        assert result == Decimal("0.00")

    def test_zero_capital_raises(self) -> None:
        with pytest.raises(PensionReduccionError, match="capital_social must be positive"):
            compute_sal_reserva_especial_dotacion(
                beneficio_neto=Decimal("120000"),
                reserva_dotada=Decimal("30000"),
                capital_social=Decimal("0"),
            )

    def test_negative_beneficio_raises(self) -> None:
        with pytest.raises(PensionReduccionError, match="beneficio_neto must be non-negative"):
            compute_sal_reserva_especial_dotacion(
                beneficio_neto=Decimal("-1"),
                reserva_dotada=Decimal("30000"),
                capital_social=Decimal("100000"),
            )


class TestPensionReduccionErrorEnvelope:
    """PensionReduccionError carries structured context, registry code, and ancestry.

    All guard raises in the relocated formulas raise PensionReduccionError. The
    error is a CoreValidationError / ValueError subclass, carries structured
    context, and maps to a stable registry code.
    """

    def test_dt12_zero_totales_context(self) -> None:
        with pytest.raises(PensionReduccionError) as exc_info:
            compute_dt12_reduccion_plan_pensiones(
                gross_rescate=Decimal("60000"),
                aportaciones_pre_2007=Decimal("9600"),
                aportaciones_totales=Decimal("0"),
            )
        exc = exc_info.value
        assert "aportaciones_totales" in str(exc)
        assert exc.context is not None
        assert exc.context["field"] == "aportaciones_totales"

    def test_dt12_negative_gross_context(self) -> None:
        with pytest.raises(PensionReduccionError) as exc_info:
            compute_dt12_reduccion_plan_pensiones(
                gross_rescate=Decimal("-1"),
                aportaciones_pre_2007=Decimal("9600"),
                aportaciones_totales=Decimal("33000"),
            )
        assert exc_info.value.context is not None
        assert exc_info.value.context["field"] == "gross_rescate"

    def test_dt12_negative_pre2007_context(self) -> None:
        with pytest.raises(PensionReduccionError) as exc_info:
            compute_dt12_reduccion_plan_pensiones(
                gross_rescate=Decimal("60000"),
                aportaciones_pre_2007=Decimal("-1"),
                aportaciones_totales=Decimal("33000"),
            )
        assert exc_info.value.context is not None
        assert exc_info.value.context["field"] == "aportaciones_pre_2007"

    def test_sal_zero_capital_context(self) -> None:
        with pytest.raises(PensionReduccionError) as exc_info:
            compute_sal_reserva_especial_dotacion(
                beneficio_neto=Decimal("120000"),
                reserva_dotada=Decimal("30000"),
                capital_social=Decimal("0"),
            )
        exc = exc_info.value
        assert "capital_social" in str(exc)
        assert exc.context is not None
        assert exc.context["field"] == "capital_social"

    def test_sal_negative_beneficio_context(self) -> None:
        with pytest.raises(PensionReduccionError) as exc_info:
            compute_sal_reserva_especial_dotacion(
                beneficio_neto=Decimal("-1"),
                reserva_dotada=Decimal("30000"),
                capital_social=Decimal("100000"),
            )
        assert exc_info.value.context is not None
        assert exc_info.value.context["field"] == "beneficio_neto"

    def test_sal_negative_reserva_context(self) -> None:
        with pytest.raises(PensionReduccionError) as exc_info:
            compute_sal_reserva_especial_dotacion(
                beneficio_neto=Decimal("120000"),
                reserva_dotada=Decimal("-1"),
                capital_social=Decimal("100000"),
            )
        assert exc_info.value.context is not None
        assert exc_info.value.context["field"] == "reserva_dotada"

    def test_pension_reduccion_error_is_core_validation_error(self) -> None:
        assert issubclass(PensionReduccionError, CoreValidationError)
        assert issubclass(PensionReduccionError, ValueError)

    def test_pension_reduccion_error_code_is_registered(self) -> None:
        try:
            compute_dt12_reduccion_plan_pensiones(
                gross_rescate=Decimal("60000"),
                aportaciones_pre_2007=Decimal("9600"),
                aportaciones_totales=Decimal("0"),
            )
        except PensionReduccionError as exc:
            code = get_registered_error_code(exc)
            assert code.code == "REFUSED_PENSION_REDUCCION_COMPUTATION"
        else:
            pytest.fail("PensionReduccionError was not raised")
