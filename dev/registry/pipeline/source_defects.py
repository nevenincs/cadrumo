"""Adjudicated defects in an AEAT-published record design, pinned to one file.

An official record design is the authority the export generator compares every
literal field against byte-for-byte, and that comparison is the only check that
reads the source document rather than the project's transcription of it. It has
to stay exact. But a published workbook can contradict itself, and when it does
no reading of it satisfies both halves: the modelo 390 filing-year 2022 and 2023
designs print an eleven-character close constant into a slot the same cell
declares as twelve bytes wide, while their seven sibling pages each print twelve
into twelve.

A declaration here records that adjudication as data rather than as a branch in
the parser or an exemption in a test. It is deliberately narrower than the thing
it unblocks: pinned to one file by digest, one cell by coordinate, and one exact
published string, and carrying the evidence that established the reading.

Two properties keep it self-limiting, and both are load-bearing rather than
incidental:

* Because the key includes the file's SHA-256, a reissued design carries a
  different digest, the declaration stops applying, and the generator refuses
  again until the new file is adjudicated on its own terms. The failure mode is
  a stale correction going dormant, never a stale correction being applied.
* Because the adjudicated literal is fed back through the SAME byte comparison
  and the SAME length check that follow it, the mechanism cannot express an
  arbitrary substitution. It can only resolve a contradiction in the direction
  the document's own surviving half supports -- a value that does not fill the
  slot the cell declares is refused exactly as it is today.

The adjudication that established this reading is recorded outside the codebase
and cites this module by path; the evidence a declaration needs to stand on its
own travels with the declaration itself, in its digest, coordinate and literal.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from cadrumo.domain.calculations.registry.errors import RegistryValidationError

if TYPE_CHECKING:
    from ._record_design_ir import RecordDesignIntermediateSource

__all__ = [
    "NoteGovernedAmountDeclaration",
    "SourceDefectDeclaration",
    "adjudicated_literal_for",
    "note_governed_amount_scale_for",
    "note_governed_amounts_for",
    "source_defects_for",
    "validate_note_governed_amount_declarations",
    "validate_source_defect_declarations",
]


class SourceDefectDeclaration(BaseModel):
    """One adjudicated contradiction in one published record-design file.

    Every field is required. A declaration without its evidence is not a
    weaker declaration, it is an unreviewed one, and the whole point of
    declaring rather than branching is that the reasoning travels with the
    correction.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=False)

    source_ref: str = Field(min_length=1)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    sheet: str = Field(min_length=1)
    source_cell: str = Field(min_length=1)
    published_content: str = Field(min_length=1)
    """The cell's content exactly as the workbook publishes it, defect included."""
    adjudicated_literal: str = Field(min_length=1)
    """The literal the document's own surviving half supports."""
    evidence: str = Field(min_length=1)
    """How the reading was established, in terms a later reviewer can re-check."""


_SOURCE_DEFECTS_BY_REF: dict[str, tuple[SourceDefectDeclaration, ...]] = {
    "aeat-dr-390-2022": (
        SourceDefectDeclaration(
            source_ref="aeat-dr-390-2022",
            source_sha256="7c6554f3182df51daaec37284dd891eb925e1f92df7e69bc01b8ccfb8e4f26fe",
            sheet="Pág. 7",
            source_cell="A53",
            published_content='Constante "</T3900700>"',
            adjudicated_literal="</T39007000>",
            evidence=(
                "Cell A53 states two facts that cannot both hold: the close constant it prints is eleven "
                "characters, and the slot the same cell declares for it is twelve bytes. Read straight out "
                "of xl/sharedStrings.xml, bypassing project code, the workbook carries </T39001000> through "
                "</T39006000> and </T39008000> at twelve characters each and </T3900700> at eleven, so the "
                "short form is in the AEAT file and no parser is implicated. Three independent signals "
                "converge on </T39007000>: the seven sibling pages all follow </T3900N000> for page N, that "
                "value is the only one filling the twelve-byte slot A53 itself declares, and it is the value "
                "the reviewed committed layout already carries. The published reading is unusable rather than "
                "merely disfavoured, since an eleven-byte literal is refused by the slot-width guard that "
                "follows this substitution regardless of how the byte comparison is settled."
            ),
        ),
    ),
    "aeat-dr-390-2023": (
        SourceDefectDeclaration(
            source_ref="aeat-dr-390-2023",
            source_sha256="179c02eddc8bab411c249fc3fda19c7015d668e1dd7930d4af79f38998b9c5a7",
            sheet="Pág. 7",
            source_cell="A53",
            published_content='Constante "</T3900700>"',
            adjudicated_literal="</T39007000>",
            evidence=(
                "Cell A53 states two facts that cannot both hold: the close constant it prints is eleven "
                "characters, and the slot the same cell declares for it is twelve bytes. Read straight out "
                "of xl/sharedStrings.xml in the independently hash-pinned 2023 workbook, bypassing project "
                "code, the file carries </T39001000> through </T39006000> and </T39008000> once each at "
                "twelve characters, carries no </T39007000>, and carries </T3900700> once at eleven. Three "
                "independent signals converge on </T39007000>: the seven sibling pages all follow "
                "</T3900N000> for page N, that value is the only one filling the twelve-byte slot A53 itself "
                "declares, and it is the value the reviewed revision layout already carries. The published "
                "reading is unusable rather than merely disfavoured, since an eleven-byte literal is refused "
                "by the slot-width guard that follows this substitution regardless of how the byte comparison "
                "is settled."
            ),
        ),
    ),
}


