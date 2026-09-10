"""Seed casilla lineage across successor editions, refusing what it cannot prove.

For every adjacent pair of editions of an in-scope modelo, each successor
casilla row is disposed of exactly once:

- **declared** -- it already carries a ``continuidad_id`` its predecessor
  edition carries. Left untouched.
- **seeded** -- a bare chain admitted only when the casilla identifier, the
  ``semantic_role`` and the ``data_type`` all agree and the dedicated printed box
  number ``form_number`` agrees where both rows state one. The general
  ``number`` field is heterogeneous by design (a byte range on one modelo, a
  one-byte wire campo's plain integer on another) and is never read for
  identity; a byte span never chains.
- **grounded** -- a continuation an adjudicated ruling proves from the official
  record designs.
- an absence of one of three kinds -- ``new_on_form`` (the box is not on the
  predecessor form), ``predecessor_edition_silent`` (the box is on the
  predecessor form but the predecessor edition does not declare it) or
  ``not_on_form`` (a product concept the form does not number). A kind is
  written only on evidence from the pinned official record design, which is
  trusted for an edition pair only when every printed number both editions
  declare resolves in its own design and the successor design retires no box.
- **refused** -- anything else, recorded in the ledger with its reason rather
  than falling through to a weaker signal.

An excluded modelo is never written. Each of its successor rows that neither
carries lineage nor declares a kind of none is still refused in the ledger, one
row at a time, under the category its exclusion names, so the ledger stays the
closed list of every unresolved row in the corpus.

Coverage is a different question from identity: whether a row has a printed box
at all is read from ``form_number`` OR a plain-integer ``number`` (that is the
shipped printed-number contract); whether two rows are the same box is read
from ``form_number`` alone.

A chain is also refused when writing it would break the registry's own load
contract: every occurrence of a chain crossing a revision boundary must carry a
``semantic_role``, and a chain whose role is unique in every revision it spans
must use the role-derived identifier.

Usage::

    python -m dev.registry.analysis.casilla_lineage_seed            # report only
    python -m dev.registry.analysis.casilla_lineage_seed --apply    # write rows and ledger

Reads the registry through the validated authority. Writes insert keys into the
casilla declaration files as text, never reformatting them, and refuse to
overwrite a differing value already present.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
import sys
import tomllib
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from itertools import pairwise
from pathlib import Path

from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.casilla_lineage import CasillaLineageOrigin
from cadrumo.domain.calculations.registry.casilla_lineage_totality import unresolved_successor_rows
from cadrumo.domain.calculations.registry.revision_order import ordered_revisions, revisions_overlap
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition
from dev.registry.compiler.registry_scope import validate_registry_scope
from dev.registry.compiler.authority import compiled_bundled_authority

from .casilla_id_grammar import classify_casilla_id
from .corpus import bundled_modelo_ids

__all__ = [
    "EXCLUDED_MODELOS",
    "DesignInventory",
    "ExcludedModelo",
    "LineagePlan",
    "LineageRefusalCategory",
    "admit_bare_chain",
    "contradictions",
    "gate_regressions",
    "insert_lineage_keys",
    "parse_design_inventory",
    "plan_modelo",
    "residual_plan",
]


class LineageRefusalCategory(StrEnum):
    """Why the seeder declined to write a lineage disposition for a successor row.

    The closed vocabulary of every reason a row is refused, named once so the
    seeder, the ledger it writes and the tests reading either share one
    spelling per reason rather than repeating the token inline.
    """

    NOT_EXAMINED = "not_examined"
    ABSENCE_UNCLASSIFIED = "absence_unclassified"
    ABSENCE_UNLOCALISED = "absence_unlocalised"
    OVERLAPPING_PREDECESSOR = "overlapping_predecessor"
    RULING_REFUSES_BARE = "ruling_refuses_bare"
    POSITIONAL_HOLD = "positional_hold"
    PARTIAL_STAMP = "partial_stamp"
    CHAIN_CONTRACT = "chain_contract"
    PRINTED_BOX_FORK = "printed_box_fork"
    GROUNDED_UNLOCALISED = "grounded_unlocalised"
    GROUNDED_BLOCKED = "grounded_blocked"
    HELD = "held"
    WITHHELD = "withheld"
    MERGED = "merged"
    ROLE_ABSENT = "role_absent"
    CONTRADICTED = "contradicted"


_UTF_8 = "utf-8"
_ANALYSIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _ANALYSIS_DIR.parents[2]
_DATA_ROOT = _REPO_ROOT / "src" / "cadrumo" / "_data"
_MODELOS_ROOT = _DATA_ROOT / "registry" / "aeat" / "modelos"
RULINGS_PATH = _ANALYSIS_DIR / "casilla_lineage_rulings.toml"
LEDGER_PATH = _ANALYSIS_DIR / "casilla_lineage_ledger.toml"


@dataclass(frozen=True, slots=True)
class ExcludedModelo:
    """A modelo this seeder never writes, and how its unresolved rows are recorded.

    ``residual_category`` is the ledger category every unresolved successor row
    of the modelo is refused under, unless an adjudicated ruling names the row
    more precisely. ``None`` means the modelo can have no unresolved successor
    row at all, so finding one is an error rather than a refusal.
    """

    reason: str
    residual_category: LineageRefusalCategory | None
    residual_reason: str


_M100_REASON = (
    "no in-registry oracle: no export surface, byte span or form_number, and semantic_role labels a grid "
    "column; box reassignment under stable identifiers is proven at scale, so nothing is seeded mechanically"
)
_M200_REASON = "export bindings are being repaired in the same tree; lineage waits for the repaired declarations"

EXCLUDED_MODELOS: Mapping[str, ExcludedModelo] = {
    "100": ExcludedModelo(
        reason=_M100_REASON,
        residual_category=LineageRefusalCategory.NOT_EXAMINED,
        residual_reason=f"not examined; its lineage is its own campaign: {_M100_REASON}",
    ),
    "200": ExcludedModelo(
        reason=_M200_REASON,
        residual_category=LineageRefusalCategory.NOT_EXAMINED,
        residual_reason=f"not examined: {_M200_REASON}",
    ),
    "309": ExcludedModelo(
        reason=(
            "its lineage is grounded by adjudication against the official record designs, including a printed box "
            "number that moved from the record-design metadata into form_number, rather than seeded"
        ),
        residual_category=LineageRefusalCategory.ABSENCE_UNCLASSIFIED,
        residual_reason=(
            "residual after adjudication against the official record designs: no ruling chains this row or names "
            "which kind of absence it is"
        ),
    ),
    "369": ExcludedModelo(
        reason="the editions are parallel schemes sharing one validity window, not a temporal sequence",
        residual_category=None,
        residual_reason="every edition declares that it has no predecessor edition",
    ),
}

_PLAIN_INTEGER = re.compile(r"^\d+$")
_DESIGN_BOX = re.compile(r"\[\s*(\d{1,4})\s*\]")
_ALPHANUMERIC = re.compile(r"\w")
_LIST_SEPARATOR = re.compile(r"^\s*(?:,|y|e|o|a)\s*$", re.IGNORECASE)
_OPERATOR_GAP = re.compile(r"^\s*[-+x*/=]\s*$")
_CASILLA_HEADER = re.compile(r'^\[\[revisions\.(?:"([^"]+)"|([A-Za-z0-9_-]+))\.casillas\]\]\s*$')
_ID_LINE = re.compile(r'^id\s*=\s*"([^"]+)"\s*$')
_CONTINUIDAD_ID = re.compile(r"^[a-z0-9][a-z0-9_-]*[a-z0-9]$|^[a-z0-9]$")
_EVIDENCE_LIMIT = 512
_SNIPPET = 70
_MIN_POSITIONAL_SPACE = 5
_MAX_POSITIONAL_EXPANSION = 3.0
_LINEAGE_KEYS = ("continuidad_id", "continuidad_origin", "continuidad_evidence")
_PARTIAL_STAMP = (
    "another occurrence of this identifier cannot carry a continuidad_id, and the registry refuses an identifier "
    "stamped in only part of its occurrences"
)


# --------------------------------------------------------------------------- design oracle


@dataclass(frozen=True, slots=True)
class DesignInventory:
    """The boxes one official record design prints, with the line each is defined on.

    A campo description ENDS with the box it prints, and any other bracket in it
    is an operand of the formula it quotes (``Resultado ([17] + [19] - [25])
    [26]`` prints 26). A cell enumerating boxes (``las casillas [20], [21] y
    [22]``) is a note about boxes, not a campo, and defines none.
    """

    relative_path: str
    sha256: str
    lines: Mapping[int, tuple[int, ...]]
    text_by_line: Mapping[int, str]

    @property
    def boxes(self) -> frozenset[int]:
        """Every box number this design prints."""
        return frozenset(self.lines)

    def defining_line(self, box: int) -> int | None:
        """The single line printing ``box``, or ``None`` when absent or printed more than once."""
        found = self.lines.get(box, ())
        return found[0] if len(found) == 1 else None

    def snippet(self, line: int) -> str:
        """A short excerpt of one design line for evidence prose."""
        text = " ".join(self.text_by_line.get(line, "").replace("|", " ").split())
        return text if len(text) <= _SNIPPET else text[: _SNIPPET - 3] + "..."


def parse_design_inventory(text: str, *, relative_path: str, sha256: str) -> DesignInventory:
    """Build a design's box inventory from its extracted text."""
    lines: dict[int, list[int]] = collections.defaultdict(list)
    text_by_line: dict[int, str] = {}
    for number, line in enumerate(text.splitlines(), start=1):
        for cell in line.split("|"):
            box = _defined_box(cell)
            if box is not None:
                lines[box].append(number)
                text_by_line[number] = line
    return DesignInventory(
        relative_path=relative_path,
        sha256=sha256,
        lines={box: tuple(found) for box, found in lines.items()},
        text_by_line=text_by_line,
    )


