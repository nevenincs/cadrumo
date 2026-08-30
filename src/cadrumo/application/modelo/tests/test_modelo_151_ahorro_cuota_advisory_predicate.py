"""The impatriado ahorro branch cannot report savings income and no tax on it in silence.

Art. 93.2.e) splits the impatriado cuota íntegra in two: the general part
(1.º) and the part corresponding to the rentas del art. 25.1.f) TRLIRNR --
dividends, interest and savings gains (2.º). Modelo 151's 2015-2022 revision
files that second branch through the operator's own page-08 boxes: casilla
``[18] Base liquidable del ahorro`` and casilla ``[20] Cuota correspondiente a
la base liquidable general del ahorro``, which together feed ``[21] Cuota
íntegra total``.

WHY THIS BRANCH AND NOT THE GENERAL ONE. The general branch is formula-derived
-- ``impatriado.cuota-integra-general`` comes from a ``lookup_bracket`` over the
art. 93.2.e).1.º escala -- so a positive base with a zero cuota there is only
reachable through a registry regression. Casilla [20] is NOT derived in this
revision: the operator supplies it. Plain omission reaches a filed declaration
that reports savings income and no tax on it, which is the shape
no-silent-under-declaration exists for.

WHAT IT DELIBERATELY DOES NOT DO. It states no rate and computes nothing. The
escala that would let casilla [20] be DERIVED rather than merely checked is not
grounded in this tree for the 2015-2022 era: the bundled corpus carries art. 93
only in its current and 2023 redactions, and the pre-2023 text was not
retrievable. Checking without a rate is the honest half of the fix; inventing a
rate to compute with would not be.

ADVISORY, not blocking, and ``implies_nonzero`` holds trivially when the
antecedent is at or below zero -- so an impatriado with no rentas del ahorro,
which is the common case, never fires.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core import validated_casilla_id
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.deadlines.models import EntityType, IVARegime, TaxpayerProfile
from .._verification_predicates import _evaluate_predicate_expression

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SURFACE = "modelo-151-ahorro-cuota-advisory"
_BASE_AHORRO = validated_casilla_id("p08.base-liquidable-del-ahorro-18", surface=_SURFACE)
_CUOTA_AHORRO = validated_casilla_id(
    "p08.cuota-correspondiente-e-general-del-ahorro-20",
    surface=_SURFACE,
)

#: Ejercicios governed by the 2015-2022 revision, sampled at both ends and inside.
_YEARS = (2015, 2019, 2022)


def _profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="12345678Z",
        entity_type=EntityType.NATURAL_PERSON,
        iva_regime=IVARegime.EXENTO,
    )


def _revision(year: int):
    return bundled_authority().snapshot("151", filing_year=year, period="0A").revision


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
    return _evaluate_predicate_expression(
        _predicate(year).expression,
        {_BASE_AHORRO: Decimal(base), _CUOTA_AHORRO: Decimal(cuota)},
        _profile(),
    )


@pytest.mark.parametrize("year", _YEARS)
def test_the_predicate_is_advisory_and_grounded(year: int) -> None:
    """Blocking would refuse filings this apparatus has no authority to refuse."""
    predicate = _predicate(year)

    assert predicate.finding_kind == "ADVISORY"
    assert "ley-35-2006:art-93" in {str(ref) for ref in predicate.legal_refs}


@pytest.mark.parametrize("year", _YEARS)
def test_it_fires_on_savings_income_declared_with_no_tax(year: int) -> None:
    """The defect it exists for: a positive ahorro base and a zero ahorro cuota."""
    assert _holds(year, "0", "0"), "a filer with no rentas del ahorro must not fire"
    assert not _holds(year, "25000.00", "0"), (
        "a positive base liquidable del ahorro with a zero cuota must surface a finding"
    )


@pytest.mark.parametrize("year", _YEARS)
def test_it_stays_quiet_when_the_branch_is_declared_properly(year: int) -> None:
    """Non-vacuity from the other side: it must not fire on a correct filing."""
    assert _holds(year, "25000.00", "4750.00")
    assert _holds(year, "6000.00", "1140.00")


@pytest.mark.parametrize("year", _YEARS)
def test_a_negative_or_zero_base_holds_trivially(year: int) -> None:
    """Material implication, so losses and empty branches are never findings."""
    assert _holds(year, "-1500.00", "0")
    assert _holds(year, "0", "0")


def test_both_branches_of_the_cuota_are_guarded() -> None:
    """The general branch already had this; the ahorro branch is the one that was missing.

    Asserted together so a future edit cannot drop one and leave the modelo
    half-guarded without a test noticing.
    """
    expressions = [predicate.expression for predicate in _revision(2019).verification_predicates or ()]

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
