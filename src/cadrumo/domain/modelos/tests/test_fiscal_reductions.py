"""Oracle, guard, and boundary-contract tests for the fiscal-reduction formulas.

Covers the DT 12ª LIRPF plan-de-pensiones reducción and the Ley 44/2015 art. 14
SAL/SLL reserva especial dotacion, relocated from the CLI to the modelos domain.
Expected values are derived from the cited regulatory formulas with explicit
derivations (oracle), not manufactured arithmetic, per the
aeat-quality-gates rule.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

import pytest

from ....core.errors import CoreValidationError, get_registered_error_code
from .._dt12_reduccion import compute_dt12_reduccion_plan_pensiones
from ..errors import PensionReduccionError
from .._sal_reserva_especial import compute_sal_reserva_especial_dotacion

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_ReductionCompute = Callable[..., Decimal]

_GUARD_ERROR_CASES: tuple[tuple[str, _ReductionCompute, dict[str, Decimal], str, str], ...] = (
    (
        "dt12-pre2007-exceeds-totales",
        compute_dt12_reduccion_plan_pensiones,
        {
            "gross_rescate": Decimal("60000"),
            "aportaciones_pre_2007": Decimal("40000"),
            "aportaciones_totales": Decimal("33000"),
        },
        "must not exceed aportaciones_totales",
        "aportaciones_pre_2007",
    ),
    (
        "dt12-zero-totales",
        compute_dt12_reduccion_plan_pensiones,
        {
            "gross_rescate": Decimal("60000"),
            "aportaciones_pre_2007": Decimal("9600"),
            "aportaciones_totales": Decimal("0"),
        },
        "aportaciones_totales must be positive",
        "aportaciones_totales",
    ),
    (
        "dt12-negative-gross",
        compute_dt12_reduccion_plan_pensiones,
        {
            "gross_rescate": Decimal("-1"),
            "aportaciones_pre_2007": Decimal("9600"),
            "aportaciones_totales": Decimal("33000"),
        },
        "gross_rescate must be non-negative",
        "gross_rescate",
    ),
    (
        "dt12-negative-pre2007",
        compute_dt12_reduccion_plan_pensiones,
        {
            "gross_rescate": Decimal("60000"),
            "aportaciones_pre_2007": Decimal("-1"),
            "aportaciones_totales": Decimal("33000"),
        },
        "aportaciones_pre_2007 must be non-negative",
        "aportaciones_pre_2007",
    ),
    (
        "sal-zero-capital",
        compute_sal_reserva_especial_dotacion,
        {
            "beneficio_neto": Decimal("120000"),
            "reserva_dotada": Decimal("30000"),
            "capital_social": Decimal("0"),
        },
        "capital_social must be positive",
        "capital_social",
    ),
    (
        "sal-negative-beneficio",
        compute_sal_reserva_especial_dotacion,
        {
            "beneficio_neto": Decimal("-1"),
            "reserva_dotada": Decimal("30000"),
            "capital_social": Decimal("100000"),
        },
        "beneficio_neto must be non-negative",
        "beneficio_neto",
    ),
    (
        "sal-negative-reserva",
        compute_sal_reserva_especial_dotacion,
        {
            "beneficio_neto": Decimal("120000"),
            "reserva_dotada": Decimal("-1"),
            "capital_social": Decimal("100000"),
        },
        "reserva_dotada must be non-negative",
        "reserva_dotada",
    ),
)


def test_fiscal_reduction_guard_errors_carry_context() -> None:
    for case_id, compute, kwargs, message, field_name in _GUARD_ERROR_CASES:
        with pytest.raises(PensionReduccionError, match=message) as exc_info:
            compute(**kwargs)
        exc = exc_info.value
        assert field_name in str(exc), case_id
        assert exc.context is not None, case_id
        assert exc.context["field"] == field_name, case_id


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

    def test_all_pre_2007_equals_full_forty_percent(self) -> None:
        """pre_2007 == totales: the whole rescate is pre-2007, so reducción = 40% gross.

        Derivation (LIRPF DT 12ª apartado 2, full pre-2007 share):
          33000 / 33000 * 60000 * 0.40 = 60000 * 0.40 = 24000.00
        """
        result = compute_dt12_reduccion_plan_pensiones(
            gross_rescate=Decimal("60000"),
            aportaciones_pre_2007=Decimal("33000"),
            aportaciones_totales=Decimal("33000"),
        )
        assert result == Decimal("24000.00")


class TestSalReservaEspecialDotacion:
    """Oracle tests for the Ley 44/2015 art. 14 SAL/SLL reserva especial dotacion."""

    def test_aitor_oracle_shape_below_cap(self) -> None:
        """beneficio=120k, capital=100k, reserva=30k.

        threshold = 100k * 2 + 0.01 = 200000.01
        (Ley 44/2015 art. 14: superior al doble del capital)
        headroom = 200000.01 - 30k = 170000.01
        dotacion_obligatoria = 120k * 10% = 12k
        dotacion = min(12k, 170000.01) = 12k
        """
        result = compute_sal_reserva_especial_dotacion(
            beneficio_neto=Decimal("120000"),
            reserva_dotada=Decimal("30000"),
            capital_social=Decimal("100000"),
        )
        assert result == Decimal("12000.00")

    def test_anti_tautology_next_year_cap_partial(self) -> None:
        """reserva=195k (near the 2x cap), capital=100k.

        threshold = 100k * 2 + 0.01 = 200000.01
        (Ley 44/2015 art. 14: superior al doble del capital)
        headroom = 200000.01 - 195k = 5000.01
        dotacion_obligatoria = 120k * 10% = 12k
        dotacion = min(12k, 5000.01) = 5000.01  (capped by headroom)
        """
        result = compute_sal_reserva_especial_dotacion(
            beneficio_neto=Decimal("120000"),
            reserva_dotada=Decimal("195000"),
            capital_social=Decimal("100000"),
        )
        assert result == Decimal("5000.01")

    def test_exact_double_cap_requires_one_cent_to_exceed(self) -> None:
        """reserva=200k exactly, capital=100k => dotacion=0.01."""
        result = compute_sal_reserva_especial_dotacion(
            beneficio_neto=Decimal("120000"),
            reserva_dotada=Decimal("200000"),
            capital_social=Decimal("100000"),
        )
        assert result == Decimal("0.01")

    def test_first_cent_above_double_cap_yields_zero(self) -> None:
        """reserva=200000.01, capital=100k => threshold reached."""
        result = compute_sal_reserva_especial_dotacion(
            beneficio_neto=Decimal("120000"),
            reserva_dotada=Decimal("200000.01"),
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


class TestPensionReduccionErrorEnvelope:
    """PensionReduccionError carries structured context, registry code, and ancestry.

    All guard raises in the relocated formulas raise PensionReduccionError. The
    error is a CoreValidationError / ValueError subclass, carries structured
    context, and maps to a stable registry code.
    """

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