def _defined_box(cell: str) -> int | None:
    """The box one design cell prints, or ``None`` when the cell prints none.

    Three shapes are told apart: a campo ending with its own box (``... ([16] x
    [24] [17]``); a formula ending with an operand and no box of its own (``[03]
    + [05]``); and a note enumerating boxes outside any parenthesis (``las
    casillas [20], [21] y [22]``). Only the first defines a box.
    """
    matches = list(_DESIGN_BOX.finditer(cell))
    if not matches or _ALPHANUMERIC.search(cell[matches[-1].end() :]):
        return None
    depths: list[int] = []
    depth = 0
    cursor = 0
    for match in matches:
        for char in cell[cursor : match.start()]:
            if char == "(":
                depth += 1
            elif char == ")":
                depth = max(0, depth - 1)
        depths.append(depth)
        cursor = match.end()
    for index in range(1, len(matches)):
        gap = cell[matches[index - 1].end() : matches[index].start()]
        if depths[index - 1] == 0 and depths[index] == 0 and _LIST_SEPARATOR.match(gap):
            return None
    if len(matches) > 1 and _OPERATOR_GAP.match(cell[matches[-2].end() : matches[-1].start()]):
        return None
    return int(matches[-1].group(1))


def printed_box(casilla: CasillaDefinition) -> int | None:
    """Coverage: the printed box a row states in form_number OR a plain-integer number."""
    if casilla.form_number is not None:
        return int(str(casilla.form_number))
    number = casilla.number.strip()
    return int(number) if _PLAIN_INTEGER.match(number) else None


def identity_box(casilla: CasillaDefinition) -> str | None:
    """Identity: the dedicated printed-number field and nothing else."""
    return None if casilla.form_number is None else str(casilla.form_number)


class DesignOracle:
    """Resolve and cache each edition's pinned official record design."""

    def __init__(self, authority: ValidatedRegistryAuthority) -> None:
        self._sources = authority.catalogues.sources
        self._cache: dict[str, DesignInventory | str] = {}

    def for_revision(self, revision: ModeloRevision) -> DesignInventory | str:
        """The revision's design inventory, or the reason none can be trusted."""
        refs = set(revision.source_refs)
        for casilla in revision.casillas:
            refs.update(casilla.source_refs)
        designs = [
            source
            for ref in sorted(refs)
            if (source := self._sources.get(ref)) is not None and str(source.kind) == "record_design"
        ]
        paths = {source.corpus_path: source for source in designs}
        if len(paths) > 1:
            paths = {
                path: source
                for path, source in paths.items()
                if source.applies_from is not None
                and source.applies_from <= revision.valid_from
                and (source.applies_to is None or revision.valid_from <= source.applies_to)
            }
        if len(paths) != 1:
            return f"revision {revision.id} names {len(paths)} applicable record designs, not exactly one"
        path, source = next(iter(paths.items()))
        if path not in self._cache:
            self._cache[path] = self._load(path, source.sha256)
        return self._cache[path]

    @staticmethod
    def _load(corpus_path: str, sha256: str) -> DesignInventory | str:
        original = _DATA_ROOT / corpus_path
        extract = original.with_name(original.name + ".extracted.md")
        if not original.is_file() or not extract.is_file():
            return f"design {corpus_path} has no bundled extract"
        digest = hashlib.sha256(original.read_bytes()).hexdigest()
        if digest != sha256:
            return f"design {corpus_path} does not match its pinned sha256"
        return parse_design_inventory(
            extract.read_text(encoding=_UTF_8),
            relative_path=str(Path(corpus_path).with_name(extract.name).as_posix()),
            sha256=sha256,
        )


# --------------------------------------------------------------------------- plan model


@dataclass(frozen=True, slots=True)
class Refusal:
    """One row the seeder declined to write, with the reason it stops."""

    modelo: str
    revision: str
    casilla_id: str
    category: LineageRefusalCategory
    reason: str
    predecessor: str | None = None


@dataclass(slots=True)
class LineagePlan:
    """Every disposition for one modelo, plus the key edits that realise them."""

    modelo: str
    edits: dict[tuple[str, str], dict[str, str]] = field(default_factory=dict)
    counts: collections.Counter[str] = field(default_factory=collections.Counter)
    refusals: list[Refusal] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def refuse(
        self,
        revision: str,
        casilla_id: str,
        category: LineageRefusalCategory,
        reason: str,
        predecessor: str | None = None,
    ) -> None:
        """Record a refusal and count it."""
        self.refusals.append(Refusal(self.modelo, revision, casilla_id, category, reason, predecessor))
        self.counts[f"refused:{category}"] += 1

    def set_keys(self, revision: str, casilla_id: str, **keys: str) -> None:
        """Stage key edits for one row, refusing to plan two values for one key."""
        staged = self.edits.setdefault((revision, casilla_id), {})
        for key, value in keys.items():
            if staged.get(key, value) != value:
                raise ValueError(f"modelo {self.modelo} {revision}/{casilla_id}: two values planned for {key}")
            staged[key] = value


