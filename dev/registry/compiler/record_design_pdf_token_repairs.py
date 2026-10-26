"""Focused PDF record-design repairs for fused and truncated tokens."""

from __future__ import annotations

import re
from collections.abc import Sequence

from .record_design_pdf_repairs import (
    _FUSED_ORDINAL_POSITION_RE,
    _FUSED_ROW_RE,
    _GLUED_NATURALEZA_ROW_RE,
    _STRANDED_COORDINATE_PAIR_RE,
    _continues,
    _previous_parsed_row,
)
from .record_design_pdf_rows import PdfRow, parse_pdf_row


def split_fused_ordinal_position_prefix(lines: tuple[str, ...]) -> tuple[str, ...]:
    """Split a row whose ordinal and position were emitted as a single number.

    Modelo 200's 2010 and 2011 PDF designs open several records this way::

        1 1 2 An C Inicio del identificador de modelo y pagina.
        23 3 Num C Modelo. Constante "200"
        36 3 An C Pagina. Constante "021"
        49 1 An C Fin de identificador de modelo.

    Read literally the second line is ordinal 23 at position 3, which is not a
    row anyone printed. It is ordinal 2 at position 3, and the ordinal ran into
    the position because AEAT's two narrow columns touch.

    RECONSTRUCTED FROM THE PREVIOUS ROW, NEVER GUESSED, and admitted only when
    both halves agree. The previous row fixes exactly one candidate -- its
    ordinal plus one, and the position where it ends -- and that candidate is
    accepted only if concatenating the two reproduces the fused token
    CHARACTER FOR CHARACTER. ``2`` and ``3`` give ``23``; anything else leaves
    the line alone.

    That is the same over-determination the sibling splitter uses, and it is
    what keeps this away from rows that legitimately open with a large ordinal:
    a real ``23 3 Num`` row at position 3 would follow a row ending at 3 with
    ordinal 22, and ``22`` and ``3`` do not spell ``23``.
    """
    split: list[str] = []
    previous: PdfRow | None = None
    for index, line in enumerate(lines):
        parsed = parse_pdf_row(line, index + 1)
        if parsed is not None:
            previous = parsed
            split.append(line)
            continue
        fused = _FUSED_ORDINAL_POSITION_RE.match(line)
        if fused is None or previous is None or previous.ordinal is None or not previous.ordinal.isdigit():
            split.append(line)
            continue
        ordinal = str(int(previous.ordinal) + 1)
        offset = previous.offset + previous.length
        if f"{ordinal}{offset}" != fused.group("fused"):
            split.append(line)
            continue
        rebuilt = f"{ordinal} {offset} {fused.group('length')} {fused.group('naturaleza')} {fused.group('rest')}"
        reparsed = parse_pdf_row(rebuilt, index + 1)
        if reparsed is None:
            split.append(line)
            continue
        previous = reparsed
        split.append(rebuilt)
    return tuple(split)


def split_glued_naturaleza_rows(lines: tuple[str, ...]) -> tuple[str, ...]:
    """Separate a naturaleza that ran into the following content-column marker.

    Modelo 200's 2010 design loses one row of its ``Pag. 22`` record this way::

        169 1690 7 Num C Agrup.interes economico y UTES - Modelo de info...
        170 1697 9 AnC A i t   i UTES M d l d i f i  R l i  d i 18 NIF
        171 1706 1 Num C Agrup.interes economico y UTES - Modelo de info...

    Nothing is missing: ordinal 170 at position 1697, nine bytes, naturaleza
    ``An``, content column ``A``. Only the space between ``An`` and the marker
    is gone, and without it the row does not parse and its nine positions read
    as a hole -- which costs the whole record.

    ADMITTED ON OVER-DETERMINATION and on the split parsing. The coordinates
    must continue the previous row -- ordinal one more, position resuming where
    it ended -- and the separated line must then parse as a row. A line that
    merely looks like this but sits at the wrong position is left alone.

    The description here is visibly mangled -- AEAT's own PDF drops characters
    from that cell -- and that is NOT this repair's business. Recovering the
    row's POSITION is what stops the record being skipped; the description is
    carried through exactly as extracted rather than being cleaned up, because
    inventing text is a different and worse failure than reporting it damaged.
    """
    split: list[str] = []
    previous: PdfRow | None = None
    for index, line in enumerate(lines):
        parsed = parse_pdf_row(line, index + 1)
        if parsed is not None:
            previous = parsed
            split.append(line)
            continue
        glued = _GLUED_NATURALEZA_ROW_RE.match(line)
        if glued is None or previous is None:
            split.append(line)
            continue
        if not _continues(previous, glued.group("ordinal"), int(glued.group("offset"))):
            split.append(line)
            continue
        rebuilt = (
            f"{glued.group('ordinal')} {glued.group('offset')} {glued.group('length')} "
            f"{glued.group('naturaleza')} {glued.group('marker')} {glued.group('rest')}"
        )
        reparsed = parse_pdf_row(rebuilt, index + 1)
        if reparsed is None:
            split.append(line)
            continue
        previous = reparsed
        split.append(rebuilt)
    return tuple(split)


