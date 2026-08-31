"""Every category citation carries the evidence its grounding state claims.

For its whole life the corpus carried none. All eighty-three citations set
``quote`` to a dotted locale key -- ``categories.registry.cuotas_colegiales.
citations.0.quote`` and its siblings -- and no ``categories.registry.`` key exists
in any of the four locale catalogues, so every one resolved through the translation
fallback to the literal word "Quote". Each citation therefore carried a document
pointer and a locator but no evidence text at all, while the maintenance tooling
documented the opposite intent: citation quotes are "verbatim AEAT excerpts and are
authored as Spanish text in the registry TOML, never translated".

The check that should have caught this could not. It asserted the translatable was
non-empty AFTER the loader had resolved it through a fallback that never yields an
empty string, so it inspected "Quote", found it non-empty, and passed eighty-three
times.

These tests replace that with corpus CONTAINMENT, which is the invariant the sibling
IVA catalogue adopted for the identical defect: a verified quotation must occur in
the normalised corpus text of its own legal reference. Containment is what a
paraphrase fails and non-emptiness cannot.

No mocks: the real shipped profiles, the real legal catalogue and the real bundled
corpus. Each test states whether it is DISCRIMINATING or SUPPORTING.
"""

from __future__ import annotations

import pytest

from ....core.citation_grounding import CitationGrounding
from ....core.resources._boundary import bundled_path
from ....domain.calculations.registry.legal import legal_reference_quotes_corpus
from ....domain.calculations.registry.loader import load_catalogue_file
from ..proportionality import CategoryCitation
from ..registry import load_category_profiles
from ..spending_category import SpendingCategory

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _legal_catalogue():
    """Return the real IRPF legal catalogue the citations resolve against."""
    return load_catalogue_file(bundled_path() / "registry" / "aeat" / "legal" / "irpf.toml").legal


def _shipped_citations() -> list[CategoryCitation]:
    """Return every citation on every shipped category profile."""
    found: list[CategoryCitation] = []
    for profile in load_category_profiles().values():
        if profile.proportionality is not None:
            found.extend(profile.proportionality.citations)
    return found


def test_no_citation_quote_is_a_locale_key() -> None:
    """DISCRIMINATING. The defect in its original shape.

    A dotted key here means the record points at a translation that does not
    exist and renders as a word derived from its own final segment.
    """
    keyed = [c for c in _shipped_citations() if c.quote.startswith("categories.registry.")]

    assert not keyed, (
        "these citations still indirect their quotation through a locale key, so the record "
        f"carries no evidence: {[(c.source.value, c.locator) for c in keyed]}"
    )


def test_every_verified_quotation_is_contained_in_its_own_provision() -> None:
    """DISCRIMINATING, and the invariant that replaces the non-emptiness check.

    Asserted per citation rather than as a count: a tally would go green again
    the moment someone adjusted the number, and says nothing about which
    citation is grounded.
    """
    catalogue = _legal_catalogue()
    uncontained: list[tuple[str, str]] = []
    for citation in _shipped_citations():
        if citation.grounding is not CitationGrounding.VERIFIED:
            continue
        assert citation.legal_ref is not None, (
            f"verified citation {citation.locator!r} carries no legal_ref to be checked against"
        )
        reference = catalogue[citation.legal_ref]
        if not legal_reference_quotes_corpus(reference, citation.quote, source_root=bundled_path()):
            uncontained.append((citation.legal_ref, citation.locator))

    assert not uncontained, (
        "these quotations do not occur in the bundled corpus text of the provision they cite, "
        f"so they are paraphrase rather than evidence: {uncontained}"
    )


def test_an_unverifiable_citation_says_why_instead_of_carrying_text() -> None:
    """DISCRIMINATING. The half that keeps the absent evidence honest.

    The containment check skips a non-verified citation by design, so candidate
    text parked in that state would never be read against anything while still
    reading as evidence to anyone who printed it.
    """
    for citation in _shipped_citations():
        if citation.grounding is CitationGrounding.VERIFIED:
            continue
        assert citation.grounding_reason.strip(), (
            f"citation {citation.locator!r} claims {citation.grounding.value!r} without recording why"
        )
        assert not citation.quote.strip(), (
            f"citation {citation.locator!r} is {citation.grounding.value!r} yet carries a quotation "
            "the containment gate will never check"
        )


def test_a_citation_naming_an_unbundled_source_is_not_labelled_refused() -> None:
    """DISCRIMINATING. The two absences are different claims about the law.

    ``UNRESOLVED`` asserts the provision was read and found not to support the
    rule. An AEAT *Manual práctico* citation was not read at all, because that
    edition is not among the bundled consolidated texts. Labelling it refused
    would assert a reading nobody performed.
    """
    for citation in _shipped_citations():
        if citation.grounding is not CitationGrounding.SOURCE_NOT_BUNDLED:
            continue
        assert citation.legal_ref is None, (
            f"citation {citation.locator!r} names a provision id yet claims its source is not "
            "bundled; a cited provision resolves against the corpus and must be verified"
        )


def test_the_seguro_de_enfermedad_citation_points_at_the_letter_that_grants_it() -> None:
    """DISCRIMINATING, and a regression on a real mis-citation this pass found.

    The shipped locator for ``seguros_salud_autonomo`` read "art. 30.2.5.c regla
    1.a". Letter c of that rule is gastos de manutención and regla 1.ª is
    aportaciones a mutualidades; neither is health insurance, which is letter a.
    The locale key hid it, because a citation that renders as "Quote" cannot be
    read against the article it names.
    """
    profile = load_category_profiles()[SpendingCategory.SEGUROS_SALUD_AUTONOMO]
    assert profile.proportionality is not None
    citations = list(profile.proportionality.citations)

    statutory = [c for c in citations if c.legal_ref == "ley-35-2006:art-30"]
    assert statutory, "the seguro category no longer cites LIRPF art. 30"
    for citation in statutory:
        assert "30.2.5.a" in citation.locator, (
            f"seguro de enfermedad is granted by LIRPF art. 30.2.5.a; this citation points at {citation.locator!r}"
        )
        assert "primas de seguro de enfermedad" in citation.quote, (
            "the quotation does not carry the sentence that grants the deduction"
        )