@dataclass(frozen=True, slots=True)
class Ruling:
    """An adjudicated boundary, applied verbatim."""

    predecessor: str
    successor: str
    refuse_bare: bool
    rationale: str
    grounded: tuple[tuple[str, str], ...]
    new_on_form: frozenset[str]
    new_on_form_stems: frozenset[str]
    not_on_form: frozenset[str]
    held: tuple[tuple[str, str], ...]
    held_stems: frozenset[str]
    held_reason: str
    withheld: tuple[tuple[str, str], ...]
    withheld_reason: str
    merged: tuple[tuple[str, str], ...]
    merged_reason: str
    discontinued: frozenset[str]


def _pairs(values: Iterable[str]) -> tuple[tuple[str, str], ...]:
    return tuple((left, right) for left, _, right in (value.partition(">") for value in values))


def load_rulings(path: Path = RULINGS_PATH) -> dict[str, list[Ruling]]:
    """Load every adjudicated ruling keyed by modelo.

    Rulings for an excluded modelo are applied to its data by whoever owns that
    modelo; this seeder reads them only to name its residual refusals precisely.
    """
    document = tomllib.loads(path.read_text(encoding=_UTF_8))
    rulings: dict[str, list[Ruling]] = collections.defaultdict(list)
    for entry in document["ruling"]:
        rulings[entry["modelo"]].append(
            Ruling(
                predecessor=entry["predecessor"],
                successor=entry["successor"],
                refuse_bare=bool(entry.get("refuse_bare", False)),
                rationale=entry["rationale"],
                grounded=_pairs(entry.get("grounded", ())),
                new_on_form=frozenset(entry.get("new_on_form", ())),
                new_on_form_stems=frozenset(entry.get("new_on_form_stems", ())),
                not_on_form=frozenset(entry.get("not_on_form", ())),
                held=_pairs(entry.get("held", ())),
                held_stems=frozenset(entry.get("held_stems", ())),
                held_reason=entry.get("held_reason", ""),
                withheld=_pairs(entry.get("withheld", ())),
                withheld_reason=entry.get("withheld_reason", ""),
                merged=_pairs(entry.get("merged", ())),
                merged_reason=entry.get("merged_reason", ""),
                discontinued=frozenset(entry.get("discontinued", ())),
            )
        )
    return dict(rulings)


# --------------------------------------------------------------------------- predicates


def admit_bare_chain(
    previous: CasillaDefinition, successor: CasillaDefinition
) -> tuple[LineageRefusalCategory | None, str]:
    """Return ``(None, detail)`` when a bare chain is admitted, else ``(category, reason)``.

    The identifier is already equal; role, type and the dedicated printed box
    must agree too. A missing role is its own category: nothing can be agreed
    with an absent role, and the load contract refuses a chain without one.
    """
    if previous.semantic_role is None or successor.semantic_role is None:
        side = "predecessor" if previous.semantic_role is None else "successor"
        return (
            LineageRefusalCategory.ROLE_ABSENT,
            f"no semantic_role on the {side} row; identity cannot be established on role",
        )
    if previous.semantic_role != successor.semantic_role:
        return (
            LineageRefusalCategory.CONTRADICTED,
            f"semantic_role moved {previous.semantic_role!r} -> {successor.semantic_role!r}",
        )
    if previous.data_type != successor.data_type:
        return (
            LineageRefusalCategory.CONTRADICTED,
            f"data_type moved {previous.data_type!s} -> {successor.data_type!s}",
        )
    before, after = identity_box(previous), identity_box(successor)
    if before is not None and after is not None and before != after:
        return LineageRefusalCategory.CONTRADICTED, f"form_number moved {before!r} -> {after!r}"
    return None, "identifier, semantic_role and data_type agree; form_number does not contradict"


def positional_hold(previous: ModeloRevision, successor: ModeloRevision) -> str | None:
    """A positional identifier space with boxes inserted: every bare chain across it is refused."""
    prev_ids = {casilla.id for casilla in previous.casillas}
    succ_ids = {casilla.id for casilla in successor.casillas}
    if not prev_ids or len(succ_ids) == len(prev_ids) or not prev_ids <= succ_ids:
        return None
    if len(prev_ids) < _MIN_POSITIONAL_SPACE or len(succ_ids) > _MAX_POSITIONAL_EXPANSION * len(prev_ids):
        return None
    prev_sections = {part for casilla in previous.casillas for part in casilla.section}
    succ_sections = {part for casilla in successor.casillas for part in casilla.section}
    if not prev_sections or not succ_sections:
        return None
    overlap = len(prev_sections & succ_sections) / len(prev_sections | succ_sections)
    if overlap > 0.25:
        return None
    return (
        f"positional identifier space: all {len(prev_ids)} predecessor ids reused among {len(succ_ids)} "
        f"successor rows with {overlap:.0%} shared section vocabulary, so boxes were inserted"
    )


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9_-]+", "-", value.lower()).strip("-_")
    return slug[:128].rstrip("-_")


def _role_derived(role: str) -> str:
    return role.lower().replace("_", "-")


# --------------------------------------------------------------------------- per-modelo planning


type _Row = tuple[str, str]


@dataclass(slots=True)
class _ChainState:
    """Continuity ids and lineage links as they will stand once the plan is written.

    A link is the step from a row to the one predecessor-edition row carrying
    its chain; it is grounded only when the continuing row declares ``grounded``
    with evidence. Links are tracked because the registry excuses a row from
    carrying a ``semantic_role`` exactly when every link it takes part in is
    grounded.
    """

    ids: dict[_Row, str]
    members: dict[str, list[_Row]]
    role_counts: dict[str, collections.Counter[str | None]]
    roles: dict[_Row, str | None]
    position: dict[str, int]
    predecessor_of: dict[_Row, _Row]
    grounded_link: dict[_Row, bool]

    @classmethod
    def of(cls, modelo: ModeloDefinition) -> _ChainState:
        revisions = ordered_revisions(modelo)
        state = cls(
            ids={},
            members=collections.defaultdict(list),
            role_counts={},
            roles={},
            position={revision.id: index for index, revision in enumerate(revisions)},
            predecessor_of={},
            grounded_link={},
        )
        for revision in revisions:
            state.role_counts[revision.id] = collections.Counter(casilla.semantic_role for casilla in revision.casillas)
            for casilla in revision.casillas:
                state.roles[(revision.id, casilla.id)] = casilla.semantic_role
                if casilla.continuidad_id is not None:
                    state.ids[(revision.id, casilla.id)] = casilla.continuidad_id
                    state.members[casilla.continuidad_id].append((revision.id, casilla.id))
        for previous, successor in pairwise(revisions):
            if revisions_overlap(previous, successor):
                continue
            for casilla in successor.casillas:
                if casilla.continuidad_id is None:
                    continue
                carriers = [row for row in state.members[casilla.continuidad_id] if row[0] == previous.id]
                if len(carriers) != 1:
                    continue
                row = (successor.id, casilla.id)
                state.predecessor_of[row] = carriers[0]
                evidence = casilla.continuidad_evidence
                state.grounded_link[row] = (
                    casilla.continuidad_origin is CasillaLineageOrigin.GROUNDED
                    and evidence is not None
                    and bool(evidence.strip())
                )
        return state

    def ids_in(self, revision: str) -> set[str]:
        return {chain for (rev, _), chain in self.ids.items() if rev == revision}

    def _role_exempt(self, row: _Row, occurrences: set[_Row], links: Mapping[_Row, tuple[_Row, bool]]) -> bool:
        """Whether ``row`` takes part in at least one link and every link it takes part in is grounded."""
        incoming = links.get(row)
        earlier = any(self.position[other[0]] < self.position[row[0]] for other in occurrences)
        incoming_grounded = incoming is not None and incoming[1]
        outgoing = [grounded for predecessor, grounded in links.values() if predecessor == row]
        incoming_ok = incoming_grounded or not earlier
        return incoming_ok and (incoming_grounded or any(outgoing)) and all(outgoing)

    def linkage_violation(self, chain: str, link: tuple[_Row, _Row], grounded: bool) -> str | None:
        """The semantic-linkage failure writing ``link`` into ``chain`` would cause, if any.

        Mirrors the load-time rule: every occurrence of a chain crossing a
        revision boundary carries a ``semantic_role`` unless every link it takes
        part in is grounded, and a chain whose declared role is unique in every
        revision it spans uses the role-derived identifier.
        """
        predecessor, successor = link
        occurrences = set(self.members.get(chain, ())) | {predecessor, successor}
        links = {
            row: (self.predecessor_of[row], self.grounded_link[row])
            for row in occurrences
            if row in self.predecessor_of
        }
        links[successor] = (predecessor, grounded)
        missing = sorted(
            row for row in occurrences if self.roles[row] is None and not self._role_exempt(row, occurrences, links)
        )
        if missing:
            return (
                f"chain {chain!r} would carry rows without semantic_role whose links are not all grounded: "
                f"{missing[:3]}"
            )
        chain_roles = {self.roles[row] for row in occurrences} - {None}
        if len(chain_roles) != 1:
            return None
        role = next(iter(chain_roles))
        if role is None:
            return None
        revisions = {revision for revision, _ in occurrences}
        if all(self.role_counts[revision][role] == 1 for revision in revisions) and chain != _role_derived(role):
            return f"chain {chain!r} has role {role!r} unique in every revision and must be {_role_derived(role)!r}"
        return None

    def link(self, chain: str, rows: Iterable[_Row]) -> None:
        for row in rows:
            if row not in self.ids:
                self.ids[row] = chain
                self.members[chain].append(row)

    def record_link(self, predecessor: _Row, successor: _Row, grounded: bool) -> None:
        self.predecessor_of[successor] = predecessor
        self.grounded_link[successor] = grounded


