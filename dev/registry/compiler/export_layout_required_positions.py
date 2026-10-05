"""Read source-declared omissibility and required positions from record designs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from .record_design_pdf_rows import naturaleza_or_none
from .record_design_schema import RecordDesignField, RecordDesignSheet

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
    house that produced the file is never the taxpayer's datum, so the design
    cannot require it of the filing: Cadrumo holds no EEDD registration and
    writes the all-zero development mock identity its governed fact declares,
    which no reader can take for a registration.
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
    return naturaleza_or_none(field.type_code or "") == "Blancos"


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
    :attr:`~.record_design_schema.RecordDesignField.components` deliberately
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
