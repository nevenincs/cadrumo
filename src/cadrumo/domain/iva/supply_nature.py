"""Whether an operation supplies goods or services, and how that may be known.

The place-of-supply rules fork on this axis before they consult anything else: a
supply of goods and a supply of services between the same two parties, for the
same amount, on the same day, are located by different articles and can carry
different treatments. So the axis has to be established before origin and
destination mean anything.

**It is evidence or it is unknown.** The nature of a supply is not derivable from
the numbers on an invoice, and it is not derivable from the words describing the
lines. A rule table over free-prose line descriptions -- "consultoría" implies
services, "material" implies goods -- is a model wearing a lookup table: it
produces a confident answer on the population it was written against and an
unmarked wrong answer everywhere else, and nothing downstream can tell the two
apart. There is no such table here and there must not be one.

**One derivation is sanctioned, because it decides by law rather than by prose.**
RD 1619/2012 art. 6.1.j obliges an issuer to print a reference to the provision
granting an exemption, so an exempt invoice carries a statutory citation. An
article number is a closed legal vocabulary: it is anchorable, and what it
establishes is fixed by the statute rather than inferred from the sentence around
it. LIVA art. 25 is an exemption for *entregas de bienes*; art. 163 octiesdecies
is a regime for *prestaciones de servicios*. Reading the number and consulting
what that article says is a lookup, not an inference.

This axis is the one the printed-mention vocabulary documents itself as unable to
serve. That vocabulary matches the fixed *menciones* art. 6.1 sets as literal
phrases, and it records that art. 6.1.j fixes no phrase at all -- an exempt
invoice prints whichever article applies, so there is no canonical string to
match. The citation is the thing it prints instead, and this module reads it.

**Every row is grounded in the bundled consolidated text, and two rows establish
nothing.** LIVA art. 84 fixes who the taxable person is, and its own first
paragraph reaches "las entregas de bienes o presten los servicios" -- both limbs,
so a reverse charge says nothing about which. Art. 163 unvicies is the Union
scheme and likewise covers "presten servicios" alongside "ventas a distancia
intracomunitarias de bienes". Both are carried as rows that establish ``None``
rather than omitted, because a caller that finds no row cannot tell "this article
does not fix the nature" from "nobody has added this article yet".

**The requirement is lazy.** :func:`supply_nature_is_required` is the whole of the
demand, and it is narrow on purpose. A domestic operation between established
parties at a registry rate is treated identically whether it supplies goods or
services, so asking for the distinction there would block an invoice on a fact its
own treatment does not depend on.

See Also:
    :class:`~domain.iva.IvaCategory`
        The catalogue whose cross-border members fork on this axis.
    :data:`~domain.iva.REGIME_LEGENDS`
        The fixed phrases art. 6.1 mandates, which the sibling axis matches. The
        citation this module reads is what art. 6.1.j obliges instead, for the
        exempt operations that vocabulary deliberately does not cover.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Final, Self

from pydantic import BaseModel, Field, model_validator

from ...core import STRICT_FROZEN_CONFIG
from .schema import IvaCategory

__all__ = [
    "LIVA_CITATION_QUALIFIERS",
    "STATUTORY_CITATIONS",
    "StatutoryCitation",
    "SupplyNature",
    "SupplyNatureDerivation",
    "SupplyNatureDerivationOutcome",
    "derive_supply_nature_from_citation",
    "match_statutory_citations",
    "supply_nature_implied_by_category",
    "supply_nature_is_required",
]


class SupplyNature(StrEnum):
    """What an operation supplies.

    Two members and no ``UNKNOWN``. Not knowing is a property of a *derivation*,
    carried by :class:`SupplyNatureDerivation`'s absent outcome, not a third kind
    of supply. A member meaning "we could not tell" is storable, and once stored
    it is indistinguishable from a fact at every later reader.
    """

    GOODS = "goods"
    """A supply of goods (*entrega de bienes*)."""

    SERVICES = "services"
    """A supply of services (*prestación de servicios*)."""


class StatutoryCitation(BaseModel):
    """One LIVA article an invoice may cite, and what citing it establishes.

    Attributes:
        article: The article number as the statute numbers it, including any
            ordinal suffix (``"163 octiesdecies"``). Matched case-folded and
            whitespace-tolerantly, never as a bare substring.
        heading: The article's own rubric, quoted from the bundled consolidated
            text, so the row can be checked against the corpus by reading it.
        corpus_ref: The bundled file the heading was quoted from, optionally
            with the ``#anchor`` of one article within it. An anchor is what
            lets a row cite a consolidated document: without it the check reads
            the whole file, and a law carrying both limbs makes every row citing
            it look mixed.
        establishes: The nature citing this article fixes, or ``None`` when the
            article governs goods and services alike. ``None`` is a finding about
            the statute, not a gap in the table.
    """

    model_config = STRICT_FROZEN_CONFIG

    article: str = Field(min_length=1)
    heading: str = Field(min_length=1)
    corpus_ref: str = Field(min_length=1)
    establishes: SupplyNature | None = None


LIVA_CITATION_QUALIFIERS: Final[tuple[str, ...]] = (
    "37/1992",
    "liva",
    "ley del iva",
    "ley iva",
    "impuesto sobre el valor añadido",
)
"""Tokens that identify a citation as naming the IVA law rather than another one.