def source_defects_for(source_ref: str) -> tuple[SourceDefectDeclaration, ...]:
    """Return the complete adjudication set declared for one official source."""
    return _SOURCE_DEFECTS_BY_REF.get(source_ref, ())


def validate_source_defect_declarations(
    declarations: tuple[SourceDefectDeclaration, ...],
    source: RecordDesignIntermediateSource,
) -> None:
    """Refuse a declaration set that is not pinned to the design being rendered.

    Mirrors the pinning discipline ``_validate_anomaly_exceptions`` applies to
    semantic-map anomalies, and for the same reason: a correction that is not
    tied to the exact bytes it was adjudicated against is a correction that can
    outlive its document.

    The SHA-256 is checked against the PARSER-READ source rather than any
    caller-supplied transport claim, so a declaration cannot be admitted by a
    profile that merely asserts the digest it wants.
    """
    seen: set[tuple[str, str, str]] = set()
    for declaration in declarations:
        key = (declaration.source_ref, declaration.sheet, declaration.source_cell)
        if key in seen:
            raise RegistryValidationError(
                f"duplicate source-defect declaration for {declaration.source_ref!r} "
                f"sheet {declaration.sheet!r} cell {declaration.source_cell!r}",
            )
        seen.add(key)
        if declaration.source_ref != source.source_ref:
            raise RegistryValidationError(
                f"source-defect declaration source {declaration.source_ref!r} does not match parser "
                f"intermediate source {source.source_ref!r}",
            )
        if declaration.source_sha256 != source.source_sha256:
            raise RegistryValidationError(
                f"source-defect declaration for {declaration.source_ref!r} is not pinned to the parser "
                "intermediate SHA-256",
            )


def adjudicated_literal_for(
    declarations: tuple[SourceDefectDeclaration, ...],
    *,
    sheet: str,
    source_cell: str,
    published_content: str,
) -> str | None:
    """Return the adjudicated literal for this cell, or ``None`` to refuse normally.

    The published content must match the declaration EXACTLY. Any other content
    means the file is not the one that was adjudicated -- a reissue, a different
    sheet revision, a parser change -- and the caller's refusal stands, which is
    the behaviour a reader should be able to assume when no declaration applies.
    """
    for declaration in declarations:
        if declaration.sheet != sheet or declaration.source_cell != source_cell:
            continue
        if declaration.published_content != published_content:
            return None
        return declaration.adjudicated_literal
    return None


