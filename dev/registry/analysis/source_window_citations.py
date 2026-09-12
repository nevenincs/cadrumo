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
import tomllib
from datetime import date
from pathlib import Path

from cadrumo.domain.calculations.registry.schema_references import (
    source_window_applies_across,
)

ROOT = Path(__file__).resolve().parents[3]
LEGAL = ROOT / "src/cadrumo/_data/registry/aeat/legal"
MODELOS = ROOT / "src/cadrumo/_data/registry/aeat/modelos"


#: Imported, never restated. ``source_window_applies_across`` calls itself the
#: one definition of the overlap rule, "so that a diagnostic copy of a source
#: cannot answer the question differently from the source itself" -- and a
#: diagnostic carrying its own copy of the rule is precisely that.
applies_across = source_window_applies_across


def source_windows(legal_dir: Path | None = None) -> dict[str, tuple[date | None, date | None, str]]:
    windows: dict[str, tuple[date | None, date | None, str]] = {}
    for path in sorted((legal_dir or LEGAL).rglob("*.toml")):
        payload = tomllib.loads(path.read_text(encoding="utf-8"))
        for source_id, entry in (payload.get("sources") or {}).items():
            windows[source_id] = (
                entry.get("applies_from"),
                entry.get("applies_to"),
                path.name,
            )
    return windows


def revision_spans(revision_dir: Path) -> tuple[date, date | None] | None:
    manifest = revision_dir / "revision.toml"
    if not manifest.exists():
        return None
    payload = tomllib.loads(manifest.read_text(encoding="utf-8"))
    for body in (payload.get("revisions") or {}).values():
        start = body.get("valid_from")
        if isinstance(start, date):
            end = body.get("valid_to")
            return start, end if isinstance(end, date) else None
    return None


def cited_sources(revision_dir: Path, known: set[str]) -> dict[str, list[str]]:
    """Source ids named anywhere under one revision, and where."""
    found: dict[str, list[str]] = {}
    for path in sorted(revision_dir.rglob("*.toml")):
        text = path.read_text(encoding="utf-8")
        for source_id in known:
            if f'"{source_id}"' in text:
                found.setdefault(source_id, []).append(
                    str(path.relative_to(revision_dir)).replace("\\", "/")
                )
    return found


#: A citation's FILE ROLE decides whether a non-overlapping window is a defect.
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
#: cited by revision.toml, a casilla shard or an export layout. Here a window
#: that excludes the revision IS the presentation-date defect.
def classify(cited_in: list[str]) -> str:
    roles = set()
    for where in cited_in:
        head = where.split("/")[0]
        if head in {"casilla_continuidad_evolutions", "identifier_evolutions"}:
            roles.add("evolution_origin")
        elif head in {"deadline_windows", "filing_schedules"}:
            roles.add("presentation_calendar")
        elif head == "constructs":
            roles.add("presentation_calendar")
        else:
            roles.add("governing_non_overlap")
    return "governing_non_overlap" if "governing_non_overlap" in roles else sorted(roles)[0]


ROLES = ("governing_non_overlap", "evolution_origin", "presentation_calendar")


def tally(findings: list[dict[str, object]]) -> dict[str, int]:
    """Count findings per role, naming every role even at zero.

    A role absent from the line reads as "not measured"; a role at zero reads as
    "measured, none found". Those are different claims.
    """
    return {role: sum(1 for f in findings if f["role"] == role) for role in ROLES}


def screen_line(
    findings: list[dict[str, object]], revisions: int, citations: int
) -> str:
    """One grepable line in the grammar the other registry screens use."""
    counts = tally(findings)
    return "source_windows " + " ".join(
        [f"{role}={counts[role]}" for role in ROLES]
        + [f"revisions={revisions}", f"citations={citations}"]
    )


def scan(
    legal_dir: Path | None = None,
    modelos_dir: Path | None = None,
    only_modelo: str | None = None,
) -> tuple[list[dict[str, object]], int, int]:
    """Return (findings, revisions_checked, citations_checked).

    Directories are parameters so a gate can point this at a constructed tree
    and plant a finding of each role. A screen only reachable through the live
    corpus cannot be given a defect to catch.
    """
    windows = source_windows(legal_dir)
    known = set(windows)
    findings: list[dict[str, object]] = []
    revisions_checked = citations_checked = 0

    for modelo_dir in sorted((modelos_dir or MODELOS).iterdir()):
        if not modelo_dir.is_dir():
            continue
        if only_modelo and modelo_dir.name != only_modelo:
            continue
        for revision_dir in sorted((modelo_dir / "revisions").glob("*")):
            if not revision_dir.is_dir():
                continue
            span = revision_spans(revision_dir)
            if span is None:
                continue
            revisions_checked += 1
            span_from, span_to = span
            for source_id, where in cited_sources(revision_dir, known).items():
                applies_from, applies_to, catalogue = windows[source_id]
                if applies_from is None and applies_to is None:
                    continue  # an undeclared window makes no claim to contradict
                citations_checked += 1
                if applies_across(
                    applies_from=applies_from,
                    applies_to=applies_to,
                    span_from=span_from,
                    span_to=span_to,
                ):
                    continue
                findings.append({
                    "modelo": modelo_dir.name,
                    "revision": revision_dir.name,
                    "revision_span": [
                        span_from.isoformat(),
                        span_to.isoformat() if span_to else None,
                    ],
                    "source": source_id,
                    "source_window": [
                        applies_from.isoformat() if applies_from else None,
                        applies_to.isoformat() if applies_to else None,
                    ],
                    "catalogue": catalogue,
                    "cited_in": where,
                    "role": classify(where),
                })
    return findings, revisions_checked, citations_checked


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--modelo", help="restrict to one modelo id")
    parser.add_argument("--screen", action="store_true", help="print only the screen line")
    arguments = parser.parse_args()

    findings, revisions_checked, citations_checked = scan(only_modelo=arguments.modelo)

    if arguments.screen:
        print(screen_line(findings, revisions_checked, citations_checked))
        return 0
    if arguments.json:
        print(json.dumps({
            "revisions_checked": revisions_checked,
            "citations_checked": citations_checked,
            "non_overlapping": len(findings),
            "by_role": tally(findings),
            "screen": screen_line(findings, revisions_checked, citations_checked),
            "findings": findings,
        }, indent=2))
        return 0

    governing = [f for f in findings if f["role"] == "governing_non_overlap"]
    for finding in sorted(findings, key=lambda f: (f["role"] != "governing_non_overlap", f["modelo"])):
        span = finding["revision_span"]
        window = finding["source_window"]
        print(
            f"{finding['role']:<11} modelo {finding['modelo']} rev {finding['revision']} "
            f"[{span[0]}..{span[1] or 'open'}] cites {finding['source']} "
            f"[{window[0] or 'open'}..{window[1] or 'open'}]  ({finding['catalogue']})"
        )
        for where in finding["cited_in"][:4]:
            print(f"              in {where}")
        extra = len(finding["cited_in"]) - 4
        if extra > 0:
            print(f"              and {extra} more file(s)")
    print(
        f"\nrevisions_checked={revisions_checked} citations_checked={citations_checked} "
        f"non_overlapping={len(findings)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
