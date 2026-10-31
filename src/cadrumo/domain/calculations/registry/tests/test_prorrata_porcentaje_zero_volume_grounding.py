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

import pytest

from . import prorrata_porcentaje_zero_volume_grounding_scenarios as scenarios
from .published_authority import published_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]


@pytest.mark.parametrize("filing_year", scenarios.LIVE_FILING_YEARS)
def test_no_volume_data_leaves_the_deduction_right_whole(filing_year: int) -> None:
    scenarios.check_no_volume_data_leaves_the_deduction_right_whole(published_snapshot, filing_year)


def test_both_live_revisions_agree_on_the_no_volume_branch() -> None:
    scenarios.check_both_live_revisions_agree_on_the_no_volume_branch(published_snapshot)


@pytest.mark.parametrize("filing_year", scenarios.LIVE_FILING_YEARS)
def test_registry_and_domain_agree_on_the_no_volume_branch(filing_year: int) -> None:
    scenarios.check_registry_and_domain_agree_on_the_no_volume_branch(published_snapshot, filing_year)


@pytest.mark.parametrize("filing_year", scenarios.LIVE_FILING_YEARS)
def test_prorrata_formula_declares_the_full_right_to_deduct_article(filing_year: int) -> None:
    scenarios.check_prorrata_formula_declares_the_full_right_to_deduct_article(published_snapshot, filing_year)


def test_both_live_revisions_declare_the_same_prorrata_formula_grounding() -> None:
    scenarios.check_both_live_revisions_declare_the_same_prorrata_formula_grounding(published_snapshot)


@pytest.mark.parametrize("filing_year", scenarios.LIVE_FILING_YEARS)
def test_no_volume_branch_holds_in_a_mid_year_period_too(filing_year: int) -> None:
    scenarios.check_no_volume_branch_holds_in_a_mid_year_period_too(published_snapshot, filing_year)


@pytest.mark.parametrize("filing_year", scenarios.LIVE_FILING_YEARS)
def test_a_wholly_exempt_trader_still_resolves_to_no_deduction_right(filing_year: int) -> None:
    scenarios.check_a_wholly_exempt_trader_still_resolves_to_no_deduction_right(published_snapshot, filing_year)
