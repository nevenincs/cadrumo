"""Development-only repairs for PDF record-design text-layer corruption."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from pathlib import Path

from cadrumo.core.resources.bundled_data import resolve_corpus_binary
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from dev.registry.pipeline.source_defects import SupplementalBlankRunDeclaration, supplemental_blank_run_for

from .record_design_pdf_rows import (
    PdfRow,
    parse_pdf_row,
    unnamed_position_candidate,
)


_M270_2023_SOURCE_SHA256 = "d845cc47e3b60d01128d27dddcc3cffd2cf64bd6dfb24e0cd0d0467d66f95a92"


def separate_m270_birth_country_coordinate(lines: tuple[str, ...], pdf_bytes: bytes) -> tuple[str, ...]:
    """Restore the lost space in AEAT's printed second birth-place component.

    The 2023 text layer joins ``496-497`` to ``CÓDIGO PAÍS``. The preceding
    ``461-495 CIUDAD`` and the parent's declared two-part subdivision prove
    both coordinates; this repair changes only their token boundary.
    """
    if hashlib.sha256(pdf_bytes).hexdigest() != _M270_2023_SOURCE_SHA256:
        return lines
    if (
        len(lines) < 619
        or lines[587].strip() != "461-497 Alfanumérico LUGAR DE NACIMIENTO"
        or lines[599].strip() != "Este campo se subdivide en dos:"
        or not lines[600].startswith("461-495 CIUDAD: 35 posiciones. Se")
        or not lines[604].startswith("496-497CÓDIGO PAÍS: Campo alfabético de")
        or not lines[618].startswith("498-499 Alfabético PAÍS O TERRITORIO DE RESIDENCIA")
    ):
        raise RegistryValidationError("M270 birth-place source rows no longer match pinned coordinate repair")
    repaired = list(lines)
    repaired[604] = repaired[604].replace("496-497CÓDIGO", "496-497 CÓDIGO", 1)
    child = unnamed_position_candidate(repaired[604], 605)
    if child is None or (child.offset, child.length) != (496, 2):
        raise RegistryValidationError("M270 birth-country coordinate repair did not recover its source row")
    return tuple(repaired)


def require_m349_operator_blank_run_cache_dependency(path: Path) -> None:
    """Revalidate both source pins before a memoized parser answer can return."""
    declaration = supplemental_blank_run_for("aeat-dr-349-2020-current")
    if declaration is None or path.suffix.lower() != ".pdf":
        return
    if path.name != declaration.pdf_filename and path.stat().st_size != declaration.pdf_byte_count:
        return
    if hashlib.sha256(path.read_bytes()).hexdigest() != declaration.source_sha256:
        if path.name != declaration.pdf_filename:
            return
        raise RegistryValidationError("M349 operator blank-run PDF no longer matches pinned source")
    _require_m349_boe_annex(declaration.boe_corpus_path, declaration.boe_sha256, declaration.boe_html_line)


def _require_m349_boe_annex(corpus_path: str, sha256: str, html_line: int) -> None:
    boe_path = resolve_corpus_binary(*corpus_path.split("/"))
    if boe_path is None:
        raise RegistryValidationError("M349 operator blank-run BOE Annex corpus source is missing")
    boe_bytes = boe_path.read_bytes()
    boe_lines = boe_bytes.decode("utf-8").splitlines()
    if (
        hashlib.sha256(boe_bytes).hexdigest() != sha256
        or len(boe_lines) <= html_line + 4
        or ">236-500</td>" not in boe_lines[html_line - 1]
        or "Blancos.</td>" not in boe_lines[html_line + 3]
    ):
        raise RegistryValidationError("M349 operator blank-run BOE Annex no longer matches pinned row")


def _m349_pdf_context_matches(lines: tuple[str, ...], declaration: SupplementalBlankRunDeclaration) -> bool:
    return (
        len(lines) >= 449
        and lines[225].startswith("TIPO DE REGISTRO 2: REGISTRO DE OPERADOR INTRACOMUNITARIO.")
        and lines[declaration.pdf_last_source_row - 1].startswith(
            f"{declaration.pdf_last_offset}-{declaration.pdf_last_offset + declaration.pdf_last_length - 1} "
            "Alfanumérico APELLIDOS Y NOMBRE O RAZÓN SOCIAL DEL SUJETO"
        )
    )


def _m349_pdf_embedded_row_matches(lines: tuple[str, ...], declaration: SupplementalBlankRunDeclaration) -> bool:
    return (
        lines[435].strip() == declaration.pdf_embedded_position_text
        and lines[446].strip() == "-------------- " + declaration.pdf_embedded_role_text
        and lines[448].startswith("TIPO DE REGISTRO 2: REGISTRO DE RETIFICACIONES.")
        and parse_pdf_row(lines[435], 436) is None
    )


def recover_m349_operator_blank_run(lines: tuple[str, ...], pdf_bytes: bytes) -> tuple[str, ...]:
    """Read the collapsed PDF row only when the exact BOE Annex corroborates it.

    The AEAT text layer gives the position pair on line 436 and its naturaleza
    on line 447, after the preceding @196+40 row. The original BOE Annex prints
    those same bytes as one unambiguous ``236-500 / Blancos`` table row. This
    repair changes the parser's *reading* of the PDF; no row is sourced from an
    invented intermediate anchor.
    """
    declaration = supplemental_blank_run_for("aeat-dr-349-2020-current")
    if declaration is None or hashlib.sha256(pdf_bytes).hexdigest() != declaration.source_sha256:
        return lines
    if not _m349_pdf_context_matches(lines, declaration) or not _m349_pdf_embedded_row_matches(lines, declaration):
        raise RegistryValidationError("M349 operator blank-run PDF geometry no longer matches pinned correction")
    _require_m349_boe_annex(declaration.boe_corpus_path, declaration.boe_sha256, declaration.boe_html_line)
    repaired = list(lines)
    repaired[435] = f"{declaration.offset}-{declaration.offset + declaration.length - 1} {declaration.description}"
    if parse_pdf_row(repaired[435], 436) is None:
        raise RegistryValidationError("M349 operator blank-run correction did not produce a record field")
    return tuple(repaired)


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
    identities: list[set[tuple[str, int]]] = [set[tuple[str, int]]()]
    line_records: list[int] = []
    record_index = 0
    for number, line in enumerate(lines, start=1):
        parsed = parse_pdf_row(line, number)
        current = identities[record_index]
        if parsed is not None and parsed.offset == 1 and current:
            record_index += 1
            current = set[tuple[str, int]]()
            identities.append(current)
        line_records.append(record_index)
        if parsed is not None and parsed.ordinal is not None:
            current.add((parsed.ordinal, parsed.offset))
    frozen = [frozenset(entry) for entry in identities]
    return [frozen[record] for record in line_records]


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


def _unparsed_pair(left: str, right: str, row_number: int) -> bool:
    """Whether neither half of a candidate split row parses on its own."""
    return parse_pdf_row(left, row_number) is None and parse_pdf_row(right, row_number + 1) is None


def _rejoin_forward_column_pair(
    line: str,
    following: str,
    row_number: int,
    claimed: frozenset[tuple[str, int]],
) -> str | None:
    """Join a coordinate head followed by a length/naturaleza tail."""
    head = _REVERSED_ROW_HEAD_RE.match(line)
    tail = REVERSED_ROW_TAIL_RE.match(following)
    if head is None or tail is None or not _unparsed_pair(line, following, row_number):
        return None
    identity = (head.group("ordinal"), int(head.group("offset")))
    if identity in claimed:
        return None
    casilla = (head.group("tail") or "").strip()
    description = tail.group("description").rstrip()
    return (
        f"{head.group('ordinal')} {head.group('offset')} "
        f"{tail.group('length')} {tail.group('type')} "
        f"{description}{' ' + casilla if casilla else ''}"
    )


def _rejoin_bled_column_pair(
    line: str,
    following: str,
    row_number: int,
    previous: PdfRow | None,
    claimed: frozenset[tuple[str, int]],
) -> str | None:
    """Join a length/naturaleza tail with a continuity-checked bled head."""
    tail = REVERSED_ROW_TAIL_RE.match(line)
    head = _REVERSED_ROW_HEAD_WITH_TAIL_RE.match(following)
    if tail is None or head is None or _REVERSED_ROW_HEAD_RE.match(following) is not None:
        return None
    if not _unparsed_pair(line, following, row_number):
        return None
    ordinal = head.group("ordinal")
    offset = int(head.group("offset"))
    if not _continues(previous, ordinal, offset) or (ordinal, offset) in claimed:
        return None
    return (
        f"{ordinal} {offset} {tail.group('length')} {tail.group('type')} "
        f"{tail.group('description').rstrip()} {head.group('trailing').strip()}"
    )


def _rejoin_tail_column_pair(
    line: str,
    following: str,
    row_number: int,
    claimed: frozenset[tuple[str, int]],
) -> str | None:
    """Join a length/naturaleza tail followed by a bare coordinate head."""
    tail = REVERSED_ROW_TAIL_RE.match(line)
    head = _REVERSED_ROW_HEAD_RE.match(following)
    if tail is None or head is None or not _unparsed_pair(line, following, row_number):
        return None
    identity = (head.group("ordinal"), int(head.group("offset")))
    if identity in claimed:
        return None
    casilla = (head.group("tail") or "").strip()
    description = tail.group("description").rstrip()
    return (
        f"{head.group('ordinal')} {head.group('offset')} "
        f"{tail.group('length')} {tail.group('type')} "
        f"{description}{' ' + casilla if casilla else ''}"
    )


def _reversed_column_pair_candidate(
    line: str,
    following: str,
    row_number: int,
    previous: PdfRow | None,
    claimed: frozenset[tuple[str, int]],
) -> str | None:
    """Return the first supported split-row join, preserving branch order."""
    return (
        _rejoin_forward_column_pair(line, following, row_number, claimed)
        or _rejoin_bled_column_pair(line, following, row_number, previous, claimed)
        or _rejoin_tail_column_pair(line, following, row_number, claimed)
    )


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
            candidate = _reversed_column_pair_candidate(
                line,
                lines[index + 1],
                index + 1,
                previous_row,
                claimed[index],
            )
            if candidate is not None:
                joined.append(candidate)
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


def _previous_parsed_row(parsed: Sequence[PdfRow | None], before: int) -> PdfRow | None:
    """Find the nearest parsed row before a source-line index."""
    return next((row for row in reversed(parsed[:before]) if row is not None), None)


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


#: A row whose ORDINAL and POSITION were emitted as one token, with the length
#: and naturaleza intact behind them: ``23 3 Num C Modelo.`` for AEAT's
#: ``2 3 3 Num C Modelo.``. Distinct from :data:`_FUSED_ROW_RE`, which covers a
#: position glued to its NATURALEZA (``59 1A Num``); here the two numbers ran
#: together and nothing is glued to a letter.
_FUSED_ORDINAL_POSITION_RE = re.compile(
    r"^\s*(?P<fused>\d+)\s+(?P<length>\d+)\s+(?P<naturaleza>An|Num|N|A)\s+(?P<rest>\S.*)$",
)


#: A row whose NATURALEZA ran into the content-column marker that follows it:
#: ``170 1697 9 AnC ...`` for AEAT's ``170 1697 9 An C ...``. The sibling
#: :data:`_DOUBLED_COORDINATE_ROW_RE` covers the same gluing when the
#: coordinates are ALSO doubled; this covers it on its own.
_GLUED_NATURALEZA_ROW_RE = re.compile(
    r"^\s*(?P<ordinal>\d+)\s+(?P<offset>\d+)\s+(?P<length>\d+)\s+"
    r"(?P<naturaleza>An|Num|N|A)(?P<marker>[A-Z])\s+(?P<rest>\S.*)$",
)


#: A row's TRUE ordinal and position, restated alone on the line below it after
#: the row itself was printed with a truncated position: ``18 215`` under
#: ``18 21 17 N ...``. Anchored end to end -- two integers and nothing else --
#: because a looser pattern would claim any line opening with two numbers.
_STRANDED_COORDINATE_PAIR_RE = re.compile(
    r"^\s*(?P<ordinal>\d+)\s+(?P<offset>\d+)\s*$",
)


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
