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

Modelos are compiled one directory at a time rather than through the
whole-corpus authority, which refuses the whole corpus when any single modelo
fails and so let one modelo's defect stop seeding for every other -- including
modelos it shares nothing with, and modelos this seeder is excluded from
writing at all. A modelo that cannot be compiled is recorded for that run as a
``[[load_failed]]`` entry carrying the first message its loader raised, and
every other modelo is seeded as before.

A modelo whose corpus already stamps a casilla identifier on some editions and
neither stamps nor excuses it on the others is held back the same way. The
registry refuses such an identifier, so no chain may be written into it and the
seeder must not try; but that is one modelo's half-finished stamping, and it is
not a reason to stop seeding the rest of the corpus. The modelo is recorded for
that run as a ``[[stamping_in_progress]]`` entry naming the chain, the editions
that carry it and the editions that do not, is skipped entirely, and every other
modelo is planned as before. The refusal to write into such a chain is unchanged:
the modelo is skipped, never seeded on weaker evidence. The run prints both kinds
of skip so a reader sees it without opening the ledger. Nor does the record make
a half-stamped chain tolerable: the registry's own partial-stamping gate pins
such chains at zero as a defect rather than a backlog, and reads the authored
corpus directly, so it stays red for exactly as long as an entry stands here.

Neither kind of skip is allowed to shrink the ledger. A skipped modelo's rows
were not judged this run, so they cannot be rejudged -- but they were judged
before, and dropping their entries would silently remove that modelo from the
closed list. Every previous ``[[refusal]]`` of a skipped modelo is therefore
carried forward verbatim, marked ``carried_from_previous_run``, naming why it
could not be rejudged and the run identifier of the last run that actually
judged it; see :func:`render_ledger`.

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

Reads each modelo through the registry loader and the shared source catalogue.
Writes insert keys into the casilla declaration files as text, never
reformatting them, and refuse to overwrite a differing value already present.
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
from datetime import UTC, datetime
from enum import StrEnum
from itertools import pairwise
from pathlib import Path

from cadrumo.domain.calculations.registry.casilla_lineage import CasillaLineageOrigin
from cadrumo.domain.calculations.registry.casilla_lineage_totality import (
    judging_predecessor,
    unresolved_successor_rows,
)
from cadrumo.domain.calculations.registry.errors import RegistryError, RegistryLoadError
from cadrumo.domain.calculations.registry.revision_order import ordered_revisions
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_references import SourceReference
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition

from ..compiler.loader import load_modelo_directory, load_shared_catalogues
from ..compiler.loader_cache import ModeloSource, discover_modelo_sources
from ..compiler.registry_scope import validate_registry_scope
from .casilla_id_grammar import classify_casilla_id

