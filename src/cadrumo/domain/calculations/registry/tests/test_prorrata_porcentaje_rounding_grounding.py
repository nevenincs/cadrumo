"""Grounding gate for the rounding DIRECTION of the M303 prorrata percentage.

LIVA art. 104 ("La prorrata general") closes its apartado Dos with a single
sentence that fixes the rounding direction of the deduction percentage::

    La prorrata de deducción resultante de la aplicación de los criterios
    anteriores se redondeará en la unidad superior.

That sentence is carried verbatim as the first ``required_text`` entry of the
``ley-37-1992:art-104`` legal-catalogue entry, whose ``corpus_ref`` resolves
into the bundled consolidated law at the ``#a104`` anchor. It is the only
``redonde*`` clause in the whole of Ley 37/1992, so the direction is not a
matter of interpretation: the percentage goes to the NEXT unit up, never to the
NEAREST one.

The registry declared this formula under the shared ``integer`` rounding code,
which the formula runtime implements as half-up. Half-up and round-up agree
only when the fractional part exceeds one half, and both AEAT manual worked
examples for this scenario (72,72 % and 55,55 %) sit above it — so the two
readings agreed on every figure the corpus could check, and the divergence went
unobserved. On a 55,2 % ratio the half-up reading returned 55 where the law
grants 56, understating the taxpayer's deduction right.

This module pins three things that together make that class of defect visible:
the ``integer-ceiling`` code means what the provision says, the shared
``integer`` code is still half-up for its other consumers, and the registry
engine agrees with the independent :mod:`domain.iva` prorrata authority on
ratios chosen so that the two roundings genuinely disagree.

See Also:
    :class:`~domain.calculations.registry.RegistryRoundingCode`
        Closed rounding-code vocabulary whose ``INTEGER_CEILING`` member
        carries the art. 104.Dos direction.
    :func:`~domain.iva.compute_prorrata_general`
        Independent domain authority for the same legal quantity.
    :class:`~domain.calculations.registry.ModeloRevision`
        Revision whose ``formulas`` carry the declared rounding code.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from . import prorrata_porcentaje_rounding_grounding_scenarios as scenarios
from .published_authority import published_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]


def test_integer_ceiling_takes_a_fractional_result_to_the_next_unit() -> None:
    scenarios.check_integer_ceiling_takes_a_fractional_result_to_the_next_unit()


def test_integer_ceiling_leaves_an_exact_unit_untouched() -> None:
    scenarios.check_integer_ceiling_leaves_an_exact_unit_untouched()


def test_shared_integer_code_is_still_half_up_for_its_other_consumers() -> None:
    scenarios.check_shared_integer_code_is_still_half_up_for_its_other_consumers()


def test_selected_ratios_discriminate_between_the_two_roundings() -> None:
    scenarios.check_selected_ratios_discriminate_between_the_two_roundings()


@pytest.mark.parametrize("filing_year", scenarios.LIVE_FILING_YEARS)
def test_both_live_m303_revisions_declare_the_round_up_code(filing_year: int) -> None:
    scenarios.check_both_live_m303_revisions_declare_the_round_up_code(published_snapshot, filing_year)


@pytest.mark.parametrize("filing_year", scenarios.LIVE_FILING_YEARS)
@pytest.mark.parametrize(
    ("con_derecho", "total"),
    (*scenarios.DISCRIMINATING_VOLUMES, *scenarios.MANUAL_VOLUMES, scenarios.EXACT_VOLUMES),
)
def test_registry_and_domain_agree_on_the_prorrata_percentage(
    filing_year: int, con_derecho: Decimal, total: Decimal
) -> None:
    scenarios.check_registry_and_domain_agree_on_the_prorrata_percentage(
        published_snapshot, filing_year, con_derecho, total
    )
