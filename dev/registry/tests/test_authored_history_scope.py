"""The authored-history escape hatch reaches the whole authored corpus.

The support envelope gates what the product will FILE. Work whose subject is
the authored source of an older ejercicio resolves against a widened envelope
instead, and a refusal to reach that source is silent: the case simply fails to
find data that is right there on disk.

So the widened floor is derived from the corpus rather than written down. These
tests hold that property, because a pinned year fails in exactly the way nobody
notices -- it stays plausible while quietly stopping short.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.errors import FilingYearOutsideSupportEnvelopeError
from cadrumo.domain.calculations.registry.temporal import select_revision

from ..compiler.authority import compiled_bundled_authority
from .profile_schema_support import (
    authored_history_authority,
    authored_history_floor,
    authored_history_supported_filing_years,
    committed_supported_filing_years,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_the_authored_history_floor_is_the_corpus_earliest_authored_coordinate() -> None:
    """Derived, so it cannot describe the corpus wrongly.

    Recomputed here from the same two authored axes, independently of the
    helper's own caching, and compared against the helper. A pinned constant
    passes this only by coincidence, and stops passing the moment the corpus
    grows an older edition -- which is the failure this replaces.
    """
    authority = compiled_bundled_authority()
    fact_years = [
        variant.valid_from.year
        for fact in authority.catalogues.facts.facts.values()
        for variant in fact.variants
        if variant.valid_from is not None
    ]
    revision_years = [
        year
        for modelo in authority.modelos
        for revision in modelo.revisions.values()
        for year in (
            revision.period_selector.years
            or ((revision.period_selector.year_from,) if revision.period_selector.year_from is not None else ())
        )
    ]
    assert fact_years and revision_years

    assert authored_history_floor() == min(*fact_years, *revision_years)


def test_the_widened_envelope_reaches_below_the_filing_floor_and_keeps_its_ceiling() -> None:
    committed = committed_supported_filing_years()
    widened = authored_history_supported_filing_years()

    assert widened.floor <= committed.floor
    assert widened.floor == authored_history_floor()
    # Only the floor moves: widening the ceiling would let a case assert a year
    # the product has no authority for at all.
    assert widened.horizon == committed.horizon
    assert widened.hard_ceiling == committed.hard_ceiling


def test_the_authored_history_authority_resolves_a_pre_floor_ejercicio_the_filing_envelope_refuses() -> None:
    """The two scopes disagree about 2020, and that disagreement is the point.

    Modelo 100 authors 2020. The filing envelope refuses it and now says why;
    the authored-history authority resolves it. A case whose subject is the
    2020 source picks the second, and the refusal from the first tells it so.
    """
    filing = compiled_bundled_authority()
    committed = filing.catalogues.require_supported_filing_years()
    assert committed.floor > 2020

    with pytest.raises(FilingYearOutsideSupportEnvelopeError):
        select_revision(filing.modelo("100"), filing_year=2020, period="0A", support=committed)

    history = authored_history_authority()
    revision = select_revision(
        history.modelo("100"),
        filing_year=2020,
        period="0A",
        support=history.catalogues.require_supported_filing_years(),
    )

    assert revision.id == "2020"


def test_no_pending_orden_declaration_is_swallowed_by_the_envelope_gate() -> None:
    """A pending-Orden year must sit inside the envelope, or its message is lost.

    `EjercicioOrdenNotYetPublishedError` exists to say something the plain
    absence refusal cannot: this year is not an authoring gap anybody can
    close, because AEAT has not issued the Orden yet. That refusal is built
    only after the envelope gate has let the request through, so a pending
    declaration for a year below the floor would be answered by the envelope
    instead and its specific advice would never reach an operator.

    Which is the RIGHT ordering -- below the floor, waiting for the Orden does
    not help, so telling someone to wait would be wrong. What is not right is
    authoring such a declaration and never learning it is inert. This asserts
    the corpus stays out of that state, derived from the live declarations and
    the live envelope so neither can drift into it unnoticed.
    """
    authority = compiled_bundled_authority()
    support = authority.catalogues.require_supported_filing_years()
    inert = tuple(
        (str(modelo.id), pending.filing_year)
        for modelo in authority.modelos
        for pending in modelo.pending_ejercicio_ordenes
        if not support.admits_filing_year(pending.filing_year)
    )

    assert not inert, (
        f"pending-Orden declarations sit outside the support envelope "
        f"[floor={support.floor}, hard_ceiling={support.hard_ceiling}], so the envelope "
        f"refusal preempts their message: {inert!r}"
    )
