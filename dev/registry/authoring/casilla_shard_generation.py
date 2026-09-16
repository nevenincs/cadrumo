"""Emit casilla shards for one revision from its own record design.

A casilla row is geometry plus two adjudicated attributes. The geometry --
offset, length, type, caption, box number -- is a transcription of what AEAT
published, and transcribing it by hand is how this corpus acquired every
positional defect it has had: a reason field over its cap, a predecessor written
as a string, an id whose position range was copied from the edition before it.
The attributes are judgement, and judgement is what an author is for.

So this module emits the geometry and refuses the judgement. Attributes are
carried forward from an already-authored edition, matched by box number; a row
with no match and no declared rule is refused rather than guessed, and the
refusal list IS the adjudication list.

The design is read through :func:`extract_record_design`, which returns the
workbook's cells intact. The markdown and JSON sidecars beside the binary are a
rendering: they join cells with a pipe, so a caption containing a pipe splits
across columns, and a caption containing a newline splits across lines carrying
its box number with it. Reading the rendering costs box numbers silently -- on
one 220-sized design, sixty-two of them. The sidecar is retained here only as a
cross-check, where a disagreement with the workbook is a refusal.

THE DEFECT THIS EXISTS TO CATCH. Some casilla ids ARE their position range,
because AEAT printed no box number for the slot. When a record grows in its
middle, every later slot moves, and an id copied from the previous edition then
names a position its own row does not occupy. It validates, it serialises, and
it is wrong by exactly the number of bytes the record grew. Modelo 220's 2025
liquidacion (I) grew seventy-one bytes inside its tramo run, and three of its
four carried ids were arithmetically wrong the moment they were copied.

THE DEFECT MATCHING ALONE DOES NOT CATCH. A row whose position held but whose
meaning was rewritten matches by number and carries its old attributes without
a murmur. That is not hypothetical either: the same 220 record kept a slot at
offset 786 while its caption changed from a generic tramo to a
cooperatives-specific one. Caption drift is therefore reported separately, with
the devengo year and page cross-references folded out first, because those move
every edition and are not meaning changes.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from cadrumo.core.toml import TomlDecodeError, parse_toml
from dev.registry.compiler.record_design_schema import (
    RecordDesignField,
    RecordDesignSheet,
)

from ..compiler.record_design import extract_record_design

__all__ = [
    "GenerationRefusedError",
    "GenerationReport",
    "RecordOutcome",
    "WaveSpec",
    "derive_number",
    "emit_records",
    "generate",
    "is_structural",
    "normalise_for_drift",
    "read_design",
]


class GenerationRefusedError(Exception):
    """The design, the prior edition or the emission did not hold up."""


#: Envelope, filler and terminator captions. A row matching one of these is not
#: a casilla: it is the modelo/pagina identifier, the reservado run AEAT fills
#: with blanks, or the end-of-record marker. The classification is asserted
#: against the design's own declared total rather than trusted, so a filler
#: shape this pattern does not know about cannot quietly become a casilla.
_STRUCTURAL = re.compile(
    r"^(inicio del identificador|fin de identificador|fin de registro|reservado"
    r"|modelo\.?$|modelo declaraci|blancos\.?$|tipo de registro\.?$"
    r"|p[aeiouáéíóú]*gina\.?$|letra$|hoja$"
    r"|indicador de p[aeiouáéíóú]*gina complementaria"
    r"|n[uú]mero de orden de la p[aeiouáéíóú]*gina"
    r" complementaria|constante)",
    re.IGNORECASE,
)
#: AEAT box numbers are not uniformly five digits. Page-one caracteres print
#: three, one family prints four, and Modelo 220 prints ``[000304]`` with an
#: extra leading zero that the corpus transcribes verbatim. A five-digit filter
#: drops real boxes and mangles that one.
_NUMBERED = re.compile(r"\[([0-9]{3,6})\]")
#: The documento de ingreso o devolucion labels its importe boxes with a bare
#: letter where every other record prints a number. The letter IS the number.
_LETTERED = re.compile(r"\[([A-Z])\]\s*$")
#: Any bracket token that LOOKS like an identifier: short, no spaces, and no
#: enumeration punctuation. A token with a space in it is prose AEAT bracketed,
#: such as ``[elemento cubierto]``; one carrying ``|``, ``<`` or ``>`` is a
#: Contenido enumeration such as ``(*)[A|E|I|0]`` or ``[<blanco>,D,R,X]``.
#:
#: A row carrying one of these that the number grammar does not recognise is
#: refused rather than falling through to a positional id. Modelo 036 numbers its
#: casillas ``[A1]``, ``[B26]``, ``[C71]``, ``[716.a]``, ``[4774bis]``,
#: ``[300,301,302]`` and ``[65]``, and under the record-oriented grammar every
#: one of those silently became a position range -- a real box number replaced by
#: a fabricated slot id, with nothing to show it happened.
_IDENTIFIER_BRACKET = re.compile(r"\[([^\]\s|<>]{1,12})\]")
_TYPE_CODES = frozenset(
    {
        "num",
        "n",
        "an",
        "a",
        "numérico",
        "alfanumérico",
        "alfabético",
        "blancos",
        "numerico",
        "alfanumerico",
        "alfabetico",
    }
)
#: Characters whose appearance means the extraction changed shape under us. A
#: non-breaking space reads as a space and matches nothing, which is how a
#: citation screen once reported twenty-three absent quotations that were all
#: present.
_FORBIDDEN = {"\N{NO-BREAK SPACE}": "NBSP", "\t": "TAB", "\r": "CR"}
_YEAR = re.compile(r"20\d\d")
_PAGE_POINTER = re.compile(r"\(?p[aeiouáéíóú]*g\.?\s*[^)]*\)?", re.IGNORECASE)
_BRACKET_TOKEN = re.compile(r"\[[0-9a-z]+\]", re.IGNORECASE)
_NON_ALNUM = re.compile(r"[^a-z0-9]+")
#: The ``# @off+len Type.`` head of a transcribed comment. The type is matched as
#: one whitespace-delimited token rather than an enumeration: designs print it as
#: ``N``, ``Num``, ``An`` on the record-oriented modelos and as ``Numérico``,
#: ``Alfanumérico``, ``Alfabético``, ``Blancos`` elsewhere. An enumeration that
#: listed only the short forms stripped ``num`` off ``Numérico`` and left
#: ``érico`` inside the folded caption, where it compared as real content.
#:
#: The type token is optional because earlier hand-authored fragments are not
#: consistent about it: modelo 220's 2024 edition writes ``# @475+17. Caption``
#: on one record and ``# @16+1 An. Caption`` on another. Requiring it left the
#: offset digits inside the folded string, where they compared as content and
#: reported drift on every row of the records that omit it.
_COMMENT_PREFIX = re.compile(r"^#\s*@\d+\+\d+(?:\.|\s+\S+)\s*")
#: A line break inside a design cell, with whatever indentation wrapped
#: around it. Folded to one space; runs of real spaces are left alone.
_NL = chr(10)
_KEY_LINE = re.compile(r"^([a-z_][a-z0-9_]*) = ")
_LINE_BREAK = re.compile(r"[^\S\r\n]*[\r\n]+[^\S\r\n]*")


@dataclass(frozen=True)
class WaveSpec:
    """One revision's authoring run, declared rather than passed piecemeal."""

    design_path: Path
    prior_casillas_dir: Path
    out_dir: Path
    revision_id: str
    legal_refs: str
    records: tuple[str, ...]
    headers: Mapping[str, str]
    #: Section vocabulary for records whose rows have no prior counterpart.
    #: A record absent from this mapping cannot adjudicate: its unmatched rows
    #: are refused, which is the correct outcome for a record nobody has judged.
    adjudicated_sections: Mapping[str, tuple[str, ...]] = field(default_factory=dict[str, tuple[str, ...]])
    #: Records whose unnumbered rows are deliberately left undeclared, holding
    #: the scope line an earlier edition drew. Widening scope inside a
    #: carry-forward run is how an edition acquires rows nobody adjudicated.
    scope_skip_unnumbered: frozenset[str] = frozenset()
    #: Declared sha256 of the design binary, from the registry's own source
    #: catalogue. The run refuses a design that is not the artifact the
    #: registry cites.
    declared_sha256: str | None = None
    ratio_lengths: frozenset[int] = frozenset({5, 6})
    #: How a row that has no counterpart in the prior edition gets its ``id``.
    #:
    #: ``"segmento_number"`` builds it as ``<SEGMENTO>:<number>``, the convention
    #: on modelos whose every casilla belongs to a named record sheet.
    #:
    #: ``"carried"`` can mint none of its own, so an unmatched row is refused even
    #: where the wave declares a section. Modelo 036 names its casillas with
    #: editorial slugs -- ``pf.identificacion-residencia-indicador`` beside
    #: ``number = "A1"``, with no segmento at all -- and modelo 280 with a
    #: per-record stem unrelated to its sheet name. A slug encodes a section path
    #: and a chosen concept name; no design states one, so no generator may
    #: invent one.
    id_scheme: str = "segmento_number"
    #: Positional-id stem per record, where the sheet's own name will not do.
    #:
    #: An unnumbered slot takes its position range as its number, prefixed by a
    #: stem. The record-oriented designs name their sheets ``T22007000`` and the
    #: lowercased name is the stem. Modelo 280 names its sheets
    #: ``Tipo 1 - Registro De Declarante`` while its corpus uses ``tipo1``, so
    #: the derived number would carry spaces and a hyphen and match nothing in
    #: the edition being carried forward.
    record_stems: Mapping[str, str] = field(default_factory=dict[str, str])
    #: Carry each row's ``legal_refs`` from the prior edition instead of applying
    #: the wave-level list.
    #:
    #: Off by default, because a carried legal_ref can name an orden that does
    #: not reach the new edition's period -- the exact defect being repaired on
    #: modelo 190 right now. On by default would be silent; opt-in makes the wave
    #: say it checked. Where a row has no prior counterpart the wave list applies
    #: regardless, since there is nothing to carry.
    carry_legal_refs: bool = False
    #: Rows the design's reader hoisted out of a desglose group, declared per
    #: record as ``{parent_offset: (child_offset, ...)}``.
    #:
    #: A record whose sub-rows surface beside their own parent does not tile, and
    #: the generator refuses it. This is the ONLY way past that refusal, and it is
    #: deliberately a declaration rather than a heuristic: a heuristic that nests
    #: any contained span would also nest a genuine overlap defect, which is the
    #: thing the tiling check exists to find.
    #:
    #: Declaring a group asserts the author read the design and confirmed the
    #: nesting AEAT printed. Modelo 280's Tipo 2 needs one: AEAT writes "se
    #: subdivide en dos" over 176-186, which is really three parts (176 SIGNO,
    #: 177-184 ENTERO, 185-186 DECIMAL), so the reader's count clause declines the
    #: repair and leaves the two grandchildren at the surface.
    declared_desglose_parents: Mapping[str, Mapping[int, tuple[int, ...]]] = field(
        default_factory=dict[str, dict[int, tuple[int, ...]]]
    )
    #: How the prior edition's shards are found, as a glob with ``{segmento}``.
    #:
    #: The record-oriented default narrows by record because a box number is only
    #: unique WITHIN a record -- modelo 220 prints ``00562`` on three different
    #: ones -- so globbing the whole directory would collide. Modelo 280 names its
    #: shards after their casillas rather than their record and prefixes every
    #: number with its own record instead, so it globs everything and relies on
    #: the number for uniqueness.
    prior_glob: str = "c{segmento}+*.toml"
    #: Derived-number to prior-number aliases, per record.
    #:
    #: Some editions name a slot for what it MEANS rather than where it sits --
    #: modelo 280's declarante NIF is ``tipo1.nif-declarante``, not
    #: ``tipo1.9-17``. No positional rule can produce that name, so matching it is
    #: an author's assertion that the slot at these bytes is that concept, and it
    #: is declared here rather than guessed by resemblance.
    number_aliases: Mapping[str, Mapping[str, str]] = field(default_factory=dict[str, dict[str, str]])
    #: Renumbered rows: the number to LOOK UP in the prior edition, per record.
    #:
    #: Distinct from ``number_aliases``, which rewrites the number a row is
    #: EMITTED under. This one changes only where the prior edition's attributes
    #: are fetched from, leaving the emitted number as this design prints it.
    #:
    #: The difference is the whole point on a renumbering. Modelo 036's 2023
    #: design prints ``[A3A]`` and the 2025 edition declares the same concept as
    #: ``A3B`` -- same offsets, same lengths, same type, byte-identical captions,
    #: with the token changing between a PROVISIONAL and a FINAL file of that one
    #: edition, which is a relabelling rather than a concept moving. Aliasing the
    #: number outright would make this edition assert that its own design prints
    #: A3B, which is false. The row must say A3A and carry A3B's attributes.
    carry_number_aliases: Mapping[str, Mapping[str, str]] = field(default_factory=dict[str, dict[str, str]])
    #: Offsets deliberately left undeclared, per record.
    #:
    #: ``scope_skip_unnumbered`` is useless on a design where NOTHING is numbered;
    #: this names the individual slots instead. Modelo 280's Tipo 2 echoes the
    #: declarante's ejercicio and NIF from Tipo 1 and its prior edition declares
    #: no casilla for either, which is a scope line to hold, not a gap to fill.
    scope_skip_positions: Mapping[str, frozenset[int]] = field(default_factory=dict[str, frozenset[int]])
    #: The box-number grammar this design actually prints, as a regex with one
    #: capturing group, applied to the bracket token's INNER text.
    #:
    #: Default is the record-oriented one: three to six digits. Modelo 036 prints
    #: nine forms against that one -- ``[101]``, ``[65]``, ``[A31]``, ``[B3A]``,
    #: ``[716.a]``, ``[4774bis]``, ``[300,301,302]``, ``[379, 380]``, ``[B1,B2]``
    #: -- and a wave that does not declare them gets a REFUSAL on every row, not
    #: a silent position range. Widening the default instead would loosen every
    #: other modelo's grammar to admit whatever the loosest one needs.
    number_grammar: str | None = None
    #: Collapse design rows that share a box number into ONE casilla.
    #:
    #: A casilla is a CONCEPT, and some designs print one concept across several
    #: fixed-width rows. Modelo 036 splits every date into día, mes and año rows
    #: under a single number, and repeats whole blocks -- Pag. 8 prints numbers
    #: 800, 801, 818 and 859 four times each at a regular stride, once per
    #: repetition of the socio block. Its authored edition declares one casilla
    #: per number and says so in its own comments ("ONE casilla over the dia, mes
    #: and ano components, all printed under the single number 805").
    #:
    #: Off by default. Emitting per row on such a design does not fail loudly --
    #: it writes several casillas carrying the SAME id, which is caught only when
    #: the modelo is loaded, after the write.
    collapse_rows_by_number: bool = False
    #: Numbers the wave declines to declare, per record, listed one by one.
    #:
    #: An enumeration rather than a flag, deliberately. "Decline whatever has no
    #: counterpart in the prior edition" would also swallow the rows that need
    #: judgement -- a renumbered box looks exactly like an undeclared one from the
    #: matcher's side. Listing them means a row that appears later, or one whose
    #: number changes, REFUSES instead of joining the declined set unnoticed.
    #:
    #: Declining is a scope decision and belongs in the revision's own prose too;
    #: this field only stops the generator refusing what the author already
    #: judged.
    scope_declined_numbers: Mapping[str, frozenset[str]] = field(default_factory=dict[str, frozenset[str]])
    #: Numbers withheld because they need a judgement nobody has made yet.
    #:
    #: SEPARATE from ``scope_declined_numbers`` on purpose, and the distinction is
    #: the point rather than bookkeeping: "excluded at parity with the prior
    #: edition" and "awaiting adjudication" are different claims about the same
    #: absence, and collapsing them is exactly the silent under-declaration this
    #: corpus refuses everywhere else. A declined number is a decision; a deferred
    #: one is an open question, and it is reported as such so it cannot quietly
    #: become permanent.
    deferred_numbers: Mapping[str, frozenset[str]] = field(default_factory=dict[str, frozenset[str]])


