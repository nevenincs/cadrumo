"""Focused PDF record-design repairs for wrapped fragments."""

from __future__ import annotations

from .record_design_pdf_repairs import (
    _BARE_COMPACT_PDF_ROW_RE,
    _REVERSED_ROW_HEAD_RE,
    _REVERSED_ROW_HEAD_WITH_TAIL_RE,
    _STRANDED_CASILLA_TAG_RE,
    _TRAILING_CASILLA_TAG_RE,
    REVERSED_ROW_TAIL_RE,
    _continues,
)
from .record_design_pdf_rows import (
    PdfRow,
    clean_pdf_line,
    parse_pdf_row,
    pdf_candidate_record_name,
    pdf_page_name,
    pdf_record_heading_name,
)


def _field_shaped_pdf_line(line: str, row_number: int) -> bool:
    """Whether a line can carry a casilla tag as a field or split-row half."""
    return (
        parse_pdf_row(line, row_number) is not None
        or REVERSED_ROW_TAIL_RE.match(line) is not None
        or _REVERSED_ROW_HEAD_RE.match(line) is not None
    )


def _can_reattach_casilla_tag(previous: str, row_number: int) -> bool:
    """Guard a stranded tag from headings, prose, and already-closed rows."""
    if not previous.strip() or _TRAILING_CASILLA_TAG_RE.search(previous) is not None:
        return False
    cleaned = clean_pdf_line(previous)
    if (
        pdf_page_name(cleaned) is not None
        or pdf_record_heading_name(cleaned) is not None
        or pdf_candidate_record_name(cleaned) is not None
    ):
        return False
    return _field_shaped_pdf_line(previous, row_number)


def reattach_stranded_casilla_tags(lines: tuple[str, ...]) -> tuple[str, ...]:
    """Fold a casilla reference emitted alone back onto the row it terminates.

    Residue of the same wrapping the neighbouring repairs address, in two
    shapes. Modelo 200's 2010 editions split a row across its columns and then
    put the casilla on a THIRD line -- ``102 1529`` / ``17 Num Deducciones ...
    aplic`` / ``[121]`` -- while its 2011-2012 editions keep the row intact and
    strand only the tag: ``15 164 17 N Balance: ... Acciones y partic`` /
    ``[194]``. Modelo 390's 2015 edition strands one the same way. In every
    shape the tag sits immediately after the description it closes, because
    extraction emits in reading order and the tag is that description's tail.

    Nothing downstream recovers it. :func:`join_wrapped_row_descriptions`
    absorbs a following line only into a row that has NO description, which
    neither shape is, and :data:`_REVERSED_ROW_HEAD_RE` admits a casilla only
    where it rides on the head half. So the tag is simply lost, and a position
    that loses its tag contributes no casilla number to coverage -- the quiet
    half of the damage found on modelo 390's ``@115``.

    The tag is folded onto the PRECEDING line, never a following one, and only
    where that line is itself field-shaped: a row, or one of the two halves of a
    split row. A heading carries a record boundary and prose carries nothing, so
    a tag next to either is left stranded and reported rather than attached to
    bytes AEAT did not put it on -- which is the failure this repair could
    otherwise cause, and the one a tiling mis-attribution proved can pass
    quietly.
    """
    folded: list[str] = []
    for line in lines:
        if folded and _STRANDED_CASILLA_TAG_RE.match(line):
            previous = folded[-1]
            if _can_reattach_casilla_tag(previous, len(folded)):
                folded[-1] = f"{previous.rstrip()} {line.strip()}"
                continue
        folded.append(line)
    return tuple(folded)


def _tail_fragment_candidate(
    line: str,
    following: str,
    previous: PdfRow | None,
) -> tuple[str, str] | None:
    """Split a leading fragment when the following tail continues ``previous``."""
    if previous is None or previous.ordinal is None or not previous.ordinal.isdigit():
        return None
    if REVERSED_ROW_TAIL_RE.match(line) is not None:
        return None
    head = _REVERSED_ROW_HEAD_RE.match(following) or _REVERSED_ROW_HEAD_WITH_TAIL_RE.match(following)
    if head is None or not _continues(previous, head.group("ordinal"), int(head.group("offset"))):
        return None
    tokens = line.split()
    for cut in range(1, len(tokens)):
        suffix = " ".join(tokens[cut:])
        if REVERSED_ROW_TAIL_RE.match(suffix) is not None:
            return " ".join(tokens[:cut]), suffix
    return None


