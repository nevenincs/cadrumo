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
- ``chain_across_recoverable_root`` - the sharing across a root whose stated
  cause is work rather than law: an unretired withdrawal, a row order the raw
  tree cannot decide. Like a pending root this reads as stale, and for a
  sharper reason -- the chain is not merely stated ahead of the root, it is
  complete, and the only thing between the edge and migration is the cause the
  root names.
- ``chain_across_root_by_law`` - the same sharing across a root the LAW gives:
  parallel scheme variants, a successor withholding by design, two editions
  overlapping in period. Here the two claims contradict rather than lag -- the
  editions do not succeed one another, so rows asserting one identity across
  them assert something the edition structure denies.

  This condition once carried the prior that the CHAIN is the likelier error.
  The corpus's only two instances disprove it, and for a reason worth stating
  because it is not specific to them: one of the causes the law set admits,
  ``overlapping predecessor``, is not authored at all. The migration tool mints
  it from a predicate that compares period SELECTORS and never reads
  ``valid_from``/``valid_to``, renders it into prose that reads like a
  judgement, and this screen then classifies that prose as law. 308's two
  editions meet at 2011-06-30 and 2011-07-01, so the rows crossing the root are
  right and the root is wrong. Where the cause is minted rather than reasoned,
  expect the ROOT to be the error.
- ``evolution_endpoint_unknown`` - an evolution whose ``from_revision`` or
  ``to_revision`` names an edition the modelo does not declare. The transition
  it records has no site.
- ``evolution_declared_off_endpoint`` - an evolution whose ``to_revision`` is
  not the edition declaring it. The record then sits where the transition did
  not happen, and the edition it describes does not carry it.
- ``evolution_restates_ancestor`` - an evolution whose ``from_revision`` is not
  the declaring edition's immediate predecessor, where every edition in between
  carries the chain AND the adjacent step has a record of its own, so this one
  restates it: the evolution family's form of the same full-copy disease
  :mod:`edition_delta_status` measures as ``member_restated``. Measured on this
  corpus the pattern is quadratic -- one modelo's sixth edition declares a
  transition from each of the five before it for the same chains.
- ``evolution_spans_unrecorded_step`` - the same non-adjacent span where the
  adjacent step has NO record, so the span is the only statement of that
  transition. Split out because an earlier wording asserted the adjacent record
  existed instead of checking; at the split, 118 of the 669 non-adjacent spans had
  none, and dropping those as duplicates would have deleted the transition. The
  remedy is the opposite one, authoring the adjacent record.

  THE TWO HALVES SIT AT OPPOSITE ENDS OF A MODELO'S HISTORY, which is what makes
  the split worth acting on rather than merely correct. Restatement accumulates
  FORWARD: each new edition can restate every transition below it, so the newest
  edition carries the most. The unrecorded step accumulates BACKWARD: an early
  transition whose adjacent record nobody authored stays unrecorded forever, so
  the oldest editions carry the most and the newest carry none. The same modelo
  shows both slopes at once on the same chains. Read a count on a LATE edition as
  deletable duplication and the same count on an EARLY edition as a missing
  record, and never pool them into one backlog: the first shrinks by removing
  statements, the second only by adding them.
- ``evolution_without_chain_members`` - an evolution naming a lineage neither
  endpoint edition MATERIALISES, so the transition it records has no rows. Asked
  of the materialised edition, not the stated rows: a delta edition inherits
  what it does not restate, and reading its stated rows called all 258 of
  modelo 714's evolutions orphans while every one of them had its site.

- ``chain_across_structural_root`` - the sharing across a root whose cause is
  ``official_structure_differs``: the successor's official record design genuinely
  differs from the predecessor's, a reordering or a byte shift, so no lineage work
  lets the predecessor materialise it. Authored from a per-family materialisation
  harness rather than inferred, which makes it a fact about the record design and
  NOT debt -- every one of the corpus's sites carries a reason containing a
  measurement. Split out of ``chain_across_root_by_law`` and not out of
  recoverable: the owning screen classifies this cause as ``root_by_law``, so
  without the split these crossings would read as the form forbidding
  inheritance. Both kinds are permanent and the EVIDENCE is what differs -- a
  norm against a harness measurement -- and reporting one as the other credits
  the legislator with what the record design did.
