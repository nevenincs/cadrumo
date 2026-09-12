"""Screen: whether a casilla's continuity chain is contiguous down its modelo's editions.

A ``continuidad_id`` asserts that a casilla in one edition is the same casilla
as one in another. :mod:`continuity_integrity` asks whether the chains a modelo
carries hold together as a set -- one grammar, more than one revision, an
evolution with endpoints. Neither it nor :mod:`edition_delta_status` asks the
question this screen owns: whether a chain runs DOWN the edition sequence
without a hole in it.

The difference matters because inheritance walks the sequence. A merge takes a
stated row to supersede the inherited row of the same lineage in the edition
before it; a chain that skips an edition in between has no row there to
supersede, so the box is materialised, then absent, then materialised again,
and nothing in the corpus says it went away. A chain like that validates,
reads as continuity everywhere it is quoted, and is wrong in the one dimension
continuity exists to state.

Conditions reported:

- ``chain_skips_edition`` - a lineage carried by two editions of a modelo and
  absent from an edition between them, which neither retires it nor declares it
  repurposed. A box does not cease to exist and return silently.
- ``chain_resumed_after_retirement`` - a lineage a ``retired`` evolution
  withdrew, carried again by a later edition. Retirement is the corpus's own
  statement that the box is gone; re-using the identifier afterwards asserts the
  opposite without withdrawing the statement.
- ``chain_ambiguous_in_edition`` - one edition's rows carry the same lineage
  twice, so a successor superseding it has two rows to choose between. The edge
  screen reports this only for a pair it examines; a modelo whose editions are
  all rooted never reaches that check, which is how the condition hides.
- ``chain_across_pending_root`` - a successor sharing a lineage with the edition
  before it while declaring a root FOR WANT OF LINEAGE. The root says the chain
  could not be stated; the rows state it. The root is stale, and each of these
  is evidence the edge is closer to migration than its own manifest claims.
- ``chain_across_root_by_law`` - the same sharing across a root the LAW gives:
  parallel scheme variants, or a successor withholding by design. Here the two
  claims contradict rather than lag -- the editions do not succeed one another,
  so rows asserting one identity across them assert something the edition
  structure denies.
- ``evolution_endpoint_unknown`` - an evolution whose ``from_revision`` or
  ``to_revision`` names an edition the modelo does not declare. The transition
  it records has no site.
- ``evolution_declared_off_endpoint`` - an evolution whose ``to_revision`` is
  not the edition declaring it. The record then sits where the transition did
  not happen, and the edition it describes does not carry it.
- ``evolution_restates_ancestor`` - an evolution whose ``from_revision`` is not
  the declaring edition's immediate predecessor, where every edition in between
  carries the chain. The adjacent step is already a record of its own, so this
  one restates it: the evolution family's form of the same full-copy disease
  :mod:`edition_delta_status` measures as ``member_restated``. Measured on this
  corpus the pattern is quadratic -- one modelo's sixth edition declares a
  transition from each of the five before it for the same chains.
- ``evolution_without_chain_members`` - an evolution naming a lineage no casilla
  of either endpoint edition carries.

Measured rather than reported as a fault:

- ``chain_shared_across_modelos`` - one lineage carried by casillas of two
  different modelos. Continuity is a statement about one form's own box, so a
  shared identifier is more likely a shared LABEL than a shared identity; but
  the corpus has never declared whether cross-modelo identity is permitted, and
  a screen must not settle that by counting it as a defect.
- ``evolution_spans_absent_editions`` - a non-adjacent evolution whose skipped
  editions do NOT carry the chain. The span is then the only way to state the
  transition, and reporting it would be reporting the corpus for being right.

Read from the authored TOML through :mod:`edition_delta_status`'s own scan, not
through the validated authority, for two reasons. The question is about what a
person authored, which is the same reason that screen reads the tree. And the
authority materialises an inherited row exactly like a stated one, so the hole
this screen looks for closes before the authority can be asked about it.

Ordering is by ``valid_from``, which is the only site stating when an edition
begins and is mandatory, and is the ordering the migration tool uses.

The screen exits 0 whatever it finds. It reports findings; it does not gate.
"""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from typing import Any, Final