class _ModeloPlanner:
    def __init__(
        self,
        modelo_id: str,
        modelo: ModeloDefinition,
        oracle: DesignOracle,
        rulings: list[Ruling],
        forbidden: frozenset[str],
    ) -> None:
        self.forbidden = forbidden
        self.modelo_id = modelo_id
        self.modelo = modelo
        self.oracle = oracle
        self.rulings = {(ruling.predecessor, ruling.successor): ruling for ruling in rulings}
        self.plan = LineagePlan(modelo_id)
        self.state = _ChainState.of(modelo)

    # -- chain writing

    def _new_chain_id(self, previous: CasillaDefinition, successor: CasillaDefinition, pair: tuple[str, str]) -> str:
        role = previous.semantic_role
        if (
            role is not None
            and role == successor.semantic_role
            and all(self.state.role_counts[revision][role] == 1 for revision in pair)
        ):
            return _role_derived(role)
        if role is not None and not self.state.members.get(_role_derived(role)):
            return _role_derived(role)
        return _slug(previous.id)

    def _write_chain(
        self,
        previous: CasillaDefinition,
        successor: CasillaDefinition,
        pair: tuple[str, str],
        origin: CasillaLineageOrigin,
        evidence: str | None,
        claimed: set[str],
    ) -> str | None:
        """Plan one continuation; return a refusal reason instead when it cannot be written."""
        prev_key, succ_key = (pair[0], previous.id), (pair[1], successor.id)
        if classify_casilla_id(previous.id) != classify_casilla_id(successor.id):
            return "the two identifiers use different grammars; no chain may cross a grammar"
        prev_chain, succ_chain = self.state.ids.get(prev_key), self.state.ids.get(succ_key)
        if prev_chain is not None and succ_chain is not None and prev_chain != succ_chain:
            return f"declared lineage disagrees: predecessor carries {prev_chain!r}, successor {succ_chain!r}"
        chain = prev_chain or succ_chain or self._new_chain_id(previous, successor, pair)
        if not _CONTINUIDAD_ID.match(chain):
            return f"no valid continuidad_id derivable from {previous.id!r}"
        if previous.id in claimed:
            return f"predecessor {previous.id!r} is already continued by another row; lineage is one-to-one"
        holders = {
            row for row in self.state.members.get(chain, ()) if row[0] in pair and row not in (prev_key, succ_key)
        }
        if holders:
            return f"chain {chain!r} is already carried by {sorted(holders)[:2]} in this pair"
        if prev_chain is None and succ_chain is None and self.state.members.get(chain):
            return f"derived chain id {chain!r} already names another chain in this modelo"
        grounded = origin is CasillaLineageOrigin.GROUNDED and bool(evidence and evidence.strip())
        violation = self.state.linkage_violation(chain, (prev_key, succ_key), grounded)
        if violation is not None:
            return violation
        self.state.link(chain, (prev_key, succ_key))
        self.state.record_link(prev_key, succ_key, grounded)
        claimed.add(previous.id)
        if prev_chain is None:
            self.plan.set_keys(pair[0], previous.id, continuidad_id=chain)
        keys = {"continuidad_origin": origin.value}
        if succ_chain is None:
            keys["continuidad_id"] = chain
        if evidence is not None:
            keys["continuidad_evidence"] = _bounded(evidence)
        self.plan.set_keys(pair[1], successor.id, **keys)
        self.plan.counts[origin.value] += 1
        return None

    def _write_absence(
        self, revision: str, casilla: CasillaDefinition, origin: CasillaLineageOrigin, evidence: str
    ) -> None:
        self.plan.set_keys(
            revision, casilla.id, continuidad_origin=origin.value, continuidad_evidence=_bounded(evidence)
        )
        self.plan.counts[origin.value] += 1

    # -- identifier-wide stamping

    def settle_partial_stamps(self) -> frozenset[str]:
        """Leave no casilla identifier stamped in some revisions and unstamped in others.

        The registry refuses an identifier that carries a ``continuidad_id`` in
        part of its occurrences. An unstamped occurrence may start a chain of its
        own only where its lineage was examined and recorded: an absence written
        by this plan or already declared, or a first-edition row an adjudicated
        ruling names -- a first edition has no predecessor, so an identifier
        there claims no continuation. Returns the identifiers that cannot be
        settled; their chains must be refused instead.
        """
        revisions = ordered_revisions(self.modelo)
        first = revisions[0].id
        ruled_first = {
            part.strip()
            for ruling in self.rulings.values()
            if ruling.predecessor == first
            for group in (ruling.grounded, ruling.held, ruling.withheld, ruling.merged)
            for left, _ in group
            for part in left.split(" + ")
            if part.strip()
        }
        occurrences: dict[str, list[str]] = collections.defaultdict(list)
        for revision in revisions:
            for casilla in revision.casillas:
                occurrences[casilla.id].append(revision.id)
        unresolvable: set[str] = set()
        starts: list[tuple[str, str]] = []
        for casilla_id, found in occurrences.items():
            unstamped = [revision for revision in found if (revision, casilla_id) not in self.state.ids]
            if len(found) < 2 or not unstamped or len(unstamped) == len(found):
                continue
            if all(self._may_start_chain(revision, casilla_id, first, ruled_first) for revision in unstamped):
                starts.extend((revision, casilla_id) for revision in unstamped)
            else:
                unresolvable.add(casilla_id)
        if unresolvable:
            return frozenset(unresolvable)
        for revision, casilla_id in starts:
            chain = self._fresh_chain_id(revision, casilla_id)
            self.state.link(chain, ((revision, casilla_id),))
            self.plan.set_keys(revision, casilla_id, continuidad_id=chain)
            self.plan.counts["chain_start"] += 1
        return frozenset[str]()

    def _may_start_chain(self, revision: str, casilla_id: str, first: str, ruled_first: set[str]) -> bool:
        planned = self.plan.edits.get((revision, casilla_id), {}).get("continuidad_origin")
        if planned is not None:
            return not CasillaLineageOrigin(planned).continues_a_chain
        for casilla in self.modelo.revisions[revision].casillas:
            if casilla.id == casilla_id and casilla.continuidad_origin is not None:
                return not casilla.continuidad_origin.continues_a_chain
        return revision == first and casilla_id in ruled_first

    def _fresh_chain_id(self, revision: str, casilla_id: str) -> str:
        role = self.state.roles[(revision, casilla_id)]
        candidates: list[str] = [_role_derived(role)] if role is not None else []
        candidates += [_slug(casilla_id), _slug(f"{casilla_id}-{revision}")]
        for candidate in candidates:
            if candidate and _CONTINUIDAD_ID.match(candidate) and not self.state.members.get(candidate):
                return candidate
        raise ValueError(f"modelo {self.modelo_id}: no free continuidad_id for {revision}/{casilla_id}")

    # -- pair walk

    def run(self) -> LineagePlan:
        revisions = ordered_revisions(self.modelo)
        for previous, successor in pairwise(revisions):
            self._pair(previous, successor)
        missing = set(self.rulings) - {(p.id, s.id) for p, s in pairwise(revisions)}
        if missing:
            raise ValueError(f"modelo {self.modelo_id}: rulings name boundaries that do not exist: {sorted(missing)}")
        return self.plan

    def _pair(self, previous: ModeloRevision, successor: ModeloRevision) -> None:
        pair = (previous.id, successor.id)
        if revisions_overlap(previous, successor):
            for casilla in successor.casillas:
                if casilla.continuidad_origin is None:
                    self.plan.refuse(
                        successor.id,
                        casilla.id,
                        LineageRefusalCategory.OVERLAPPING_PREDECESSOR,
                        f"{previous.id} and {successor.id} share a validity window; neither precedes the other",
                    )
            return
        ruling = self.rulings.get(pair)
        claimed = {
            casilla.id
            for casilla in previous.casillas
            if casilla.continuidad_id is not None
            and any(other.continuidad_id == casilla.continuidad_id for other in successor.casillas)
        }
        handled: set[str] = set()
        if ruling is not None:
            handled = self._apply_ruling(ruling, previous, successor, claimed)
        hold = None if ruling is not None else positional_hold(previous, successor)
        if hold is not None:
            self.plan.notes.append(f"{previous.id} -> {successor.id}: {hold}")
        previous_by_id = {casilla.id: casilla for casilla in previous.casillas}
        prev_design = self.oracle.for_revision(previous)
        succ_design = self.oracle.for_revision(successor)
        design_trust = _design_trust(previous, successor, prev_design, succ_design)
        prior_chains = self.state.ids_in(previous.id)
        for casilla in successor.casillas:
            if casilla.id in handled:
                continue
            if casilla.continuidad_origin is not None:
                self.plan.counts[casilla.continuidad_origin.value] += 1
                continue
            if casilla.continuidad_id is not None and casilla.continuidad_id in prior_chains:
                self.plan.counts["declared"] += 1
                continue
            candidate = previous_by_id.get(casilla.id)
            if candidate is not None:
                if ruling is not None and ruling.refuse_bare:
                    self.plan.refuse(
                        successor.id,
                        casilla.id,
                        LineageRefusalCategory.RULING_REFUSES_BARE,
                        "adjudication proves the identifier space was reassigned across this boundary",
                        predecessor=candidate.id,
                    )
                    continue
                if hold is not None:
                    self.plan.refuse(
                        successor.id, casilla.id, LineageRefusalCategory.POSITIONAL_HOLD, hold, predecessor=candidate.id
                    )
                    continue
                category, detail = admit_bare_chain(candidate, casilla)
                if category is not None:
                    self.plan.refuse(successor.id, casilla.id, category, detail, predecessor=candidate.id)
                    continue
                if casilla.id in self.forbidden:
                    self.plan.refuse(
                        successor.id,
                        casilla.id,
                        LineageRefusalCategory.PARTIAL_STAMP,
                        _PARTIAL_STAMP,
                        predecessor=candidate.id,
                    )
                    continue
                refused = self._write_chain(candidate, casilla, pair, CasillaLineageOrigin.SEEDED, None, claimed)
                if refused is not None:
                    self.plan.refuse(
                        successor.id,
                        casilla.id,
                        LineageRefusalCategory.CHAIN_CONTRACT,
                        refused,
                        predecessor=candidate.id,
                    )
                continue
            self._classify_absence(previous, successor, casilla, prev_design, succ_design, design_trust)

    def _classify_absence(
        self,
        previous: ModeloRevision,
        successor: ModeloRevision,
        casilla: CasillaDefinition,
        prev_design: DesignInventory | str,
        succ_design: DesignInventory | str,
        design_trust: str | None,
    ) -> None:
        box = printed_box(casilla)
        if box is None:
            self.plan.refuse(
                successor.id,
                casilla.id,
                LineageRefusalCategory.ABSENCE_UNCLASSIFIED,
                "no predecessor row and no printed box, so no record design can say which kind of absence this is",
            )
            return
        if design_trust is not None or isinstance(prev_design, str) or isinstance(succ_design, str):
            reason = design_trust or "the record design pair cannot be read"
            self.plan.refuse(successor.id, casilla.id, LineageRefusalCategory.ABSENCE_UNCLASSIFIED, reason)
            return
        declarers = sorted(other.id for other in previous.casillas if printed_box(other) == box)
        if declarers:
            self.plan.refuse(
                successor.id,
                casilla.id,
                LineageRefusalCategory.PRINTED_BOX_FORK,
                f"the predecessor edition declares printed box [{box}] on {declarers[:2]}; identity is read from "
                "form_number alone and lineage is one-to-one, so this is not an absence",
            )
            return
        succ_line = succ_design.defining_line(box)
        if succ_line is None:
            self.plan.refuse(
                successor.id,
                casilla.id,
                LineageRefusalCategory.ABSENCE_UNCLASSIFIED,
                f"box [{box}] is printed on more than one line of {succ_design.relative_path}; page is unqualified",
            )
            return
        if box in prev_design.boxes:
            prev_line = prev_design.defining_line(box)
            if prev_line is None:
                self.plan.refuse(
                    successor.id,
                    casilla.id,
                    LineageRefusalCategory.ABSENCE_UNCLASSIFIED,
                    f"box [{box}] is printed on more than one line of {prev_design.relative_path}; page is unqualified",
                )
                return
            self._write_absence(
                successor.id,
                casilla,
                CasillaLineageOrigin.PREDECESSOR_EDITION_SILENT,
                f"{_cite(prev_design, prev_line)} prints box [{box}] ({prev_design.snippet(prev_line)}); "
                f"edition {previous.id} declares no row for it",
            )
            return
        self._write_absence(
            successor.id,
            casilla,
            CasillaLineageOrigin.NEW_ON_FORM,
            f"{_cite(succ_design, succ_line)} prints box [{box}]; {_cite(prev_design, None)} prints no box [{box}] "
            "and retires none",
        )

    # -- rulings

    def _apply_ruling(
        self,
        ruling: Ruling,
        previous: ModeloRevision,
        successor: ModeloRevision,
        claimed: set[str],
    ) -> set[str]:
        pair = (previous.id, successor.id)
        prev_rows = {casilla.id: casilla for casilla in previous.casillas}
        succ_rows = {casilla.id: casilla for casilla in successor.casillas}
        prev_design = self.oracle.for_revision(previous)
        succ_design = self.oracle.for_revision(successor)
        handled: set[str] = set()

        def require(rows: Mapping[str, CasillaDefinition], casilla_id: str, side: str) -> CasillaDefinition:
            if casilla_id not in rows:
                raise ValueError(f"modelo {self.modelo_id} ruling {pair}: unknown {side} row {casilla_id!r}")
            return rows[casilla_id]

        def stem_of(casilla_id: str) -> str:
            return re.sub(r"-\d+$", "", casilla_id)

        for left, right in ruling.grounded:
            prev_row, succ_row = require(prev_rows, left, "predecessor"), require(succ_rows, right, "successor")
            handled.add(right)
            if succ_row.continuidad_origin is not None:
                self.plan.counts[succ_row.continuidad_origin.value] += 1
                continue
            if left in self.forbidden or right in self.forbidden:
                self.plan.refuse(
                    successor.id, right, LineageRefusalCategory.PARTIAL_STAMP, _PARTIAL_STAMP, predecessor=left
                )
                continue
            evidence = _grounded_evidence(prev_row, succ_row, prev_design, succ_design, ruling.rationale)
            if evidence is None:
                self.plan.refuse(
                    successor.id,
                    right,
                    LineageRefusalCategory.GROUNDED_UNLOCALISED,
                    "the ruling proves this continuation but neither a printed-box line nor a record campo "
                    "locates both rows in the pinned designs",
                    predecessor=left,
                )
                continue
            refused = self._write_chain(prev_row, succ_row, pair, CasillaLineageOrigin.GROUNDED, evidence, claimed)
            if refused is not None:
                self.plan.refuse(
                    successor.id,
                    right,
                    LineageRefusalCategory.GROUNDED_BLOCKED,
                    f"{refused}. Evidence: {evidence}",
                    predecessor=left,
                )
        for group, reason, category in (
            (ruling.held, ruling.held_reason, LineageRefusalCategory.HELD),
            (ruling.withheld, ruling.withheld_reason, LineageRefusalCategory.WITHHELD),
            (ruling.merged, ruling.merged_reason, LineageRefusalCategory.MERGED),
        ):
            for left, right in group:
                # A contested row names no single predecessor: which one it continues is the open question.
                for part in filter(None, (piece.strip() for piece in left.split(" + "))):
                    require(prev_rows, part, "predecessor")
                require(succ_rows, right, "successor")
                handled.add(right)
                self.plan.refuse(successor.id, right, category, reason, predecessor=left or None)
        for casilla_id, casilla in succ_rows.items():
            if casilla_id in handled:
                continue
            # A stem rule speaks for occurrences the predecessor does not carry by identifier; an
            # occurrence it does carry is judged as a bare chain like any other row.
            stem = None if casilla_id in prev_rows else stem_of(casilla_id)
            if stem is not None and stem in ruling.held_stems:
                handled.add(casilla_id)
                self.plan.refuse(successor.id, casilla_id, LineageRefusalCategory.HELD, ruling.held_reason)
            elif casilla_id in ruling.new_on_form or (stem is not None and stem in ruling.new_on_form_stems):
                handled.add(casilla_id)
                if casilla.continuidad_origin is not None:
                    self.plan.counts[casilla.continuidad_origin.value] += 1
                    continue
                evidence = _ruled_new_evidence(casilla, prev_design, succ_design, ruling.rationale)
                if evidence is None:
                    self.plan.refuse(
                        successor.id,
                        casilla_id,
                        LineageRefusalCategory.ABSENCE_UNLOCALISED,
                        "the ruling finds no predecessor, but neither a printed-box line nor a record campo "
                        "range locates the row in the pinned design",
                    )
                    continue
                self._write_absence(successor.id, casilla, CasillaLineageOrigin.NEW_ON_FORM, evidence)
            elif casilla_id in ruling.not_on_form:
                handled.add(casilla_id)
                if casilla.continuidad_origin is not None:
                    self.plan.counts[casilla.continuidad_origin.value] += 1
                    continue
                if printed_box(casilla) is not None:
                    raise ValueError(f"modelo {self.modelo_id}: not_on_form row {casilla_id!r} states a printed box")
                design = succ_design if isinstance(succ_design, DesignInventory) else None
                where = _cite(design, None) if design is not None else f"the {successor.id} record design"
                self._write_absence(
                    successor.id,
                    casilla,
                    CasillaLineageOrigin.NOT_ON_FORM,
                    f"{where} numbers no box for this row and it states none; {ruling.rationale}",
                )
        named = set(ruling.new_on_form) | set(ruling.not_on_form)
        unknown = sorted(named - set(succ_rows))
        if unknown:
            raise ValueError(f"modelo {self.modelo_id} ruling {pair}: unknown successor rows {unknown[:5]}")
        for casilla_id in sorted(ruling.discontinued):
            require(prev_rows, casilla_id, "predecessor")
            self.plan.notes.append(
                f"{previous.id} -> {successor.id}: {casilla_id} is discontinued ({ruling.rationale})"
            )
        return handled


