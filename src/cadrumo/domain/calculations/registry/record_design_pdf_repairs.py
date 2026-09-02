"""Repair PDF record-design text-layer row corruption."""

from __future__ import annotations

import re

from .record_design_pdf_rows import (
    PdfRow,
    clean_pdf_line,
    parse_pdf_row,
    pdf_candidate_record_name,
    pdf_page_name,
    pdf_record_heading_name,
)

REVERSED_ROW_TAIL_RE = re.compile(
    r"^\s*(?P<length>\d+)\s+(?P<type>An|Num|Tit|N|A)\.?\s+(?P<description>\S.*)$",
    re.IGNORECASE,
)
_REVERSED_ROW_HEAD_RE = re.compile(
    r"^\s*(?P<ordinal>\d+)\s+(?P<offset>\d+)\s*(?P<tail>\[[^\]]*\]\s*)?$",
)


#: A head half carrying description text after its position: ``79 1236 (2 a 6)
#: [021]``. Admitted only under the continuity constraint below, never on the
#: pattern alone -- prose beginning with two numbers is common.
_REVERSED_ROW_HEAD_WITH_TAIL_RE = re.compile(
    r"^\s*(?P<ordinal>\d+)\s+(?P<offset>\d+)\s+(?P<trailing>\S.*)$",
)


def _continues(previous: PdfRow | None, ordinal: str, offset: int) -> bool:
    """Whether this ordinal and position resume exactly where ``previous`` ended.

    The same over-determination the glued-ordinal split relies on: the ordinal
    must follow by one AND the position must resume at the previous row's end.
    Two independent facts, from a row already read, that must agree -- which is
    what lets a head half be admitted when description text has bled onto its
    line and the pattern alone would match prose.
    """
    if previous is None or previous.ordinal is None or not previous.ordinal.isdigit():
        return False
    return ordinal == str(int(previous.ordinal) + 1) and offset == previous.offset + previous.length


def _row_identities_by_record(lines: tuple[str, ...]) -> list[frozenset[tuple[str, int]]]:
    """For each line, the row identities its OWN record already states intact.

    Scoped per record, and that scoping is the whole point. The duplicate guard
    exists to stop a split row being joined when the design also emits it whole,
    which is a statement about one record -- but every record restarts at
    ordinal 1 position 1, so low identities recur throughout a design. Measured
    on modelo 200's 2010 edition, ``(30, 419)`` is stated intact by 28 different
    records and ``(7, 28)`` by 34. A design-wide guard therefore refused almost
    every legitimate join, and did so silently, because a refused join is
    indistinguishable from no join at all.

    Record boundaries come from the same geometry the parser uses: a row
    declaring position 1 begins a record, because a fixed-width record is
    contiguous from its first byte.
    """
    boundaries: list[int] = []
    identities: list[set[tuple[str, int]]] = []
    current: set[tuple[str, int]] = set()
    for number, line in enumerate(lines, start=1):
        parsed = parse_pdf_row(line, number)
        if parsed is not None and parsed.offset == 1 and current:
            identities.append(current)
            boundaries.append(number - 1)
            current = set()
        if parsed is not None and parsed.ordinal is not None:
            current.add((parsed.ordinal, parsed.offset))
    identities.append(current)

    frozen = [frozenset(entry) for entry in identities]
    per_line: list[frozenset[tuple[str, int]]] = []
    segment = 0
    for index in range(len(lines)):
        while segment < len(boundaries) and index >= boundaries[segment]:
            segment += 1
        per_line.append(frozen[segment])
    return per_line


def undouble_struck_rows(lines: tuple[str, ...]) -> tuple[str, ...]:
    """Repair a row whose glyphs the PDF text layer emitted twice.

    Modelo 390's 2015 edition double-strikes some rows: ``4422 662255 1177 NN
    55.. OOppeerraacciioonneess`` is ``42 625 17 N 5. Operaciones``, every
    character duplicated while the separating spaces stay single. Eight rows
    arrive that way and each one is a position the record otherwise reports as
    dropped.

    The repair is self-verifying, which is what keeps it from being a guess: a
    line is rewritten ONLY when it does not parse as a row, every token it is
    built from is an exact pairwise repetition, and the de-doubled result does
    parse. A line failing any of the three is returned untouched. Nothing here
    reasons about what the row ought to say -- the doubling either undoes
    cleanly into a row or it does not.

    Tokens that are not doubled are left alone rather than making the whole line
    ineligible, because AEAT's own text mixes them: a description can carry a
    single-struck fragment beside doubled ones.
    """
    repaired: list[str] = []
    for number, line in enumerate(lines, start=1):
        if parse_pdf_row(line, number) is not None:
            repaired.append(line)
            continue
        candidate = " ".join(
            token[::2]
            if len(token) >= 2
            and len(token) % 2 == 0
            and all(token[i] == token[i + 1] for i in range(0, len(token), 2))
            else token
            for token in line.split(" ")
        )
        repaired.append(candidate if candidate != line and parse_pdf_row(candidate, number) is not None else line)
    return tuple(repaired)