@dataclass(frozen=True)
class RecordOutcome:
    """What one record sheet produced."""

    segmento: str
    filename: str
    emitted: int
    carried: int
    adjudicated: int
    out_of_scope: int
    tiled: int
    declared_total: int
    body: str


@dataclass
class GenerationReport:
    """Everything the run decided, including what it declined to decide."""

    outcomes: list[RecordOutcome] = field(default_factory=list)
    #: Shards in out_dir this run does not reproduce. Not refused: a wave may
    #: legitimately share a directory with rows it does not own -- modelo 220's
    #: two declaration headers sit in their own shard the money-closure wave
    #: never writes. Reported because the other cause is a shard left stale by a
    #: rename, and that one is a defect.
    orphaned_shards: list[str] = field(default_factory=list)
    #: Attested fields carried forward from rows already on disk -- fields this
    #: generator does not emit and cannot re-derive. Reported so a re-run that
    #: silently dropped them would show as a zero here rather than as nothing.
    attestations_restored: int = 0
    drift: list[str] = field(default_factory=list)
    #: Numbers withheld pending a judgement, reported so an open question cannot
    #: quietly become a permanent absence.
    deferred: list[str] = field(default_factory=list)
    #: Rows whose Contenido changed while the caption held. Reported apart from
    #: caption drift because they are different findings: a rewritten caption is
    #: a relabelling, a rewritten Contenido is usually a changed admissible
    #: domain -- a clave added, a conditional rule altered.
    content_drift: list[str] = field(default_factory=list)
    refusals: list[str] = field(default_factory=list)

    @property
    def total_emitted(self) -> int:
        """Return the number of casillas emitted across all records."""
        return sum(outcome.emitted for outcome in self.outcomes)