def _truncated_offset_candidate(
    lines: tuple[str, ...],
    parsed: Sequence[PdfRow | None],
    index: int,
) -> str | None:
    """Build a corrected row when its stranded pair proves the offset."""
    pair = _STRANDED_COORDINATE_PAIR_RE.match(lines[index])
    if pair is None:
        return None
    damaged = parsed[index - 1]
    if damaged is None or damaged.ordinal is None or damaged.ordinal != pair.group("ordinal"):
        return None
    anchor = _previous_parsed_row(parsed, index - 1)
    if anchor is None:
        return None
    stated = int(pair.group("offset"))
    resumes = anchor.offset + anchor.length
    if stated != resumes or damaged.offset == resumes:
        return None
    rebuilt = re.sub(
        rf"^(\s*{re.escape(damaged.ordinal)})\s+{damaged.offset}\s",
        rf"\g<1> {stated} ",
        lines[index - 1],
        count=1,
    )
    return rebuilt if parse_pdf_row(rebuilt, index) is not None else None


def repair_truncated_offset_rows(lines: tuple[str, ...]) -> tuple[str, ...]:
    """Restore a row whose position lost a digit, from the pair restating it below.

    Modelo 200's 2011 design loses one row of its ``Pag. 44`` record this way::

        17 198 17 N  Inst. inversion colectiva - Cuenta perdidas y ganancias ...
        18 21 17 N   Inst. inversion colectiva - Cuenta perdidas y ganancias ...
        18 215
        19 232 17 N  Inst. inversion colectiva - Cuenta perdidas y ganancias ...

    The middle row PARSES, which is what makes this dangerous: it reads as
    ordinal 18 at position 21, seventeen bytes, and nothing downstream doubts
    it. Position 215 is then a hole and the record is skipped, while the row
    quietly claims bytes 21-37 that belong to other fields.

    The truncation is visible only against the neighbours, and they settle it
    three ways at once. The stranded pair must repeat the parsed row's OWN
    ordinal; the position it states must resume exactly where the row above
    ends; and the position the row currently claims must NOT. All three, or the
    line is left alone -- the third is what stops this touching a healthy row
    that merely happens to sit above a stray pair.

    Distinct from :func:`recover_coordinate_stutter_rows`, which handles the
    same restatement when the stutter line also carries the casilla tag and the
    damaged half does not parse at all. Here the line is bare and the damaged
    half parses wrongly, so neither of that function's halves matches.
    """
    parsed = list(parse_pdf_row(line, index + 1) for index, line in enumerate(lines))

    repaired: dict[int, str] = {}
    dropped: set[int] = set()
    for index in range(1, len(lines)):
        rebuilt = _truncated_offset_candidate(lines, parsed, index)
        if rebuilt is None:
            continue
        repaired[index - 1] = rebuilt
        parsed[index - 1] = parse_pdf_row(rebuilt, index)
        dropped.add(index)

    if not repaired:
        return lines
    return tuple(repaired.get(index, line) for index, line in enumerate(lines) if index not in dropped)


def split_fused_ordinal_offset_rows(lines: tuple[str, ...]) -> tuple[str, ...]:
    """Separate a row whose first two columns were emitted without a space.

    Modelo 100's 2012, 2013 and 2014 editions each lose exactly one position --
    9 -- and always the same row: the ``Indicador de pagina complementaria``
    flag arrives as ``59 1A ...`` where AEAT prints ``5 9 1 A ...``. Both the
    ordinal/offset pair and the length/naturaleza pair are fused, so no
    column-shaped pattern matches and the row is refused.

    Splitting ``59`` needs no guesswork, and that is what makes this safe: the
    previous row already fixes both values. The ordinal must follow by one and
    the offset must resume where that row ended, so the split is accepted ONLY
    when concatenating those two expected numbers reproduces the fused token
    exactly. ``5`` and ``9`` give ``59``; any other reading of that token, and
    any line whose neighbours do not agree, is left alone.
    """
    split: list[str] = []
    previous: PdfRow | None = None
    for index, line in enumerate(lines):
        parsed = parse_pdf_row(line, index + 1)
        if parsed is not None:
            previous = parsed
            split.append(line)
            continue
        fused = _FUSED_ROW_RE.match(line)
        if fused is not None and previous is not None and previous.ordinal is not None and previous.ordinal.isdigit():
            ordinal = int(previous.ordinal) + 1
            offset = previous.offset + previous.length
            if fused.group(1) == f"{ordinal}{offset}":
                rebuilt = f"{ordinal} {offset} {fused.group(2)} {fused.group(3)} {fused.group(4)}"
                candidate = parse_pdf_row(rebuilt, index + 1)
                if candidate is not None:
                    previous = candidate
                    split.append(rebuilt)
                    continue
        split.append(line)
    return tuple(split)
