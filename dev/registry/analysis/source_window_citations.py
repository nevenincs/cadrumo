"""Report sources whose declared window excludes a revision that cites them.

A ``[sources.*]`` entry's ``applies_from``/``applies_to`` is a PERIOD window. It
is overlap-checked against a revision's own span by
``source_window_applies_across``. An informativa's approving orden is published
in the January AFTER the ejercicio it governs, so it is easy to record that
presentation date as ``applies_from`` -- and the entry then excludes the very
revision whose form it approves.

The symptom is silent. The modelo still loads, because the overlap is not
checked at load time. Modelo 345 carried two of these: its base order declared a
window starting 2023-01-01 while the 2022 revision cited it in five files.

Advisory by construction, and classified rather than filtered. A non-overlapping
citation is not automatically a defect: a continuity evolution names the design a
concept came FROM, and a deadline window names the calendar of the year the
return is PRESENTED. Both cite outside their own span correctly. Suppressing them
by count would hide the population that matters; the signal labels every finding
with the role of the file that cites it and lets the reader see all of them.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable, Iterator, Mapping
from datetime import date
from typing import TypedDict

from pydantic import BaseModel

from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_base import MANIFEST_ONLY
from cadrumo.domain.calculations.registry.schema_catalogues import RegistryCatalogues
from cadrumo.domain.calculations.registry.schema_references import (
    source_window_applies_across,
)

from ..compiler.authority import compiled_bundled_authority

#: A catalogue entry's period window: ``(from, to)``, either side open.
type Window = tuple[date | None, date | None]


#: Imported, never restated. ``source_window_applies_across`` calls itself the
#: one definition of the overlap rule, "so that a diagnostic copy of a source
#: cannot answer the question differently from the source itself" -- and a
#: diagnostic carrying its own copy of the rule is precisely that.
applies_across = source_window_applies_across


def source_windows(catalogues: RegistryCatalogues) -> dict[str, Window]:
    """Return applicability windows declared by every source in the hydrated catalogue."""
    return {source_id: (entry.applies_from, entry.applies_to) for source_id, entry in catalogues.sources.items()}


def legal_windows(catalogues: RegistryCatalogues) -> dict[str, Window]:
    """Every [legal.*] reference's period window.

    A legal reference states its reach two ways. ``governs_periods_from`` /
    ``governs_periods_to`` name the PERIODS the provision governs and are the
    right axis; ``effective_from`` / ``effective_to`` name when the text was in
    force, which for an orden published after the ejercicio it governs is a
    different thing entirely. Only the period axis is admissible.
    """
    # An entry declaring only effectiveness makes NO claim about periods, so
    # there is nothing for a citation to contradict. Reading effectiveness as a
    # period window is the same category error as reading a source's publication
    # date as its applicability window: Orden HAC/657/2025 is effective 1 July
    # 2025 and governs periods in 2024, and that reading produced 59 findings of
    # which none was a defect. The missing declaration is a gap in the corpus,
    # not a wrong one.
    return {
        ref_id: (entry.governs_periods_from, entry.governs_periods_to)
        for ref_id, entry in catalogues.legal.items()
        if entry.governs_periods_from is not None
    }


def _is_delta_declaration(name: str, value: object) -> bool:
    """Whether a revision field is manifest-only authoring machinery rather than effective data.

    Overrides, removals, positions and attestations name rows by id and carry the
    edit, not the row. The rows they edit are in the hydrated families.
    """
    field = ModeloRevision.model_fields[name]
    return MANIFEST_ONLY in field.metadata and _holds_models(value)


def _holds_models(value: object) -> bool:
    """Whether a field value is, or directly contains, a registry model."""
    if isinstance(value, BaseModel):
        return True
    if isinstance(value, Mapping):
        return any(isinstance(item, BaseModel) for item in value.values())
    return isinstance(value, tuple | list | frozenset) and any(isinstance(item, BaseModel) for item in value)


def _leaves(value: object, field: str) -> Iterator[tuple[str, str]]:
    """Yield every string under ``value`` with the nearest field name that carries it."""
    if isinstance(value, str):
        yield field, value
    elif isinstance(value, BaseModel):
        for name in type(value).model_fields:
            yield from _leaves(getattr(value, name), name)
    elif isinstance(value, Mapping):
        for item in value.values():
            yield from _leaves(item, field)
    elif isinstance(value, tuple | list | frozenset):
        for item in value:
            yield from _leaves(item, field)


def cited_sources(revision: ModeloRevision, known: set[str]) -> dict[str, list[str]]:
    """Source ids named anywhere in one hydrated revision, and where.

    "Where" is ``family#field``: the revision family that holds the citation and
    the field that carries it, because the field decides the role as much as the
    family does. A field of the revision itself reads ``revision#field``. The
    revision is the hydrated one, so a citation inherited from a predecessor is
    found here exactly as one the revision authored.
    """
    found: dict[str, list[str]] = {}
    for name in ModeloRevision.model_fields:
        value = getattr(revision, name)
        if _is_delta_declaration(name, value):
            continue
        head = name if _holds_models(value) else "revision"
        for field, text in _leaves(value, name):
            if text not in known:
                continue
            where = found.setdefault(text, [])
            location = f"{head}#{field}"
            if location not in where:
                where.append(location)
    return found


#: A citation's FAMILY ROLE decides whether a non-overlapping window is a defect.
#: Two roles cite outside their own span by design and must not be swept:
#:
#: HISTORICAL -- a continuity or identifier evolution names the design a concept
#: came FROM. Citing the predecessor's window is the whole point of the record.
#:
#: FILING_YEAR -- a deadline window or filing schedule names the calendar of the
#: year the return is PRESENTED, which for an annual modelo is the year after
#: its period. Modelo 322's 2022 revision citing the 2023 calendario is correct.
#:
#: GOVERNING -- the revision's own approving orden, form spec or record design,
#: cited by the revision itself, a casilla or an export layout. Here a window
#: that excludes the revision IS the presentation-date defect.
def family_stem(source_id: str) -> str:
    """The part of a source id that survives a generation change.

    ``aeat-dr-190-2024`` and ``aeat-dr-190-2025`` are the same artefact family in
    consecutive editions; the stem is everything before the trailing year.
    """
    parts = source_id.split("-")
    # Strip exactly ONE trailing year, never every trailing number. Stripping
    # all of them collapsed "aeat-dr-190-2024" and "aeat-dr-193-2024" to the
    # same "aeat-dr", which would have called two different modelos the same
    # family and reclassified a real defect as a deliberate hand-off.
    if len(parts) > 1 and len(parts[-1]) == 4 and parts[-1].isdigit():
        parts.pop()
    return "-".join(parts)


def has_current_sibling(source_id: str, covering: set[str]) -> bool:
    """Whether a same-family source that DOES cover this revision is cited too.

    An earlier design cited beside the current one is a deliberate generational
    hand-off, not a revision resting on a stale artefact for want of a fresh one.
    Widening the earlier window to silence it would erase the hand-off.
    """
    stem = family_stem(source_id)
    mine = trailing_year(source_id)
    # Only an EARLIER source beside a covering one is superseded. A LATER source
    # beside covering earlier ones is a forward citation, and the citing file's
    # role decides whether that is correct -- modelo 280's deadline windows name
    # the calendario of each filing year's PRESENTATION year, so the newest of
    # the three sits outside the revision's span on purpose.
    return any(
        other != source_id and family_stem(other) == stem and (mine is None or (trailing_year(other) or 0) > mine)
        for other in covering
    )


def trailing_year(source_id: str) -> int | None:
    """The four-digit year a source id ends with, if it ends with one."""
    tail = source_id.split("-")[-1]
    return int(tail) if len(tail) == 4 and tail.isdigit() else None


def classify(cited_in: list[str], *, superseded: bool = False, calendar_evidence: bool = False) -> str:
    """Classify a citation whose declared window does not overlap its revision."""
    if superseded:
        return "superseded_alongside_current"
    roles = {_citation_role(where, calendar_evidence=calendar_evidence) for where in cited_in}
    return "governing_non_overlap" if "governing_non_overlap" in roles else sorted(roles)[0]


def _citation_role(where: str, *, calendar_evidence: bool) -> str:
    """Read a citation's semantic role from its family and field, never from its date."""
    location, _, key = where.partition("#")
    head = location.split("/")[0]
    if head in {"casilla_continuidad_evolutions", "identifier_evolutions"}:
        return "evolution_origin"
    if key in {"additional_source_refs", "continuidad_evidence"}:
        # A shard comparing two generations cites the earlier one on purpose.
        return "evolution_origin"
    if head in {"deadline_windows", "filing_schedules"}:
        return "presentation_calendar"
    if head == "constructs" and calendar_evidence:
        # A construct citing the SAME source a deadline window on this
        # revision cites is referencing that deadline evidence, not making an
        # independent claim. A construct citing a source NO deadline window
        # cites is governing: modelo 131's editions name a Sede help page only
        # from constructs, and reading that as a filing calendar let the same
        # source be classified two different ways across editions.
        return "presentation_calendar"
    if head == "application_links" and key in {"source_refs", "source_ref"}:
        # An application link whose surface is filing or deadline points at
        # the Sede page for the year the return is PRESENTED.
        return "presentation_calendar"
    return "governing_non_overlap"