def rejoin_reversed_column_rows(lines: tuple[str, ...]) -> tuple[str, ...]:
    """Reassemble a row whose PDF columns were emitted in the wrong order.

    Modelo 200's older editions emit some rows as two lines with the columns
    swapped -- ``17 Num Ret. e ingr. a cuenta ... `` followed by ``30 419
    [596]`` -- where AEAT's row is ``30 419 17 Num Ret. e ingr. a cuenta ...
    [596]``. Every one of those positions is otherwise unread, and they are the
    bulk of modelo 200's reported damage: 592 such pairs across six editions.

    Neither half is a row on its own, and that is the evidence. The first line
    has a length and a naturaleza but declares no position, so it can state
    nothing about the record's extent; the second names an ordinal and a
    position but no width. Only together do they make a field, and each supplies
    exactly the columns the other lacks -- nothing here is inferred from
    neighbouring rows or from a sequence.

    A wrong pairing cannot pass quietly: it would place a field at a position
    some other row already covers, and :func:`contiguity_failure` refuses
    partial overlap and any extent past the declared total. The join is
    therefore checked by the same arithmetic that reports the holes it closes.
    """
    # A design may emit the SAME row both split and intact. Joining the split
    # copy would then declare a position the intact row already declares --
    # harmless to contiguity, which permits containment, and therefore silent:
    # modelo 200's 2012-2014 editions each gained twelve duplicate importe
    # fields that way, in records that had no holes at all. So the intact rows
    # are collected first and a pair claiming one of their (ordinal, position)
    # identities is left alone.
    claimed = _row_identities_by_record(lines)
    joined: list[str] = []
    index = 0
    previous_row: PdfRow | None = None
    while index < len(lines):
        line = lines[index]
        parsed_here = parse_pdf_row(line, index + 1)
        if parsed_here is not None:
            previous_row = parsed_here
        if index + 1 < len(lines):
            # The two halves arrive in either order. Swapped -- length, type and
            # description first -- is how modelo 200's 2010 editions emit some
            # rows; in natural order the row simply breaks after its position,
            # leaving ``7 28`` above ``17 Num Deducc...``. Both are one row split
            # over two lines, and neither half is a row alone, so the same
            # evidence and the same duplicate guard apply to each.
            forward_head = _REVERSED_ROW_HEAD_RE.match(line)
            forward_tail = REVERSED_ROW_TAIL_RE.match(lines[index + 1])
            if (
                forward_head is not None
                and forward_tail is not None
                and parse_pdf_row(line, index + 1) is None
                and parse_pdf_row(lines[index + 1], index + 2) is None
                and (forward_head.group("ordinal"), int(forward_head.group("offset"))) not in claimed[index]
            ):
                casilla = (forward_head.group("tail") or "").strip()
                description = forward_tail.group("description").rstrip()
                joined.append(
                    f"{forward_head.group('ordinal')} {forward_head.group('offset')} "
                    f"{forward_tail.group('length')} {forward_tail.group('type')} "
                    f"{description}{' ' + casilla if casilla else ''}",
                )
                index += 2
                continue
            # The head may carry description text bled onto its line. That
            # pattern alone matches prose, so it is admitted only when the
            # ordinal and position resume exactly where the last read row ended.
            tail = REVERSED_ROW_TAIL_RE.match(line)
            bled = _REVERSED_ROW_HEAD_WITH_TAIL_RE.match(lines[index + 1])
            if (
                tail is not None
                and bled is not None
                and _REVERSED_ROW_HEAD_RE.match(lines[index + 1]) is None
                and parse_pdf_row(line, index + 1) is None
                and parse_pdf_row(lines[index + 1], index + 2) is None
                and _continues(previous_row, bled.group("ordinal"), int(bled.group("offset")))
                and (bled.group("ordinal"), int(bled.group("offset"))) not in claimed[index]
            ):
                joined.append(
                    f"{bled.group('ordinal')} {bled.group('offset')} "
                    f"{tail.group('length')} {tail.group('type')} "
                    f"{tail.group('description').rstrip()} {bled.group('trailing').strip()}",
                )
                index += 2
                continue
            head = _REVERSED_ROW_HEAD_RE.match(lines[index + 1])
            if (
                tail is not None
                and head is not None
                and parse_pdf_row(line, index + 1) is None
                and parse_pdf_row(lines[index + 1], index + 2) is None
                and (head.group("ordinal"), int(head.group("offset"))) not in claimed[index]
            ):
                casilla = (head.group("tail") or "").strip()
                description = tail.group("description").rstrip()
                joined.append(
                    f"{head.group('ordinal')} {head.group('offset')} "
                    f"{tail.group('length')} {tail.group('type')} "
                    f"{description}{' ' + casilla if casilla else ''}",
                )
                index += 2
                continue
        joined.append(line)
        index += 1
    return tuple(joined)