from .edition_delta_status import (
    EditionStatus,
    _bundled_registry_root,
    _root_kind,
    scan_registry,
)

__all__ = [
    "CONDITIONS",
    "MEASUREMENTS",
    "ChainFinding",
    "Evolution",
    "census",
    "read_evolutions",
    "screen",
]

_REVISIONS: Final = "revisions"
_EVOLUTIONS: Final = "casilla_continuidad_evolutions"
_LINEAGE: Final = "continuidad_id"
_RETIRED: Final = "retired"
#: The evolution kind that states a lineage moved to a different box. A
#: repurpose is a legitimate reason for a lineage to be absent from an edition,
#: so it excuses a hole the way a retirement does.
_REPURPOSED: Final = "repurposed"

#: Every condition this screen can report, declared once so the set cannot be
#: misread off the source.
CONDITIONS: Final[tuple[str, ...]] = (
    "chain_skips_edition",
    "chain_resumed_after_retirement",
    "chain_ambiguous_in_edition",
    "chain_across_pending_root",
    "chain_across_root_by_law",
    "evolution_endpoint_unknown",
    "evolution_declared_off_endpoint",
    "evolution_restates_ancestor",
    "evolution_without_chain_members",
)

#: Measured beside the conditions and never counted as findings.
MEASUREMENTS: Final[tuple[str, ...]] = (
    "chain_shared_across_modelos",
    "evolution_spans_absent_editions",
)


@dataclass(frozen=True, slots=True)
class ChainFinding:
    """One located break in a continuity chain."""

    modelo: str
    edition: str
    kind: str
    chain: str
    detail: str


@dataclass(frozen=True, slots=True)
class Evolution:
    """One authored continuity evolution record, with the edition that declares it."""

    modelo: str
    edition: str
    chain: str
    from_revision: str
    to_revision: str
    kind: str


def read_evolutions(registry_root: Path, *, modelo_ids: tuple[str, ...] = ()) -> tuple[Evolution, ...]:
    """Read every authored continuity evolution below a registry root.

    Evolutions may sit in the edition manifest or in any fragment under the
    edition, which is why every TOML file below an edition is read for the
    section rather than one expected file. A record missing an endpoint or a
    lineage is skipped here and caught by the schema; this screen reports what
    the corpus states, not what it fails to parse.
    """
    found: list[Evolution] = []
    modelos_root = registry_root / "modelos"
    if not modelos_root.is_dir():
        return ()
    for modelo_dir in sorted(path for path in modelos_root.iterdir() if path.is_dir()):
        if modelo_ids and modelo_dir.name not in modelo_ids:
            continue
        editions_dir = modelo_dir / _REVISIONS
        if not editions_dir.is_dir():
            continue
        for edition_dir in sorted(path for path in editions_dir.iterdir() if path.is_dir()):
            edition_id = edition_dir.name
            for path in sorted(edition_dir.rglob("*.toml")):
                table = tomllib.loads(path.read_text(encoding="utf-8")).get(_REVISIONS, {}).get(edition_id, {})
                declared = table.get(_EVOLUTIONS) if isinstance(table, dict) else None
                for record in declared if isinstance(declared, list) else ():
                    if not isinstance(record, dict):
                        continue
                    chain = record.get(_LINEAGE)
                    start, end = record.get("from_revision"), record.get("to_revision")
                    if not (isinstance(chain, str) and isinstance(start, str) and isinstance(end, str)):
                        continue
                    found.append(
                        Evolution(
                            modelo=modelo_dir.name,
                            edition=edition_id,
                            chain=chain,
                            from_revision=start,
                            to_revision=end,
                            kind=str(record.get("evolution_kind", "")),
                        )
                    )
    return tuple(found)


def _ordered(statuses: Iterable[EditionStatus]) -> tuple[EditionStatus, ...]:
    """A modelo's editions in the order inheritance walks them."""
    return tuple(sorted(statuses, key=lambda status: (status.valid_from, status.edition)))


def _chains_of(status: EditionStatus) -> Counter[str]:
    """Every lineage the edition's rows state, with how many rows state it."""
    return Counter(lineage for _, lineage in status.stated_keys if lineage is not None)


