"""Every year-only selection refusal in the coverage matrix is legally irreducible.

The temporal coverage matrix addresses each cell by ``(modelo, revision,
filing_year, period)``. AEAT does not always honour that coordinate system: an
orden may replace a design *inside* a filing year, so the year carries two
designs and no year-only answer is correct in either direction. The resolver
refuses such a cell deliberately rather than picking, and this gate holds that
refusal to its justification.

The discriminator is the PERIOD axis, and the corpus makes it visible. Modelos
303, 490 and 763 all split mid-year, and none of them refuses: their halves
declare disjoint period sets, so ``2T`` and ``3T`` name the design by
themselves. Modelo 369's three OSS schemes share a start date and partition the
periods the same way. Only a split whose halves declare OVERLAPPING periods is
undecidable -- Modelo 308 declares ``AD-HOC`` on both sides of the July 2011
boundary, and ``AD-HOC`` carries no sub-year granularity to discriminate on.

So the obligation is not "do not refuse". It is that every refusal is explained
by a boundary AEAT actually published: the halves must overlap on period, their
validity windows must be disjoint and split inside the refused year, and the
later half must be grounded in a legal entry whose own ``effective_from`` falls
on that boundary. Grounding is read from the legal catalogue rather than from
the revision that claims it, so a revision cannot vouch for its own date.

The refusal must also be reducible by the axis the coordinate system lacks: a
date-qualified query resolves each half to a distinct revision. That is what
separates "this coordinate is too coarse" from "this registry is broken", and it
is asserted per refusal rather than assumed.

Nothing here is keyed to a tally or to Modelo 308. A new grounded mid-year
AD-HOC split passes without editing this file; an ungrounded one fails.
"""

from __future__ import annotations

from datetime import date
from itertools import pairwise

import pytest

from ....core.resources import bundled_path
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.errors import AmbiguousRevisionSelectionError
from ....domain.calculations.registry.loader import load_registry_tree
from ....domain.calculations.registry.temporal import select_revision
from ..temporal_coverage import compose_temporal_coverage

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _authority():
    authority = bundled_authority()
    authority.validate_registry()
    return authority


def _co_claimants(modelo, filing_year: int, period: str):
    """Return every revision of ``modelo`` whose selector claims this year and period."""
    return sorted(
        (
            revision
            for revision in modelo.revisions.values()
            if revision.period_selector.includes_year(filing_year) and period in set(revision.period_selector.periods)
        ),
        key=lambda revision: revision.valid_from,
    )


def _refused_selection_rows():
    report = compose_temporal_coverage(authority=_authority())
    return tuple(row for row in report.refused_rows if row.failure_code == "law_selection_refused")


def test_every_year_only_refusal_is_an_overlapping_period_split() -> None:
    """A refusal must come from co-claimants the period axis cannot separate."""
    authority = _authority()

    for row in _refused_selection_rows():
        modelo = next(candidate for candidate in authority.modelos if candidate.id == str(row.modelo))
        claimants = _co_claimants(modelo, row.filing_year, str(row.period))

        assert len(claimants) > 1, (
            f"modelo {row.modelo} {row.filing_year} {row.period}: selection refused but only "
            f"{len(claimants)} revision claims the coordinate; the refusal has no mid-year boundary "
            "to explain it and is a resolver defect rather than a coarse coordinate"
        )


def test_every_refused_split_has_disjoint_windows_breaking_inside_the_year() -> None:
    """The halves must partition the year, so a date could name one of them."""
    authority = _authority()

    for row in _refused_selection_rows():
        modelo = next(candidate for candidate in authority.modelos if candidate.id == str(row.modelo))
        claimants = _co_claimants(modelo, row.filing_year, str(row.period))

        for earlier, later in pairwise(claimants):
            assert earlier.valid_to is not None, (
                f"modelo {row.modelo}: revision {earlier.id} co-claims {row.filing_year} with "
                f"{later.id} but never closes; two open windows overlap forever"
            )
            assert earlier.valid_to < later.valid_from, (
                f"modelo {row.modelo}: revisions {earlier.id} and {later.id} overlap on "
                f"{earlier.valid_to}; a refused coordinate must still partition cleanly"
            )
            assert later.valid_from.year == row.filing_year, (
                f"modelo {row.modelo}: the boundary at {later.valid_from} falls outside the refused "
                f"year {row.filing_year}, so it cannot be what makes the year undecidable"
            )