#: A row whose ordinal and position are emitted twice before the rest of the
#: row: ``99 1592 99 1592 17 Num ...``. The repeat is the evidence -- the line
#: states the same two numbers twice, so dropping the first pair asserts nothing
#: the row does not already say about itself.
_STUTTERED_PDF_ROW_RE = re.compile(
    r"^(?P<indent>\s*)(?P<ordinal>\d+)\s+(?P<offset>\d+)\s+(?P=ordinal)\s+(?P=offset)\s+(?P<rest>\d.*)$",
)


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


#: The TRUE ordinal and position of a damaged row, restated on a line of its
#: own: ``54 827 Ajustes por valoracion [380]``. The line is not itself a row --
#: it carries no length and no naturaleza -- so it can only be read together
#: with the half that does.
_COORDINATE_STUTTER_RE = re.compile(
    r"^\s*(?P<ordinal>\d+)\s+(?P<offset>\d+)\s+(?P<rest>\S.*)$",
)

#: The other half: length, naturaleza and description with no coordinates at
#: all, which is what a row whose coordinate column was lost leaves behind.
_ORPHAN_MEASURE_RE = re.compile(
    r"^\s*(?P<length>\d+)\s+(?P<naturaleza>An|Num|N|A)\.?\s+(?P<description>\S.*)$",
    re.IGNORECASE,
)

#: A casilla reference anywhere in a line.
_ANY_CASILLA_TAG_RE = re.compile(r"\[\d+\]")


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

    def _anchor(before: int) -> PdfRow | None:
        for index in range(before - 1, -1, -1):
            if parsed[index] is not None:
                return parsed[index]
        return None

    rebuilt: dict[int, str] = {}
    dropped: set[int] = set()
    for index, line in enumerate(lines):
        if parsed[index] is not None or index == 0:
            continue
        stutter = _COORDINATE_STUTTER_RE.match(line)
        if stutter is None or not _ANY_CASILLA_TAG_RE.search(line):
            continue
        donor_index = index - 1
        if donor_index in dropped or donor_index in rebuilt:
            continue
        anchor = _anchor(donor_index)
        donor_row = parsed[donor_index]
        if donor_row is None:
            measure = _ORPHAN_MEASURE_RE.match(lines[donor_index])
            if measure is None:
                continue
            length = measure.group("length")
            naturaleza = measure.group("naturaleza")
            description = measure.group("description")
        else:
            if _continues(anchor, donor_row.ordinal or "", donor_row.offset):
                continue  # the neighbour is a healthy row, not a damaged half
            length = str(donor_row.length)
            naturaleza = donor_row.type_code
            description = donor_row.description
        ordinal = stutter.group("ordinal")
        offset = int(stutter.group("offset"))
        if not _continues(anchor, ordinal, offset):
            continue
        rebuilt[donor_index] = f"{ordinal} {offset} {length} {naturaleza} {description} {stutter.group('rest')}"
        dropped.add(index)

    if not rebuilt:
        return lines
    return tuple(rebuilt.get(index, line) for index, line in enumerate(lines) if index not in dropped)


#: A row whose three coordinate numbers were emitted ALONE on their own line,
#: with the naturaleza and description following on the next: ``5 10 1`` then
#: ``An C Indicador de pagina complementaria.``. Deliberately anchored end to
#: end, so the line must be EXACTLY ordinal, position and length and nothing
#: else -- a looser pattern that tolerated a trailing fragment was measured
#: claiming forty lines on one design where two were real.
_BARE_COORDINATE_TRIPLE_RE = re.compile(
    r"^\s*(?P<ordinal>\d+)\s+(?P<offset>\d+)\s+(?P<length>\d+)\s*$",
)