# --------------------------------------------------------------------------- evidence text


def _bounded(evidence: str) -> str:
    text = " ".join(evidence.split())
    if len(text) > _EVIDENCE_LIMIT:
        raise ValueError(f"evidence exceeds {_EVIDENCE_LIMIT} characters: {text[:120]!r}")
    return text


def _with_rationale(locus: str, rationale: str) -> str:
    """Append the ruling's rationale when it fits; the checkable locus is never cut."""
    combined = f"{locus}. {rationale}"
    return combined if len(" ".join(combined.split())) <= _EVIDENCE_LIMIT else f"{locus}."


def _cite(design: DesignInventory | None, line: int | None) -> str:
    if design is None:
        return "the record design"
    where = design.relative_path if line is None else f"{design.relative_path}:{line}"
    return f"{where} (sha256 {design.sha256[:12]})"


_BYTE_POSITIONS = re.compile(r"^\d+(?:\s*-\s*\d+)?$")


def _row_locus(casilla: CasillaDefinition, design: DesignInventory | str) -> str | None:
    """Where the design shows this row: a printed-box line, or a record and campo byte range.

    ``None`` when neither exists, so a claim about the row cannot name a checkable locus.
    """
    if not isinstance(design, DesignInventory):
        return None
    box = printed_box(casilla)
    if box is not None and (line := design.defining_line(box)) is not None:
        return f"{_cite(design, line)} box [{box}] ({design.snippet(line)})"
    if casilla.segmento and _BYTE_POSITIONS.match(casilla.number.strip()):
        return f"{_cite(design, None)} record {casilla.segmento} campo at byte position {casilla.number.strip()}"
    return None