def read_design(path: Path) -> dict[str, RecordDesignSheet]:
    """Return the design's record sheets, refusing a partial read.

    ``require_complete`` is deliberate: a sheet the parser skipped is a record
    that will be missing from the emission with nothing at the call site to say
    so.
    """
    extraction = extract_record_design(path)
    return {sheet.name.strip(): sheet for sheet in extraction.require_complete()}


def verify_design_hash(path: Path, declared: str | None) -> str:
    """Refuse a design binary that is not the artifact the registry cites."""
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if declared is not None and actual != declared:
        raise GenerationRefusedError(f"design sha256 {actual} does not match the declared {declared}")
    return actual


def cross_check_sidecar(design_path: Path, sheets: Mapping[str, RecordDesignSheet]) -> None:
    """Refuse when the JSON sidecar describes a different design than the workbook.

    The sidecar is not the source of geometry here, but it is what several
    analysis passes read, so a disagreement between the two means one of them is
    describing a design nobody is authoring against.
    """
    sidecar = Path(str(design_path) + ".extracted.json")
    if not sidecar.exists():
        return
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    declared = payload.get("source_sha256")
    actual = hashlib.sha256(design_path.read_bytes()).hexdigest()
    if declared and declared != actual:
        raise GenerationRefusedError(f"the sidecar describes {declared} but the binary on disk is {actual}")
    # The sheet-name comparison only means something when the sidecar's units ARE
    # sheets. A workbook sidecar splits by worksheet and its titles are the record
    # names; a PDF sidecar splits by PAGE and titles them "Pag. 1"..."Pag. N",
    # because a PDF has no sheets and the reader derives records from the text.
    # Comparing the two would refuse every PDF-sourced design for a disagreement
    # that is really a difference of unit.
    if payload.get("source_kind") != "diseno_registro_workbook":
        return
    titles = {unit["title"].strip() for unit in payload.get("units", ())}
    missing = set(sheets) - titles
    if missing:
        raise GenerationRefusedError(f"the workbook carries sheets the sidecar does not: {sorted(missing)}")


