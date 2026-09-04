"""The suffered-retención advisory for capital mobiliario ahorro fires on uncredited withholding, and only then.

Casilla 0597 is the retención the taxpayer SUFFERED on rendimientos del
capital mobiliario sujetos a la base del ahorro, declared by the payer on
Modelo 123 (or annually on Modelo 193) and credited by the taxpayer against
the cuota. It is a bound casilla, so with no observation to resolve it the
engine threads an absent slot as a zero and emits nothing: an uncredited
retención is tax already paid and paid again, arriving as a clean number in
the over-declaration direction this apparatus otherwise does not watch.

The antecedent is 0036, the GROSS total ingresos íntegros del capital
mobiliario ahorro (the sum of the per-source components: dividendos,
intereses, letras del Tesoro, otros activos financieros, seguros de
capitalización, rentas por imposición de capitales, deuda subordinada /
preferentes, PALP), because retención is computed on gross. It is
deliberately NOT 0038 (rendimiento neto) or 0040 (rendimiento neto
reducido), both of which are post-deducciones / post-reducción and can be
zero for a filer who did suffer withholding, which would suppress the
advisory in the cases it exists for — the exact objection the trabajo
predicate's own 0025 rejection already established, applied here on this
revision's own casilla set rather than by analogy.

The silent case is as load-bearing as the firing one, for the same reason
the trabajo predicate's is: ``implies_nonzero`` holds trivially at or below
zero, so a filer with no capital mobiliario ahorro income never fires, and
that is what this asserts rather than assumes.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.casilla_id import validated_casilla_id
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.contribuyente.entity_type import EntityType
from ....domain.deadlines.models import IVARegime, TaxpayerProfile
from .._verification_predicates import _evaluate_predicate_expression

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: Every M100 revision declaring casilla 0597. Each was resolved from that
#: revision's OWN casilla set through semantic_role rather than copied,
#: because ids renumber across filing years even when they happen to agree
#: here (verified independently against all six: 0036 and 0597 hold in
#: every one).
_REVISION_YEARS = (2020, 2021, 2022, 2023, 2024, 2025)


def _predicate_id(year: int) -> str:
    return f"modelo-100-{year}-retenciones-capital-mobiliario-declaradas-cuando-ingresos-integros-positivos"


_GROSS_CAPITAL_MOBILIARIO_AHORRO_INCOME = validated_casilla_id(
    "0036",
    surface="capital-mobiliario-retencion-advisory",
)
_RETENCION_CAPITAL_MOBILIARIO = validated_casilla_id("0597", surface="capital-mobiliario-retencion-advisory")


def _profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="12345678Z",
        entity_type=EntityType.NATURAL_PERSON,
        iva_regime=IVARegime.EXENTO,
    )


def _predicate(year: int):
    """Return the registry's own declared predicate, not a hand-written expression."""
    revision = bundled_authority().snapshot("100", filing_year=year, period="0A").revision
    for predicate in revision.verification_predicates or ():
        if predicate.predicate_id == _predicate_id(year):
            return predicate
    pytest.fail(f"{_predicate_id(year)} is not declared on the M100/{year} revision")


def _holds(year: int, gross: str, retencion: str) -> bool:
    predicate = _predicate(year)
    return _evaluate_predicate_expression(
        predicate.expression,
        {_GROSS_CAPITAL_MOBILIARIO_AHORRO_INCOME: Decimal(gross), _RETENCION_CAPITAL_MOBILIARIO: Decimal(retencion)},
        _profile(),
    )


@pytest.mark.parametrize("year", _REVISION_YEARS)
def test_the_predicate_is_declared_advisory_and_grounded(year: int) -> None:
    """Advisory rather than blocking, because a lawful zero retención exists.

    A blocking form would refuse a legitimate filing by a taxpayer whose
    payer withheld nothing, which is lawful for some capital mobiliario
    products.
    """
    predicate = _predicate(year)

    assert predicate.finding_kind == "ADVISORY"
    assert predicate.expression == 'implies_nonzero(["0036", "0597"])'
    assert predicate.legal_refs, "an advisory over a regulated value must carry its provisions"


@pytest.mark.parametrize("year", _REVISION_YEARS)
def test_it_fires_when_capital_mobiliario_income_is_declared_and_no_retencion_is_credited(year: int) -> None:
    """The defect case: gross income present, withholding absent."""
    assert _holds(year, "5000.00", "0") is False


@pytest.mark.parametrize("year", _REVISION_YEARS)
def test_it_holds_silently_when_there_is_no_capital_mobiliario_income(year: int) -> None:
    """The control, and the reason a category-keyed signal would be wrong here too.

    Without this, a predicate that simply always fired would pass the test above.
    """
    assert _holds(year, "0", "0") is True


@pytest.mark.parametrize("year", _REVISION_YEARS)
def test_it_holds_when_the_retencion_is_credited(year: int) -> None:
    """The ordinary case: income declared and withholding credited, so nothing fires."""
    assert _holds(year, "5000.00", "950.00") is True
