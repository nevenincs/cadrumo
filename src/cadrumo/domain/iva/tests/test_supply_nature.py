"""The nature of a supply is read from a citation or it is unknown.

Two properties carry this module. The first is that every row of the citation
table says what the bundled consolidated text says -- checked by reading the
corpus file the row names, not by restating the row. The second is that nothing
else derives: prose describing the lines, the amounts, and the rate all leave the
axis absent, because none of them is evidence of what was supplied.

The table is deliberately checked against the corpus rather than against a
hand-written expectation. An expectation copied from the row under test would
pass whatever the row said, which is the tautology this domain's rules single
out: the test must be able to fail if the row is wrong about the statute.

See Also:
    :class:`~domain.iva.IvaCategory`
        The catalogue whose members decide whether this axis is demanded at all.
"""

from __future__ import annotations

import re

import pytest

from ....core import resolve_anchored_extracted_unit
from ....core.resources import bundled_path
from ..schema import IvaCategory
from ..supply_nature import (
    LIVA_CITATION_QUALIFIERS,
    STATUTORY_CITATIONS,
    StatutoryCitation,
    SupplyNature,
    SupplyNatureDerivationOutcome,
    derive_supply_nature_from_citation,
    match_statutory_citations,
    supply_nature_implied_by_category,
    supply_nature_is_required,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# Resolved through the same bundled-data boundary production reads the corpus
# by, rather than by counting parent directories from this file. Path arithmetic
# would go stale the moment the module moves, and it silently resolves to a
# directory that does not exist rather than saying so.
_BUNDLED_ROOT = bundled_path()

# Words the statute itself uses for each limb. The check below reads the bundled
# article and asks which limbs its rubric and opening reach; these are the tokens
# that answer that, not a paraphrase of the row under test.
#
# ``de bienes`` carries most of the goods side on purpose: the statute reaches
# that limb through several constructions -- entregas, exportaciones,
# adquisiciones intracomunitarias, ventas a distancia -- and enumerating them
# invites a row whose article uses a form nobody listed to pass unchecked. The
# services tokens stay explicit because ``servicios`` alone appears in
# definitions that do not scope the article.
_GOODS_WORDS = ("de bienes",)
_SERVICES_WORDS = ("presten servicios", "prestaciones de servicios", "prestación de servicios")

#: The articles that DEFINE each limb, used to prove the vocabulary above is the
#: statute's rather than this file's. Their rubrics are "Concepto de entrega de
#: bienes" and "Concepto de prestación de servicios".
_GOODS_DEFINITION_REF = "corpus/normatives/html/ley-37-1992.html#a8"
_SERVICES_DEFINITION_REF = "corpus/normatives/html/ley-37-1992.html#a11"

#: Assimilated exports, bundled as its own file and deliberately not a row.
_ASSIMILATED_EXPORTS_REF = "corpus/normatives/html/ley-37-1992-art-22.html"


def _bundled_text(corpus_ref: str) -> str:
    """Return the cited text, scoped to one article whenever the row names an anchor.

    An anchored ``corpus_ref`` resolves to that single extracted unit through the
    same core resolver the registry's evidence validator reads citations by, so
    an article is read here the way it is read everywhere else in the tree.

    Scoping is what lets a row cite a consolidated document at all. Reading the
    whole of the IVA law reaches the goods limb and the services limb alike, so
    every row citing it would look mixed and could only ever establish nothing --
    which is exactly why the general place-of-supply articles could not be
    declared while the reader was file-scoped.
    """
    path_text, separator, anchor = corpus_ref.partition("#")
    if not separator:
        path = _BUNDLED_ROOT / f"{path_text}.extracted.md"
        assert path.is_file(), f"the row names a corpus file that is not bundled: {corpus_ref}"
        return path.read_text(encoding="utf-8", errors="replace").casefold()

    sidecar = _BUNDLED_ROOT / f"{path_text}.extracted.json"
    assert sidecar.is_file(), f"the row names a corpus sidecar that is not bundled: {corpus_ref}"
    # ``include_title`` carries the article's own rubric, which is where the
    # statute names the limb most plainly -- "Lugar de realización de las
    # entregas de bienes" against "... de las prestaciones de servicios".
    return resolve_anchored_extracted_unit(sidecar, anchor=anchor, include_title=True).casefold()


def _assert_row_matches_its_article(citation: StatutoryCitation) -> None:
    """Read the corpus and confirm the row's claim survives contact with it.

    The three cases the statute produces, each checked on the article's own
    words: an article reaching only the goods limb must establish ``GOODS``, only
    the services limb ``SERVICES``, and one reaching both must establish nothing.

    Extracted from the parametrized case so a proof can drive it with a row that
    is deliberately wrong. A gate nothing can fail is not a gate.
    """
    text = _bundled_text(citation.corpus_ref)

    # Bounded to the opening of the article, where the rubric and the scoping
    # paragraph state what it governs. A long article mentions the other limb
    # incidentally further down, and reading the whole of it would make every row
    # look mixed.
    opening = text[:1200]
    reaches_goods = any(word in opening for word in _GOODS_WORDS)
    reaches_services = any(word in opening for word in _SERVICES_WORDS)
    assert reaches_goods or reaches_services, "the bundled opening names neither limb; the row cannot be checked"

    establishes = citation.establishes
    if reaches_goods and reaches_services:
        assert establishes is None, (
            "the bundled article reaches both the goods and the services limb, so citing it "
            "cannot fix the nature of the supply"
        )
    elif reaches_goods:
        assert establishes is SupplyNature.GOODS
    else:
        assert establishes is SupplyNature.SERVICES


@pytest.mark.parametrize("citation", STATUTORY_CITATIONS, ids=lambda c: c.article)
def test_every_row_says_what_the_bundled_article_says(citation: StatutoryCitation) -> None:
    """Every shipped row, against the text it cites.

    This is what makes the table falsifiable. Asserting the row against a literal
    typed here would restate it; asserting it against the text the row cites can
    fail when the row is wrong, which is the only version worth running.
    """
    _assert_row_matches_its_article(citation)


def test_a_row_claiming_the_wrong_limb_at_its_anchor_is_refused() -> None:
    """The mutation proof: the gate reds on a row the statute contradicts.

    Art. 69 governs *prestaciones de servicios* and this row claims it fixes
    goods. Nothing about the row's own fields is inconsistent -- only the corpus
    says otherwise -- so a green here would mean the check had stopped reading
    the article and every row above was passing on its own say-so.
    """
    wrong = StatutoryCitation(
        article="69",
        heading="Lugar de realización de las prestaciones de servicios. Reglas generales.",
        corpus_ref="corpus/normatives/html/ley-37-1992.html#a69",
        establishes=SupplyNature.GOODS,
    )

    with pytest.raises(AssertionError):
        _assert_row_matches_its_article(wrong)


def test_the_limb_vocabulary_is_the_statutes_own_words() -> None:
    """The tokens the whole check turns on, checked against the law that fixes them.

    Every row above is decided by whether one of these phrases appears in an
    article's opening, so a token this file invented would decide real rows on a
    word the statute never uses -- and nothing else in the suite would notice,
    because every case would agree with the same invention.

    Two claims. Each token occurs verbatim in the bundled IVA law, so none is a
    paraphrase. And each limb's vocabulary is anchored in the article that
    DEFINES that limb: art. 8 for *entrega de bienes*, art. 11 for *prestación
    de servicios*.
    """
    whole_law = _bundled_text("corpus/normatives/html/ley-37-1992.html")
    for word in (*_GOODS_WORDS, *_SERVICES_WORDS):
        assert word in whole_law, f"{word!r} appears nowhere in the bundled law, so it is this file's word"

    goods_definition = _bundled_text(_GOODS_DEFINITION_REF)
    services_definition = _bundled_text(_SERVICES_DEFINITION_REF)

    assert any(word in goods_definition for word in _GOODS_WORDS), (
        "no goods token appears in art. 8, the article that defines the goods limb"
    )
    assert any(word in services_definition for word in _SERVICES_WORDS), (
        "no services token appears in art. 11, the article that defines the services limb"
    )


def test_assimilated_exports_still_cannot_be_read_from_its_own_words() -> None:
    """Why art. 22 has no row, pinned as a fact about the corpus rather than prose.

    LIVA art. 22 reaches both limbs -- "las entregas, construcciones,
    transformaciones, reparaciones, mantenimiento, fletamento ... y
    arrendamiento" is services as much as goods -- but it says so by enumerating
    operation KINDS rather than by naming either limb, so this check cannot read
    what it establishes from the article itself. Deciding it needs arts. 8 and
    11, where the statute defines the two limbs.

    Kept as a case rather than a comment because the claim is falsifiable and
    the situation can change: if the vocabulary widens or the corpus is
    re-extracted such that art. 22's opening does name a limb, this reds and the
    row becomes declarable -- which is a ruling to make, not a check to relax.
    """
    opening = _bundled_text(_ASSIMILATED_EXPORTS_REF)[:1200]

    assert not any(word in opening for word in (*_GOODS_WORDS, *_SERVICES_WORDS)), (
        "art. 22's opening now names a limb, so what it establishes has become readable and the "
        "table's recorded reason for omitting it no longer holds"
    )
    assert "22" not in {citation.article for citation in STATUTORY_CITATIONS}, (
        "art. 22 has a row while its own words still cannot be read, so the row rests on nothing"
    )


def test_two_anchors_in_one_document_read_as_two_different_articles() -> None:
    """The property a file-scoped read cannot have, pinned on the real corpus.

    Both articles live in the same consolidated document. A reader that fell
    back to the file would hand back identical text for the two anchors and find
    both limbs either way; the anchored reader finds one limb each. Losing this
    would not fail loudly -- it would quietly make every anchored row establish
    nothing.
    """
    goods = _bundled_text("corpus/normatives/html/ley-37-1992.html#a68")[:1200]
    services = _bundled_text("corpus/normatives/html/ley-37-1992.html#a69")[:1200]

    assert goods != services, "the two anchors resolved to the same text, so the anchor is not scoping"
    assert any(word in goods for word in _GOODS_WORDS)
    assert not any(word in goods for word in _SERVICES_WORDS)
    assert any(word in services for word in _SERVICES_WORDS)
    assert not any(word in services for word in _GOODS_WORDS)


def test_the_table_carries_both_natures_and_at_least_one_that_fixes_nothing() -> None:
    """A one-sided table cannot fail in the direction it does not cover.

    Stated as a property rather than a count: pinning the number of rows would
    encode this moment and fail the next time an article is bundled.
    """
    established = {citation.establishes for citation in STATUTORY_CITATIONS}
    assert SupplyNature.GOODS in established
    assert SupplyNature.SERVICES in established
    assert None in established, "no row establishes nothing, so the mixed-article case is untested"


def test_an_article_number_without_its_statute_derives_nothing() -> None:
    """The namespace guard: a bare number names an article of some law, not of this one.

    Ley 27/2014 art. 21 is a corporate-income provision and this repository
    bundles its text too, so reading ``art. 21`` out of context would confidently
    return the wrong law's answer.
    """
    assert match_statutory_citations("Operación exenta según art. 21") == ()
    assert (
        derive_supply_nature_from_citation(
            printed_citation="Operación exenta según art. 21",
        ).outcome
        is SupplyNatureDerivationOutcome.ABSENT
    )

    # The same sentence, qualified, does derive -- so the empty result above is
    # the qualifier's doing and not a broken matcher.
    qualified = derive_supply_nature_from_citation(printed_citation="Operación exenta según art. 21 LIVA")
    assert qualified.outcome is SupplyNatureDerivationOutcome.DERIVED
    assert qualified.nature is SupplyNature.GOODS


@pytest.mark.parametrize(
    "printed",
    [
        "Exenta art. 25 LIVA",
        "exenta artículo 25 de la Ley 37/1992",
        "EXENTO ARTS. 25 Y 26 LEY DEL IVA",
        "Operación exenta (art.25 LIVA)",
    ],
)
def test_the_printed_forms_a_document_actually_uses_all_reach_the_same_row(printed: str) -> None:
    """One article, four typographies. The statute fixes the number, not the layout."""
    derivation = derive_supply_nature_from_citation(printed_citation=printed)
    assert derivation.outcome is SupplyNatureDerivationOutcome.DERIVED
    assert derivation.nature is SupplyNature.GOODS


def test_a_number_that_is_not_an_article_reference_is_not_read_as_one() -> None:
    """An amount or a longer article number must not match a declared row."""
    assert match_statutory_citations("Base imponible 25,00 EUR - Ley 37/1992") == ()
    assert match_statutory_citations("según art. 250 LIVA") == ()


def test_free_prose_describing_the_lines_derives_nothing() -> None:
    """The property the whole module exists for: no rule table over descriptions.

    Both sentences name what was supplied unambiguously to a human reader, and in
    a vocabulary a keyword table would happily map. Neither may derive anything,
    because a table that answered these would answer the ambiguous ones too and
    give back no way to tell which kind of answer it produced.
    """
    assert (
        derive_supply_nature_from_citation(
            printed_citation="Servicios de consultoría informática prestados durante marzo",
        ).outcome
        is SupplyNatureDerivationOutcome.ABSENT
    )
    assert (
        derive_supply_nature_from_citation(
            printed_citation="Suministro de material de oficina: 40 cajas de folios",
        ).outcome
        is SupplyNatureDerivationOutcome.ABSENT
    )


def test_an_article_governing_both_limbs_establishes_nothing_while_reporting_what_it_read() -> None:
    """A cited article that fixes nothing is a different fact from no citation."""
    derivation = derive_supply_nature_from_citation(
        printed_citation="Inversión del sujeto pasivo, art. 84 LIVA",
    )

    assert derivation.outcome is SupplyNatureDerivationOutcome.ABSENT
    assert derivation.nature is None
    assert [citation.article for citation in derivation.citations] == ["84"]


def test_two_citations_establishing_different_natures_are_reported_not_resolved() -> None:
    """The document disagrees with itself; picking a side would erase the signal."""
    derivation = derive_supply_nature_from_citation(
        printed_citation="Exenta art. 25 LIVA; régimen art. 163 octiesdecies LIVA",
    )

    assert derivation.outcome is SupplyNatureDerivationOutcome.CONTRADICTED
    assert derivation.nature is None
    assert len(derivation.citations) == 2


def test_a_suffixed_article_does_not_match_a_differently_suffixed_one() -> None:
    """``163 octiesdecies`` and ``163 unvicies`` are different articles.

    They differ only in an ordinal suffix, and they establish different things --
    services for one, nothing for the other -- so a matcher keying on the number
    alone would swap a derived answer for an absent one.
    """
    services_only = match_statutory_citations("art. 163 octiesdecies LIVA")
    assert [citation.article for citation in services_only] == ["163 octiesdecies"]

    mixed_only = match_statutory_citations("art. 163 unvicies LIVA")
    assert [citation.article for citation in mixed_only] == ["163 unvicies"]


@pytest.mark.parametrize(
    "category",
    [
        IvaCategory.DOMESTIC_GENERAL,
        IvaCategory.DOMESTIC_REDUCED,
        IvaCategory.DOMESTIC_SUPER_REDUCED,
        IvaCategory.DOMESTIC_ZERO,
        IvaCategory.DOMESTIC_EXEMPT,
        IvaCategory.DOMESTIC_NOT_SUBJECT,
    ],
)
def test_a_domestic_operation_is_never_asked_for_the_distinction(category: IvaCategory) -> None:
    """Laziness in the direction that matters: no invoice blocked on an idle fact.

    A domestic supply is taxed at its registry rate whether it supplied a good or
    a service, so demanding the nature here would refuse invoices for a
    distinction their own treatment ignores.
    """
    assert supply_nature_is_required(category) is False


@pytest.mark.parametrize(
    "category",
    [
        IvaCategory.DOMESTIC_REVERSE_CHARGE,
        IvaCategory.INTRA_COMMUNITY_SUPPLY,
        IvaCategory.INTRA_COMMUNITY_SERVICE_SUPPLY,
        IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
    ],
)
def test_a_branch_where_the_law_forks_does_ask(category: IvaCategory) -> None:
    """The other direction, so laziness cannot be a blanket "never ask"."""
    assert supply_nature_is_required(category) is True


def test_a_category_the_catalogue_names_a_service_derives_services() -> None:
    """The gap the place-of-supply rows closed, pinned as a consistency invariant.

    A member the catalogue calls a service supply is a *prestación de servicios*
    by its own name, so any nature its grounding yields other than ``SERVICES``
    is a disagreement between the catalogue and the statute rather than a
    preference. Both members derived nothing until arts. 69 and 70 could be
    declared, and an operator was asked a question the law had answered.

    Discovered from the catalogue rather than listed, so a member added later is
    covered without editing this file.
    """
    service_named = tuple(category for category in IvaCategory if "SERVICE" in category.name)
    assert service_named, "the catalogue names no service member, so this case cannot discriminate"

    for category in service_named:
        derivation = supply_nature_implied_by_category(category)
        assert derivation.nature is SupplyNature.SERVICES, (
            f"{category.value} is named a service but its grounding derives {derivation.nature} ({derivation.outcome})"
        )


@pytest.mark.parametrize(
    "category",
    [
        IvaCategory.INTRA_COMMUNITY_SUPPLY,
        IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
        IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED,
    ],
)
def test_the_goods_categories_still_derive_goods(category: IvaCategory) -> None:
    """The other side of the same change, so the rows cannot have moved the answer.

    Adding a services article to the vocabulary must not disturb what the goods
    families derived. Each of these rests on an article defining an operation on
    *bienes* -- arts. 25, 15 and 21 -- and none cites art. 68 alongside them.
    """
    assert supply_nature_implied_by_category(category).nature is SupplyNature.GOODS


def test_no_shipped_category_is_grounded_in_articles_that_disagree() -> None:
    """A contradiction here is a defect in the component table, not a stray input.

    ``CONTRADICTED`` is the honest report for a document citing incompatible
    articles. Reached through a CATEGORY it means something else: the family's
    own grounding disagrees with itself, which no invoice can resolve and no
    operator can be asked about. Stated as a property so it keeps holding as
    articles and members are added.
    """
    for category in IvaCategory:
        derivation = supply_nature_implied_by_category(category)
        assert derivation.outcome is not SupplyNatureDerivationOutcome.CONTRADICTED, (
            f"{category.value} is grounded in articles establishing different natures: {derivation.note}"
        )


def test_an_unplaced_operation_is_asked_rather_than_assumed_domestic() -> None:
    """Fail-closed on the open case.

    Answering ``False`` for a category not yet established would skip the question
    for exactly the invoices that have not been placed on a branch -- the
    restrictive-provision-as-default shape, silently capturing the population the
    narrow rule does not govern.
    """
    assert supply_nature_is_required(None) is True


def test_every_qualifier_is_lowercase_so_the_casefolded_match_can_find_it() -> None:
    """A guard on the table itself: an uppercase qualifier would never match.

    The lookup casefolds the document text and then searches for each qualifier
    verbatim, so a qualifier carrying a capital could not be found in any input.
    That failure is silent -- the axis would simply stop deriving.
    """
    for qualifier in LIVA_CITATION_QUALIFIERS:
        assert qualifier == qualifier.casefold()


def test_no_declared_article_pattern_matches_a_bare_number_in_running_text() -> None:
    """Every row needs the article word; none may fire on a naked figure."""
    for citation in STATUTORY_CITATIONS:
        bare = re.sub(r"\s+", " ", citation.article)
        assert match_statutory_citations(f"Total {bare} LIVA") == (), (
            f"row {citation.article} matched a number with no article reference before it"
        )