def _excused(evolutions: Iterable[Evolution], chain: str, edition: str) -> bool:
    """Whether an evolution explains this lineage's absence from this edition.

    A retirement at or before the edition, or a repurpose touching it, is the
    corpus stating that the box left the form. Both are legitimate reasons for
    the hole, and a screen that ignored them would report every properly
    withdrawn box as a break.
    """
    return any(
        evolution.chain == chain
        and evolution.kind in {_RETIRED, _REPURPOSED}
        and edition in {evolution.from_revision, evolution.to_revision}
        for evolution in evolutions
    )


def modelo_findings(
    modelo: str,
    statuses: tuple[EditionStatus, ...],
    evolutions: tuple[Evolution, ...],
) -> tuple[ChainFinding, ...]:
    """Return one modelo's chain-contiguity findings.

    Takes the modelo's editions and evolutions rather than the whole corpus, as
    the sibling screens' per-unit functions do, so a test can hand it a tree
    carrying one constructed defect and assert the KIND reported rather than
    inspecting the index underneath it.
    """
    findings: list[ChainFinding] = []
    ordered = _ordered(statuses)
    positions = {status.edition: index for index, status in enumerate(ordered)}
    carried = {status.edition: _chains_of(status) for status in ordered}
    mine = tuple(evolution for evolution in evolutions if evolution.modelo == modelo)

    for status in ordered:
        for chain, count in sorted(carried[status.edition].items()):
            if count > 1:
                findings.append(
                    ChainFinding(
                        modelo=modelo,
                        edition=status.edition,
                        kind="chain_ambiguous_in_edition",
                        chain=chain,
                        detail=f"{count} rows of this edition carry the lineage",
                    )
                )

    # A hole: carried before and after, absent in between, with nothing in the
    # corpus saying the box left the form.
    spans: dict[str, list[int]] = defaultdict(list)
    for index, status in enumerate(ordered):
        for chain in carried[status.edition]:
            spans[chain].append(index)
    for chain, seen in sorted(spans.items()):
        for gap in range(min(seen), max(seen)):
            if gap in seen:
                continue
            absent = ordered[gap]
            if _excused(mine, chain, absent.edition):
                continue
            findings.append(
                ChainFinding(
                    modelo=modelo,
                    edition=absent.edition,
                    kind="chain_skips_edition",
                    chain=chain,
                    detail=(
                        f"carried by {ordered[min(seen)].edition} and {ordered[max(seen)].edition}, "
                        f"absent here, neither retired nor repurposed"
                    ),
                )
            )

    # A retirement is a statement; carrying the lineage again after it withdraws
    # nothing and contradicts it.
    for evolution in mine:
        if evolution.kind != _RETIRED or evolution.to_revision not in positions:
            continue
        retired_at = positions[evolution.to_revision]
        for later in ordered[retired_at + 1 :]:
            if evolution.chain in carried[later.edition]:
                findings.append(
                    ChainFinding(
                        modelo=modelo,
                        edition=later.edition,
                        kind="chain_resumed_after_retirement",
                        chain=evolution.chain,
                        detail=f"retired at {evolution.to_revision}, carried again here",
                    )
                )

    # A chain crossing an edge whose successor declares it has no predecessor.
    # WHICH root it is decides what the sharing means, so the two are never
    # pooled: a root pending lineage is stale in the face of a stated chain,
    # while a root the law gives is contradicted by one.
    for predecessor, successor in pairwise(ordered):
        if not successor.declares_no_predecessor:
            continue
        pending = _root_kind(successor.root_reason) == "root_pending_lineage"
        kind = "chain_across_pending_root" if pending else "chain_across_root_by_law"
        detail = (
            f"shared with {predecessor.edition}, which this edition roots away from for want of lineage"
            if pending
            else f"shared with {predecessor.edition}, which this edition declares by law it does not succeed"
        )
        findings.extend(
            ChainFinding(modelo=modelo, edition=successor.edition, kind=kind, chain=chain, detail=detail)
            for chain in sorted(set(carried[predecessor.edition]) & set(carried[successor.edition]))
        )

    for evolution in mine:
        unknown = [name for name in (evolution.from_revision, evolution.to_revision) if name not in positions]
        if unknown:
            findings.append(
                ChainFinding(
                    modelo=modelo,
                    edition=evolution.edition,
                    kind="evolution_endpoint_unknown",
                    chain=evolution.chain,
                    detail=f"names {', '.join(unknown)}, which the modelo does not declare",
                )
            )
            continue
        if evolution.to_revision != evolution.edition:
            findings.append(
                ChainFinding(
                    modelo=modelo,
                    edition=evolution.edition,
                    kind="evolution_declared_off_endpoint",
                    chain=evolution.chain,
                    detail=f"records a transition into {evolution.to_revision}, not into the declaring edition",
                )
            )
        start, end = positions[evolution.from_revision], positions[evolution.to_revision]
        skipped = ordered[start + 1 : end]
        if skipped and all(evolution.chain in carried[status.edition] for status in skipped):
            findings.append(
                ChainFinding(
                    modelo=modelo,
                    edition=evolution.edition,
                    kind="evolution_restates_ancestor",
                    chain=evolution.chain,
                    detail=(
                        f"{evolution.from_revision} -> {evolution.to_revision} spans {end - start} steps, "
                        f"and {', '.join(status.edition for status in skipped)} carry the chain"
                    ),
                )
            )
        endpoints = carried[evolution.from_revision] + carried[evolution.to_revision]
        if evolution.chain not in endpoints:
            findings.append(
                ChainFinding(
                    modelo=modelo,
                    edition=evolution.edition,
                    kind="evolution_without_chain_members",
                    chain=evolution.chain,
                    detail=f"no casilla of {evolution.from_revision} or {evolution.to_revision} carries it",
                )
            )
    return tuple(findings)