def is_structural(description: str) -> bool:
    """Whether a row is envelope, filler or terminator rather than a casilla."""
    return bool(_STRUCTURAL.match(description.strip()))


def derive_number(
    description: str,
    offset: int,
    length: int,
    segmento: str,
    stem: str | None = None,
    grammar: str | None = None,
) -> tuple[str, str]:
    """Return the box number and the caption with its number token removed.

    The number is located anywhere in the description, never by position in the
    string: Modelo 220's documento de ingreso prints it mid-caption with a form
    placeholder after it, so a trailing-token rule silently mints a positional id
    for a row that has a real number.
    """
    # The workbook hands back the cell intact, newlines and all. A caption is
    # transcribed into a one-line TOML comment, so a line break inside the cell
    # is folded to a single space -- left in, the second line escapes the
    # comment and the fragment is not TOML at all.
    #
    # ONLY the line breaks. AEAT's own runs of spaces are part of what it
    # printed -- "en  credito", "Apellidos  o Razon Social", "(3)-  Resultado"
    # all carry a real double space -- and collapsing those would quietly edit
    # the transcription this corpus exists to preserve.
    flattened = _LINE_BREAK.sub(" ", description).strip()
    pattern = re.compile(grammar) if grammar else _NUMBERED
    matches = tuple(pattern.finditer(flattened))
    if matches:
        number = matches[-1].group(1)
        if not isinstance(number, str):
            raise GenerationRefusedError("the number grammar did not capture a string")
        return number, pattern.sub("", flattened).strip()
    lettered = _LETTERED.search(flattened)
    if lettered:
        letter = lettered.group(1)
        if not isinstance(letter, str):
            raise GenerationRefusedError("the letter grammar did not capture a string")
        return letter, _LETTERED.sub("", flattened).strip()
    prefix = stem or segmento.lower()
    slot = f"{offset}" if length == 1 else f"{offset}-{offset + length - 1}"
    return f"{prefix}.{slot}", flattened


def group_comment(members: Sequence[RecordDesignField], caption: str) -> str:
    """Render the comment for one casilla, which may span several design rows."""
    if len(members) == 1:
        return comment_line(members[0], caption)
    first, last = members[0], members[-1]
    span = last.offset + last.length - first.offset
    parts = ", ".join(f"@{m.offset}+{m.length}" for m in members)
    return (
        f"# @{first.offset}+{span} {first.type_code}. {caption} "
        f"[ONE casilla over {len(members)} printed components: {parts}]"
    )


def comment_line(row: RecordDesignField, caption: str) -> str:
    """Render the transcribed comment for one design row.

    ONE renderer, used both to write the fragment and to compare against a prior
    edition's line. Two renderers drift apart: the emitted comment carried the
    Contenido cell after a pipe while the drift comparison used the caption
    alone, so on a design where every row has Contenido -- modelo 280, where the
    whole semantic payload lives there -- every carried row reported a meaning
    change. A 100% false-positive rate makes the list useless exactly where it
    is most needed, and it was invisible on a design whose Contenido is mostly
    empty.
    """
    content = _LINE_BREAK.sub(" ", row.content).strip() if row.content else ""
    trailing = f" | {content}" if content else ""
    return f"# @{row.offset}+{row.length} {row.type_code}. {caption}{trailing}"


def normalise_for_drift(caption: str) -> str:
    """Fold a caption so only a meaning change survives the comparison.

    The devengo year and the page cross-references move in every edition and are
    not meaning changes; AEAT renumbers its own schedules constantly. What must
    survive is a rewritten predicate.
    """
    folded = caption.lower()
    folded = _COMMENT_PREFIX.sub("", folded)
    folded = _PAGE_POINTER.sub("", folded)
    folded = _YEAR.sub("", folded)
    folded = _BRACKET_TOKEN.sub("", folded)
    return _NON_ALNUM.sub("", folded)


