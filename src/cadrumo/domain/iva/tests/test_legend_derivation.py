"""The legend axis derives only what the issuer wrote, and defaults to nothing.

Every expected value here comes from RD 1619/2012 art. 6.1 as carried in
:data:`~domain.iva.REGIME_LEGENDS` -- the phrases are quoted from the bundled
consolidated text, and the category each one declares is the regulation's, not
this suite's. Nothing is computed from the code under test.

The gate that matters most is the one asserting the axis derives NOTHING for the
ordinary invoice. Six of the seven mandated mentions declare no category, and an
invoice printing none at all is entirely normal, so an absent outcome is the
common case rather than a gap. A default would make every one of those invoices
carry a category the issuer never stated.

See Also:
    :func:`~domain.iva.derive_category_from_regime_legend`
        The derivation under test.
    :data:`~domain.iva.REGIME_LEGENDS`
        The statutory vocabulary the expectations are read from.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ..legend_derivation import (
    LegendDerivation,
    LegendDerivationOutcome,
    derive_category_from_regime_legend,
    match_regime_legend,
)
from ..regime_legend import REGIME_LEGENDS, RegimeLegend
from ..schema import IvaCategory

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# The one mention that fixes a category, per art. 6.1.m. Read from the table
# rather than restated, so a change to the regulation's encoding reaches these
# cases instead of leaving them asserting a value the table no longer carries.
_DECLARING = tuple(legend for legend in REGIME_LEGENDS if legend.declares is not None)
_SILENT = tuple(legend for legend in REGIME_LEGENDS if legend.declares is None)


def test_the_table_still_has_exactly_one_declaring_mention() -> None:
    """The premise the rest of this module rests on, asserted rather than assumed.

    If a row is ever added that declares a category, the cases below stop
    describing the table and this says so. Without it a later table change could
    leave the absent-outcome gates passing vacuously.
    """
    assert len(_DECLARING) == 1
    assert len(_SILENT) == 6
    assert _DECLARING[0].declares is IvaCategory.DOMESTIC_REVERSE_CHARGE
    assert _DECLARING[0].expects_repercutido_line is False


def test_the_reverse_charge_mention_derives_the_category_the_regulation_fixes() -> None:
    """Art. 6.1.m: the mention states the operation is reverse-charged."""
    legend = _DECLARING[0]

    derivation = derive_category_from_regime_legend(
        printed_legend=legend.phrase,
        has_repercutido_line=False,
    )

    assert derivation.outcome is LegendDerivationOutcome.DERIVED
    assert derivation.category is IvaCategory.DOMESTIC_REVERSE_CHARGE
    assert derivation.legend is not None
    assert derivation.legend.provision == "art-6.1.m"
    assert derivation.derived_from


def test_a_repercutido_line_beside_the_reverse_charge_mention_is_a_contradiction() -> None:
    """The document disagrees with itself, and neither side wins.

    A reverse-charge invoice charges no Spanish IVA, so a printed cuota beside
    that mention means the mention or the line is wrong. Which one is not
    decidable from the page, so no category is carried.
    """
    derivation = derive_category_from_regime_legend(
        printed_legend=_DECLARING[0].phrase,
        has_repercutido_line=True,
    )

    assert derivation.outcome is LegendDerivationOutcome.CONTRADICTED
    assert derivation.category is None
    assert derivation.legend is not None
    assert derivation.note


@pytest.mark.parametrize("legend", _SILENT, ids=lambda legend: legend.provision)
def test_a_mandated_mention_that_declares_nothing_derives_nothing(legend: RegimeLegend) -> None:
    """Six of seven mentions say nothing about the category, and must stay silent.

    These are real, mandated mentions -- a self-billing arrangement, a special
    regime's accounting -- and the temptation is to read a category out of them
    because they are present and specific. None of them fixes one.
    """
    phrase = legend.phrase

    for has_line in (True, False):
        derivation = derive_category_from_regime_legend(printed_legend=phrase, has_repercutido_line=has_line)
        assert derivation.outcome is LegendDerivationOutcome.ABSENT
        assert derivation.category is None


@pytest.mark.parametrize(
    "printed",
    [None, "", "   ", "Factura simplificada", "operación exenta según art. 20 LIVA"],
    ids=["none", "empty", "blank", "unrelated-text", "exempt-reference"],
)
def test_the_ordinary_invoice_derives_nothing_rather_than_defaulting(printed: str | None) -> None:
    """The anti-default gate, and the one most likely to be pressured.

    Most invoices print no mandated mention. The axis must return ABSENT for all
    of them rather than treating the silence as evidence of ordinary domestic
    supply -- a restrictive provision used as a default silently captures the
    whole population it does not govern, and a wrong category is worse than an
    absent one because an absent one asks the operator.

    The exempt reference is included deliberately: art. 6.1.j fixes no phrase for
    an exempt operation, so there is nothing to match and nothing to derive. That
    absence is the regulation's, not an omission in the table.
    """
    derivation = derive_category_from_regime_legend(printed_legend=printed, has_repercutido_line=True)

    assert derivation.outcome is LegendDerivationOutcome.ABSENT
    assert derivation.category is None
    assert derivation.legend is None


@pytest.mark.parametrize(
    "printed",
    ["INVERSIÓN DEL SUJETO PASIVO", "Inversión Del Sujeto Pasivo", "Operación con inversión del sujeto pasivo."],
    ids=["upper", "title", "embedded-in-a-line"],
)
def test_the_match_is_case_folded_and_survives_surrounding_text(printed: str) -> None:
    """Art. 6.1 fixes the wording, not the typography or the layout."""
    matched = match_regime_legend(printed)

    assert matched is not None
    assert matched.declares is IvaCategory.DOMESTIC_REVERSE_CHARGE


def test_a_paraphrase_is_not_a_mandated_mention() -> None:
    """Loosening the match would derive a regime from words nobody printed.

    The counterpart of the case above: case folding is a typography allowance,
    not a licence to recognise wording the regulation does not fix.
    """
    assert match_regime_legend("el sujeto pasivo se invierte en esta operación") is None


class TestTheRecordCannotMisreportItsOwnState:
    """Each outcome carries exactly what it establishes, enforced at construction."""

    def test_a_derived_outcome_without_a_category_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            LegendDerivation(outcome=LegendDerivationOutcome.DERIVED, derived_from=("regime_legend",))

    def test_a_contradicted_outcome_carrying_a_category_is_refused(self) -> None:
        """A caller holding the value would use it and skip the contradiction."""
        with pytest.raises(ValidationError):
            LegendDerivation(
                outcome=LegendDerivationOutcome.CONTRADICTED,
                legend=_DECLARING[0],
                category=IvaCategory.DOMESTIC_REVERSE_CHARGE,
            )

    def test_an_absent_outcome_carrying_a_legend_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            LegendDerivation(outcome=LegendDerivationOutcome.ABSENT, legend=_DECLARING[0])


def test_the_axis_needs_no_counterparty_facts_at_all() -> None:
    """The reason this axis can run on evidence alone, stated as a check.

    ``classify_iva`` resolves the counterparty-dependent categories and needs
    ``customer_tax_status``, which is a profile fact rather than a document fact.
    This derivation takes only the printed mention and whether a tax line is
    present, so it cannot stray into that table's domain and the two cannot
    silently disagree. A signature change that added a counterparty parameter
    would break that separation, and reddens here.
    """
    import inspect

    parameters = set(inspect.signature(derive_category_from_regime_legend).parameters)

    assert parameters == {"printed_legend", "has_repercutido_line"}
