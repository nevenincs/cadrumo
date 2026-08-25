"""Registry-build gate: an authored fixed-width layout must cover its official design.

:func:`~._validate_export_exemption.validate_export_exemption_declarations`
refuses a revision that declares NO export layout. It cannot tell a complete
layout from a tenth of one, because it never reads the official record design:
it asks only whether the registry declared *something*. Modelo 714 is the worked
case -- five revisions each declaring 127 fields across 10 records against a
bundled AEAT design carrying 1,200+ positions across 12 records, two of which
(the ``714-00`` file envelope and ``714-Ingreso o Devolución``, which carries
forma de pago, IBAN and importe del ingreso) are not authored at all. It passed.
A filing generated from it would carry a blank NIF, a blank name, a blank IBAN
and a blank resumen block behind a perfectly valid digest.

This module closes that. For every revision declaring a fixed-width export
layout, it reads the official bundled design that layout itself cites and
refuses when a position the design requires has no authored slot.

What counts as required, and why it is read from the design
-----------------------------------------------------------

A fixed-width record is CONTIGUOUS: AEAT declares its whole byte extent and the
file carries every byte of it. So a position the layout does not declare is not
"optional", it is a datum the application can never write -- the slot emits fill
and the operator gets a structurally thin record behind a valid digest. The
default is therefore that every position is required, and omissibility must be
something the DESIGN says, never something a per-modelo allowlist asserts:

* a position AEAT marks ``OBLIGATORIO`` in its own obligatoriness column is
  required, and that marking overrides every omissibility signal below;
* a position AEAT reserves for itself ("Reservado para la Administración",
  "RESERVADO PARA LA A.E.A.T.") is omissible -- the filer must not write it;
* a position AEAT declares as fill ("BLANCOS", "Sin contenido", a blank
  constant) is omissible -- there is no datum there.

Where AEAT *desglosa* a printed field into sub-fields, the SUB-FIELDS are the
positions and the parent's span is not one; each sub-field is judged for
omissibility on its own. See :func:`_required_positions` for why requiring the
parent inverted the incentive on Modelo 576.

Everything else is required. Measured over the eighteen bundled designs backing
a fixed-width layout: 570 positions marked obligatorio, 266 administration-
reserved, 29 declared fill, 8,297 ordinary data positions.

What counts as written: bytes, carrying data
--------------------------------------------

Coverage is measured by BYTE EXTENT, not by ``(offset, length)`` identity. The
design's grouping of bytes into rows and the layout's grouping of the same bytes
into fields are independent, and both are legitimate; demanding they agree made
three design sheets literally unsatisfiable. And a ``filler`` never covers a
required position: it emits blanks, so counting it hid 185 positions the
operator's filing leaves empty -- including modelos the gate reported COMPLETE.
:func:`_covers` carries the evidence for both halves.

Joining an authored record to its design sheet
----------------------------------------------

The registry declares no link between an authored ``ExportRecordDefinition`` and
the design sheet it renders, and the two vocabularies do not correspond: Modelo
714 writes ``record_type = "714-01"`` against a sheet named
``714-01 Patrimonio``, Modelo 390 writes ``page_01`` against ``Pág. 1``, Modelo
145 writes ``communication`` against ``PDF record design``, and Modelo 720's
records carry no discriminating name at all. **Matching those by name would be
inventing a mapping**, and a wrong mapping produces confident refusals against
positions the layout does write.

So the join is made on CONTENT, which is where a fixed-width record's identity
actually lives: AEAT declares each record's discriminating constants ("Constante
``<T``", "Constante ``714``", "Constante ``01000``") at exact offsets, and the
authored record declares the same bytes as ``literal`` fields. A record joins a
sheet when their declared constants agree at shared coordinates and contradict
at none, and the sheet takes the record whose agreement count is a unique
maximum.

**Where the join cannot be established the check does not guess and does not
pass.** It falls back to asking whether ANY record of the layout writes the
coordinate -- a strictly weaker question that can only under-report, never
over-report -- and the refusal says which mode produced it, so a reader is never
left thinking a fallback verdict is a per-record one. This is why an
unjoinable design still yields a usable, honest verdict rather than an
authoritative-looking wrong one.

A partial read never produces a pass
------------------------------------

:func:`~._record_design.extract_record_design` returns what it could read
alongside what it could not, and
:meth:`~._record_design_schema.RecordDesignExtraction.accept_partial` tolerates
the difference. The off-load-path coverage inventory in
``_record_design_coverage`` deliberately takes that tolerance, and its own
docstring records why: tightening it would make Modelo 232's legitimately
skipped ``TABLAS`` lookup tab refuse the whole modelo.

**This gate does not share that tolerance and does not need to.** It calls
:meth:`~._record_design_schema.RecordDesignExtraction.require_complete` and
converts the refusal into its own diagnostic, because a design whose record body
was skipped understates the modelo and would hand back an inflated coverage
figure that nothing downstream could tell from a real one -- the exact false
green this gate exists to remove. Modelo 232 is unaffected because it declares
no fixed-width layout and never reaches here; the tolerance in the advisory
instrument is left exactly as it was, for the consumer whose blast radius it was
written about.

An unreachable design binary is likewise a refusal, not a skip. The corpus
binaries live in the mandatory ``cadrumo_data`` companion namespace, so
"unreadable" is a broken installation rather than a supported configuration, and
reporting completeness over a file nobody read is the one outcome this module
must never produce.

See Also:
    :func:`~._validate_export_exemption.validate_export_exemption_declarations`
        The sibling that refuses a revision declaring no layout at all.
    :func:`~._record_design.extract_record_design`
        The official-design reader, and the completeness contract it returns.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from ....core import ExportLayoutFormat
from ....core.resources import resolve_corpus_binary
from .._export_field_kind import CasillaFieldKind
from .export import derive_export_layouts_from_bindings
from .record_design import _naturaleza_or_none, extract_record_design
from ._record_design_schema import RecordDesignField, RecordDesignSheet
from .schema import (
    AuxiliaryEnvelopeHeaderDefinition,
    ExportFieldDefinition,
    ExportLayoutDefinition,
    ExportRecordDefinition,
    FilingEnvelopeDefinition,
    ModeloRevision,
    SourceReference,
)
from .errors import RegistryValidationError

#: AEAT's own obligatoriness marking, read from the column its designs head
#: ``Oblig.`` (which the parser lands in ``RecordDesignField.validation``).
#: Matched with word boundaries so a prose "no obligatorio" elsewhere in a
#: validation cell is not mistaken for the marking itself.
_OBLIGATORIO: Final = re.compile(r"\bOBLIGATORI[OA]\b", re.IGNORECASE)

#: The word by which AEAT names a slot it reserves. Necessary but NOT sufficient
#: on its own -- see :func:`_administration_reserved` for the two signals that
#: decide what the word means on a given row.
#:
#: Read from the field's DESCRIPTION only -- never from its validation or
#: contenido prose, which is where the word appears innocently. Modelo 720's
#: ``TIPO DE DERECHO REAL SOBRE INMUEBLE`` (25 bytes of taxpayer data) explains
#: itself with "se deberá indicar en el espacio reservado", and scanning that
#: prose excused a real datum from the check -- a silent pass, which is the one
#: direction this gate must never fail in.
_RESERVED_WORD: Final = re.compile(r"\breservad[oa]s?\b", re.IGNORECASE)

#: AEAT naming the reservation's OWNER: "RESERVADO PARA LA A.E.A.T.", "Reservado
#: para la Administración", "Reservado para el sello electrónico de la AEAT",
#: "Reservado AEAT". This is the authority stating whose bytes these are, so it
#: settles the row outright.
#:
#: ``[^.;]`` is load-bearing: it cannot cross a sentence break, which is what
#: separates naming an owner from using "Reservado" as a bare label in front of
#: an unrelated clause. The window is wide enough for "para el sello electrónico
#: de la " to reach its ``AEAT``.
_RESERVED_FOR_ADMINISTRATION: Final = re.compile(
    r"\breservad[oa]s?\b[^.;]{0,40}?\b(?:administraci[oó]n|a\.?e\.?a\.?t\.?)\b",
    re.IGNORECASE,
)

#: AEAT's tick notation for a mark the FILER writes -- a quoted ``X``.
#:
#: This is the signal that a "Reservado"-labelled row holds a datum after all.
#: It is deliberately the quoted ``X`` and not any value set: Modelo 131
#: ``@627+1`` and Modelo 303 ``@840+1``/``@841+1`` declare ``"0" o blanco`` on
#: rows that ARE the administración's, and ``"0"`` is an AEAT-side marker rather
#: than a filer tick. Those three are settled by the owner rule above regardless,
#: so this pattern never has to adjudicate them.
_FILER_MARK: Final = re.compile(r"[\"'«“‘]\s*X\s*[\"'»”’]", re.IGNORECASE)

#: A position AEAT declares as fill rather than as a datum. Anchored to the whole
#: cell: a description that merely MENTIONS blancos while carrying a real field
#: ("Rellenar con blancos si no hay importe") still holds a datum, and matching
#: it loosely would excuse a slot that carries one.
#:
#: The leading article is part of the spelling. ``^\W*`` consumes only
#: non-word characters, so it could not reach past the ``E`` of "En blanco" and
#: 760 positions AEAT declares as holding NO datum were classed required --
#: 663 of them Modelo 200's. Harmless while a filler counted as written; once a
#: filler no longer covers a required position (see :func:`_covers`), the only
#: way to satisfy such a position became writing a datum AEAT does not want,
#: which is the gate paying for the wrong shape again.
#:
#: The trailing ``$`` is LOAD-BEARING and must not be relaxed to catch the
#: wider population. 2,245 positions merely mention blanco, and the bulk are
#: value sets where blank is one permitted value of a real datum -- ``"S" o
#: blanco``, ``X o blanco``, ``"0" - blanco, "1" - Si``. Every one of those is a
#: position the filer MUST be able to write, so excusing them would be a silent
#: pass across hundreds of positions. Only the leading-article gap is fixed.
_DECLARED_FILL: Final = re.compile(
    r"^\W*(?:constante\W{0,3})?(?:en\s+)?(?:blancos?|sin\s+contenido|no\s+utilizad[oa]s?|libre)\W*$",
    re.IGNORECASE,
)

#: AEAT's declaration that a position holds a fixed value rather than a datum.
#: Read from any cell of the row, because AEAT splits the declaration across
#: cells as often as it keeps it in one: Modelo 714's ``714-02`` writes
#: ``Constante "<T"`` in a single ``Contenido`` cell, while Modelo 111 and
#: Modelo 714's own ``714-00`` envelope put ``Constante.`` in ``Descripción``
#: and ``"<T"`` in ``Contenido``. Modelo 360's design declares its identifier
#: constants without the word at all ("Inicio del identificador de modelo y
#: página obligatorio <T360010>"), so the identifier-block vocabulary is
#: accepted alongside -- those phrases name the fixed record-delimiter cells
#: and nothing else in any bundled design.
_CONSTANT_DECLARATION: Final = re.compile(
    r"[Cc]onstante|identificador de modelo y página|fin de registro",
)

#: The quoted value itself (``"714"``, ``'1'``, ``«720»``). ONLY the quoted
#: spelling is read: an unquoted "Constante 2021" or "Constante. Blanco" does
#: not delimit its own value, and guessing where the value ends would put a
#: wrong anchor into the join.
_QUOTED_VALUE: Final = re.compile(
    "[\"'«“‘]([^\"'»«”’‘“]{1,40})[\"'»”’]",
)

#: The identifier-block constant, read for cells whose row carries the
#: identifier vocabulary (``<T360010>``, ``</T360020>``): the angle-bracket
#: spelling AEAT prints without the word "Constante". Bounded to the ``<T``
#: marker so a stray quoted word in the same cell's nota text cannot become
#: a wrong anchor.
_IDENTIFIER_VALUE: Final = re.compile(r"</?T\d{1,10}>")

#: The identifier-block row vocabulary: the phrases AEAT uses for the fixed
#: record-delimiter cells, which is where ``<T`` identifiers appear.
_IDENTIFIER_VOCABULARY: Final = re.compile(r"identificador de modelo y página|fin de registro")

#: How many missing positions one sheet enumerates before the message says how
#: many more there are. The bundled design is the exhaustive worklist; this
#: message is the entry point into it, and a refusal listing a thousand
#: coordinates is one nobody reads.
_ENUMERATED_PER_RECORD: Final = 8


@dataclass(frozen=True, slots=True)
class _RequiredPosition:
    """One official position an authored layout must be able to write."""

    sheet: str
    offset: int
    length: int
    description: str
    obligatorio: bool
    #: AEAT's own ``Contenido`` cell declares this position's content to be
    #: blanks, while its obligatoriness column still demands the position. An
    #: obligatory BLANK: the field must be emitted so the record stays
    #: contiguous, and a ``filler`` is the only faithful way to emit it.
    declared_blank: bool


def _administration_reserved(field: RecordDesignField) -> bool:
    """Return whether AEAT reserves this position for itself.

    The word "Reservado" alone does not settle it, and reading it as though it
    did was a real defect: Modelo 111's ``@552+1`` is described ``Reservado.
    Administración presentando declaración de Colegio Concertado (CC)`` and
    declares ``"X" o blanco``. That is a mark the PRESENTER writes -- Spain's
    *pago delegado* arrangement, where an education Administración presents the
    Modelo 111 for a state-subsidised school -- so the row was excused from
    coverage while the layout correctly wrote a datum there, and the
    reserved-span rule then reported that datum as trespassing on AEAT's bytes.
    The tree was internally inconsistent because this predicate was.

    Two signals decide it, in order:

    * AEAT naming the OWNER ("Reservado para la Administración", "RESERVADO PARA
      LA A.E.A.T.", "Reservado AEAT") settles the row as reserved whatever its
      contenido says. Modelo 131 ``@627+1`` and Modelo 303 ``@840+1`` are the
      reason this comes first: they are the administración's AND declare a value
      set, so a content-led rule would wrongly hand them to the filer.
    * Otherwise AEAT's filer tick ``"X"`` means the row holds a datum despite the
      label -- read from ``Contenido``, or from the description where none exists.

    A "Reservado"-labelled row that names no owner and declares no filer tick
    stays reserved -- Modelo 840's forty-odd ``Reservado. Apart. VII: Cuota
    [103]`` rows, which carry no contenido at all, are the population that
    depends on that fallback.

    Measured over the bundled corpus: 2,953 rows carry the word, and exactly one
    POSITION -- Modelo 111's Colegio Concertado tick, in the 2016/2019 xlsx
    ``Contenido`` and in the 2012 PDF's description -- is reclassified.
    """
    description = field.description or ""
    if not _RESERVED_WORD.search(description):
        return False
    if _RESERVED_FOR_ADMINISTRATION.search(description):
        return True
    return not _FILER_MARK.search((field.content or "").strip() or description)


#: A ``Nota N`` citation inside a field's own naming cell.
_NOTE_CITATION = re.compile(
    r"\(\s*(?:Nota\s*(?P<ordinal>\d{1,2})|(?P<symbol>[*]{1,3}))\s*\)",
    re.IGNORECASE,
)

#: The same citation standing alone in a field's CONTENT cell, where some
#: designs put it instead of in the naming cell. Anchored whole-cell.
_BARE_NOTE_CITATION = re.compile(
    r"\(?\s*(?:Nota\s*(?P<ordinal>\d{1,2})|(?P<symbol>[*]{1,3}))\s*\)?",
    re.IGNORECASE,
)

#: The note body that delegates a position to the software house. AEAT prints
#: this verbatim beneath the field table: "A cumplimentar por las entidades
#: desarrolladoras (EEDD)". Matched on the DELEGATION, never on the bare note
#: citation -- one design's Nota 1 says this, another's says something else
#: entirely, so a citation alone can never be an omissibility signal.
_EEDD_DELEGATED = re.compile(r"entidades\s+desarrolladoras|EEDD", re.IGNORECASE)


def _eedd_delegated_reason(field: RecordDesignField, sheet: RecordDesignSheet) -> str | None:
    """Return a reason when the design delegates this position to the EEDD.

    Two independent signals must agree: the field's own naming cell cites a
    note, and THAT note's body -- as printed on the same sheet -- delegates the
    position to the entidad desarrolladora. A position identifying the software
    house that produced the file has no value this application could write:
    Cadrumo holds no EEDD registration, so writing one would invent a
    regulatory identity and writing blank would assert an empty EEDD rather
    than an absent one.
    """
    citation = _NOTE_CITATION.search(field.description or "")
    if citation is None:
        # Several designs put the citation in the CONTENT column instead of the
        # naming cell, unparenthesised: m131 and m390 print "Versión del
        # Programa" with a content cell of exactly "Nota 1". The whole cell must
        # be the citation -- a note referenced inside prose is discussion, not a
        # declaration about this position.
        citation = _BARE_NOTE_CITATION.fullmatch((field.content or "").strip())
    if citation is None:
        return None
    marker = citation.group("ordinal") or citation.group("symbol") or ""
    body = sheet.note_body(marker)
    if body is None:
        # AEAT does not always type the marker on the definition row it prints.
        # An unmarked delegation body is accepted only when the sheet prints
        # exactly one, so the mapping from citation to body stays unambiguous.
        body = sheet.note_body("")
    if body is None or not _EEDD_DELEGATED.search(body):
        return None
    return "delegated to the entidad desarrolladora by the design's own footnote"


#: AEAT naming the electronic-seal slot in the cell that NAMES the field.
#: Necessary but not sufficient on its own -- see
#: :func:`_aeat_program_sealed_reason` for the second signal that decides it.
_SELLO_ELECTRONICO_NAMED: Final = re.compile(r"\bsello\s+electr[oó]nico\b", re.IGNORECASE)

#: AEAT delegating a position to its OWN programs: "que será cumplimentado
#: exclusivamente por los programas oficiales de la A.E.A.T.". Read from the
#: CONTENT cell, because that is where these designs put the delegation while
#: the description carries only the bare field name.
#:
#: ``[^.;]`` bounds it to one clause for the same reason
#: :data:`_RESERVED_FOR_ADMINISTRATION` does: it must not reach across a
#: sentence break and pair a "cumplimentado por" from one statement with an
#: "AEAT" from the next.
_AEAT_PROGRAM_COMPLETED: Final = re.compile(
    r"cumplimentad[oa]\s+(?:[^.;]{0,30}?\s+)?por\s+(?:los\s+)?programas[^.;]{0,40}?a\.?e\.?a\.?t\.?",
    re.IGNORECASE,
)


def _aeat_program_sealed_reason(field: RecordDesignField) -> str | None:
    """Return a reason when the design reserves this slot for AEAT's own seal.

    Two independent signals must agree, the same shape
    :func:`_eedd_delegated_reason` uses: the field's own naming cell calls it the
    ``sello electrónico``, and its content cell delegates completion to AEAT's
    official programs. Neither alone decides it -- "sello electrónico" appears
    in prose about other slots, and "cumplimentado por los programas" is not by
    itself a statement about whose bytes these are.

    Separate from :func:`_administration_reserved` rather than a widening of it,
    because that predicate deliberately reads the DESCRIPTION only: Modelo 720's
    ``TIPO DE DERECHO REAL SOBRE INMUEBLE`` carries 25 bytes of taxpayer data and
    explains itself with "en el espacio reservado", so admitting content prose
    there once excused a real datum. These designs put the delegation in content
    while naming only ``SELLO ELECTRÓNICO`` in the description, so the pairing is
    what makes reading content safe here.

    Measured across the bundled corpus: 96 positions name the sello, 78 of them
    already omissible through the owner rule, and exactly 18 are reclassified by
    this one -- every one a declarante-record seal slot in Modelos 180, 182, 184,
    188, 190, 193, 194, 296 and 347. Modelo 347's 2008 design names the sello but
    carries a chart-geometry placeholder instead of the delegation, and correctly
    stays required.
    """
    if not _SELLO_ELECTRONICO_NAMED.search(field.description or ""):
        return None
    if not _AEAT_PROGRAM_COMPLETED.search(field.content or ""):
        return None
    return "reserved for AEAT's own programs by the design's own content declaration"


def _omissible_reason(field: RecordDesignField, sheet: RecordDesignSheet | None = None) -> str | None:
    """Return why the DESIGN says this position may go unwritten, else ``None``.

    Obligatoriness wins outright: a position AEAT marks ``OBLIGATORIO`` is
    required even when its description also mentions reserved space or fill,
    because the marking is the authority's direct statement about that slot and
    the prose around it is not.

    Every signal is read from the cell that NAMES the field, never from the
    explanatory prose beside it. An omissibility signal is the only thing here
    that can turn a real gap into a pass, so it is deliberately the hardest
    thing to trip.
    """
    if _OBLIGATORIO.search(field.validation or ""):
        return None
    if _administration_reserved(field):
        return "reserved for the Administración"
    if (sealed := _aeat_program_sealed_reason(field)) is not None:
        return sealed
    for text in (field.description, field.content):
        if text and _DECLARED_FILL.match(text.strip()):
            return "declared fill"
    if _declared_fill_naturaleza(field):
        return "declared fill by naturaleza"
    if sheet is not None:
        return _eedd_delegated_reason(field, sheet)
    return None


def _declared_fill_naturaleza(field: RecordDesignField) -> bool:
    """Whether AEAT's NATURALEZA column types this position as fill.

    Read from the typed naturaleza cell, not from prose, which is why it belongs
    beside the other signals rather than as a widening of :data:`_DECLARED_FILL`.
    That pattern reads the DESCRIPTION and is deliberately anchored, because the
    same words appear inside real data positions -- ``"X o blanco"``,
    ``'"0" - blanco, "1" - Si'`` -- and excusing those would pass hundreds of
    slots in silence. A naturaleza of ``Blancos`` states no choice: it is the
    design typing the field itself, the same column that says ``Numerico`` or
    ``Alfanumerico`` everywhere else.

    Needed because the description cell is not reliably the fill word even when
    the naturaleza is. Measured across every bundled design, 152 positions carry
    a ``Blancos`` naturaleza and 146 were already omissible through their
    description; the SIX this admits are every one a genuine fill run whose
    description simply says it differently -- Modelo 194's ``CEROS.`` twice,
    Modelo 296's ``BLANCO MODELO 296``, Modelo 604's English ``BLANK`` twice, and
    Modelo 349's ``@236+265``, whose description cell caught the page footnote
    ``* Todos los importes seran positivos.`` instead of the fill word.

    That last one is why this is a correctness fix and not a convenience:
    Modelo 349's trailing 265 bytes are typed ``Blancos`` and run to the record's
    declared 500, so the gate was demanding real taxpayer data for a span the
    design fills with blanks -- a requirement no correct layout can satisfy,
    which is the incentive inversion this module exists to remove.

    ``OBLIGATORIO`` still wins outright: the caller checks it first, so a
    position AEAT marks obligatorio stays required whatever its naturaleza says.
    """
    return _naturaleza_or_none(field.type_code or "") == "Blancos"


def _position(sheet_name: str, field: RecordDesignField) -> _RequiredPosition:
    description_tail = re.split(r"[.;:]\s*", field.description.strip())[-1] if field.description else ""
    return _RequiredPosition(
        sheet=sheet_name,
        offset=field.offset,
        length=field.length,
        description=field.description,
        obligatorio=bool(_OBLIGATORIO.search(field.validation or "")),
        declared_blank=bool(
            (field.content and _DECLARED_FILL.match(field.content.strip()))
            or (description_tail and _DECLARED_FILL.match(description_tail))
        ),
    )


def _required_positions(sheet: RecordDesignSheet) -> tuple[_RequiredPosition, ...]:
    """Return every position of ``sheet`` an authored layout must be able to write.

    Where AEAT *desglosa* a printed field into sub-fields, THE SUB-FIELDS ARE THE
    POSITIONS and the parent's own span is not one. The parent is a printed
    grouping whose extent
    :attr:`~._record_design_schema.RecordDesignField.components` deliberately
    leaves intact for geometry consumers; asking a layout to write the group as a
    single position asks it to write the wrong thing.

    Modelo 576 is the worked case. Row ``19`` spans ``@514+40`` and says so in
    prose -- "Este campo se desglosa en los 8 campos siguientes" -- over
    ``19.1``..``19.8``, one of which (``19.3``, ``@520+8``) is RESERVADO para
    AEAT. Requiring the parent inverted the incentive at exactly the wrong
    place: a layout authoring the eight leaves faithfully was refused at 41/42
    because none of them sits at ``(514, 40)``, while a single 40-byte blob
    satisfied the check and wrote taxpayer data straight across AEAT's own
    reserved bytes. The gate rewarded the shape that corrupts the filing.

    Omissibility is judged per sub-field, so ``19.3`` drops out and the seven
    real data slots stay required. A parent the design ITSELF declares omissible
    takes its whole span out with it: nothing inside a span reserved for the
    Administración is a datum the filer may write.
    """
    positions: list[_RequiredPosition] = []
    for field in sheet.fields:
        if _omissible_reason(field, sheet) is not None:
            continue
        if field.components:
            positions.extend(
                _position(sheet.name, component)
                for component in field.components
                if _omissible_reason(component, sheet) is None
            )
            continue
        positions.append(_position(sheet.name, field))
    return tuple(positions)


def _sheet_constants(sheet: RecordDesignSheet) -> dict[tuple[int, int], str]:
    """Return the discriminating constants AEAT declares, by exact coordinate.

    The declaration and its value are read across the ROW, not within one cell.
    AEAT writes them together as often as it splits them -- ``Constante "<T"``
    in one ``Contenido`` cell, versus ``Constante.`` in ``Descripción`` beside
    ``"<T"`` in ``Contenido`` -- and requiring them adjacent silently emptied
    the constant set for whole modelos. A sheet with no constants cannot be
    joined to its authored record at all, so the check quietly degraded to the
    weaker layout-wide question for Modelo 111, 115, 117, 123, 126, 128, 130,
    202, 220, 222, 303, 308, 309, 322, 341, 353 and Modelo 714's own envelope.
    Nothing announced the downgrade, which is what made it durable.

    Both halves stay required. The word alone anchors nothing, and an unquoted
    value does not delimit itself; demanding a quoted value in a row AEAT marks
    ``Constante`` is what keeps an ENUMERATION ("01" ... "12" o "1T") -- which
    would produce a WRONG join rather than a missing one -- out of the set.
    """
    constants: dict[tuple[int, int], str] = {}
    for field in sheet.fields:
        cells = (field.content, field.description)
        # Identifier-block rows (``<T360010>``-style) are read ONLY through the
        # identifier pattern: the same row's CONTENT cell can carry pages of
        # nota prose whose first quoted word would otherwise become a wrong
        # anchor (Modelo 360's fin-de-registro cells showed exactly that).
        if any(text and _IDENTIFIER_VOCABULARY.search(text) for text in cells):
            for text in cells:
                if not text:
                    continue
                identifier = _IDENTIFIER_VALUE.search(text)
                if identifier is not None:
                    constants[(field.offset, field.length)] = identifier.group(0).strip()
                    break
            continue
        if not any(text and _CONSTANT_DECLARATION.search(text) for text in cells):
            continue
        for text in cells:
            if not text:
                continue
            matched = _QUOTED_VALUE.search(text)
            if matched is not None:
                constants[(field.offset, field.length)] = matched.group(1).strip()
                break
    return constants


def _record_literals(record: ExportRecordDefinition) -> dict[tuple[int, int], str]:
    return {
        (field.offset, field.length): field.literal
        for field in record.fields
        if field.kind is CasillaFieldKind.LITERAL
        and field.literal is not None
        and field.offset is not None
        and field.length is not None
    }


def _record_written_positions(record: ExportRecordDefinition) -> set[tuple[int, int]]:
    return {
        (field.offset, field.length) for field in record.fields if field.offset is not None and field.length is not None
    }


def _written_bytes(fields: Iterable[ExportFieldDefinition], *, data_only: bool) -> set[int]:
    """Return every byte ``fields`` writes, optionally counting only real data.

    ``data_only`` drops :attr:`~.CasillaFieldKind.FILLER` slots. A filler emits
    blanks, so a required position it "covers" is a position the operator's
    filing leaves empty -- see :func:`_covers` for why that must not count.
    """
    written: set[int] = set()
    for field in fields:
        if field.offset is None or field.length is None:
            continue
        if data_only and field.kind is CasillaFieldKind.FILLER:
            continue
        written.update(range(field.offset, field.offset + field.length))
    return written


def _administration_reserved_bytes(sheet: RecordDesignSheet) -> dict[int, str]:
    """Return every byte AEAT reserves for itself, mapped to the row that says so.

    Walks sub-fields as well as top-level rows, because AEAT reserves inside a
    desglose too: Modelo 576's ``19.3 @520+8 RESERVADO para AEAT`` sits between
    seven real data sub-fields of one printed row.
    """
    reserved: dict[int, str] = {}
    for field in sheet.fields:
        for candidate in (field, *field.components):
            if _OBLIGATORIO.search(candidate.validation or ""):
                continue
            if not _administration_reserved(candidate):
                continue
            for byte in range(candidate.offset, candidate.offset + candidate.length):
                reserved[byte] = candidate.description
    return reserved


def _reserved_write_failures(
    sheet: RecordDesignSheet,
    fields: Iterable[ExportFieldDefinition],
) -> list[str]:
    """Return every authored field that writes taxpayer data into reserved bytes.

    Byte-extent coverage asks whether a required position's bytes are written,
    which is the right question and an incomplete one: one wide field satisfies
    every position it spans, INCLUDING the administración's own bytes in
    between. Modelo 576 is the worked case -- a single 40-byte field over row
    19 covers all seven of its real sub-fields and writes straight across
    ``19.3``, the eight bytes AEAT reserves. Under coverage alone that reads as
    complete, which is the same incentive inversion, one layer down, that
    requiring the parent span produced in the first place.

    A ``filler`` there is CORRECT and is not reported: the record is contiguous,
    so those bytes must still be emitted, as blanks. The rule is that a field
    carrying a value may not claim bytes the design says belong to AEAT -- never
    that fillers are suspect.
    """
    reserved = _administration_reserved_bytes(sheet)
    if not reserved:
        return []
    failures: list[str] = []
    for field in fields:
        if field.offset is None or field.length is None or field.kind is CasillaFieldKind.FILLER:
            continue
        clash = sorted(byte for byte in range(field.offset, field.offset + field.length) if byte in reserved)
        if clash:
            failures.append(
                f"field {field.id!r} (@{field.offset}+{field.length}) writes data into "
                f"@{clash[0]}..{clash[-1]}, which the design reserves for the Administración "
                f"({reserved[clash[0]]!r}); emit those bytes as a filler instead"
            )
    return failures


def _covers(position: _RequiredPosition, data_bytes: set[int], fill_bytes: set[int]) -> bool:
    """Whether the layout can really write every byte of ``position``.

    Coverage is measured by BYTE EXTENT, not by ``(offset, length)`` identity,
    because the design's grouping of bytes into rows and the layout's grouping
    of the same bytes into fields are independent and both are legitimate. AEAT
    declares one 193-byte ``DIRECCIÓN DEL INMUEBLE`` where the application holds
    fifteen separate facts, and declares eight sub-positions where Modelo 576
    holds one span; matching coordinates demanded that the two groupings agree,
    which they never had to.

    Insisting on identity was not merely imprecise, it was UNSATISFIABLE for
    three design sheets. Modelo 280's, Modelo 190's and Modelo 349's tipo-2
    sheets each declare a parent row AND its sub-rows, so identity demanded
    overlapping byte ranges -- and
    :func:`~._export._reject_overlapping_ranges` forbids any record from
    declaring two overlapping fields. No correct layout could satisfy both
    halves. Modelo 280 is authored complete against its official design and was
    reported at 33/53, every one of the twenty "unwritten" positions a
    coordinate it does in fact write.

    A FILLER never covers a required position. The gate counted one before, and
    across the bundled tree that hid 185 positions the operator's filing emits
    as blanks -- Modelo 270 reported 36/36 complete while blanking ``NÚMERO
    IDENTIFICATIVO DE LA DECLARACIÓN``, Modelo 341 33/33 while blanking
    ``SWIFT``, Modelo 190 96.2% against a real data coverage of 32%. A blank
    where AEAT expects a datum is exactly the silent under-declaration this gate
    exists to refuse, so a position is covered only when real data reaches every
    one of its bytes.

    A filler over bytes the design ITSELF declares omissible stays correct and
    stays legal: a fixed-width record is contiguous and those bytes must still
    be emitted. Such positions never reach here, because
    :func:`_required_positions` excluded them.

    The one position that DOES reach here and is satisfied by a filler is the
    obligatory BLANK -- AEAT marking a position obligatorio while its own
    ``Contenido`` cell declares the content to be blanks. Both statements are
    the authority's and neither overrides the other: the field must be emitted,
    and what it emits is blanks. Requiring real data there made 34 positions
    across Modelos 369, 322, 036, 210 and 353 UNSATISFIABLE -- a filler did not
    cover them, and a value-carrying field would both contradict the Contenido
    cell and trip :func:`_reserved_write_failures` for claiming reserved bytes.
    A rule no correct layout can satisfy is a rule that teaches authors to write
    the wrong shape, which is the incentive inversion this module exists to
    remove.
    """
    countable = fill_bytes if position.declared_blank else data_bytes
    return all(byte in countable for byte in range(position.offset, position.offset + position.length))


def _belongs_to_layout(sheet: RecordDesignSheet, records: Sequence[ExportRecordDefinition]) -> bool:
    """Whether this design sheet is one THIS layout is supposed to render at all.

    One bundled workbook can describe several independent filing schemas. Modelo
    369 is the case: its ``union``, ``exterior`` and ``importación`` schemas each
    declare their own layout, and all three cite the SAME design workbook, whose
    sheets carry a per-schema ``Página`` constant (``01``-``03`` Ext, ``04``-``09``
    Un, ``10``-``12`` Imp). Measuring every layout against every sheet scored
    each complete schema against all 1,513 positions, including the other two
    schemas' -- a structural cap no authoring could lift, and the reason all
    three looked permanently incomplete while each writes its own sheets in full.

    The question is asked PER COORDINATE, not per record. Asking whether any
    record agrees overall answers "yes" for every sheet, because the envelope
    record declares only ``<T`` and ``369`` -- constants every sheet in the
    workbook shares -- and so agrees with all fourteen. The discriminating byte
    is the one where the layout's records actually disagree with each other.

    So a sheet is out of scope when, at some coordinate it declares, EVERY
    record that speaks to that coordinate contradicts it. Under the importación
    layout, sheet ``T36901 Ext`` declares ``(6,2) = "01"`` while every record
    declaring ``(6,2)`` says ``"00"``, ``"10"``, ``"11"``, ``"12"`` -- AEAT's own
    statement that this sheet is another schema's.

    Silence is never taken as exclusion: a coordinate no record speaks to, or a
    sheet declaring no constants at all, leaves the sheet IN scope and falls
    through to the weaker layout-wide question. "No evidence either way" must
    not shrink a denominator, which is the one direction this gate must never
    fail in.
    """
    literals_by_record = [_record_literals(record) for record in records]
    for coordinate, value in _sheet_constants(sheet).items():
        declaring = [literals[coordinate] for literals in literals_by_record if coordinate in literals]
        if declaring and all(declared != value for declared in declaring):
            return False
    return True


def _join_record(
    sheet: RecordDesignSheet,
    records: Sequence[ExportRecordDefinition],
) -> ExportRecordDefinition | None:
    """Return the one authored record whose declared constants identify this sheet.

    Agreement is counted only over coordinates BOTH sides declare a constant at,
    and any contradiction there disqualifies the record outright -- Modelo 714's
    ``714-02`` writes ``"02000"`` where the ``714-01`` sheet declares ``"01000"``,
    which is precisely the byte AEAT uses to tell the two records apart.

    A unique maximum is required. Modelo 390's page records all agree on ``<T``
    and ``390``, so a merely-nonzero agreement would match every page to every
    sheet; the page discriminator breaks the tie, and where nothing does, the
    sheet stays unjoined rather than taking an arbitrary winner.
    """
    constants = _sheet_constants(sheet)
    if not constants:
        return None
    scored: list[tuple[int, ExportRecordDefinition]] = []
    for record in records:
        literals = _record_literals(record)
        shared = constants.keys() & literals.keys()
        if not shared:
            continue
        if any(constants[key] != literals[key] for key in shared):
            continue
        scored.append((len(shared), record))
    if not scored:
        return None
    best = max(score for score, _ in scored)
    winners = [record for score, record in scored if score == best]
    return winners[0] if len(winners) == 1 else None


def _design_sources(
    layout: ExportLayoutDefinition,
    source_refs: Mapping[str, SourceReference],
) -> tuple[SourceReference, ...]:
    return tuple(
        source
        for ref in layout.source_refs
        if (source := source_refs.get(ref)) is not None and source.kind == "record_design"
    )


def _read_design_sheets(source: SourceReference) -> tuple[RecordDesignSheet, ...] | str:
    """Return the source's sheets, or the reason no complete design could be read.

    ``require_complete`` rather than ``accept_partial``: a coverage figure
    derived from a partly-read design is inflated by exactly the records that
    were dropped, and nothing downstream can tell that from real coverage.
    """
    path = resolve_corpus_binary(*source.corpus_path.split("/"))
    if path is None:
        return (
            f"its official record design {source.id!r} ({source.corpus_path!r}) is not reachable in "
            f"this installation, so its coverage cannot be verified. The corpus binaries ship in the "
            f"mandatory cadrumo_data companion namespace; an unreachable design is a broken "
            f"installation, and reporting a layout complete against a file nobody read is the one "
            f"outcome this gate must never produce"
        )
    try:
        return extract_record_design(path).require_complete()
    except RegistryValidationError as exc:
        return (
            f"its official record design {source.id!r} could not be read in full, so its coverage "
            f"cannot be verified: {exc}. A coverage figure derived from a partly-read design is "
            f"inflated by exactly the records that were dropped"
        )


def _envelope_written_positions(envelope: FilingEnvelopeDefinition) -> set[tuple[int, int]]:
    written: set[tuple[int, int]] = set()
    offset = 1
    for field in envelope.prefix_fields:
        written.add((offset, field.length))
        offset += field.length
    return written


def _envelope_written_bytes(envelope: FilingEnvelopeDefinition) -> set[int]:
    """Return every byte the filing envelope's prefix fields write.

    The byte-extent counterpart of :func:`_envelope_written_positions`. Every
    prefix field carries a real declared value, so none is filler and the
    data-only distinction :func:`_written_bytes` draws does not arise here.
    """
    written: set[int] = set()
    offset = 1
    for field in envelope.prefix_fields:
        written.update(range(offset, offset + field.length))
        offset += field.length
    return written


def _missing_report(
    sheets: Sequence[RecordDesignSheet],
    records: Sequence[ExportRecordDefinition],
    *,
    envelope: FilingEnvelopeDefinition | None = None,
    auxiliary_header: AuxiliaryEnvelopeHeaderDefinition | None = None,
) -> tuple[int, int, list[str]]:
    """Return ``(required, missing, per-sheet lines)`` for one design against one layout."""
    layout_written: set[int] = set()
    layout_emitted: set[int] = set()
    for record in records:
        layout_written |= _written_bytes(record.fields, data_only=True)
        layout_emitted |= _written_bytes(record.fields, data_only=False)
    if envelope is not None:
        layout_written |= _envelope_written_bytes(envelope)
        layout_emitted |= _envelope_written_bytes(envelope)
    required_total = 0
    missing_total = 0
    lines: list[str] = []
    #: Positions already counted, keyed by (design record, coordinate). A layout
    #: may cite SEVERAL editions of one modelo's design -- Modelo 190 cites its
    #: 2024 and 2025 Diseños de Registro together -- and the editions repeat the
    #: sheets they share. Counting them once per citation double-counts every
    #: shared position in BOTH numerator and denominator: Modelo 190 reported
    #: 102/106 where the union of its editions declares 100/104. The layout has
    #: to satisfy each position ONCE, however many editions declare it, so the
    #: later edition contributes only what it adds -- which is exactly the
    #: (389, 1) and (390, 5) rows 2025 introduces.
    counted: set[tuple[str, int, int]] = set()
    for sheet in sheets:
        if not _belongs_to_layout(sheet, records):
            continue
        required = tuple(
            position
            for position in _required_positions(sheet)
            if (sheet.name, position.offset, position.length) not in counted
        )
        counted.update((sheet.name, position.offset, position.length) for position in required)
        required_total += len(required)
        is_envelope_sheet = envelope is not None and sheet.name == envelope.record_identity
        # The envelope sheet is decided BEFORE the content join, never after it.
        # The join matches on declared constants, and an envelope opens with the
        # same `<T` and modelo bytes its page records do, so it agrees with every
        # one of them. With a single body record that agreement is trivially a
        # unique maximum, and the envelope is "joined" to a page whose fields sit
        # at unrelated offsets -- reporting the page's identificación block as
        # intruding on the envelope's own reserved run. Modelo 353's 2008-2025
        # edition, which has exactly one body record, showed that. The envelope
        # is emitted by the envelope contract and is never an authored record, so
        # its coverage question has one correct answer regardless of the join.
        joined = None if is_envelope_sheet else _join_record(sheet, records)
        if is_envelope_sheet:
            assert envelope is not None
            consulted = ()
            written = _envelope_written_bytes(envelope)
            emitted = written
        elif joined is not None:
            consulted = tuple(joined.fields)
            written = _written_bytes(consulted, data_only=True)
            emitted = _written_bytes(consulted, data_only=False)
        elif sheet.auxiliary_envelope_header is not None:
            # An auxiliary header is NOT a fixed record and no authored record
            # renders it, so the generic fallback below is actively wrong here:
            # it asks whether ANY record writes the coordinate, and the other
            # records' fields sit at the same low offsets, so a header position
            # gets "covered" by an unrelated record's field or -- worse --
            # reported as that field intruding on the header's reserved run.
            # Modelo 232 showed exactly that, blaming dr23201 fields for writing
            # into DR23200's administración bytes.
            #
            # A declared header is emitted byte-for-byte over its prefix spans:
            # every one of its required positions carries a real value at filing
            # time (literals, modelo, year, period, product identity), so the
            # full extent counts as written. A layout that declares none
            # genuinely emits nothing for the header, and every required
            # position is attributed to the header itself.
            consulted = ()
            if auxiliary_header is not None:
                # Design offsets are one-based, so the declared extent covers
                # bytes @1..@extent exactly.
                written = set(range(1, auxiliary_header.prefix_extent + 1))
                emitted = written
            else:
                written = set()
                emitted = set()
        else:
            consulted = tuple(field for record in records for field in record.fields)
            written = layout_written
            emitted = layout_emitted
        missing = [position for position in required if not _covers(position, written, emitted)]
        missing_total += len(missing)
        # Checked against whichever fields the coverage question consulted,
        # joined or not: an unjoined sheet still knows which bytes AEAT keeps,
        # and a wide field claiming them is a defect either way.
        if intrusions := _reserved_write_failures(sheet, consulted):
            # Counted alongside the gap so a layout cannot trade one for the
            # other: writing across the administración's bytes is how a single
            # wide field "covers" every position it spans.
            missing_total += len(intrusions)
            lines.append(f"design record {sheet.name!r}: {'; '.join(intrusions)}")
        if not missing:
            continue
        if is_envelope_sheet:
            scope = f"filing envelope {sheet.name!r}"
        elif joined is not None:
            scope = f"authored record {joined.id!r} (record_type {joined.record_type!r})"
        elif sheet.auxiliary_envelope_header is not None:
            scope = (
                f"auxiliary envelope header {sheet.name!r}, which this layout does not emit: the "
                "header is a source-proved 328-byte composition outside the fixed-record totals, so "
                "it needs its own emission contract rather than an authored fixed record"
            )
        else:
            scope = (
                "NO authored record could be identified for this design record, so the check fell "
                "back to asking whether any record of the layout writes the coordinate -- a weaker "
                "question, so this count is a floor, not the whole gap"
            )
        shown = ", ".join(
            f"@{position.offset}+{position.length} "
            f"{'[OBLIGATORIO] ' if position.obligatorio else ''}{position.description!r}"
            for position in missing[:_ENUMERATED_PER_RECORD]
        )
        remainder = (
            f" and {len(missing) - _ENUMERATED_PER_RECORD} more" if len(missing) > _ENUMERATED_PER_RECORD else ""
        )
        lines.append(
            f"design record {sheet.name!r}: {len(missing)} of {len(required)} required positions "
            f"unwritten by {scope}; {shown}{remainder}"
        )
    return required_total, missing_total, lines


def _layout_failure(
    *,
    prefix: str,
    layout: ExportLayoutDefinition,
    source_refs: Mapping[str, SourceReference],
) -> str | None:
    design_sources = _design_sources(layout, source_refs)
    if not design_sources:
        return (
            f"{prefix}: fixed-width export layout {layout.id!r} cites no official record-design "
            f"source, so nothing states what a complete layout for it would contain and its "
            f"completeness cannot be verified. Cite the modelo's bundled Diseño de Registros in the "
            f"layout's source_refs"
        )
    sheets: list[RecordDesignSheet] = []
    for source in design_sources:
        read = _read_design_sheets(source)
        if isinstance(read, str):
            return f"{prefix}: fixed-width export layout {layout.id!r} cannot be checked because {read}"
        sheets.extend(read)
    required, missing, lines = _missing_report(
        sheets,
        layout.records,
        envelope=layout.filing_envelope,
        auxiliary_header=layout.auxiliary_envelope_header,
    )
    if not missing:
        return None
    coverage = 100.0 * (required - missing) / required if required else 0.0
    return (
        f"{prefix}: fixed-width export layout {layout.id!r} writes only {required - missing} of the "
        f"{required} positions its official record design requires ({coverage:.1f}% coverage), so a "
        f"filing generated from it would carry fill where AEAT expects data -- behind a digest that "
        f"is valid, because a digest locks bytes and asserts nothing about completeness. Required "
        f"means every position of the official design except the ones the design ITSELF declares "
        f"omissible (reserved for the Administración, or declared fill); a position AEAT marks "
        f"OBLIGATORIO is required regardless. There is no percentage floor and no exemption: author "
        f"the missing positions from the design at "
        f"{', '.join(repr(source.corpus_path) for source in design_sources)}. " + " | ".join(lines)
    )


def validate_export_layout_record_coverage(
    *,
    prefix: str,
    revision: ModeloRevision,
    source_refs: Mapping[str, SourceReference],
) -> list[str]:
    """Refuse every fixed-width layout that cannot write its official design.

    Resolves the revision's layouts the way snapshot build does -- through
    :func:`derive_export_layouts_from_bindings`, so binding-derived record fields
    count as written -- and checks each fixed-width one against the bundled AEAT
    record design it cites.

    A revision declaring no fixed-width layout yields nothing here. Modelo 100
    and Modelo 390's XML-dictionary siblings file through a dictionary and have
    no positional design to be measured against, and Modelo 720 assembles its
    records from ``binding_record`` selectors that
    :func:`derive_export_layouts_from_bindings` materialises before this runs.
    The revision that declares NO layout at all is the sibling gate's subject,
    not this one's: reporting it here too would put a second count into
    circulation for one defect.

    Failures accumulate rather than raising, so one load reports every
    incomplete layout instead of the first, and one failure covers one layout so
    the enumeration stays a worklist rather than a wall.

    Args:
        prefix: Caller-supplied ``modelo N revision R`` diagnostic prefix.
        revision: The :class:`ModeloRevision` under validation.
        source_refs: The registry source catalogue, keyed by source ID, used to
            resolve each layout's cited record-design binary.

    Returns:
        Accumulated diagnostics; empty when every fixed-width layout writes
        every position its official design requires.
    """
    failures: list[str] = []
    for layout in derive_export_layouts_from_bindings(revision):
        if layout.format is not ExportLayoutFormat.FIXED_WIDTH:
            continue
        failure = _layout_failure(prefix=prefix, layout=layout, source_refs=source_refs)
        if failure is not None:
            failures.append(failure)
    return failures


__all__ = ["validate_export_layout_record_coverage"]
