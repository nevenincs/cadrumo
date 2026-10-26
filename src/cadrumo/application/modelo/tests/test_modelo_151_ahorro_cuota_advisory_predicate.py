"""The impatriado ahorro branch cannot report savings income and no tax on it in silence.

Art. 93.2.e) splits the impatriado cuota íntegra in two: the general part
(1.º) and the part corresponding to the rentas del art. 25.1.f) TRLIRNR --
dividends, interest and savings gains (2.º). Modelo 151 computes both, each from
its own base by ``lookup_bracket`` over the escala of the year, and its export
writes the ahorro pair into the design's boxes [18] and [20].

WHY A PREDICATE OVER A COMPUTED PAIR. The cuota is formula-derived, so a positive
ahorro base with a zero cuota is only reachable through a registry regression in
the escala or the formula chain. The verify gate must still surface that rather
than grant a clean verification (no-silent-under-declaration), exactly as the
general branch's predicate does.

ADVISORY, not blocking, and ``implies_nonzero`` holds trivially when the
antecedent is at or below zero -- so an impatriado with no rentas del ahorro,
which is the common case, never fires. The years come from the published support
envelope, so every supported edition is held to it.
"""

from __future__ import annotations

from decimal import Decimal
from functools import cache

import pytest

from ....core.casilla_id import validated_casilla_id
from ....domain.calculations.registry.tests.published_authority import (
    published_authored_revision,
    published_supported_filing_years,
)
from ....domain.contribuyente.entity_type import EntityType
from ....domain.deadlines.models import IVARegime, TaxpayerProfile
from ..verification_predicates import evaluate_predicate_expression

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_SURFACE = "modelo-151-ahorro-cuota-advisory"
_BASE_AHORRO = validated_casilla_id("impatriado.base-liquidable-ahorro", surface=_SURFACE)
_CUOTA_AHORRO = validated_casilla_id("impatriado.cuota-integra-ahorro", surface=_SURFACE)


@cache
def _years() -> tuple[int, ...]:
    support = published_supported_filing_years()
    assert support is not None, "the published authority declares no support envelope"
    return tuple(support.years)


def _profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="12345678Z",
        entity_type=EntityType.from_registry("natural_person"),
        iva_regime=IVARegime("EXENTO"),
    )


def _revision(year: int):
    return published_authored_revision("151", year=year)


def _predicate(year: int):
    """Return the registry's own declared predicate, located by what it GUARDS.

    Found by its casilla pair rather than by predicate_id, so renaming the
    predicate does not silently empty this module.
    """
    for predicate in _revision(year).verification_predicates or ():
        expression = predicate.expression
        if str(_BASE_AHORRO) in expression and str(_CUOTA_AHORRO) in expression:
            return predicate
    pytest.fail(f"M151/{year} declares no predicate guarding the ahorro base/cuota pair")


def _holds(year: int, base: str, cuota: str) -> bool:
    return evaluate_predicate_expression(
        _predicate(year).expression,
        {_BASE_AHORRO: Decimal(base), _CUOTA_AHORRO: Decimal(cuota)},
        _profile(),
    )


@pytest.mark.parametrize("year", _years())
def test_the_predicate_is_advisory_and_grounded(year: int) -> None:
    """Blocking would refuse filings this apparatus has no authority to refuse."""
    predicate = _predicate(year)

    assert predicate.finding_kind == "ADVISORY"
    assert "ley-35-2006:art-93" in {str(ref) for ref in predicate.legal_refs}


@pytest.mark.parametrize("year", _years())
def test_it_fires_on_savings_income_declared_with_no_tax(year: int) -> None:
    """The defect it exists for: a positive ahorro base and a zero ahorro cuota."""
    assert _holds(year, "0", "0"), "a filer with no rentas del ahorro must not fire"
    assert not _holds(year, "25000.00", "0"), (
        "a positive base liquidable del ahorro with a zero cuota must surface a finding"
    )


@pytest.mark.parametrize("year", _years())
def test_it_stays_quiet_when_the_branch_is_declared_properly(year: int) -> None:
    """Non-vacuity from the other side: it must not fire on a correct filing."""
    assert _holds(year, "25000.00", "5130.00")
    assert _holds(year, "6000.00", "1140.00")


@pytest.mark.parametrize("year", _years())
def test_a_negative_or_zero_base_holds_trivially(year: int) -> None:
    """Material implication, so losses and empty branches are never findings."""
    assert _holds(year, "-1500.00", "0")
    assert _holds(year, "0", "0")


@pytest.mark.parametrize("year", _years())
def test_both_branches_of_the_cuota_are_guarded(year: int) -> None:
    """Asserted together so a future edit cannot drop one and leave the modelo half-guarded."""
    expressions = [predicate.expression for predicate in _revision(year).verification_predicates or ()]

    general = [
        expression
        for expression in expressions
        if "impatriado.base-liquidable-general" in expression and "impatriado.cuota-integra-general" in expression
    ]
    ahorro = [
        expression for expression in expressions if str(_BASE_AHORRO) in expression and str(_CUOTA_AHORRO) in expression
    ]

    assert general, "the general-branch soundness predicate has gone"
    assert ahorro, "the ahorro-branch soundness predicate has gone"