- ``chain_partially_grounded`` - a chain with some links grounded and some not.
  Exemption is per OCCURRENCE and bilateral: an occurrence is exempt only once
  every link touching it is grounded, so grounding one link exempts the
  occurrences at its ends whose other links are also grounded -- a final-link
  pass buys the terminal occurrence and nothing else. It does NOT buy nothing, and
  an earlier wording here said it did: 322 carries 114 chains grounded at their
  final link only and sits at 148 exempt of 847 occurrences.
- ``ruling_reference_unknown`` - an adjudicated ruling naming a casilla the
  edition it names does not carry. The rulings file is the seeder's canonical
  input for a modelo it will not seed mechanically, so a ruling pointing at a row
  that is not there directs the seeder at nothing.

Measured rather than reported as a fault:

- ``chain_fully_grounded`` - chains every link of which is grounded. GROUNDED means the
  successor occurrence states ``continuidad_origin = "grounded"`` and nothing else does:
  ``seeded`` is the seeder having identified the row and not yet evidenced it, and the
  absence origins resolve a row for LEDGER totality while discharging no link here. A
  census of non-``None`` origins therefore overstates grounding by exactly those
  populations -- see the note at ``_GROUNDED``.
- ``chain_links_to_ground`` - the remaining ungrounded links, summed over chains
  that are not yet complete. Links rather than chains, because the work is per
  link and a chain part-way through still needs each of the rest.
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
#: What a crossing chain is called for each root kind, and the wording that
#: says why. Keyed on the owning screen's own classification so the two cannot
#: drift: when that screen learned to tell a recoverable root from a terminal
#: one, a two-way split here would have kept reporting 355 crossings as
#: contradictions of law when they are evidence of a stale root.
_CHAIN_ROOT_KINDS: Final[dict[str, tuple[str, str]]] = {
    "root_pending_lineage": ("chain_across_pending_root", "roots away from for want of lineage"),
    "root_recoverable": ("chain_across_recoverable_root", "roots away from for a cause that is work, not law"),
    "root_by_law": ("chain_across_root_by_law", "declares by law it does not succeed"),
}

#: The root cause naming a MEASURED structural difference against the prior
#: edition. Authored from a per-family materialisation harness rather than
#: inferred, so it is a fact about the record design and not a task: a chain
#: crossing such a root is expected and permanent.
_STRUCTURE_DIFFERS: Final = "official_structure_differs"

#: The evolution kind that states a lineage moved to a different box. A
#: repurpose is a legitimate reason for a lineage to be absent from an edition,
#: so it excuses a hole the way a retirement does.
_REPURPOSED: Final = "repurposed"

#: The measurement's version, bumped on any change to what the conditions
#: COUNT, so a lane diffing two runs can tell instrument movement from corpus
#: movement instead of having to remember which changed.
_SIGNAL_SCHEMA: Final = 6

#: Every condition this screen can report, declared once so the set cannot be
#: misread off the source.
CONDITIONS: Final[tuple[str, ...]] = (
    "chain_skips_edition",
    "chain_resumed_after_retirement",
    "chain_ambiguous_in_edition",
    "chain_across_pending_root",
    "chain_across_recoverable_root",
    "chain_across_structural_root",
    "chain_across_root_by_law",
    "evolution_endpoint_unknown",
    "evolution_declared_off_endpoint",
    "evolution_restates_ancestor",
    "evolution_spans_unrecorded_step",
    "evolution_without_chain_members",
    "chain_partially_grounded",
    "ruling_reference_unknown",
)

#: The adjudicated-rulings file, which is the seeder's canonical input for a
#: modelo it will not seed mechanically. Read raw: its entries are TOML before
#: they are anything else, and this screen must keep reporting when the domain
#: does not import.
_RULINGS_FILE: Final = Path(__file__).with_name("casilla_lineage_rulings.toml")

