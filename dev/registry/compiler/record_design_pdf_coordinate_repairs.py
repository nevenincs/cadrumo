"""Focused PDF record-design repairs for coordinate anomalies."""

from __future__ import annotations

import re

from .record_design_pdf_repairs import (
    _ANY_CASILLA_TAG_RE,
    _BARE_COORDINATE_LOOKAHEAD,
    _BARE_COORDINATE_LOOKBEHIND,
    _BARE_COORDINATE_TRIPLE_RE,
    _COORDINATE_STUTTER_RE,
    _DOUBLED_COORDINATE_ROW_RE,
    _NATURALEZA_HEAD_RE,
    _ORPHAN_MEASURE_RE,
    _STUTTERED_PDF_ROW_RE,
    _continues,
    _previous_parsed_row,
)
from .record_design_pdf_rows import PdfRow, parse_pdf_row


def collapse_stuttered_row_prefix(lines: tuple[str, ...]) -> tuple[str, ...]:
    """Drop a row's duplicated ordinal-and-position prefix.

    Modelo 200's 2010 and 2011 editions emit nine rows this way, and every one
    of their positions is currently reported as a hole, so the duplication is
    not cosmetic -- it costs the record the field.

    Deliberately narrow to the SELF-EVIDENCING case. A row may also arrive with
    genuine leading text, where the tail of a wrapped description spills onto
    its line, and those cannot be admitted on the line's own evidence: measured
    across the bundled corpus, lines of that shape include both real rows and
    prose carrying number sequences, and nothing in the line distinguishes them.
    A back-reference to the same two numbers has no such ambiguity.
    """
    return tuple(
        f"{match.group('indent')}{match.group('ordinal')} {match.group('offset')} {match.group('rest')}"
        if (match := _STUTTERED_PDF_ROW_RE.match(line)) is not None
        else line
        for line in lines
    )


def _coordinate_stutter_donor(
    lines: tuple[str, ...],
    parsed: tuple[PdfRow | None, ...],
    donor_index: int,
    anchor: PdfRow | None,
) -> tuple[str, str, str] | None:
    """Return the donor's length, naturaleza, and description when usable."""
    donor = parsed[donor_index]
    if donor is None:
        measure = _ORPHAN_MEASURE_RE.match(lines[donor_index])
        if measure is None:
            return None
        return (
            str(measure.group("length")),
            str(measure.group("naturaleza")),
            str(measure.group("description")),
        )
    if _continues(anchor, donor.ordinal or "", donor.offset):
        return None
    return str(donor.length), donor.type_code, donor.description


def _coordinate_stutter_candidate(
    lines: tuple[str, ...],
    parsed: tuple[PdfRow | None, ...],
    index: int,
    rebuilt: dict[int, str],
    dropped: set[int],
) -> tuple[int, str] | None:
    """Build a coordinate-stutter row only when both halves are evidenced."""
    stutter = _COORDINATE_STUTTER_RE.match(lines[index])
    if stutter is None or not _ANY_CASILLA_TAG_RE.search(lines[index]):
        return None
    donor_index = index - 1
    if donor_index in dropped or donor_index in rebuilt:
        return None
    anchor = _previous_parsed_row(parsed, donor_index)
    donor = _coordinate_stutter_donor(lines, parsed, donor_index, anchor)
    if donor is None:
        return None
    ordinal = stutter.group("ordinal")
    offset = int(stutter.group("offset"))
    if not _continues(anchor, ordinal, offset):
        return None
    length, naturaleza, description = donor
    return donor_index, f"{ordinal} {offset} {length} {naturaleza} {description} {stutter.group('rest')}"


