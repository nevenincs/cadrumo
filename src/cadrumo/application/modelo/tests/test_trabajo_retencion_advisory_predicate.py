"""The suffered-retención advisory fires on uncredited withholding, and only then.

Casilla 0596 is the retención the taxpayer SUFFERED on rendimientos del trabajo,
declared by the payer on Modelo 111 and credited by the taxpayer against the
cuota. It is a bound casilla, so with no observation to resolve it the engine
threads an absent slot as a zero and emits nothing: an uncredited retención is tax
already paid and paid again, arriving as a clean number in the over-declaration
direction this apparatus otherwise does not watch.

The antecedent is 0012, the gross trabajo income total, because retención is
computed on gross. It is deliberately NOT 0025 (rendimiento neto reducido), which
is post-deducciones and can be zero for a filer who did suffer withholding, which
would suppress the advisory in the cases it exists for.

The silent case is as load-bearing as the firing one. A signal keyed on the
declared income CATEGORY was measured and refused because withholding is scaled to
the payer's projected annual rate and is lawfully zero below the thresholds, so a
category-keyed rule fires on low-income filers whose zero is correct.
``implies_nonzero`` holds trivially at or below zero, so a filer with no trabajo
income never fires, and that is what this asserts rather than assumes.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.casilla_id import validated_casilla_id
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.contribuyente.entity_type import EntityType
from ....domain.deadlines.models import IrpfIncomeCategory, IVARegime, TaxpayerProfile
from .._verification_predicates import evaluate_predicate_expression

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: Every M100 revision declaring casilla 0596. Each was resolved from that
#: revision's OWN casilla set through semantic_role rather than copied, because
#: ids renumber across filing years even when they happen to agree here.
_REVISION_YEARS = (2020, 2021, 2022, 2023, 2024, 2025)


def _predicate_id(year: int) -> str:
    return f"modelo-100-{year}-retenciones-trabajo-declaradas-cuando-ingresos-integros-trabajo-positivos"


_GROSS_TRABAJO_INCOME = validated_casilla_id("0012", surface="trabajo-retencion-advisory")
_RETENCION_TRABAJO = validated_casilla_id("0596", surface="trabajo-retencion-advisory")


def _profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="12345678Z",
        entity_type=EntityType.NATURAL_PERSON,
        irpf_income_categories=frozenset({IrpfIncomeCategory.TRABAJO}),
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
    return evaluate_predicate_expression(
        predicate.expression,
        {_GROSS_TRABAJO_INCOME: Decimal(gross), _RETENCION_TRABAJO: Decimal(retencion)},
        _profile(),
    )


@pytest.mark.parametrize("year", _REVISION_YEARS)
def test_the_predicate_is_declared_advisory_and_grounded(year: int) -> None:
    """Advisory rather than blocking, because a lawful zero retención exists.

    A blocking form would refuse a legitimate filing by a taxpayer whose payer
    withheld nothing, which is lawful below the withholding thresholds.
    """
    predicate = _predicate(year)

    assert predicate.finding_kind == "ADVISORY"
    assert predicate.expression == 'implies_nonzero(["0012", "0596"])'
    assert predicate.legal_refs, "an advisory over a regulated value must carry its provisions"


@pytest.mark.parametrize("year", _REVISION_YEARS)
def test_it_fires_when_trabajo_income_is_declared_and_no_retencion_is_credited(year: int) -> None:
    """The defect case: gross income present, withholding absent."""
    assert _holds(year, "18000.00", "0") is False


@pytest.mark.parametrize("year", _REVISION_YEARS)
def test_it_holds_silently_when_there_is_no_trabajo_income(year: int) -> None:
    """The control, and the reason a category-keyed signal was refused.

    Without this, a predicate that simply always fired would pass the test above.
    """
    assert _holds(year, "0", "0") is True


@pytest.mark.parametrize("year", _REVISION_YEARS)
def test_it_holds_when_the_retencion_is_credited(year: int) -> None:
    """The ordinary case: income declared and withholding credited, so nothing fires."""
    assert _holds(year, "18000.00", "2400.00") is True