ROLES = (
    "governing_non_overlap",
    "legal_window_non_overlap",
    "superseded_alongside_current",
    "evolution_origin",
    "presentation_calendar",
)


class SourceWindowFinding(TypedDict):
    """Structured finding emitted by the source-window citation scan."""

    modelo: str
    revision: str
    revision_span: list[str | None]
    source: str
    source_window: list[str | None]
    cited_in: list[str]
    role: str


def tally(findings: list[SourceWindowFinding]) -> dict[str, int]:
    """Count findings per role, naming every role even at zero.

    A role absent from the line reads as "not measured"; a role at zero reads as
    "measured, none found". Those are different claims.
    """
    return {role: sum(1 for f in findings if f["role"] == role) for role in ROLES}


def screen_line(findings: list[SourceWindowFinding], revisions: int, citations: int) -> str:
    """One grepable line in the grammar the other registry screens use."""
    counts = tally(findings)
    return "source_windows " + " ".join(
        [f"{role}={counts[role]}" for role in ROLES] + [f"revisions={revisions}", f"citations={citations}"]
    )


def scan(
    modelos: Iterable[ModeloDefinition],
    catalogues: RegistryCatalogues,
    only_modelo: str | None = None,
) -> tuple[list[SourceWindowFinding], int, int]:
    """Return (findings, revisions_checked, citations_checked).

    The hydrated modelos and catalogues are parameters so a gate can hand this a
    constructed registry and plant a finding of each role. A screen only
    reachable through the live corpus cannot be given a defect to catch.
    """
    windows = source_windows(catalogues)
    # A ref id could in principle be declared in both families; the source
    # catalogue wins so an id is never counted twice under two roles.
    legal = {k: v for k, v in legal_windows(catalogues).items() if k not in windows}
    known = set(windows) | set(legal)
    findings: list[SourceWindowFinding] = []
    revisions_checked = citations_checked = 0
    for modelo in sorted(modelos, key=lambda definition: str(definition.id)):
        if only_modelo not in (None, "") and str(modelo.id) != only_modelo:
            continue
        for revision_id in sorted(modelo.revisions):
            revision_findings, citations = _scan_revision(
                str(modelo.id), revision_id, modelo.revisions[revision_id], windows, legal, known
            )
            findings.extend(revision_findings)
            revisions_checked += 1
            citations_checked += citations
    return findings, revisions_checked, citations_checked