class NoteGovernedAmountDeclaration(BaseModel):
    """One amount run whose ``Contenido`` cells carry only a footnote pointer.

    A workbook design normally spells an amount slot's representation in its
    ``Contenido`` cell -- ``15 enteros 2 decimales`` -- and the numeric
    derivation reads it there. A cell holding nothing but ``Nota N`` states no
    representation at all, and reading it as an unscaled integer is an
    invention: it silently decides that the emitted digits are euros in a run
    whose every other member emits cents, which is a filing wrong by two orders
    of magnitude on a monetary casilla.

    A declaration here records the adjudication of one such run against the
    note the pointer names. It is pinned the same way a
    :class:`SourceDefectDeclaration` is -- to one file by digest and to one
    sheet by name, carrying the exact published pointer and the exact note text
    that was read -- and it is self-limiting for the same reasons:

    * The SHA-256 makes a reissued design drop out of the table, so the
      generator refuses to the unstated reading again rather than carrying a
      stale adjudication into a document nobody re-read.
    * The declared representation is fed back through the SAME slot-width check
      every content-derived representation passes, so a declaration cannot widen,
      narrow, or re-scale a slot the design's own geometry contradicts.
    * The scope is the sheet that PRINTS the note, because a note label
      identifies a note only together with its sheet; the same ``Nota 2`` on
      another sheet is another note and is not covered.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=False)

    source_ref: str = Field(min_length=1)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    sheet: str = Field(min_length=1)
    published_content: str = Field(min_length=1)
    """The pointer exactly as the ``Contenido`` cells of this run publish it."""
    note_cell: str = Field(min_length=1)
    """Where on this sheet the design defines the note the pointer names."""
    note_statement: str = Field(min_length=1)
    """The note's text as read from that cell, so a later reviewer re-reads it."""
    integer_digits: int = Field(gt=0)
    decimal_digits: int = Field(gt=0)
    """Positive: a run adjudicated to carry no decimals states that in its cells."""
    evidence: str = Field(min_length=1)
    """How the reading was established, in terms a later reviewer can re-check."""


_NOTE_GOVERNED_AMOUNTS_BY_REF: dict[str, tuple[NoteGovernedAmountDeclaration, ...]] = {
    "aeat-dr-200-2025": (
        NoteGovernedAmountDeclaration(
            source_ref="aeat-dr-200-2025",
            source_sha256="92392cdb46d8e7c7f6e4e6477306570e15edfd64d5ea3e6d631e5cf847dd5509",
            sheet="DP200019",
            published_content="Nota 1",
            note_cell="A254",
            note_statement=(
                "A cumplimentar exclusivamente por entidades que pertenezcan a grupos mercantiles (carácter 00039)"
            ),
            integer_digits=15,
            decimal_digits=2,
            evidence=(
                "Twenty-six 'Deducción resto del grupo' slots on DP200019 carry the bare pointer 'Nota 1' where "
                "their four siblings in each I+D+i year block -- 'Deducción pendiente/generada', 'Deducción "
                "reducida', 'Aplicado en esta liquidación' and 'Importe abonado por insuficiencia de cuota' -- "
                "carry no Contenido at all. Read from the workbook itself, every one of the twenty-six is "
                "aeat_type 'Num' at length 17, exactly like those siblings. The note the pointer names is "
                "defined at A253/A254 and says who fills the slot, not how a value is written: it withholds "
                "APPLICABILITY to entities in a grupo mercantil and states no scale, sign or decimal count. "
                "The representation therefore stands unchanged from the surrounding run, which this design "
                "settles for itself in DP200001!A121 -- 'NOTA: Los importes son de 15 enteros (o N + 14) y 2 "
                "decimales' -- the same cell the reviewed width-17 render profile for this modelo, revision and "
                "digest already cites when it assigns 15 enteros and 2 decimales to every unsigned width-17 "
                "amount of this design, the untagged siblings of these very rows included. Reading the pointer "
                "as an unscaled integer instead would emit euros into a cents field."
            ),
        ),
        NoteGovernedAmountDeclaration(
            source_ref="aeat-dr-200-2025",
            source_sha256="92392cdb46d8e7c7f6e4e6477306570e15edfd64d5ea3e6d631e5cf847dd5509",
            sheet="DP200020B",
            published_content="Nota 1",
            note_cell="A106",
            note_statement="Sólo se admitirán valores hasta un máximo de 99999,99 (00000000009999999)",
            integer_digits=15,
            decimal_digits=2,
            evidence=(
                "The single slot on DP200020B carrying the bare pointer 'Nota 1' is the 'Incremento porcentual "
                "de la plantilla media total' row, aeat_type 'Num' at length 17 as read from the workbook. The "
                "note defined at A105/A106 states the representation OUTRIGHT rather than by inference: it "
                "spells the maximum admissible value twice, once as '99999,99' and once as the wire form that "
                "value takes, '00000000009999999'. That wire form is seventeen characters, fills the slot the "
                "same row declares, and places two digits after the comma, which is fifteen integer positions "
                "and two decimals and nothing else. The design's own general statement in DP200001!A121 -- "
                "'NOTA: Los importes son de 15 enteros (o N + 14) y 2 decimales' -- and the reviewed width-17 "
                "render profile that cites it for this digest agree. The note additionally caps the value at "
                "99999,99; that ceiling is a value domain rather than a representation, is not expressible in "
                "this declaration, and is deliberately left unasserted here rather than approximated."
            ),
        ),
    ),
    "aeat-dr-390-2025": tuple(
        NoteGovernedAmountDeclaration(
            source_ref="aeat-dr-390-2025",
            source_sha256="6d33d8a4245976e55dc31ff85065b420f76d1588110dc1eb541a8039c5e3f252",
            sheet=sheet,
            published_content="Nota 2",
            note_cell=note_cell,
            note_statement="Nota 2: estas casillas deben estar rellenas a 0",
            integer_digits=15,
            decimal_digits=2,
            evidence=(
                "The 2025 design replaced the Contenido clause of the expired temporary-rate slots -- the "
                "0%, 2%, 5% and 7,5% rows and the 0%, 0,26%, 0,62% and 1% recargo rows -- with the pointer "
                "'Nota 2', where the 2024 design of the same modelo spelled '15 enteros 2 decimales' in every "
                "one of them. The note the pointer names says 'estas casillas deben estar rellenas a 0': it "
                "withholds the VALUE for a rate that no longer applies and says nothing about how digits are "
                "written. The representation therefore stands unchanged from the surrounding run, which the "
                "same sheet still states outright on every 17-position amount whose rate survives into 2025 "
                "(4%, 10% and 21% bases and cuotas), and which the 2024 design states on these very rows. "
                "Reading the pointer as an unscaled integer instead would emit euros into a cents field."
            ),
        )
        for sheet, note_cell in (
            ("Pág. 2", "A119"),
            ("Pág. 2 bis", "A44"),
            ("Pág. 3", "A120"),
            ("Pág. 4", "A62"),
        )
    ),
}