def _grounded_evidence(
    previous: CasillaDefinition,
    successor: CasillaDefinition,
    prev_design: DesignInventory | str,
    succ_design: DesignInventory | str,
    rationale: str,
) -> str | None:
    before, after = _row_locus(previous, prev_design), _row_locus(successor, succ_design)
    if before is None or after is None:
        return None
    return _with_rationale(f"{before} continues as {after}", rationale)


def _ruled_new_evidence(
    casilla: CasillaDefinition,
    prev_design: DesignInventory | str,
    succ_design: DesignInventory | str,
    rationale: str,
) -> str | None:
    locus = _row_locus(casilla, succ_design)
    box = printed_box(casilla)
    if locus is None or not isinstance(prev_design, DesignInventory):
        return None
    earlier = prev_design.lines.get(box, ()) if box is not None else ()
    if len(earlier) == 1:
        line = earlier[0]
        before = f"{_cite(prev_design, line)} prints [{box}] as another concept ({prev_design.snippet(line)})"
    elif earlier:
        before = f"{_cite(prev_design, None)} prints [{box}] only as other concepts, at lines {list(earlier[:4])}"
    elif box is not None:
        before = f"{_cite(prev_design, None)} prints no box [{box}]"
    else:
        before = f"no counterpart in {_cite(prev_design, None)}"
    return _with_rationale(f"{locus}; {before}", rationale)