def bundled_scan(only_modelo: str | None = None) -> tuple[list[SourceWindowFinding], int, int]:
    """Scan the compiled bundled registry, the same hydration the other screens read."""
    authority = compiled_bundled_authority()
    return scan(authority.modelos, authority.catalogues, only_modelo)


def _scan_revision(
    modelo: str,
    revision_id: str,
    revision: ModeloRevision,
    windows: dict[str, Window],
    legal: dict[str, Window],
    known: set[str],
) -> tuple[list[SourceWindowFinding], int]:
    """Inspect citations of one hydrated revision against its own validity span."""
    span_from, span_to = revision.valid_from, revision.valid_to
    cited = cited_sources(revision, known)
    covering = _covering_sources(cited, windows, legal, span_from, span_to)
    findings: list[SourceWindowFinding] = []
    citations_checked = 0
    for source_id, where in cited.items():
        window = legal[source_id] if source_id in legal else windows[source_id]
        finding, checked = _citation_finding(
            modelo,
            revision_id,
            source_id,
            where,
            window,
            source_id in legal,
            covering,
            span_from,
            span_to,
        )
        citations_checked += checked
        if finding is not None:
            findings.append(finding)
    return findings, citations_checked


def _covering_sources(
    cited: dict[str, list[str]],
    windows: dict[str, Window],
    legal: dict[str, Window],
    span_from: date,
    span_to: date | None,
) -> set[str]:
    """Collect cited source ids whose declared windows cover this revision."""
    return {
        source_id
        for source_id in cited
        if applies_across(
            applies_from=(legal.get(source_id) or windows[source_id])[0],
            applies_to=(legal.get(source_id) or windows[source_id])[1],
            span_from=span_from,
            span_to=span_to,
        )
    }


