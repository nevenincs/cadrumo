"""Probe revision selection using the period codes each revision actually declares.

Three separate investigations in this project's registry work reached a wrong
conclusion the same way: a revision was asked whether it resolves, the question
was put with a period code that revision does not accept, and the resulting
refusal was read as the registry being unable to answer. Once it read as
temporal selection silently collapsing three regimes into one; once as two
declared regimes being unreachable; once as a whole modelo refusing every year.
All three were the question's shape, not the registry's state.

The refusal is identical in every case, which is the root of it. A revision that
declares no coverage for a year and a revision asked with a code from a
different period family both raise the same error, so the caller cannot tell a
finding from a mistake without going back to the declaration - which is exactly
the step a caller in a hurry skips.

This module removes the opportunity. It reads the period codes off each
revision's own selector and probes with those, so a refusal reported here is a
refusal of a question the revision was designed to answer. It cannot prove a
revision is unreachable by asking it the wrong thing, because it does not know
how to ask the wrong thing.

A year-only question is itself under-specified where two revisions split inside
one year, so a refusal at that shape is retried with a date inside the
revision's own window. The distinction matters: a registry refusing an ambiguous
coordinate is behaving correctly, and reporting that as a finding would be this
module committing the error it exists to prevent.

Coverage of the declared year range is deliberately not assumed: the years
probed come from the caller, and a revision declaring no year bounds is probed
at the year its window opens. What the module reports is one row per revision
and declared period code, saying what that pair resolves to - the revision
itself, a different revision, or a refusal by name.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import date

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.errors import AmbiguousRevisionSelectionError
from cadrumo.domain.calculations.registry.ids import RevisionId
from cadrumo.domain.calculations.registry.schema import ModeloRevision

from ..compiler.authority import admitted_revision_id, compiled_bundled_authority
from ..maintenance_support import (
    coverage_assessment_floor,
    coverage_assessment_horizon,
    revision_selection_coordinates,
)

__all__ = [
    "SelectionProbe",
    "declared_period_codes",
    "probe_modelo",
]

_GRADES = (RegistryAuthorityGrade.FILING, RegistryAuthorityGrade.APPLICABILITY)


@dataclass(frozen=True, slots=True)
class SelectionProbe:
    """What one revision's own period code resolves to at one filing year."""

    modelo: str
    revision: str
    period: str
    filing_year: int
    resolved: str | None
    refusal: str | None
    #: Whether the filing year ALONE could not choose, so a date inside the
    #: revision's own window was needed. Recorded rather than discarded: a
    #: successful retry leaves `resolved` set and clears `refusal`, so without
    #: this a coordinate the year cannot decide is reported exactly like one it
    #: decides outright, and the class this screen exists to find disappears
    #: into the ordinary rows.
    year_alone_ambiguous: bool = False

    @property
    def resolves_to_itself(self) -> bool:
        """Whether the revision answers the question it declares it can answer."""
        return self.resolved == self.revision


def declared_period_codes(revision: object) -> tuple[str, ...]:
    """Return the period codes a revision's selector declares, in declaration order.

    A revision declaring none is reported as declaring none rather than being
    given a default, because a default is how the wrong code gets asked.
    """
    selector = getattr(revision, "period_selector", None)
    return tuple(str(code) for code in getattr(selector, "periods", ()) or ())


def _probe_year(
    *,
    filing_year: int | None,
    coordinates: tuple[tuple[int, str], ...],
) -> int | None:
    """Choose the requested year or the earliest supported coordinate."""
    if filing_year is not None:
        return filing_year
    if not coordinates:
        return None
    return min(item[0] for item in coordinates)


def _resolve_declared_period(
    authority: ValidatedRegistryAuthority,
    modelo_id: str,
    *,
    filing_year: int,
    period: str,
    on: date | None = None,
    stop_on_ambiguity: bool,
) -> tuple[str | None, str | None]:
    """Try authority grades in declaration order, retaining the last refusal."""
    resolved: str | None = None
    refusal: str | None = None
    for grade in _GRADES:
        try:
            if on is None:
                resolved = str(
                    admitted_revision_id(
                        authority,
                        modelo_id,
                        filing_year=filing_year,
                        period=period,
                        grade=grade,
                    )
                )
            else:
                resolved = str(
                    admitted_revision_id(
                        authority,
                        modelo_id,
                        filing_year=filing_year,
                        period=period,
                        on=on,
                        grade=grade,
                    )
                )
            break
        except AmbiguousRevisionSelectionError:
            refusal = AmbiguousRevisionSelectionError.__name__
            if stop_on_ambiguity:
                break
        except Exception as error:
            refusal = type(error).__name__
    return resolved, refusal


