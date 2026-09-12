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

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from cadrumo.domain.calculations.registry.record_design_schema import (
    RecordDesignField,
    RecordDesignSheet,
)

from ..compiler.record_design import extract_record_design

__all__ = [
    "GenerationRefused",
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


class GenerationRefused(Exception):
    """The design, the prior edition or the emission did not hold up."""


#: Envelope, filler and terminator captions. A row matching one of these is not
#: a casilla: it is the modelo/pagina identifier, the reservado run AEAT fills
#: with blanks, or the end-of-record marker. The classification is asserted
#: against the design's own declared total rather than trusted, so a filler
#: shape this pattern does not know about cannot quietly become a casilla.
_STRUCTURAL = re.compile(
    r"^(inicio del identificador|fin de identificador|fin de registro|reservado"
    r"|modelo\.?$|modelo declaraci|blancos$|tipo de registro$"
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
_TYPE_CODES = frozenset({
    "num", "n", "an", "a",
    "numérico", "alfanumérico", "alfabético", "blancos",
    "numerico", "alfanumerico", "alfabetico",
})
#: Characters whose appearance means the extraction changed shape under us. A
#: non-breaking space reads as a space and matches nothing, which is how a
#: citation screen once reported twenty-three absent quotations that were all
#: present.
_FORBIDDEN = {" ": "NBSP", "\t": "TAB", "\r": "CR"}
_YEAR = re.compile(r"20\d\d")
_PAGE_POINTER = re.compile(
    r"\(?p[aeiouáéíóú]*g\.?\s*[^)]*\)?", re.IGNORECASE
)
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
    adjudicated_sections: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
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
    drift: list[str] = field(default_factory=list)
    #: Rows whose Contenido changed while the caption held. Reported apart from
    #: caption drift because they are different findings: a rewritten caption is
    #: a relabelling, a rewritten Contenido is usually a changed admissible
    #: domain -- a clave added, a conditional rule altered.
    content_drift: list[str] = field(default_factory=list)
    refusals: list[str] = field(default_factory=list)

    @property
    def total_emitted(self) -> int:
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
        raise GenerationRefused(
            f"design sha256 {actual} does not match the declared {declared}"
        )
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
        raise GenerationRefused(
            f"the sidecar describes {declared} but the binary on disk is {actual}"
        )
    titles = {unit["title"].strip() for unit in payload.get("units", ())}
    missing = set(sheets) - titles
    if missing:
        raise GenerationRefused(
            f"the workbook carries sheets the sidecar does not: {sorted(missing)}"
        )


def is_structural(description: str) -> bool:
    """Whether a row is envelope, filler or terminator rather than a casilla."""
    return bool(_STRUCTURAL.match(description.strip()))


def derive_number(description: str, offset: int, length: int, segmento: str) -> tuple[str, str]:
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
    numbers = _NUMBERED.findall(flattened)
    if numbers:
        return numbers[-1], _NUMBERED.sub("", flattened).strip()
    lettered = _LETTERED.search(flattened)
    if lettered:
        return lettered.group(1), _LETTERED.sub("", flattened).strip()
    stem = segmento.lower()
    slot = f"{offset}" if length == 1 else f"{offset}-{offset + length - 1}"
    return f"{stem}.{slot}", flattened


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


def audit_sheet(sheet: RecordDesignSheet) -> list[str]:
    """Refusals that must stop a run rather than be skipped past."""
    problems: list[str] = []
    name = sheet.name.strip()
    for row in sheet.fields:
        for char, label in _FORBIDDEN.items():
            if char in row.description:
                problems.append(f"{name} @{row.offset}: description contains {label}")
        if row.type_code.strip().lower() not in _TYPE_CODES:
            problems.append(f"{name} @{row.offset}: unknown type_code {row.type_code!r}")
        if len(_NUMBERED.findall(row.description)) > 1:
            problems.append(
                f"{name} @{row.offset}: more than one box token in one description; "
                "the number rule has become ambiguous"
            )
        recognised = set(_NUMBERED.findall(row.description)) | {
            match.group(1) for match in _LETTERED.finditer(row.description)
        }
        for token in _IDENTIFIER_BRACKET.findall(row.description):
            if token not in recognised and not _NUMBERED.fullmatch(f"[{token}]"):
                problems.append(
                    f"{name} @{row.offset}: bracket token [{token}] is not a recognised "
                    "box number on this wave's grammar; it would silently become a "
                    "position range"
                )
    cursor = 1
    for row in sorted(sheet.fields, key=lambda item: item.offset):
        if row.offset != cursor:
            problems.append(
                f"{name}: tiling breaks at @{row.offset}, expected @{cursor}"
            )
            break
        cursor = row.offset + row.length
    else:
        tiled = cursor - 1
        if sheet.total_positions is not None and tiled != sheet.total_positions:
            problems.append(
                f"{name}: tiles {tiled} but the design declares {sheet.total_positions}"
            )
    return problems


def load_prior_attributes(directory: Path, segmento: str) -> dict[str, dict[str, str]]:
    """Read adjudicated attributes and the transcribed caption from an edition."""
    attributes: dict[str, dict[str, str]] = {}
    for path in sorted(directory.glob(f"c{segmento}+*.toml")):
        current: dict[str, str] = {}
        number: str | None = None
        pending = ""
        for raw in path.read_text(encoding="utf-8").split("\n"):
            line = raw.strip()
            if line.startswith("# @"):
                pending = line
            elif line.startswith("[[revisions."):
                if number:
                    attributes[number] = current
                current, number = {"_caption": pending}, None
            elif line.startswith("number = "):
                number = line.split("=", 1)[1].strip().strip('"')
            elif line.startswith(("id = ", "segmento = ")):
                key, value = line.split("=", 1)
                current[key.strip()] = value.strip().strip('"')
            elif line.startswith(("section = ", "data_type = ")):
                key, value = line.split("=", 1)
                current[key.strip()] = value.strip()
        if number:
            attributes[number] = current
    return attributes


def _render_row(
    *,
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
        f"{comment_line(row, caption)}\n"
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
            raise GenerationRefused(f"{segmento}: no such sheet in the design")
        problems = audit_sheet(sheet)
        if problems:
            raise GenerationRefused("; ".join(problems))

        prior = load_prior_attributes(spec.prior_casillas_dir, segmento)
        emitted: list[str] = []
        carried = adjudicated = out_of_scope = 0

        for row in sorted(sheet.fields, key=lambda item: item.offset):
            if is_structural(row.description):
                continue
            number, caption = derive_number(
                row.description, row.offset, row.length, segmento
            )
            positional = number.startswith(f"{segmento.lower()}.")
            if positional and segmento in spec.scope_skip_unnumbered:
                out_of_scope += 1
                continue

            if number in prior:
                attributes = prior[number]
                section = attributes["section"]
                data_type = attributes["data_type"]
                # The id is carried, never rebuilt. On the record-oriented
                # modelos it happens to equal "<SEGMENTO>:<number>", but modelo
                # 036 names its casillas with editorial slugs and modelo 280
                # with a per-record stem, and neither is derivable from a design.
                casilla_id = attributes.get("id") or f"{segmento}:{number}"
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
                    elif was_content and normalise_for_drift(was_content) != normalise_for_drift(
                        now_content
                    ):
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
                report.refusals.append(
                    f"{segmento}:{number} @{row.offset}+{row.length} {caption[:70]}"
                )
                continue

            emitted.append(
                _render_row(
                    revision_id=spec.revision_id,
                    segmento=row_segmento,
                    casilla_id=casilla_id,
                    number=number,
                    row=row,
                    caption=caption,
                    section=section,
                    data_type=data_type,
                    legal_refs=spec.legal_refs,
                )
            )

        if report.refusals:
            continue
        if not emitted:
            raise GenerationRefused(f"{segmento}: nothing emitted")

        first = _filename_stem(emitted[0])
        last = _filename_stem(emitted[-1])
        filename = (
            f"c{segmento}+{first}__c{segmento}+{last}.toml"
            if spec.id_scheme == "segmento_number"
            else f"c{first}__c{last}.toml"
        )
        body = spec.headers[segmento] + "\n\n" + "\n".join(emitted)
        tiled = sum(row.length for row in sheet.fields)
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

        if write:
            spec.out_dir.mkdir(parents=True, exist_ok=True)
            target = spec.out_dir / filename
            target.write_text(body, encoding="utf-8")
            back = target.read_text(encoding="utf-8")
            if back != body:
                raise GenerationRefused(f"{segmento}: read-back differs from the write")
            for number, line in enumerate(back.splitlines(), start=1):
                if line and not line.startswith(("#", "[", "i", "n", "s", "d", "r", "l")):
                    raise GenerationRefused(
                        f"{segmento}: line {number} is neither comment nor key: {line[:60]!r}"
                    )
            marker = f'[[revisions."{spec.revision_id}".casillas]]'
            if back.count(marker) != len(emitted):
                raise GenerationRefused(f"{segmento}: read-back casilla count is wrong")

    if report.refusals:
        raise GenerationRefused(
            f"{len(report.refusals)} row(s) need adjudication: "
            + "; ".join(report.refusals[:5])
        )
    return report


def format_report(report: GenerationReport) -> str:
    """Render a run for a human, drift and all."""
    lines = [
        f"OK {outcome.segmento}: emit={outcome.emitted} carried={outcome.carried} "
        f"adjudicated={outcome.adjudicated} out-of-scope={outcome.out_of_scope} "
        f"tiled={outcome.tiled}=={outcome.declared_total} -> {outcome.filename}"
        for outcome in report.outcomes
    ]
    lines.append(f"\nCAPTION DRIFT on position-stable rows: {len(report.drift)}")
    lines.extend(f"  {entry}" for entry in report.drift)
    lines.append(f"\nTOTAL casillas: {report.total_emitted}")
    return "\n".join(lines)


def sections_of(sheets: Sequence[RecordDesignSheet]) -> dict[str, int]:
    """Field counts per sheet, for asserting a run against a measured shape."""
    return {sheet.name.strip(): len(sheet.fields) for sheet in sheets}
