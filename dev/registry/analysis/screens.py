"""One entry point over every registry declaration screen.

Each screen owns one condition and is runnable on its own. This module runs all
of them against a single loaded authority and prints one census line per screen,
so a maintainer asking "what is the state of the declarations" has one command
rather than seven, and so the registry is loaded once rather than seven times.

It adds no analysis of its own and owns no condition. Every count it prints
comes from the screen that owns that condition, which is where the rule, the
docstring explaining it, and the detector test all live. A screen missing from
the table below is simply not run; there is no discovery by naming convention,
because a screen that silently stopped running would be indistinguishable from
a condition that stopped occurring.

Screens report and never gate. The conditions that are clean corpus-wide are
additionally gated in ``dev/registry/tests/test_declaration_invariant_gates.py``
as invariants rather than counts.
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from cadrumo.application.modelo.registry_discovery import registry_modelo_codes
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority

from .casilla_id_grammar import screen_authority as grammar_screen
from .continuity_integrity import screen_authority as continuity_screen
from .export_ref_symmetry import screen_authority as export_ref_screen
from .grade_earned import screen_authority as grade_screen
from .modelo_capability import screen_authority as modelo_capability_screen
from .monetary_scale import screen_authority as monetary_scale_screen
from .provenance_consistency import outside_reference_index
from .provenance_consistency import screen_authority as provenance_screen
from .revision_name_window import screen_authority as revision_name_screen
from .temporal_site_agreement import screen_authority as temporal_site_screen
from .wire_type_compatibility import screen_authority as wire_type_screen

__all__ = ["FINDING_IDENTITY_CONTRACT", "SCREENS", "ScreenEntry", "run_screens"]


@dataclass(frozen=True, slots=True)
class ScreenEntry:
    """One screen, and how to reduce its result to a reportable count."""

    name: str
    run: Callable[[ValidatedRegistryAuthority, tuple[str, ...]], Sequence[object]]
    counts: str


def _divergent_transitions(authority: ValidatedRegistryAuthority, modelo_ids: tuple[str, ...]) -> Sequence[object]:
    """Return the distinct divergent type transitions, not one row per casilla.

    The screen measures per casilla, which is right, but the census a maintainer
    reads first should count what they would act on. Across the corpus 3,349
    divergent casillas resolve to 27 distinct declared-to-wire transitions, and
    the step that settles them declares transitions rather than adjudicating
    fields. Counting casillas here overstated that work by two orders of
    magnitude.
    """
    return sorted(
        {
            (str(item.casilla_type), str(item.wire_type))
            for item in wire_type_screen(authority, modelo_ids)
            if item.divergent
        }
    )


def _monetary_findings_needing_action(
    authority: ValidatedRegistryAuthority, modelo_ids: tuple[str, ...]
) -> Sequence[object]:
    """Return the monetary findings that need a decision, not the shapes reported for visibility.

    The screen reports four conditions and one of them is not a defect: a
    monetary casilla carried by several fields of one record is the official
    integer-and-decimal part split, reported so the shape is countable. It is
    the large majority of the screen's rows, so counting them here presented a
    several-fold overstatement of the work as the first number a maintainer
    reads. The screen still reports them; this census does not count them as
    findings.

    The proportion is deliberately not written as a pair of numbers. It was, and
    the totals drifted while the argument stayed true - which is the same defect
    this package exists to find, in the explanation of a screen rather than in a
    declaration.
    """
    return [item for item in monetary_scale_screen(authority, modelo_ids) if item.kind != "money_split_representation"]


def _outside_references(authority: ValidatedRegistryAuthority, modelo_ids: tuple[str, ...]) -> Sequence[object]:
    """Return the references that sit outside a manifest, not every child citing one.

    One missing reference is cited by every casilla, formula and binding that
    names it, so the raw row count exceeds the number of things to fix by roughly
    nineteen to one.
    """
    return sorted(outside_reference_index(tuple(provenance_screen(authority, modelo_ids))))


def _mixing_modelos(authority: ValidatedRegistryAuthority, modelo_ids: tuple[str, ...]) -> Sequence[object]:
    """Return only the modelos using more than one identifier grammar."""
    return [use for use in grammar_screen(authority, modelo_ids) if use.mixes]


#: What a caller may assume about any screen's finding, and nothing more.
#:
#: Every finding identifies the modelo it concerns. That is the whole contract.
#: A revision coordinate is carried by eight of the nine finding types and is
#: deliberately absent from the ninth, because a continuity chain spans
#: revisions and pinning one would name a revision the defect does not belong
#: to. A condition discriminator is carried only by the screens reporting more
#: than one condition; on a single-condition screen it would be a constant
#: column.
#:
#: Written down because assuming more than this has misread these screens seven
#: times in one campaign - a cross-screen key on `kind` reported two screens as
#: collapsing every row onto one coordinate, which was the absent attribute
#: reading as None rather than any property of the screens.
FINDING_IDENTITY_CONTRACT: tuple[str, ...] = ("modelo",)


SCREENS: tuple[ScreenEntry, ...] = (
    ScreenEntry("export_ref_symmetry", export_ref_screen, "casillas claiming an uncarried export field"),
    ScreenEntry("casilla_id_grammar", _mixing_modelos, "modelos mixing identifier grammars"),
    ScreenEntry(
        "revision_name_window",
        revision_name_screen,
        "revision names that misstate the window they declare, or claim none",
    ),
    ScreenEntry(
        "temporal_site_agreement", temporal_site_screen, "revisions whose temporal sites fall silent or disagree"
    ),
    ScreenEntry(
        "wire_type_compatibility", _divergent_transitions, "distinct casilla-to-wire type transitions that diverge"
    ),
    ScreenEntry(
        "continuity_integrity", continuity_screen, "modelos with no continuity, and chains that do not hold together"
    ),
    ScreenEntry(
        "monetary_scale",
        _monetary_findings_needing_action,
        "monetary fields whose scale is missing, unusual, or unlike their siblings",
    ),
    ScreenEntry(
        "grade_earned",
        grade_screen,
        "declared grades that do not match what their prerequisites support, in either direction",
    ),
    ScreenEntry("provenance_consistency", _outside_references, "references cited from outside their revision manifest"),
    ScreenEntry(
        "modelo_capability",
        modelo_capability_screen,
        "revisions whose declared filing rung and the machinery behind it disagree",
    ),
)


def run_screens(authority: ValidatedRegistryAuthority, modelo_ids: tuple[str, ...]) -> tuple[tuple[str, int, str], ...]:
    """Run every enrolled screen and return its name, count and what the count means."""
    return tuple((entry.name, len(entry.run(authority, modelo_ids)), entry.counts) for entry in SCREENS)


def main() -> int:
    """Print one census row per screen and a closing total; always exit 0."""
    authority = bundled_authority()
    modelo_ids = tuple(sorted(str(code) for code in registry_modelo_codes()))
    results = run_screens(authority, modelo_ids)
    for name, count, meaning in results:
        sys.stdout.write(f"screen name={name} findings={count} counts={meaning!r}\n")
    total = sum(count for _, count, _ in results)
    sys.stdout.write(f"summary screens={len(results)} findings={total}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
