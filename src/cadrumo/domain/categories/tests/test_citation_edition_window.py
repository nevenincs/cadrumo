"""The anti-mirror invariant: an edition-dated citation may not outreach its edition.

A citation naming an annual publication asserts that THAT edition supports the
rule. Stretching its validity window across a neighbouring year converts a
document nobody opened into a grounding claim, and does it silently -- the
widened record is indistinguishable from one that was actually read.

This is not hypothetical. The retired per-year spending-category corpus was
produced exactly that way: a reviewed year's file was copied and its 41
year-dated references and URLs were rewritten by string substitution, so the
copy asserted, 41 times, that a specific manual at a specific URL said something
nobody had checked. Collapsing that corpus onto validity windows would have
laundered the copy into a multi-year grounding claim unless something refused it.

The invariant lives on the model rather than only here, so a corpus cannot
acquire the shape in the first place; these tests prove it discriminates.
"""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from cadrumo.core.i18n import Translatable as tr

from .._proportionality import (
    ANNUAL_EDITION_CITATION_SOURCES,
    CategoryCitation,
    CategoryCitationSource,
    parse_http_url,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_BOE_URL = "https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764"


def _citation(
    *,
    source: CategoryCitationSource,
    reference: str,
    valid_from: date,
    valid_to: date,
) -> CategoryCitation:
    return CategoryCitation(
        source=source,
        reference=reference,
        locator="art. 30",
        url=parse_http_url(_BOE_URL),
        quote=tr("Texto autoritativo de prueba."),
        valid_from=valid_from,
        valid_to=valid_to,
    )


def test_an_edition_dated_citation_windowed_to_its_own_year_is_accepted() -> None:
    citation = _citation(
        source=CategoryCitationSource.MANUAL_RENTA,
        reference="Manual práctico Renta 2025",
        valid_from=date(2025, 1, 1),
        valid_to=date(2025, 12, 31),
    )

    assert citation.window.years() == (2025,)


@pytest.mark.parametrize(
    ("valid_from", "valid_to", "expected_outside"),
    [
        pytest.param(date(2024, 1, 1), date(2025, 12, 31), "[2024]", id="widened-backwards"),
        pytest.param(date(2025, 1, 1), date(2026, 12, 31), "[2026]", id="widened-forwards"),
        pytest.param(date(2022, 1, 1), date(2026, 12, 31), "2022", id="widened-both-ways"),
    ],
)
def test_widening_an_edition_dated_citation_past_its_edition_is_refused(
    valid_from: date,
    valid_to: date,
    expected_outside: str,
) -> None:
    """DISCRIMINATING. This is the exact act that produced the retired mirror."""
    with pytest.raises(ValidationError, match="never widen an edition-dated citation") as caught:
        _citation(
            source=CategoryCitationSource.MANUAL_RENTA,
            reference="Manual práctico Renta 2025",
            valid_from=valid_from,
            valid_to=valid_to,
        )

    assert expected_outside in str(caught.value)


def test_an_annual_source_must_name_the_edition_it_was_read_from() -> None:
    """Dropping the year would otherwise be a one-token escape from the invariant."""
    with pytest.raises(ValidationError, match="must name the edition year"):
        _citation(
            source=CategoryCitationSource.MANUAL_RENTA,
            reference="Manual práctico Renta",
            valid_from=date(2025, 1, 1),
            valid_to=date(2025, 12, 31),
        )


def test_a_statute_reference_year_is_an_enactment_and_does_not_bound_the_window() -> None:
    """The invariant keys on the source taxonomy, never on sniffing for a year.

    "Ley 35/2006" names when the law was passed. A year-sniffing rule would read
    2006 as an edition and refuse every statutory citation in the corpus, which
    is why the annual-edition set is declared rather than inferred.
    """
    citation = _citation(
        source=CategoryCitationSource.LEY_IRPF,
        reference="Ley 35/2006",
        valid_from=date(2022, 1, 1),
        valid_to=date(2026, 12, 31),
    )

    assert citation.window.years() == (2022, 2023, 2024, 2025, 2026)


def test_every_annual_edition_source_is_held_to_the_invariant() -> None:
    """Enumerated from the declared set, so a new annual source cannot slip past.

    Adding a member to ``ANNUAL_EDITION_CITATION_SOURCES`` extends this test
    without editing it; adding an annual publication and forgetting to enrol it
    is the failure this cannot catch, and is the reason the set sits beside the
    enum it partitions.
    """
    assert ANNUAL_EDITION_CITATION_SOURCES, "the annual-edition set is empty; the invariant would be inert"

    for source in sorted(ANNUAL_EDITION_CITATION_SOURCES):
        with pytest.raises(ValidationError):
            _citation(
                source=source,
                reference="Publicación anual 2025",
                valid_from=date(2025, 1, 1),
                valid_to=date(2026, 12, 31),
            )


def test_the_shipped_corpus_satisfies_the_invariant_through_the_real_loader() -> None:
    """SUPPORTING: the shipped data loads, which it cannot do while violating it.

    The invariant is a model validator, so a violating citation refuses at load;
    this asserts the corpus is actually reached rather than trivially empty.
    """
    from .._registry import load_category_profiles

    profiles = load_category_profiles()
    edition_dated = [
        citation
        for profile in profiles.values()
        for citation in profile.proportionality.citations
        if citation.source in ANNUAL_EDITION_CITATION_SOURCES
    ]

    assert edition_dated, "the shipped corpus carries no edition-dated citations; this gate is vacuous"