def screen(statuses: tuple[EditionStatus, ...], evolutions: tuple[Evolution, ...]) -> tuple[ChainFinding, ...]:
    """Screen every modelo's chains for contiguity down its edition sequence."""
    by_modelo: dict[str, list[EditionStatus]] = defaultdict(list)
    for status in statuses:
        by_modelo[status.modelo].append(status)
    findings: list[ChainFinding] = []
    for modelo, editions in sorted(by_modelo.items()):
        findings.extend(modelo_findings(modelo, tuple(editions), evolutions))
    return tuple(findings)


def spans_over_absent_editions(statuses: tuple[EditionStatus, ...], evolutions: tuple[Evolution, ...]) -> int:
    """Non-adjacent evolutions whose skipped editions do not carry the chain.

    The complement of ``evolution_restates_ancestor`` within the non-adjacent
    population, and the reason that condition tests the skipped editions rather
    than the span alone: an evolution reaching over a stretch where the box was
    not on the form states the transition the only way it can be stated.
    """
    by_modelo: dict[str, list[EditionStatus]] = defaultdict(list)
    for status in statuses:
        by_modelo[status.modelo].append(status)
    total = 0
    for modelo, editions in by_modelo.items():
        ordered = _ordered(editions)
        positions = {status.edition: index for index, status in enumerate(ordered)}
        carried = {status.edition: set(_chains_of(status)) for status in ordered}
        for evolution in evolutions:
            if evolution.modelo != modelo:
                continue
            if evolution.from_revision not in positions or evolution.to_revision not in positions:
                continue
            skipped = ordered[positions[evolution.from_revision] + 1 : positions[evolution.to_revision]]
            if skipped and not all(evolution.chain in carried[status.edition] for status in skipped):
                total += 1
    return total


def census(statuses: tuple[EditionStatus, ...], evolutions: tuple[Evolution, ...]) -> dict[str, int]:
    """Corpus-wide chain coverage, reported beside the findings."""
    per_modelo: dict[str, set[str]] = defaultdict(set)
    chained_rows = 0
    for status in statuses:
        for _, lineage in status.stated_keys:
            if lineage is not None:
                per_modelo[status.modelo].add(lineage)
                chained_rows += 1
    modelos_per_chain: Counter[str] = Counter()
    for chains in per_modelo.values():
        modelos_per_chain.update(chains)
    return {
        "editions": len(statuses),
        "chained_rows": chained_rows,
        "chains": sum(len(chains) for chains in per_modelo.values()),
        "evolutions": len(evolutions),
        "chain_shared_across_modelos": sum(1 for count in modelos_per_chain.values() if count > 1),
        "evolution_spans_absent_editions": spans_over_absent_editions(statuses, evolutions),
    }


