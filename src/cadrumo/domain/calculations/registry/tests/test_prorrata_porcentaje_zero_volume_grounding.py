"""Grounding gate for the no-volume-data branch of the M303 prorrata percentage.

The prorrata volume casillas (``iva.prorrata-volumen-total`` /
``iva.prorrata-volumen-con-derecho``) are optional manual inputs, so the
overwhelming majority of filers — every trader with no exempt-without-right
operations — leave them blank and the percentage formula reaches its
no-volume-data branch.

LIVA art. 102.Uno makes the regla de prorrata applicable only where the sujeto
pasivo performs deduction-granting and non-granting operations *conjuntamente*::

    La regla de prorrata será de aplicación cuando el sujeto pasivo, en el
    ejercicio de su actividad empresarial o profesional, efectúe conjuntamente
    entregas de bienes o prestaciones de servicios que originen el derecho a la
    deducción y otras operaciones de análoga naturaleza que no habiliten para
    el ejercicio del citado derecho.

With no volumes declared that antecedent is unmet, so art. 104.Uno's percentage
limitation never bites and the input tax is deductible in full under arts. 92
and 94 — an effective percentage of 100. A percentage of 0 is the art. 104.Dos
answer only when the NUMERATOR is zero while the denominator is positive, which
is the computed branch, not this one; returning 0 for a blank declaration
asserts a total loss of the deduction right on a taxpayer who declared no fact
supporting it.

The two live revision families disagreed on exactly this branch: the post-2022 family
returned 100 while ``2022`` still returned 0, so a fully-taxable
trader amending a 2022 filing had every deduction zeroed. The applicable
law is identical across both windows — art. 102 was last amended by Ley 3/2006
(in force 01/01/2006, before the earlier window opens) and art. 104's only
later amendment, Ley 22/2013, touches apartado Tres.1º — so the divergence was
a defect in the earlier revision rather than a reflection of different law.

See Also:
    :func:`~domain.iva.compute_prorrata_general`
        Independent domain authority for the same legal quantity, which has
        always reported 100 when total operations are zero.
    :class:`~domain.calculations.registry.ModeloRevision`
        Revision whose ``formulas`` carry the branch under test.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core import CasillaId, validated_casilla_id
from .....core.resources import resources
from ....iva import (
    ProrrataInputs,
    ProrrataKind,
    compute_prorrata_general,
)
from .. import (
    calculate_registry_snapshot,
    resolve_available_bound_inputs_by_casilla_id,
    resolve_ledger_iva_aggregation_binding_values,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PORCENTAJE_ID: CasillaId = validated_casilla_id("iva.prorrata-porcentaje", surface="test casilla id")
_VOLUMEN_TOTAL_ID: CasillaId = validated_casilla_id("iva.prorrata-volumen-total", surface="test casilla id")
_VOLUMEN_CON_DERECHO_ID: CasillaId = validated_casilla_id(
    "iva.prorrata-volumen-con-derecho",
    surface="test casilla id",
)

#: 2020 resolves to the 2022 revision (period_selector 2022),
#: 2024 to its early-period epoch. Both windows sit entirely inside the unamended
#: art. 102.Uno / art. 104.Uno text, so both are bound by the same reading.
_LIVE_FILING_YEARS = (2020, 2024)

#: The percentage a full right to deduct carries. Read off arts. 92/94 (the
#: whole of the input tax is deductible when no prorrata limitation applies),
#: never off the formula under test.
_FULL_RIGHT_TO_DEDUCT = Decimal("100")

#: The art. 104.Dos answer for a trader whose operations are ALL exempt without
#: right: numerator zero over a positive denominator.
_NO_DEDUCTION_RIGHT = Decimal("0")


#: The settlement period and a mid-year quarter, with the liquidation date each
#: closes on. The prorrata percentage formula carries no date or period term, so
#: it should not move between them; probing both is what makes that a measured
#: fact rather than a reading of the expression.
_SETTLEMENT_PERIOD = ("4T", (12, 31))
_MID_YEAR_PERIOD = ("1T", (3, 31))


def _registry_percentage(
    filing_year: int,
    con_derecho: Decimal,
    total: Decimal,
    period: tuple[str, tuple[int, int]] = _SETTLEMENT_PERIOD,
) -> Decimal:
    """The prorrata percentage via the real registry snapshot and formula runtime."""
    period_token, (close_month, close_day) = period
    snapshot = resources().modelos.authority.snapshot("303", filing_year=filing_year, period=period_token)
    declared = {binding.id for binding in snapshot.revision.bindings}
    binding_values: dict[str, Decimal] = {
        binding_id: Decimal("100") if binding_id.endswith("state-attribution-ratio") else Decimal("0")
        for binding_id in declared
        & {
            "modelo-303-compensacion-pendiente-anteriores",
            "modelo-303-autoconsumo-promotor-base",
            "modelo-303-profile-state-attribution-ratio",
        }
    }
    binding_values.update(resolve_ledger_iva_aggregation_binding_values(snapshot.revision, ()))
    inputs = {
        **resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values),
        _VOLUMEN_TOTAL_ID: total,
        _VOLUMEN_CON_DERECHO_ID: con_derecho,
    }
    result = calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        binding_values=binding_values,
        date_context={"filing_period": date(filing_year, close_month, close_day)},
    )
    return result.values[_PORCENTAJE_ID]


@pytest.mark.parametrize("filing_year", _LIVE_FILING_YEARS)
def test_no_volume_data_leaves_the_deduction_right_whole(filing_year: int) -> None:
    """A blank prorrata declaration must not cost the taxpayer the deduction right.

    The expected value is the regulated full-deduction default (arts. 92/94,
    reached because art. 102.Uno's *conjuntamente* antecedent is unmet), not a
    re-run of the registry formula.
    """
    snapshot = resources().modelos.authority.snapshot("303", filing_year=filing_year, period="4T")
    percentage = _registry_percentage(filing_year, Decimal("0"), Decimal("0"))

    assert percentage == _FULL_RIGHT_TO_DEDUCT, (
        f"M303 {snapshot.revision.id}: a filing declaring no prorrata volumes "
        f"resolves the percentage to {percentage}; LIVA art. 102.Uno makes the "
        "regla de prorrata inapplicable when no exempt-without-right operations "
        "are declared, so the input tax stays deductible in full (arts. 92/94)"
    )


def test_both_live_revisions_agree_on_the_no_volume_branch() -> None:
    """One legal question, two revisions, one answer.

    Art. 102.Uno has stood in its current form since 01/01/2006 and art. 104's
    only post-2009 amendment (Ley 22/2013) touches apartado Tres.1º, so nothing
    in the earlier revision's applicable law can justify a different branch
    value. A divergence here is a defect, and this is the assertion that
    surfaces one.
    """
    by_revision = {
        resources().modelos.authority.snapshot("303", filing_year=year, period="4T").revision.id: (
            _registry_percentage(year, Decimal("0"), Decimal("0"))
        )
        for year in _LIVE_FILING_YEARS
    }

    assert len(by_revision) == len(_LIVE_FILING_YEARS), "the probe years must resolve to distinct revisions"
    assert len(set(by_revision.values())) == 1, (
        f"the live M303 revisions disagree on the no-volume prorrata branch: {by_revision}; "
        "the applicable articles are unamended across both windows, so they must agree"
    )


@pytest.mark.parametrize("filing_year", _LIVE_FILING_YEARS)
def test_registry_and_domain_agree_on_the_no_volume_branch(filing_year: int) -> None:
    """The independent domain authority is the second reading of the same rule.

    :func:`~domain.iva.compute_prorrata_general` has always reported 100 when
    total operations are zero, grounded in the same full-deduction criterion.
    The registry formula is the second implementation and the two must not be
    able to disagree.
    """
    domain_percentage = compute_prorrata_general(
        ProrrataInputs(
            operaciones_con_derecho_deduccion=Decimal("0"),
            operaciones_sin_derecho_deduccion=Decimal("0"),
        ),
        year=filing_year,
        kind=ProrrataKind.DEFINITIVA,
    ).percentage

    assert _registry_percentage(filing_year, Decimal("0"), Decimal("0")) == domain_percentage


#: LIVA art. 94 is headed "Operaciones cuya realización origina el derecho a la
#: deducción". It is the article that decides which operations grant the right,
#: so it supplies both the membership rule for the art. 104.Dos regla-1.ª
#: numerator and the full-deduction consequence this branch rests on.
_FULL_RIGHT_TO_DEDUCT_ARTICLE = "ley-37-1992:art-94"

_PRORRATA_PORCENTAJE_FORMULA_ID = "modelo-303-iva-prorrata-porcentaje"


def _prorrata_formula_legal_refs(filing_year: int) -> tuple[str, ...]:
    """The prorrata percentage formula's own declared legal refs for one filing year."""
    snapshot = resources().modelos.authority.snapshot("303", filing_year=filing_year, period="4T")
    formula = next(f for f in snapshot.revision.formulas if f.id == _PRORRATA_PORCENTAJE_FORMULA_ID)
    return tuple(formula.legal_refs)


@pytest.mark.parametrize("filing_year", _LIVE_FILING_YEARS)
def test_prorrata_formula_declares_the_full_right_to_deduct_article(filing_year: int) -> None:
    """The article the branch's consequence rests on must be declared on the formula itself.

    Carrying art. 94 only on the enclosing construct leaves a reader of this
    formula unable to see why a blank declaration yields a full deduction, and
    unable to see which article decides what enters the numerator. The
    dependency is the formula's, so the declaration is too.
    """
    refs = _prorrata_formula_legal_refs(filing_year)
    revision_id = resources().modelos.authority.snapshot("303", filing_year=filing_year, period="4T").revision.id

    assert _FULL_RIGHT_TO_DEDUCT_ARTICLE in refs, (
        f"M303 {revision_id}: the prorrata percentage formula declares {refs!r} and omits "
        f"{_FULL_RIGHT_TO_DEDUCT_ARTICLE!r}, the article that determines which operations "
        "originate the right to deduct and therefore both what the art. 104.Dos numerator "
        "counts and why a no-volume declaration leaves the deduction whole"
    )


def test_both_live_revisions_declare_the_same_prorrata_formula_grounding() -> None:
    """One legal question, two revisions, one set of citations.

    Art. 94's only amendment (art. 10.14 of Real Decreto-ley 7/2021, in force
    01-07-2021) rewrites apartado Uno número 1.º letra c, the exempt-operations
    enumeration, and leaves the chapeau and the sujetas-y-no-exentas rule this
    formula rests on untouched. Nothing in either window's applicable law can
    justify a different citation set, so a divergence is drift.
    """
    by_revision = {
        resources().modelos.authority.snapshot("303", filing_year=year, period="4T").revision.id: frozenset(
            _prorrata_formula_legal_refs(year),
        )
        for year in _LIVE_FILING_YEARS
    }

    assert len(by_revision) == len(_LIVE_FILING_YEARS), "the probe years must resolve to distinct revisions"
    assert len(set(by_revision.values())) == 1, (
        f"the live M303 revisions ground the prorrata percentage formula differently: {by_revision}"
    )


@pytest.mark.parametrize("filing_year", _LIVE_FILING_YEARS)
def test_no_volume_branch_holds_in_a_mid_year_period_too(filing_year: int) -> None:
    """The branch is not a settlement-period effect, on either revision.

    Modelo 303 genuinely does behave differently at settlement — the art.
    105.Cuatro regularización is due once a year — so "the percentage is the
    same in a mid-year quarter" is worth measuring rather than reading off the
    formula expression. This assertion carries the mid-year axis that the
    single-filing-year Modelo 303 regression used to be the only holder of, so
    retiring that regression loses no coverage.
    """
    percentage = _registry_percentage(filing_year, Decimal("0"), Decimal("0"), period=_MID_YEAR_PERIOD)

    assert percentage == _FULL_RIGHT_TO_DEDUCT
    assert percentage == _registry_percentage(filing_year, Decimal("0"), Decimal("0")), (
        "the no-volume prorrata percentage must not depend on the filing period"
    )


@pytest.mark.parametrize("filing_year", _LIVE_FILING_YEARS)
def test_a_wholly_exempt_trader_still_resolves_to_no_deduction_right(filing_year: int) -> None:
    """Prove the branch is a branch, not a blanket 100.

    Without this the assertions above would pass on a formula that answered 100
    for every input, including the one case where art. 104.Dos genuinely yields
    zero: a positive denominator with nothing in the numerator, i.e. a trader
    all of whose operations are exempt without right to deduct.
    """
    assert _registry_percentage(filing_year, Decimal("0"), Decimal("40000")) == _NO_DEDUCTION_RIGHT