#: Ruling fields whose entries are `predecessor>successor` pairs spanning two
#: editions, versus those naming a SUCCESSOR row alone. Getting this wrong is
#: how a check reports 167 breakages where there are 2: the single-id lists name
#: successor rows only, and `merged` entries are compound `A + B` expressions
#: rather than ids at all.
#: Every limitation this screen can record. Declared for the same reason the delta
#: screen declares its own: a limitation's name otherwise exists only as a literal at its
#: emit site, so one that stops being emitted is caught by nothing -- and a lost
#: limitation reads as an axis that was measured and found clean.
LIMITATIONS: Final[tuple[str, ...]] = (
    "ruling_references_unchecked",
    "rulings_unreadable",
)


#: The scope-dependent limitation's prefix, named once so the emit site and the
#: per-call reset cannot drift apart.
_UNCHECKED_REFERENCES: Final = "ruling_references_unchecked:"

_RULING_PAIR_FIELDS: Final = ("grounded", "held", "withheld")
_RULING_SUCCESSOR_FIELDS: Final = ("new_on_form", "not_on_form")

#: The origin marking a link as established from cited evidence rather than
#: inferred from a predicate.
#: The ONLY ``continuidad_origin`` value that discharges a link. Named here with the
#: values that do NOT, because the field answers two different questions and a census
#: counting non-``None`` origins reports them as one:
#:
#:   grounded                    3,232 rows   discharges the link
#:   seeded                      3,932 rows   the seeder IDENTIFIED the row; no evidence yet
#:   new_on_form                   428 rows   absence origins: they resolve a row for LEDGER
#:   predecessor_edition_silent    349 rows   totality and discharge NOTHING here
#:   not_on_form                    32 rows
#:   None                       10,109 rows
#:
#: So 4,741 rows carry an origin and still owe their link, and 83% of those are the
#: seeder's own ``seeded`` output -- the corpus is not mislabelled, it is mid-pipeline.
#:
#: DO NOT REACH FOR ``CasillaLineageOrigin.continues_a_chain``. The domain owns the typed
#: vocabulary and that property is True for ``grounded`` AND ``seeded``, because it answers
#: whether the row ASSERTS a continuation -- a different question from whether the link is
#: grounded, and the one a reader looking for a ready-made predicate finds first. This
#: screen deliberately compares a literal rather than importing the enum, because it must
#: keep reporting when the domain cannot be imported; the cost is that a renamed enum value
#: would silently make every link read ungrounded, taking ``chain_links_to_ground`` from
#: 7,253 to the full 10,473 with no error anywhere. A test pins the literal against the enum
#: so that rename fails loudly instead.
#: Modelo 390 is the worked example: 49% of its chained rows carry an origin and EIGHT are
#: grounded, so it reads as half-finished on the ledger axis and untouched on this one.
#: Twice in one session a reader concluded from an origin census that grounding work was
#: done. Counts measured 2026-09-13 and will drift; the partition will not.
_GROUNDED: Final = "grounded"

