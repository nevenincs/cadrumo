"""The Modelo 200 compensation ceiling for negative taxable bases (LIS art. 26.1), every supported exercise.

The ceiling is the most of the pending stock (casilla 00670) the period may
compensate: the greater of the 1 millon floor and the percentage of the base
imponible previa, plus the rentas of casillas 00545 (quitas por acuerdo con
acreedores) and 01509 (reversion de deterioros, DT 16a.8) that the limit does
not reach. An entity that marks casilla 00072 (extincion) does not apply the
limit unless the extincion follows a restructuring, which the registry does not
tell apart, so its ceiling has no value until the operator enters it.

The expected figures are worked by hand from the Manual practico de Sociedades:
70 per cent of 5.000.000 is 3.500.000, and the rentas raise it one for one.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core.authority_grade import RegistryAuthorityGrade
from .....core.casilla_id import CasillaId, validated_casilla_id
from ..bindings import CasillaObservation
from ..formula_runtime import RegistryCalculationResult, calculate_registry_snapshot
from ..formula_runtime_ops import RegistryUnresolvedOutcomeReason
from ..schema import RegistrySnapshot
from .authored_editions import filing_year_envelope
from .modelo_200_casilla_ids import (
    M200_BONIFICACIONES_CASILLA,
    M200_CORRECCIONES_AUMENTO_CASILLA,
    M200_CORRECCIONES_DISMINUCION_CASILLA,
    M200_CUOTA_LIQUIDA_NEGATIVA_CASILLA,
    M200_CUOTA_LIQUIDA_POSITIVA_CASILLA,
    M200_DEDUCCION_DOBLE_IMPOSICION_CASILLA,
    M200_RESERVA_CAPITALIZACION_CASILLA,
    M200_RESULTADO_CONTABLE_CASILLA,
)
from .modelo_200_turnover import PRIOR_TWELVE_MONTHS_TURNOVER, turnover_binding_values
from .published_authority import published_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_EXERCISES = tuple(filing_year_envelope().years)
_DISPATCH_BINDING = "modelo-200-profile-legal-entity-form"
_CEILING_FORMULA = "modelo-200-bin-aplicada-maxima"
_QUITAS: CasillaId = validated_casilla_id("DP200014:00545", surface="_QUITAS")
_REVERSION_DETERIOROS: CasillaId = validated_casilla_id("01509", surface="_REVERSION_DETERIOROS")
_REVERSION_PARTICIPACIONES: CasillaId = validated_casilla_id("00925", surface="_REVERSION_PARTICIPACIONES")
_EXTINCION: CasillaId = validated_casilla_id("00072", surface="_EXTINCION")
_NUEVA_CREACION: CasillaId = validated_casilla_id("00070", surface="_NUEVA_CREACION")
_TIER_PARAMETER = "is.modelo-200.bin-limite-da15-tramo-alto-porcentaje"
_STOCK_BINDING = "modelo-200-bin-pendiente-ejercicios-anteriores"

_BASE = Decimal("5000000")
_STOCK = Decimal("10000000")
_GENERAL_LIMIT = Decimal("3500000.00")


def _snapshot(exercise: int) -> RegistrySnapshot:
    return published_snapshot("200", filing_year=exercise, period="0A", grade=RegistryAuthorityGrade.CALCULATION)


def _declared_casillas(exercise: int) -> frozenset[CasillaId]:
    return frozenset(casilla.id for casilla in _snapshot(exercise).revision.casillas)


def _reads_da_15_tiers(exercise: int) -> bool:
    revision = _snapshot(exercise).revision
    return _TIER_PARAMETER in {p.id for p in revision.parameters} and PRIOR_TWELVE_MONTHS_TURNOVER in {
        b.id for b in revision.bindings
    }


# The editions that state casilla 00925 among the rentas outside the limit, and those that read the
# turnover of the twelve months before the period (the DA 15a tiers); the others are covered by the
# editions that print neither (the editions that carry the tier parameters and the binding).
_EXERCISES_WITH_REVERSION_PARTICIPACIONES = tuple(
    e for e in _EXERCISES if _REVERSION_PARTICIPACIONES in _declared_casillas(e)
)
_EXERCISES_WITHOUT_TIERS = tuple(
    e for e in _EXERCISES if _TIER_PARAMETER not in {p.id for p in _snapshot(e).revision.parameters}
)
_EXERCISES_WITH_TIERS = tuple(e for e in _EXERCISES if _reads_da_15_tiers(e))


def _in_edition(snapshot: RegistrySnapshot, casilla_id: CasillaId) -> CasillaId:
    """The id the edition gives the box a sibling edition names ``casilla_id`` (the sheet prefix moves)."""
    number = casilla_id.rsplit(":", 1)[-1]
    matches = [c.id for c in snapshot.revision.casillas if c.number == number and c.id.rsplit(":", 1)[-1] == number]
    return matches[0] if len(matches) == 1 else casilla_id


def _ceiling_casilla(snapshot: RegistrySnapshot) -> CasillaId:
    return next(f.target_casilla_id for f in snapshot.revision.formulas if f.id == _CEILING_FORMULA)


def _calculate(
    exercise: int,
    *,
    marked: dict[CasillaId, Decimal] | None = None,
    turnover: Decimal = Decimal("10000000"),
    formula_overrides: dict[CasillaId, CasillaObservation] | None = None,
) -> RegistryCalculationResult:
    snapshot = _snapshot(exercise)
    declared = {casilla.id for casilla in snapshot.revision.casillas}
    inputs: dict[CasillaId, Decimal] = {
        M200_RESULTADO_CONTABLE_CASILLA: _BASE,
        M200_CORRECCIONES_AUMENTO_CASILLA: Decimal("0"),
        M200_CORRECCIONES_DISMINUCION_CASILLA: Decimal("0"),
        M200_RESERVA_CAPITALIZACION_CASILLA: Decimal("0"),
        M200_DEDUCCION_DOBLE_IMPOSICION_CASILLA: Decimal("0"),
        M200_BONIFICACIONES_CASILLA: Decimal("0"),
        M200_CUOTA_LIQUIDA_POSITIVA_CASILLA: Decimal("0"),
        M200_CUOTA_LIQUIDA_NEGATIVA_CASILLA: Decimal("0"),
    }
    inputs = {_in_edition(snapshot, casilla_id): value for casilla_id, value in inputs.items()}
    for casilla_id, value in (marked or {}).items():
        assert casilla_id in declared, f"{casilla_id} is not declared by the {exercise} edition"
        inputs[casilla_id] = value
    return calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        enum_binding_values={_DISPATCH_BINDING: "sl"},
        binding_values={
            "modelo-200-profile-new-entity-flag": Decimal("0"),
            **turnover_binding_values(snapshot, turnover),
            "modelo-200-profile-tributacion-estado-porcentaje": Decimal("100"),
            _STOCK_BINDING: _STOCK,
            "modelo-200-dotaciones-deterioro-creditos-saldo-no-cumplido-anteriores": Decimal("0"),
            "modelo-200-dotaciones-deterioro-creditos-saldo-cumplido-anteriores": Decimal("0"),
        },
        relation_values={
            f"modelo-200-pago-fraccionado-{ordinal}-{modalidad}": Decimal("0")
            for ordinal in ("primero", "segundo", "tercero")
            for modalidad in ("40-2", "40-3")
        },
        date_context={"filing_period": date(exercise, 12, 31)},
        formula_overrides=formula_overrides,
    )


@pytest.mark.parametrize("exercise", _EXERCISES)
def test_ceiling_is_the_general_limit_when_no_renta_is_stated(exercise: int) -> None:
    result = _calculate(exercise)

    assert result.values[_ceiling_casilla(_snapshot(exercise))] == _GENERAL_LIMIT


@pytest.mark.parametrize("exercise", _EXERCISES)
def test_quitas_and_reversion_de_deterioros_raise_the_ceiling_one_for_one(exercise: int) -> None:
    result = _calculate(exercise, marked={_QUITAS: Decimal("200000"), _REVERSION_DETERIOROS: Decimal("100000")})

    assert result.values[_ceiling_casilla(_snapshot(exercise))] == Decimal("3800000.00")


@pytest.mark.parametrize("exercise", _EXERCISES)
def test_each_renta_counts_on_its_own(exercise: int) -> None:
    quitas = _calculate(exercise, marked={_QUITAS: Decimal("200000")})
    deterioros = _calculate(exercise, marked={_REVERSION_DETERIOROS: Decimal("100000")})
    ceiling = _ceiling_casilla(_snapshot(exercise))

    assert quitas.values[ceiling] == Decimal("3700000.00")
    assert deterioros.values[ceiling] == Decimal("3600000.00")


@pytest.mark.parametrize("exercise", _EXERCISES)
def test_the_ceiling_never_exceeds_the_pending_stock(exercise: int) -> None:
    result = _calculate(exercise, marked={_QUITAS: Decimal("9000000")})

    assert result.values[_ceiling_casilla(_snapshot(exercise))] == _STOCK


@pytest.mark.parametrize("exercise", _EXERCISES_WITH_REVERSION_PARTICIPACIONES)
def test_reversion_de_participaciones_counts_where_the_edition_declares_it(exercise: int) -> None:
    snapshot = _snapshot(exercise)
    result = _calculate(exercise, marked={_REVERSION_PARTICIPACIONES: Decimal("50000")})

    assert result.values[_ceiling_casilla(snapshot)] == Decimal("3550000.00")


@pytest.mark.parametrize("exercise", _EXERCISES)
def test_a_nueva_creacion_has_the_stock_as_ceiling(exercise: int) -> None:
    result = _calculate(exercise, marked={_NUEVA_CREACION: Decimal("1")})

    assert result.values[_ceiling_casilla(_snapshot(exercise))] == _STOCK


@pytest.mark.parametrize(
    ("turnover", "percent"),
    [(Decimal("30000000"), Decimal("50")), (Decimal("70000000"), Decimal("25"))],
)
@pytest.mark.parametrize("exercise", _EXERCISES_WITH_TIERS)
def test_the_da_15_tiers_apply_where_the_edition_reads_the_twelve_month_turnover(
    exercise: int, turnover: Decimal, percent: Decimal
) -> None:
    snapshot = _snapshot(exercise)
    result = _calculate(exercise, turnover=turnover, marked={_QUITAS: Decimal("200000")})

    assert result.values[_ceiling_casilla(snapshot)] == _BASE * percent / Decimal(100) + Decimal("200000")


@pytest.mark.parametrize("exercise", _EXERCISES_WITHOUT_TIERS)
def test_an_edition_whose_manual_prints_no_da_15_limits_keeps_the_general_percentage(exercise: int) -> None:
    result = _calculate(exercise, turnover=Decimal("70000000"))

    assert result.values[_ceiling_casilla(_snapshot(exercise))] == _GENERAL_LIMIT


@pytest.mark.parametrize("exercise", _EXERCISES)
def test_an_entity_that_marks_extincion_has_no_ceiling_and_the_reason_is_named(exercise: int) -> None:
    snapshot = _snapshot(exercise)
    ceiling = _ceiling_casilla(snapshot)

    result = _calculate(exercise, marked={_EXTINCION: Decimal("1")})

    assert ceiling not in result.values
    reasons = [outcome.reason for outcome in result.unresolved_outcomes if outcome.casilla_id == ceiling]
    assert reasons == [RegistryUnresolvedOutcomeReason.M200_EXTINCION_ENTIDAD_UNSUPPORTED]


@pytest.mark.parametrize("exercise", _EXERCISES)
def test_an_entity_that_does_not_mark_extincion_is_not_refused(exercise: int) -> None:
    result = _calculate(exercise, marked={_EXTINCION: Decimal("0")})

    assert not [o for o in result.unresolved_outcomes if o.casilla_id == _ceiling_casilla(_snapshot(exercise))]


@pytest.mark.parametrize("exercise", _EXERCISES)
def test_the_operator_entering_the_ceiling_admits_an_extincion(exercise: int) -> None:
    snapshot = _snapshot(exercise)
    ceiling = _ceiling_casilla(snapshot)
    formula = next(f for f in snapshot.revision.formulas if f.id == _CEILING_FORMULA)
    entered = CasillaObservation(
        casilla_id=ceiling,
        value=Decimal("7000000"),
        formula_id=formula.id,
        op=formula.expression.op or "value",
        legal_refs=formula.legal_refs,
        source_refs=formula.source_refs,
    )

    result = _calculate(exercise, marked={_EXTINCION: Decimal("1")}, formula_overrides={ceiling: entered})

    assert result.values[ceiling] == Decimal("7000000")
    assert not [o for o in result.unresolved_outcomes if o.casilla_id == ceiling]