def _design_trust(
    previous: ModeloRevision,
    successor: ModeloRevision,
    prev_design: DesignInventory | str,
    succ_design: DesignInventory | str,
) -> str | None:
    """Why the design pair cannot classify an absence, or ``None`` when it can."""
    for revision, design in ((previous, prev_design), (successor, succ_design)):
        if isinstance(design, str):
            return design
        stated = {box for casilla in revision.casillas if (box := printed_box(casilla)) is not None}
        unresolved = sorted(stated - design.boxes)
        if unresolved:
            return (
                f"{design.relative_path} does not print {len(unresolved)} box(es) edition {revision.id} declares "
                f"(e.g. {unresolved[:4]}), so its inventory cannot be trusted"
            )
    if isinstance(prev_design, str) or isinstance(succ_design, str):
        return "the record design pair cannot be read"
    if prev_design.relative_path == succ_design.relative_path:
        return None
    retired = sorted(prev_design.boxes - succ_design.boxes)
    if retired:
        return (
            f"{succ_design.relative_path} retires {len(retired)} box(es) of the predecessor design "
            f"(e.g. {retired[:4]}); a new number may be a renumbering"
        )
    return None


# --------------------------------------------------------------------------- consistency


def contradictions(modelo: ModeloDefinition, plan: LineagePlan) -> list[str]:
    """Cross-revision contradictions the planned state would contain.

    A continuation must find its chain on the predecessor edition; an absence
    must not. Checked over every row carrying an origin once the plan is applied.
    """
    revisions = ordered_revisions(modelo)
    stated: dict[tuple[str, str], dict[str, str | None]] = {}
    for revision in revisions:
        for casilla in revision.casillas:
            row = {
                "continuidad_id": casilla.continuidad_id,
                "continuidad_origin": None if casilla.continuidad_origin is None else casilla.continuidad_origin.value,
            }
            row.update(plan.edits.get((revision.id, casilla.id), {}))
            stated[(revision.id, casilla.id)] = row
    problems: list[str] = []
    for previous, successor in pairwise(revisions):
        prior = {row["continuidad_id"] for (rev, _), row in stated.items() if rev == previous.id} - {None}
        seen: collections.Counter[str] = collections.Counter()
        for (rev, casilla_id), row in stated.items():
            if rev != successor.id:
                continue
            chain, origin = row["continuidad_id"], row["continuidad_origin"]
            if chain is not None:
                seen[chain] += 1
            if origin is None:
                continue
            continues = CasillaLineageOrigin(origin).continues_a_chain
            if continues and chain not in prior:
                problems.append(f"{successor.id}/{casilla_id}: {origin} but chain {chain!r} absent from {previous.id}")
            if not continues and chain is not None and chain in prior:
                problems.append(f"{successor.id}/{casilla_id}: {origin} but chain {chain!r} present in {previous.id}")
        problems.extend(f"{successor.id}: chain {chain!r} on {n} rows" for chain, n in seen.items() if n > 1)
    return problems


def materialise(modelo: ModeloDefinition, plan: LineagePlan) -> ModeloDefinition:
    """The modelo as it will load once the plan is written."""
    revisions = {}
    for revision_id, revision in modelo.revisions.items():
        casillas = []
        for casilla in revision.casillas:
            keys = plan.edits.get((revision.id, casilla.id))
            if keys is None:
                casillas.append(casilla)
                continue
            update: dict[str, object] = dict(keys)
            if "continuidad_origin" in update:
                update["continuidad_origin"] = CasillaLineageOrigin(keys["continuidad_origin"])
            casillas.append(casilla.model_copy(update=update))
        revisions[revision_id] = revision.model_copy(update={"casillas": tuple(casillas)})
    return modelo.model_copy(update={"revisions": revisions})


def gate_regressions(modelo: ModeloDefinition, plan: LineagePlan) -> list[str]:
    """Registry-scope failures the plan would introduce, judged by the registry's own validators.

    The seeder's incremental checks decide link by link; this is the exact
    answer, so the plan and the load-time gates cannot disagree.
    """
    if not plan.edits:
        # A plan with no edits materialises to the modelo itself, so it can regress nothing.
        return []
    before = set(validate_registry_scope((modelo,)))
    return sorted(set(validate_registry_scope((materialise(modelo, plan),))) - before)


# --------------------------------------------------------------------------- writing


def insert_lineage_keys(text: str, revision: str, edits: Mapping[str, Mapping[str, str]]) -> tuple[str, set[str]]:
    """Insert lineage keys into the named casilla tables of one declaration file.

    Returns the new text and the casilla ids it edited. A key already present
    with the same value is left alone; a differing value is refused.
    """
    lines = text.split("\n")
    output: list[str] = []
    done: set[str] = set()
    index = 0
    while index < len(lines):
        line = lines[index]
        output.append(line)
        header = _CASILLA_HEADER.match(line)
        index += 1
        if header is None or (header.group(1) or header.group(2)) != revision:
            continue
        block: list[str] = []
        while index < len(lines) and not lines[index].lstrip().startswith("["):
            block.append(lines[index])
            index += 1
        casilla_id = next((m.group(1) for entry in block if (m := _ID_LINE.match(entry))), None)
        if casilla_id is None or casilla_id not in edits:
            output.extend(block)
            continue
        output.extend(_edit_block(block, casilla_id, edits[casilla_id]))
        done.add(casilla_id)
    return "\n".join(output), done


def _edit_block(block: list[str], casilla_id: str, keys: Mapping[str, str]) -> list[str]:
    present: dict[str, int] = {}
    for position, entry in enumerate(block):
        key = entry.split("=", 1)[0].strip()
        if key in _LINEAGE_KEYS or key == "id":
            present[key] = position
    new_lines: list[str] = []
    for key in _LINEAGE_KEYS:
        if key not in keys:
            continue
        rendered = f"{key} = {json.dumps(keys[key], ensure_ascii=False)}"
        if key in present:
            if block[present[key]].strip() != rendered:
                raise ValueError(f"casilla {casilla_id!r} already declares a different {key}: {block[present[key]]!r}")
            continue
        new_lines.append(rendered)
    anchor = present.get("continuidad_id", present["id"])
    return [*block[: anchor + 1], *new_lines, *block[anchor + 1 :]]


def _casilla_files(modelo_id: str, revision: str) -> Iterator[Path]:
    yield from sorted((_MODELOS_ROOT / modelo_id / "revisions" / revision / "casillas").rglob("*.toml"))


def apply_plan(plan: LineagePlan) -> int:
    """Write a plan's edits into the declaration files; return the number of rows edited."""
    by_revision: dict[str, dict[str, dict[str, str]]] = collections.defaultdict(dict)
    for (revision, casilla_id), keys in plan.edits.items():
        by_revision[revision][casilla_id] = keys
    edited = 0
    for revision, edits in sorted(by_revision.items()):
        remaining = dict(edits)
        for path in _casilla_files(plan.modelo, revision):
            text = path.read_text(encoding=_UTF_8)
            new_text, done = insert_lineage_keys(text, revision, remaining)
            if new_text != text:
                path.write_text(new_text, encoding=_UTF_8, newline="\n")
            for casilla_id in done:
                remaining.pop(casilla_id)
            edited += len(done)
        if remaining:
            raise ValueError(f"modelo {plan.modelo} {revision}: rows not found on disk: {sorted(remaining)[:5]}")
    return edited