def audit_sheet(
    sheet: RecordDesignSheet,
    declared_desglose: Mapping[int, tuple[int, ...]] | None = None,
    grammar: str | None = None,
) -> list[str]:
    """Refusals that must stop a run rather than be skipped past."""
    problems: list[str] = []
    name = sheet.name.strip()
    for row in sheet.fields:
        for char, label in _FORBIDDEN.items():
            if char in row.description:
                problems.append(f"{name} @{row.offset}: description contains {label}")
        if row.type_code.strip().lower() not in _TYPE_CODES:
            problems.append(f"{name} @{row.offset}: unknown type_code {row.type_code!r}")
        if len(re.findall(grammar or _NUMBERED.pattern, row.description)) > 1:
            problems.append(
                f"{name} @{row.offset}: more than one box token in one description; "
                "the number rule has become ambiguous"
            )
        pattern = re.compile(grammar) if grammar else _NUMBERED
        recognised = {
            match.group(1) if pattern.groups else match.group(0) for match in pattern.finditer(row.description)
        } | {match.group(1) for match in _LETTERED.finditer(row.description)}
        for token in _IDENTIFIER_BRACKET.findall(row.description):
            if token not in recognised:
                problems.append(
                    f"{name} @{row.offset}: bracket token [{token}] is not a recognised "
                    "box number on this wave's grammar; it would silently become a "
                    "position range"
                )
    # A top-level row whose span sits inside another top-level row's span is a
    # desglose sub-row the reader could not nest -- a grandchild hoisted to the
    # surface. Summing it double-counts its bytes and the record appears not to
    # tile. Modelo 280's Tipo 2 does exactly this: AEAT writes "se subdivide en
    # dos" over a group that is really three parts, the nester's count clause
    # correctly declines to repair it, and 177-184 and 185-186 surface beside
    # their own grandparent at 176-186, making the record sum 510 against a
    # declared 500. Refusing names the real defect; excluding them would paper
    # over a reader limitation with a generator workaround.
    hoisted = {child for children in (declared_desglose or {}).values() for child in children}
    ordered = [row for row in sorted(sheet.fields, key=lambda item: item.offset) if row.offset not in hoisted]
    for outer in ordered:
        outer_end = outer.offset + outer.length
        contained = [
            inner
            for inner in ordered
            if inner is not outer and inner.offset >= outer.offset and inner.offset + inner.length <= outer_end
        ]
        if contained:
            spans = ", ".join(f"@{item.offset}+{item.length}" for item in contained)
            problems.append(
                f"{name}: @{outer.offset}+{outer.length} contains {spans} at the same "
                "level; these are desglose sub-rows the reader did not nest, and "
                "summing them double-counts the record"
            )
            break

    cursor = 1
    for row in ordered:
        if row.offset != cursor:
            problems.append(f"{name}: tiling breaks at @{row.offset}, expected @{cursor}")
            break
        cursor = row.offset + row.length
    else:
        tiled = cursor - 1
        if sheet.total_positions is not None and tiled != sheet.total_positions:
            problems.append(f"{name}: tiles {tiled} but the design declares {sheet.total_positions}")
    return problems


def load_prior_attributes(
    directory: Path, segmento: str, glob: str = "c{segmento}+*.toml"
) -> dict[str, dict[str, str]]:
    """Read adjudicated attributes and the transcribed caption from an edition."""
    attributes: dict[str, dict[str, str]] = {}
    for path in sorted(directory.glob(glob.format(segmento=segmento))):
        current: dict[str, str] = {}
        collecting_legal_refs: list[str] | None = None
        collecting_section: list[str] | None = None
        number: str | None = None
        pending = ""
        for raw in path.read_text(encoding="utf-8").split("\n"):
            line = raw.strip()
            if line.startswith("# @"):
                pending = line
            elif line.startswith("[[revisions."):
                open_array = (
                    "legal_refs"
                    if collecting_legal_refs is not None
                    else "section"
                    if collecting_section is not None
                    else None
                )
                if open_array is not None:
                    # An array that never closed leaves the field unset and the row
                    # takes the wave default without a word -- the exact silence
                    # that cost modelo 036 all 530 of its legal_refs. Refuse on the
                    # malformed prior instead, naming the casilla it belongs to.
                    raise GenerationRefusedError(
                        f"{path.name}: {open_array} array for casilla {number!r} is never closed"
                    )
                if number:
                    attributes[number] = current
                current, number = {"_caption": pending}, None
                collecting_legal_refs = None
                collecting_section = None
            elif line.startswith("number = "):
                number = line.split("=", 1)[1].strip().strip('"')
            elif line.startswith(("id = ", "segmento = ")):
                key, value = line.split("=", 1)
                current[key.strip()] = value.strip().strip('"')
            elif line.startswith("legal_refs = "):
                # A prior edition may write this array on one line or across
                # many. Requiring a closing bracket on the same line made
                # carry_legal_refs SILENTLY INERT against any multi-line
                # prior -- every row fell back to the wave default and the
                # run still reported carried=N. Modelo 036 lost all 530 rows
                # that way against a prior with 702 multi-line arrays.
                value = line.split("=", 1)[1].strip()
                if value.endswith("]"):
                    current["legal_refs"] = value
                else:
                    collecting_legal_refs = [value]
            elif collecting_legal_refs is not None:
                collecting_legal_refs.append(line.strip())
                if line.rstrip().endswith("]"):
                    current["legal_refs"] = " ".join(collecting_legal_refs)
                    collecting_legal_refs = None
            elif line.startswith(("section = ", "data_type = ")):
                key, value = line.split("=", 1)
                key, value = key.strip(), value.strip()
                # section is an ARRAY and a prior edition may wrap it. Taking the
                # first line alone would store a bare "[" and emit TOML that does
                # not parse -- worse than the legal_refs case, which merely fell
                # back to a default. 156 section arrays are multi-line in this
                # corpus today, all on modelo 200.
                if key == "section" and not value.endswith("]"):
                    collecting_section = [value]
                else:
                    current[key] = value
            elif collecting_section is not None:
                collecting_section.append(line.strip())
                if line.rstrip().endswith("]"):
                    current["section"] = " ".join(collecting_section)
                    collecting_section = None
        if number:
            attributes[number] = current
    return attributes