def _probe_declared_period(
    authority: ValidatedRegistryAuthority,
    modelo_id: str,
    revision_id: RevisionId,
    revision: ModeloRevision,
    *,
    filing_year: int,
    period: str,
) -> SelectionProbe:
    """Probe one declared period and retry only an ambiguous year with a date."""
    resolved, refusal = _resolve_declared_period(
        authority,
        modelo_id,
        filing_year=filing_year,
        period=period,
        stop_on_ambiguity=True,
    )
    year_alone_ambiguous = refusal == AmbiguousRevisionSelectionError.__name__
    if year_alone_ambiguous:
        resolved, refusal = _resolve_declared_period(
            authority,
            modelo_id,
            filing_year=filing_year,
            period=period,
            on=revision.valid_from,
            stop_on_ambiguity=False,
        )
    return SelectionProbe(
        modelo=modelo_id,
        revision=str(revision_id),
        period=period,
        filing_year=filing_year,
        resolved=resolved,
        refusal=None if resolved else refusal,
        year_alone_ambiguous=year_alone_ambiguous,
    )


def probe_modelo(
    authority: ValidatedRegistryAuthority, modelo_id: str, *, filing_year: int | None = None
) -> tuple[SelectionProbe, ...]:
    """Probe every revision of one modelo with the codes it declares.

    Args:
        authority: The validated registry authority to ask.
        modelo_id: The modelo whose revisions are probed.
        filing_year: The year to ask about; each revision's own opening year
            when omitted, which is the year it is certain to have an opinion on.

    Returns:
        One probe per revision and declared period code.
    """
    horizon = coverage_assessment_horizon(authority.catalogues)
    floor = coverage_assessment_floor(authority.catalogues)
    probes: list[SelectionProbe] = []
    for revision_id, revision in authority.modelo(modelo_id).revisions.items():
        # An omitted year asks about the revision's earliest SELECTABLE
        # coordinate, not its opening year. The two differ for every edition
        # that opens below the supported floor: asked about its opening year the
        # registry refuses because the year is out of support, and the probe
        # reported that as the revision failing to resolve itself. A revision
        # lying wholly below the floor has no coordinate to be asked about.
        coordinates = revision_selection_coordinates(revision, assessment_horizon=horizon, assessment_floor=floor)
        year = _probe_year(filing_year=filing_year, coordinates=coordinates)
        if year is None:
            continue
        for code in declared_period_codes(revision):
            # Two revisions may split inside one year. Only an ambiguous year
            # is retried with a date inside the current revision's own window.
            probes.append(
                _probe_declared_period(
                    authority,
                    modelo_id,
                    revision_id,
                    revision,
                    filing_year=year,
                    period=code,
                )
            )
    return tuple(probes)


def main(argv: list[str] | None = None) -> int:
    """Print one row per revision and declared period code; always exit 0."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("modelo")
    parser.add_argument("--filing-year", type=int, default=None)
    parser.add_argument("--only-surprising", action="store_true", help="hide rows resolving to themselves")
    args = parser.parse_args(argv)

    probes = probe_modelo(compiled_bundled_authority(), args.modelo, filing_year=args.filing_year)
    surprising = 0
    for probe in probes:
        if not probe.resolves_to_itself:
            surprising += 1
        elif args.only_surprising:
            continue
        outcome = probe.resolved or f"refused({probe.refusal})"
        sys.stdout.write(
            f"selection modelo={probe.modelo} revision={probe.revision} period={probe.period} "
            f"year={probe.filing_year} resolved={outcome} "
            f"year_alone_ambiguous={str(probe.year_alone_ambiguous).lower()}\n"
        )
    ambiguous = sum(1 for probe in probes if probe.year_alone_ambiguous)
    sys.stdout.write(
        f"summary probes={len(probes)} not_resolving_to_themselves={surprising} year_alone_ambiguous={ambiguous}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
