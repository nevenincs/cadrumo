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
from pathlib import Path
from typing import Final

from cadrumo.application.modelo.registry_discovery import registry_modelo_codes
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority

from .casilla_id_grammar import screen_authority as grammar_screen
from .continuity_integrity import screen_authority as continuity_screen
from .export_ref_symmetry import screen_authority as export_ref_screen
from .footnote_only_wire_facts import screen_authority as footnote_only_screen
from .grade_earned import screen_authority as grade_screen
from .manifest_uncited_references import screen_authority as manifest_uncited_screen
from .modelo_capability import screen_authority as modelo_capability_screen
from .monetary_scale import screen_authority as monetary_scale_screen
from .note_label_scope import screen_corpus as note_label_scope_screen
from .note_text_drift import screen_corpus as note_text_drift_screen
from .provenance_consistency import outside_reference_index
from .provenance_consistency import screen_authority as provenance_screen
from .revision_name_window import screen_authority as revision_name_screen
from .rule_grounding_coverage import screen_authority as rule_grounding_screen
from .temporal_site_agreement import screen_authority as temporal_site_screen
from .type_convention_notes import screen_authority as type_convention_screen
from .unnumbered_note_scope import screen_corpus as unnumbered_note_scope_screen
from .wire_type_compatibility import screen_authority as wire_type_screen

#: A newline, named so the entry-point search below carries no escape.
LINE_BREAK = chr(10)

#: Named once per module rather than repeated at each read site, where a typo
#: would be a silent decode change rather than an error.
_UTF_8: Final[str] = "utf-8"

__all__ = [
    "CORPUS_SCREENS",
    "FINDING_IDENTITY_CONTRACT",
    "SCREENS",
    "SCREEN_ENTRY_POINTS",
    "CorpusScreenEntry",
    "ScreenEntry",
    "run_corpus_screens",
    "run_screens",
    "screen_findings",
    "screen_module_names",
]


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


def _fields_without_grounding(
    authority: ValidatedRegistryAuthority, modelo_ids: tuple[str, ...]
) -> Sequence[object]:
    """Return only the fields for which no official wording was located.

    The grounding screen's own total is, by construction, the count of fields
    needing a rule - which is what the pointer screen beside it already reports.
    Two rows carrying the same number read as one measurement taken twice. What
    this screen adds is the RESIDUE: the fields that no type convention and no
    design note speaks to, and which therefore have nowhere for a reviewed rule
    to come from. That is nought today and it is the number worth watching,
    because it rises the moment a design arrives without either.
    """
    return [item for item in rule_grounding_screen(authority, modelo_ids) if item.kind == "ungrounded"]


def _mixing_modelos(authority: ValidatedRegistryAuthority, modelo_ids: tuple[str, ...]) -> Sequence[object]:
    """Return only the modelos using more than one identifier grammar."""
    return [use for use in grammar_screen(authority, modelo_ids) if use.mixes]


#: What a caller may assume about any screen's FINDING, and nothing more.
#:
#: Every finding type this package defines identifies the modelo it concerns.
#: That is the whole contract, and it is a statement about the screens' own
#: findings rather than about the rows this runner reports: two entries below
#: collapse their screen onto a different unit - a reference that sits outside
#: a manifest, a wire-type transition - and those rows are a report, not a
#: finding. A caller reading this runner gets whatever the entry chose; a
#: caller calling a screen gets a finding, and a finding names its modelo.
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
        "disagreements between a declared grade and what its prerequisites support, in either direction",
    ),
    ScreenEntry("provenance_consistency", _outside_references, "references cited from outside their revision manifest"),
    ScreenEntry(
        "modelo_capability",
        modelo_capability_screen,
        "disagreements between a revision's declared filing rung and the machinery behind it",
    ),
    ScreenEntry(
        "manifest_uncited_references",
        manifest_uncited_screen,
        "manifest references no child of the revision cites",
    ),
    ScreenEntry(
        "footnote_only_wire_facts",
        footnote_only_screen,
        "fields whose wire fact sits behind a footnote pointer rather than in their own cell",
    ),
    ScreenEntry(
        "type_convention_notes",
        type_convention_screen,
        "design notes stating a wire convention for a whole AEAT type",
    ),
    ScreenEntry(
        "rule_grounding_coverage",
        _fields_without_grounding,
        "fields needing a reviewed rule for which no official wording was located at all",
    ),
)


@dataclass(frozen=True, slots=True)
class CorpusScreenEntry:
    """One screen that reads the design corpus rather than the loaded authority.

    A separate table because the signature genuinely differs - these take no
    authority and no modelo set, since a transcription belongs to a design and
    not to a revision - and forcing them through :class:`ScreenEntry` would mean
    passing arguments they ignore. They are screens in every other sense, and
    the enrolment gate treats both tables as one population: a module presenting
    either entry point must appear in the matching table and in the contributor
    README.
    """

    name: str
    run: Callable[[], Sequence[object]]
    counts: str