def _render_row(
    *,
    members: Sequence[RecordDesignField],
    revision_id: str,
    segmento: str | None,
    casilla_id: str,
    number: str,
    row: RecordDesignField,
    caption: str,
    section: str,
    data_type: str,
    legal_refs: str,
) -> str:
    segmento_line = f'segmento = "{segmento}"\n' if segmento else ""
    return (
        f"{group_comment(members, caption)}\n"
        f'[[revisions."{revision_id}".casillas]]\n'
        f'id = "{casilla_id}"\n'
        f'number = "{number}"\n'
        f"{segmento_line}"
        f"section = {section}\n"
        f"data_type = {data_type}\n"
        f"required = false\n"
        f'input_kind = "manual"\n'
        f"legal_refs = {legal_refs}\n"
    )


def generate(spec: WaveSpec, *, write: bool = False) -> GenerationReport:
    """Emit one revision's shards, refusing anything that needs a judgement."""
    verify_design_hash(spec.design_path, spec.declared_sha256)
    sheets = read_design(spec.design_path)
    cross_check_sidecar(spec.design_path, sheets)
    return emit_records(spec, sheets, write=write)


def _filename_stem(block: str) -> str:
    """The part of a rendered row's id that names it inside its file.

    Record-oriented ids are ``<SEGMENTO>:<number>`` and the segmento is already
    in the filename, so only the tail is repeated. A slug id -- modelo 036's
    ``pf.identificacion-residencia-indicador`` -- has no colon at all, and
    splitting on one raised IndexError rather than producing a wrong name, which
    is the better of the two failures but still a failure.
    """
    casilla_id = block.split('id = "')[1].split('"')[0]
    _, separator, tail = casilla_id.partition(":")
    return tail if separator else casilla_id


