"""Whether Modelo 200 asks for the cuota liquida minima [00619] (LIS art. 30 bis.1), every supported year.

Art. 30 bis.1 applies the tributacion minima to a contribuyente "cuyo importe
neto de la cifra de negocios sea al menos de 20 millones de euros durante los
12 meses anteriores a la fecha en que se inicie el periodo impositivo" and to
one "que tribute en el regimen de consolidacion fiscal ... con independencia de
su importe neto de la cifra de negocios", and not to the entidades of Ley
49/2002 taxed at 10 per cent (art. 29.3), the fondos de pensiones (art. 29.5)
or the SOCIMI. Where it applies the registry leaves its internal requirement box
without a value and names the edition's [00619] for the operator to state;
where it does not, the box is 0 and nothing is asked.

The cases are read from the law and the Manual practico de Sociedades, not from
the formula under test: the threshold is the manual's "al menos de 20 millones",
so 20.000.000,00 is inside and 19.999.999,99 outside. Every case runs the
compiled registry through the real calculation engine.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.domain.calculations.registry.formula_runtime import (
    RegistryCalculationResult,
    calculate_registry_snapshot,
)
from cadrumo.domain.calculations.registry.formula_runtime_ops import (
    OPERATOR_BOX_CONTEXT_KEY,
    RegistryUnresolvedOutcomeReason,
)
from cadrumo.domain.calculations.registry.schema import RegistrySnapshot
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.domain.calculations.registry.tests.modelo_200_casilla_ids import (
    M200_BONIFICACIONES_CASILLA,
    M200_CORRECCIONES_AUMENTO_CASILLA,
    M200_CORRECCIONES_DISMINUCION_CASILLA,
    M200_CUOTA_LIQUIDA_NEGATIVA_CASILLA,
    M200_CUOTA_LIQUIDA_POSITIVA_CASILLA,
    M200_DEDUCCION_DOBLE_IMPOSICION_CASILLA,
    M200_RESERVA_CAPITALIZACION_CASILLA,
    M200_RESULTADO_CONTABLE_CASILLA,
)
from cadrumo.domain.calculations.registry.tests.modelo_200_turnover import (
    PRIOR_TWELVE_MONTHS_TURNOVER,
    turnover_binding_values,
)

from ..compiler.authority import compiled_bundled_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_YEARS = tuple(filing_year_envelope().years)
_FORMULA = "modelo-200-cuota-liquida-minima-exigida"
_MINIMUM_CHAIN = "is-liquidacion-iv-cuota-liquida-minima"
_REASON = RegistryUnresolvedOutcomeReason.M200_CUOTA_LIQUIDA_MINIMA_UNSTATED
_LEGAL_FORM_BINDING = "modelo-200-profile-legal-entity-form"
_NEW_ENTITY_BINDING = "modelo-200-profile-new-entity-flag"
_DOMINANTE = validated_casilla_id("DP200001:00009", surface="test entidad dominante")
_DEPENDIENTE = validated_casilla_id("DP200001:00010", surface="test entidad dependiente")
_SOCIMI = validated_casilla_id("DP200001:00012", surface="test SOCIMI")
_FONDO_PENSIONES = validated_casilla_id("DP200001:00048", surface="test fondo de pensiones")

#: "al menos de 20 millones de euros" (manual "Cuota liquida minima (casilla 00619)").
_AT_THRESHOLD = Decimal("20000000.00")
_BELOW_THRESHOLD = Decimal("19999999.99")


def _snapshot(year: int) -> RegistrySnapshot:
    return compiled_bundled_authority().snapshot(
        "200", filing_year=year, period="0A", grade=RegistryAuthorityGrade.CALCULATION
    )


def _in_edition(snapshot: RegistrySnapshot, casilla_id: CasillaId) -> CasillaId:
    """The id the edition gives a box a sibling edition names ``casilla_id`` (the sheet prefix moves)."""
    number = casilla_id.rsplit(":", 1)[-1]
    matches = [c.id for c in snapshot.revision.casillas if c.number == number and c.id.rsplit(":", 1)[-1] == number]
    return matches[0] if len(matches) == 1 else casilla_id


def _requirement_box(snapshot: RegistrySnapshot) -> CasillaId:
    return next(f.target_casilla_id for f in snapshot.revision.formulas if f.id == _FORMULA)


def _minimum_box(snapshot: RegistrySnapshot) -> CasillaId:
    """The edition's own printed [00619], found by its continuity chain rather than by its record."""
    (box,) = (c.id for c in snapshot.revision.casillas if c.continuidad_id == _MINIMUM_CHAIN)
    return box


