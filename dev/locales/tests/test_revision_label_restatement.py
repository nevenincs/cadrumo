"""Real-behaviour tests for the cross-revision label restatement census.

The classification is the instrument here, so it is proven on constructed input
holding one of each population. The live corpus is then asserted by ORDERING
rather than by figure: every count this reports is a live measurement that moves
whenever a revision or a translation lands, and a test pinning one would fail on
work that changed nothing about the property.
"""

from __future__ import annotations

import pytest

from ..revision_label_restatement import (
    casilla_labels,
    label_restatement_census,
    restatement_split,
    translation_diverges_where_source_agrees,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_the_split_separates_restated_divergent_and_single_labels() -> None:
    """Constructed input holding one of each population is classified into three.

    Restatement is counted as the SURPLUS, so a casilla labelled identically
    under three revisions contributes two: that is the number of strings a
    derivation would remove, and counting the casilla instead would understate
    the corpus by every revision past the second.
    """
    census = restatement_split(
        {
            "200": {
                "00001": {"2023": "misma", "2024": "misma", "2025": "misma"},
                "00002": {"2023": "una", "2024": "otra"},
                "00003": {"2024": "sola"},
            }
        },
        locale="es",
    )
    assert (census.restated, census.divergent, census.single) == (2, 1, 1)
    assert census.labels == 6
    assert census.worst == (("200", 2),)


def test_a_corpus_whose_revisions_all_differ_reports_no_restatement() -> None:
    """The instrument must not report duplication where none exists.

    Without this the split could return its restated count from the revision
    count alone and still pass the case above.
    """
    census = restatement_split(
        {"100": {"01": {"2023": "a", "2024": "b"}, "02": {"2023": "c", "2024": "d"}}},
        locale="es",
    )
    assert census.restated == 0
    assert (census.divergent, census.single) == (2, 0)


def test_the_shipped_spanish_catalogue_restates_most_of_its_multi_revision_labels() -> None:
    """The live corpus is read, and restatement dominates divergence.

    Held as an ordering, not a figure. The claim is that the catalogues carry
    more text repeating itself than text that genuinely differs, which is what
    makes the derivation worth building; the exact counts are what the census
    prints.
    """
    census = label_restatement_census("es")
    assert census.labels > 0, "the census read no labels, so it measured nothing"
    assert census.restated > census.divergent > 0
    assert census.worst[0][1] > 0


def test_every_shipped_locale_carries_its_own_restatement() -> None:
    """A derivation collapsing one locale and not the others is not done.

    Asserted per locale so the census cannot pass on Spanish alone.
    """
    from .._paths import LOCALES_DIR
    from ..manager import discover_locale_codes

    measured = {locale: label_restatement_census(locale) for locale in sorted(discover_locale_codes(LOCALES_DIR))}
    assert len(measured) > 1, "only one catalogue was discovered"
    assert all(census.restated > 0 for census in measured.values() if census.labels)


def test_translations_diverge_where_the_spanish_source_does_not() -> None:
    """Two translations of one source string are reported as their own population.

    This is a defect rather than a cost: the official text said the same thing
    under both revisions, so the reader of one cannot tell which translation is
    current. Pinned by shape and by the modelo carrying them, not by count.
    """
    found = translation_diverges_where_source_agrees("es", "hu")
    assert found, "the condition lost its live proof"
    assert all(isinstance(modelo, str) and isinstance(casilla, str) for modelo, casilla in found)
    # Every reported casilla must really be identical in the source and really
    # differ in the target, or the instrument is reporting its own arithmetic.
    source = casilla_labels("es")
    target = casilla_labels("hu")
    for modelo, casilla in found[:50]:
        assert len(set(source[modelo][casilla].values())) == 1
        assert len(set(target[modelo][casilla].values())) > 1