__all__ = [
    "EXCLUDED_MODELOS",
    "SCHEMA_EVIDENCE_LIMIT",
    "CarriedRefusal",
    "DesignInventory",
    "DesignPlacement",
    "ExcludedModelo",
    "LineagePlan",
    "LineageRefusalCategory",
    "LongEvidence",
    "ModeloLoadFailure",
    "PartialStamping",
    "PreviousLedger",
    "admit_bare_chain",
    "carried_refusals",
    "contradictions",
    "gate_regressions",
    "insert_lineage_keys",
    "judged_pairs",
    "load_corpus",
    "load_previous_ledger",
    "parse_design_inventory",
    "partition_contradictions",
    "plan_corpus",
    "plan_modelo",
    "render_ledger",
    "residual_plan",
    "run_identifier",
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
_REGISTRY_ROOT = _DATA_ROOT / "registry" / "aeat"
_MODELOS_ROOT = _REGISTRY_ROOT / "modelos"
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
EXCLUDED_MODELOS: Mapping[str, ExcludedModelo] = {
    "100": ExcludedModelo(
        reason=_M100_REASON,
        residual_category=LineageRefusalCategory.NOT_EXAMINED,
        residual_reason=f"not examined; its lineage is its own campaign: {_M100_REASON}",
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
# Beyond a plain number, modelo 036 prints three non-numeric box shapes: a section
# letter with one or two digits and an optional subdivision letter ([A4], [A72], [B3B]),
# a bis box ([412bis], [4774bis]) and a dotted subdivision ([716.a]). Each is no wider
# than the record designs print, so [AB12], [A123], [a4], [412ter] and [716.ab] are not
# boxes.
_NON_NUMERIC_BOX = r"\d{1,5}bis|\d{1,5}\.[a-z]|[A-Z]\d{1,2}[A-Z]?"
_PRINTED_BOX = re.compile(rf"^(?:{_NON_NUMERIC_BOX})$")
_DESIGN_BOX = re.compile(rf"\[\s*({_NON_NUMERIC_BOX}|\d{{1,5}})\s*\]")
_ALPHANUMERIC = re.compile(r"\w")
_LIST_SEPARATOR = re.compile(r"^\s*(?:,|y|e|o|a)\s*$", re.IGNORECASE)
_OPERATOR_GAP = re.compile(r"^\s*[-+x*/=]\s*$")
# An extract heads each record's campo table with the page the design prints it on
# ("# Pag. 3", "# Pág. 6"); every campo row below it belongs to that record.
_RECORD_HEADING = re.compile(r"^#+\s+(\S.*)$")
_CASILLA_HEADER = re.compile(r'^\[\[revisions\.(?:"([^"]+)"|([A-Za-z0-9_-]+))\.casillas\]\]\s*$')
_ID_LINE = re.compile(r"""^id\s*=\s*(?:"([^"]+)"|'([^']+)')\s*$""")
_CONTINUIDAD_ID = re.compile(r"^[a-z0-9][a-z0-9_-]*[a-z0-9]$|^[a-z0-9]$")
_EVIDENCE_ADVISORY = 512
_RECORDED_REASON_LIMIT = 512
_SNIPPET = 70


def _schema_evidence_limit() -> int:
    """The maximum length the casilla row model accepts for ``continuidad_evidence``.

    Read off the model rather than restated here, so the seeder's bound is the
    one that will actually refuse the value and cannot drift from it.
    """
    for constraint in CasillaDefinition.model_fields["continuidad_evidence"].metadata:
        limit = getattr(constraint, "max_length", None)
        if limit is not None:
            return int(limit)
    raise ValueError("CasillaDefinition.continuidad_evidence declares no maximum length")


SCHEMA_EVIDENCE_LIMIT = _schema_evidence_limit()
_MIN_POSITIONAL_SPACE = 5
_MAX_POSITIONAL_EXPANSION = 3.0
_LINEAGE_KEYS = ("continuidad_id", "continuidad_origin", "continuidad_evidence")
_PARTIAL_STAMP = (
    "another occurrence of this identifier cannot carry a continuidad_id, and the registry refuses an identifier "
    "stamped in only part of its occurrences"
)


# --------------------------------------------------------------------------- design oracle


@dataclass(frozen=True, slots=True)
class DesignPlacement:
    """Where one design line puts its campo: the record it belongs to and its byte span.

    ``record`` is the record the extract heads the campo table with (``Pag. 3``),
    ``offset`` the one-based byte position the design prints in its *Posic.*
    column and ``length`` the width it prints in *Lon*.
    """

    record: str
    offset: int
    length: int

    @property
    def end(self) -> int:
        """The first byte position after this campo."""
        return self.offset + self.length


@dataclass(frozen=True, slots=True)
class DesignInventory:
    """The boxes one official record design prints, with the line each is defined on.

    A campo description ENDS with the box it prints, and any other bracket in it
    is an operand of the formula it quotes (``Resultado ([17] + [19] - [25])
    [26]`` prints 26). A cell enumerating boxes (``las casillas [20], [21] y
    [22]``) is a note about boxes, not a campo, and defines none.

    AEAT prints ONE box number across several campo lines when the field it
    numbers is split into printed components -- a date as dia, mes and ano at
    ``@263+2``, ``@265+2`` and ``@267+4``, filed under box ``[425]`` alone. Those
    lines locate the box as surely as a single line does, because together they
    tile one contiguous span of one record. The same number printed for two
    unrelated campos does not, and stays unlocalised.
    """

    relative_path: str
    sha256: str
    lines: Mapping[int | str, tuple[int, ...]]
    text_by_line: Mapping[int, str]
    placements: Mapping[int, DesignPlacement]

    @property
    def boxes(self) -> frozenset[int | str]:
        """Every box number this design prints."""
        return frozenset(self.lines)

    def defining_lines(self, box: int | str) -> tuple[int, ...] | None:
        """The line(s) locating ``box``, or ``None`` when this design locates it nowhere.

        One line locates a box outright. Several locate it only when they are the
        printed components of ONE field: the same record, and byte spans that tile
        one contiguous run. Any other repetition prints one number for more than
        one concept and locates nothing.
        """
        found = self.lines.get(box, ())
        if not found:
            return None
        if len(found) == 1:
            return found
        return found if self._component_span(found) is not None else None

    def defining_line(self, box: int | str) -> int | None:
        """The line a citation of ``box`` anchors on, or ``None`` when it is unlocalised.

        For a field printed as several components this is the first of them; the
        span the components tile is read off :meth:`component_span`.
        """
        found = self.defining_lines(box)
        return None if found is None else found[0]

    def component_span(self, box: int | str) -> DesignPlacement | None:
        """The one span a multi-component box tiles, or ``None`` when it has none."""
        found = self.lines.get(box, ())
        return None if len(found) < 2 else self._component_span(found)

    def unlocalised_reason(self, box: int | str) -> str:
        """Why several lines printing ``box`` do not locate it, for the refusal prose."""
        found = self.lines.get(box, ())
        placed = [self.placements.get(line) for line in found]
        if any(placement is None for placement in placed):
            unplaced = [line for line, placement in zip(found, placed, strict=True) if placement is None]
            return f"lines {list(found)} print it and {unplaced} record no byte position, so no span can be checked"
        spans = [placement for placement in placed if placement is not None]
        records = sorted({placement.record for placement in spans})
        if len(records) > 1:
            return f"lines {list(found)} print it in different records {records}, so they are not one field"
        printed = [f"@{placement.offset}+{placement.length}" for placement in sorted(spans, key=lambda p: p.offset)]
        return f"lines {list(found)} print it at {printed}, which do not tile one contiguous field"

    def snippet(self, line: int) -> str:
        """A short excerpt of one design line for evidence prose."""
        text = " ".join(self.text_by_line.get(line, "").replace("|", " ").split())
        return text if len(text) <= _SNIPPET else text[: _SNIPPET - 3] + "..."

    def _component_span(self, found: tuple[int, ...]) -> DesignPlacement | None:
        """The span ``found`` tiles as components of one field, or ``None`` when they do not."""
        placed = [self.placements.get(line) for line in found]
        if any(placement is None for placement in placed):
            return None
        spans = sorted((placement for placement in placed if placement is not None), key=lambda p: p.offset)
        if len({placement.record for placement in spans}) != 1:
            return None
        for before, after in pairwise(spans):
            if before.end != after.offset:
                return None
        return DesignPlacement(
            record=spans[0].record,
            offset=spans[0].offset,
            length=spans[-1].end - spans[0].offset,
        )


def parse_design_inventory(text: str, *, relative_path: str, sha256: str) -> DesignInventory:
    """Build a design's box inventory from its extracted text."""
    lines: dict[int | str, list[int]] = collections.defaultdict(list)
    text_by_line: dict[int, str] = {}
    placements: dict[int, DesignPlacement] = {}
    record = ""
    for number, line in enumerate(text.splitlines(), start=1):
        heading = _RECORD_HEADING.match(line)
        if heading is not None:
            record = " ".join(heading.group(1).split())
            continue
        cells = line.split("|")
        for cell in cells:
            box = _defined_box(cell)
            if box is not None:
                lines[box].append(number)
                text_by_line[number] = line
        if number in text_by_line and (placement := _placement(record, cells)) is not None:
            placements[number] = placement
    return DesignInventory(
        relative_path=relative_path,
        sha256=sha256,
        lines={box: tuple(found) for box, found in lines.items()},
        text_by_line=text_by_line,
        placements=placements,
    )


def _placement(record: str, cells: list[str]) -> DesignPlacement | None:
    """The byte span one campo row prints, or ``None`` when the row prints none.

    A campo row is ``Nº | Posic. | Lon | Tipo | Descripcion ...``; a row that
    does not print both a position and a width states no span to reason about.
    """
    if len(cells) < 3:
        return None
    offset, length = cells[1].strip(), cells[2].strip()
    if not _PLAIN_INTEGER.match(offset) or not _PLAIN_INTEGER.match(length):
        return None
    return DesignPlacement(record=record, offset=int(offset), length=int(length))


def _box_key(printed: str) -> int | str:
    """The comparable identity of one printed box token.

    A numeric box compares as an integer, so the five-digit ``[00101]`` and a
    row numbered ``101`` are the same box. A non-numeric box carries no numeric
    meaning and compares verbatim, case included.
    """
    return int(printed) if _PLAIN_INTEGER.match(printed) else printed


def _box_order(box: int | str) -> tuple[int, int, str]:
    """A total order over boxes for evidence prose: numeric boxes first, then non-numeric ones."""
    return (0, box, "") if isinstance(box, int) else (1, 0, box)


def _defined_box(cell: str) -> int | str | None:
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
    return _box_key(matches[-1].group(1))


def printed_box(casilla: CasillaDefinition) -> int | str | None:
    """Coverage: the printed box a row states in form_number OR its own number.

    A row's own number counts as a printed box when it is a plain integer or one
    of the non-numeric box shapes the record designs print; anything else -- a
    slug, a byte range -- is not a box.
    """
    if casilla.form_number is not None:
        return int(str(casilla.form_number))
    number = casilla.number.strip()
    if _PLAIN_INTEGER.match(number):
        return int(number)
    return number if _PRINTED_BOX.match(number) else None


def identity_box(casilla: CasillaDefinition) -> str | None:
    """Identity: the dedicated printed-number field and nothing else."""
    return None if casilla.form_number is None else str(casilla.form_number)


class DesignOracle:
    """Resolve and cache each edition's pinned official record design.

    The oracle reads the shared source catalogue and nothing else of the
    corpus: a revision names its designs by source ref, and the catalogue says
    where each one lives and what it hashes to. That catalogue is corpus-wide
    but compiles on its own -- :func:`load_shared_catalogues` builds it without
    compiling a single modelo -- so the oracle needs no whole-corpus authority
    and a modelo that fails to load cannot take it down.
    """

    def __init__(self, sources: Mapping[str, SourceReference]) -> None:
        self._sources = sources
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


@dataclass(frozen=True, slots=True)
class LongEvidence:
    """One row whose evidence runs past the advisory length but stays within the schema's cap.

    Written, not refused: the schema is the bound, and cutting a checkable
    citation to a house style loses the one thing the evidence is for. Reported
    so an unusually long citation is visible without opening the ledger.
    """

    modelo: str
    revision: str
    casilla: str
    length: int


@dataclass(slots=True)
class LineagePlan:
    """Every disposition for one modelo, plus the key edits that realise them."""

    modelo: str
    edits: dict[tuple[str, str], dict[str, str]] = field(default_factory=dict)
    counts: collections.Counter[str] = field(default_factory=collections.Counter)
    refusals: list[Refusal] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    long_evidence: list[LongEvidence] = field(default_factory=list)

    def record_evidence(self, revision: str, casilla_id: str, evidence: str) -> str:
        """Bound one evidence string by the schema's cap, recording it when it is unusually long."""
        text = _bounded(evidence)
        if len(text) > _EVIDENCE_ADVISORY:
            self.long_evidence.append(LongEvidence(self.modelo, revision, casilla_id, len(text)))
        return text

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


def judged_pairs(
    modelo: ModeloDefinition, revisions: tuple[ModeloRevision, ...]
) -> tuple[tuple[ModeloRevision, ModeloRevision], ...]:
    """Every ``(predecessor, successor)`` edition pair whose successor rows are judged.

    Pairing is the lineage totality rule's own
    :func:`~cadrumo.domain.calculations.registry.casilla_lineage_totality.judging_predecessor`,
    reused rather than restated: a predecessor is the edition an edition's rows
    continue from, which is a closed earlier edition and never a concurrent
    sibling sharing its validity window. Period selectors do not decide it --
    two adjacent editions may name overlapping period tokens while the earlier
    one closes before the later one opens, and those rows do continue.
    """
    return tuple(
        (predecessor, successor)
        for index, successor in enumerate(revisions)
        if (predecessor := judging_predecessor(modelo, revisions, index)) is not None
    )


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
        for previous, successor in judged_pairs(modelo, revisions):
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
            keys["continuidad_evidence"] = self.plan.record_evidence(pair[1], successor.id, evidence)
        self.plan.set_keys(pair[1], successor.id, **keys)
        self.plan.counts[origin.value] += 1
        return None

    def _write_absence(
        self, revision: str, casilla: CasillaDefinition, origin: CasillaLineageOrigin, evidence: str
    ) -> None:
        self.plan.set_keys(
            revision,
            casilla.id,
            continuidad_origin=origin.value,
            continuidad_evidence=self.plan.record_evidence(revision, casilla.id, evidence),
        )
        self.plan.counts[origin.value] += 1

    def _already_disposed(self, casilla: CasillaDefinition) -> bool:
        """Count a row whose continuation or kind of none the corpus already declares, and stop judging it.

        A declared ``continuidad_origin`` is the disposition the lineage
        totality rule reads to call the row resolved. Re-judging it here can
        only disagree with that rule, and a refusal it produced would put an
        entry in the ledger for a row the gate resolves -- a stale exception,
        not an unresolved row. Counted under the origin it declares, so the
        run's report still accounts for every successor row exactly once.
        """
        if casilla.continuidad_origin is None:
            return False
        self.plan.counts[casilla.continuidad_origin.value] += 1
        return True

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

    def partial_stamp_records(self, unsettled: frozenset[str]) -> tuple[PartialStamping, ...]:
        """Name what is half-stamped about each identifier :meth:`settle_partial_stamps` could not settle.

        Read after a pass that forbade chains on these identifiers, so what is
        left is the corpus's own state rather than anything this run planned:
        the chain the stamped editions already carry, and the editions that
        carry neither it nor an examined absence.
        """
        records: list[PartialStamping] = []
        for casilla_id in sorted(unsettled):
            stamped: list[str] = []
            unstamped: list[str] = []
            chains: list[str] = []
            for revision in ordered_revisions(self.modelo):
                if all(casilla.id != casilla_id for casilla in revision.casillas):
                    continue
                chain = self.state.ids.get((revision.id, casilla_id))
                if chain is None:
                    unstamped.append(revision.id)
                    continue
                stamped.append(revision.id)
                if chain not in chains:
                    chains.append(chain)
            records.append(
                PartialStamping(
                    modelo=self.modelo_id,
                    casilla=casilla_id,
                    chain=" + ".join(chains),
                    stamped=tuple(stamped),
                    unstamped=tuple(unstamped),
                )
            )
        return tuple(records)

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
        pairs = judged_pairs(self.modelo, ordered_revisions(self.modelo))
        for previous, successor in pairs:
            self._pair(previous, successor)
        missing = set(self.rulings) - {(p.id, s.id) for p, s in pairs}
        if missing:
            raise ValueError(f"modelo {self.modelo_id}: rulings name boundaries that do not exist: {sorted(missing)}")
        return self.plan

    def _pair(self, previous: ModeloRevision, successor: ModeloRevision) -> None:
        pair = (previous.id, successor.id)
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
            if self._already_disposed(casilla):
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
                f"box [{box}] is printed on more than one line of {succ_design.relative_path}; page is unqualified: "
                f"{succ_design.unlocalised_reason(box)}",
            )
            return
        if box in prev_design.boxes:
            prev_line = prev_design.defining_line(box)
            if prev_line is None:
                self.plan.refuse(
                    successor.id,
                    casilla.id,
                    LineageRefusalCategory.ABSENCE_UNCLASSIFIED,
                    f"box [{box}] is printed on more than one line of {prev_design.relative_path}; page is "
                    f"unqualified: {prev_design.unlocalised_reason(box)}",
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
            if self._already_disposed(succ_row):
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
                succ_row = require(succ_rows, right, "successor")
                handled.add(right)
                if self._already_disposed(succ_row):
                    continue
                self.plan.refuse(successor.id, right, category, reason, predecessor=left or None)
        for casilla_id, casilla in succ_rows.items():
            if casilla_id in handled:
                continue
            # A stem rule speaks for occurrences the predecessor does not carry by identifier; an
            # occurrence it does carry is judged as a bare chain like any other row.
            stem = None if casilla_id in prev_rows else stem_of(casilla_id)
            if stem is not None and stem in ruling.held_stems:
                handled.add(casilla_id)
                if self._already_disposed(casilla):
                    continue
                self.plan.refuse(successor.id, casilla_id, LineageRefusalCategory.HELD, ruling.held_reason)
            elif casilla_id in ruling.new_on_form or (stem is not None and stem in ruling.new_on_form_stems):
                handled.add(casilla_id)
                if self._already_disposed(casilla):
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
                if self._already_disposed(casilla):
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
    """Normalise evidence whitespace, refusing only what the casilla row model itself would refuse.

    The bound is the schema's, read from the model. A shorter house style is
    not a reason to lose a checkable citation: evidence longer than
    ``_EVIDENCE_ADVISORY`` but within the schema cap is written and reported,
    and only evidence the schema would reject stops the run.
    """
    text = " ".join(evidence.split())
    if len(text) > SCHEMA_EVIDENCE_LIMIT:
        raise ValueError(f"evidence exceeds the schema's {SCHEMA_EVIDENCE_LIMIT}-character cap: {text[:120]!r}")
    return text


def _with_rationale(locus: str, rationale: str) -> str:
    """Append the ruling's rationale when it fits the advisory length; the checkable locus is never cut.

    Composition, not the bound: the rationale is repeated prose and the locus
    is the part a reader checks, so the rationale is dropped rather than
    pushing routine evidence past the advisory length.
    """
    combined = f"{locus}. {rationale}"
    return combined if len(" ".join(combined.split())) <= _EVIDENCE_ADVISORY else f"{locus}."


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
    if box is not None and (found := design.defining_lines(box)) is not None:
        line = found[0]
        span = design.component_span(box)
        over = "" if span is None else f" over {len(found)} printed components @{span.offset}+{span.length}"
        return f"{_cite(design, line)} box [{box}]{over} ({design.snippet(line)})"
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
    localised = None if box is None else prev_design.defining_lines(box)
    if localised is not None:
        line = localised[0]
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
        unresolved = sorted(stated - design.boxes, key=_box_order)
        if unresolved:
            return (
                f"{design.relative_path} does not print {len(unresolved)} box(es) edition {revision.id} declares "
                f"(e.g. {unresolved[:4]}), so its inventory cannot be trusted"
            )
    if isinstance(prev_design, str) or isinstance(succ_design, str):
        return "the record design pair cannot be read"
    if prev_design.relative_path == succ_design.relative_path:
        return None
    retired = sorted(prev_design.boxes - succ_design.boxes, key=_box_order)
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
        casilla_id = next(((m.group(1) or m.group(2)) for entry in block if (m := _ID_LINE.match(entry))), None)
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


# --------------------------------------------------------------------------- corpus loading


@dataclass(frozen=True, slots=True)
class ModeloLoadFailure:
    """A modelo that could not be compiled at all, and the first message its loader raised.

    Recorded at modelo level because a modelo that does not load has no rows to
    record: its editions are never materialised, so its casillas cannot be
    enumerated and none of them can be named. The record is therefore not a
    per-row refusal, and :func:`render_ledger` keeps it out of the ``[[refusal]]``
    array the lineage totality gate reads.
    """

    modelo: str
    reason: str


def load_corpus(
    sources: Iterable[ModeloSource],
) -> tuple[dict[str, ModeloDefinition], tuple[ModeloLoadFailure, ...]]:
    """Compile each modelo on its own, so one that cannot load stops only itself.

    The whole-corpus authority refuses the entire corpus when any single modelo
    fails, which would stop seeding all fifty-eight modelos for a defect in one
    -- including a modelo this seeder is excluded from writing and never reads
    a chain from. Loading per directory keeps the blast radius at the modelo:
    the one that fails is returned as a :class:`ModeloLoadFailure` and every
    other modelo is planned exactly as before.

    Only :class:`RegistryLoadError` is caught. It is the loader's own boundary
    type: a malformed manifest, an unreadable fragment, a schema violation and
    an ambiguous delta-edition merge all arrive as one. Anything else is a
    defect in this tooling and must not be recorded as a data failure.
    """
    loaded: dict[str, ModeloDefinition] = {}
    failures: list[ModeloLoadFailure] = []
    for source in sources:
        try:
            loaded[source.modelo_id] = load_modelo_directory(source.path)
        except RegistryLoadError as error:
            failures.append(ModeloLoadFailure(source.modelo_id, _recorded_reason(str(error))))
    return loaded, tuple(failures)


def _recorded_reason(message: str) -> str:
    """The first line of a loader message, made fit to commit in the ledger.

    The loader names the directory it refused by resolved absolute path, which
    would put one machine's checkout location into a shared artifact and make
    the ledger differ per machine. The repository prefix is dropped and the
    remaining separators are written the one way, so two checkouts of the same
    tree record the same reason. The result is bounded like any other recorded
    reason.
    """
    text = next((line.strip() for line in message.splitlines() if line.strip()), "")
    root = str(_REPO_ROOT.resolve())
    for prefix in (f"{root}\\", f"{root}/", root):
        text = text.replace(prefix, "")
    text = text.replace("\\", "/")
    return text if len(text) <= _RECORDED_REASON_LIMIT else text[: _RECORDED_REASON_LIMIT - 3] + "..."


# --------------------------------------------------------------------------- driver


@dataclass(frozen=True, slots=True)
class PartialStamping:
    """An identifier the corpus stamps on some editions of a modelo and not on others.

    Recorded at modelo level for the same reason a load failure is: the modelo
    is skipped whole, so none of its rows is dispositioned and none can be
    named. :func:`render_ledger` keeps it out of the ``[[refusal]]`` array the
    lineage totality gate reads.

    The state is a half-finished stamping pass, whoever is or is not conducting
    it: the stamped editions carry ``chain``, and each edition in ``unstamped``
    carries neither it nor a recorded absence excusing its start. The registry
    refuses that identifier, so this seeder writes nothing into the modelo until
    the pass finishes.
    """

    modelo: str
    casilla: str
    chain: str
    stamped: tuple[str, ...]
    unstamped: tuple[str, ...]

    def describe(self) -> str:
        """One line naming the chain and the editions, for the ledger and the run's output."""
        chain = self.chain or "(no chain id)"
        return (
            f"chain {chain} on {self.casilla}: stamped in {', '.join(self.stamped)}; "
            f"unstamped in {', '.join(self.unstamped)}"
        )


def _partial_stamping_error(modelo_id: str, records: tuple[PartialStamping, ...]) -> RegistryError:
    """Build the registered registry refusal carrying the structured records."""
    return RegistryError(
        f"modelo {modelo_id}: identifiers stay partly stamped: {[record.casilla for record in records][:5]}",
        context={"modelo_id": modelo_id, "partial_stamping_records": records},
    )


def plan_modelo(
    modelo_id: str,
    modelo: ModeloDefinition,
    oracle: DesignOracle,
    rulings: Mapping[str, list[Ruling]],
) -> LineagePlan:
    """Plan every lineage disposition for one modelo.

    Planning repeats until no identifier would be left partly stamped: each pass
    forbids chains on the identifiers the previous pass could not settle. An
    identifier still partly stamped once its chains are forbidden is the
    corpus's own half-finished state, not this plan's doing, and raises
    :class:`RegistryError` rather than being seeded on weaker evidence.
    """
    forbidden: frozenset[str] = frozenset[str]()
    while True:
        planner = _ModeloPlanner(modelo_id, modelo, oracle, rulings.get(modelo_id, []), forbidden)
        plan = planner.run()
        unsettled = planner.settle_partial_stamps()
        if not unsettled:
            return plan
        if unsettled <= forbidden:
            raise _partial_stamping_error(modelo_id, planner.partial_stamp_records(unsettled))
        forbidden |= unsettled


def plan_corpus(
    modelo_ids: Iterable[str],
    loaded: Mapping[str, ModeloDefinition],
    oracle: DesignOracle,
    rulings: Mapping[str, list[Ruling]],
) -> tuple[list[LineagePlan], tuple[PartialStamping, ...]]:
    """Plan each modelo on its own, so one left partly stamped stops only itself.

    Mirrors :func:`load_corpus` at the next stage: the blast radius of a defect
    stays at the modelo that carries it. Only :class:`RegistryError` is
    caught -- it is this planner's own boundary type for a corpus state it
    refuses to write into. Anything else is a defect in this tooling and must
    not be recorded as a data state.
    """
    plans: list[LineagePlan] = []
    partial: list[PartialStamping] = []
    for modelo_id in modelo_ids:
        try:
            plans.append(plan_modelo(modelo_id, loaded[modelo_id], oracle, rulings))
        except RegistryError as error:
            context = error.context
            if context is None:
                raise
            records = context.get("partial_stamping_records", ())
            if not isinstance(records, tuple) or not all(isinstance(record, PartialStamping) for record in records):
                raise
            partial.extend(records)
    return plans, tuple(partial)


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


@dataclass(frozen=True, slots=True)
class CarriedRefusal:
    """A previous run's refusal, carried forward because its modelo could not be rejudged.

    Carried verbatim: the row it names and the category and reason it stopped
    are the previous run's words, not a fresh judgement. ``carried_reason`` says
    why this run could not rejudge it. ``last_judged`` is the identifier of the
    run that did judge it, propagated unchanged across repeated carries, and
    ``carried_runs`` counts the consecutive runs that have carried it since.
    Those two are what make staleness visible rather than implied: an entry
    judged in this morning's run and one carried twenty times since a run weeks
    ago read differently in the ledger.
    """

    modelo: str
    revision: str
    casilla: str
    category: str
    reason: str
    predecessor: str | None
    carried_reason: str
    last_judged: str
    carried_runs: int

    @property
    def key(self) -> tuple[str, str, str]:
        """The row this entry names, in the ledger's own key order."""
        return (self.modelo, self.revision, self.casilla)


@dataclass(frozen=True, slots=True)
class PreviousLedger:
    """The ledger as the previous run left it: when it judged, and what it refused per modelo."""

    judged_at: str
    refusals: Mapping[str, tuple[Mapping[str, object], ...]]


def run_identifier(moment: datetime | None = None) -> str:
    """The identifier a run stamps on what it judges: a UTC instant, to the second."""
    return (moment or datetime.now(UTC)).astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_previous_ledger(path: Path = LEDGER_PATH) -> PreviousLedger:
    """Read the committed ledger, so a modelo this run cannot rejudge keeps its entries.

    A missing ledger is a first run and carries nothing. Refusals are kept as
    their raw tables rather than parsed into :class:`Refusal`, because carrying
    forward must be verbatim: whatever the previous run wrote is the previous
    run's judgement, and reshaping it here would quietly restate it.
    """
    if not path.is_file():
        return PreviousLedger(judged_at="", refusals={})
    document = tomllib.loads(path.read_text(encoding=_UTF_8))
    run = document.get("run")
    judged_at = run.get("judged_at", "") if isinstance(run, Mapping) else ""
    by_modelo: dict[str, list[Mapping[str, object]]] = collections.defaultdict(list)
    for entry in document.get("refusal", ()):
        modelo = entry.get("modelo")
        if isinstance(modelo, str):
            by_modelo[modelo].append(entry)
    return PreviousLedger(
        judged_at=str(judged_at),
        refusals={modelo: tuple(entries) for modelo, entries in by_modelo.items()},
    )


def carried_refusals(previous: PreviousLedger, skipped: Mapping[str, str]) -> tuple[CarriedRefusal, ...]:
    """Carry every previous refusal of a skipped modelo forward, dated by its last real judgement.

    ``skipped`` maps each modelo this run could neither load nor plan to the
    reason it was skipped. An entry the previous run itself carried keeps its
    original ``last_judged`` and increments its carry count; an entry the
    previous run judged takes that run's identifier. A previous ledger naming no
    run cannot date what it judged, so its entries carry the only honest value
    available -- ``unknown`` -- rather than being backdated to a run that never
    judged them.
    """
    carried: list[CarriedRefusal] = []
    for modelo in sorted(skipped):
        for entry in previous.refusals.get(modelo, ()):
            was_carried = entry.get("carried_from_previous_run") is True
            last_judged = entry.get("last_judged") if was_carried else previous.judged_at
            runs = entry.get("carried_runs", 0) if was_carried else 0
            predecessor = entry.get("predecessor")
            carried.append(
                CarriedRefusal(
                    modelo=modelo,
                    revision=str(entry["revision"]),
                    casilla=str(entry["casilla"]),
                    category=str(entry["category"]),
                    reason=str(entry["reason"]),
                    predecessor=None if predecessor is None else str(predecessor),
                    carried_reason=skipped[modelo],
                    last_judged=str(last_judged) if isinstance(last_judged, str) and last_judged else "unknown",
                    carried_runs=(runs if isinstance(runs, int) and not isinstance(runs, bool) else 0) + 1,
                )
            )
    return tuple(carried)


def partition_contradictions(
    checks: Mapping[str, list[str]],
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Split contradictions into the ones that refuse the write and the ones recorded instead.

    An excluded modelo is adjudicated by hand outside this tool: its plan comes
    from :func:`residual_plan` and proposes no edit, so a contradiction found in
    it survives every run the seeder will ever make. Refusing the whole corpus
    on its behalf deadlocks every other modelo against a repair this run is not
    the one to make, and the ledger is whole-corpus or nothing, so the deadlock
    is total rather than partial.

    Returning it separately is not forgiving it. The second mapping is rendered
    into the ledger as ``[[excluded_contradiction]]`` with every offending row
    named, and the first still refuses the write outright, so a modelo this run
    seeds gains nothing from this split.
    """
    blocking: dict[str, list[str]] = {}
    excluded: dict[str, list[str]] = {}
    for modelo_id, problems in checks.items():
        if not problems:
            continue
        target = excluded if modelo_id in EXCLUDED_MODELOS else blocking
        target[modelo_id] = problems
    return blocking, excluded


def render_ledger(
    plans: list[LineagePlan],
    checks: Mapping[str, list[str]],
    load_failures: Iterable[ModeloLoadFailure],
    partial_stampings: Iterable[PartialStamping],
    *,
    excluded_contradictions: Mapping[str, list[str]] | None = None,
    carried: Iterable[CarriedRefusal] = (),
    judged_at: str = "",
) -> str:
    """Render the ledger: one refusal per unresolved row, plus the run's modelo-level records.

    A load failure is rendered as its own ``[[load_failed]]`` entry, and a
    modelo skipped for a partly stamped identifier as its own
    ``[[stamping_in_progress]]`` entry. Both are modelo-level because a modelo
    skipped whole dispositions no row and so can name none: neither record
    invents a row key, and neither is read by the lineage totality gate.

    An ``[[excluded_contradiction]]`` records a contradiction found in an
    excluded modelo's residual plan, naming every offending row. It is
    modelo-level for a different reason: the rows it names exist and are real,
    but they are a hand adjudication's to resolve and not this run's, so the
    entry must not be read as covering them. The gate keeps its teeth where
    they matter -- a contradiction in a modelo this run seeds still refuses the
    write outright -- and stops holding the other modelos hostage to a repair
    it is structurally unable to make.

    Skipping a modelo does not drop its rows. It means this run did not rejudge
    them, not that they stopped needing an entry, so every ``[[refusal]]`` the
    previous run wrote for a skipped modelo is carried forward verbatim as a
    ``[[refusal]]`` again, marked ``carried_from_previous_run``, naming in
    ``carried_reason`` why it could not be rejudged and in ``last_judged`` the
    identifier of the run that did judge it. The ledger therefore stays the
    closed list over the whole corpus whatever fails, and nothing is quietly
    covered either: a carried entry states in the ledger that it asserts
    something about an older corpus state, and ``carried_runs`` says how long it
    has been asserting it.

    That is what keeps the gate honest once it stops compiling the whole corpus
    at once. A gate partitioned by modelo judges only the modelos it could load,
    reports the rest as ``unjudged``, and is never green while that list is
    non-empty. It withholds a carried entry from both the uncovered and the
    stale side rather than reading a record of an older judgement as a claim
    about a corpus it never saw. When the modelo loads again it is judged again,
    its carried entries with it, and any that no longer fit are reported stale
    until the seeder runs and replaces them with fresh ones.

    ``judged_at`` identifies this run and dates every entry not marked carried.
    """
    out = [
        "# Casilla lineage ledger, written by casilla_lineage_seed.py --apply. Do not edit by hand.",
        "#",
        "# Every successor row that neither carries lineage nor declares its kind of none is listed",
        "# here, one refusal per row, with the category and reason it stopped. That includes every",
        "# such row of an excluded modelo, whether examined or not. The list is closed: a row missing",
        "# from it, or an entry whose row no longer needs it, fails the lineage totality gate.",
        "#",
        "# [run].judged_at identifies the run that wrote this file. Every [[refusal]] that does not",
        "# say otherwise was judged in that run, against the corpus as it then stood.",
        "#",
        "# A [[load_failed]] modelo is recorded at modelo level and names no row, because a modelo",
        "# that does not compile has no rows to name. It is deliberately not a [[refusal]]: the",
        "# totality gate reads rows, and a modelo-level entry must neither cover one nor go stale.",
        "# Nothing is lost by that, because skipping a modelo never shrinks this list: each previous",
        "# [[refusal]] of a skipped modelo is carried forward verbatim with carried_from_previous_run",
        "# = true, the carried_reason it could not be rejudged, the last_judged run that did judge it,",
        "# and carried_runs counting the carries since. The gate is partitioned by modelo: it judges",
        "# only what it could load, reports the rest as unjudged, and is never green while one is",
        "# listed here. An entry whose carried_runs keeps climbing is a repair nobody finished.",
        "#",
        "# A [[stamping_in_progress]] modelo was skipped whole because the corpus stamps one of its",
        "# casilla identifiers on some editions and neither stamps nor excuses it on the others. It is",
        "# modelo-level and not a [[refusal]] for the same reason, and it closes no hole either. The",
        "# closing is not this seeder's: the registry's own partial-stamping gate already pins half-",
        "# stamped chains at zero and calls them a defect rather than a backlog, and it scans the",
        "# authored corpus, so it is red for exactly as long as an entry stands here. This record",
        "# keeps one modelo's half-finished pass from stopping the other fifty-seven; it does not",
        "# make the half-finished pass tolerable, and no entry here is ever a resting state.",
        "#",
        "# An [[excluded_contradiction]] names a contradiction this run found in an EXCLUDED modelo,",
        "# with every offending row spelled out. An excluded modelo is adjudicated by hand outside",
        "# this tool, so its plan proposes no edit and the seeder cannot resolve the contradiction",
        "# however often it runs; refusing the whole corpus on its behalf would deadlock every other",
        "# modelo against a repair this run is not the one to make. Recording it here is not",
        "# tolerating it. The contradiction is a live defect in the authored corpus, it is named so a",
        "# hand adjudication can find it, and the same contradiction in a modelo this run DOES seed",
        "# still refuses the write outright.",
        "",
    ]
    if judged_at:
        out += ["[run]", f"judged_at = {json.dumps(judged_at)}", ""]
    for modelo_id, excluded in sorted(EXCLUDED_MODELOS.items()):
        out += ["[[excluded]]", f"modelo = {json.dumps(modelo_id)}", f"reason = {json.dumps(excluded.reason)}", ""]
    for failure in sorted(load_failures, key=lambda entry: entry.modelo):
        out += [
            "[[load_failed]]",
            f"modelo = {json.dumps(failure.modelo)}",
            f"reason = {json.dumps(failure.reason, ensure_ascii=False)}",
            "",
        ]
    for record in sorted(partial_stampings, key=lambda entry: (entry.modelo, entry.casilla)):
        out += [
            "[[stamping_in_progress]]",
            f"modelo = {json.dumps(record.modelo)}",
            f"casilla = {json.dumps(record.casilla, ensure_ascii=False)}",
            f"chain = {json.dumps(record.chain, ensure_ascii=False)}",
            f"stamped = {json.dumps(list(record.stamped), ensure_ascii=False)}",
            f"unstamped = {json.dumps(list(record.unstamped), ensure_ascii=False)}",
            "",
        ]
    for modelo_id, problems in sorted((excluded_contradictions or {}).items()):
        out += [
            "[[excluded_contradiction]]",
            f"modelo = {json.dumps(modelo_id)}",
            "contradictions = [",
            *(f"  {json.dumps(problem, ensure_ascii=False)}," for problem in problems),
            "]",
            "",
        ]
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
    judged: set[tuple[str, str, str]] = set()
    for plan in plans:
        for refusal in plan.refusals:
            judged.add((refusal.modelo, refusal.revision, refusal.casilla_id))
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
    for entry in sorted(carried, key=lambda record: record.key):
        # A modelo is either judged this run or carried, never both, so a collision is this
        # tooling contradicting itself rather than a data state, and the reader would refuse
        # the doubly-named row anyway. Fail here, where the cause is still visible.
        if entry.key in judged:
            raise ValueError(f"carried refusal {entry.key} is also judged in this run")
        out += [
            "[[refusal]]",
            f"modelo = {json.dumps(entry.modelo)}",
            f"revision = {json.dumps(entry.revision)}",
            f"casilla = {json.dumps(entry.casilla, ensure_ascii=False)}",
        ]
        if entry.predecessor is not None:
            out.append(f"predecessor = {json.dumps(entry.predecessor, ensure_ascii=False)}")
        out += [
            f"category = {json.dumps(entry.category)}",
            f"reason = {json.dumps(entry.reason, ensure_ascii=False)}",
            "carried_from_previous_run = true",
            f"carried_reason = {json.dumps(entry.carried_reason, ensure_ascii=False)}",
            f"last_judged = {json.dumps(entry.last_judged)}",
            f"carried_runs = {entry.carried_runs}",
            "",
        ]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--apply", action="store_true", help="write the planned keys and the ledger")
    parser.add_argument("--modelo", action="append", help="limit to these modelos (repeatable)")
    args = parser.parse_args(argv)

    loaded, load_failures = load_corpus(discover_modelo_sources(_MODELOS_ROOT))
    oracle = DesignOracle(load_shared_catalogues(_REGISTRY_ROOT).sources)
    rulings = load_rulings()
    modelo_ids = sorted(loaded)
    selected = [
        modelo_id
        for modelo_id in modelo_ids
        if modelo_id not in EXCLUDED_MODELOS
        and len(loaded[modelo_id].revisions) > 1
        and (not args.modelo or modelo_id in args.modelo)
    ]
    failed = {failure.modelo for failure in load_failures}
    unknown = set(rulings) - set(selected) - set(EXCLUDED_MODELOS) - failed
    if unknown and not args.modelo:
        raise SystemExit(f"rulings name modelos outside scope: {sorted(unknown)}")
    plans, partial_stampings = plan_corpus(selected, loaded, oracle, rulings)
    plans += [
        residual_plan(modelo_id, loaded[modelo_id], rulings.get(modelo_id, ()))
        for modelo_id in modelo_ids
        if modelo_id in EXCLUDED_MODELOS and (not args.modelo or modelo_id in args.modelo)
    ]
    plans.sort(key=lambda plan: plan.modelo)
    checks = {
        plan.modelo: [
            *contradictions(loaded[plan.modelo], plan),
            *(f"gate: {failure}" for failure in gate_regressions(loaded[plan.modelo], plan)),
        ]
        for plan in plans
    }

    for failure in sorted(load_failures, key=lambda entry: entry.modelo):
        print(f"{failure.modelo}: load_failed; {failure.reason}")
    for record in sorted(partial_stampings, key=lambda entry: (entry.modelo, entry.casilla)):
        print(f"{record.modelo}: stamping_in_progress; {record.describe()}")
    totals: collections.Counter[str] = collections.Counter()
    for plan in plans:
        totals.update(plan.counts)
        shown = ", ".join(f"{key}={value}" for key, value in sorted(plan.counts.items()))
        print(f"{plan.modelo}: {shown}; contradictions={len(checks[plan.modelo])}")
        for problem in checks[plan.modelo][:5]:
            print(f"    CONTRADICTION {problem}")
    print("total:", ", ".join(f"{key}={value}" for key, value in sorted(totals.items())))
    long_evidence = [entry for plan in plans for entry in plan.long_evidence]
    if long_evidence:
        longest = max(long_evidence, key=lambda entry: entry.length)
        print(
            f"warning: {len(long_evidence)} evidence string(s) longer than {_EVIDENCE_ADVISORY} characters, within "
            f"the schema cap of {SCHEMA_EVIDENCE_LIMIT}; longest {longest.length} at "
            f"{longest.modelo} {longest.revision}/{longest.casilla}"
        )
    # Repeated after the per-modelo lines: a skip scrolls past among fifty-eight of them, and a
    # reader must not have to open the ledger to learn that a modelo was left unseeded.
    if partial_stampings:
        skipped = sorted({record.modelo for record in partial_stampings})
        print(f"skipped {len(skipped)} modelo(s) for partly stamped chains: {', '.join(skipped)}")
        for record in sorted(partial_stampings, key=lambda entry: (entry.modelo, entry.casilla)):
            print(f"    SKIPPED {record.modelo} {record.describe()}")
    skipped = {
        **{failure.modelo: f"modelo could not be compiled this run: {failure.reason}" for failure in load_failures},
        **{
            record.modelo: f"modelo was skipped this run for a partly stamped identifier: {record.describe()}"
            for record in partial_stampings
        },
    }
    carried = carried_refusals(load_previous_ledger(), skipped)
    if carried:
        by_modelo = collections.Counter(entry.modelo for entry in carried)
        print(f"carried {len(carried)} previous refusal(s) forward for {len(by_modelo)} unjudged modelo(s):")
        for modelo_id, count in sorted(by_modelo.items()):
            oldest = min(entry.last_judged for entry in carried if entry.modelo == modelo_id)
            runs = max(entry.carried_runs for entry in carried if entry.modelo == modelo_id)
            print(f"    CARRIED {modelo_id} {count} row(s), last judged {oldest}, carried {runs} run(s)")
    for modelo_id in sorted(skipped):
        if modelo_id not in {entry.modelo for entry in carried}:
            print(f"    CARRIED {modelo_id} no previous refusal to carry; the ledger names none of its rows")
    blocking, excluded_contradictions = partition_contradictions(checks)
    for modelo_id, problems in sorted(excluded_contradictions.items()):
        print(f"{modelo_id}: excluded_contradiction; {len(problems)} contradiction(s) left to hand adjudication")
        for problem in problems:
            print(f"    EXCLUDED_CONTRADICTION {problem}")
    if any(blocking.values()):
        print("refusing to write: the plan contains contradictions", file=sys.stderr)
        return 1
    if args.apply:
        edited = sum(apply_plan(plan) for plan in plans)
        if not args.modelo:
            LEDGER_PATH.write_text(
                render_ledger(
                    plans,
                    checks,
                    load_failures,
                    partial_stampings,
                    excluded_contradictions=excluded_contradictions,
                    carried=carried,
                    judged_at=run_identifier(),
                )
                + "\n",
                encoding=_UTF_8,
                newline="\n",
            )
        print(f"edited {edited} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
