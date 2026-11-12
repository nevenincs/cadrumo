"""Modelo 200 liquidación boxes against the line of the Sociedades manual that defines each.

Every expected amount below is worked by hand from the cited line of the bundled
AEAT Manual práctico de Sociedades (``corpus/manuals/sociedades/<edition>/
source.pdf.extracted.md``), never read from a run. The exercises come from the
manual editions that print the cited text and from the Modelo 200 revisions that
calculate them, so no year is named here.

2024 edition lines used:
    L14021 "[00552] = [00550] - [01032] - [00547]"; L14034-14036 a zero or
      negative 00550 is entered "precedida del signo menos (-) tanto en dicha
      casilla [00550] como en la casilla [00552]" with cero in 00562, 00582 and
      00592.
    L14648-14656 "[00562] = [01330] x [00558]/100", "siempre ... positiva o cero".
    L14670 tipo general 25; L14671-14675 nueva creación 15, not for an entidad
      patrimonial; L14682-14683 INCN < 1 millón 23, not for an entidad
      patrimonial; L14686 entidades de crédito 30; L14704-14712 cooperativas
      fiscalmente protegidas; L14724 Ley 49/2002 10; L14752-14755 nota (1): a
      cooperativa fiscalmente protegida states the 20 of its resultados
      cooperativos in 00558 "a los únicos efectos de cumplimentar" it;
      L26990 a cooperativa's 00562 is built from its cuota íntegra previa.
    L14281-14300 the BIN límite of 70 per cent of 00550, 50 at an INCN of the
      prior 12 months of at least 20 millones and 25 at 60 millones (DA 15ª.1
      LIS); L14305-14306 up to 1 millón in any case; L14481-14485 the rentas of
      00545, 00925 and 01509 are taken off 00547 before the límite; L3183-3192
      a nueva creación marking 00070 does not apply the límite.
2023 edition lines used:
    L13026-13050 the same 00552 rule and sign; L13561, L13689 the same 00562
      rule; L13568-13641 the same rate table as 2024; L13273-13277 the 70 per
      cent límite with no DA 15ª turnover límites; L2908 casilla 00070.
2025 edition lines used:
    L14097, L14111 the same 00552 rule; L14948-14954 the same 00562 rule;
    L14980-14983 INCN < 1 millón: "Hasta 50.000 euros 21 por 100 / Resto Base
      Imponible 22 por 100"; record design aeat-dr-200-2025 DP200014 field 31,
      Nota 1: a double rate fills 00558 with both rates
      (01-200-ejercicio-2025-10-9-mb-xls.xls.extracted.md L1530-1534).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core.authority_grade import RegistryAuthorityGrade
from .....core.casilla_id import CasillaId, validated_casilla_id
from .....core.resources.bundled_data import bundled_path
from ..formula_runtime import RegistryCalculationResult, calculate_registry_snapshot
from ..formula_runtime_ops import RegistryUnresolvedOutcomeReason
from .authored_editions import authored_revisions_where, manual_editions_printing
from .modelo_200_casilla_ids import (
    M200_BIN_APLICADA_CASILLA,
    M200_CORRECCIONES_AUMENTO_CASILLA,
    M200_CORRECCIONES_DISMINUCION_CASILLA,
    M200_CUOTA_INTEGRA_CASILLA,
    M200_RESERVA_CAPITALIZACION_CASILLA,
    M200_RESULTADO_CONTABLE_CASILLA,
)
from .published_authority import published_snapshot, published_source_reference

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]

_M200 = "200"


def _casilla(raw: str) -> CasillaId:
    return validated_casilla_id(raw, surface="test_modelo_200_liquidacion_manual_lines")


_BASE_PREVIA = _casilla("DP200014:00550")
_BASE_IMPONIBLE = _casilla("DP200014:00552")
_TIPO_GRAVAMEN = _casilla("DP200014:00558")
_CUOTA_INTEGRA_AJUSTADA = _casilla("DP200014:00582")
_CUOTA_LIQUIDA = _casilla("DP200014B:00592")
_BIN_MAXIMA = _casilla("DP200014:bin-aplicada-maxima")

_FORM = "modelo-200-profile-legal-entity-form"
_NEW_ENTITY = "modelo-200-profile-new-entity-flag"
_INCN = "modelo-200-profile-incn-prior-12-months"
_BIN_STOCK = "modelo-200-bin-pendiente-ejercicios-anteriores"

_MARKED = Decimal("1")
_INCN_GENERAL = Decimal("12000000")
_INCN_MICRO = Decimal("600000")


def _calculated(exercise: int) -> bool:
    return any(
        revision.valid_from.year <= exercise and (revision.valid_to is None or exercise <= revision.valid_to.year)
        for revision in authored_revisions_where(
            _M200, lambda revision: revision.effective_authority_grade is not RegistryAuthorityGrade.APPLICABILITY
        )
    )


_FLAT_23_EXERCISES = tuple(
    exercise
    for exercise in manual_editions_printing(
        "sociedades",
        "Entidades INCN < 1 millón de euros en el período impositivo inmediato anterior",
        "tributan al tipo de gravamen reducido del 23 por ciento",
    )
    if _calculated(exercise)
)
_TWO_RATE_EXERCISES = tuple(
    exercise
    for exercise in manual_editions_printing(
        "sociedades",
        "aplican los tipos de gravamen que se indican en la siguiente escala",
        "Por la parte de base imponible restante, el tipo del 22 por ciento",
    )
    if _calculated(exercise)
)
_EXERCISES = tuple(sorted(set(_FLAT_23_EXERCISES) | set(_TWO_RATE_EXERCISES)))
assert _FLAT_23_EXERCISES, "no calculated Modelo 200 exercise has a manual printing the flat 23 per cent"
assert _TWO_RATE_EXERCISES, "no calculated Modelo 200 exercise has a manual printing the 21 / 22 scale"
_TURNOVER_LIMIT_EXERCISES = tuple(
    exercise
    for exercise in manual_editions_printing(
        "sociedades",
        "sustituirán el límite del 70 por ciento por los siguientes",
        "El 50 por ciento",
        "El 25 por ciento",
    )
    if _calculated(exercise)
)
_RENTAS_OUTSIDE_LIMIT_EXERCISES = tuple(
    exercise
    for exercise in manual_editions_printing("sociedades", "citadas casillas [00545], [00925] y [01509]")
    if _calculated(exercise)
)
assert _TURNOVER_LIMIT_EXERCISES, "no calculated Modelo 200 exercise has a manual printing the DA 15ª límites"
assert _RENTAS_OUTSIDE_LIMIT_EXERCISES, "no calculated Modelo 200 exercise has a manual printing 00545, 00925, 01509"


def _calculate(
    exercise: int,
    *,
    resultado: Decimal,
    form: str = "sl",
    incn: Decimal = _INCN_GENERAL,
    new_entity: Decimal = Decimal("0"),
    marked: tuple[str, ...] = (),
    inputs: dict[CasillaId, Decimal] | None = None,
    bin_stock: Decimal = Decimal("0"),
) -> RegistryCalculationResult:
    """Run the 0A chain of one exercise for a sociedad with no correction, reserva or BIN applied."""
    casilla_inputs: dict[CasillaId, Decimal] = {
        M200_RESULTADO_CONTABLE_CASILLA: resultado,
        M200_CORRECCIONES_AUMENTO_CASILLA: Decimal("0"),
        M200_CORRECCIONES_DISMINUCION_CASILLA: Decimal("0"),
        M200_RESERVA_CAPITALIZACION_CASILLA: Decimal("0"),
        M200_BIN_APLICADA_CASILLA: Decimal("0"),
    }
    casilla_inputs.update({_casilla(raw): _MARKED for raw in marked})
    casilla_inputs.update(inputs or {})
    return calculate_registry_snapshot(
        published_snapshot(_M200, filing_year=exercise, period="0A", grade=RegistryAuthorityGrade.CALCULATION),
        inputs=casilla_inputs,
        enum_binding_values={_FORM: form},
        binding_values={
            _NEW_ENTITY: new_entity,
            _INCN: incn,
            "modelo-200-profile-tributacion-estado-porcentaje": Decimal("100"),
            _BIN_STOCK: bin_stock,
            "modelo-200-dotaciones-deterioro-creditos-saldo-no-cumplido-anteriores": Decimal("0"),
            "modelo-200-dotaciones-deterioro-creditos-saldo-cumplido-anteriores": Decimal("0"),
        },
        relation_values={
            "modelo-200-pagos-fraccionados-anuales": Decimal("0"),
            "modelo-200-pagos-fraccionados-anuales-40-2": Decimal("0"),
        },
        date_context={"filing_period": date(exercise, 12, 31)},
    )


def _tipo(exercise: int, rate: str) -> Decimal:
    """Casilla 00558 for a single rate, as the exercise's own record design states the box.

    Every design prints 00558 in four positions. The 2023 and 2024 designs read
    "2 enteros y 2 decimales", so the box holds the percentage. The 2025 design
    points the row to Nota 1: a single rate fills the first two digits and 00 the
    last two, so 25 is the code 2500 (01-200-ejercicio-2025-10-9-mb-xls.xls
    .extracted.md L1495, L1530-1534), and the box holds that code.
    """
    snapshot = published_snapshot(_M200, filing_year=exercise, period="0A", grade=RegistryAuthorityGrade.CALCULATION)
    designs = [
        source
        for source in (published_source_reference(ref) for ref in snapshot.revision.source_refs)
        if source.kind == "record_design"
    ]
    assert len(designs) == 1, designs
    text = bundled_path(f"{designs[0].corpus_path}.extracted.md").read_text(encoding="utf-8")
    rows = [line for line in text.splitlines() if "Tipo de gravamen [00558]" in line]
    assert len(rows) == 1, rows
    if rows[0].rstrip().endswith("Nota 1"):
        return Decimal(rate) * 100
    assert rows[0].rstrip().endswith("2 enteros y 2 decimales"), rows[0]
    return Decimal(rate)


def _reason(result: RegistryCalculationResult, casilla_id: CasillaId) -> RegistryUnresolvedOutcomeReason | None:
    return next((outcome.reason for outcome in result.unresolved_outcomes if outcome.casilla_id == casilla_id), None)


@pytest.mark.parametrize("exercise", _EXERCISES)
def test_negative_base_previa_keeps_its_sign_in_the_base_imponible(exercise: int) -> None:
    """00550 = -30.000 -> 00552 = -30.000; 00562 = 00582 = 00592 = 0 (L14021, L14034-14036)."""
    values = _calculate(exercise, resultado=Decimal("-30000")).values

    assert values[_BASE_PREVIA] == Decimal("-30000.00")
    assert values[_BASE_IMPONIBLE] == Decimal("-30000.00")
    assert values[M200_CUOTA_INTEGRA_CASILLA] == Decimal("0.00")
    assert values[_CUOTA_INTEGRA_AJUSTADA] == Decimal("0.00")
    assert values[_CUOTA_LIQUIDA] == Decimal("0.00")


@pytest.mark.parametrize("exercise", _EXERCISES)
def test_cuota_integra_is_the_base_times_the_tipo(exercise: int) -> None:
    """Base 100.000 at the general rate: 00558 = 25, 00562 = 100.000 x 25 / 100 = 25.000 (L14648-14656, L14670)."""
    values = _calculate(exercise, resultado=Decimal("100000")).values

    assert values[_TIPO_GRAVAMEN] == _tipo(exercise, "25")
    assert values[M200_CUOTA_INTEGRA_CASILLA] == Decimal("25000.00")


@pytest.mark.parametrize("exercise", _EXERCISES)
def test_nueva_creacion_takes_fifteen(exercise: int) -> None:
    """A nueva creación of LIS art. 29.1 below 1 millón INCN: 15, 100.000 x 15 / 100 = 15.000 (L14671-14675)."""
    values = _calculate(exercise, resultado=Decimal("100000"), incn=_INCN_MICRO, new_entity=_MARKED).values

    assert values[_TIPO_GRAVAMEN] == _tipo(exercise, "15")
    assert values[M200_CUOTA_INTEGRA_CASILLA] == Decimal("15000.00")


@pytest.mark.parametrize("exercise", _EXERCISES)
def test_entidad_patrimonial_takes_the_general_rate_whatever_its_size_or_age(exercise: int) -> None:
    """Casilla 00066 marked, new and below 1 millón: still 25, 25.000 (L14671-14675, L14682-14683)."""
    values = _calculate(
        exercise, resultado=Decimal("100000"), incn=_INCN_MICRO, new_entity=_MARKED, marked=("00066",)
    ).values

    assert values[_TIPO_GRAVAMEN] == _tipo(exercise, "25")
    assert values[M200_CUOTA_INTEGRA_CASILLA] == Decimal("25000.00")


@pytest.mark.parametrize("exercise", _EXERCISES)
def test_ley_49_2002_entity_takes_ten(exercise: int) -> None:
    """Casilla 00001 marked: 10, 100.000 x 10 / 100 = 10.000 (L14724)."""
    values = _calculate(exercise, resultado=Decimal("100000"), form="sin_fines_lucrativos", marked=("00001",)).values

    assert values[_TIPO_GRAVAMEN] == _tipo(exercise, "10")
    assert values[M200_CUOTA_INTEGRA_CASILLA] == Decimal("10000.00")


@pytest.mark.parametrize("exercise", _EXERCISES)
def test_sin_fines_lucrativos_without_its_regime_is_refused(exercise: int) -> None:
    """A non-profit that marks neither 00001 nor another régimen has no rate in the table to take."""
    result = _calculate(exercise, resultado=Decimal("100000"), form="sin_fines_lucrativos")

    assert _reason(result, _TIPO_GRAVAMEN) is RegistryUnresolvedOutcomeReason.M200_TAX_REGIME_UNSUPPORTED
    assert M200_CUOTA_INTEGRA_CASILLA not in result.values


@pytest.mark.parametrize("exercise", _EXERCISES)
def test_cooperativa_protegida_states_twenty_and_leaves_its_cuota_to_the_cooperative_split(exercise: int) -> None:
    """00017 marked: 00558 = 20 (L14704-14712, nota L14752-14755); 00562 refused (L26990)."""
    result = _calculate(exercise, resultado=Decimal("100000"), form="cooperativa", marked=("00017",))

    assert result.values[_TIPO_GRAVAMEN] == _tipo(exercise, "20")
    assert _reason(result, M200_CUOTA_INTEGRA_CASILLA) is RegistryUnresolvedOutcomeReason.M200_TAX_REGIME_UNSUPPORTED


@pytest.mark.parametrize("exercise", _EXERCISES)
def test_cooperativa_stating_no_protection_is_refused(exercise: int) -> None:
    """A cooperativa marking none of 00017, 00018 and 00019 states no rate to take."""
    result = _calculate(exercise, resultado=Decimal("100000"), form="cooperativa")

    assert _reason(result, _TIPO_GRAVAMEN) is RegistryUnresolvedOutcomeReason.M200_TAX_REGIME_UNSUPPORTED
    assert _reason(result, M200_CUOTA_INTEGRA_CASILLA) is RegistryUnresolvedOutcomeReason.M200_TAX_REGIME_UNSUPPORTED


@pytest.mark.parametrize("exercise", _EXERCISES)
@pytest.mark.parametrize(
    "flag",
    [
        "00024",
        "00034",
        "00063",
        "DP200001:00083",
        "00015",
        "00079",
        "00003",
        "DP200001:00004",
        "00008",
        "00012",
        "00048",
        "00002",
        "00080",
    ],
)
def test_a_regime_with_its_own_rate_is_refused_not_given_the_general_one(exercise: int, flag: str) -> None:
    """Crédito, hidrocarburos, DT 22ª, emergente, ZEC, 1 per cent, SOCIMI, pensiones, parcialmente exenta, uniones.

    Their rates (L14676-14695, L14732-14751) or cuota rules are not authored, so
    00558 has no value and the cuota íntegra none either; never the general 25.
    """
    result = _calculate(exercise, resultado=Decimal("100000"), marked=(flag,))

    assert _reason(result, _TIPO_GRAVAMEN) is RegistryUnresolvedOutcomeReason.M200_TAX_REGIME_UNSUPPORTED
    assert _TIPO_GRAVAMEN not in result.values
    assert M200_CUOTA_INTEGRA_CASILLA not in result.values


@pytest.mark.parametrize("exercise", _TWO_RATE_EXERCISES)
def test_two_rate_scale_computes_the_cuota_and_states_the_double_rate(exercise: int) -> None:
    """INCN 600.000, base 100.000: 50.000 x 21 % + 50.000 x 22 % = 10.500 + 11.000 = 21.500 (L14980-14983).

    00558 holds the design's code "2122" (Nota 1: first rate, then second rate).
    """
    result = _calculate(exercise, resultado=Decimal("100000"), incn=_INCN_MICRO)

    assert result.values[M200_CUOTA_INTEGRA_CASILLA] == Decimal("21500.00")
    assert result.values[_TIPO_GRAVAMEN] == Decimal("2122")
    assert _reason(result, _TIPO_GRAVAMEN) is None


@pytest.mark.parametrize("exercise", _FLAT_23_EXERCISES)
def test_flat_reduced_rate_is_one_rate(exercise: int) -> None:
    """INCN 600.000, base 100.000: 00558 = 23, 00562 = 23.000 (L14682-14683, L14648-14656)."""
    values = _calculate(exercise, resultado=Decimal("100000"), incn=_INCN_MICRO).values

    assert values[_TIPO_GRAVAMEN] == Decimal("23")
    assert values[M200_CUOTA_INTEGRA_CASILLA] == Decimal("23000.00")


# Base previa 10.000.000 and a pending stock of 9.000.000 (casilla 00670).
_BIN_BASE_PREVIA = Decimal("10000000")
_BIN_STOCK_HELD = Decimal("9000000")


@pytest.mark.parametrize("exercise", _EXERCISES)
def test_bin_ceiling_is_seventy_per_cent_of_the_base_previa(exercise: int) -> None:
    """70 % x 10.000.000 = 7.000.000 at an INCN of 12.000.000 (L14282-14284)."""
    values = _calculate(exercise, resultado=_BIN_BASE_PREVIA, bin_stock=_BIN_STOCK_HELD).values

    assert values[_BIN_MAXIMA] == Decimal("7000000.00")


@pytest.mark.parametrize("exercise", _TURNOVER_LIMIT_EXERCISES)
@pytest.mark.parametrize(
    ("incn", "ceiling"),
    [
        # INCN 20.000.000: 50 % x 10.000.000 = 5.000.000 (L14294-14297).
        (Decimal("20000000"), Decimal("5000000.00")),
        # INCN 60.000.000: 25 % x 10.000.000 = 2.500.000 (L14298-14300).
        (Decimal("60000000"), Decimal("2500000.00")),
    ],
)
def test_bin_ceiling_follows_the_turnover_of_the_prior_twelve_months(
    exercise: int, incn: Decimal, ceiling: Decimal
) -> None:
    values = _calculate(exercise, resultado=_BIN_BASE_PREVIA, incn=incn, bin_stock=_BIN_STOCK_HELD).values

    assert values[_BIN_MAXIMA] == ceiling


@pytest.mark.parametrize("exercise", _EXERCISES)
def test_bin_ceiling_keeps_the_one_million_floor(exercise: int) -> None:
    """Base previa 1.000.000, stock 9.000.000: 70 % is 700.000, the floor 1.000.000 (L14305-14306)."""
    values = _calculate(exercise, resultado=Decimal("1000000"), bin_stock=_BIN_STOCK_HELD).values

    assert values[_BIN_MAXIMA] == Decimal("1000000.00")


@pytest.mark.parametrize("exercise", _RENTAS_OUTSIDE_LIMIT_EXERCISES)
def test_bin_ceiling_rises_by_the_rentas_outside_the_limit(exercise: int) -> None:
    """00545 = 200.000 and 01509 = 50.000 are taken off 00547 first: 7.000.000 + 250.000 (L14481-14485)."""
    values = _calculate(
        exercise,
        resultado=_BIN_BASE_PREVIA,
        bin_stock=_BIN_STOCK_HELD,
        inputs={_casilla("00545"): Decimal("200000"), _casilla("01509"): Decimal("50000")},
    ).values

    assert values[_BIN_MAXIMA] == Decimal("7250000.00")


@pytest.mark.parametrize("exercise", _EXERCISES)
def test_bin_ceiling_of_a_nueva_creacion_marking_00070_is_the_stock(exercise: int) -> None:
    """Art. 26.3 LIS: no límite, so the whole 9.000.000 stock may be compensated (L3183-3192)."""
    values = _calculate(exercise, resultado=_BIN_BASE_PREVIA, bin_stock=_BIN_STOCK_HELD, marked=("00070",)).values

    assert values[_BIN_MAXIMA] == Decimal("9000000.00")