A bare article number is meaningless without its statute. Art. 21 of Ley 27/1992
is an IVA export exemption; art. 21 of Ley 27/2014 is a corporate-income
provision, and this repository bundles the text of both. Requiring one of these
qualifiers somewhere in the cited text is what stops the axis reading an article
number out of the wrong namespace -- the failure that makes a wrong answer look
exactly like a right one.
"""


STATUTORY_CITATIONS: Final[tuple[StatutoryCitation, ...]] = (
    StatutoryCitation(
        article="21",
        heading="Exenciones en las exportaciones de bienes.",
        corpus_ref="corpus/normatives/html/ley-37-1992-art-21.html",
        establishes=SupplyNature.GOODS,
    ),
    StatutoryCitation(
        article="25",
        heading="Exenciones en las entregas de bienes destinados a otro Estado miembro.",
        corpus_ref="corpus/normatives/html/ley-37-1992-art-25.html",
        establishes=SupplyNature.GOODS,
    ),
    StatutoryCitation(
        article="15",
        heading="Concepto de adquisición intracomunitaria de bienes.",
        corpus_ref="corpus/normatives/html/ley-37-1992-art-15.html",
        establishes=SupplyNature.GOODS,
    ),
    StatutoryCitation(
        article="163 quinvicies",
        heading="Ámbito de aplicación.",
        corpus_ref="corpus/normatives/html/ley-37-1992-art-163-quinvicies.html",
        establishes=SupplyNature.GOODS,
    ),
    StatutoryCitation(
        article="163 octiesdecies",
        heading="Ámbito de aplicación.",
        corpus_ref="corpus/normatives/html/ley-37-1992-art-163-octiesdecies.html",
        establishes=SupplyNature.SERVICES,
    ),
    StatutoryCitation(
        article="68",
        heading="Lugar de realización de las entregas de bienes.",
        corpus_ref="corpus/normatives/html/ley-37-1992.html#a68",
        establishes=SupplyNature.GOODS,
    ),
    StatutoryCitation(
        article="69",
        heading="Lugar de realización de las prestaciones de servicios. Reglas generales.",
        corpus_ref="corpus/normatives/html/ley-37-1992.html#a69",
        establishes=SupplyNature.SERVICES,
    ),
    StatutoryCitation(
        article="70",
        heading="Lugar de realización de las prestaciones de servicios. Reglas especiales.",
        corpus_ref="corpus/normatives/html/ley-37-1992.html#a70",
        establishes=SupplyNature.SERVICES,
    ),
    StatutoryCitation(
        article="84",
        heading="Sujetos pasivos.",
        corpus_ref="corpus/normatives/html/ley-37-1992-art-84.html",
        establishes=None,
    ),
    StatutoryCitation(
        article="163 unvicies",
        heading="Ámbito de aplicación.",
        corpus_ref="corpus/normatives/html/ley-37-1992-art-163-unvicies.html",
        establishes=None,
    ),
)
"""Every LIVA article this axis can read, and what each one establishes.

Two shapes of ``corpus_ref`` appear here, and the difference is bookkeeping
rather than authority. A row citing a per-article bundled file names that file;
a row citing an article of the consolidated law names the file and the article's
anchor. Both resolve to exactly one article, which is the property that matters:
a row whose check could reach the whole IVA law would see the goods limb and the
services limb alike and could only ever establish nothing.

