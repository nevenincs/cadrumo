"""The M131 datos-base advisory fires on a pago fraccionado declared without its rendimientos, and only then.

Casilla 01 ("Suma de rendimientos netos") is the módulos rendimiento the
filer declares for the datos-base activities. It is ``input_kind = "manual"``,
declares no formula, is not schema-required, and — unlike its siblings — is
read by no formula in any M131 revision: 03 feeds 04, 05 feeds 06, and
07 = 02 + 04 + 06 never references 01. Nothing downstream notices its
absence, so an omitted 01 reaches the fichero as a zero rendimiento beside a
positive pago fraccionado.

The revision already declared ``implies_nonzero(["01", "02"])``, which fires
on a positive 01 with a zero 02. That predicate is structurally incapable of
catching this defect: ``implies_nonzero`` holds trivially at or below zero, so
the case where 01 is *itself* the omitted field satisfies it. The converse
predicate asserted here is the one that watches the income direction.

The antecedent is 02 (pago fraccionado previo por datos-base), deliberately
NOT 07 (the summed pagos previos). RD 439/2007 art. 110.1.b routes the two
lawful ways to owe a pago fraccionado with no datos-base rendimiento to other
casillas — "no pudiera determinarse ningún dato-base" through 03/04, and
actividades agrícolas, ganaderas y forestales (art. 110.1.c) through 05/06 —
so both leave 02 at zero while 07 stays positive. An antecedent of 07 would
therefore false-fire on every pure-agrario and sin-datos-base filer, which is
the restrictive-provision-as-default shape that trains operators to ignore the
alert. Keyed on 02, the fire condition is unreachable for a lawful filing:
art. 110.1.b fixes 02 at el 4 / 3 / 2 por ciento of 01, a scale whose minimum
is 2 por 100, so a strictly positive 02 implies a strictly positive 01.

The silent cases are as load-bearing as the firing one and are asserted rather
than assumed, because a predicate that simply always fired would satisfy the
firing test alone.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core import validated_casilla_id
from cadrumo.domain.calculations.registry.temporal import select_revision
from ....domain.deadlines import EntityType, IVARegime, TaxpayerProfile
from ....tests.registry_tree import bundled_registry_tree
from .._verification_predicates import _evaluate_predicate_expression, evaluate_advisory_predicate_fires

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: One filing year per M131 revision. Each resolves to its revision through the
#: law-determined (modelo, filing_year, period) triple rather than by naming a
#: revision id, so a re-dated revision cannot silently repoint this gate.
_REVISION_YEARS = (2023, 2024, 2025, 2026)

_SUMA_RENDIMIENTOS_NETOS = validated_casilla_id("01", surface="m131-datos-base-rendimientos-advisory")
_PAGO_FRACCIONADO_PREVIO_DATOS_BASE = validated_casilla_id("02", surface="m131-datos-base-rendimientos-advisory")


def _predicate_id(year: int) -> str:
    revision = "2019-2023" if year <= 2023 else str(year)
    return f"modelo-131-{revision}-rendimientos-declarados-cuando-pago-fraccionado-datos-base-positivo"


def _profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="12345678Z",
        entity_type=EntityType.NATURAL_PERSON,
        iva_regime=IVARegime.EXENTO,
    )


def _predicate(year: int):
    """Return the registry's own declared predicate, not a hand-written expression."""
    modelos, _catalogues = bundled_registry_tree()
    modelo = next(candidate for candidate in modelos if candidate.id == "131")
    revision = select_revision(modelo, filing_year=year, period="1T")
    for predicate in revision.verification_predicates or ():
        if predicate.predicate_id == _predicate_id(year):
            return predicate
    pytest.fail(f"{_predicate_id(year)} is not declared on the M131/{year} revision")


def _holds(year: int, rendimientos: str, pago_previo: str) -> bool:
    return _evaluate_predicate_expression(
        _predicate(year).expression,
        {
            _SUMA_RENDIMIENTOS_NETOS: Decimal(rendimientos),
            _PAGO_FRACCIONADO_PREVIO_DATOS_BASE: Decimal(pago_previo),
        },
        _profile(),
    )


