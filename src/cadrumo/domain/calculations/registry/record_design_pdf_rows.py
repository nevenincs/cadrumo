"""Parse PDF record-design row syntax and headings."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from .errors import RegistryValidationError
from .record_design_layout_markers import _RECORD_TERMINATOR_PHRASE
from .record_design_sources import _SinglePositionCorrectionIndex

if TYPE_CHECKING:
    from .record_design_pdf_state import _PdfFieldDraft
    from .record_design_schema import RecordDesignField

#: The space between LENGTH and TYPE is optional because the PDF text layer
#: loses it: modelo 100's 2009 through 2011 editions all write
#: ``5 9 1A Indicador de pagina complementaria`` for a row that is length 1,
#: type A. Requiring the space dropped the row and reported the byte it
#: declares -- position 9 -- as a hole in a record that was otherwise whole.
#:
#: The split stays unambiguous because length is digits and type is a closed
#: alternation, so ``1A`` can only be 1 + A. Measured over every bundled PDF
#: before allowing it, this admits three lines in three designs, all the same
#: genuine row.
#: ``Tit`` is a naturaleza in its own right, not a typo. Modelo 100 uses it
#: for the one-byte code naming WHICH titular an entry belongs to, and the
#: rows say so themselves: every occurrence ends its description in
#: "... - Titular" or "... - Contribuyente". Across the six bundled editions
#: that use it there are 454 such rows and every one declares length 1, which
#: is what a holder code is.
#:
#: Leaving it unrecognised dropped all 454, and because they sit BETWEEN
#: read rows the loss showed up as scattered single-byte holes -- 12, 192,
#: 372, 581 in one record alone -- which reads like corpus damage rather
#: than one missing token.
#: A trailing period after the type is abbreviation punctuation, not a
#: different token: modelo 131 writes ``52 464 13 An. Complementaria (7) -
#: Numero de Justificante anterior``. The narrative path has always accepted
#: it -- ``_naturaleza_or_none`` strips ' .' before matching -- so this only
#: brings the compact path into line with the recogniser beside it.
#:
#: Three lines in three designs, and they are the whole of modelo 131's
#: reported damage: each edition lost this one 13-byte row and reported it as
#: a dropped run at 464-476, 477-489 and 503-515 respectively.
_COMPACT_PDF_ROW_RE = re.compile(
    r"^\s*(?P<ordinal>\d+)\s+(?P<offset>\d+)\s+(?P<length>\d+)\s*(?P<type>An|Num|Tit|N|A)\.?\s+(?P<text>.+)$",
    re.IGNORECASE,
)
#: A PDF row declaring the physical end of record. Its DESCRIPTION half composes
#: the SHARED terminator phrase rather than carrying a second private spelling, so
#: the workbook splitter and this recogniser cannot drift on what a CRLF row is.
#: They already had: this one has known the terminator since it was written, while
#: the workbook path refused every design that declared one.
_COMPACT_PDF_CRLF_ROW_RE = re.compile(
    r"^\s*(?P<ordinal>\d+)\s+(?P<offset>\d+)\s+(?P<type>An|Num|N|A)\s+"
    rf"(?P<text>(?:{_RECORD_TERMINATOR_PHRASE}).*)$",
    re.IGNORECASE,
)
#: One narrative-PDF position row: ``<start>[-<end>] <naturaleza> <description>``.
#:
#: The naturaleza is captured LOOSELY here and validated afterwards by
#: :func:`_naturaleza_or_none`, rather than spelled out as a closed alternation.
#: AEAT's own spelling varies across the bundled corpus -- gender ("Numérica"
#: beside "Numérico"), accent placement ("Alfanúmerico" for "Alfanumérico") and
#: outright typos ("Afabético") all ship -- and a closed alternation turns every
#: variant into a SILENTLY dropped row, because a line that fails to match is
#: indistinguishable from ordinary prose.
#:
#: The dash alternative accepts AEAT's genuine dash-naturaleza rows
#: ("176-237 -------------- BLANCOS") but MUST NOT be followed by a digit.
#: Without that guard the engine backtracks on any row whose naturaleza it does
#: not recognise, re-reads the RANGE SEPARATOR as the type, and manufactures a
#: one-byte field at the start position carrying the rest of the line as its
#: description. Both known fabrications come from that one path: Modelo 190's
#: phantom @108+1 out of the prose "(posiciones 108 - 147) tenga contenido", and
#: Modelo 156's "36 - 75 Afabético APELLIDOS Y NOMBRE" read as a 1-byte field
#: instead of a 40-byte campo. An invented position is the worst failure
#: available here: it inflates the denominator, so an author chasing the ratio
#: would write bytes AEAT never defined -- for Modelo 156, truncating a real
#: taxpayer's name to one character. A genuine dash-naturaleza row is always
#: followed by its description, never by a number, so the guard costs nothing.
#:
#: UNDERSCORES count as that same rule. AEAT draws the empty naturaleza cell
#: with whatever character the source used: most designs use dashes
#: ("226-487 -------------- BLANCOS"), Modelo 185 uses underscores
#: ("58 ______ BLANCOS."). Both mean the same thing -- no naturaleza, the
#: description says BLANCOS -- and ``[^\W\d_]+`` cannot pick an underscore run
#: up because it excludes ``_`` by construction, so without this the rows drop.
#: Measured across every bundled PDF design before widening: exactly TWO rows in
#: ONE design newly match, both of them ``BLANCOS`` fill in Modelo 185, whose
#: two sheets were each skipped for the resulting hole and left that design
#: yielding nothing at all.
#: A design may letter a field row as an item of a lettered group before
#: giving its position: modelo 604's English ATF design writes
#: ``A. 325 Alphabetic CORRECTION.`` and ``A. 350-367 Numeric CORRECTED TAX``
#: for the two rows of its correction block, while every other row in that
#: record opens with the position. Requiring the position first dropped both,
#: leaving a one-byte hole at 325 that read as a dropped row.
#:
#: The marker is admitted, NOT the looseness it could imply: the naturaleza
#: guard still decides, so a prose line opening ``A. 15 personas`` is rejected
#: exactly as ``15 personas`` is. Measured over every bundled PDF before
#: allowing it, this admits two lines in one design and nothing else.
_NARRATIVE_PDF_ROW_RE = re.compile(
    r"^\s*(?:[^\W\d_]{1,2}\.\s+)?(?P<start>\d+)(?:\s*[-\u2013]\s*(?P<end>\d+))?\s+"
    r"(?P<type>[^\W\d_]+|[-\u2013_]+(?!\s*\d))\s*"
    r"(?P<text>.*)$",
    re.IGNORECASE,
)
#: ``Pag`` is abbreviated WITH a period in some designs and without in others
#: -- Modelo 360 heads its page two "Pag. 2 DISENO DE REGISTRO 25/03/2021" --
#: and requiring whitespace straight after the stem lost every period-form
#: heading, leaving that record body unidentified and the design partly read.
_PDF_PAGE_RECORD_RE = re.compile(r"^P[áa]g\.?\s+(?P<page>\d+)\s+DISE[ÑN]O DE REGISTRO\b", re.IGNORECASE)
#: Some designs head a further record "Anexo" in the SAME running-header shape
#: their numbered pages use, rather than as the quoted `ANEXO <<...>>` title
#: :data:`_PDF_RECORD_ANEXO_HEADING_RE` recognises. Modelo 840 writes
#: "Pag 1 DISENO DE REGISTRO", "Pag 2 DISENO DE REGISTRO" and then
#: "Anexo DISENO DE REGISTRO" for its third record, whose own opening tag is
#: `<T840030>` beside the pages' `<T840010>` and `<T840020>`. Without this the
#: third record has no read identity and the whole design reports PARTIAL --
#: correctly, because a real record body was going unread.
_PDF_ANEXO_PAGE_RECORD_RE = re.compile(r"^Anexo\s+DISE[ÑN]O DE REGISTRO\b", re.IGNORECASE)
_PDF_RECORD_HEADING_RE = re.compile(
    r"^(?:[A-Z]\.?\s*-?\s*)?(?:TIPO DE REGISTRO|Tipo de registro|RECORD TYPE|Record [Tt]ype)\s+"
    r"(?P<record>\d+)\s*:\s*(?P<title>.+)$",
    re.IGNORECASE,
)
#: English AEAT record-design translations also head a record with the reversed
#: word order "TYPE <n> RECORD: <title>" (observed in the modelo 604 ATF English
#: appendix), distinct from the "RECORD TYPE <n>: <title>" order above.
_PDF_RECORD_HEADING_REVERSED_RE = re.compile(
    r"^(?:[A-Z]\.?\s*-?\s*)?TYPE\s+(?P<record>\d+)\s+RECORD\s*:\s*(?P<title>.+)$",
    re.IGNORECASE,
)
#: A THIRD Spanish word order -- "REGISTRO DE TIPO <n>: <title>" -- which AEAT
#: uses at least as often as the two above: modelos 165, 180, 182, 184, 187, 188,
#: 193, 296 and 345 all head their perceptor/declarado record with it, several
#: separating number from title with a full stop rather than a colon.
#:
#: DELIBERATELY NOT A SPLITTING HEADING. The same phrase occurs inside ordinary
#: field prose ("Consignar lo contenido en estas mismas posiciones del registro
#: de tipo 1.", "... del registro de tipo 2. Registro de perceptor, toma el valor
#: 1) ..."), so treating a match as a record boundary on the text alone would
#: manufacture records that do not exist -- the opposite defect, and a worse one,
#: because an invented record inflates every coverage denominator derived from
#: the design. A match here only STAGES a name; whether a record actually starts
#: is decided by geometry, in :meth:`_PdfParseState._begins_a_new_record_body`.
_PDF_RECORD_HEADING_TYPE_LAST_RE = re.compile(
    r"^(?:[A-Z]\.?\s*-?\s*)?REGISTRO DE TIPO\s+(?P<record>\d+)\s*[:.]\s*(?P<title>\S.*)$",
    re.IGNORECASE,
)


#: A FOURTH shape: an annex record headed by its own quoted title, which is how
#: Modelo 296 heads the two anexos that follow its perceptor record --
#: ``ANEXO <<VALORES NEGOCIABLES. RELACION DE PAGO A CONTRIBUYENTES`` and
#: ``ANEXO <<VALORES NEGOCIABLES. RELACION DE CERTIFICADOS DE PAGO``, each with
#: its hoja discriminator on the following line. Both were read as prose, so both
#: record bodies arrived unidentified and the design never read whole.
#:
#: The opening quotation mark is REQUIRED, and that is what separates a titled
#: annex record from a prose reference to a numbered annex ("... que figuran en
#: el anexo II de la Orden EHA/3496/2011"). Like the type-last shape above this
#: only STAGES a name; geometry decides whether a record starts.
_PDF_RECORD_ANEXO_HEADING_RE = re.compile(
    r"^ANEXO\s+[«“\"'](?P<title>[^»”\"']{4,120})",
    re.IGNORECASE,
)
#: A bare anexo IDENTIFIER standing alone on its line: modelo 100's 2014 edition
#: heads its extra record ``Anexo B.5``, with no quoted title for
#: :data:`_PDF_RECORD_ANEXO_HEADING_RE` to take and no ``DISEÑO DE REGISTRO``
#: for :data:`_PDF_ANEXO_PAGE_RECORD_RE`. Without it that record body restarts
#: at position 1 with no read identity and the design reports PARTIAL.
#:
#: Anchored to the WHOLE line and to the ``letter.digit`` shape, so a sentence
#: mentioning an anexo cannot match: the identifier must be all the line says.
_PDF_RECORD_BARE_ANEXO_RE = re.compile(r"^ANEXO\s+(?P<tag>[A-Z]\.\d{1,2})$", re.IGNORECASE)

#: A bare ``<modelo>-<page>`` tag standing alone on its line, which is how the
#: Modelo 100 PDFs head each of their record bodies -- "100-01", "100-02" and so
#: on, printed above the ``Nº Posic. Long. Tipo`` column header. It is the same
#: naming AEAT uses for the Modelo 714 workbook tabs ("714-01 Patrimonio"),
#: which arrive named because they are sheet tabs; in a PDF the tag is only a
#: line of text and nothing was reading it.
#:
#: Anchored to the WHOLE line, which is what keeps it from eating a position
#: range: a field row always carries a naturaleza and a description after its
#: range, so a line holding nothing but the tag is never one. Measured across
#: every bundled PDF design before adding it: six designs match, all six are
#: Modelo 100, and every occurrence names that design's own modelo. Like its
#: sibling above it only STAGES a name -- geometry still decides whether a
#: record starts -- so a tag appearing anywhere else stays inert.
_PDF_RECORD_MODELO_PAGE_TAG_RE = re.compile(r"^(?P<tag>\d{3}-\d{2})$")


@dataclass(frozen=True, slots=True)
class _PdfRow:
    source_row: int
    ordinal: str | None
    offset: int
    length: int
    type_code: str
    description: str


def _position_runs(positions: list[int]) -> str:
    """Render a sorted position list as compact ``a-b`` runs."""
    runs: list[str] = []
    start = previous = positions[0]
    for position in positions[1:]:
        if position == previous + 1:
            previous = position
            continue
        runs.append(str(start) if start == previous else f"{start}-{previous}")
        start = previous = position
    runs.append(str(start) if start == previous else f"{start}-{previous}")
    return ", ".join(runs[:6]) + (" and more" if len(runs) > 6 else "")


#: A naturaleza column holding only dash/underscore punctuation. AEAT uses it to
#: mean "no data type", i.e. filler positions.
_DASH_NATURALEZA_RE = re.compile(r"[-–_]+")

#: The fillers a dash naturaleza may describe. Anchored and word-bounded so
#: "BLANCOS." and "CEROS." match while a sentence merely opening with a similar
#: word does not.
_FILLER_DESCRIPTION_RE = re.compile(r"(?i)^(?:blancos?|ceros?)\b")


def _parse_pdf_row(line: str, source_row: int) -> _PdfRow | None:
    compact = _COMPACT_PDF_ROW_RE.match(line)
    if compact is not None:
        return _PdfRow(
            source_row=source_row,
            ordinal=compact.group("ordinal"),
            offset=int(compact.group("offset")),
            length=int(compact.group("length")),
            type_code=compact.group("type"),
            description=compact.group("text").strip(),
        )

    crlf = _COMPACT_PDF_CRLF_ROW_RE.match(line)
    if crlf is not None:
        return _PdfRow(
            source_row=source_row,
            ordinal=crlf.group("ordinal"),
            offset=int(crlf.group("offset")),
            length=2,
            type_code=crlf.group("type"),
            description=crlf.group("text").strip(),
        )

    narrative = _NARRATIVE_PDF_ROW_RE.match(line)
    if narrative is None:
        return None

    naturaleza = _naturaleza_or_none(narrative.group("type"))
    if (
        naturaleza is not None
        and _DASH_NATURALEZA_RE.fullmatch(narrative.group("type") or "")
        and not _FILLER_DESCRIPTION_RE.match(narrative.group("text").strip())
    ):
        # A BARE DASH in the naturaleza column means "no data type -- filler",
        # so the row's own description says which filler: BLANCOS/BLANCO or
        # CEROS. When it says anything else the dash is not a naturaleza at all
        # but the punctuation of an ENUMERATED PROSE ITEM inside a field's
        # description -- AEAT writes "1 - En el caso de que en el campo Clave
        # Tipo de Identificacion se haya consignado una 'C'..." -- and reading
        # that as a row invents a field at position 1.
        #
        # That invention is not a lost row, it is a lost RECORD: because the
        # fabricated offset restarts at 1, the extractor concluded a new record
        # body began mid-description and reported an unidentified record it
        # could not name. Modelo 181 lost one that way in each of its three
        # bundled editions.
        #
        # MEASURED before narrowing, across all 102 bundled design PDFs: 183
        # rows carry a bare-dash naturaleza. Every legitimate one describes
        # filler -- including eight that declare a SINGLE position rather than a
        # range (BLANCOS at 58, 81 and 500 across modelos 185, 270, 296 and
        # 347), which is why the absence of a range is NOT the discriminator and
        # rejecting on it would have dropped eight real rows. The six that
        # describe prose are exactly modelo 181's three editions, twice each.
        return None
    if naturaleza is None:
        # The line has a leading number but the token after it names no
        # naturaleza AEAT uses, so this is prose, not a position row. AEAT
        # routinely opens a field's DESCRIPTION with that field's own range
        # ("68-107 APELLIDOS Y NOMBRE: Se consignara el primer ..."), and
        # treating those as rows would invent positions wholesale -- measured
        # across the bundled corpus, 41 designs carry such prose.
        return None

    start = int(narrative.group("start"))
    end_group = narrative.group("end")
    end = int(end_group) if end_group is not None else start
    if end < start:
        raise RegistryValidationError(f"PDF row {source_row} has inverted position range {start}-{end}")
    return _PdfRow(
        source_row=source_row,
        ordinal=None,
        offset=start,
        length=end - start + 1,
        type_code=naturaleza,
        description=narrative.group("text").strip(),
    )


#: A row whose ORDINAL and POSITION were run together by the PDF text layer:
#: ``23 3 Num Modelo. OBLIGATORIO Constante "200"`` is ordinal 2 at position 3,
#: not ordinal 23. Three leading tokens where a row has four.
_GLUED_ORDINAL_POSITION_ROW_RE = re.compile(
    r"^\s*(?P<glued>\d{2,})\s+(?P<length>\d+)\s+(?P<type>An|Num|Tit|N|A)\.?\s+(?P<text>.+)$",
    re.IGNORECASE,
)


def _split_glued_ordinal_position(
    line: str,
    row_number: int,
    *,
    previous: _PdfFieldDraft | RecordDesignField | None,
) -> _PdfRow | None:
    """Recover a row whose ordinal and position were run together.

    Modelo 200's older editions lose the space after the ordinal for the three
    identifier rows of most records, writing ``23 3 Num``, ``36 3 An`` and
    ``49 1 An`` where AEAT declares ordinals 2, 3 and 4 at positions 3, 6 and 9.
    Thirty-two of the forty holed records in the 2010 edition report the
    resulting ``3-9`` gap, and it is the single most common hole shape in the
    corpus.

    A split is admitted ONLY when it is over-determined. ``23`` is read as
    ordinal 2 and position 3 only if BOTH the ordinal continues the previous
    row's ordinal by one AND the position resumes exactly where the previous row
    ended -- two independent facts that must agree, from a row already read
    rather than from a guess about this one. Any other split, or either
    constraint failing, returns ``None`` and the gap stays reported.

    This is why the shape was recorded and left alone when it was first met on
    modelo 100: there the glued row sits alone, with no read row before it to
    close the constraint, and ``59`` is as readable as ordinal 59. Nothing about
    the token changed -- what changed is that here the surrounding rows pin it.
    """
    if previous is None:
        return None
    match = _GLUED_ORDINAL_POSITION_ROW_RE.match(line)
    if match is None or _parse_pdf_row(line, row_number) is not None:
        return None
    glued = match.group("glued")
    expected_ordinal = None if previous.ordinal is None or not previous.ordinal.isdigit() else int(previous.ordinal) + 1
    expected_offset = previous.offset + previous.length
    if expected_ordinal is None or glued != f"{expected_ordinal}{expected_offset}":
        return None
    naturaleza = _naturaleza_or_none(match.group("type")) or match.group("type")
    return _PdfRow(
        source_row=row_number,
        ordinal=str(expected_ordinal),
        offset=expected_offset,
        length=int(match.group("length")),
        # The normalised naturaleza, matching the sibling constructor above. It was
        # computed here and then discarded in favour of the raw token, which is why
        # the assignment read as dead.
        type_code=naturaleza,
        description=match.group("text").strip(),
    )


def _unnamed_position_candidate(
    line: str,
    source_row: int,
    *,
    sheet: str = "",
    single_position_corrections: _SinglePositionCorrectionIndex | None = None,
) -> _PdfRow | None:
    """Return a position row whose naturaleza AEAT omitted, else ``None``.

    Deliberately NOT consulted by :func:`_parse_pdf_row`, which must keep
    refusing these outright: the same shape is overwhelmingly prose, because AEAT
    routinely opens a field's description with that field's own range, and 41
    bundled designs do. A candidate returned here is admitted only by
    :meth:`_PdfSheetDraft.fill_unread_gaps`, and only into a span no read row
    claims -- so it can add a field the sheet was missing entirely and can never
    displace, override or duplicate one that was read.

    """
    narrative = _NARRATIVE_PDF_ROW_RE.match(line)
    if narrative is None or _naturaleza_or_none(narrative.group("type")) is not None:
        return None
    start = int(narrative.group("start"))
    end_group = narrative.group("end")
    if end_group is None:
        # A single position with no naturaleza is indistinguishable from a
        # numbered prose sentence; only an explicit range is evidence of
        # extent, or a declared correction naming this exact position. See
        # :class:`RecordDesignSinglePositionCorrection` for why the declaration
        # is the only admissible substitute for the missing range.
        declared = (single_position_corrections or {}).get((sheet, start))
        if declared is None:
            return None
        return _PdfRow(
            source_row=source_row,
            ordinal=None,
            offset=start,
            length=1,
            type_code=declared.corrected_type,
            description=declared.description,
        )
    end = int(end_group)
    if end < start:
        return None
    text = (narrative.group("type") + " " + narrative.group("text")).strip()
    return _PdfRow(
        source_row=source_row,
        ordinal=None,
        offset=start,
        length=end - start + 1,
        type_code=ABSENT_NATURALEZA_TYPE_CODE,
        description=text,
    )


def _naturaleza_or_none(value: str) -> str | None:
    """Return the canonical naturaleza ``value`` names, or ``None`` if it names none.

    Matched on an ACCENT-STRIPPED stem rather than an exact spelling, because
    AEAT's designs are not spelled consistently and every unmatched spelling was
    a row dropped in silence. ``Numérica`` (feminine) and ``Alfanúmerico``
    (accent on the u, not the e) both ship in the bundled corpus and both read
    correctly here; before this, the first cost modelo 193 its positions
    182-192 and the second its 315-321, with ``is_complete`` still ``True``.

    Returning ``None`` rather than echoing the raw token back is the point: an
    unrecognised naturaleza must not become a field's type_code, because that is
    how a line of prose turns into a position.
    """
    raw = value.strip(" .")
    # The dash naturaleza is tested on the RAW token, before normalisation.
    # Stripping accents encodes to ASCII, which discards an en-dash entirely and
    # leaves an empty string, so testing it afterwards silently rejected every
    # genuine "226-487 - BLANCOS." row in the corpus.
    #
    # UNDERSCORES are the same rule drawn with a different character: Modelo 185
    # writes "58 ______ BLANCOS." where other designs write dashes. Both are an
    # empty naturaleza cell whose description says BLANCOS.
    if raw and set(raw) <= {"-", "–", "_"}:
        return "Blancos"
    normalised = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii").lower()
    if not normalised:
        return None
    # AEAT names the fill naturaleza in Spanish far more often than in English:
    # "58 BLANCO", "187-390 BLANCOS", "58-107 Blancos BLANCOS". Recognising only
    # the English "blank" and the dash form dropped every one of those rows, and
    # a dropped filler run is not cosmetic -- modelo 349 lost 204 bytes at
    # 187-390 and 32 at 147-178, which took its whole design below the
    # contiguity check and left a live layout unmeasurable.
    if normalised.startswith("blanco") or normalised == "blank":
        return "Blancos"
    # The ADJECTIVE stems, never the bare noun. "num" also prefixes
    # "NUMERO"/"NÚMERO", which opens a great many AEAT field NAMES
    # ("147-151 NÚMERO DE REGISTRO DEL FONDO DE PENSIONES:"). Reading that as a
    # naturaleza promoted the wrapped tail of the description to a top-level
    # field and pushed modelo 345's tipo 2 record 45 bytes past its declared
    # 500 -- inventing two positions inside spans the layout already writes,
    # which no record may declare because they would overlap.
    if normalised.startswith(("alfanumeric", "alphanumeric")):
        return "Alfanumérico"
    # "afabetic" is AEAT's own typo for "alfabético", shipped in modelo 156's
    # "36 - 75 Afabético APELLIDOS Y NOMBRE DEL AFILIADO O MUTUALISTA". Dropping
    # it left a 40-byte hole exactly where the taxpayer's name belongs. It is
    # listed explicitly rather than folded into a looser stem because a wider
    # prefix would start matching field-name words.
    if normalised.startswith(("alfabetic", "alphabetic", "afabetic")):
        return "Alfabético"
    if normalised.startswith("numeric"):
        return "Numérico"
    return None


def _pdf_page_name(line: str) -> str | None:
    match = _PDF_PAGE_RECORD_RE.match(line)
    if match is not None:
        return f"Pág. {match.group('page')}"
    if _PDF_ANEXO_PAGE_RECORD_RE.match(line) is not None:
        return "Anexo"
    return None


def _pdf_record_heading_name(line: str) -> str | None:
    match = _PDF_RECORD_HEADING_RE.match(line) or _PDF_RECORD_HEADING_REVERSED_RE.match(line)
    if match is None:
        return None
    title = _normalise_pdf_sheet_name(match.group("title"))
    return f"Tipo {match.group('record')} - {title}"


def _pdf_candidate_record_name(line: str) -> str | None:
    """Return the record name a line MIGHT be heading, for geometry to confirm.

    Separate from :func:`_pdf_record_heading_name` precisely because it is not
    trusted on its own: see :data:`_PDF_RECORD_HEADING_TYPE_LAST_RE` for why
    this word order cannot split a record on the text alone.
    """
    tag = _PDF_RECORD_MODELO_PAGE_TAG_RE.match(line.strip())
    if tag is not None:
        tag_value = tag.group("tag")
        assert isinstance(tag_value, str)
        return tag_value
    anexo = _PDF_RECORD_ANEXO_HEADING_RE.match(line.strip())
    if anexo is not None:
        return "Anexo - " + _normalise_pdf_sheet_name(anexo.group("title"))
    bare_anexo = _PDF_RECORD_BARE_ANEXO_RE.match(line.strip())
    if bare_anexo is not None:
        bare_anexo_tag = bare_anexo.group("tag")
        assert isinstance(bare_anexo_tag, str)
        return "Anexo " + bare_anexo_tag.upper()
    match = _PDF_RECORD_HEADING_TYPE_LAST_RE.match(line)
    if match is None:
        return None
    title = _normalise_pdf_sheet_name(match.group("title"))
    return f"Tipo {match.group('record')} - {title}"


# The column-header spellings AEAT prints across diseño-de-registro PDFs.
# Each variant is a list of required column groups; a group holds the
# interchangeable spellings of one column, so a line matches a variant when
# every group contributes at least one token.
_PDF_HEADER_VARIANTS: Final[tuple[tuple[tuple[str, ...], ...], ...]] = (
    (("POSICIONES", "POSICIÓN"), ("NATURALEZA",), ("DESCRIPCI",)),
    (("Nº POSIC",), ("LON",), ("TIPO",), ("DESCRIPCI",)),
    (("POSITIONS",), ("NATURE",), ("DESCRIPTION",)),
)


def _is_pdf_header(line: str) -> bool:
    normalised = line.upper()
    return any(
        all(any(token in normalised for token in column) for column in variant) for variant in _PDF_HEADER_VARIANTS
    )


def _is_pdf_footer(line: str) -> bool:
    return bool(
        re.match(r"^P[áa]gina\s+\d+\s+de\s+\d+$", line, re.IGNORECASE)
        or re.match(r"^Ejercicio\s+\d{4}(?:\s+\d+)?$", line, re.IGNORECASE)
        or re.match(r"^\d+$", line),
    )


def _is_pdf_page_heading(line: str) -> bool:
    return bool(
        line.startswith("Modelo ")
        or line.startswith("Agencia Tributaria")
        or line.startswith("Declaración Informativa")
        or line.startswith("Declaración informativa")
        or line.startswith("determinados ")
        or line.startswith("determinadas ")
        or line == "Resumen anual"
        or line == "MODELO 193"
        or line == "MODELO 190"
        or line == "DISEÑOS DE REGISTRO",
    )


def _looks_like_title_continuation(line: str) -> bool:
    letters = [char for char in line if char.isalpha()]
    if not letters:
        return False
    return not any(char.islower() for char in letters)


def _clean_pdf_line(line: str) -> str:
    return " ".join(line.strip().split())


def _join_pdf_parts(parts: list[str]) -> str:
    return " ".join(part.strip() for part in parts if part.strip())


def _normalise_pdf_sheet_name(value: str) -> str:
    return _join_pdf_parts([value.replace(".", " ").strip()]).strip(". ").title()


#: :data:`_VISUAL_CHART_TYPE_CODE`, which marks a design that has no type column
#: at all: here the column exists and this one row is blank in it. Never a
#: guess -- an inferred "Alfanumerico" would be indistinguishable from one AEAT
#: actually printed.
ABSENT_NATURALEZA_TYPE_CODE = "No consta"