**Art. 22 is deliberately absent, and not for that reason.** Assimilated exports
are bundled as their own file, so scoping is not the obstacle. Its opening
enumerates operation kinds -- "las entregas, construcciones, transformaciones,
reparaciones, mantenimiento, fletamento ... y arrendamiento" -- without naming
either limb, so the check cannot read what it establishes from the article
itself. Which limbs it reaches IS decidable, but only by consulting arts. 8 and
11, where the statute defines the two limbs; until the check does that, no row
can be declared honestly. Typing the answer in directly would be the paraphrase
this table exists to avoid.

What the table reaches is therefore the *exemption*, *special regime* and
*place-of-supply* citations an invoice prints, which is the population art. 6.1.j
obliges to print a reference at all. An ordinary cross-border invoice citing
nothing derives nothing and asks the operator, which is the designed outcome
rather than a failure.
"""


def _citation_pattern(article: str) -> re.Pattern[str]:
    """Compile the article-reference matcher for one row.

    Requires an article-reference word before the number, so a bare figure in an
    amount or a date cannot match, and a word boundary after it, so ``25`` does
    not match inside ``250``. Ordinal suffixes are matched as whole words for the
    same reason: ``163 vicies`` must not match inside ``163 quinvicies``.

    No suffixed article is also declared bare, so a bare number needs no
    lookahead barring a suffix after it. Adding one would be actively wrong:
    ``art. 21 LIVA`` puts a word right after the number, and refusing that would
    reject the qualifier the match requires elsewhere.
    """
    parts = article.split()
    number = re.escape(parts[0])
    tail = "".join(rf"\s+\b{re.escape(part)}\b" for part in parts[1:])
    return re.compile(
        rf"\bart(?:\.|s\.|ículos?|icles?)?\s*{number}\b{tail}",
        re.IGNORECASE,
    )


_CITATION_PATTERNS: Final[tuple[tuple[StatutoryCitation, re.Pattern[str]], ...]] = tuple(
    (citation, _citation_pattern(citation.article)) for citation in STATUTORY_CITATIONS
)


class SupplyNatureDerivationOutcome(StrEnum):
    """What the citation axis was able to conclude.

    Closed, and without a "probable" member for the same reason the legend axis
    has none: there is no honest threshold between "the issuer cited this article"
    and "the issuer did not".
    """

    DERIVED = "derived"
    """Exactly one nature is established by the articles the document cites."""

    CONTRADICTED = "contradicted"
    """The document cites articles that establish different natures.

    Reported rather than resolved. An invoice citing both a goods exemption and a
    services regime is internally inconsistent, and which citation is the mistake
    is not decidable from the page.
    """

    ABSENT = "absent"
    """Nothing to derive from, and the ordinary outcome.

    No citation printed, no LIVA qualifier beside it, or only articles that
    establish nothing. Most invoices legitimately land here; a domestic invoice is
    obliged to cite no article at all.
    """


class SupplyNatureDerivation(BaseModel):
    """The citation axis's conclusion about one document.

    Attributes:
        outcome: Which of the three states applies.
        nature: The established nature, set only on ``DERIVED``. Deliberately
            ``None`` on ``CONTRADICTED``: carrying one of two disagreeing values
            would let a caller use it while ignoring the disagreement.
        citations: The matched articles, in declaration order. Populated whenever
            anything matched, including the rows that establish nothing, so a
            caller can cite what it read.
        note: Operator-facing explanation, populated on ``CONTRADICTED``.
    """

    model_config = STRICT_FROZEN_CONFIG

    outcome: SupplyNatureDerivationOutcome
    nature: SupplyNature | None = None
    citations: tuple[StatutoryCitation, ...] = ()
    note: str = ""

    @model_validator(mode="after")
    def _each_outcome_carries_exactly_what_it_claims(self) -> Self:
        """Refuse a record whose payload does not match the state it reports."""
        if self.outcome is SupplyNatureDerivationOutcome.DERIVED:
            if self.nature is None:
                raise ValueError("a derived outcome must carry the nature it established")
            if not self.citations:
                raise ValueError("a derived outcome must record the citations it followed from")
        elif self.outcome is SupplyNatureDerivationOutcome.CONTRADICTED:
            if self.nature is not None:
                raise ValueError(
                    "a contradicted outcome must not carry a nature: the document disagrees with itself, "
                    "and a caller holding the value would use it without the contradiction",
                )
            if len(self.citations) < 2:
                raise ValueError("a contradicted outcome must carry the citations that disagreed")
        elif self.nature is not None:
            raise ValueError("an absent outcome establishes nothing, so it carries no nature")
        return self


#: Named so the absent outcome reads as a decision rather than a fall-through.
_NOTHING_DERIVED: Final = SupplyNatureDerivation(outcome=SupplyNatureDerivationOutcome.ABSENT)


def match_statutory_citations(printed: str | None) -> tuple[StatutoryCitation, ...]:
    """Return every declared LIVA article *printed* cites, in declaration order.

    Matching requires two things together: an article reference for one of the
    declared numbers, and a token from :data:`LIVA_CITATION_QUALIFIERS` somewhere
    in the same text. Requiring the qualifier is what keeps the axis inside the
    IVA law's namespace; an article number alone names an article of whichever
    statute the reader assumed.

    Args:
        printed: Text transcribed from the document -- the regime mention, or
            whatever line carries the citation -- or ``None``.

    Returns:
        The matching rows, possibly empty. Rows that establish nothing are
        included: they were genuinely cited, and a caller reporting what it read
        needs them.
    """
    if printed is None:
        return ()
    folded = printed.casefold()
    if not folded.strip():
        return ()
    if not any(qualifier in folded for qualifier in LIVA_CITATION_QUALIFIERS):
        return ()
    return tuple(citation for citation, pattern in _CITATION_PATTERNS if pattern.search(printed))


def derive_supply_nature_from_citation(*, printed_citation: str | None) -> SupplyNatureDerivation:
    """Derive the nature of the supply from the articles the document cites.

    The whole axis. Citations are matched against the closed statutory vocabulary;
    the natures those articles establish are collected; and a value is derived only
    when they agree on exactly one.

    Args:
        printed_citation: Text transcribed from the document, or ``None``.

    Returns:
        :class:`SupplyNatureDerivation`: One of the three outcomes, carrying
        exactly what that outcome establishes.
    """
    citations = match_statutory_citations(printed_citation)
    if not citations:
        return _NOTHING_DERIVED
    natures = {citation.establishes for citation in citations if citation.establishes is not None}
    if not natures:
        # Every cited article governs both limbs. A real citation that fixes
        # nothing, which is a different fact from no citation at all -- so the
        # rows ride along even though the outcome is absent.
        return SupplyNatureDerivation(
            outcome=SupplyNatureDerivationOutcome.ABSENT,
            citations=citations,
        )
    if len(natures) > 1:
        cited = ", ".join(f"art. {citation.article}" for citation in citations)
        return SupplyNatureDerivation(
            outcome=SupplyNatureDerivationOutcome.CONTRADICTED,
            citations=citations,
            note=(
                f"the document cites articles that establish different natures of supply ({cited}); "
                "which citation is the mistake is not decidable from the document"
            ),
        )
    return SupplyNatureDerivation(
        outcome=SupplyNatureDerivationOutcome.DERIVED,
        nature=natures.pop(),
        citations=citations,
    )


#: Separates the norm from its article in a component-table legal reference,
#: as in ``ley-37-1992:art-25``. Named because this module and the table it
#: reads must agree on it exactly, and a literal spelled twice drifts silently.
_ARTICLE_REFERENCE_SEPARATOR: Final[str] = ":art-"


def supply_nature_implied_by_category(category: IvaCategory | None) -> SupplyNatureDerivation:
    """Derive the nature from the articles the CATEGORY itself rests on.

    The second route to the same answer, and it needs no citation printed on the
    page: a category is grounded in specific LIVA articles, and some of those
    articles define the operation as one of goods. An *entrega intracomunitaria*
    is exempt under art. 25, which exempts "las entregas de bienes definidas en
    el artículo 8" -- so an operator asked goods-or-services about one is being
    asked a question the law has already answered.

    **Two existing authorities, joined; no third judgement.** Which articles
    ground a category is already declared once, in the component table's
    ``legal_refs``. What an article establishes about the nature is already
    declared once, in :data:`STATUTORY_CITATIONS`, each row carrying its
    ``corpus_ref``. This walks from one to the other and rules on nothing
    itself, which is what keeps a second category-keyed table -- a rival
    authority on one question -- from existing.

    **The dangerous case excludes itself, and that is the design rather than
    luck.** LIVA art. 22, assimilated exports, covers "las entregas,
    construcciones, transformaciones, reparaciones, mantenimiento, fletamento...
    y arrendamiento": services as much as goods. A hand-written map over the
    export family would have asserted GOODS on service exports. Art. 22 has no
    row in the citation table because nothing ever ruled what it establishes, so
    the join finds nothing and the category stays open.

    Measured over the shipped tables: the three goods families derive GOODS --
    intra-community supply and export via arts. 25 and 21, intra-community
    acquisition via art. 15 -- and the two SERVICE members derive SERVICES via
    the general place-of-supply rules 69 and 70. The services half arrived
    entirely through the citation table: nothing here changed to admit it, which
    is the join working as intended.

    Args:
        category: The category the document declared, or ``None``.

    Returns:
        :class:`SupplyNatureDerivation`: One of the three outcomes, carrying
        exactly what that outcome establishes. ``ABSENT`` whenever the category
        is unknown, ungrounded, or grounded only in articles that fix nothing.
    """
    if category is None:
        return _NOTHING_DERIVED

    citations = _category_supply_nature_citations(category)
    if not citations:
        return _NOTHING_DERIVED

    return _category_supply_nature_derivation(category, citations)


def _category_supply_nature_citations(category: IvaCategory) -> tuple[StatutoryCitation, ...]:
    """Join a category's declared legal refs to the closed citation vocabulary."""
    # Imported at call time: the component table reaches the schema and the
    # classification modules, so a module-scope import would make this lean
    # module pay for them. The sanctioned cycle-break shape, and it changes only
    # WHEN the owning module executes.
    from .components import IVA_CATEGORY_COMPONENTS

    grounding = {
        reference
        for key, components in IVA_CATEGORY_COMPONENTS.items()
        # The table is keyed per category AND direction, and the nature is a
        # property of the supply rather than of who filed it -- so every row for
        # this category contributes, whichever way the document ran.
        if key[0] is category
        for reference in components.legal_refs
    }
    articles = {
        reference.split(_ARTICLE_REFERENCE_SEPARATOR, 1)[1]
        for reference in grounding
        if _ARTICLE_REFERENCE_SEPARATOR in reference
    }
    return tuple(citation for citation in STATUTORY_CITATIONS if citation.article in articles)


