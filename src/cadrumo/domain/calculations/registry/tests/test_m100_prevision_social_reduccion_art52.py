"""Modelo 100 pension-system reduction (LIRPF art. 52): its limits, calculated through the real registry.

Every figure below is worked by hand from LIRPF art. 52.1 and the Manual practico de Renta, and the
boxes are named by semantic role, never by number. Each exercise is taken from the published support
envelope; which rule governs it is read from the dated legal references the registry declares, so no
year is written here.

The worker in each case has only work income paid in money (``_ROLE_DINERARIO``); the fixed art.
19.2.f expense of 2.000 leaves the net work income of art. 19 at gross minus 2.000. Every gross
figure is at most 60.000, so the coefficient table of art. 52.1.b.1.º applies when the employer
contributes.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from decimal import Decimal

import pytest

from .....core.authority_grade import RegistryAuthorityGrade
from ..authority import PinnedAuthorityOperation
from ..formula_runtime import RegistryCalculationResult
from ..schema import RegistrySnapshot
from .authored_editions import manual_edition_matches, manual_editions_printing, supported_exercises_with_projection
from .prevision_social_calculation_support import ROLE_ALQUILER, calculate_m100_by_role, casilla_for_role

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]

_FORMULA_ID = "renta-reduccion-prevision-social-total"
_JOINT_REASON = "joint-return-member-income-unavailable"

_ROLE_DINERARIO = "irpf_rendimiento_trabajo_importe_integro_dinerario"
_ROLE_NETO_TRABAJO = "irpf_rendimiento_trabajo_rendimiento_neto"
_ROLE_SALDO_GENERAL = "irpf_saldo_neto_rdtos_base_imponible_general"
_ROLE_EO_NETO = "irpf_rendimiento_act_eco_eo_resto_rdto_neto"
_ROLE_REDUCCION = "irpf_reduccion_prevision_social_total"
_ROLE_TRABAJADOR = "irpf_red_prevision_social_aportaciones_trabajador"
_ROLE_TRABAJADOR_MISMO_INSTRUMENTO = "irpf_red_prevision_social_aportaciones_trabajador_con_contribucion_empresarial"
_ROLE_EMPRESARIAL = "irpf_red_prevision_social_contribuciones_empresariales_excepto_scd"
_ROLE_AUTONOMO = "irpf_red_prevision_social_aportaciones_autonomos_empresarios"
_ROLE_DEPENDENCIA = "irpf_red_prevision_social_contribuciones_scd"

#: The art. 52 redaction of Ley 22/2021 (1.500 + 8.500, worker contributions up to the employer's)
#: and the one of Ley 31/2022 (coefficient table, 4.250 autonomo increment).
_LEY_22_2021_REDACTION = "ley-35-2006:art-52-2022"
_LEY_31_2022_REDACTION = "ley-35-2006:art-52"


def _first_year(authority: PinnedAuthorityOperation, reference: str) -> int:
    return authority.legal_reference(reference).effective_from.year


def _formula_years(authority: PinnedAuthorityOperation) -> tuple[int, ...]:
    first = _first_year(authority, _LEY_22_2021_REDACTION)
    return tuple(year for year in supported_exercises_with_projection("100") if year >= first)


def _coefficient_rule(year: int, authority: PinnedAuthorityOperation) -> bool:
    return year >= _first_year(authority, _LEY_31_2022_REDACTION)


def _snapshot(registry_snapshot: Callable[..., RegistrySnapshot], year: int) -> RegistrySnapshot:
    return registry_snapshot("100", year, "0A", grade=RegistryAuthorityGrade.CALCULATION)


def _reduction(snapshot: RegistrySnapshot, result: RegistryCalculationResult) -> Decimal:
    return result.values[casilla_for_role(snapshot, _ROLE_REDUCCION)]


def _value(snapshot: RegistrySnapshot, result: RegistryCalculationResult, role: str) -> Decimal:
    return result.values[casilla_for_role(snapshot, role)]


def test_the_formula_is_declared_from_the_ley_22_2021_redaction_and_absent_before(
    registry_snapshot: Callable[..., RegistrySnapshot],
    registry_authority: PinnedAuthorityOperation,
) -> None:
    """Every envelope exercise from the 1.500 + 8.500 redaction computes the box; earlier ones do not yet."""
    first = _first_year(registry_authority, _LEY_22_2021_REDACTION)
    years = supported_exercises_with_projection("100")
    assert any(year >= first for year in years)
    for year in years:
        snapshot = _snapshot(registry_snapshot, year)
        declared = any(formula.id == _FORMULA_ID for formula in snapshot.revision.formulas)
        assert declared is (year >= first), year


_EXCESS_RULE = "rd-439-2007:art-51"
_CUOTA_CHAIN = "renta-cuota-chain"


def test_the_excess_rule_is_cited_once_and_appended_last_to_the_cuota_chain(
    registry_snapshot: Callable[..., RegistrySnapshot],
    registry_authority: PinnedAuthorityOperation,
) -> None:
    """RIRPF art. 51 grounds the formula and is appended to its construct, leaving the inherited order intact.

    The chain's references are declared once and inherited by index, so the citation is the last
    member in every exercise that calculates the box, and every reference of the formula is in it.
    """
    for year in _formula_years(registry_authority):
        revision = _snapshot(registry_snapshot, year).revision
        formula = next(formula for formula in revision.formulas if formula.id == _FORMULA_ID)
        chain = next(construct for construct in revision.constructs if construct.id == _CUOTA_CHAIN)

        assert _EXCESS_RULE in formula.legal_refs, year
        assert set(formula.legal_refs) <= set(chain.legal_refs), year
        assert chain.legal_refs.count(_EXCESS_RULE) == 1, year
        assert chain.legal_refs[-1] == _EXCESS_RULE, year


def test_rental_income_does_not_raise_the_percentage_limit(
    registry_snapshot: Callable[..., RegistrySnapshot],
    registry_authority: PinnedAuthorityOperation,
) -> None:
    """Art. 52.1.a takes 30% of net work and activity income only; a rent in the general base adds nothing.

    Gross work 22.000 -> net work (art. 19) 20.000 -> 30% = 6.000. Employer contribution 8.000:
    1.500 + min(8.000, 8.500) = 9.500 >= 8.000, so the absolute limit allows 8.000.
    0468 = min(6.000, 8.000) = 6.000. A reduced rental yield of 30.000 lifts the general balance above
    26.667, so 30% of that balance (the old base) would have allowed the full 8.000.
    """
    for year in _formula_years(registry_authority):
        snapshot = _snapshot(registry_snapshot, year)
        result = calculate_m100_by_role(
            snapshot,
            year,
            {_ROLE_DINERARIO: Decimal("22000"), ROLE_ALQUILER: Decimal("30000"), _ROLE_EMPRESARIAL: Decimal("8000")},
        )

        assert _value(snapshot, result, _ROLE_NETO_TRABAJO) == Decimal("20000.00"), year
        assert _value(snapshot, result, _ROLE_SALDO_GENERAL) * Decimal("0.30") > Decimal("8000"), year
        assert _reduction(snapshot, result) == Decimal("6000.00"), year


def test_objective_estimation_activity_income_counts_toward_the_percentage_limit(
    registry_snapshot: Callable[..., RegistrySnapshot],
    registry_authority: PinnedAuthorityOperation,
) -> None:
    """Net activity income before art. 32 enters the 30% base.

    No work income; objective-estimation net activity income 10.000 -> 30% = 3.000.
    Employer contribution 9.000 is within 1.500 + 8.500. 0468 = min(3.000, 9.000) = 3.000.
    """
    for year in _formula_years(registry_authority):
        snapshot = _snapshot(registry_snapshot, year)
        result = calculate_m100_by_role(
            snapshot, year, {_ROLE_EO_NETO: Decimal("10000"), _ROLE_EMPRESARIAL: Decimal("9000")}
        )

        assert _reduction(snapshot, result) == Decimal("3000.00"), year


@pytest.mark.parametrize(
    ("figures", "expected"),
    [
        # Art. 52.1.b general limit: own contributions 3.000, nothing that unlocks an increment.
        # 0468 = min(15.000, min(3.000, 1.500)) = 1.500.
        pytest.param({_ROLE_TRABAJADOR: Decimal("3000")}, Decimal("1500.00"), id="general-1500"),
        # Increment: employer contribution 12.000 -> 1.500 + min(12.000, 8.500) = 10.000.
        # 0468 = min(15.000, min(12.000, 10.000)) = 10.000.
        pytest.param({_ROLE_EMPRESARIAL: Decimal("12000")}, Decimal("10000.00"), id="increment-8500"),
        # Collective dependency insurance has its own 5.000: 7.000 -> 5.000, plus 10.000 general.
        # 0468 = min(15.000, 10.000 + 5.000) = 15.000, which is also exactly the 30% limit.
        pytest.param(
            {_ROLE_EMPRESARIAL: Decimal("12000"), _ROLE_DEPENDENCIA: Decimal("7000")},
            Decimal("15000.00"),
            id="dependencia-5000",
        ),
    ],
)
def test_each_absolute_limit_in_every_exercise(
    figures: Mapping[str, Decimal],
    expected: Decimal,
    registry_snapshot: Callable[..., RegistrySnapshot],
    registry_authority: PinnedAuthorityOperation,
) -> None:
    """Gross work 52.000 -> net 50.000 -> 30% = 15.000, which does not bind below 15.000."""
    for year in _formula_years(registry_authority):
        snapshot = _snapshot(registry_snapshot, year)
        result = calculate_m100_by_role(snapshot, year, {_ROLE_DINERARIO: Decimal("52000"), **figures})

        assert _reduction(snapshot, result) == expected, year


def test_the_autonomo_increment_is_capped_at_4250_from_ley_31_2022(
    registry_snapshot: Callable[..., RegistrySnapshot],
    registry_authority: PinnedAuthorityOperation,
) -> None:
    """Own autonomo contributions 6.000; net work 50.000, so the 30% limit (15.000) does not bind.

    Ley 22/2021: the empresario individual's own contributions count as employer contributions, so
    the limit is 1.500 + min(6.000, 8.500) = 7.500 and 0468 = 6.000.
    Ley 31/2022: they form the second increment, at most 4.250: 1.500 + min(0 + 4.250, 8.500) = 5.750,
    and 0468 = min(6.000, 5.750) = 5.750.
    """
    for year in _formula_years(registry_authority):
        snapshot = _snapshot(registry_snapshot, year)
        result = calculate_m100_by_role(
            snapshot, year, {_ROLE_DINERARIO: Decimal("52000"), _ROLE_AUTONOMO: Decimal("6000")}
        )

        expected = Decimal("5750.00") if _coefficient_rule(year, registry_authority) else Decimal("6000.00")
        assert _reduction(snapshot, result) == expected, year


@pytest.mark.parametrize("employer_income", ["up-to-60000", "above-60000"])
def test_worker_contributions_to_the_employer_instrument_follow_the_coefficient_table(
    employer_income: str,
    registry_snapshot: Callable[..., RegistrySnapshot],
    registry_authority: PinnedAuthorityOperation,
) -> None:
    """Employer contribution 1.000, worker contribution to the same plan 3.000; net work 50.000.

    Ley 22/2021 (worker up to the employer's amount): increment = 1.000 + min(3.000, 1.000) = 2.000;
    limit 1.500 + 2.000 = 3.500; 0468 = min(4.000, 3.500) = 3.500.
    Ley 31/2022, income from that employer up to 60.000: the worker counts up to
    1.250 + 0,25 x (1.000 - 500) = 1.375; increment = 1.000 + 1.375 = 2.375; limit 3.875;
    0468 = min(4.000, 3.875) = 3.875.
    Ley 31/2022, income above 60.000: multiplier 1, as under Ley 22/2021: 0468 = 3.500.
    """
    for year in _formula_years(registry_authority):
        snapshot = _snapshot(registry_snapshot, year)
        figures = {
            _ROLE_DINERARIO: Decimal("52000"),
            _ROLE_EMPRESARIAL: Decimal("1000"),
            _ROLE_TRABAJADOR_MISMO_INSTRUMENTO: Decimal("3000"),
        }
        up_to_60000 = employer_income == "up-to-60000"
        result = calculate_m100_by_role(snapshot, year, figures, income_up_to_60000=up_to_60000)

        table = _coefficient_rule(year, registry_authority) and up_to_60000
        expected = Decimal("3875.00") if table else Decimal("3500.00")
        assert _reduction(snapshot, result) == expected, year


def test_the_first_tramo_of_the_coefficient_table_multiplies_by_two_and_a_half(
    registry_snapshot: Callable[..., RegistrySnapshot],
    registry_authority: PinnedAuthorityOperation,
) -> None:
    """Employer contribution 400, worker contribution 3.000, income from that employer up to 60.000.

    Ley 31/2022: the worker counts up to 2,5 x 400 = 1.000; increment = 400 + 1.000 = 1.400;
    limit 1.500 + 1.400 = 2.900; 0468 = min(3.400, 2.900) = 2.900.
    Ley 22/2021: increment = 400 + min(3.000, 400) = 800; limit 2.300; 0468 = 2.300.
    """
    for year in _formula_years(registry_authority):
        snapshot = _snapshot(registry_snapshot, year)
        figures = {
            _ROLE_DINERARIO: Decimal("52000"),
            _ROLE_EMPRESARIAL: Decimal("400"),
            _ROLE_TRABAJADOR_MISMO_INSTRUMENTO: Decimal("3000"),
        }
        result = calculate_m100_by_role(snapshot, year, figures)

        expected = Decimal("2900.00") if _coefficient_rule(year, registry_authority) else Decimal("2300.00")
        assert _reduction(snapshot, result) == expected, year


def test_a_joint_return_with_contributions_leaves_the_reduction_unresolved(
    registry_snapshot: Callable[..., RegistrySnapshot],
    registry_authority: PinnedAuthorityOperation,
) -> None:
    """Art. 52.1 limits each member on that member's own income, which a joint return does not separate.

    With a contribution the box is unresolved for that reason, never zero; with none it is zero.
    """
    for year in _formula_years(registry_authority):
        snapshot = _snapshot(registry_snapshot, year)
        target = casilla_for_role(snapshot, _ROLE_REDUCCION)

        with_contribution = calculate_m100_by_role(
            snapshot, year, {_ROLE_DINERARIO: Decimal("52000"), _ROLE_TRABAJADOR: Decimal("1000")}, declaration_type=2
        )
        without = calculate_m100_by_role(snapshot, year, {_ROLE_DINERARIO: Decimal("52000")}, declaration_type=2)

        unresolved = {str(outcome.casilla_id): outcome for outcome in with_contribution.unresolved_outcomes}
        assert target in unresolved, year
        assert unresolved[target].reason.value == _JOINT_REASON
        assert target not in with_contribution.values
        assert _reduction(snapshot, without) == Decimal("0.00"), year


#: The excesses pending from earlier ejercicios (Anexo C.3) other than the collective dependency
#: insurance ones, and those.
_ROLE_EXCESO_GENERAL = "irpf_red_prevision_social_exceso_ejercicios_anteriores"
_ROLE_EXCESO_DEPENDENCIA = "irpf_red_prevision_social_exceso_scd"
_ROLE_EMPRESA_DECISION_TRABAJADOR = "irpf_red_prevision_social_aportaciones_empresa_decision_trabajador"
_ROLE_BASE_LIQUIDABLE_GENERAL = "irpf_base_liquidable_general"


@pytest.mark.parametrize(
    ("excess", "expected"),
    [
        # 4.000 pending, no contribution of the year: the excess takes the whole 1.500 + 8.500 pool,
        # whatever its origin, so all 4.000 reduce (the 1.500 sub-limit alone allowed 1.500).
        pytest.param(Decimal("4000"), Decimal("4000.00"), id="above-1500"),
        # 12.000 pending: the pool allows 10.000; the rest stays pending.
        pytest.param(Decimal("12000"), Decimal("10000.00"), id="above-the-pool"),
    ],
)
def test_earlier_excesses_reduce_against_the_whole_pool(
    excess: Decimal,
    expected: Decimal,
    registry_snapshot: Callable[..., RegistrySnapshot],
    registry_authority: PinnedAuthorityOperation,
) -> None:
    """RIRPF art. 51: the excess draws on the art. 52.1.b limit "por su importe total incrementado".

    Gross work 52.000 -> net 50.000 -> 30% = 15.000, which does not bind.
    """
    for year in _formula_years(registry_authority):
        snapshot = _snapshot(registry_snapshot, year)
        result = calculate_m100_by_role(
            snapshot, year, {_ROLE_DINERARIO: Decimal("52000"), _ROLE_EXCESO_GENERAL: excess}
        )

        assert _reduction(snapshot, result) == expected, year


def test_own_contributions_reduce_within_what_the_excess_leaves_of_the_pool(
    registry_snapshot: Callable[..., RegistrySnapshot],
    registry_authority: PinnedAuthorityOperation,
) -> None:
    """RIRPF art. 51: the excess goes first, then the year's own amounts within "el límite máximo conjunto restante".

    Net work 50.000 -> 30% = 15.000. Excess 9.000 reduces first; 10.000 - 9.000 = 1.000 of the pool
    remains. Own personal contribution 3.000 has its 1.500 sub-limit, so the remaining pool binds:
    own reduction min(3.000, 1.500, 1.000) = 1.000 and 0468 = 9.000 + 1.000 = 10.000.
    """
    for year in _formula_years(registry_authority):
        snapshot = _snapshot(registry_snapshot, year)
        figures = {
            _ROLE_DINERARIO: Decimal("52000"),
            _ROLE_EXCESO_GENERAL: Decimal("9000"),
            _ROLE_TRABAJADOR: Decimal("3000"),
        }
        result = calculate_m100_by_role(snapshot, year, figures)

        assert _reduction(snapshot, result) == Decimal("10000.00"), year


#: The Manual practico de Renta example "aportaciones a sistemas de previsión social", in the
#: normalised text of each edition. It captures, in order: the general and the dependency insurance
#: excess pending from the previous ejercicio, the personal plan contribution, the employer
#: contribution, the dependency insurance contribution, the flexible-pay worker amount, the net work
#: income, and the summary line "base liquidable general (base - reduction) = result".
_MANUAL_EXAMPLE = (
    r"ejemplo: aportaciones a sistemas de prevision social .{0,900}?"
    r"exceso pendiente que ascendia a ([\d.]+) euros por las aportaciones y contribuciones al plan de pensiones, "
    r"y ([\d.]+) euros por la contribucion empresarial al seguro colectivo de dependencia\. .{0,200}?"
    r"aportaciones al plan de pensiones privado por importe de ([\d.]+) euros\. .{0,120}?"
    r"plan de pensiones de empleo de la misma por importe de ([\d.]+) euros "
    r"y de ([\d.]+) al seguro colectivo de dependencia\. .{0,1200}?"
    r"solicita que aporten ([\d.]+) euros .{0,400}?rendimientos netos del trabajo .{0,40}?ascienden a ([\d.]+) euros"
    r".{0,9000}?base liquidable general \(([\d.]+) . ([\d.]+)\) = ([\d.]+)"
)
#: The fixed other expense of art. 19.2.f that turns the money gross into the net work income.
_FIXED_WORK_EXPENSE = Decimal("2000")


def _manual_amount(printed: str) -> Decimal:
    return Decimal(printed.replace(".", ""))


def test_the_manual_worked_example_of_every_exercise_with_a_manual(
    registry_snapshot: Callable[..., RegistrySnapshot],
    registry_authority: PinnedAuthorityOperation,
) -> None:
    """Each bundled manual edition's worked example, read from its text, through the real resolver.

    Locators, ``corpus/manuals/renta/<edition>/part1/source.pdf.extracted.md``: 2022 lines
    34393-34545, 2023 lines 40487-40660, 2024 lines 44817-44990, 2025 lines 40580-40753. Each states
    net work income and general base 30.500, so 30% = 9.150; pending from the previous ejercicio
    3.500 general and 1.500 dependency insurance; own contributions: personal plan 500, dependency
    insurance 1.000, employer 1.500 with a flexible-pay worker amount of 2.500 (2022, Ley 22/2021)
    or employer 1.400 with 2.300, of which the coefficient table admits 1.475 (2023 to 2025, Ley
    31/2022). The money gross is the net plus the fixed 2.000 of art. 19.2.f; the 2023 to 2025
    editions print a gross of 35.000, whose other expenses do not reach the limit.

    The excess 5.000 reduces first and the own amounts take the 4.150 the 30% leaves, with the
    1.500 reduced only by the 500 personal contribution, never by the excess: 0468 = 9.150 and the
    base liquidable general is 21.350. A sub-limit consumed by the excess would give 9.000 (Ley
    22/2021) or 8.875 (Ley 31/2022). The summary line "Remanente de base imponible (30.000 - 5.000)
    = 25.500" misprints the 30.500 base.
    """
    examples = manual_edition_matches("renta", _MANUAL_EXAMPLE)
    printed = set(manual_editions_printing("renta"))
    exercises = [year for year in _formula_years(registry_authority) if year in printed]
    assert exercises
    assert set(exercises) <= set(examples), sorted(set(exercises) - set(examples))
    for year in exercises:
        (excess, excess_dependency, personal, employer, dependency, worker, net, base, reduction, liquidable) = (
            _manual_amount(group) for group in examples[year].groups()
        )
        snapshot = _snapshot(registry_snapshot, year)
        figures = {
            _ROLE_DINERARIO: net + _FIXED_WORK_EXPENSE,
            _ROLE_EXCESO_GENERAL: excess,
            _ROLE_EXCESO_DEPENDENCIA: excess_dependency,
            _ROLE_TRABAJADOR: personal,
            _ROLE_EMPRESARIAL: employer,
            _ROLE_EMPRESA_DECISION_TRABAJADOR: worker,
            _ROLE_DEPENDENCIA: dependency,
        }
        result = calculate_m100_by_role(snapshot, year, figures)

        assert _value(snapshot, result, _ROLE_NETO_TRABAJO) == net == base, year
        assert _reduction(snapshot, result) == reduction, year
        assert _value(snapshot, result, _ROLE_BASE_LIQUIDABLE_GENERAL) == liquidable, year