#: How far past the naturaleza half the anchoring successor row may sit. The
#: wrapped Contenido cell runs to three lines in the measured corpus.
_BARE_COORDINATE_LOOKAHEAD = 6

#: How far ABOVE a bare triple its naturaleza half may sit. Wider than the
#: lookahead because a page break drops several lines of running furniture --
#: the modelo name, the version and the two-line subtitle -- between them.
_BARE_COORDINATE_LOOKBEHIND = 12

#: The half that follows it: naturaleza then description, no numbers of its own.
_NATURALEZA_HEAD_RE = re.compile(
    r"^\s*(?P<naturaleza>An|Num|N|A)\s+(?P<rest>\D\S*.*)$",
)


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
    for index, line in enumerate(lines):
        if parsed[index] is not None or index + 1 >= len(lines):
            continue
        triple = _BARE_COORDINATE_TRIPLE_RE.match(line)
        if triple is None or parsed[index + 1] is not None:
            continue
        head = _NATURALEZA_HEAD_RE.match(lines[index + 1])
        head_index = index + 1
        if head is None:
            # The naturaleza half may sit ABOVE the triple instead, separated by
            # the wrapped Contenido cell and a page break's running furniture.
            # Modelo 200's 2010 and 2011 designs print it that way; the 2010
            # update prints it below. Same row, mirrored.
            for candidate in range(index - 1, max(-1, index - 1 - _BARE_COORDINATE_LOOKBEHIND), -1):
                if parsed[candidate] is not None:
                    break
                found = _NATURALEZA_HEAD_RE.match(lines[candidate])
                if found is not None:
                    head, head_index = found, candidate
                    break
        if head is None:
            continue
        ordinal = triple.group("ordinal")
        offset = int(triple.group("offset"))
        length = int(triple.group("length"))

        successor_index = None
        for candidate in range(index + 2, min(index + 2 + _BARE_COORDINATE_LOOKAHEAD, len(lines))):
            if parsed[candidate] is not None:
                successor_index = candidate
                break
        if successor_index is None:
            continue
        successor = parsed[successor_index]
        assert successor is not None
        if successor.ordinal != str(int(ordinal) + 1) or successor.offset != offset + length:
            continue

        start = min(index, head_index)
        middle = " ".join(
            lines[position].strip() for position in range(start, successor_index) if position not in {index, head_index}
        )
        rebuilt[start] = (
            f"{ordinal} {offset} {length} {head.group('naturaleza')} {head.group('rest')} {middle}".rstrip()
        )
        consumed.update(position for position in range(start, successor_index) if position != start)

    if not rebuilt:
        return lines
    return tuple(rebuilt.get(index, line) for index, line in enumerate(lines) if index not in consumed)


#: A row whose ORDINAL and POSITION were emitted as one token, with the length
#: and naturaleza intact behind them: ``23 3 Num C Modelo.`` for AEAT's
#: ``2 3 3 Num C Modelo.``. Distinct from :data:`_FUSED_ROW_RE`, which covers a
#: position glued to its NATURALEZA (``59 1A Num``); here the two numbers ran
#: together and nothing is glued to a letter.
_FUSED_ORDINAL_POSITION_RE = re.compile(
    r"^\s*(?P<fused>\d+)\s+(?P<length>\d+)\s+(?P<naturaleza>An|Num|N|A)\s+(?P<rest>\S.*)$",
)


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


#: A row whose NATURALEZA ran into the content-column marker that follows it:
#: ``170 1697 9 AnC ...`` for AEAT's ``170 1697 9 An C ...``. The sibling
#: :data:`_DOUBLED_COORDINATE_ROW_RE` covers the same gluing when the
#: coordinates are ALSO doubled; this covers it on its own.
_GLUED_NATURALEZA_ROW_RE = re.compile(
    r"^\s*(?P<ordinal>\d+)\s+(?P<offset>\d+)\s+(?P<length>\d+)\s+"
    r"(?P<naturaleza>An|Num|N|A)(?P<marker>[A-Z])\s+(?P<rest>\S.*)$",
)


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


