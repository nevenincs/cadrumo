"""Record design extraction, number interpretation, and geometry checks."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path

from cadrumo.core.hashing import sha256_file
from dev.registry.compiler.record_design_schema import (
    RecordDesignField,
    RecordDesignSheet,
)

from ..compiler.record_design import extract_record_design
from .casilla_shard_types import GenerationRefusedError

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


_LINE_BREAK = re.compile(r"[^\S\r\n]*[\r\n]+[^\S\r\n]*")


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
    actual = sha256_file(path)
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
    actual = sha256_file(design_path)
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
    for row in sheet.fields:
        problems.extend(_row_declaration_problems(sheet.name.strip(), row, grammar))
    problems.extend(_geometry_problems(sheet, declared_desglose))
    return problems


def _row_declaration_problems(
    name: str,
    row: RecordDesignField,
    grammar: str | None,
) -> list[str]:
    problems = [
        f"{name} @{row.offset}: description contains {label}"
        for char, label in _FORBIDDEN.items()
        if char in row.description
    ]
    if row.type_code.strip().lower() not in _TYPE_CODES:
        problems.append(f"{name} @{row.offset}: unknown type_code {row.type_code!r}")
    if len(re.findall(grammar or _NUMBERED.pattern, row.description)) > 1:
        problems.append(
            f"{name} @{row.offset}: more than one box token in one description; the number rule has become ambiguous"
        )
    pattern = re.compile(grammar) if grammar else _NUMBERED
    recognised = {
        match.group(1) if pattern.groups else match.group(0) for match in pattern.finditer(row.description)
    } | {match.group(1) for match in _LETTERED.finditer(row.description)}
    problems.extend(_unrecognised_bracket_problems(name, row, recognised))
    return problems


def _unrecognised_bracket_problems(
    name: str,
    row: RecordDesignField,
    recognised: set[str],
) -> list[str]:
    return [
        f"{name} @{row.offset}: bracket token [{token}] is not a recognised "
        "box number on this wave's grammar; it would silently become a position range"
        for token in _IDENTIFIER_BRACKET.findall(row.description)
        if token not in recognised
    ]


def _geometry_problems(
    sheet: RecordDesignSheet,
    declared_desglose: Mapping[int, tuple[int, ...]] | None,
) -> list[str]:
    problems = []
    overlap = _same_level_overlap_problem(sheet, declared_desglose)
    if overlap is not None:
        problems.append(overlap)
    tiling = _tiling_problem(sheet, declared_desglose)
    if tiling is not None:
        problems.append(tiling)
    return problems


def _same_level_overlap_problem(
    sheet: RecordDesignSheet,
    declared_desglose: Mapping[int, tuple[int, ...]] | None,
) -> str | None:
    # Surface descendants indicate a nesting failure; excluding an undeclared
    # span would conceal the double-counting that the audit must reject.
    hoisted = {child for children in (declared_desglose or {}).values() for child in children}
    ordered = [row for row in sorted(sheet.fields, key=lambda item: item.offset) if row.offset not in hoisted]
    return _first_contained_span_problem(sheet.name.strip(), ordered)


def _first_contained_span_problem(name: str, ordered: Sequence[RecordDesignField]) -> str | None:
    for outer in ordered:
        contained = _contained_fields(outer, ordered)
        if contained:
            spans = ", ".join(f"@{item.offset}+{item.length}" for item in contained)
            return (
                f"{name}: @{outer.offset}+{outer.length} contains {spans} at the same "
                "level; these are desglose sub-rows the reader did not nest, and "
                "summing them double-counts the record"
            )
    return None


def _contained_fields(
    outer: RecordDesignField,
    ordered: Sequence[RecordDesignField],
) -> list[RecordDesignField]:
    outer_end = outer.offset + outer.length
    return [
        inner
        for inner in ordered
        if inner is not outer and inner.offset >= outer.offset and inner.offset + inner.length <= outer_end
    ]


def _tiling_problem(
    sheet: RecordDesignSheet,
    declared_desglose: Mapping[int, tuple[int, ...]] | None,
) -> str | None:
    hoisted = {child for children in (declared_desglose or {}).values() for child in children}
    ordered = [row for row in sorted(sheet.fields, key=lambda item: item.offset) if row.offset not in hoisted]
    cursor = 1
    for row in ordered:
        if row.offset != cursor:
            return f"{sheet.name.strip()}: tiling breaks at @{row.offset}, expected @{cursor}"
        cursor = row.offset + row.length
    tiled = cursor - 1
    if sheet.total_positions is not None and tiled != sheet.total_positions:
        return f"{sheet.name.strip()}: tiles {tiled} but the design declares {sheet.total_positions}"
    return None