CORPUS_SCREENS: tuple[CorpusScreenEntry, ...] = (
    CorpusScreenEntry(
        "note_label_scope",
        note_label_scope_screen,
        "designs where one note label is defined on more than one sheet",
    ),
    CorpusScreenEntry(
        "note_text_drift",
        note_text_drift_screen,
        "note labels whose wording differs between a modelo's designs",
    ),
    CorpusScreenEntry(
        "unnumbered_note_scope",
        unnumbered_note_scope_screen,
        "designs carrying an unnumbered note, by the structure that bears on its scope",
    ),
)


def run_screens(authority: ValidatedRegistryAuthority, modelo_ids: tuple[str, ...]) -> tuple[tuple[str, int, str], ...]:
    """Run every enrolled screen and return its name, count and what the count means."""
    return tuple((entry.name, len(entry.run(authority, modelo_ids)), entry.counts) for entry in SCREENS)


#: The function names by which a module presents itself as a screen.
#:
#: Declared once because nine gates were narrow in this one way, each written
#: when `screen_authority` was the only entry point, and every one of them
#: silently stopped covering a whole class of screen the day `screen_corpus`
#: appeared. Two carried their own copy of this literal, four iterated the
#: authority table, two ran only the authority runner, and one claimed a scope
#: its body did not have. A check that recognises one shape of a thing reports
#: its blind spot as absence.
SCREEN_ENTRY_POINTS: tuple[str, ...] = ("screen_authority", "screen_corpus")


def screen_module_names() -> frozenset[str]:
    """Return every analysis module presenting a screen entry point.

    The walk lives here rather than in the gates that need it, so a new entry
    point is added in one place and every gate widens with it.
    """
    analysis = Path(__file__).resolve().parent
    return frozenset(
        path.stem
        for path in analysis.glob("*.py")
        if path.name != Path(__file__).name
        and any(f"{LINE_BREAK}def {entry}(" in path.read_text(encoding=_UTF_8) for entry in SCREEN_ENTRY_POINTS)
    )


def screen_findings(
    authority: ValidatedRegistryAuthority, modelo_ids: tuple[str, ...]
) -> tuple[tuple[str, tuple[object, ...]], ...]:
    """Return each screen's OWN findings, by name, from both tables.

    Every screen is called through its own entry point rather than through the
    table's ``run``, and the difference matters. A table entry may project - to
    the subset needing action, to an index, to the residue - so the runner can
    report one meaningful number per screen. Those projections drop findings by
    design, and a gate reading them inspects whatever survived rather than what
    the screen emits.

    The earlier version of this helper read the table, and four kinds were
    invisible to the kind-naming gate because of it: the monetary screen's
    split-representation kind, filtered out by the projection that keeps only
    findings needing action, and all three grounded kinds of the grounding
    screen, whose entry projects onto its ungrounded residue - which is empty,
    so not one of its kinds reached the gate at all. Both projections are right
    for the runner and wrong for a gate, which is why the two now read different
    functions.
    """
    import importlib

    findings: list[tuple[str, tuple[object, ...]]] = []
    for name in sorted(screen_module_names()):
        module = importlib.import_module(f"{__package__}.{name}")
        authority_entry = getattr(module, "screen_authority", None)
        if authority_entry is not None:
            findings.append((name, tuple(authority_entry(authority, modelo_ids))))
        else:
            findings.append((name, tuple(module.screen_corpus())))
    return tuple(findings)


def run_corpus_screens() -> tuple[tuple[str, int, str], ...]:
    """Run every enrolled corpus screen and return its name, count and meaning."""
    return tuple((entry.name, len(entry.run()), entry.counts) for entry in CORPUS_SCREENS)


def main() -> int:
    """Print one census row per screen and a closing total; always exit 0."""
    authority = bundled_authority()
    modelo_ids = tuple(sorted(str(code) for code in registry_modelo_codes()))
    results = run_screens(authority, modelo_ids)
    for name, count, meaning in results:
        sys.stdout.write(f"screen name={name} rows={count} counts={meaning!r}\n")
    total = sum(count for _, count, _ in results)
    # `rows`, not `findings`. Two entries report a collapsed unit rather than
    # the screen's own findings, and calling every row a finding is the exact
    # conflation the identity contract above separates. Each line's `counts`
    # label says what that screen's rows actually are.
    sys.stdout.write(f"summary screens={len(results)} rows={total}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