#: Measured beside the conditions and never counted as findings.
MEASUREMENTS: Final[tuple[str, ...]] = (
    "chain_fully_grounded",
    "chain_links_to_ground",
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


def ruling_reference_findings(
    statuses: tuple[EditionStatus, ...], path: Path = _RULINGS_FILE
) -> tuple[ChainFinding, ...]:
    """Name every adjudicated ruling that references a row its edition does not carry.

    A ruling is the seeder's only path for a modelo it will not seed
    mechanically, so a broken reference there is not a refused row: it raises
    out of the ruling application and takes the WHOLE modelo. Worse, it stays
    invisible while the modelo sits on the exclusion list, which is exactly
    where adjudication-only modelos live — so the corpus can accrue these and
    meet them all at once, at the moment a campaign finishes and the exclusion
    lifts.

    `merged` is deliberately not checked: its entries are compound `A + B`
    expressions naming two rows that fold into one, not identifiers, and
    treating them as ids reports every one of them as broken.

    A ZERO HERE MEANS NOTHING WITHOUT THE SCOPE. The rulings file is global while
    the statuses handed in may be scoped to one modelo, and an endpoint whose
    edition was never scanned is skipped -- correctly, since the question cannot
    be answered, but silently. Scoped to one modelo, every one of the corpus's
    24 ruling endpoints skips -- 2,937 individual casilla references -- and this
    returns no findings, which reads as a clean bill for precisely the condition
    whose whole argument above is that these accrue invisibly. So the count of
    unchecked REFERENCES is emitted as a limitation, counted the way the loop
    counts rather than per ruling or per endpoint, so a reader seeing zero
    findings can tell whether that is coverage or absence.
    """
    if not path.is_file():
        return ()
    try:
        document = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        _note_ruling_limitation(f"rulings_unreadable: {type(exc).__name__}")
        return ()
    rows: dict[tuple[str, str], set[str]] = defaultdict(set)
    for status in statuses:
        rows[(status.modelo, status.edition)].update(status.rows_by_id)
    # This answer is SCOPE-DEPENDENT, so it belongs to this call and not to the
    # process. `_note_ruling_limitation` dedupes on exact text, which does not
    # help: each scope produces a different string, so across two calls they
    # accumulate and a whole-corpus run whose own answer is zero inherits every
    # earlier scope's. A harness that runs a scoped scan and then a full one --
    # the normal way to verify a scope fix -- then gets a full scan declaring
    # thousands of references unchecked that it actually checked. The limitation
    # would outlive the question it answers, which is the species of defect it
    # was added to report.
    _RULING_LIMITATIONS[:] = [text for text in _RULING_LIMITATIONS if not text.startswith(_UNCHECKED_REFERENCES)]
    findings: list[ChainFinding] = []
    unchecked = 0
    for ruling in document.get("ruling", ()):
        modelo = str(ruling.get("modelo", ""))
        predecessor, successor = str(ruling.get("predecessor", "")), str(ruling.get("successor", ""))
        checks: list[tuple[str, str, str]] = []
        for field in _RULING_PAIR_FIELDS:
            for entry in ruling.get(field, ()) or ():
                left, separator, right = str(entry).partition(">")
                if separator:
                    checks += [(predecessor, left, field), (successor, right, field)]
                else:
                    checks.append((predecessor, left, field))
        for field in _RULING_SUCCESSOR_FIELDS:
            checks += [(successor, str(entry), field) for entry in ruling.get(field, ()) or ()]
        for edition, casilla, field in checks:
            known = rows.get((modelo, edition))
            if known is None:
                unchecked += 1
                continue
            if not casilla or casilla in known:
                continue
            findings.append(
                ChainFinding(
                    modelo=modelo,
                    edition=edition,
                    kind="ruling_reference_unknown",
                    chain=casilla,
                    detail=f"ruling `{field}` names a row this edition does not carry",
                )
            )
    if unchecked:
        _note_ruling_limitation(
            f"{_UNCHECKED_REFERENCES} {unchecked} casilla references across the rulings name an "
            "edition this scan did not read, so they were not checked"
        )
    return tuple(findings)


def _note_ruling_limitation(text: str) -> None:
    if text not in _RULING_LIMITATIONS:
        _RULING_LIMITATIONS.append(text)


_RULING_LIMITATIONS: list[str] = []


def grounding_by_chain(
    statuses: tuple[EditionStatus, ...],
) -> dict[str, tuple[int, int]]:
    """Per chain, how many of its links are grounded and how many links it has.

    A chain's LINKS are the steps between consecutive editions carrying it. The
    role exemption is per-occurrence and bilateral -- an occurrence is exempt
    only when every link touching it is grounded -- so a chain discharges as a
    whole or not at all. A two-edition chain is one link and grounding it
    exempts both ends; a four-edition chain is three links and grounding two of
    them leaves the middle occurrences still requiring a role.

    That makes the CHAIN the unit of work, and the cost of a chain the number of
    links in it. Sizing route (b) as a flat row count overstates how much a
    partial pass discharges, which is nothing.

    A KNOWN LIMIT, checked rather than assumed. Holders are STATED rows, so a
    delta edition that inherits an occurrence without restating it is not a
    holder and its link is not counted. That is correct for grounding -- an
    inherited occurrence states no row, so it has no ``semantic_role`` to
    require and nothing to ground -- but it means the link count is a count of
    stated steps, not of editions the chain passes through. Every modelo this
    condition currently reports on (322, 309, 308) authors every edition in
    full, so the two coincide there. On a delta-authored modelo they would not,
    and the reading to keep is that a chain's cost is the grounding work it
    needs, not the distance it travels.  The sole exception is a typed casilla
    lineage attestation on an exact predecessor edge: it preserves the
    successor occurrence and its grounding claim after the corresponding row
    is omitted as inherited.  This raw screen checks shape, edge, retirement,
    and materialised predecessor membership; it does not call that evidence
    compiler-validated.
    """
    per_chain: dict[str, tuple[int, int]] = {}
    by_modelo: dict[str, list[EditionStatus]] = defaultdict(list)
    for status in statuses:
        by_modelo[status.modelo].append(status)
    for modelo, editions in by_modelo.items():
        ordered = _ordered(editions)
        carried: dict[str, list[EditionStatus]] = defaultdict(list)
        origins: dict[tuple[str, str], str] = {}
        for status in ordered:
            for row in status.rows_by_id.values():
                chain = row.get(_LINEAGE)
                if not isinstance(chain, str) or not chain:
                    continue
                carried[chain].append(status)
                origins[(chain, status.edition)] = str(row.get("continuidad_origin", ""))
        stated = {status.edition: _chains_of(status) for status in ordered}
        materialised = _materialised_chains(ordered, stated)
        by_edition = {status.edition: status for status in ordered}
        for status in ordered:
            for attestation in status.lineage_attestations:
                chain = str(attestation.continuidad_id) if attestation.continuidad_id is not None else ""
                if (
                    attestation.family != "casillas"
                    or not chain
                    or attestation.origin.value != _GROUNDED
                    or attestation.to_revision != status.edition
                    or status.predecessor_id != attestation.from_revision
                    or attestation.from_revision not in by_edition
                    or chain not in materialised.get(attestation.from_revision, ())
                    or chain in status.retired_lineages
                ):
                    continue
                # Do not manufacture another stated row.  Add only the logical
                # target occurrence that the exact-edge sidecar displaced.
                holders = carried[chain]
                if all(holder.edition != status.edition for holder in holders):
                    holders.append(status)
                origins[(chain, status.edition)] = _GROUNDED
        for chain, holders in carried.items():
            holders.sort(key=lambda holder: ordered.index(holder))
            links = len(holders) - 1
            if links < 1:
                continue
            # A link is grounded when the SUCCESSOR occurrence states it: the
            # later row is the one carrying the evidence for the step it makes.
            grounded = sum(1 for status in holders[1:] if origins.get((chain, status.edition)) == _GROUNDED)
            per_chain[f"{modelo}/{chain}"] = (grounded, links)
    return per_chain


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


def _materialised_chains(
    ordered: tuple[EditionStatus, ...],
    carried: Mapping[str, Counter[str]],
) -> dict[str, frozenset[str]]:
    """Every lineage each edition SERVES, inherited rows included.

    A delta edition states only what changed and inherits the rest, so the
    lineages it carries are its own stated ones plus everything its predecessor
    materialises. The stated set answers a different question, and two of this
    screen's conditions genuinely want it -- ``chain_ambiguous_in_edition``
    because two STATED rows are the ambiguity it names.

    Reading one for the other reported all 258 of modelo 714's evolutions as
    naming a lineage no casilla carries. 714's editions 2022 through 2025 each
    declare a predecessor and state 23 rows while materialising 111, so the 86
    lineages per edition were carried the whole time. The chain is walked rather
    than resolved in sequence so the answer does not depend on a predecessor
    sorting ahead of its successor.
    """
    by_edition = {status.edition: status for status in ordered}

    def walk(edition: str, seen: frozenset[str]) -> frozenset[str]:
        status = by_edition.get(edition)
        if status is None or edition in seen:
            return frozenset()
        own = frozenset(carried.get(edition, ()))
        parent = status.predecessor_id
        if not parent:
            return own
        return own | walk(parent, seen | {edition})

    return {status.edition: walk(status.edition, frozenset()) for status in ordered}


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
    materialised = _materialised_chains(ordered, carried)
    mine = tuple(evolution for evolution in evolutions if evolution.modelo == modelo)
    declared = {(evolution.chain, evolution.from_revision, evolution.to_revision) for evolution in mine}

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
            # A DELTA edition states only what changed and inherits the rest, so
            # a chain it does not restate is carried, not missing. Reading a
            # stated-row absence as a hole reported both of the corpus's only
            # two skips as defects when neither was: 390/2024 declares
            # predecessor 2023 and 303/2024-hasta-08-y-2t declares 2023, and
            # both predecessors carry the chain the successor was accused of
            # dropping.
            #
            # The hole this screen exists to find is a chain absent from the
            # MATERIALISED edition, and for a delta edition that means absent
            # from its predecessor too -- which, if it were, would make the
            # predecessor the edition with the hole rather than this one.
            if absent.declares_predecessor:
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
        # The three root kinds mean three different things for a crossing chain,
        # and pooling any two of them loses the distinction. Read from the
        # screen that owns the classification rather than re-derived here, so a
        # kind added there cannot silently fall into the wrong bucket.
        # The declared CAUSE wins over the wording, exactly as the owning screen
        # decides it. This passed the reason alone, so every root carrying a
        # cause code was classified from prose -- the one thing the comment above
        # says this must not do.
        root = _root_kind(successor.root_reason, successor.root_cause)
        kind, why = _CHAIN_ROOT_KINDS[root]
        # A structural root gets its own kind, and it comes out of root_by_law
        # rather than out of recoverable: the owning screen maps
        # `official_structure_differs` to `root_by_law`, so without this override
        # every such crossing would read as the form forbidding inheritance. Both
        # are permanent and the EVIDENCE differs, which is the whole reason to
        # split them -- a root by law rests on a norm, a structural root on a
        # measured per-family materialisation result. Calling a harness
        # measurement "by law" attributes to the legislator what the record design
        # did.
        #
        # A structural root is not work: the design really is reordered, the
        # edition genuinely cannot be materialised from its predecessor, and no
        # lineage or grounding pass changes that. The chains still crossing it are
        # not a defect either -- the box is the same concept while the editions
        # cannot be merged, and both claims are true at once.
        if successor.root_cause == _STRUCTURE_DIFFERS:
            kind, why = (
                "chain_across_structural_root",
                "roots away from on a measured structural difference, which no lineage work changes",
            )
        detail = f"shared with {predecessor.edition}, which this edition {why}"
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
            # Whether this restates anything depends on the adjacent step HAVING a
            # record, which an earlier version of this condition asserted instead
            # of checking. Measured on the corpus, 118 of 669 findings had no
            # adjacent record at all, so the spanning evolution was the only
            # statement of the transition and dropping it would have lost the
            # transition rather than removed a duplicate. The two cases need
            # opposite work, so they are reported apart.
            adjacent = (evolution.chain, ordered[end - 1].edition, evolution.to_revision)
            if adjacent in declared:
                kind = "evolution_restates_ancestor"
                why = f"and {', '.join(status.edition for status in skipped)} carry the chain"
            else:
                kind = "evolution_spans_unrecorded_step"
                why = (
                    f"and no evolution records {ordered[end - 1].edition} -> {evolution.to_revision}, "
                    f"so this span is the only statement of the transition"
                )
            findings.append(
                ChainFinding(
                    modelo=modelo,
                    edition=evolution.edition,
                    kind=kind,
                    chain=evolution.chain,
                    detail=f"{evolution.from_revision} -> {evolution.to_revision} spans {end - start} steps, {why}",
                )
            )
        endpoints = materialised[evolution.from_revision] | materialised[evolution.to_revision]
        if evolution.chain not in endpoints:
            findings.append(
                ChainFinding(
                    modelo=modelo,
                    edition=evolution.edition,
                    kind="evolution_without_chain_members",
                    chain=evolution.chain,
                    detail=f"neither {evolution.from_revision} nor {evolution.to_revision} materialises it",
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
    findings.extend(ruling_reference_findings(statuses))
    # A chain part-way through grounding is the trap, but not because it
    # discharges nothing -- an earlier wording of this said so and was wrong.
    # Exemption is per occurrence and bilateral, so grounding one link exempts
    # only the occurrences at its ends whose OTHER links are also grounded. On
    # 322 a pass grounded the final link of 114 chains: each gained the terminal
    # occurrence and nothing else, leaving the modelo at 148 exempt of 847. The
    # trap is that the work reads as 114 chains advanced when it bought a quarter
    # of each, and the remaining two links per chain are the whole cost.
    for key, (grounded, links) in sorted(grounding_by_chain(statuses).items()):
        if 0 < grounded < links:
            modelo, _, chain = key.partition("/")
            findings.append(
                ChainFinding(
                    modelo=modelo,
                    edition="<chain>",
                    kind="chain_partially_grounded",
                    chain=chain,
                    detail=(
                        f"{grounded} of {links} links grounded; only occurrences whose every "
                        f"touching link is grounded are exempt, so the ungrounded links bound the rest"
                    ),
                )
            )
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
        "chain_fully_grounded": sum(
            1 for grounded, links in grounding_by_chain(statuses).values() if grounded == links
        ),
        "chain_links_to_ground": sum(
            links - grounded for grounded, links in grounding_by_chain(statuses).values() if grounded < links
        ),
        "evolution_spans_absent_editions": spans_over_absent_editions(statuses, evolutions),
    }


def _declaring_sites(findings: tuple[ChainFinding, ...]) -> Counter[str]:
    """Per condition, how many distinct editions declare the thing being reported.

    A root-crossing finding is emitted once per chain crossing one root, so its
    count scales with the modelo's chain population while the work does not: the
    corpus's 7,444 ``chain_across_pending_root`` findings are fifteen root
    declarations, and 6,547 of them are six editions of two frozen modelos.
    Reporting findings alone overstated the remaining work by three orders of
    magnitude for most of this campaign. The site count is the unit a person
    acts on; the finding count is the evidence weight behind it.
    """
    return Counter(
        {
            kind: len({(finding.modelo, finding.edition) for finding in findings if finding.kind == kind})
            for kind in CONDITIONS
        }
    )


def _payload(findings: tuple[ChainFinding, ...], counts: Mapping[str, int]) -> dict[str, Any]:
    tally = Counter(finding.kind for finding in findings)
    sites = _declaring_sites(findings)
    return {
        "census": dict(counts),
        "conditions": {kind: tally.get(kind, 0) for kind in CONDITIONS},
        "declaring_sites": {kind: sites.get(kind, 0) for kind in CONDITIONS},
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
    sites = _declaring_sites(findings)
    per_modelo: Counter[str] = Counter(finding.modelo for finding in findings)
    lines = [
        f"# chain_contiguity schema={_SIGNAL_SCHEMA} conditions={len(CONDITIONS)} measurements={len(MEASUREMENTS)}",
        "census " + " ".join(f"{key}={value}" for key, value in sorted(counts.items())),
        " ".join(["condition", *(f"{kind}={tally.get(kind, 0)}" for kind in CONDITIONS)]),
        " ".join(["sites", *(f"{kind}={sites.get(kind, 0)}" for kind in CONDITIONS)]),
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
    sites = _declaring_sites(findings)
    active = [(kind, tally[kind]) for kind in CONDITIONS if tally[kind]]
    out += [
        f"  {kind:<34} {count:>8,}   {sites[kind]:>3} declaring {'site' if sites[kind] == 1 else 'sites'}"
        for kind, count in active
    ] or ["  all clean"]
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