def _category_supply_nature_derivation(
    category: IvaCategory,
    citations: tuple[StatutoryCitation, ...],
) -> SupplyNatureDerivation:
    natures = {citation.establishes for citation in citations if citation.establishes is not None}
    if not natures:
        return SupplyNatureDerivation(
            outcome=SupplyNatureDerivationOutcome.ABSENT,
            citations=citations,
        )
    if len(natures) > 1:
        grounded = ", ".join(f"art. {citation.article}" for citation in citations)
        return SupplyNatureDerivation(
            outcome=SupplyNatureDerivationOutcome.CONTRADICTED,
            citations=citations,
            note=(
                f"the {category.value!r} category is grounded in articles that establish different "
                f"natures of supply ({grounded}); the category cannot settle which"
            ),
        )
    return SupplyNatureDerivation(
        outcome=SupplyNatureDerivationOutcome.DERIVED,
        nature=natures.pop(),
        citations=citations,
    )


#: The categories whose treatment does not fork on the nature of the supply.
#:
#: Every domestic member. A domestic supply between established parties is taxed
#: at its registry rate, and that rate is settled by the rate tier rather than by
#: whether the thing supplied was a good or a service -- so demanding the
#: distinction here would block an invoice on a fact its own treatment ignores.
#: The reverse-charge member is deliberately NOT in this set: art. 84's sub-rules
#: reach specific supplies, and it is the one domestic member where the law looks.
_NATURE_INDIFFERENT_CATEGORIES: Final[frozenset[IvaCategory]] = frozenset(
    {
        IvaCategory.DOMESTIC_GENERAL,
        IvaCategory.DOMESTIC_REDUCED,
        IvaCategory.DOMESTIC_SUPER_REDUCED,
        IvaCategory.DOMESTIC_ZERO,
        IvaCategory.DOMESTIC_EXEMPT,
        IvaCategory.DOMESTIC_NOT_SUBJECT,
    },
)


def supply_nature_is_required(category: IvaCategory | None) -> bool:
    """Whether resolving this operation needs the nature of the supply.

    The laziness rule, in one place so it cannot be answered differently at two
    call sites. The distinction is demanded on the branches where the law forks on
    it -- the cross-border members, and the domestic reverse charge -- and not on
    the domestic members that are settled by their rate tier.

    Args:
        category: The category under consideration, or ``None`` when none has been
            established yet.

    Returns:
        ``True`` when the nature must be known before the operation can be
        resolved. ``None`` returns ``True``: an operation whose category is still
        open may yet land on a forking branch, and answering ``False`` there would
        skip the question for exactly the invoices that have not been placed.
    """
    if category is None:
        return True
    return category not in _NATURE_INDIFFERENT_CATEGORIES