#: A row's TRUE ordinal and position, restated alone on the line below it after
#: the row itself was printed with a truncated position: ``18 215`` under
#: ``18 21 17 N ...``. Anchored end to end -- two integers and nothing else --
#: because a looser pattern would claim any line opening with two numbers.
_STRANDED_COORDINATE_PAIR_RE = re.compile(
    r"^\s*(?P<ordinal>\d+)\s+(?P<offset>\d+)\s*$",
)


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
        pair = _STRANDED_COORDINATE_PAIR_RE.match(lines[index])
        if pair is None:
            continue
        damaged = parsed[index - 1]
        damaged_ordinal = damaged.ordinal if damaged is not None else None
        if damaged is None or damaged_ordinal is None or damaged_ordinal != pair.group("ordinal"):
            continue
        anchor = None
        for candidate in range(index - 2, -1, -1):
            if parsed[candidate] is not None:
                anchor = parsed[candidate]
                break
        if anchor is None:
            continue
        stated = int(pair.group("offset"))
        resumes = anchor.offset + anchor.length
        if stated != resumes or damaged.offset == resumes:
            continue
        rebuilt = re.sub(
            rf"^(\s*{re.escape(damaged_ordinal)})\s+{damaged.offset}\s",
            rf"\g<1> {stated} ",
            lines[index - 1],
            count=1,
        )
        if parse_pdf_row(rebuilt, index) is None:
            continue
        repaired[index - 1] = rebuilt
        parsed[index - 1] = parse_pdf_row(rebuilt, index)
        dropped.add(index)

    if not repaired:
        return lines
    return tuple(repaired.get(index, line) for index, line in enumerate(lines) if index not in dropped)


#: A field row whose four tokens are complete but whose DESCRIPTION wrapped onto
#: the next line. AEAT does this often enough to matter: modelo 202 writes
#: ``15 80 1 Num`` and puts "Datos adicionales (3) - Cooperativa fiscalmente
#: protegida ..." underneath.
_BARE_COMPACT_PDF_ROW_RE = re.compile(
    r"^\s*\d+\s+\d+\s+\d+\s+(?:An|Num|N|A)\s*$",
    re.IGNORECASE,
)


#: A casilla reference AEAT emitted on a line of its own, orphaned from the
#: description it terminates.
_STRANDED_CASILLA_TAG_RE = re.compile(r"^\s*\[\d+\]\s*$")

#: A bracketed casilla reference already closing a line.
_TRAILING_CASILLA_TAG_RE = re.compile(r"\[\d+\]\s*$")


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
            cleaned = clean_pdf_line(previous)
            if (
                previous.strip()
                and not _TRAILING_CASILLA_TAG_RE.search(previous)
                and pdf_page_name(cleaned) is None
                and pdf_record_heading_name(cleaned) is None
                and pdf_candidate_record_name(cleaned) is None
                and (
                    parse_pdf_row(previous, len(folded)) is not None
                    or REVERSED_ROW_TAIL_RE.match(previous) is not None
                    or _REVERSED_ROW_HEAD_RE.match(previous) is not None
                )
            ):
                folded[-1] = f"{previous.rstrip()} {line.strip()}"
                continue
        folded.append(line)
    return tuple(folded)


#: A row whose ORDINAL and OFFSET arrived fused into one token and whose LENGTH
#: and NATURALEZA arrived fused into another: ``59 1A Indicador ...`` for what
#: AEAT prints as ``5 9 1 A Indicador ...``.
_FUSED_ROW_RE = re.compile(r"^\s*(\d+)\s+(\d+)([A-Za-z][A-Za-z.]*)\s+(\S.*)$")


#: A row whose OFFSET and LENGTH were emitted twice and whose naturaleza was
#: glued to the description's opening column marker:
#: ``137 1777 15 1777 15 AnC B Participaciones ...`` for AEAT's
#: ``137 1777 15 An C B Participaciones ...``.
_DOUBLED_COORDINATE_ROW_RE = re.compile(
    r"^\s*(?P<ordinal>\d+)\s+(?P<offset>\d+)\s+(?P<length>\d+)\s+"
    r"(?P=offset)\s+(?P=length)\s+(?P<naturaleza>An|Num|Tit|N|A)(?P<rest>\S.*)$",
)


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
        recovered = False
        if (
            previous is not None
            and previous.ordinal is not None
            and previous.ordinal.isdigit()
            and index + 1 < len(lines)
            and REVERSED_ROW_TAIL_RE.match(line) is None
        ):
            head = _REVERSED_ROW_HEAD_RE.match(lines[index + 1]) or _REVERSED_ROW_HEAD_WITH_TAIL_RE.match(
                lines[index + 1],
            )
            if head is not None and _continues(previous, head.group("ordinal"), int(head.group("offset"))):
                tokens = line.split()
                for cut in range(1, len(tokens)):
                    suffix = " ".join(tokens[cut:])
                    if REVERSED_ROW_TAIL_RE.match(suffix) is not None:
                        split.append(" ".join(tokens[:cut]))
                        split.append(suffix)
                        recovered = True
                        break
        if not recovered:
            split.append(line)
    return tuple(split)


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