def split_tail_from_leading_fragment(lines: tuple[str, ...]) -> tuple[str, ...]:
    """Separate a reversed-column TAIL from the previous row's trailing fragment.

    Modelo 200's 2010 edition prints two consecutive RIC rows whose descriptions
    differ only by a footnote marker, and the extraction runs the first row's
    trailing ``(1) [020]`` into the second row's tail::

        '78 1219 17 Num Reg.reserva ... Inv.anticipadas futuras dotaciones R'
        '(1) [020] 17 Num Reg.reserva ... Inv.anticipadas futuras dotaciones'
        '79 1236 (2 a 6) [021]'

    The middle line is row 79's length, naturaleza and description; the last is
    its ordinal and position. :func:`rejoin_reversed_column_rows` pairs a tail
    with an adjacent head, but that tail cannot match
    :data:`REVERSED_ROW_TAIL_RE` while a footnote and a casilla tag sit in
    front of it, so the pair is never formed and position 1236 is lost.

    Two independent facts are required before splitting, neither read off the
    line being changed. The SUFFIX must be a well-formed tail, and the FOLLOWING
    line must be a head whose ordinal follows the last row read by one and whose
    offset resumes exactly where that row ended. A fragment that happens to
    precede tail-shaped text, with no head continuing the sequence after it, is
    left alone.

    The fragment is emitted as its own line rather than dropped: it is the
    previous row's own content, and discarding text to make a row appear is the
    defect this repair exists to undo, inverted.
    """
    split: list[str] = []
    previous: PdfRow | None = None
    for index, line in enumerate(lines):
        parsed = parse_pdf_row(line, index + 1)
        if parsed is not None:
            previous = parsed
            split.append(line)
            continue
        candidate = _tail_fragment_candidate(line, lines[index + 1], previous) if index + 1 < len(lines) else None
        if candidate is None:
            split.append(line)
            continue
        fragment, tail = candidate
        split.append(fragment)
        split.append(tail)
    return tuple(split)


def split_row_from_wrapped_content(lines: tuple[str, ...]) -> tuple[str, ...]:
    """Separate a row from a preceding fragment of the previous cell's content.

    AEAT's ``Contenido`` column wraps, and its last fragment can be emitted on
    the same line as the NEXT row. Modelo 131's 2009 design does exactly that:
    the payment-form codes wrap over three lines and the third arrives as
    ``Domiciliacion 48 465 1 Num Ingreso (4) - Forma de pago``. The line does
    not begin with its ordinal, so the row is refused and position 465 is the
    record's only hole.

    Splitting on appearance alone would fabricate rows out of prose, so the
    suffix must satisfy the same OVER-DETERMINATION the reversed-column repair
    relies on: it parses as a row AND its ordinal follows the previous row's by
    one AND its offset resumes exactly where that row ended. Two independent
    facts from an already-read row must both agree, which prose beginning with
    two numbers cannot do by accident.

    The stripped fragment is emitted as its own line rather than discarded. It
    is content, the parser already ignores standalone content lines, and
    dropping text to make a row appear would be the same defect in reverse.
    """
    split: list[str] = []
    previous: PdfRow | None = None
    for index, line in enumerate(lines):
        parsed = parse_pdf_row(line, index + 1)
        if parsed is not None:
            previous = parsed
            split.append(line)
            continue
        recovered = False
        if previous is not None:
            tokens = line.split()
            for cut in range(1, len(tokens)):
                suffix = " ".join(tokens[cut:])
                candidate = parse_pdf_row(suffix, index + 1)
                if candidate is None or candidate.ordinal is None:
                    continue
                if _continues(previous, candidate.ordinal, candidate.offset):
                    split.append(" ".join(tokens[:cut]))
                    split.append(suffix)
                    previous = candidate
                    recovered = True
                    break
        if not recovered:
            split.append(line)
    return tuple(split)


def join_wrapped_row_descriptions(lines: tuple[str, ...]) -> tuple[str, ...]:
    """Reattach a description AEAT wrapped onto the line after its row.

    Done as a pre-pass rather than by loosening the row pattern, and the
    difference is not cosmetic. Admitting a description-less row creates a field
    that may never receive one -- the continuation handler only fills the field
    still under construction, so anything that intervenes leaves it empty and a
    later validator refuses the whole design. Three modelo 200 editions failed
    exactly that way when the pattern was loosened. Joining first means every
    row still reaches the parser complete, and no invariant downstream changes.

    The line consumed must not itself look like a row, a page heading or a
    record heading: those carry their own meaning and absorbing one would lose a
    field or a record boundary. A row whose next line offers nothing usable is
    left exactly as it was, to be reported as the hole it is.
    """
    joined: list[str] = []
    absorbed = False
    for index, line in enumerate(lines):
        if absorbed:
            absorbed = False
            continue
        if _BARE_COMPACT_PDF_ROW_RE.match(line) and index + 1 < len(lines):
            candidate = lines[index + 1]
            cleaned = clean_pdf_line(candidate)
            if (
                candidate.strip()
                and parse_pdf_row(candidate, index + 2) is None
                and pdf_page_name(cleaned) is None
                and pdf_record_heading_name(cleaned) is None
                and pdf_candidate_record_name(cleaned) is None
            ):
                joined.append(f"{line.rstrip()} {candidate.strip()}")
                absorbed = True
                continue
        joined.append(line)
    return tuple(joined)