def _calculate(
    year: int,
    *,
    turnover: Decimal | None,
    marked: tuple[CasillaId, ...] = (),
    legal_form: str = "sl",
    new_entity: bool = False,
) -> RegistryCalculationResult:
    snapshot = _snapshot(year)
    declared = {casilla.id for casilla in snapshot.revision.casillas}
    inputs: dict[CasillaId, Decimal] = {
        _in_edition(snapshot, casilla_id): value
        for casilla_id, value in {
            M200_RESULTADO_CONTABLE_CASILLA: Decimal("2000000"),
            M200_CORRECCIONES_AUMENTO_CASILLA: Decimal("0"),
            M200_CORRECCIONES_DISMINUCION_CASILLA: Decimal("0"),
            M200_RESERVA_CAPITALIZACION_CASILLA: Decimal("0"),
            M200_DEDUCCION_DOBLE_IMPOSICION_CASILLA: Decimal("0"),
            M200_BONIFICACIONES_CASILLA: Decimal("0"),
            M200_CUOTA_LIQUIDA_POSITIVA_CASILLA: Decimal("0"),
            M200_CUOTA_LIQUIDA_NEGATIVA_CASILLA: Decimal("0"),
        }.items()
    }
    for casilla_id in marked:
        assert casilla_id in declared, f"{casilla_id} is not declared by the {year} edition"
        inputs[casilla_id] = Decimal("1")
    turnover_values = turnover_binding_values(snapshot, Decimal("0") if turnover is None else turnover)
    unresolved: tuple[str, ...] = ()
    if turnover is None:
        turnover_values.pop(PRIOR_TWELVE_MONTHS_TURNOVER)
        unresolved = (PRIOR_TWELVE_MONTHS_TURNOVER,)
    return calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        enum_binding_values={_LEGAL_FORM_BINDING: legal_form},
        binding_values={
            _NEW_ENTITY_BINDING: Decimal("1") if new_entity else Decimal("0"),
            **turnover_values,
            "modelo-200-profile-tributacion-estado-porcentaje": Decimal("100"),
            "modelo-200-bin-pendiente-ejercicios-anteriores": Decimal("0"),
            "modelo-200-dotaciones-deterioro-creditos-saldo-no-cumplido-anteriores": Decimal("0"),
            "modelo-200-dotaciones-deterioro-creditos-saldo-cumplido-anteriores": Decimal("0"),
        },
        unresolved_binding_ids=unresolved,
        relation_values={
            f"modelo-200-pago-fraccionado-{ordinal}-{modalidad}": Decimal("0")
            for ordinal in ("primero", "segundo", "tercero")
            for modalidad in ("40-2", "40-3")
        },
        date_context={"filing_period": date(year, 12, 31)},
    )


def _asks_for_the_minimum(year: int, result: RegistryCalculationResult) -> bool:
    snapshot = _snapshot(year)
    requirement = _requirement_box(snapshot)
    outcomes = [outcome for outcome in result.unresolved_outcomes if outcome.casilla_id == requirement]
    if not outcomes:
        return False
    (outcome,) = outcomes
    assert outcome.reason is _REASON
    assert outcome.context[OPERATOR_BOX_CONTEXT_KEY] == _minimum_box(snapshot)
    assert requirement not in result.values
    return True


def _asks_nothing(year: int, result: RegistryCalculationResult) -> bool:
    requirement = _requirement_box(_snapshot(year))
    return result.values.get(requirement) == Decimal("0") and not [
        outcome for outcome in result.unresolved_outcomes if outcome.casilla_id == requirement
    ]


def test_every_supported_year_resolves_an_edition_carrying_the_requirement_and_the_turnover() -> None:
    assert _YEARS
    for year in _YEARS:
        revision = _snapshot(year).revision
        assert _FORMULA in {formula.id for formula in revision.formulas}
        assert PRIOR_TWELVE_MONTHS_TURNOVER in {binding.id for binding in revision.bindings}
        binding = next(b for b in revision.bindings if b.id == PRIOR_TWELVE_MONTHS_TURNOVER)
        assert "ley-27-2014:art-30-bis" in binding.legal_refs


@pytest.mark.parametrize("year", _YEARS)
def test_a_turnover_of_at_least_twenty_million_asks_for_the_edition_box(year: int) -> None:
    assert _asks_for_the_minimum(year, _calculate(year, turnover=_AT_THRESHOLD))


@pytest.mark.parametrize("year", _YEARS)
def test_a_turnover_below_twenty_million_without_consolidation_asks_nothing(year: int) -> None:
    assert _asks_nothing(year, _calculate(year, turnover=_BELOW_THRESHOLD))


@pytest.mark.parametrize("key", [_DOMINANTE, _DEPENDIENTE], ids=["dominante", "dependiente"])
@pytest.mark.parametrize("year", _YEARS)
def test_a_group_entity_is_asked_whatever_its_turnover(year: int, key: CasillaId) -> None:
    assert _asks_for_the_minimum(year, _calculate(year, turnover=_BELOW_THRESHOLD, marked=(key,)))


@pytest.mark.parametrize("year", _YEARS)
def test_a_group_entity_is_asked_even_with_the_turnover_undeclared(year: int) -> None:
    assert _asks_for_the_minimum(year, _calculate(year, turnover=None, marked=(_DOMINANTE,)))


@pytest.mark.parametrize(
    ("marked", "legal_form"),
    [((), "sin_fines_lucrativos"), ((_SOCIMI,), "sl"), ((_FONDO_PENSIONES,), "sl")],
    ids=["ley-49-2002-art-29-3", "socimi", "fondo-de-pensiones-art-29-5"],
)
@pytest.mark.parametrize("year", _YEARS)
def test_an_excluded_contribuyente_is_not_asked_even_in_a_group(
    year: int, marked: tuple[CasillaId, ...], legal_form: str
) -> None:
    result = _calculate(year, turnover=_AT_THRESHOLD, marked=(*marked, _DOMINANTE), legal_form=legal_form)

    assert _asks_nothing(year, result)


@pytest.mark.parametrize("year", _YEARS)
def test_a_nueva_creacion_at_the_reduced_rate_is_not_excluded(year: int) -> None:
    assert _asks_for_the_minimum(year, _calculate(year, turnover=_AT_THRESHOLD, new_entity=True))


@pytest.mark.parametrize("year", _YEARS)
def test_an_undeclared_turnover_leaves_the_requirement_without_a_reason(year: int) -> None:
    """The calculation alone cannot ask for the minimum: verification's turnover gate must."""
    result = _calculate(year, turnover=None)
    requirement = _requirement_box(_snapshot(year))

    assert requirement not in result.values
    assert not [outcome for outcome in result.unresolved_outcomes if outcome.casilla_id == requirement]