@pytest.mark.parametrize("year", _REVISION_YEARS)
def test_the_predicate_is_declared_advisory_and_grounded(year: int) -> None:
    """Advisory rather than blocking, because the operator may hold the correcting figure.

    A blocking form would refuse the filing outright on a discrepancy the
    taxpayer can legitimately explain at the counter, so the guard prompts a
    review instead.
    """
    predicate = _predicate(year)

    assert predicate.finding_kind == "ADVISORY"
    assert predicate.expression == 'implies_nonzero(["02", "01"])'
    assert predicate.legal_refs, "an advisory over a regulated value must carry its provisions"


@pytest.mark.parametrize("year", _REVISION_YEARS)
def test_it_fires_when_a_datos_base_pago_is_declared_without_its_rendimientos(year: int) -> None:
    """The defect case: the pago fraccionado is declared, the income that produced it is not."""
    assert _holds(year, "0", "450.00") is False


@pytest.mark.parametrize("year", _REVISION_YEARS)
def test_it_holds_silently_for_a_genuine_no_activity_filer(year: int) -> None:
    """The control the firing test cannot provide: a filer who owes nothing sees nothing."""
    assert _holds(year, "0", "0") is True


@pytest.mark.parametrize("year", _REVISION_YEARS)
def test_it_holds_when_the_rendimientos_are_declared(year: int) -> None:
    """The ordinary datos-base filing: income declared and pago derived from it."""
    assert _holds(year, "18000.00", "450.00") is True


@pytest.mark.parametrize("year", _REVISION_YEARS)
def test_it_holds_for_agrario_and_sin_datos_base_filers(year: int) -> None:
    """Both lawful no-datos-base routes leave casilla 02 at zero, so neither may fire.

    An agrario filer settles through 05/06 and a sin-datos-base filer through
    03/04 (RD 439/2007 art. 110.1.c and art. 110.1.b in fine). Both carry a
    positive 07 with an empty 01, which is exactly why the antecedent is 02 and
    not 07.
    """
    assert _holds(year, "0", "0") is True


@pytest.mark.parametrize("year", _REVISION_YEARS)
def test_a_negative_antecedent_holds_trivially(year: int) -> None:
    """``implies_nonzero`` is defined at or below zero, so a loss never fires."""
    assert _holds(year, "0", "-10.00") is True


@pytest.mark.parametrize("year", _REVISION_YEARS)
def test_an_absent_casilla_01_is_read_as_zero_and_still_fires(year: int) -> None:
    """Omission is the defect, so the missing-key case must behave as the zero case.

    The evaluator defaults an unpopulated casilla to zero; asserting it here
    keeps a future change to that default from silently reopening the gap.
    """
    assert (
        _evaluate_predicate_expression(
            _predicate(year).expression,
            {_PAGO_FRACCIONADO_PREVIO_DATOS_BASE: Decimal("450.00")},
            _profile(),
        )
        is False
    )


@pytest.mark.parametrize("year", _REVISION_YEARS)
def test_the_calculate_path_advisory_agrees_with_the_verify_path(year: int) -> None:
    """The two surfaces read one predicate, so a divergence would be a real defect.

    ``evaluate_advisory_predicate_fires`` drives the calculate-path diagnostic
    and ``_evaluate_predicate_expression`` the verify-path finding. For this
    operator they are exact complements, and pinning that here is what stops
    one surface from reporting the under-declaration while the other stays
    quiet.
    """
    expression = _predicate(year).expression
    for rendimientos, pago_previo in (("0", "450.00"), ("0", "0"), ("18000.00", "450.00"), ("0", "-10.00")):
        values = {
            _SUMA_RENDIMIENTOS_NETOS: Decimal(rendimientos),
            _PAGO_FRACCIONADO_PREVIO_DATOS_BASE: Decimal(pago_previo),
        }
        fires = evaluate_advisory_predicate_fires(expression, values)
        holds = _evaluate_predicate_expression(expression, values, _profile())
        assert fires is not holds, f"calculate/verify disagree at 01={rendimientos}, 02={pago_previo}"