def emit_records(
    spec: WaveSpec,
    sheets: Mapping[str, RecordDesignSheet],
    *,
    write: bool = False,
) -> GenerationReport:
    """Emit from already-read sheets.

    Separate from :func:`generate` so the emission can be exercised against a
    constructed sheet. A gate that can only reach this logic through a real
    workbook cannot plant a defect in it, and a planted defect is the only
    evidence that the refusals here have teeth.
    """
    report = GenerationReport()
    for segmento in spec.records:
        sheet = sheets.get(segmento)
        if sheet is None:
            raise GenerationRefusedError(f"{segmento}: no such sheet in the design")
        problems = audit_sheet(sheet, spec.declared_desglose_parents.get(segmento), spec.number_grammar)
        if problems:
            raise GenerationRefusedError("; ".join(problems))

        prior = load_prior_attributes(spec.prior_casillas_dir, segmento, spec.prior_glob)
        emitted: list[str] = []
        carried = adjudicated = out_of_scope = 0

        hoisted = {
            child for children in spec.declared_desglose_parents.get(segmento, {}).values() for child in children
        }
        stem = spec.record_stems.get(segmento, segmento.lower())
        grouped: dict[str, list[RecordDesignField]] = {}
        captions: dict[str, str] = {}
        for candidate in sorted(sheet.fields, key=lambda item: item.offset):
            if candidate.offset in hoisted or is_structural(candidate.description):
                continue
            derived, derived_caption = derive_number(
                candidate.description,
                candidate.offset,
                candidate.length,
                segmento,
                stem,
                spec.number_grammar,
            )
            derived = spec.number_aliases.get(segmento, {}).get(derived, derived)
            if spec.collapse_rows_by_number:
                grouped.setdefault(derived, []).append(candidate)
                captions.setdefault(derived, derived_caption)
            else:
                grouped[f"{derived}@{candidate.offset}"] = [candidate]
                captions[f"{derived}@{candidate.offset}"] = derived_caption

        for key, members in grouped.items():
            row = members[0]
            number = key.split("@")[0] if not spec.collapse_rows_by_number else key
            caption = captions[key]
            positional = number.startswith(f"{stem}.")
            row_legal_refs = spec.legal_refs
            if row.offset in spec.scope_skip_positions.get(segmento, frozenset()):
                out_of_scope += 1
                continue
            if positional and segmento in spec.scope_skip_unnumbered:
                out_of_scope += 1
                continue
            if number in spec.scope_declined_numbers.get(segmento, frozenset()):
                out_of_scope += 1
                continue
            if number in spec.deferred_numbers.get(segmento, frozenset()):
                report.deferred.append(
                    f"{segmento}:{number} @{row.offset}+{row.length} ({len(members)} printed row(s)) {caption[:64]}"
                )
                continue

            carry_key = spec.carry_number_aliases.get(segmento, {}).get(number, number)
            if carry_key in prior:
                attributes = prior[carry_key]
                section = attributes["section"]
                data_type = attributes["data_type"]
                # The id is carried, never rebuilt. On the record-oriented
                # modelos it happens to equal "<SEGMENTO>:<number>", but modelo
                # 036 names its casillas with editorial slugs and modelo 280
                # with a per-record stem, and neither is derivable from a design.
                casilla_id = attributes.get("id") or f"{segmento}:{number}"
                if spec.carry_legal_refs and attributes.get("legal_refs"):
                    row_legal_refs = attributes["legal_refs"]
                row_segmento = attributes.get("segmento") or None
                carried += 1
                was = attributes.get("_caption", "")
                if was:
                    # Compare caption against caption and content against
                    # content, splitting both sides the same way. Comparing a
                    # whole rendered line against a hand-authored prior does not
                    # work: the earlier editions of this corpus wrote the type
                    # into some comments and not others, and never wrote the
                    # Contenido cell at all, so every content-bearing row would
                    # read as drift.
                    was_caption, _, was_content = was.partition(" | ")
                    now_caption, _, now_content = comment_line(row, caption).partition(" | ")
                    if normalise_for_drift(was_caption) != normalise_for_drift(now_caption):
                        report.drift.append(
                            f"{segmento}:{number} @{row.offset}+{row.length}\n"
                            f"    prior: {was_caption[2:].strip()[:96]}\n"
                            f"    now:   {caption[:96]}"
                        )
                    # Content drift is reported separately and only where the
                    # prior recorded content at all. On designs whose semantic
                    # payload lives in Contenido -- the clave enumerations and
                    # conditional rules -- a caption comparison is blind to a
                    # meaning change by construction.
                    elif was_content and normalise_for_drift(was_content) != normalise_for_drift(now_content):
                        report.content_drift.append(
                            f"{segmento}:{number} @{row.offset}+{row.length}\n"
                            f"    prior contenido: {was_content.strip()[:96]}\n"
                            f"    now contenido:   {now_content.strip()[:96]}"
                        )
            elif segmento in spec.adjudicated_sections and spec.id_scheme == "segmento_number":
                tokens = spec.adjudicated_sections[segmento]
                section = "[" + ", ".join(f'"{token}"' for token in tokens) + "]"
                data_type = '"ratio"' if row.length in spec.ratio_lengths else '"money"'
                casilla_id = f"{segmento}:{number}"
                row_segmento = segmento
                adjudicated += 1
            else:
                report.refusals.append(f"{segmento}:{number} @{row.offset}+{row.length} {caption[:70]}")
                continue

            emitted.append(
                _render_row(
                    members=members,
                    revision_id=spec.revision_id,
                    segmento=row_segmento,
                    casilla_id=casilla_id,
                    number=number,
                    row=row,
                    caption=caption,
                    section=section,
                    data_type=data_type,
                    legal_refs=row_legal_refs,
                )
            )

        if report.refusals:
            continue
        if not emitted:
            raise GenerationRefusedError(f"{segmento}: nothing emitted")

        first = _filename_stem(emitted[0])
        last = _filename_stem(emitted[-1])
        filename = (
            f"c{segmento}+{first}__c{segmento}+{last}.toml"
            if spec.id_scheme == "segmento_number"
            else f"c{first}__c{last}.toml"
        )
        body = spec.headers[segmento] + "\n\n" + "\n".join(emitted)
        tiled = sum(row.length for row in sheet.fields if row.offset not in hoisted)
        report.outcomes.append(
            RecordOutcome(
                segmento=segmento,
                filename=filename,
                emitted=len(emitted),
                carried=carried,
                adjudicated=adjudicated,
                out_of_scope=out_of_scope,
                tiled=tiled,
                declared_total=sheet.total_positions or tiled,
                body=body,
            )
        )

    # NOTHING IS WRITTEN UNTIL EVERY RECORD HAS BEEN EMITTED AND CHECKED.
    #
    # An id must be unique across the whole EDITION, not merely within a record,
    # and a duplicate does not refuse anywhere downstream of here -- it serialises
    # into valid TOML and is caught only when somebody loads the modelo, after the
    # files are on disk. Modelo 036 would have produced 263 casillas sharing 85
    # ids, because AEAT prints one box number over several rows.
    #
    # Deferring the writes also means a refusal on the last record cannot leave
    # the first ones written. Emission is all-or-nothing.
    _refuse_duplicate_ids(report)

    # ATTESTATIONS ON DISK OUTLIVE THE RUN THAT WROTE THE ROW.
    #
    # This generator emits eight fields. Everything else a row carries was put
    # there afterwards by a seeder or a person -- continuidad and semantic_role --
    # and re-emitting the eight would delete it with nothing to notice it by. The
    # harvest runs against out_dir BEFORE anything is written, and a row that has
    # been attested but would no longer be emitted refuses rather than losing it.
    harvested = harvest_attestations(spec.out_dir, spec.revision_id)
    if harvested:
        refuse_dropped_attestations(
            harvested,
            set(emitted_ids(report)),
            {outcome.filename for outcome in report.outcomes},
        )
        restored = 0
        for index, outcome in enumerate(report.outcomes):
            body, carried = reattach_attestations(outcome.body, harvested, spec.revision_id)
            restored += carried
            report.outcomes[index] = dataclasses.replace(outcome, body=body)
        report.attestations_restored = restored
        produced = {outcome.filename for outcome in report.outcomes}
        report.orphaned_shards = sorted(path.name for path in spec.out_dir.glob("*.toml") if path.name not in produced)

    if write:
        for outcome in report.outcomes:
            spec.out_dir.mkdir(parents=True, exist_ok=True)
            target = spec.out_dir / outcome.filename
            target.write_text(outcome.body, encoding="utf-8")
            back = target.read_text(encoding="utf-8")
            if back != outcome.body:
                raise GenerationRefusedError(f"{outcome.segmento}: read-back differs from the write")
            for number, line in enumerate(back.splitlines(), start=1):
                if line and not (line.startswith(("#", "[")) or _KEY_LINE.match(line)):
                    raise GenerationRefusedError(
                        f"{outcome.segmento}: line {number} is neither comment nor key: {line[:60]!r}"
                    )
            try:
                parse_toml(back)
            except TomlDecodeError as error:
                raise GenerationRefusedError(
                    f"{outcome.segmento}: the emitted shard does not parse: {error}"
                ) from error
            marker = f'[[revisions."{spec.revision_id}".casillas]]'
            if back.count(marker) != outcome.emitted:
                raise GenerationRefusedError(f"{outcome.segmento}: read-back casilla count is wrong")

    if report.refusals:
        raise GenerationRefusedError(
            f"{len(report.refusals)} row(s) need adjudication: " + "; ".join(report.refusals[:5])
        )
    return report


def _source_lines(data: bytes) -> list[str]:
    """Decode a shard and split it, tolerating either line-ending style."""
    return data.decode("utf-8").replace(chr(13) + _NL, _NL).split(_NL)


def harvest_attestations(out_dir: Path, revision_id: str) -> dict[str, tuple[str, list[str]]]:
    """Every key line a later pass added to rows this generator already wrote.

    The generator emits eight fields. Anything else on a row on disk was put there
    by somebody else -- ``continuidad_id`` with its origin and evidence,
    ``semantic_role`` with its cardinality. Those are attestations: a person or a
    seeder asserting something this generator cannot re-derive. A re-run that
    simply re-emits its own eight fields deletes them and reports nothing, because
    from here the output looks exactly as it did the first time. On 2026-09-12 that
    was 423 stamps on modelo 036, 54 on 280 and 6 on 220.

    Harvest is keyed by casilla id and scans the WHOLE directory rather than the
    file a row is expected in, because a shard is named for its first and last
    casilla and a row that gains a neighbour moves file. The file a row was found
    in is returned with it, because whether losing the row matters depends on
    whether this run overwrites that file.
    """
    harvested: dict[str, tuple[str, list[str]]] = {}
    marker = f'[[revisions."{revision_id}".casillas]]'
    if not out_dir.is_dir():
        return harvested
    for path in sorted(out_dir.glob("*.toml")):
        current: list[str] = []
        casilla_id: str | None = None
        for line in _source_lines(path.read_bytes()):
            if line.strip() == marker:
                if casilla_id:
                    harvested[casilla_id] = (path.name, current)
                current = []
                casilla_id = None
                continue
            if line.startswith("id = "):
                casilla_id = line.split("=", 1)[1].strip().strip('"')
                continue
            if _KEY_LINE.match(line):
                current.append(line)
        if casilla_id:
            harvested[casilla_id] = (path.name, current)
    return harvested


