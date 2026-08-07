"""Deriving an IVA category from the regime mention the issuer printed.

The narrowest axis of the deterministic classifier, and the only one that needs
nothing but the document. Spanish law does not leave the regime of an operation
to be inferred: RD 1619/2012 art. 6.1 obliges the issuer to print a fixed
*mención* whenever certain regimes apply, so for those cases the paper states the
regime in words the regulation itself sets. Copying a printed phrase is something
a reading stage may do; concluding what that phrase declares is something
deterministic code may do. Neither step guesses.

**Why this axis rather than the full rule table.**
:func:`~domain.iva.classify_iva` already exists and is the single classifier for
this domain; nothing here duplicates or competes with it. That table resolves the
categories that depend on WHO the counterparty is -- their tax status and
residency -- and ``customer_tax_status`` is a profile fact rather than a document
fact, which is exactly why it cannot be derived from evidence alone. The legend
axis needs neither input. It reports only what the issuer themselves declared in
writing, so it never enters that table's domain and the two cannot silently
disagree.

**Three outcomes, and "probably" is not one.** A legend is present and consistent
with the tax evidence on the page, or it contradicts that evidence, or there is
nothing to derive from. No score, no ranking, no numeric confidence anywhere:
those exist to let a caller pick a threshold, and there is no honest threshold
between "the issuer declared this" and "the issuer did not".

**The absent outcome is the common one, and it must stay that way.**
:data:`~domain.iva.REGIME_LEGENDS` has seven rows and exactly one declares a
category, because that is the measured state of the regulation rather than an
unfinished table. Most invoices legitimately derive nothing here. The pressure to
close that gap with a default -- treating an unstated counterparty country as
domestic, or a legend-less invoice as ordinary domestic supply -- is the
restrictive-provision-as-default trap: it silently captures the whole population
the provision does not govern. **A wrong category is worse than an absent one**,
because an absent category asks the operator and a wrong one does not.

**The exempt case cannot be derived here at all.** Art. 6.1.j fixes no phrase for
an exempt operation; it requires a reference to the provision granting the
exemption, so an exempt invoice prints whichever article applies and no canonical
string exists to match. That absence is load-bearing and is documented on
:data:`~domain.iva.REGIME_LEGENDS`.

See Also:
    :class:`~domain.iva.RegimeLegend`
        The statutory mention this module reads, and its declared expectations.
    :class:`~domain.iva.IvaCategory`
        The closed catalogue a legend resolves into.
    :func:`~domain.iva.classify_iva`
        The counterparty-dependent rule table this axis deliberately stays out of.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final, Self

from pydantic import BaseModel, model_validator

from ...core import STRICT_FROZEN_CONFIG
from ._regime_legend import REGIME_LEGENDS, RegimeLegend
from ._schema import IvaCategory

__all__ = [
    "LegendDerivation",
    "LegendDerivationOutcome",
    "derive_category_from_regime_legend",
    "match_regime_legend",
]


class LegendDerivationOutcome(StrEnum):
    """What the legend axis was able to conclude.

    Closed, and deliberately without a "probable" member. The axis either has the
    issuer's own written declaration or it does not.
    """

    DERIVED = "derived"
    """A legend declared a category and the printed tax evidence agrees with it."""

    CONTRADICTED = "contradicted"
    """A legend declared a category the printed tax evidence contradicts.

    Reported rather than resolved. The document is internally inconsistent, and
    picking whichever side looks more likely would erase the one signal that says
    so. Turning this into an operator-facing blocking finding belongs to the
    review path, not here.
    """

    ABSENT = "absent"
    """Nothing to derive from: no legend printed, or one that declares no category.

    The expected outcome for most invoices. Six of the seven mandated mentions
    declare no category, and an invoice printing none at all is entirely ordinary.
    """


class LegendDerivation(BaseModel):
    """The legend axis's conclusion about one document.

    Attributes:
        outcome: Which of the three states applies.
        category: The declared category, set only on ``DERIVED``. Deliberately
            ``None`` on ``CONTRADICTED``: the legend named a category, but the
            page disagrees with itself, and carrying the value anyway would let a
            caller use it while ignoring the contradiction.
        legend: The matched mention, on ``DERIVED`` and ``CONTRADICTED`` alike.
            Carries the ``provision`` so a value derived here can cite the
            article that put the phrase on the page.
        derived_from: The inputs this conclusion followed from, named so the
            derivation can be reproduced by hand. Recorded in place of a printed
            anchor, because a derived value has none.
        note: Operator-facing explanation, populated on ``CONTRADICTED`` to say
            what disagreed with what.
    """

    model_config = STRICT_FROZEN_CONFIG

    outcome: LegendDerivationOutcome
    category: IvaCategory | None = None
    legend: RegimeLegend | None = None
    derived_from: tuple[str, ...] = ()
    note: str = ""

    @model_validator(mode="after")
    def _each_outcome_carries_exactly_what_it_claims(self) -> Self:
        """Refuse a record whose payload does not match the state it reports.

        Each outcome is a different claim about the evidence, and a payload that
        does not fit its state is how a caller ends up reading a category off a
        record that did not establish one.
        """
        if self.outcome is LegendDerivationOutcome.DERIVED:
            if self.category is None or self.legend is None:
                raise ValueError("a derived outcome must carry both the category and the legend that declared it")
            if not self.derived_from:
                raise ValueError("a derived outcome must record the inputs it followed from")
        elif self.outcome is LegendDerivationOutcome.CONTRADICTED:
            if self.legend is None:
                raise ValueError("a contradicted outcome must carry the legend that was contradicted")
            if self.category is not None:
                raise ValueError(
                    "a contradicted outcome must not carry a category: the document disagrees with itself, "
                    "and a caller holding the value would use it without the contradiction",
                )
        elif self.category is not None or self.legend is not None:
            raise ValueError("an absent outcome derives nothing, so it carries neither a category nor a legend")
        return self


#: Named so the absent outcome reads as a decision rather than a fall-through.
_NOTHING_DERIVED: Final = LegendDerivation(outcome=LegendDerivationOutcome.ABSENT)


def match_regime_legend(printed: str | None) -> RegimeLegend | None:
    """Return the mandated mention *printed* contains, or ``None``.

    Matching is case-folded because art. 6.1 fixes the wording rather than the
    typography, and documents print the mentions in capitals, title case and
    sentence case alike. Nothing else is normalised: a phrase the regulation does
    not fix is not a mandated mention, and loosening the match to catch
    paraphrases would derive a regime from words the issuer did not print.

    Containment rather than equality, because the mention is printed as a line on
    an invoice among other text, and the reading stage is instructed to copy the
    phrase but may carry surrounding punctuation with it.

    Args:
        printed: The phrase transcribed from the document, or ``None``.

    Returns:
        The matching :class:`~domain.iva.RegimeLegend`, or ``None`` when the text
        is absent, blank, or contains no mandated mention.
    """
    if printed is None:
        return None
    folded = printed.casefold()
    if not folded.strip():
        return None
    for legend in REGIME_LEGENDS:
        if legend.phrase.casefold() in folded:
            return legend
    return None


def derive_category_from_regime_legend(
    *,
    printed_legend: str | None,
    has_repercutido_line: bool,
) -> LegendDerivation:
    """Derive the IVA category the issuer declared in writing, if any.

    The whole axis. A mention is matched against the closed statutory vocabulary;
    if it declares a category, the declaration is checked against the tax evidence
    the page actually carries, and only an agreeing pair derives a value.

    The check is possible because :class:`~domain.iva.RegimeLegend` already states
    per mention whether an invoice printing it should carry a repercutido rate and
    cuota. A "inversión del sujeto pasivo" invoice charges no Spanish IVA, so a
    repercutido line beside that mention means one of the two is wrong -- and
    which one is not decidable from the page. Reporting the disagreement keeps
    that visible; averaging over it would not.

    Args:
        printed_legend: The mention transcribed from the document, or ``None``.
        has_repercutido_line: Whether the document carries a repercutido rate and
            cuota. Passed in as an already-established fact rather than recomputed
            here: what counts as a printed tax line is the reading stage's
            business, and re-deciding it here would be a second authority on it.

    Returns:
        :class:`LegendDerivation`: One of the three outcomes, carrying exactly
        what that outcome establishes.
    """
    legend = match_regime_legend(printed_legend)
    if legend is None or legend.declares is None:
        # Six of the seven mandated mentions declare no category, so this is the
        # ordinary path rather than a failure. It stays ABSENT rather than
        # acquiring a domestic default: the mentions that declare nothing are
        # obligations about the billing arrangement or a special regime's
        # accounting, and none fixes the operation's category on its own.
        return _NOTHING_DERIVED

    inputs = ("regime_legend", "iva_rate", "iva_amount")
    if legend.expects_repercutido_line != has_repercutido_line:
        expected = "a repercutido rate and cuota" if legend.expects_repercutido_line else "no repercutido line"
        observed = "one is printed" if has_repercutido_line else "none is printed"
        return LegendDerivation(
            outcome=LegendDerivationOutcome.CONTRADICTED,
            legend=legend,
            derived_from=inputs,
            note=(
                f"the document prints the mention {legend.phrase!r} ({legend.provision}), which expects "
                f"{expected}, but {observed}; the document disagrees with itself and the category cannot "
                "be taken from either side"
            ),
        )
    return LegendDerivation(
        outcome=LegendDerivationOutcome.DERIVED,
        category=legend.declares,
        legend=legend,
        derived_from=inputs,
    )