def recover_coordinate_stutter_rows(lines: tuple[str, ...]) -> tuple[str, ...]:
    """Rebuild a row whose coordinate column was damaged, from the stutter restating it.

    Modelo 200's 2010 and 2011 editions lose the coordinate column on some rows
    and then restate it. The damage takes two forms: the coordinates vanish
    entirely, leaving ``17 N <description>``; or they survive mangled, so
    ``54 827`` arrives as ``4 82`` and parses as a real but WRONG row at
    ordinal 4, position 82. Either way a following line states the true pair.

    Both halves are required, and that is the whole guard. The coordinates are
    admitted only when they are OVER-DETERMINED against the last undamaged row
    -- the ordinal must follow by one AND the position must resume where that
    row ended, the same two independent facts :func:`_continues` checks
    everywhere else. The length and naturaleza are never inferred: they must be
    stated by the donor half. Where no donor exists the site is left alone,
    which is why this declines the three sites in these same two editions that
    state coordinates and a casilla tag but nothing else -- recovering those
    would mean inventing a naturaleza and truncating a description.
    """
    parsed = tuple(parse_pdf_row(line, index + 1) for index, line in enumerate(lines))

    rebuilt: dict[int, str] = {}
    dropped: set[int] = set()
    for index, _line in enumerate(lines):
        if parsed[index] is not None or index == 0:
            continue
        candidate = _coordinate_stutter_candidate(lines, parsed, index, rebuilt, dropped)
        if candidate is None:
            continue
        donor_index, repaired = candidate
        rebuilt[donor_index] = repaired
        dropped.add(index)

    if not rebuilt:
        return lines
    return tuple(rebuilt.get(index, line) for index, line in enumerate(lines) if index not in dropped)


def _bare_coordinate_naturaleza_half(
    lines: tuple[str, ...],
    parsed: tuple[PdfRow | None, ...],
    index: int,
) -> tuple[re.Match[str], int] | None:
    """Locate the naturaleza half, below first and then above a bare triple."""
    head_index = index + 1
    head = _NATURALEZA_HEAD_RE.match(lines[head_index])
    if head is not None:
        return head, head_index
    for candidate in range(index - 1, max(-1, index - 1 - _BARE_COORDINATE_LOOKBEHIND), -1):
        if parsed[candidate] is not None:
            break
        found = _NATURALEZA_HEAD_RE.match(lines[candidate])
        if found is not None:
            return found, candidate
    return None


def _bare_coordinate_successor(
    parsed: tuple[PdfRow | None, ...],
    index: int,
    line_count: int,
) -> tuple[int, PdfRow] | None:
    """Find the first parsed row after a bare triple within the bounded window."""
    for candidate in range(index + 2, min(index + 2 + _BARE_COORDINATE_LOOKAHEAD, line_count)):
        successor = parsed[candidate]
        if successor is not None:
            return candidate, successor
    return None


def _bare_coordinate_triple(
    lines: tuple[str, ...],
    parsed: tuple[PdfRow | None, ...],
    index: int,
) -> re.Match[str] | None:
    """Return a bare triple only when the following line is not a row."""
    triple = _BARE_COORDINATE_TRIPLE_RE.match(lines[index])
    if triple is None:
        return None
    if parsed[index + 1] is not None:
        return None
    return triple


def _bare_coordinate_continues(triple: re.Match[str], successor: PdfRow) -> bool:
    """Whether a successor agrees with both coordinates stated by a triple."""
    ordinal = triple.group("ordinal")
    offset = int(triple.group("offset"))
    length = int(triple.group("length"))
    return successor.ordinal == str(int(ordinal) + 1) and successor.offset == offset + length


def _bare_coordinate_middle(
    lines: tuple[str, ...],
    start: int,
    successor_index: int,
    triple_index: int,
    head_index: int,
) -> str:
    """Fold wrapped content between the two halves into the rebuilt row."""
    return " ".join(
        lines[position].strip()
        for position in range(start, successor_index)
        if position not in {triple_index, head_index}
    )


def _bare_coordinate_candidate(
    lines: tuple[str, ...],
    parsed: tuple[PdfRow | None, ...],
    index: int,
) -> tuple[int, str, tuple[int, ...]] | None:
    """Build a bare-coordinate row when its successor over-determines it."""
    triple = _bare_coordinate_triple(lines, parsed, index)
    if triple is None:
        return None
    half = _bare_coordinate_naturaleza_half(lines, parsed, index)
    if half is None:
        return None
    head, head_index = half
    successor_data = _bare_coordinate_successor(parsed, index, len(lines))
    if successor_data is None:
        return None
    successor_index, successor = successor_data
    if not _bare_coordinate_continues(triple, successor):
        return None
    ordinal = triple.group("ordinal")
    offset = int(triple.group("offset"))
    length = int(triple.group("length"))
    start = min(index, head_index)
    middle = _bare_coordinate_middle(
        lines,
        start,
        successor_index,
        index,
        head_index,
    )
    replacement = f"{ordinal} {offset} {length} {head.group('naturaleza')} {head.group('rest')} {middle}".rstrip()
    consumed = tuple(position for position in range(start, successor_index) if position != start)
    return start, replacement, consumed