def reattach_attestations(body: str, harvested: dict[str, tuple[str, list[str]]], revision_id: str) -> tuple[str, int]:
    """Carry every attested field forward onto the row it was made about.

    A field the emission already produces is never overwritten: the generator is
    the authority for its own eight, the attestation for everything else.
    """
    marker = f'[[revisions."{revision_id}".casillas]]'
    out: list[str] = []
    block: list[str] = []
    casilla_id: str | None = None
    carried = 0

    def flush() -> None:
        nonlocal carried, block, casilla_id
        if casilla_id:
            emitted = {match.group(1) for line in block if (match := _KEY_LINE.match(line))}
            for line in harvested.get(casilla_id, ("", []))[1]:
                key_match = _KEY_LINE.match(line)
                if key_match is None:
                    raise GenerationRefusedError(f"attestation line is not a key line: {line!r}")
                key = key_match.group(1)
                if key not in emitted:
                    block.append(line)
                    carried += 1
        out.extend(block)
        block, casilla_id = [], None

    for line in body.split(_NL):
        if line.strip() == marker:
            flush()
            block = [line]
            continue
        if block:
            if line.startswith("id = "):
                casilla_id = line.split("=", 1)[1].strip().strip('"')
                block.append(line)
                continue
            if _KEY_LINE.match(line):
                block.append(line)
                continue
            flush()
        out.append(line)
    flush()
    return _NL.join(out), carried


def refuse_dropped_attestations(
    harvested: dict[str, tuple[str, list[str]]],
    emitted: set[str],
    overwritten: set[str],
) -> None:
    """Refuse when a shard this run rewrites holds an attested row it will not re-emit.

    Preservation only helps a row the emission still produces. A row that has been
    attested, lives in a file this run overwrites, and is no longer emitted --
    because the scope narrowed, the grammar changed, or a number moved into the
    declined set -- would lose its attestation with nothing to carry it onto.

    A row in a shard this run does not write is NOT at risk and must not refuse:
    modelo 220's two declaration headers live in their own shard that the
    money-closure wave never touches, and refusing on them would have blocked a
    generator that was never going to harm them.
    """
    orphaned = sorted(
        casilla_id
        for casilla_id, (source, lines) in harvested.items()
        if lines and casilla_id not in emitted and source in overwritten
    )
    if not orphaned:
        return
    raise GenerationRefusedError(
        f"{len(orphaned)} attested row(s) sit in a shard this run rewrites and "
        f"would not be re-emitted: {', '.join(orphaned[:5])}"
        f"{' ...' if len(orphaned) > 5 else ''}. They carry fields this generator "
        "does not produce (continuidad or semantic_role), so re-emitting without "
        "them destroys work that cannot be re-derived here. Restore the rows to "
        "scope, or move the attestations, before running again."
    )


def emitted_ids(report: GenerationReport) -> list[str]:
    """Every casilla id this run would write, in emission order."""
    return [
        block.split('id = "')[1].split('"')[0]
        for outcome in report.outcomes
        for block in outcome.body.split("[[revisions.")[1:]
    ]


def _refuse_duplicate_ids(report: GenerationReport) -> None:
    """Refuse before writing when two casillas would share an id."""
    seen: dict[str, int] = {}
    for casilla_id in emitted_ids(report):
        seen[casilla_id] = seen.get(casilla_id, 0) + 1
    duplicates = {key: count for key, count in seen.items() if count > 1}
    if not duplicates:
        return
    worst = sorted(duplicates.items(), key=lambda kv: -kv[1])[:5]
    detail = ", ".join(f"{key} x{count}" for key, count in worst)
    raise GenerationRefusedError(
        f"{len(duplicates)} casilla id(s) would be written more than once "
        f"({sum(duplicates.values())} rows): {detail}. An id must be unique across the "
        "whole edition. A duplicate serialises into valid TOML and is caught only when "
        "the modelo is loaded, which is after the files are on disk -- so it is refused "
        "here, before anything is written."
    )


def format_report(report: GenerationReport) -> str:
    """Render a run for a human, drift and all."""
    lines = [
        f"OK {outcome.segmento}: emit={outcome.emitted} carried={outcome.carried} "
        f"adjudicated={outcome.adjudicated} out-of-scope={outcome.out_of_scope} "
        f"tiled={outcome.tiled}=={outcome.declared_total} -> {outcome.filename}"
        for outcome in report.outcomes
    ]
    lines.append(f"\nDEFERRED pending adjudication: {len(report.deferred)}")
    lines.extend(f"  {entry}" for entry in report.deferred)
    lines.append(f"\nCAPTION DRIFT on position-stable rows: {len(report.drift)}")
    lines.extend(f"  {entry}" for entry in report.drift)
    if report.orphaned_shards:
        lines.append(f"\nSHARDS IN out_dir THIS RUN DOES NOT PRODUCE: {len(report.orphaned_shards)}")
        lines.extend(f"  {name}" for name in report.orphaned_shards)
    lines.append(f"\nATTESTATIONS carried forward from disk: {report.attestations_restored}")
    lines.append(f"\nTOTAL casillas: {report.total_emitted}")
    return "\n".join(lines)


def sections_of(sheets: Sequence[RecordDesignSheet]) -> dict[str, int]:
    """Field counts per sheet, for asserting a run against a measured shape."""
    return {sheet.name.strip(): len(sheet.fields) for sheet in sheets}
