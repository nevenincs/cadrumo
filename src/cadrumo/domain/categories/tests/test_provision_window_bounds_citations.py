"""A statutory category citation may not be asserted beyond the provision it cites.

This is the second half of the anti-mirror contract. An edition-dated citation is
bounded by the edition year it names, which
``test_citation_edition_window`` enforces. A statutory citation names no edition,
so without this gate its window would be pure author assertion -- and widening
statutory windows is exactly how someone would turn this corpus's year-coverage
gate green without reading anything.

Here the permissible span is DERIVED: the registry legal catalogue records when
each provision took effect and, where repealed, when it stopped. A window inside
that span is a checkable fact about the law; one outside it is a fabrication the
catalogue itself refutes.

Together the two gates cover the corpus exhaustively, which is the property
:func:`test_every_citation_source_is_bounded_on_exactly_one_axis` pins: a new
citation source cannot arrive bounded by neither.
"""

from __future__ import annotations

from datetime import date

import pytest

from ....core.resources import bundled_path
from ....core.validity_window import ValidityWindow
from ...calculations.registry.loader import load_registry_tree
from ...calculations.registry.schema_references import LegalReference
from .._proportionality import (
    ANNUAL_EDITION_CITATION_SOURCES,
    STATUTORY_CITATION_SOURCES,
    CategoryCitation,
    CategoryCitationSource,
)
from .._registry import load_category_profiles

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _legal_catalogue() -> dict[str, LegalReference]:
    _modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    return dict(catalogues.legal)


def _statutory_citations() -> list[tuple[str, CategoryCitation]]:
    return [
        (f"{category.value}/{citation.locator}", citation)
        for category, profile in load_category_profiles().items()
        for citation in profile.proportionality.citations
        if citation.source in STATUTORY_CITATION_SOURCES
    ]


def _outside_provision(
    window: ValidityWindow,
    entry: LegalReference,
) -> str:
    if window.valid_from < entry.effective_from:
        return (
            f"window opens {window.valid_from.isoformat()} before the provision took effect "
            f"{entry.effective_from.isoformat()}"
        )
    if entry.effective_to is not None and window.valid_to > entry.effective_to:
        return (
            f"window closes {window.valid_to.isoformat()} after the provision was repealed "
            f"{entry.effective_to.isoformat()}"
        )
    return ""


def test_every_statutory_citation_names_a_provision_the_catalogue_carries() -> None:
    """Anchor: an unresolvable id would make the span check silently skip a row."""
    catalogue = _legal_catalogue()
    citations = _statutory_citations()

    assert citations, "no statutory citations were measured; every assertion here would be vacuous"

    unresolved = sorted({citation.legal_ref for _label, citation in citations if citation.legal_ref not in catalogue})
    assert unresolved == [], (
        f"these category citations name provisions absent from the legal catalogue: {unresolved}. "
        "Enrol the provision with its corpus_ref and effective span, or cite one that exists."
    )


def test_every_statutory_citation_stays_inside_its_provisions_effective_span() -> None:
    """The whole shipped surface, re-derived from the catalogue on every run.

    Property, not tally: amending a provision's effective date automatically
    re-judges every citation that rests on it, with no constant to update here.
    """
    catalogue = _legal_catalogue()

    violations = [
        f"{label} ({citation.legal_ref}): {problem}"
        for label, citation in _statutory_citations()
        if citation.legal_ref in catalogue
        and (problem := _outside_provision(citation.window, catalogue[citation.legal_ref]))
    ]

    assert violations == [], (
        "these category citations are asserted beyond the provisions they cite:\n  "
        + "\n  ".join(sorted(violations))
        + "\nNarrow the window to what the provision supports, or cite the provision that actually "
        "covers the wider span. Never widen a window to admit a filing year nobody read."
    )


def test_every_citation_source_is_bounded_on_exactly_one_axis() -> None:
    """No source may be bounded by neither gate, and none by both.

    Derived from the enum rather than listed, so a new citation source lands in
    one partition or reds here. A source in neither would be a citation whose
    window nothing checks -- the hole both gates exist to close.
    """
    every_source = set(CategoryCitationSource)

    assert every_source == ANNUAL_EDITION_CITATION_SOURCES | STATUTORY_CITATION_SOURCES
    assert set() == ANNUAL_EDITION_CITATION_SOURCES & STATUTORY_CITATION_SOURCES


def test_a_statutory_citation_must_name_its_provision() -> None:
    """DISCRIMINATING: without legal_ref there is no axis to judge the window on."""
    from pydantic import ValidationError

    from ....core.i18n import Translatable as tr
    from .._proportionality import parse_http_url

    with pytest.raises(ValidationError, match="must name it with legal_ref"):
        CategoryCitation(
            source=CategoryCitationSource.LEY_IRPF,
            reference="Ley 35/2006",
            locator="art. 28.1",
            url=parse_http_url("https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764"),
            quote=tr("Texto."),
            valid_from=date(2022, 1, 1),
            valid_to=date(2026, 12, 31),
        )


def test_a_window_opening_before_its_provision_took_effect_is_a_violation() -> None:
    """DISCRIMINATING: the shape a future author produces by widening backwards."""
    catalogue = _legal_catalogue()
    entry = catalogue["ley-35-2006:art-30"]
    too_early = ValidityWindow(
        valid_from=date(entry.effective_from.year - 3, 1, 1),
        valid_to=date(2026, 12, 31),
    )

    assert "before the provision took effect" in _outside_provision(too_early, entry)


def test_a_window_inside_the_span_is_not_a_violation() -> None:
    catalogue = _legal_catalogue()
    entry = catalogue["ley-35-2006:art-28"]

    assert not _outside_provision(
        ValidityWindow(valid_from=date(2022, 1, 1), valid_to=date(2026, 12, 31)),
        entry,
    )