def rejoin_bare_coordinate_rows(lines: tuple[str, ...]) -> tuple[str, ...]:
    """Rebuild a row split between a bare coordinate line and its naturaleza half.

    Modelo 200's ``17-200-orden-eha-1338-2010`` design emits the ``Indicador de
    pagina complementaria`` row of its Pag. 21 and Pag. 22 records this way::

        5 10 1
        An C Indicador de pagina complementaria.
        Blanco (No
        complementaria) o
        "C" (Complementaria)
        6 11 1 A C Operaciones fusion, escision, canje valores - ...

    Position 10 is then the ONLY hole on either record, and a record read with a
    hole is skipped whole, so two sheets are lost to one split row.

    ANCHORED ON THE SUCCESSOR, NOT THE PREDECESSOR, and that is forced rather
    than chosen. On these pages the rows above -- ordinals 2, 3 and 4 -- are
    emitted with their ordinal and position FUSED (``23 3 Num``, ``36 3 An``)
    and are not recovered until record assembly, so at line-repair time the
    nearest parsed row above is ordinal 1 and a backward check can never be
    satisfied. The row BELOW is intact.

    The over-determination is the same strength either way: the successor's
    ordinal must be one more than the rebuilt row's AND its position must resume
    exactly where the rebuilt row ends. Two independent facts, from a row read
    without help, that must agree.

    The intervening lines are the wrapped ``Contenido`` cell and are folded into
    the description rather than dropped, so nothing AEAT printed is discarded.
    """
    parsed = tuple(parse_pdf_row(line, index + 1) for index, line in enumerate(lines))

    rebuilt: dict[int, str] = {}
    consumed: set[int] = set()
    for index, _line in enumerate(lines):
        if parsed[index] is not None or index + 1 >= len(lines):
            continue
        candidate = _bare_coordinate_candidate(lines, parsed, index)
        if candidate is None:
            continue
        start, replacement, positions = candidate
        rebuilt[start] = replacement
        consumed.update(positions)

    if not rebuilt:
        return lines
    return tuple(rebuilt.get(index, line) for index, line in enumerate(lines) if index not in consumed)


def collapse_doubled_coordinate_rows(lines: tuple[str, ...]) -> tuple[str, ...]:
    """Collapse a row whose position and length were printed twice.

    Modelo 200's 2010 edition emits some rows with the coordinate pair repeated
    and the naturaleza run into the description's stray column marker, which
    matches no column shape and is refused -- leaving a hole the width of the
    row it lost.

    Two independent confirmations are required, and the first is what makes this
    safe: the repeat must be EXACT, matched by backreference rather than by
    re-reading two numbers that merely look similar, so the source itself states
    the coordinate twice. The row must then also continue the previous one --
    ordinal by one, offset resuming where it ended -- so a doubled pair that
    lands in the wrong place is still refused.

    The naturaleza is separated on its own evidence: it is a closed set, so a
    token beginning with one of its members and continuing into text can only be
    that member followed by description. No position is inferred anywhere; every
    number written out here was read from the line.
    """
    collapsed: list[str] = []
    previous: PdfRow | None = None
    for index, line in enumerate(lines):
        parsed = parse_pdf_row(line, index + 1)
        if parsed is not None:
            previous = parsed
            collapsed.append(line)
            continue
        doubled = _DOUBLED_COORDINATE_ROW_RE.match(line)
        if (
            doubled is not None
            and previous is not None
            and previous.ordinal is not None
            and previous.ordinal.isdigit()
            and _continues(previous, doubled.group("ordinal"), int(doubled.group("offset")))
        ):
            rebuilt = (
                f"{doubled.group('ordinal')} {doubled.group('offset')} {doubled.group('length')} "
                f"{doubled.group('naturaleza')} {doubled.group('rest').strip()}"
            )
            candidate = parse_pdf_row(rebuilt, index + 1)
            if candidate is not None:
                previous = candidate
                collapsed.append(rebuilt)
                continue
        collapsed.append(line)
    return tuple(collapsed)
