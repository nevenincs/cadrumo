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

from typing import TYPE_CHECKING, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from cadrumo.domain.calculations.registry.errors import RegistryValidationError

if TYPE_CHECKING:
    from .record_design_intermediate import RecordDesignIntermediateSource

__all__ = [
    "NoteGovernedAmountDeclaration",
    "NoteStatedApplicabilityDeclaration",
    "SourceDefectDeclaration",
    "adjudicated_literal_for",
    "note_governed_amount_for",
    "note_governed_amounts_for",
    "note_stated_applicability_for",
    "note_stated_applicability_reading_for",
    "note_states_only_applicability",
    "source_defects_for",
    "validate_note_governed_amount_declarations",
    "validate_note_stated_applicability_declarations",
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
    source_cell: str | None,
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


#: The two sign policies an adjudicated amount run can carry, named exactly as
#: ``Width17MembershipRule.sign_policy`` names them so one vocabulary describes
#: the sign wherever a width-17 amount is settled.
#:
#: ``unsigned`` spends every declared byte on digits. ``n-prefix`` spends the
#: leading byte on the marker the fixed-width codec writes there -- ``N`` for a
#: negative value, a space otherwise -- so the digits occupy one byte less than
#: the slot. That difference is the whole reason the sign has to be DECLARED
#: rather than left implicit: the same seventeen-byte slot holds fifteen integer
#: digits unsigned and fourteen signed, and reading the wrong one emits a value
#: ten times its true magnitude.
_UNSIGNED_SIGN_POLICY: Final = "unsigned"
_N_PREFIX_SIGN_POLICY: Final = "n-prefix-negative-blank-nonnegative"

#: The decimal count the ``money`` wire type fixes inside its codec. A signed
#: declaration renders through that type and therefore cannot carry any other
#: count; the validator below refuses the combination rather than letting the
#: codec silently overrule a declared scale.
_MONEY_CODEC_DECIMALS: Final = 2


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
    sign_policy: Literal["unsigned", "n-prefix-negative-blank-nonnegative"]
    """Whether the slot spends a byte on a sign marker, READ per declaration.

    Declared per run, though no longer because the corpus disagrees with itself.

    This once argued that ``Tipo`` could not settle the sign, on the grounds
    that modelo 200 pairs ``N`` with a sign position while modelo 390 prints
    ``Tipo`` ``N`` on width-17 rows whose ``Contenido`` says ``15 enteros 2
    decimales`` -- seventeen digits with no room for a marker. **That reasoning
    is withdrawn.** It read one cell and missed the note beside it.

    AEAT states the convention for every design in "Disenos de registro - breve
    manual de uso" (v.2, 12/12/2022): numeric fields are right-aligned and
    zero-filled ``sin signos``, and only NEGATIVE amounts are ``precedidos del
    caracter 'N'``. The marker therefore DISPLACES the leading digit instead of
    demanding an extra byte, which is exactly what modelo 200's own note means
    by ``15 enteros (o N + 14)``. The two designs never disagreed: ``Contenido``
    states the non-negative capacity, which is why the identical string sits on
    signed and unsigned rows throughout the corpus.

    So ``Tipo`` does settle the sign, and the generator now derives it. What is
    still declared here is the per-run REPRESENTATION - integer and decimal
    extent - which the type column does not state.
    """
    mandated_values: tuple[str, ...] | None
    """The closed value domain the note MANDATES, or ``None`` when it mandates none.

    A note can withhold more than a representation. Modelo 390's 2025 Nota 2 --
    "estas casillas deben estar rellenas a 0" -- states the VALUE the expired
    temporary-rate slots may carry, and a slot whose only admissible value is
    zero is under-declared while the pipeline emits a nonzero one at the right
    scale. This field is how that mandate is recorded, and it is required rather
    than defaulted so a declaration that asserts no domain says so explicitly
    instead of inheriting silence.

    Members are spelled in WHOLE UNITS, unsigned and zero-canonical, because
    that is the value the fixed-width codec settles against before it applies
    the scale: ``"0"`` on a fifteen-and-two slot is the quantity zero, whose
    wire form is the seventeen zero bytes the scale produces. A wire digit run
    would read as minor units on a scaled slot and as units on an unscaled one,
    so the two spellings would disagree by ``10 ** decimal_digits`` while
    looking identical.

    Deliberately NOT parsed out of ``note_statement``: the mandate is read by a
    person and recorded here, so a note whose Spanish a matcher would misread
    cannot quietly acquire or lose a domain.
    """
    evidence: str = Field(min_length=1)
    """How the reading was established, in terms a later reviewer can re-check."""

    @property
    def signed(self) -> bool:
        """Whether the slot carries the codec's sign marker in its leading byte."""
        return self.sign_policy == _N_PREFIX_SIGN_POLICY

    @property
    def wire_length(self) -> int:
        """The bytes this representation occupies, sign position included.

        This is what the slot-width check compares against, so an adjudication
        that does not fill the slot the design declares is refused exactly as an
        unsigned one is -- the sign position is accounted for rather than
        excused.
        """
        return self.integer_digits + self.decimal_digits + (1 if self.signed else 0)

    @model_validator(mode="after")
    def _require_a_scale_the_signed_codec_can_carry(self) -> NoteGovernedAmountDeclaration:
        # A signed amount renders through the `money` wire type, which fixes its
        # scale at two decimals inside the codec and accepts no declared count.
        # Admitting any other count here would publish a field whose declared
        # scale and emitted scale disagree, with nothing downstream to catch it.
        if self.signed and self.decimal_digits != _MONEY_CODEC_DECIMALS:
            raise ValueError(
                f"{self.sign_policy} renders through the money wire type, which fixes "
                f"{_MONEY_CODEC_DECIMALS} decimals; {self.decimal_digits} cannot be carried",
            )
        return self

    @model_validator(mode="after")
    def _require_a_domain_the_export_schema_can_carry(self) -> NoteGovernedAmountDeclaration:
        # The schema carries a closed domain on the unsigned scaled-amount shape
        # and on signed money, so a design that types a slot signed AND mandates
        # its value keeps both: the domain is never traded for the sign.
        if self.mandated_values is None:
            return self
        if not self.mandated_values or len(set(self.mandated_values)) != len(self.mandated_values):
            raise ValueError("mandated_values must be non-empty and unique")
        invalid = tuple(
            value
            for value in self.mandated_values
            if not (value.isascii() and value.isdigit() and str(int(value)) == value)
            or len(value) > self.integer_digits
        )
        if invalid:
            raise ValueError(
                f"mandated_values must be zero-canonical unsigned unit values of at most "
                f"{self.integer_digits} digits; {invalid!r} are not",
            )
        return self


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
            sign_policy=_UNSIGNED_SIGN_POLICY,
            mandated_values=None,
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
            sign_policy=_UNSIGNED_SIGN_POLICY,
            mandated_values=None,
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
        *(
            NoteGovernedAmountDeclaration(
                source_ref="aeat-dr-200-2025",
                source_sha256="92392cdb46d8e7c7f6e4e6477306570e15edfd64d5ea3e6d631e5cf847dd5509",
                sheet="DP200014B",
                published_content=pointer,
                note_cell=note_cell,
                note_statement=note_statement,
                integer_digits=14,
                decimal_digits=2,
                sign_policy=_N_PREFIX_SIGN_POLICY,
                mandated_values=None,
                evidence=(
                    "Rows A94 and A95 of DP200014B are the two 'Rectificativa' slots the 2025 design added for "
                    "the anterior autoliquidación: ordinales 89 and 90, positions 1408 and 1425, length 17, "
                    "Tipo 'N', described as 'Resultado a ingresar correspondiente a la anterior autoliquidación "
                    "... previos a la rectificación (A)' and '... que se anula con la presentación de esta "
                    "autoliquidación rectificativa (B)'. They are the only two rows of this record whose "
                    "Contenido cell holds anything at all besides a Constante: every one of the twenty-three "
                    "other Tipo 'N' width-17 amounts of the same record leaves it empty and takes the reviewed "
                    "width-17 render profile, which assigns them the signed money form. Both notes were read "
                    "from the sheet that defines them. Nota 1 (A101/A102) states WHEN the two casillas may "
                    "carry content, conditioning them on the página 1 domiciliación-baja field; Nota 2 "
                    "(A105/A106) states a CONSISTENCY relation, that casilla 01578 must equal A - B computed "
                    "from these very campos 89 and 90. Neither states a representation: no scale, no decimal "
                    "count, no sign, no alignment. So the representation is the one this design states for "
                    "itself in DP200001!A121 -- 'NOTA: Los importes son de 15 enteros (o N + 14) y 2 "
                    "decimales' -- the same cell the two DP200019 and DP200020B declarations above already "
                    "cite. That cell states TWO paired forms, not one, and the pairing is what settles these "
                    "rows: '15 enteros' for an unsigned importe, and 'N + 14' for one carrying the sign "
                    "marker, both with 2 decimales, both filling seventeen bytes. These slots are Tipo 'N' and "
                    "hold a resultado a ingresar that the rectificativa arithmetic subtracts, so they take the "
                    "signed form the same design gives their twenty-three siblings: one sign position, "
                    "fourteen integer digits, two decimals. Reading the pointer as an unscaled integer instead "
                    "emits euros into a run whose every other member emits cents, and drops the sign a "
                    "subtraction needs."
                ),
            )
            for pointer, note_cell, note_statement in (
                (
                    "Nota 1",
                    "A102",
                    (
                        'Estas casillas solo pueden tener contenido si el campo "Autoliquidación rectificativa '
                        "- Como consecuencia de la presentación de la autoliquidación rectificativa solicito dar "
                        'de baja la domiciliación efectuada" de la página 1 tiene valor 1 (opción Sí).'
                    ),
                ),
                (
                    "Nota 2",
                    "A106",
                    (
                        'Si el campo "Autoliquidación rectificativa - Como consecuencia de la presentación de la '
                        'autoliquidación rectificativa solicito dar de baja la domiciliación efectuada" de la '
                        "página 1 tiene valor 1 (opción Sí), el valor de la casilla 01578 debe coincidir con el "
                        "resultado de calcular A - B (campos 89 y 90 de esta misma página)."
                    ),
                ),
            )
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
            integer_digits=14,
            decimal_digits=2,
            sign_policy=_N_PREFIX_SIGN_POLICY,
            mandated_values=("0",),
            evidence=(
                "The 2025 design replaced the Contenido clause of the expired temporary-rate slots -- the "
                "0%, 2%, 5% and 7,5% rows and the 0%, 0,26%, 0,62% and 1% recargo rows -- with the pointer "
                "'Nota 2', where the 2024 design of the same modelo spelled '15 enteros 2 decimales' in every "
                "one of them. The note the pointer names says 'estas casillas deben estar rellenas a 0': it "
                "withholds the VALUE for a rate that no longer applies and says nothing about how digits are "
                "written. The representation therefore stands unchanged from the surrounding run, which the "
                "same sheet still states outright on every 17-position amount whose rate survives into 2025 "
                "(4%, 10% and 21% bases and cuotas), and which the 2024 design states on these very rows. "
                "Reading the pointer as an unscaled integer instead would emit euros into a cents field. "
                "The note's OTHER half is the value: 'deben estar rellenas a 0' is a mandate, not guidance, "
                "and it closes these slots to the single quantity zero, which is what mandated_values ('0') "
                "records. Zero is the whole domain because the rates the slots priced -- 0%, 2%, 5%, 7,5% "
                "and the 0%, 0,26%, 0,62% and 1% recargos -- expired before the 2025 ejercicio, so no base "
                "or cuota can accrue against them; the slots survive only to hold the record layout's "
                "positions. The unit spelling is what the fixed-width codec settles against, and on this "
                "fifteen-and-two slot the quantity zero reaches the wire as seventeen zero bytes, which is "
                "also the fill AEAT prescribes for an empty numeric slot -- so the mandate and the blank "
                "fill agree byte for byte and the constraint adds refusal without changing any emitted "
                "record. A cents reading of '0' would be the same bytes here and a hundredfold error on any "
                "nonzero member, which is why the domain is declared in units. The type column types these "
                "slots N, and the sign is declared with the mandate rather than traded for it: N plus "
                "fourteen integer digits and two decimals, the representation the same design states for "
                "its signed seventeen-position amounts, so the zero still reaches the wire as seventeen zero "
                "bytes."
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


def note_governed_amount_for(
    declarations: tuple[NoteGovernedAmountDeclaration, ...],
    *,
    sheet: str,
    published_content: str,
) -> NoteGovernedAmountDeclaration | None:
    """Return the adjudication covering this cell, or ``None`` to derive normally.

    The whole declaration is returned rather than its digit pair alone, because
    the digit pair does not determine the wire form on its own: the same counts
    mean different bytes depending on whether a sign position is spent, and a
    caller handed only ``(integer, decimal)`` would have to guess the rest.

    This is the one matcher a cell is admitted by. The renderer and the
    footnote census both take the covering declaration from it, which is what
    keeps the two from disagreeing about which cells are covered.

    ``published_content`` is the cell's whitespace-normalised content, which is
    what the numeric derivation reads. Anything the declaration does not name
    exactly leaves the caller's own derivation standing, which is the behaviour
    a reader should be able to assume when no declaration applies.
    """
    for declaration in declarations:
        if declaration.sheet != sheet or declaration.published_content != published_content:
            continue
        return declaration
    return None


class NoteStatedApplicabilityDeclaration(BaseModel):
    """One ``Contenido`` cell whose whole content is a note about WHEN a slot applies.

    A :class:`NoteGovernedAmountDeclaration` answers the question "what does this
    note say the representation is". This one answers a different question and
    gives a different answer: the note was read, it states applicability -- which
    periods, which filers, which conditions -- and it states no representation at
    all. Nothing about the wire form was learned, so nothing about the wire form
    may be adjudicated here, and this declaration carries no digit counts by
    construction.

    What it settles is a routing question the design's own vocabulary already
    answers. AEAT's ``Diseños de registro`` manual defines ``Contenido`` as
    "aclaraciones relativas al formato del campo, valores que puede tomar, etc."
    and a ``Nota`` as "aclaraciones al contenido". A cell holding only a pointer
    to an applicability note therefore states no format, exactly as a blank cell
    states none, and the field belongs where every blank-``Contenido`` numeric
    field of its design already goes: to the reviewed render profile.

    That is a REVIEWED PROJECT INFERENCE and not official authority. The field
    inherits whatever rule the profile states for its anchor, on the same
    evidence and with the same standing as its structurally identical siblings --
    no better. What this declaration removes is the anomaly of one field of a run
    being read differently from the rest of it for no reason the design gives.

    It is pinned exactly as its sibling families are -- one file by digest, one
    sheet by name, one exact published pointer -- and is self-limiting for the
    same reasons:

    * The SHA-256 makes a reissued design drop out of the table, so the field
      returns to the historical reading until somebody re-reads the new file.
    * The declaration admits a field to the reviewed profile and decides nothing
      there. If the profile states no rule for that anchor the generator refuses,
      so a declaration cannot by itself put a representation on the wire.
    * The scope is the sheet that PRINTS the note, because a note label
      identifies a note only together with its sheet.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=False)

    source_ref: str = Field(min_length=1)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    sheet: str = Field(min_length=1)
    published_content: str = Field(min_length=1)
    """The pointer exactly as the ``Contenido`` cell publishes it, whitespace-normalised."""
    note_cell: str = Field(min_length=1)
    """Where on this sheet the design defines the note the pointer names."""
    note_statement: str = Field(min_length=1)
    """The note's text as read from that cell, so a later reviewer re-reads it."""
    evidence: str = Field(min_length=1)
    """How the reading was established, in terms a later reviewer can re-check."""


_NOTE_STATED_APPLICABILITY_BY_REF: dict[str, tuple[NoteStatedApplicabilityDeclaration, ...]] = {
    "aeat-dr-353-2026": (
        NoteStatedApplicabilityDeclaration(
            source_ref="aeat-dr-353-2026",
            source_sha256="cb1374a79a87b7c8282ff3c964d78b250bedfa11750decfa0e5e7f90e8f97380",
            sheet="35301",
            published_content="Nota 4.",
            note_cell="B157",
            note_statement="Solo para periodos 02 y siguientes.",
            evidence=(
                "Row A132 of sheet 35301 is the 'Liquidación. Pago a cuenta de entregas de gasolinas, gasóleos "
                "y biocarburantes ... atribuible a la Administración del Estado [10]' slot: position 1211, "
                "length 17, naturaleza 'Num'. Twenty-eight fields of the same record share its width and its "
                "amount family, and every one of them leaves the Contenido cell empty and takes the reviewed "
                "width-17 render profile. This one differs from them in exactly one respect: its Contenido "
                "cell reads 'Nota 4.'. The note is defined on the same sheet at B156/B157 and reads in full "
                "'Solo para periodos 02 y siguientes.' -- a statement of WHEN the slot applies, carrying no "
                "scale, no decimal count, no sign and no alignment. Nothing about the wire form is stated "
                "there, and nothing about it is adjudicated here. This design states no representation for "
                "the slot anywhere: neither the 2026 workbook nor the 2021-2025 one contains the word "
                "'enteros' at all, the 2008 dr353.pdf leaves Contenido empty on every 17-position amount, and "
                "AEAT's general 'Diseños de registro - breve manual de uso' sets no corpus-wide importe rule. "
                "So the field is admitted to the reviewed render profile that already governs its twenty-eight "
                "siblings, and inherits their rule and their evidence -- a reviewed project inference, not an "
                "official statement. Reading the pointer as an unscaled integer instead, which is what the "
                "unadjudicated fallthrough does, emits euros into a run whose every other member emits cents."
            ),
        ),
    ),
}


def note_stated_applicability_for(source_ref: str) -> tuple[NoteStatedApplicabilityDeclaration, ...]:
    """Return the complete applicability-note set declared for one official source."""
    return _NOTE_STATED_APPLICABILITY_BY_REF.get(source_ref, ())


def validate_note_stated_applicability_declarations(
    declarations: tuple[NoteStatedApplicabilityDeclaration, ...],
    source: RecordDesignIntermediateSource,
) -> None:
    """Refuse a declaration set that is not pinned to the design being rendered.

    The SHA-256 is checked against the PARSER-READ source, exactly as the two
    sibling validators check it, so a declaration cannot be admitted by a caller
    that merely asserts the digest it wants.
    """
    seen: set[tuple[str, str, str]] = set()
    for declaration in declarations:
        key = (declaration.source_ref, declaration.sheet, declaration.published_content)
        if key in seen:
            raise RegistryValidationError(
                f"duplicate note-stated applicability declaration for {declaration.source_ref!r} "
                f"sheet {declaration.sheet!r} content {declaration.published_content!r}",
            )
        seen.add(key)
        if declaration.source_ref != source.source_ref:
            raise RegistryValidationError(
                f"note-stated applicability declaration source {declaration.source_ref!r} does not match parser "
                f"intermediate source {source.source_ref!r}",
            )
        if declaration.source_sha256 != source.source_sha256:
            raise RegistryValidationError(
                f"note-stated applicability declaration for {declaration.source_ref!r} is not pinned to the "
                "parser intermediate SHA-256",
            )


def note_stated_applicability_reading_for(
    declarations: tuple[NoteStatedApplicabilityDeclaration, ...],
    *,
    sheet: str,
    published_content: str,
) -> NoteStatedApplicabilityDeclaration | None:
    """Return the applicability reading covering this cell, or ``None``.

    This is the one matcher a cell is admitted by, exactly as
    :func:`note_governed_amount_for` is for the sibling family. The eligibility
    predicate asks it through :func:`note_states_only_applicability` and the
    footnote census asks it for the declaration itself, so neither can hold a
    second copy of the sheet-and-content comparison that decides coverage.

    ``published_content`` is the cell's whitespace-normalised content, which is
    what both the eligibility predicate and the numeric derivation read. Anything
    the declaration does not name exactly leaves the caller's own reading
    standing, which is the behaviour a reader should be able to assume when no
    declaration applies.
    """
    for declaration in declarations:
        if declaration.sheet != sheet or declaration.published_content != published_content:
            continue
        return declaration
    return None


def note_states_only_applicability(
    declarations: tuple[NoteStatedApplicabilityDeclaration, ...],
    *,
    sheet: str,
    published_content: str,
) -> bool:
    """Report whether this exact cell has been read and found to state no wire fact.

    The boolean form of :func:`note_stated_applicability_reading_for`, for the
    eligibility predicate, which needs the verdict and not the declaration.
    """
    return (
        note_stated_applicability_reading_for(declarations, sheet=sheet, published_content=published_content)
        is not None
    )