# --------------------------------------------------------------------------- driver


def plan_modelo(
    modelo_id: str,
    modelo: ModeloDefinition,
    oracle: DesignOracle,
    rulings: Mapping[str, list[Ruling]],
) -> LineagePlan:
    """Plan every lineage disposition for one modelo.

    Planning repeats until no identifier would be left partly stamped: each pass
    forbids chains on the identifiers the previous pass could not settle.
    """
    forbidden: frozenset[str] = frozenset[str]()
    while True:
        planner = _ModeloPlanner(modelo_id, modelo, oracle, rulings.get(modelo_id, []), forbidden)
        plan = planner.run()
        unsettled = planner.settle_partial_stamps()
        if not unsettled:
            return plan
        if unsettled <= forbidden:
            raise ValueError(f"modelo {modelo_id}: identifiers stay partly stamped: {sorted(unsettled)[:5]}")
        forbidden |= unsettled


def residual_plan(modelo_id: str, modelo: ModeloDefinition, rulings: Iterable[Ruling]) -> LineagePlan:
    """Refuse, row by row, every unresolved successor row of an excluded modelo.

    Writes nothing: the plan carries refusals only. A row an adjudicated ruling
    holds, withholds or merges is refused under that ruling's category and
    reason; every other row takes the modelo's residual category. The rows are
    exactly those the lineage totality rule reports, so the ledger and the gate
    reading it cannot disagree about which rows need an entry.
    """
    excluded = EXCLUDED_MODELOS[modelo_id]
    ruled: dict[tuple[str, str], tuple[LineageRefusalCategory, str, str]] = {}
    for ruling in rulings:
        for category, pairs, reason in (
            (LineageRefusalCategory.HELD, ruling.held, ruling.held_reason),
            (LineageRefusalCategory.WITHHELD, ruling.withheld, ruling.withheld_reason),
            (LineageRefusalCategory.MERGED, ruling.merged, ruling.merged_reason),
        ):
            for predecessor, successor in pairs:
                ruled[(ruling.successor, successor)] = (category, reason, predecessor)
    rows = {
        (str(revision.id), str(casilla.id)): casilla
        for revision in modelo.revisions.values()
        for casilla in revision.casillas
    }
    plan = LineagePlan(modelo_id)
    for key in unresolved_successor_rows(modelo):
        if excluded.residual_category is None:
            raise ValueError(
                f"modelo {modelo_id} {key.revision}/{key.casilla}: an unresolved successor row in a modelo that "
                f"cannot have one ({excluded.residual_reason})"
            )
        precise = ruled.get((key.revision, key.casilla))
        if precise is not None:
            category, reason, predecessor = precise
            plan.refuse(key.revision, key.casilla, category, reason, predecessor)
            continue
        chain = rows[(key.revision, key.casilla)].continuidad_id
        shape = "no continuidad_id" if chain is None else f"continuidad_id {chain!r} starts its chain in this edition"
        plan.refuse(key.revision, key.casilla, excluded.residual_category, f"{excluded.residual_reason}; {shape}")
    return plan


def _ledger(plans: list[LineagePlan], checks: Mapping[str, list[str]]) -> str:
    out = [
        "# Casilla lineage ledger, written by casilla_lineage_seed.py --apply. Do not edit by hand.",
        "#",
        "# Every successor row that neither carries lineage nor declares its kind of none is listed",
        "# here, one refusal per row, with the category and reason it stopped. That includes every",
        "# such row of an excluded modelo, whether examined or not. The list is closed: a row missing",
        "# from it, or an entry whose row no longer needs it, fails the lineage totality gate.",
        "",
    ]
    for modelo_id, excluded in sorted(EXCLUDED_MODELOS.items()):
        out += ["[[excluded]]", f"modelo = {json.dumps(modelo_id)}", f"reason = {json.dumps(excluded.reason)}", ""]
    for plan in plans:
        out.append(f"[summary.{json.dumps(plan.modelo)}]")
        # Chain starts are an artefact of one write, not a disposition; the rows carry them.
        out += [f"{json.dumps(key)} = {value}" for key, value in sorted(plan.counts.items()) if key != "chain_start"]
        out.append(f"contradictions = {len(checks[plan.modelo])}")
        if plan.notes:
            out.append("notes = [")
            out += [f"  {json.dumps(note, ensure_ascii=False)}," for note in plan.notes]
            out.append("]")
        out.append("")
    for plan in plans:
        for refusal in plan.refusals:
            out += [
                "[[refusal]]",
                f"modelo = {json.dumps(refusal.modelo)}",
                f"revision = {json.dumps(refusal.revision)}",
                f"casilla = {json.dumps(refusal.casilla_id, ensure_ascii=False)}",
            ]
            if refusal.predecessor is not None:
                out.append(f"predecessor = {json.dumps(refusal.predecessor, ensure_ascii=False)}")
            out += [
                f"category = {json.dumps(refusal.category)}",
                f"reason = {json.dumps(refusal.reason, ensure_ascii=False)}",
                "",
            ]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--apply", action="store_true", help="write the planned keys and the ledger")
    parser.add_argument("--modelo", action="append", help="limit to these modelos (repeatable)")
    args = parser.parse_args(argv)

    authority = compiled_bundled_authority()
    oracle = DesignOracle(authority)
    rulings = load_rulings()
    selected = [
        modelo_id
        for modelo_id in bundled_modelo_ids()
        if modelo_id not in EXCLUDED_MODELOS
        and len(authority.modelo(modelo_id).revisions) > 1
        and (not args.modelo or modelo_id in args.modelo)
    ]
    unknown = set(rulings) - set(selected) - set(EXCLUDED_MODELOS)
    if unknown and not args.modelo:
        raise SystemExit(f"rulings name modelos outside scope: {sorted(unknown)}")
    plans = [plan_modelo(modelo_id, authority.modelo(modelo_id), oracle, rulings) for modelo_id in selected]
    plans += [
        residual_plan(modelo_id, authority.modelo(modelo_id), rulings.get(modelo_id, ()))
        for modelo_id in bundled_modelo_ids()
        if modelo_id in EXCLUDED_MODELOS and (not args.modelo or modelo_id in args.modelo)
    ]
    plans.sort(key=lambda plan: plan.modelo)
    checks = {
        plan.modelo: [
            *contradictions(authority.modelo(plan.modelo), plan),
            *(f"gate: {failure}" for failure in gate_regressions(authority.modelo(plan.modelo), plan)),
        ]
        for plan in plans
    }

    totals: collections.Counter[str] = collections.Counter()
    for plan in plans:
        totals.update(plan.counts)
        shown = ", ".join(f"{key}={value}" for key, value in sorted(plan.counts.items()))
        print(f"{plan.modelo}: {shown}; contradictions={len(checks[plan.modelo])}")
        for problem in checks[plan.modelo][:5]:
            print(f"    CONTRADICTION {problem}")
    print("total:", ", ".join(f"{key}={value}" for key, value in sorted(totals.items())))
    if any(checks.values()):
        print("refusing to write: the plan contains contradictions", file=sys.stderr)
        return 1
    if args.apply:
        edited = sum(apply_plan(plan) for plan in plans)
        if not args.modelo:
            LEDGER_PATH.write_text(_ledger(plans, checks) + "\n", encoding=_UTF_8, newline="\n")
        print(f"edited {edited} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