def note_governed_amounts_for(source_ref: str) -> tuple[NoteGovernedAmountDeclaration, ...]:
    """Return the complete note-governed amount set declared for one official source."""
    return _NOTE_GOVERNED_AMOUNTS_BY_REF.get(source_ref, ())


def validate_note_governed_amount_declarations(
    declarations: tuple[NoteGovernedAmountDeclaration, ...],
    source: RecordDesignIntermediateSource,
) -> None:
    """Refuse a declaration set that is not pinned to the design being rendered.

    The SHA-256 is checked against the PARSER-READ source, exactly as
    :func:`validate_source_defect_declarations` checks it, so a declaration
    cannot be admitted by a caller that merely asserts the digest it wants.
    """
    seen: set[tuple[str, str, str]] = set()
    for declaration in declarations:
        key = (declaration.source_ref, declaration.sheet, declaration.published_content)
        if key in seen:
            raise RegistryValidationError(
                f"duplicate note-governed amount declaration for {declaration.source_ref!r} "
                f"sheet {declaration.sheet!r} content {declaration.published_content!r}",
            )
        seen.add(key)
        if declaration.source_ref != source.source_ref:
            raise RegistryValidationError(
                f"note-governed amount declaration source {declaration.source_ref!r} does not match parser "
                f"intermediate source {source.source_ref!r}",
            )
        if declaration.source_sha256 != source.source_sha256:
            raise RegistryValidationError(
                f"note-governed amount declaration for {declaration.source_ref!r} is not pinned to the parser "
                "intermediate SHA-256",
            )


def note_governed_amount_scale_for(
    declarations: tuple[NoteGovernedAmountDeclaration, ...],
    *,
    sheet: str,
    published_content: str,
) -> tuple[int, int] | None:
    """Return the adjudicated whole/decimal digit pair, or ``None`` to derive normally.

    ``published_content`` is the cell's whitespace-normalised content, which is
    what the numeric derivation reads. Anything the declaration does not name
    exactly leaves the caller's own derivation standing, which is the behaviour
    a reader should be able to assume when no declaration applies.
    """
    for declaration in declarations:
        if declaration.sheet != sheet or declaration.published_content != published_content:
            continue
        return declaration.integer_digits, declaration.decimal_digits
    return None
