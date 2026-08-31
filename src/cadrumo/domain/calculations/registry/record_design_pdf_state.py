"""Stateful reconstruction of PDF record-design sheets."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Final

from pydantic import ConfigDict, TypeAdapter

from .errors import RegistryValidationError
from .record_design_pdf_repairs import _REVERSED_ROW_TAIL_RE
from .record_design_pdf_rows import (
    _clean_pdf_line,
    _is_pdf_footer,
    _is_pdf_header,
    _is_pdf_page_heading,
    _join_pdf_parts,
    _looks_like_title_continuation,
    _naturaleza_or_none,
    _normalise_pdf_sheet_name,
    _parse_pdf_row,
    _pdf_candidate_record_name,
    _pdf_page_name,
    _pdf_record_heading_name,
    _PdfRow,
    _position_runs,
    _split_glued_ordinal_position,
    _unnamed_position_candidate,
)
from .record_design_schema import (
    RecordDesignExtraction,
    RecordDesignField,
    RecordDesignRangeStartCorrection,
    RecordDesignSheet,
    RecordDesignSinglePositionCorrection,
    RecordDesignSkippedSheet,
)
from .record_design_sources import _EMPTY_CORRECTIONS, _CorrectionIndex
from .record_design_workbook import (
    _declared_subdivision_count,
    _fold_untagged_desglose_components,
    _solve_declared_desglose_holes,
    _tiles_exactly,
)

_NUMERIC_TUPLE_ADAPTER: TypeAdapter[tuple[int | float, ...]] = TypeAdapter(
    tuple[int | float, ...], config=ConfigDict(strict=True)
)


@dataclass(slots=True)
class _PdfFieldDraft:
    sheet: str
    row: int
    ordinal: str | None
    offset: int
    length: int
    type_code: str
    description_parts: list[str] = field(default_factory=list)
    content_parts: list[str] = field(default_factory=list)

    def append_continuation(self, line: str) -> None:
        if not self.description_parts or (not self.content_parts and _looks_like_title_continuation(line)):
            self.description_parts.append(line)
            return
        self.content_parts.append(line)

    def finish(self) -> RecordDesignField:
        description = _join_pdf_parts(self.description_parts)
        if not description and self.type_code == "Blancos":
            # A fill run needs no description: AEAT writes the naturaleza alone
            # ("58 BLANCO", "187-390 BLANCOS") because there is no datum to name.
            # Demanding one here discarded the row, and a discarded fill run
            # leaves a hole that reads as "the reader lost a field".
            description = "Blancos"
        if not description:
            raise RegistryValidationError(f"{self.sheet!r} PDF row {self.row} missing description")
        return RecordDesignField(
            sheet=self.sheet,
            row=self.row,
            ordinal=self.ordinal,
            offset=self.offset,
            length=self.length,
            type_code=self.type_code,
            complementary=None,
            description=description,
            validation=None,
            content=_join_pdf_parts(self.content_parts) or None,
        )


@dataclass(slots=True)
class _PdfSheetDraft:
    name: str
    fields: list[RecordDesignField] = field(default_factory=list)
    current: _PdfFieldDraft | None = None
    #: Whether the source NAMED this record body. ``False`` marks a body the
    #: geometry proved exists -- its positions restart at 1 -- whose heading the
    #: parser did not recognise, so its identity is unknown. Such a body is
    #: reported as a skipped sheet rather than returned, because handing back a
    #: record under a name nobody read would be an invented record identity.
    identified: bool = True
    #: The source row at which this body's first position was seen, used to name
    #: an unidentified body by where it is rather than by what it might be.
    opened_at_row: int | None = None
    #: Rows carrying a position RANGE and a description but no naturaleza, held
    #: for :meth:`fill_unread_gaps`. Staged rather than admitted on sight because
    #: the shape is dominated by prose; see :func:`_unnamed_position_candidate`.
    unnamed_candidates: list[_PdfRow] = field(default_factory=list)
    #: Declared corrections that authorised a staged candidate, recorded so a
    #: design read only BECAUSE of a declaration is never reported as one AEAT
    #: published cleanly.
    applied_corrections: list[RecordDesignSinglePositionCorrection] = field(default_factory=list)
    #: Rows carrying a length, a naturaleza and a description but NO position,
    #: paired with the position the row before them implies. The mirror image of
    #: ``unnamed_candidates``, and admitted by the same containment test.
    headless_candidates: list[_PdfRow] = field(default_factory=list)

    def has_started(self) -> bool:
        """Whether any field of this record body has been seen yet."""
        return bool(self.fields) or self.current is not None

    def start_field(self, row: _PdfRow) -> None:
        self.finish_current()
        self.current = _PdfFieldDraft(
            sheet=self.name,
            row=row.source_row,
            ordinal=row.ordinal if row.ordinal is not None else str(len(self.fields) + 1),
            offset=row.offset,
            length=row.length,
            type_code=row.type_code,
            description_parts=[row.description] if row.description else [],
        )

    def finish_current(self) -> None:
        if self.current is None:
            return
        self.fields.append(self.current.finish())
        self.current = None

    def fill_unread_gaps(self) -> None:
        """Admit staged candidates that fall wholly inside a span no row claims.

        A fixed-width record is contiguous, so an interior span no read row
        covers is a row that was dropped, not a span AEAT left undescribed. Where
        a staged candidate covers exactly such a span it is the dropped row, and
        admitting it is the only reading that makes the record whole.

        The containment test is what keeps this safe. A candidate overlapping any
        claimed position is discarded, so a prose line restating a field's own
        range -- the shape this parser must keep refusing -- can never be
        admitted: its range is claimed by the very field it describes. Only a
        genuine hole can absorb one.

        Modelo 296 is the worked case: its perceptor record declares 500
        positions and read none of 413-432, because AEAT printed
        ``413-432 CODIGO LEI DEL PERCEPTOR`` with no naturaleza while its
        neighbour ``433-452 Alfanumerico NIF EN EL PAIS...`` carries one.
        """
        staged = [*self.unnamed_candidates, *self.headless_candidates]
        if not staged or not self.fields:
            return
        claimed: set[int] = set()
        for read in self.fields:
            claimed.update(range(read.offset, read.offset + read.length))
        admitted: list[RecordDesignField] = []
        for candidate in staged:
            span = range(candidate.offset, candidate.offset + candidate.length)
            if claimed.isdisjoint(span):
                admitted.append(
                    RecordDesignField(
                        sheet=self.name,
                        row=candidate.source_row,
                        ordinal=None,
                        offset=candidate.offset,
                        length=candidate.length,
                        type_code=candidate.type_code,
                        description=candidate.description,
                    ),
                )
                claimed.update(span)
        if admitted:
            self.fields = sorted([*self.fields, *admitted], key=lambda read: read.offset)

    def fill_declared_desglose_gaps(self) -> None:
        """Admit a dropped sub-field whose absence AEAT's own declared COUNT proves.

        :meth:`fill_unread_gaps` admits only into a span NO read row claims, and
        that guard is deliberately conservative: the candidate shape is
        overwhelmingly prose, because AEAT routinely opens a field's description
        with that field's own range, and 41 bundled designs do. Admitting into a
        claimed span on containment alone would turn that prose into invented
        positions -- the Modelo 190 ``@108+1`` and Modelo 156 one-byte
        ``APELLIDOS`` class of fabrication, the worst failure available here.

        A desglose parent's span is the one place that guard is too strong, and
        only when the design itself supplies the arithmetic. Where AEAT writes
        "Este campo se subdivide en cuatro", the count is the authority stating
        how many sub-fields exist. If fewer were read, the run leaves a hole, and
        a staged candidate fills that hole EXACTLY such that the sub-fields then
        tile the parent end to end AND number exactly the declared count, then
        the candidate is the dropped row and nothing else fits: three
        independent facts -- the count, the tiling, and the exact hole -- all have
        to agree at once.

        Modelo 184 is the worked case and, measured across every bundled PDF
        design, the ONLY site where all three agree. Its ``@147+9`` says "se
        subdivide en cuatro:" over sub-fields at 147, 148 and 149-150, leaving
        151-155 unread, because AEAT printed ``151-155 PORCENTAJE DE RENTA
        ATRIBUIBLE A MIEMBROS RESIDENTES`` with no naturaleza on the naming row
        while its neighbour ``149-150 Alfabetico CLAVE PAIS:`` carries one -- the
        same omission that cost Modelo 296 its ``413-432 CODIGO LEI``.

        The conjunction is what keeps this safe, and each clause excludes real
        sites. Modelo 038's eleven chart-geometry artefacts declare no count and
        are refused at the first clause. Modelos 165 and 280 declare TWO, already
        read two, and hold a one-byte gap: admitting there would make three where
        AEAT says two, so the count clause refuses them and their genuine
        one-byte defect is left visible rather than papered over.
        """
        if not self.unnamed_candidates or not self.fields:
            return
        # Grouped, never a single candidate per offset: AEAT nests these. Modelo
        # 184 stages BOTH "151-155 PORCENTAJE..." and the "151- 153 ENTERO" it
        # subdivides into, so keying one candidate per offset silently picks
        # whichever was read last and loses the one that actually fits.
        by_offset: dict[int, list[_PdfRow]] = {}
        for candidate in self.unnamed_candidates:
            by_offset.setdefault(candidate.offset, []).append(candidate)
        admitted: list[RecordDesignField] = []
        index = 0
        while index < len(self.fields):
            parent = self.fields[index]
            run: list[RecordDesignField] = []
            cursor = index + 1
            while cursor < len(self.fields):
                child = self.fields[cursor]
                if (
                    child.offset >= parent.offset
                    and child.offset + child.length <= parent.offset + parent.length
                    and (child.offset, child.length) != (parent.offset, parent.length)
                ):
                    run.append(child)
                    cursor += 1
                else:
                    break
            index = cursor if run else index + 1
            declared = _declared_subdivision_count(parent)
            # ``run`` may be EMPTY. Modelo 190's 81-107 and 108-147 each say
            # "Este campo se subdivide en tres/cuatro" and NONE of their
            # sub-rows was read, so requiring an already-read child would
            # skip exactly the designs where the whole desglose went unread.
            # The declared count still carries the proof: the candidates must
            # tile the parent end to end AND number exactly what it declares.
            if declared is None or _tiles_exactly(parent, run) or len(run) >= declared:
                continue
            covered: set[int] = set()
            for child in run:
                covered.update(range(child.offset, child.offset + child.length))
            chosen = _solve_declared_desglose_holes(
                parent=parent,
                covered=covered,
                by_offset=by_offset,
                wanted=declared - len(run),
            )
            if chosen is None:
                continue
            fillers = [
                RecordDesignField(
                    sheet=self.name,
                    row=candidate.source_row,
                    ordinal=None,
                    offset=candidate.offset,
                    length=candidate.length,
                    type_code=candidate.type_code,
                    description=candidate.description,
                )
                for candidate in chosen
            ]
            if not _tiles_exactly(parent, sorted([*run, *fillers], key=lambda read: read.offset)):
                continue
            admitted.extend(fillers)
        if admitted:
            self.fields = sorted([*self.fields, *admitted], key=lambda read: read.offset)

    def finish(self, *, source_label: str) -> RecordDesignSheet:
        self.finish_current()
        self.fill_unread_gaps()
        self.fill_declared_desglose_gaps()
        self.fields = _fold_untagged_desglose_components(self.fields)
        total_positions = max((field.offset + field.length - 1 for field in self.fields), default=None)
        sheet = RecordDesignSheet(
            name=self.name,
            fields=tuple(self.fields),
            total_positions=total_positions,
            corrections=tuple(self.applied_corrections),
        )
        _validate_pdf_sheet(sheet, source_label=source_label)
        return sheet


@dataclass(frozen=True, slots=True)
class _PdfSheetResult:
    """One finished record body and whether the source named it."""

    sheet: RecordDesignSheet
    identified: bool
    opened_at_row: int | None


#: A record's own closing identifier, which names the modelo and the page it
#: belongs to: ``</T200001>`` closes page 1 of modelo 200. AEAT writes it as the
#: last field of every page record in the designs that head their records with
#: nothing a heading recogniser can see.
_PDF_RECORD_END_IDENTIFIER_RE = re.compile(r"</T(?P<modelo>\d{3})(?P<page>[A-Z0-9]{2,5})>")
#: The same fact stated at the TOP of the record, as the contenido of its
#: ``Página`` row: ``3 6 3 An Página. OBLIGATORIO Constante "001"``.
_PDF_PAGE_CONSTANT_RE = re.compile(r'Constante\s*"(?P<page>[A-Z0-9]{2,5})"')


#: The widths AEAT writes a página constant in, observed across the bundled
#: corpus: two digits (modelo 763), three (modelo 200), five (modelo 390's
#: composite). Four is deliberately absent -- that is an ejercicio.
_PAGE_CONSTANT_WIDTHS: Final[frozenset[int]] = frozenset({2, 3, 5})


def _page_label_from_token(token: str) -> str:
    """The page a record's página constant names, as the design writes it.

    Most designs write a number directly: modelo 200's ``001``, modelo 763's
    ``02``. Two shapes are not plain numbers and both are read as AEAT states
    them.

    Modelo 390's 2015 edition writes a five-digit composite, ``01000`` through
    ``08000``, where the leading digits are the page and the trailing ``000`` is
    a sub-counter. That split is not assumed: the design cross-checks it, since
    the record its running header names ``Pag. 1`` is the record declaring
    ``Constante "01000"``.

    Modelo 200 writes an ALPHABETIC page for one record -- ``Constante "DID"``,
    closing ``</T200DID>`` -- and its own vector example lists that record in
    the page sequence beside the numbered ones
    (``...017018019019DIDFIN``). There is no number to derive, so the token is
    the label.
    """
    if token.isdigit():
        if len(token) == 5 and token.endswith("000"):
            return str(int(token[:2]))
        return str(int(token))
    return token


def _recovered_record_identity(sheet: RecordDesignSheet) -> str | None:
    """Name an unheaded record body from the identity it declares about itself.

    Some AEAT designs never head a record with a title. Each record states which
    page it is twice: as the ``Constante "006"`` of its Página field, and as the
    ``</T200006>`` closing identifier AEAT requires as the record's last field.
    Both are declared required CONTENT, so reading them is recovery rather than
    guesswork.

    The closing identifier is preferred, because it names the modelo as well as
    the page and a stray constant elsewhere in the body cannot imitate it. It is
    set aside in exactly one circumstance: when its page component is not as
    wide as the Página field DECLARES that component to be. The identifier is a
    concatenation, so a lost digit inside it is silent -- modelo 390's seventh
    record closes ``</T3900700>``, seven digits where its siblings carry eight,
    which read as page 700. The field's own length is what exposes that, and
    where the two disagree without such a width contradiction the identifier is
    still trusted, because nothing says which side is the corrupt one.

    The Página strategy is keyed on GEOMETRY, never on the word "Página". These
    designs are published as PDFs whose text layer does not survive decoding
    intact -- the label arrives as ``P?gina`` -- so a reader matching the
    Spanish label would work on the editions that decode cleanly and fail on the
    ones that do not. AEAT fixes the geometry instead: the modelo constant at
    positions 3-5 and the page constant immediately after it. Requiring BOTH is
    what makes this safe, since a lone constant elsewhere cannot satisfy it, and
    the constant must be exactly as wide as its field declares.

    Returns ``None`` when the body declares neither identity, leaving it
    unidentified and on the worklist exactly as before. Recovering a name the
    record did not state would be inventing an identity, which is worse than
    reporting the gap.
    """
    by_offset = {field.offset: field for field in sheet.fields}
    modelo_field, page_field = by_offset.get(3), by_offset.get(6)
    declared_page: str | None = None
    if (
        modelo_field is not None
        and page_field is not None
        and modelo_field.length == 3
        and _pdf_declared_constant(modelo_field) is not None
    ):
        candidate = _pdf_declared_constant(page_field)
        # Two conditions, and both earn their place. The constant must be as
        # wide as its own field declares -- that is what lets modelo 763's two
        # digits, modelo 200's three and modelo 390's five all be read without a
        # reader-side assumption. And the width must be one AEAT actually uses
        # for a page: a FOUR-digit constant at this position is an ejercicio,
        # ``Constante "2011"``, and self-consistency alone would happily read it
        # as page 2011.
        if candidate is not None and len(candidate) == page_field.length and page_field.length in _PAGE_CONSTANT_WIDTHS:
            declared_page = candidate

    for design_field in reversed(sheet.fields):
        for text in (design_field.content, design_field.description, design_field.validation):
            if not text:
                continue
            match = _PDF_RECORD_END_IDENTIFIER_RE.search(str(text))
            if match is None:
                continue
            closing = match.group("page")
            # The closing identifier is matched anywhere in a field's text, so a
            # token bled in from a neighbouring record can be picked up. That is
            # tolerable for a numeric page, which the width check still guards,
            # but not for an ALPHABETIC one: modelo 200's ``</T200DID>`` appears
            # in prose inside other records, and reading it there renamed a
            # 1,618-field record after the token that belongs to a 45-field one.
            # An alphabetic page is therefore taken only from the Página field,
            # which geometry anchors.
            if not closing.isdigit():
                break
            if declared_page is not None and len(closing) != len(declared_page):
                return f"Pág. {_page_label_from_token(declared_page)}"
            return f"Pág. {_page_label_from_token(closing)}"

    if declared_page is not None:
        return f"Pág. {_page_label_from_token(declared_page)}"
    return None


def _pdf_declared_constant(field: RecordDesignField) -> str | None:
    """The three-digit constant a field declares as its required content."""
    for text in (field.content, field.description, field.validation):
        if not text:
            continue
        match = _PDF_PAGE_CONSTANT_RE.search(str(text))
        if match is not None:
            page = match.group("page")
            assert isinstance(page, str)
            return page
    return None


def _unidentified_record_body_name(row_number: int) -> str:
    """Name an unnamed record body by WHERE it is, never by what it might be."""
    return f"<unidentified record body beginning at source row {row_number}>"


class _PdfParseState:
    """Mutable state for the PDF record-design line parser.

    Encapsulates the locals (``current`` draft sheet, ``in_table`` flag,
    ``pending_name`` carried across page-name boundaries, ``pending_record_name``
    staged by a candidate record heading) so the per-line dispatch can mutate
    them without threading out-parameters through every helper.
    """

    __slots__ = (
        "corrections",
        "current",
        "in_table",
        "pending_name",
        "pending_record_name",
        "repair_glued_rows",
        "results",
        "source_label",
    )

    def __init__(
        self,
        *,
        source_label: str,
        corrections: _CorrectionIndex = _EMPTY_CORRECTIONS,
        repair_glued_rows: bool = False,
    ) -> None:
        self.repair_glued_rows = repair_glued_rows
        self.results: list[_PdfSheetResult] = []
        self.current: _PdfSheetDraft | None = None
        self.in_table: bool = False
        self.pending_name: str | None = None
        self.pending_record_name: str | None = None
        self.source_label = source_label
        self.corrections = corrections

    def finalise(self) -> RecordDesignExtraction:
        """Return the parsed records, naming every one the parser did not read.

        Three things land in ``skipped`` rather than being dropped, and each was
        previously invisible:

        * a record heading the parser recognised but found no field rows under;
        * a record body whose existence geometry proves -- its positions restart
          at 1 -- but whose heading the parser did not recognise, so it has no
          identity to return it under;
        * both together.

        The rule is one sentence: A READ THAT RETURNS FEWER RECORDS THAN THE
        DOCUMENT CONTAINS MUST NEVER REPORT COMPLETE. Every one of these makes
        :attr:`RecordDesignExtraction.is_complete` false, so
        :meth:`RecordDesignExtraction.require_complete` -- the guard that exists
        precisely to catch an incomplete read -- can finally see them.
        """
        self.close_current_body()
        self._recover_unidentified_bodies()
        read = tuple(result.sheet for result in self.results if result.identified and result.sheet.fields)
        if not read:
            raise RegistryValidationError("record-design PDF did not contain parseable field rows")
        read = _recover_inline_constants(read)
        read = _apply_range_start_corrections(read, self.corrections.range_start_corrections)
        # A sheet whose rows do not tile its own declared extent was not read as
        # published, so it is reported as SKIPPED rather than handed over as if
        # it were whole. See :func:`contiguity_failure`.
        broken = {sheet.name: reason for sheet in read if (reason := contiguity_failure(sheet)) is not None}
        return RecordDesignExtraction(
            source=self.source_label,
            sheets=tuple(sheet for sheet in read if sheet.name not in broken),
            skipped=(
                *(
                    RecordDesignSkippedSheet(name=result.sheet.name, reason=_skipped_record_reason(result))
                    for result in self.results
                    if not (result.identified and result.sheet.fields)
                ),
                *(RecordDesignSkippedSheet(name=name, reason=reason) for name, reason in broken.items()),
            ),
        )

    def _recover_unidentified_bodies(self) -> None:
        """Give every unheaded body the identity it declares about itself.

        A recovered name must be UNIQUE within the design. Two bodies resolving
        to one name would silently merge two records into one identity, which is
        the failure the unidentified-body report exists to prevent -- so a
        collision leaves both on the worklist rather than picking a winner.
        """
        taken = {result.sheet.name for result in self.results if result.identified}
        recovered: dict[int, str] = {}
        seen: dict[str, int] = {}
        for index, result in enumerate(self.results):
            if result.identified or not result.sheet.fields:
                continue
            name = _recovered_record_identity(result.sheet)
            if name is None or name in taken:
                continue
            if name in seen:
                recovered.pop(seen[name], None)
                continue
            seen[name] = index
            recovered[index] = name
        for index, name in recovered.items():
            result = self.results[index]
            self.results[index] = _PdfSheetResult(
                sheet=result.sheet.model_copy(update={"name": name}),
                identified=True,
                opened_at_row=result.opened_at_row,
            )

    def feed(self, line: str, row_number: int) -> None:
        if not line or _is_pdf_footer(line):
            return
        if self._consume_page_name(line):
            return
        if self._consume_record_heading(line):
            return
        self._stage_candidate_record_name(line)
        if self._consume_table_header(line):
            return
        if self._consume_title_continuation(line):
            return
        if _is_pdf_page_heading(line):
            return
        if self._consume_field_row(line, row_number):
            return
        self._stage_unnamed_position_candidate(line, row_number)
        self._stage_headless_tail(line, row_number)
        self._consume_field_continuation(line)

    def _stage_unnamed_position_candidate(self, line: str, row_number: int) -> None:
        """Hold a range-carrying row whose naturaleza AEAT omitted, for the gap fill.

        Staged even though the line ALSO reaches
        :meth:`_consume_field_continuation`, which is deliberate: the two are not
        alternatives, because at this point nothing knows whether the line is a
        dropped row or the continuation prose it far more often is. The gap fill
        decides later on geometry. Where it admits one, the text appears both on
        the admitted field and on the neighbouring description it was absorbed
        into -- accepted, because a duplicated description is visible and
        harmless while a dropped field is neither.
        """
        if self.current is None:
            return
        candidate = _unnamed_position_candidate(
            line,
            row_number,
            sheet=self.current.name,
            single_position_corrections=self.corrections.single_position_corrections,
        )
        if candidate is None:
            return
        self.current.unnamed_candidates.append(candidate)
        declared = self.corrections.single_position_corrections.get((self.current.name, candidate.offset))
        if declared is not None and candidate.length == 1:
            self.current.applied_corrections.append(declared)

    def _stage_headless_tail(self, line: str, row_number: int) -> None:
        """Hold a row that kept its length and naturaleza but lost its position.

        A page break can swallow a row's position half outright, leaving only
        ``17 N Sociedades de garantia reciproca - ...`` with the ``6 11`` above
        it gone. The position is not guessed from that line: it is taken from
        where the previous row ENDS, and the candidate is then subject to the
        same containment test every staged candidate faces -- admitted only if
        the span it would occupy is one no read row claims.

        That test is what makes this a reading. Three independent facts must
        agree before such a row appears: the position follows the previous row,
        the length is the one AEAT printed, and the span is exactly a hole. A
        fragment that would overlap anything already read is discarded, so a
        wrapped description restating a field's width can never be admitted.
        """
        if self.current is None or not self.repair_glued_rows:
            return
        match = _REVERSED_ROW_TAIL_RE.match(line)
        if match is None or _parse_pdf_row(line, row_number) is not None:
            return
        previous = self._last_seen_field()
        if previous is None:
            return
        naturaleza = _naturaleza_or_none(match.group("type"))
        if naturaleza is None and match.group("type") not in {"An", "Num", "N", "A", "Tit"}:
            return
        self.current.headless_candidates.append(
            _PdfRow(
                source_row=row_number,
                ordinal=None,
                offset=previous.offset + previous.length,
                length=int(match.group("length")),
                type_code=match.group("type"),
                description=match.group("description").strip(),
            ),
        )

    def _last_seen_field(self) -> _PdfFieldDraft | RecordDesignField | None:
        """The most recent field of the body under construction, finished or not."""
        if self.current is None:
            return None
        if self.current.current is not None:
            return self.current.current
        return self.current.fields[-1] if self.current.fields else None

    def close_current_body(self) -> None:
        if self.current is None:
            return
        self.results.append(
            _PdfSheetResult(
                sheet=self.current.finish(source_label=self.source_label),
                identified=self.current.identified,
                opened_at_row=self.current.opened_at_row,
            ),
        )
        self.current = None

    def _open_body(self, name: str, *, identified: bool = True) -> None:
        self.close_current_body()
        self.current = _PdfSheetDraft(name, identified=identified)
        self.pending_record_name = None

    def _consume_page_name(self, line: str) -> bool:
        page_name = _pdf_page_name(line)
        if page_name is None:
            return False
        self.pending_name = page_name
        if self.current is not None and self.current.name != page_name:
            self._open_body(page_name)
        return True

    def _consume_record_heading(self, line: str) -> bool:
        heading_name = _pdf_record_heading_name(line)
        if heading_name is None:
            return False
        self._open_body(heading_name)
        self.in_table = False
        return True

    def _consume_table_header(self, line: str) -> bool:
        if not _is_pdf_header(line):
            return False
        if self.current is None:
            self.current = _PdfSheetDraft(self.pending_name or "PDF record design")
        self.in_table = True
        return True

    def _consume_title_continuation(self, line: str) -> bool:
        if self.in_table or self.current is None or self.current.fields:
            return False
        if not _looks_like_title_continuation(line):
            return False
        self.current.name = _normalise_pdf_sheet_name(_join_pdf_parts([self.current.name, line]))
        return True

    def _stage_candidate_record_name(self, line: str) -> None:
        """Remember a candidate record name WITHOUT acting on it.

        Staged rather than consumed on both counts: the line stays in the
        parser's ordinary pipeline exactly as before (so no field description
        loses text it used to carry), and no record boundary is created from
        the text. Only :meth:`_begins_a_new_record_body`, reading position
        geometry, decides a record actually starts -- at which point this name
        is used if one was staged since the last field row, and discarded
        otherwise. A candidate matched inside field prose is therefore inert.
        """
        candidate = _pdf_candidate_record_name(line)
        if candidate is not None:
            self.pending_record_name = candidate

    def _begins_a_new_record_body(self, row: _PdfRow) -> bool:
        """Whether ``row`` starts a record body distinct from the one being read.

        POSITION 1 OCCURS EXACTLY ONCE PER RECORD. A fixed-width record is
        contiguous from its first byte, so a row declaring position 1 while the
        body under construction already holds fields is not a continuation of
        that body under any reading -- it is the next record. This is geometry
        AEAT itself declares, not a text heuristic, so it holds for every
        heading spelling, every word order and every design that heads its
        records with no recognisable line at all.

        Modelo 180 is the worked case: AEAT heads its perceptor record
        ``REGISTRO DE TIPO 2: REGISTRO DE PERCEPTOR.`` -- a word order the
        heading recogniser did not know -- so seventeen perceptor positions
        were appended to the declarante record, the extraction returned ONE
        sheet for a two-record document, and it reported itself complete.
        """
        return self.current is not None and row.offset == 1 and self.current.has_started()

    def _consume_field_row(self, line: str, row_number: int) -> bool:
        row = _parse_pdf_row(line, row_number)
        if row is None and self.repair_glued_rows:
            row = _split_glued_ordinal_position(line, row_number, previous=self._last_seen_field())
        if row is None:
            return False
        if self.current is None:
            self.current = _PdfSheetDraft(self.pending_name or "PDF record design")
        elif self._begins_a_new_record_body(row):
            staged = self.pending_record_name
            self._open_body(
                staged if staged is not None else _unidentified_record_body_name(row_number),
                identified=staged is not None,
            )
        if self.current.opened_at_row is None:
            self.current.opened_at_row = row_number
        self.current.start_field(row)
        self.in_table = True
        self.pending_record_name = None
        return True

    def _consume_field_continuation(self, line: str) -> None:
        if self.in_table and self.current is not None and self.current.current is not None:
            self.current.current.append_continuation(line)


def _skipped_record_reason(result: _PdfSheetResult) -> str:
    if not result.sheet.fields:
        return "record heading recognised but no field rows parsed under it"
    return (
        f"a distinct record body begins here -- its positions restart at 1 at source row "
        f"{result.opened_at_row} -- but the source's heading for it was not recognised, so this "
        f"record has no read identity. It is reported unread rather than merged into the record "
        f"above it, because merging understates the document by a whole record while still "
        f"reporting the read complete"
    )


def _extract_pdf_lines(
    lines: tuple[str, ...],
    *,
    source_label: str,
    corrections: _CorrectionIndex = _EMPTY_CORRECTIONS,
    repair_glued_rows: bool = False,
) -> RecordDesignExtraction:
    state = _PdfParseState(
        source_label=source_label,
        corrections=corrections,
        repair_glued_rows=repair_glued_rows,
    )
    for row_number, raw_line in enumerate(lines, start=1):
        state.feed(_clean_pdf_line(raw_line), row_number)
    return state.finalise()


def _validate_pdf_sheet(sheet: RecordDesignSheet, *, source_label: str) -> None:
    if not sheet.fields:
        return
    first_field = sheet.fields[0]
    if first_field.offset != 1:
        raise RegistryValidationError(
            f"{source_label} {sheet.name!r} first field starts at position {first_field.offset}; expected 1",
        )
    for parsed_field in sheet.fields:
        if parsed_field.offset < 1:
            raise RegistryValidationError(
                f"{source_label} {sheet.name!r} field ordinal {parsed_field.ordinal} has invalid "
                f"position {parsed_field.offset}",
            )
        if parsed_field.length < 1:
            raise RegistryValidationError(
                f"{source_label} {sheet.name!r} field ordinal {parsed_field.ordinal} has invalid "
                f"length {parsed_field.length}",
            )
    terminal_position = max(parsed_field.offset + parsed_field.length - 1 for parsed_field in sheet.fields)
    if sheet.total_positions is not None and terminal_position != sheet.total_positions:
        raise RegistryValidationError(
            f"{source_label} {sheet.name!r} declares {sheet.total_positions} total positions "
            f"but parsed fields fill {terminal_position}",
        )


#: A record row declaring a bracket constant: ``Constante "<VECTOR>"`` opens a
#: payload region and ``Constante "</VECTOR>"`` closes it.
_PDF_BRACKET_CONSTANT_RE = re.compile(r'Constante\s*"<(?P<closing>/?)(?P<tag>[A-Z][A-Z0-9_]*)>"')


def _bracketed_payload_positions(sheet: RecordDesignSheet) -> set[int]:
    """Positions a record brackets as a payload region rather than numbering.

    Some AEAT records wrap a block of content between two constant rows --
    ``Constante "<VECTOR>"`` at 329-336 and ``Constante "</VECTOR>"`` at 637-645
    in modelo 200's 2010 orden edition -- and describe what sits between them in
    PROSE rather than as numbered field rows ("y el resto a blancos hasta
    completar las 300 posiciones"). The bytes are declared; only the numbering
    is absent.

    Contiguity reads that as a 300-byte hole and reports the record as partly
    read, which is wrong in a way that matters: it is indistinguishable from the
    dropped-row defect the check exists to catch, so a genuine reader bug in
    such a record would hide behind an expected complaint.

    The span is taken from the two constants' own offsets, never from the prose.
    That is what keeps this from being an invention: AEAT declares both markers
    as required content at fixed positions, so what they bracket is fixed too.
    The prose is corroboration and it agrees exactly -- 337 to 636 is 300
    positions -- but nothing here parses it.

    Only a MATCHED pair counts, and only in the order open-then-close. A lone
    marker, or a closing marker before its opening, describes no region and is
    left to be reported as the hole it is.
    """
    openings: dict[str, RecordDesignField] = {}
    covered: set[int] = set()
    for design_field in sorted(sheet.fields, key=lambda item: item.offset):
        for text in (design_field.content, design_field.description, design_field.validation):
            if not text:
                continue
            match = _PDF_BRACKET_CONSTANT_RE.search(str(text))
            if match is None:
                continue
            tag = match.group("tag")
            if not match.group("closing"):
                openings[tag] = design_field
            elif (opening := openings.pop(tag, None)) is not None:
                start = opening.offset + opening.length
                if start < design_field.offset and not _numbers_rows_inside(sheet, start, design_field.offset):
                    covered.update(range(start, design_field.offset))
            break
    return covered


def _numbers_rows_inside(sheet: RecordDesignSheet, start: int, end: int) -> bool:
    """Whether the design numbers any field row strictly inside ``start``..``end``.

    This is what keeps bracket accounting from weakening the hole check. A
    bracket credited unconditionally would hide a genuine dropped row that
    happened to fall between two markers, which is the exact defect contiguity
    exists to catch.

    So a bracket earns its region ONLY when AEAT numbers nothing inside it --
    the opaque-payload case, where the bytes are described in prose. Modelo
    200's structural ``<AUX>`` wrapper numbers five rows inside itself and is
    therefore NOT credited; it does not need to be, because those rows already
    tile it. Its ``<VECTOR>`` payload numbers none and is credited.
    """
    return any(start <= probe.offset < end for probe in sheet.fields)


#: A constant AEAT states inside a field's own description, in its own quotes:
#: ``Inicio del identificador de modelo y pagina. "<T840010>". OBLIGATORIO``.
_INLINE_CONSTANT_RE = re.compile(r'"([^"]{1,40})"')


def _recover_inline_constants(sheets: tuple[RecordDesignSheet, ...]) -> tuple[RecordDesignSheet, ...]:
    """Return ``sheets`` with inline-stated constants surfaced as field content.

    AEAT publishes most record designs with a Contenido column, and the reader fills
    ``content`` from it. A few designs have no such column and state the constant
    inside the description instead, so those fields arrive with ``content=None`` and
    every consumer that needs the official constant -- the export generator's literal
    fields above all -- has nothing to read.

    SCOPED TO THE DOCUMENT, NOT TO A MODELO. The fallback fires only when NO field in
    the whole extraction carries content, which is what "this design has no Contenido
    column" means. That matters: measured across the bundled corpus, 210 designs have
    the column and one does not, and a rule that fired per-field instead would have
    given content to 1,625 fields across 13 modelos -- including modelo 210, where the
    quoted text is an enumeration of alternatives ("Transferencia cuenta bancaria en
    Espana"-"Transferencia...") and not a constant at all.
    """
    if any(existing.content for sheet in sheets for existing in sheet.fields):
        return sheets
    recovered: list[RecordDesignSheet] = []
    for sheet in sheets:
        fields: list[RecordDesignField] = []
        for design_field in sheet.fields:
            match = _INLINE_CONSTANT_RE.search(design_field.description or "")
            if match is None:
                fields.append(design_field)
                continue
            fields.append(design_field.model_copy(update={"content": match.group(0)}))
        recovered.append(sheet.model_copy(update={"fields": tuple(fields)}))
    return tuple(recovered)


def _apply_range_start_corrections(
    sheets: tuple[RecordDesignSheet, ...],
    corrections: Mapping[tuple[str, int], RecordDesignRangeStartCorrection],
) -> tuple[RecordDesignSheet, ...]:
    """Extend a declared filler run backwards over a span no field describes.

    Applied to a row that WAS read, at a start AEAT mis-declared: Modelo 165's
    2013 orden prints ``104-500 BLANCOS`` where both later editions of the same
    orden print ``102-500``, leaving 102-103 described by nothing.

    THE PRECONDITION IS ENFORCED HERE, not trusted from the declaration, and it
    is the whole guard: every position the run would gain must currently be
    described by NO field on the sheet. A correction that would swallow, split
    or overlap a read field RAISES rather than applying, so this kind can only
    ever reclaim a hole -- it can never invent a field, displace one, or quietly
    absorb data AEAT actually declared. A declaration naming a start no row
    begins at raises too, because a correction that matches nothing is a
    mis-transcription and silently ignoring it would leave the hole it was
    written to close.
    """
    if not corrections:
        return sheets
    corrected: list[RecordDesignSheet] = []
    for sheet in sheets:
        applicable = {start: correction for (name, start), correction in corrections.items() if name == sheet.name}
        if not applicable:
            corrected.append(sheet)
            continue
        described: set[int] = set()
        for parsed in sheet.fields:
            described.update(range(parsed.offset, parsed.offset + parsed.length))
        fields = list(sheet.fields)
        applied: list[RecordDesignRangeStartCorrection] = []
        for start, correction in sorted(applicable.items()):
            matches = [index for index, parsed in enumerate(fields) if parsed.offset == start]
            if not matches:
                raise RegistryValidationError(
                    f"record-design sheet {sheet.name!r} declares a range-start correction at "
                    f"{start} but no field begins there; the correction names nothing and the "
                    "span it was written to close would stay open",
                )
            gained = set(range(correction.corrected_start, start))
            if collides := sorted(gained & described):
                raise RegistryValidationError(
                    f"record-design sheet {sheet.name!r} range-start correction would extend a run "
                    f"back over position(s) {collides} that a read field already describes; this "
                    "correction kind reclaims a hole and must never displace declared data",
                )
            index = matches[0]
            original = fields[index]
            fields[index] = original.model_copy(
                update={
                    "offset": correction.corrected_start,
                    "length": original.length + (start - correction.corrected_start),
                },
            )
            described |= gained
            applied.append(correction)
        corrected.append(
            sheet.model_copy(update={"fields": tuple(fields), "corrections": (*sheet.corrections, *applied)}),
        )
    return tuple(corrected)


def contiguity_failure(sheet: RecordDesignSheet) -> str | None:
    """Return why ``sheet``'s parsed rows do not tile its declared extent, else ``None``.

    Reported as a SKIPPED sheet rather than raised, so
    :meth:`RecordDesignExtraction.require_complete` refuses -- which is what the
    coverage gate calls -- while ``accept_partial`` consumers keep working. A
    hard extraction error would have destroyed the reading of every design that
    is merely PARTLY unreadable, taking live modelos out of measurement
    entirely; a skip states the same fact without that collateral.

    The terminal-position check above compares only the LAST byte, so a row
    dropped or invented in the MIDDLE of a record leaves it satisfied. That is
    how every silent reader defect survived: modelo 156's ``36-75 Afabetico
    APELLIDOS Y NOMBRE`` vanished, leaving a 40-byte hole in a 250-byte record
    while ``is_complete`` stayed ``True`` and the modelo reported clean --
    coverage measured over 19 positions that AEAT declares as 20, with the
    taxpayer's name no longer checked at all. A false green is strictly worse
    than the refusal it replaced.

    A fixed-width record is contiguous, so the parsed rows must cover every byte
    from 1 to the declared total. Overlap by CONTAINMENT is expected and
    permitted -- AEAT prints a parent row and its own subdivisions (Modelo 190's
    ``@81+27`` over its three sub-ranges, Modelo 180's ``@135+193`` over
    fifteen), and both are real statements about the same bytes. What is refused
    is a HOLE (rows were dropped) and a PARTIAL overlap or an extent past the
    declared total (rows were invented), because neither can be a faithful read
    of a contiguous record.

    This is the visible-refusal principle applied where it is unambiguous. Doing
    it per LINE is not possible: AEAT routinely opens a field's description with
    that field's own range ("68-107 APELLIDOS Y NOMBRE: Se consignara el
    primer"), so "looks like a position row" is dominated by prose -- measured
    across the bundled corpus, 41 designs carry such lines. At sheet level the
    arithmetic is decisive and needs no classification.
    """
    if sheet.total_positions is None:
        return None
    covered: set[int] = set()
    for parsed_field in sheet.fields:
        covered.update(range(parsed_field.offset, parsed_field.offset + parsed_field.length))
    covered |= _bracketed_payload_positions(sheet)
    declared = set(range(1, sheet.total_positions + 1))
    if holes := sorted(declared - covered):
        return (
            f"declares {sheet.total_positions} total positions but {_position_runs(holes)} were not "
            f"read at all, so rows were dropped; a record read with holes understates every coverage "
            f"figure derived from it"
        )
    # No "beyond the declared extent" leg: ``total_positions`` is DERIVED as
    # ``max(offset + length - 1)`` on the PDF paths, so the covered set is a
    # subset of the declared span by construction and such a check can never
    # fire. Measured across 2,581 bundled sheets: zero hits. A check whose zero
    # is not evidence is worse than no check, because it reads as coverage.
    # Fabricated rows show up as OVERLAP and as a length sum exceeding the
    # extent, which is where they are caught.
    return None