def test_every_refused_boundary_is_grounded_in_a_published_orden() -> None:
    """The boundary date must be attested by the legal catalogue, not by the revision.

    A revision declaring its own ``valid_from`` proves nothing about AEAT. The
    legal entry carries an independent ``effective_from``, so requiring the two
    to agree makes the boundary a cited regulatory fact.
    """
    authority = _authority()
    _modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))

    for row in _refused_selection_rows():
        modelo = next(candidate for candidate in authority.modelos if candidate.id == str(row.modelo))
        claimants = _co_claimants(modelo, row.filing_year, str(row.period))

        for later in claimants[1:]:
            grounding = [
                catalogues.legal[ref]
                for ref in later.orden_aplicabilidad
                if ref in catalogues.legal and catalogues.legal[ref].effective_from == later.valid_from
            ]
            assert grounding, (
                f"modelo {row.modelo}: revision {later.id} opens on {later.valid_from} and makes "
                f"{row.filing_year} undecidable, but no orden it cites carries that effective_from. "
                "An undecidable year must be AEAT's doing, not the authoring tree's"
            )


def test_a_date_resolves_every_refused_coordinate_to_one_revision() -> None:
    """Anti-tautology: the corpus can answer; only the year-only coordinate cannot.

    Without this the gate would accept a registry that refuses because it is
    broken, since 'refuses and is grounded' is satisfiable by a corpus no date
    can resolve either.
    """
    authority = _authority()

    for row in _refused_selection_rows():
        modelo = next(candidate for candidate in authority.modelos if candidate.id == str(row.modelo))
        claimants = _co_claimants(modelo, row.filing_year, str(row.period))

        with pytest.raises(AmbiguousRevisionSelectionError):
            select_revision(modelo, filing_year=row.filing_year, period=str(row.period), on=None)

        resolved = set()
        for claimant in claimants:
            probe = max(claimant.valid_from, date(row.filing_year, 1, 1))
            selected = select_revision(
                modelo,
                filing_year=row.filing_year,
                period=str(row.period),
                on=probe,
            )
            assert selected.id == claimant.id, (
                f"modelo {row.modelo}: a date inside {claimant.id}'s own window resolved to "
                f"{selected.id}; the date axis does not recover the design AEAT published"
            )
            resolved.add(str(selected.id))

        assert len(resolved) == len(claimants), (
            f"modelo {row.modelo} {row.filing_year}: the date axis collapsed "
            f"{len(claimants)} co-claimants onto {len(resolved)} revision(s), so the refusal is "
            "not merely a coarse coordinate"
        )


def test_a_period_separated_midyear_split_is_not_treated_as_undecidable() -> None:
    """Discrimination proof: the explanation must reject splits the period axis settles.

    Modelos 303, 490 and 763 all replace a design mid-year. None may refuse, and
    none may be explainable by this gate's rule -- otherwise the rule is a rubber
    stamp that would licence any overlap at all. The split is derived from the
    corpus, so this stays honest if those trees change.
    """
    authority = _authority()
    examined = 0

    for modelo in authority.modelos:
        revisions = sorted(modelo.revisions.values(), key=lambda revision: revision.valid_from)
        for revision in revisions:
            if (revision.valid_from.month, revision.valid_from.day) == (1, 1):
                continue
            year = revision.valid_from.year
            siblings = [
                other for other in revisions if other.id != revision.id and other.period_selector.includes_year(year)
            ]
            if not siblings:
                continue
            own = set(revision.period_selector.periods)
            for sibling in siblings:
                shared = own & set(sibling.period_selector.periods)
                if shared:
                    continue
                examined += 1
                for period in sorted(own):
                    selected = select_revision(modelo, filing_year=year, period=period, on=None)
                    assert selected.id == revision.id, (
                        f"modelo {modelo.id}: period {period} in {year} resolved to {selected.id} "
                        f"rather than {revision.id}; a disjoint period set must name its design "
                        "without a date"
                    )

    assert examined, (
        "no period-separated mid-year split was found in the corpus, so the discrimination proof "
        "asserted nothing; the rule above is unverified"
    )