def _payload(findings: tuple[ChainFinding, ...], counts: Mapping[str, int]) -> dict[str, Any]:
    tally = Counter(finding.kind for finding in findings)
    return {
        "census": dict(counts),
        "conditions": {kind: tally.get(kind, 0) for kind in CONDITIONS},
        "findings": [
            {
                "modelo": finding.modelo,
                "edition": finding.edition,
                "kind": finding.kind,
                "chain": finding.chain,
                "detail": finding.detail,
            }
            for finding in findings
        ],
    }


def _signal_lines(findings: tuple[ChainFinding, ...], counts: Mapping[str, int]) -> list[str]:
    """The diffable record form: fixed fields, deterministic order, no paths."""
    tally = Counter(finding.kind for finding in findings)
    per_modelo: Counter[str] = Counter(finding.modelo for finding in findings)
    lines = [
        "# chain_contiguity schema=1",
        "census " + " ".join(f"{key}={value}" for key, value in sorted(counts.items())),
        " ".join(["condition", *(f"{kind}={tally.get(kind, 0)}" for kind in CONDITIONS)]),
        " ".join(["clean", *(kind for kind in CONDITIONS if not tally.get(kind))]) or "clean none",
    ]
    lines += [f"modelo {modelo} findings={count}" for modelo, count in sorted(per_modelo.items())]
    return lines


def main() -> int:
    """Print the chain-contiguity signal; always exit 0."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--registry-root", type=Path, default=None, help="registry root holding modelos/")
    parser.add_argument("--modelo", action="append", default=[], help="restrict to these modelo ids")
    parser.add_argument("--findings", action="store_true", help="print one row per finding as well")
    parser.add_argument("--json", action="store_true", help="print the full report as JSON instead")
    parser.add_argument("--lines", action="store_true", help="print the diffable record lines")
    arguments = parser.parse_args()

    registry_root = (arguments.registry_root or _bundled_registry_root()).resolve()
    modelo_ids = tuple(arguments.modelo)
    statuses = scan_registry(registry_root, modelo_ids=modelo_ids)
    evolutions = read_evolutions(registry_root, modelo_ids=modelo_ids)
    findings = screen(statuses, evolutions)
    counts = census(statuses, evolutions)

    if arguments.json:
        sys.stdout.write(json.dumps(_payload(findings, counts), indent=2, sort_keys=True) + "\n")
        return 0

    if arguments.findings:
        for finding in findings:
            sys.stdout.write(
                f"chain modelo={finding.modelo} edition={finding.edition} kind={finding.kind} "
                f"chain={finding.chain} detail={finding.detail!r}\n"
            )

    if arguments.lines:
        for line in _signal_lines(findings, counts):
            sys.stdout.write(line + "\n")
        return 0

    tally = Counter(finding.kind for finding in findings)
    rule = "=" * 78
    out = [
        "CHAIN CONTIGUITY",
        rule,
        "  corpus     " + "   ".join(f"{key} {value:,}" for key, value in sorted(counts.items())),
        "",
        "CONDITIONS",
    ]
    active = [(kind, tally[kind]) for kind in CONDITIONS if tally[kind]]
    out += [f"  {kind:<34} {count:>8,}" for kind, count in active] or ["  all clean"]
    clean = [kind for kind in CONDITIONS if not tally[kind]]
    if clean and active:
        out.append("  clean: " + ", ".join(clean))
    out.append("")
    by_modelo = Counter(finding.modelo for finding in findings)
    if by_modelo:
        out.append("MODELOS  (sorted by findings)")
        out += [
            f"  {modelo:<8} {count:>8,}"
            for modelo, count in sorted(by_modelo.items(), key=lambda item: (-item[1], item[0]))
        ]
        out.append("")
    sys.stdout.write("\n".join(out) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