def _citation_finding(
    modelo: str,
    revision: str,
    source_id: str,
    where: list[str],
    window: Window,
    is_legal: bool,
    covering: set[str],
    span_from: date,
    span_to: date | None,
) -> tuple[SourceWindowFinding | None, int]:
    """Create one non-overlap finding and return whether its window was measured."""
    applies_from, applies_to = window
    if applies_from is None and applies_to is None:
        return None, 0
    if applies_across(
        applies_from=applies_from,
        applies_to=applies_to,
        span_from=span_from,
        span_to=span_to,
    ):
        return None, 1
    return (
        {
            "modelo": modelo,
            "revision": revision,
            "revision_span": [span_from.isoformat(), span_to.isoformat() if span_to else None],
            "source": source_id,
            "source_window": [
                applies_from.isoformat() if applies_from else None,
                applies_to.isoformat() if applies_to else None,
            ],
            "cited_in": where,
            "role": _finding_role(source_id, where, is_legal, covering),
        },
        1,
    )


def _finding_role(source_id: str, where: list[str], is_legal: bool, covering: set[str]) -> str:
    """Select legal-window role or classify a source citation by its file roles."""
    if is_legal:
        return "legal_window_non_overlap"
    calendar_evidence = any(
        entry.split("#")[0].split("/")[0] in {"deadline_windows", "filing_schedules"} for entry in where
    )
    return classify(
        where,
        superseded=has_current_sibling(source_id, covering),
        calendar_evidence=calendar_evidence,
    )


def main() -> int:
    """Render source-window findings for the selected modelo scope."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--modelo", help="restrict to one modelo id")
    parser.add_argument("--screen", action="store_true", help="print only the screen line")
    arguments = parser.parse_args()

    findings, revisions_checked, citations_checked = bundled_scan(arguments.modelo)

    if arguments.screen:
        print(screen_line(findings, revisions_checked, citations_checked))
        return 0
    if arguments.json:
        print(
            json.dumps(
                {
                    "revisions_checked": revisions_checked,
                    "citations_checked": citations_checked,
                    "non_overlapping": len(findings),
                    "by_role": tally(findings),
                    "screen": screen_line(findings, revisions_checked, citations_checked),
                    "findings": findings,
                },
                indent=2,
            )
        )
        return 0

    for finding in sorted(findings, key=lambda f: (f["role"] != "governing_non_overlap", f["modelo"])):
        span = finding["revision_span"]
        window = finding["source_window"]
        print(
            f"{finding['role']:<11} modelo {finding['modelo']} rev {finding['revision']} "
            f"[{span[0]}..{span[1] or 'open'}] cites {finding['source']} "
            f"[{window[0] or 'open'}..{window[1] or 'open'}]"
        )
        for where in finding["cited_in"][:4]:
            print(f"              in {where}")
        extra = len(finding["cited_in"]) - 4
        if extra > 0:
            print(f"              and {extra} more file(s)")
    print(
        f"\nrevisions_checked={revisions_checked} citations_checked={citations_checked} non_overlapping={len(findings)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
