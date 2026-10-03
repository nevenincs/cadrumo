"""Parse and ground casilla lineage evidence in pinned official record designs."""

from __future__ import annotations

import collections
import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path

from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_references import SourceReference
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition

from .casilla_lineage_seed_paths import _DATA_ROOT, _UTF_8
from .casilla_lineage_seed_types import _EVIDENCE_ADVISORY

_PLAIN_INTEGER = re.compile(r"^\d+$")

_NON_NUMERIC_BOX = r"\d{1,5}bis|\d{1,5}\.[a-z]|[A-Z]\d{1,2}[A-Z]?"

_PRINTED_BOX = re.compile(rf"^(?:{_NON_NUMERIC_BOX})$")

_DESIGN_BOX = re.compile(rf"\[\s*({_NON_NUMERIC_BOX}|\d{{1,5}})\s*\]")

_ALPHANUMERIC = re.compile(r"\w")

_LIST_SEPARATOR = re.compile(r"^\s*(?:,|y|e|o|a)\s*$", re.IGNORECASE)

_OPERATOR_GAP = re.compile(r"^\s*[-+x*/=]\s*$")

_BYTE_POSITIONS = re.compile(r"^\d+(?:\s*-\s*\d+)?$")

_RECORD_HEADING = re.compile(r"^#+\s+(\S.*)$")

_SNIPPET = 70


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
        unplaced = _unplaced_lines(found, placed)
        if unplaced:
            return f"lines {list(found)} print it and {unplaced} record no byte position, so no span can be checked"
        spans = [placement for placement in placed if placement is not None]
        return _unlocalised_span_reason(found, spans)

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
    depths = _parenthesis_depths(cell, matches)
    if _contains_list_separator(cell, matches, depths):
        return None
    if len(matches) > 1 and _OPERATOR_GAP.match(cell[matches[-2].end() : matches[-1].start()]):
        return None
    return _box_key(matches[-1].group(1))


def _parenthesis_depths(cell: str, matches: list[re.Match[str]]) -> list[int]:
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
    return depths


def _contains_list_separator(cell: str, matches: list[re.Match[str]], depths: list[int]) -> bool:
    for index in range(1, len(matches)):
        gap = cell[matches[index - 1].end() : matches[index].start()]
        if depths[index - 1] == 0 and depths[index] == 0 and _LIST_SEPARATOR.match(gap):
            return True
    return False


def _unplaced_lines(found: tuple[int, ...], placed: list[DesignPlacement | None]) -> list[int]:
    return [line for line, placement in zip(found, placed, strict=True) if placement is None]


def _unlocalised_span_reason(found: tuple[int, ...], spans: list[DesignPlacement]) -> str:
    records = sorted({placement.record for placement in spans})
    if len(records) > 1:
        return f"lines {list(found)} print it in different records {records}, so they are not one field"
    printed = [f"@{placement.offset}+{placement.length}" for placement in sorted(spans, key=lambda p: p.offset)]
    return f"lines {list(found)} print it at {printed}, which do not tile one contiguous field"


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
        """Bind source declarations and initialise the per-path inventory cache."""
        self._sources = sources
        self._cache: dict[str, DesignInventory | str] = {}

    def for_revision(self, revision: ModeloRevision) -> DesignInventory | str:
        """The revision's design inventory, or the reason none can be trusted."""
        paths = _applicable_design_paths(revision, _revision_designs(self._sources, revision))
        if len(paths) != 1:
            return _design_count_error(revision, paths)
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


def _revision_designs(sources: Mapping[str, SourceReference], revision: ModeloRevision) -> list[SourceReference]:
    refs = set(revision.source_refs)
    for casilla in revision.casillas:
        refs.update(casilla.source_refs)
    return [
        source
        for ref in sorted(refs)
        if (source := sources.get(ref)) is not None and str(source.kind) == "record_design"
    ]


def _applicable_design_paths(revision: ModeloRevision, designs: list[SourceReference]) -> dict[str, SourceReference]:
    paths = {source.corpus_path: source for source in designs}
    if len(paths) <= 1:
        return paths
    return {
        path: source
        for path, source in paths.items()
        if source.applies_from is not None
        and source.applies_from <= revision.valid_from
        and (source.applies_to is None or revision.valid_from <= source.applies_to)
    }


def _design_count_error(revision: ModeloRevision, paths: Mapping[str, SourceReference]) -> str:
    return f"revision {revision.id} names {len(paths)} applicable record designs, not exactly one"


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
