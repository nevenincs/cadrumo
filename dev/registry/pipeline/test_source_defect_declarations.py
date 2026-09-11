"""An adjudicated source defect is narrow, pinned, and cannot launder geometry.

The generator compares every literal field against the AEAT-published design
byte-for-byte, and that comparison is the only check reading the source document
rather than the project's transcription of it. A declaration lets one
*self-contradictory* cell be read the way the document's own surviving half
supports -- and must not become a general tolerance.

These tests pin the three properties the governing ADR relies on:

* the declaration applies only to the exact published bytes it was adjudicated
  against, so a reissued or re-parsed file falls back to refusal;
* it must be pinned to the PARSER-READ source and digest, not a caller's claim;
* and the adjudicated literal is fed back through the same slot-width check,
  so it can resolve a contradiction but never widen a field.

The third is the one worth guarding hardest. Substituting before the geometry
check is what makes the mechanism safe; substituting after it would turn a
narrow adjudication into an arbitrary override, and nothing about the
declaration's own shape would reveal the difference.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Final

import pytest
from pydantic import ValidationError

from cadrumo.core.filing_producer_key import FilingProducerKey
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.fixed_width_codec import (
    ExportEncoding,
    parse_fixed_width_export_field,
    render_fixed_width_export_field,
)
from cadrumo.domain.calculations.registry.static_inspection import RegistryRevisionInspection

from ..compiler.loader import load_registry_tree
from ._export_tree import (
    ExportTreeTransportProfile,
    _literal_derivation,
    _numeric_derivation,
    render_complete_export_tree,
)
from .joined_record_design import JoinedRecordDesignField, join_record_design_semantics
from .record_design_intermediate import (
    RecordDesignIntermediate,
    RecordDesignIntermediateField,
    RecordDesignWorkbookFormat,
    load_record_design_intermediate,
)
from .render_profile import (
    load_render_profile,
    load_render_profile_source_evidence,
)
from .render_profile_eligibility import (
    _states_no_wire_fact,
    project_render_profile_eligibility,
)
from .semantic_map import (
    SemanticMapEntry,
    load_semantic_map,
)
from .source_defects import (
    NoteGovernedAmountDeclaration,
    NoteStatedApplicabilityDeclaration,
    SourceDefectDeclaration,
    adjudicated_literal_for,
    note_governed_amount_for,
    note_governed_amounts_for,
    note_stated_applicability_for,
    note_stated_applicability_reading_for,
    note_states_only_applicability,
    source_defects_for,
    validate_note_governed_amount_declarations,
    validate_note_stated_applicability_declarations,
    validate_source_defect_declarations,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: The hash-pinned 2025 Modelo 390 design both adjudication mechanisms are read from.
_M390_2025_SOURCE_REF: Final = "aeat-dr-390-2025"

#: The real modelo 390 filing-year 2022 workbook digest this mechanism was built for.
_SHA: Final = "7c6554f3182df51daaec37284dd891eb925e1f92df7e69bc01b8ccfb8e4f26fe"
_SHA_2023: Final = "179c02eddc8bab411c249fc3fda19c7015d668e1dd7930d4af79f38998b9c5a7"
_OTHER_SHA: Final = "58f731b0c72eff7fd23484000c74e73e0ac803a5167065176d78cac8712f5fe7"

#: The slot width every adjudicated amount run of these designs declares. Both
#: paired forms of modelo 200's DP200001!A121 fill it: fifteen digits and two
#: decimals unsigned, or a sign position with fourteen and two.
_WIDTH_17: Final = 17

#: The cell content EXACTLY as the production parser hands it to the renderer.
#: Read from the hash-pinned workbook rather than composed here. The wrapper is
#: load-bearing: ``_literal_derivation`` passes ``parser_field.content`` raw,
#: before the note split and the quote fold, so a declaration carrying only the
#: inner tag would silently never match and the generator would refuse as though
#: no declaration existed. Every sibling page reads ``Constante "</T3900N000>"``
#: at 24 characters; this cell reads 23 into a slot it declares as 12.
_PUBLISHED: Final = 'Constante "</T3900700>"'
#: The reading the siblings, the tag grammar and the declared width all support.
_ADJUDICATED: Final = "</T39007000>"


@pytest.mark.parametrize(
    ("source_ref", "source_sha256"),
    (
        ("aeat-dr-390-2022", _SHA),
        ("aeat-dr-390-2023", _SHA_2023),
    ),
)
def test_pipeline_catalogue_owns_each_hash_pinned_m390_adjudication(
    source_ref: str,
    source_sha256: str,
) -> None:
    declarations = source_defects_for(source_ref)

    assert len(declarations) == 1
    declaration = declarations[0]
    assert (
        declaration.source_ref,
        declaration.source_sha256,
        declaration.sheet,
        declaration.source_cell,
        declaration.published_content,
        declaration.adjudicated_literal,
    ) == (source_ref, source_sha256, "Pág. 7", "A53", _PUBLISHED, _ADJUDICATED)
    assert declaration.evidence.strip()


def _declaration(**overrides: object) -> SourceDefectDeclaration:
    fields: dict[str, object] = {
        "source_ref": "aeat-dr-390-2022",
        "source_sha256": _SHA,
        "sheet": "Pág. 7",
        "source_cell": "A53",
        "published_content": _PUBLISHED,
        "adjudicated_literal": _ADJUDICATED,
        "evidence": (
            "xl/sharedStrings.xml of the hash-pinned workbook carries the eleven-character form "
            "while the same cell declares a twelve-byte slot and seven sibling pages carry twelve"
        ),
    }
    fields.update(overrides)
    return SourceDefectDeclaration.model_validate(fields)


def _intermediate(*, source_ref: str = "aeat-dr-390-2022", sha: str = _SHA) -> RecordDesignIntermediate:
    return RecordDesignIntermediate.model_validate(
        {
            "source": {
                "source_ref": source_ref,
                "source_sha256": sha,
                "workbook_format": RecordDesignWorkbookFormat.XLSX,
                "design_epoch": "2022",
            },
            "sheets": (
                {
                    "sheet": "Pág. 7",
                    "record_identity": "modelo-390-page-07",
                    "declared_total": 12,
                    "fields": (
                        {
                            "sheet": "Pág. 7",
                            "record_identity": "modelo-390-page-07",
                            "source_row": 53,
                            "source_cell": "A53",
                            "ordinal": "1",
                            "offset": 1,
                            "length": 12,
                            "aeat_type": "An",
                            "normalized_description": "Fin de registro",
                            "content": _PUBLISHED,
                        },
                    ),
                },
            ),
        }
    )


def _joined_literal_field(*, length: int = 12, literal: str = _ADJUDICATED) -> JoinedRecordDesignField:
    parser_field = _intermediate().sheets[0].fields[0].model_copy(update={"length": length})
    entry = SemanticMapEntry.model_validate(
        {
            "anchor": {
                "sheet": parser_field.sheet,
                "source_row": parser_field.source_row,
                "source_cell": parser_field.source_cell,
                "ordinal": parser_field.ordinal,
                "record_identity": parser_field.record_identity,
            },
            "export_field_id": "modelo-390-page-07-close",
            "kind": "literal",
            "literal": literal,
            "legal_refs": ("orden-hac-1-2021:art-1",),
            "source_refs": ("aeat-dr-390-2022",),
        }
    )
    return JoinedRecordDesignField(parser_field=parser_field, semantic_entry=entry)


def _profile() -> ExportTreeTransportProfile:
    return ExportTreeTransportProfile.model_validate(
        {
            "modelo": "390",
            "design_epoch": "2022",
            "source_ref": "aeat-dr-390-2022",
            "source_sha256": _SHA,
            "layout_id": "aeat-dr-390-2022",
            "format": "fixed_width",
            "encoding": ExportEncoding.ISO_8859_1,
            "line_ending": "crlf",
            "serializer_convention": "rtoml-pretty-v1",
        }
    )


class TestTheDeclarationAppliesOnlyToWhatItAdjudicated:
    def test_the_exact_published_content_resolves_to_the_adjudicated_literal(self) -> None:
        resolved = adjudicated_literal_for(
            (_declaration(),), sheet="Pág. 7", source_cell="A53", published_content=_PUBLISHED
        )

        assert resolved == _ADJUDICATED

    def test_different_published_content_falls_back_to_refusal(self) -> None:
        """A reissued or re-parsed file is not the file that was adjudicated."""
        resolved = adjudicated_literal_for(
            (_declaration(),), sheet="Pág. 7", source_cell="A53", published_content='Constante "</T3900701>"'
        )

        assert resolved is None

    def test_another_cell_is_untouched(self) -> None:
        resolved = adjudicated_literal_for(
            (_declaration(),), sheet="Pág. 7", source_cell="A54", published_content=_PUBLISHED
        )

        assert resolved is None

    def test_an_empty_declaration_set_changes_nothing(self) -> None:
        assert adjudicated_literal_for((), sheet="Pág. 7", source_cell="A53", published_content=_PUBLISHED) is None


class TestTheDeclarationMustBePinnedToTheParsedSource:
    def test_a_matching_declaration_validates(self) -> None:
        validate_source_defect_declarations((_declaration(),), _intermediate().source)

    def test_a_foreign_source_ref_refuses(self) -> None:
        with pytest.raises(RegistryValidationError, match="does not match parser"):
            validate_source_defect_declarations((_declaration(source_ref="aeat-dr-390-2023"),), _intermediate().source)

    def test_a_digest_that_is_not_the_parsed_one_refuses(self) -> None:
        """The pin is what stops a correction outliving the document it describes."""
        with pytest.raises(RegistryValidationError, match="not pinned to the parser"):
            validate_source_defect_declarations((_declaration(source_sha256=_OTHER_SHA),), _intermediate().source)

    def test_two_declarations_for_one_cell_refuse(self) -> None:
        pair = (_declaration(), _declaration(adjudicated_literal="</T39007001>"))

        with pytest.raises(RegistryValidationError, match="duplicate source-defect declaration"):
            validate_source_defect_declarations(pair, _intermediate().source)

    def test_evidence_is_required(self) -> None:
        """A declaration without its reasoning is unreviewed, not merely terse."""
        with pytest.raises(ValidationError, match="evidence"):
            _declaration(evidence="")


class TestTheAdjudicationCannotLaunderGeometry:
    """The substitution runs BEFORE the byte and slot-width checks, not instead of them."""

    def test_the_adjudicated_literal_satisfies_the_slot_and_renders(self) -> None:
        derivation = _literal_derivation(
            _joined_literal_field(),
            _profile(),
            export_record_id="modelo-390-page-07",
            source_defects=(_declaration(),),
        )

        assert derivation.derivation_code == "literal-exact-v1"

    def test_without_the_declaration_the_byte_comparison_still_refuses(self) -> None:
        """Proves the fixture reproduces the real defect rather than passing trivially."""
        with pytest.raises(RegistryValidationError, match="does not agree byte-for-byte"):
            _literal_derivation(
                _joined_literal_field(),
                _profile(),
                export_record_id="modelo-390-page-07",
            )

    def test_an_adjudicated_literal_that_does_not_fill_the_slot_is_still_refused(self) -> None:
        """The mechanism resolves a contradiction; it cannot widen or shrink a field.

        Here the declaration and the reviewed layout agree on an eleven-character
        value, so the byte comparison passes -- and the slot-width check must
        still refuse, because the cell declares twelve. If this ever passes, the
        substitution has moved after the geometry check and the declaration has
        become an arbitrary override.
        """
        with pytest.raises(RegistryValidationError, match="but the official slot is"):
            _literal_derivation(
                _joined_literal_field(literal=_PUBLISHED),
                _profile(),
                export_record_id="modelo-390-page-07",
                source_defects=(_declaration(adjudicated_literal=_PUBLISHED),),
            )


class TestTheValidatorMatchesWhatTheRendererPassesIt:
    """The wiring, not just the pieces.

    Every other test here calls the validator directly, and that is exactly how
    a real defect survived: the renderer passed ``joined.source`` -- already a
    RecordDesignIntermediateSource -- while the validator reached one level
    deeper for ``.source``, so the pieces each worked and the seam raised
    AttributeError the moment a declaration was supplied through the entry
    point. A unit test per function cannot see a mismatch between them.
    """

    def test_the_renderer_passes_the_type_the_validator_declares(self) -> None:
        import inspect

        from . import _export_tree

        hints = inspect.signature(validate_source_defect_declarations).parameters
        annotation = hints["source"].annotation
        assert "RecordDesignIntermediateSource" in str(annotation)

        source = inspect.getsource(_export_tree)
        assert "validate_source_defect_declarations(source_defects, joined.source)" in source

    def test_the_validator_accepts_a_real_joined_source(self) -> None:
        """Drives the actual object the renderer holds, not a stand-in."""
        validate_source_defect_declarations((_declaration(),), _intermediate().source)


class TestNoteGovernedAmountAdjudication:
    """A ``Contenido`` cell holding only a footnote pointer states no scale.

    Modelo 390's 2025 design replaced the ``15 enteros 2 decimales`` clause of
    its expired temporary-rate amount slots with the bare pointer ``Nota 2``,
    whose note reads "estas casillas deben estar rellenas a 0" -- it withholds
    the VALUE and says nothing about how digits are written. Read as an unscaled
    integer, those slots emit euros into a run of monetary casillas whose every
    surviving member emits cents, which is a filing wrong by two orders of
    magnitude and the one condition no per-field rule can see.

    These tests pin the same three properties the literal adjudication above
    relies on -- exact published content, parser-read digest, and geometry fed
    back through the normal width check -- plus the one this mechanism adds: an
    unadjudicated pointer keeps the historical reading rather than being
    silently re-scaled by a rule nobody reviewed for that document.
    """

    _M390_2025_SHA: Final = "6d33d8a4245976e55dc31ff85065b420f76d1588110dc1eb541a8039c5e3f252"
    _POINTER: Final = "Nota 2"

    @staticmethod
    def _declaration(**overrides: object) -> NoteGovernedAmountDeclaration:
        fields: dict[str, object] = {
            "source_ref": "aeat-dr-390-2025",
            "source_sha256": TestNoteGovernedAmountAdjudication._M390_2025_SHA,
            "sheet": "Pág. 2",
            "published_content": TestNoteGovernedAmountAdjudication._POINTER,
            "note_cell": "A119",
            "note_statement": "Nota 2: estas casillas deben estar rellenas a 0",
            "integer_digits": 15,
            "decimal_digits": 2,
            # An unsigned fifteen-and-two run, the shape these mechanics tests
            # exercise; the live 390 runs are signed, as their design types them N.
            "sign_policy": "unsigned",
            "mandated_values": ("0",),
            "evidence": "the surviving rates on the same sheet state 15 enteros 2 decimales at the same width",
        }
        fields.update(overrides)
        return NoteGovernedAmountDeclaration.model_validate(fields)

    @staticmethod
    def _joined_amount_field(
        *, sheet: str = "Pág. 2", length: int = 17, aeat_type: str = "Num"
    ) -> JoinedRecordDesignField:
        """Build one pointer-content amount row; its design type must agree with the run's sign."""
        parser_field = RecordDesignIntermediateField.model_validate(
            {
                "sheet": sheet,
                "record_identity": sheet,
                "source_row": 14,
                "source_cell": "A14",
                "ordinal": "9",
                "offset": 64,
                "length": length,
                "aeat_type": aeat_type,
                "normalized_description": "Reg. ordin. - Tipo 2% - Cuota [668]",
                "content": TestNoteGovernedAmountAdjudication._POINTER,
            }
        )
        entry = SemanticMapEntry.model_validate(
            {
                "anchor": {
                    "sheet": parser_field.sheet,
                    "source_row": parser_field.source_row,
                    "source_cell": parser_field.source_cell,
                    "ordinal": parser_field.ordinal,
                    "record_identity": parser_field.record_identity,
                },
                "export_field_id": "modelo-390-page-02-casilla-tipo-2-cuota",
                "kind": "casilla",
                "casilla_id": "iva.anual.repercutido.tipo-2.cuota",
                "legal_refs": ("ley-37-1992:art-90",),
                "source_refs": ("aeat-dr-390-2025",),
            }
        )
        return JoinedRecordDesignField(parser_field=parser_field, semantic_entry=entry)

    def test_the_live_catalogue_covers_every_sheet_the_2025_design_points_from(self) -> None:
        declarations = note_governed_amounts_for("aeat-dr-390-2025")

        assert {item.sheet for item in declarations} == {"Pág. 2", "Pág. 2 bis", "Pág. 3", "Pág. 4"}
        for declaration in declarations:
            assert declaration.source_sha256 == self._M390_2025_SHA
            assert declaration.published_content == self._POINTER
            # The design types these slots N: N plus fourteen integer digits and
            # two decimals, the signed seventeen-position representation.
            assert declaration.signed is True
            assert (declaration.integer_digits, declaration.decimal_digits) == (14, 2)
            # The note states two things, and both are recorded: the run's
            # representation, and the value it mandates.
            assert declaration.mandated_values == ("0",)
            assert "rellenas a 0" in declaration.note_statement

    def test_an_adjudicated_pointer_renders_the_scale_its_run_states(self) -> None:
        derived = _numeric_derivation(
            self._joined_amount_field(),
            export_record_id="modelo-390-page-02",
            note_governed_amounts=(self._declaration(),),
        )

        assert derived.derivation_code == "numeric-note-governed-amount-v1"
        assert str(derived.field.data_type) == "decimal"
        assert derived.field.decimals == 2

    def test_the_mandated_value_reaches_the_field_and_closes_its_domain(self) -> None:
        """The note mandates zero, so the layout refuses anything else at the boundary.

        Scale alone left the mandate unenforced: a nonzero would have been
        emitted at the right scale, which is a silent under-declaration of what
        the design states. The domain travels from the declaration onto the
        field and the codec settles every value against it, in both directions.
        """
        derived = _numeric_derivation(
            self._joined_amount_field(),
            export_record_id="modelo-390-page-02",
            note_governed_amounts=(self._declaration(),),
        )

        assert derived.field.allowed_values == ("0",)
        # Zero renders as the seventeen zero bytes the mandate describes, which
        # is byte-identical to the blank fill an absent numeric slot takes.
        assert render_fixed_width_export_field(derived.field, Decimal("0.00")) == "0" * 17
        assert render_fixed_width_export_field(derived.field, None) == "0" * 17
        with pytest.raises(RegistryValidationError, match="outside allowed_values"):
            render_fixed_width_export_field(derived.field, Decimal("1.00"))
        with pytest.raises(RegistryValidationError, match="outside allowed_values"):
            parse_fixed_width_export_field(derived.field, "0" * 14 + "100")

    def test_a_run_whose_note_mandates_no_value_leaves_the_domain_open(self) -> None:
        """Absence of a mandate is declared, never defaulted, and stays open.

        A declaration is the record of what a person read in one note. Reading
        390's Nota 2 must not close the domain of a run whose own note says
        nothing about values.
        """
        derived = _numeric_derivation(
            self._joined_amount_field(),
            export_record_id="modelo-390-page-02",
            note_governed_amounts=(self._declaration(mandated_values=None),),
        )

        assert derived.field.allowed_values is None
        assert render_fixed_width_export_field(derived.field, Decimal("1.00")) == "0" * 14 + "100"

    def test_a_mandated_value_the_export_schema_cannot_carry_is_refused(self) -> None:
        """Teeth on the declaration itself, in the three ways it can be wrong."""
        with pytest.raises(ValidationError, match="zero-canonical unsigned unit values"):
            self._declaration(mandated_values=("00",))
        with pytest.raises(ValidationError, match="zero-canonical unsigned unit values"):
            self._declaration(mandated_values=("0", "1234567890123456"))
        with pytest.raises(ValidationError, match="non-empty and unique"):
            self._declaration(mandated_values=())

    def test_a_signed_run_keeps_its_mandated_value_through_to_the_layout(self) -> None:
        """A design can type a slot signed and mandate its value; neither is traded for the other."""
        declaration = self._declaration(
            sign_policy="n-prefix-negative-blank-nonnegative",
            integer_digits=14,
            mandated_values=("0",),
        )

        derived = _numeric_derivation(
            self._joined_amount_field(aeat_type="N"),
            export_record_id="modelo-390-page-02",
            note_governed_amounts=(declaration,),
        )

        assert derived.field.signed is True
        assert str(derived.field.data_type) == "money"
        assert derived.field.allowed_values == ("0",)

    def test_an_unadjudicated_pointer_keeps_the_reading_it_always_had(self) -> None:
        """The correction is opt-in per design; it never re-scales a document nobody read."""
        derived = _numeric_derivation(
            self._joined_amount_field(),
            export_record_id="modelo-390-page-02",
            note_governed_amounts=(),
        )

        assert derived.derivation_code == "numeric-integer-v1"
        assert str(derived.field.data_type) == "integer"

    def test_a_declaration_does_not_reach_another_sheets_note_of_the_same_number(self) -> None:
        """A note label identifies a note only together with the sheet printing it."""
        derived = _numeric_derivation(
            self._joined_amount_field(sheet="Pág. 5"),
            export_record_id="modelo-390-page-05",
            note_governed_amounts=(self._declaration(),),
        )

        assert derived.derivation_code == "numeric-integer-v1"

    def test_the_declared_representation_cannot_contradict_the_slots_own_width(self) -> None:
        with pytest.raises(RegistryValidationError, match="content declares 17"):
            _numeric_derivation(
                self._joined_amount_field(length=16),
                export_record_id="modelo-390-page-02",
                note_governed_amounts=(self._declaration(),),
            )

    def test_a_declaration_pinned_to_another_digest_is_refused(self) -> None:
        with pytest.raises(RegistryValidationError, match="not pinned to the parser"):
            validate_note_governed_amount_declarations(
                (self._declaration(source_sha256=_OTHER_SHA),),
                _intermediate(source_ref="aeat-dr-390-2025", sha=self._M390_2025_SHA).source,
            )


class TestModelo200NoteGovernedAmounts:
    """Modelo 200's 2025 design points two amount runs at notes that state no scale.

    Twenty-six ``Deducción resto del grupo`` slots on DP200019 and the
    ``Incremento porcentual de la plantilla media`` slot on DP200020B carry the
    bare pointer ``Nota 1`` where their siblings carry no ``Contenido`` at all.
    DP200019's note names WHO fills the slot; DP200020B's note spells the
    maximum admissible value together with the seventeen-character wire form it
    takes, which states fifteen integer positions and two decimals outright.
    Either way the run's representation is the one this design states for itself
    in ``DP200001!A121``, and the unscaled integer reading emits euros into a
    cents field.

    These tests hold the declared adjudication against that design, and hold the
    boundary that keeps it from travelling: the two notes carry the same label,
    so a declaration for one sheet must not reach the other.
    """

    _M200_2025_SHA: Final = "92392cdb46d8e7c7f6e4e6477306570e15edfd64d5ea3e6d631e5cf847dd5509"
    _POINTER: Final = "Nota 1"

    @staticmethod
    def _joined_amount_field(*, sheet: str, length: int = 17, content: str | None = None) -> JoinedRecordDesignField:
        # DP200014B's two pointer rows are Tipo 'N'; the DP200019 run this
        # helper was written for is Tipo 'Num'. The type travels with the sheet
        # so each case exercises the row shape its own design publishes.
        signed_sheet = sheet == "DP200014B"
        parser_field = RecordDesignIntermediateField.model_validate(
            {
                "sheet": sheet,
                "record_identity": sheet,
                "source_row": 94 if signed_sheet else 119,
                "source_cell": "A94" if signed_sheet else "A119",
                "ordinal": "89" if signed_sheet else "114",
                "offset": 1408 if signed_sheet else 1849,
                "length": length,
                "aeat_type": "N" if signed_sheet else "Num",
                "normalized_description": (
                    "Resultado a ingresar correspondiente a la anterior autoliquidación (A)"
                    if signed_sheet
                    else "Deducciones I+D+i excluidas de límite - Deducción resto del grupo"
                ),
                "content": content if content is not None else TestModelo200NoteGovernedAmounts._POINTER,
            }
        )
        entry = SemanticMapEntry.model_validate(
            {
                "anchor": {
                    "sheet": parser_field.sheet,
                    "source_row": parser_field.source_row,
                    "source_cell": parser_field.source_cell,
                    "ordinal": parser_field.ordinal,
                    "record_identity": parser_field.record_identity,
                },
                "export_field_id": "m200-2025.dp200019.f0114",
                "kind": "header",
                "producer_key": FilingProducerKey.M200_DEDUCCION_RESTO_DEL_GRUPO,
                "legal_refs": ("ley-27-2014:art-39",),
                "source_refs": ("aeat-dr-200-2025",),
            }
        )
        return JoinedRecordDesignField(parser_field=parser_field, semantic_entry=entry)

    def test_the_live_catalogue_pins_every_pointer_run_to_the_read_design(self) -> None:
        declarations = note_governed_amounts_for("aeat-dr-200-2025")

        assert {item.sheet for item in declarations} == {"DP200019", "DP200020B", "DP200014B"}
        for declaration in declarations:
            assert declaration.source_sha256 == self._M200_2025_SHA
            assert declaration.note_statement.strip() == declaration.note_statement
            assert declaration.note_statement
            # Every run of this design fills the same seventeen-byte slot, by
            # one of the two paired forms DP200001!A121 states.
            assert declaration.wire_length == _WIDTH_17
            assert declaration.decimal_digits == 2

    def test_the_unsigned_runs_spend_every_byte_on_digits(self) -> None:
        by_sheet = {item.sheet: item for item in note_governed_amounts_for("aeat-dr-200-2025")}

        for sheet in ("DP200019", "DP200020B"):
            declaration = by_sheet[sheet]
            assert declaration.published_content == self._POINTER
            assert declaration.sign_policy == "unsigned"
            assert declaration.signed is False
            assert (declaration.integer_digits, declaration.decimal_digits) == (15, 2)

    def test_each_declaration_quotes_the_note_its_own_sheet_defines(self) -> None:
        by_sheet = {item.sheet: item for item in note_governed_amounts_for("aeat-dr-200-2025")}

        assert by_sheet["DP200019"].note_cell == "A254"
        assert "grupos mercantiles" in by_sheet["DP200019"].note_statement
        assert by_sheet["DP200020B"].note_cell == "A106"
        assert "00000000009999999" in by_sheet["DP200020B"].note_statement

    def test_the_pointer_run_renders_the_scale_its_design_states(self) -> None:
        derived = _numeric_derivation(
            self._joined_amount_field(sheet="DP200019"),
            export_record_id="m200-2025-dp200019",
            note_governed_amounts=note_governed_amounts_for("aeat-dr-200-2025"),
        )

        assert derived.field.data_type == "decimal"
        assert derived.field.decimals == 2
        assert derived.derivation_code == "numeric-note-governed-amount-v1"

    def test_the_same_label_on_an_undeclared_sheet_keeps_the_unscaled_reading(self) -> None:
        derived = _numeric_derivation(
            self._joined_amount_field(sheet="DP200015"),
            export_record_id="m200-2025-dp200015",
            note_governed_amounts=note_governed_amounts_for("aeat-dr-200-2025"),
        )

        assert derived.field.data_type == "integer"
        assert derived.field.decimals is None
        assert derived.derivation_code == "numeric-integer-v1"

    def test_the_signed_rectificativa_run_renders_the_paired_form_its_design_states(self) -> None:
        """``DP200001!A121`` states two forms; a Tipo 'N' slot takes ``N + 14``.

        The unsigned reading is not merely differently spelled here: it drops
        the sign the rectificativa subtraction Nota 2 describes needs, and reads
        fourteen integer positions as fifteen, which is a magnitude error of ten
        on top of the hundredfold one the unscaled reading makes.
        """
        for pointer in ("Nota 1", "Nota 2"):
            derived = _numeric_derivation(
                self._joined_amount_field(sheet="DP200014B", content=pointer),
                export_record_id="m200-2025-dp200014b",
                note_governed_amounts=note_governed_amounts_for("aeat-dr-200-2025"),
            )

            assert derived.derivation_code == "numeric-note-governed-amount-v1"
            assert derived.field.data_type == "money", pointer
            assert derived.field.signed is True, pointer
            # `money` carries its scale inside the codec, and the schema refuses
            # a field declaring decimals beside any other data_type.
            assert derived.field.decimals is None, pointer

    def test_each_signed_declaration_quotes_the_note_its_own_row_points_at(self) -> None:
        by_pointer = {
            item.published_content: item
            for item in note_governed_amounts_for("aeat-dr-200-2025")
            if item.sheet == "DP200014B"
        }

        assert set(by_pointer) == {"Nota 1", "Nota 2"}
        for declaration in by_pointer.values():
            assert declaration.sign_policy == "n-prefix-negative-blank-nonnegative"
            assert declaration.signed is True
            assert (declaration.integer_digits, declaration.decimal_digits) == (14, 2)
        assert by_pointer["Nota 1"].note_cell == "A102"
        assert "solo pueden tener contenido" in by_pointer["Nota 1"].note_statement
        assert by_pointer["Nota 2"].note_cell == "A106"
        assert "01578" in by_pointer["Nota 2"].note_statement

    def test_the_signed_width_check_counts_the_sign_position(self) -> None:
        """Sixteen digits and a marker fill seventeen bytes; sixteen bytes do not.

        Without the sign position in the count, this declaration would appear to
        need sixteen bytes and would silently pass in a sixteen-byte slot.
        """
        with pytest.raises(RegistryValidationError, match="content declares 17"):
            _numeric_derivation(
                self._joined_amount_field(sheet="DP200014B", content="Nota 1", length=16),
                export_record_id="m200-2025-dp200014b",
                note_governed_amounts=note_governed_amounts_for("aeat-dr-200-2025"),
            )

    def test_a_signed_declaration_cannot_carry_a_scale_the_money_codec_refuses(self) -> None:
        """The signed wire type fixes two decimals, so no other count may be declared.

        Admitting one would publish a field whose declared scale and emitted
        scale disagree, with nothing downstream positioned to notice.
        """
        signed = next(item for item in note_governed_amounts_for("aeat-dr-200-2025") if item.sheet == "DP200014B")

        with pytest.raises(ValidationError, match="fixes 2 decimals"):
            NoteGovernedAmountDeclaration.model_validate({**signed.model_dump(), "decimal_digits": 4})

    def test_both_designs_n_typed_runs_share_one_signed_representation(self) -> None:
        """Modelo 200 and modelo 390 mean the same wire form by Tipo 'N' on a width-17 amount.

        Modelo 200's DP200001!A121 spells it 'N + 14' beside the unsigned '15'.
        Modelo 390's '15 enteros 2 decimales' states the non-negative capacity
        of the same slot, because the N displaces the leading digit instead of
        claiming a byte. Both runs are declared signed, fourteen and two, and
        fill the same seventeen bytes.
        """
        m200 = next(item for item in note_governed_amounts_for("aeat-dr-200-2025") if item.sheet == "DP200014B")
        m390 = next(iter(note_governed_amounts_for("aeat-dr-390-2025")))

        assert m200.signed is True
        assert (m200.integer_digits, m200.decimal_digits) == (14, 2)
        assert m390.signed is True
        assert (m390.integer_digits, m390.decimal_digits) == (14, 2)
        assert m200.wire_length == m390.wire_length == _WIDTH_17

    def test_the_declared_scale_cannot_contradict_the_slots_own_width(self) -> None:
        with pytest.raises(RegistryValidationError, match="content declares 17"):
            _numeric_derivation(
                self._joined_amount_field(sheet="DP200019", length=16),
                export_record_id="m200-2025-dp200019",
                note_governed_amounts=note_governed_amounts_for("aeat-dr-200-2025"),
            )

    def test_a_declaration_pinned_to_another_digest_is_refused(self) -> None:
        stale = tuple(
            item.model_copy(update={"source_sha256": _OTHER_SHA})
            for item in note_governed_amounts_for("aeat-dr-200-2025")
        )

        with pytest.raises(RegistryValidationError, match="not pinned to the parser"):
            validate_note_governed_amount_declarations(
                stale,
                _intermediate(source_ref="aeat-dr-200-2025", sha=self._M200_2025_SHA).source,
            )


@pytest.fixture(scope="module")
def m390_2025_render_authorities():
    """Assemble the real 390/2025 render inputs the drift gate itself assembles.

    Deliberately the shipped semantic map, render profile, registry tree and
    hash-verified design binary rather than a constructed stand-in: the property
    under test is that the renderer resolves its adjudication set from the
    PARSER-READ source, which a synthetic source could not prove.
    """
    epoch = "2025"
    semantic_map = load_semantic_map(Path("dev/registry/mappings/modelo_390") / epoch)
    render_profile = load_render_profile(Path("dev/registry/render_profiles/modelo_390") / epoch)
    modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    modelo = next(item for item in modelos if str(item.id) == "390")
    inspection = RegistryRevisionInspection.from_revision(
        modelo=modelo,
        revision=modelo.revisions["2025"],
        source_root=bundled_path(),
        sources=catalogues.sources,
        legal_ref_ids=frozenset(catalogues.legal),
    )
    intermediate = load_record_design_intermediate(
        bundled_path(),
        catalogues.sources,
        source_ref=_M390_2025_SOURCE_REF,
        filing_year=2025,
        design_epoch=epoch,
    )
    joined = join_record_design_semantics(semantic_map, intermediate, inspection)
    transport = ExportTreeTransportProfile(
        modelo="390",
        design_epoch=epoch,
        source_ref=_M390_2025_SOURCE_REF,
        source_sha256=intermediate.source.source_sha256,
        layout_id="generated-modelo-390-2025-fichero",
        format="fixed_width",
        encoding=ExportEncoding.ISO_8859_1,
        line_ending="crlf",
        serializer_convention="rtoml-pretty-v1",
    )
    evidence = load_render_profile_source_evidence(
        bundled_path() / catalogues.sources[_M390_2025_SOURCE_REF].corpus_path,
        render_profile,
    )
    return joined, semantic_map, transport, render_profile, evidence


class TestNoteGovernedAmountsReachTheRenderer:
    """The renderer owns the adjudication set; a caller cannot supply or suppress one.

    ``render_complete_export_tree`` takes no note-governed parameter. It resolves
    the set from the joined source it was handed and validates the digest pin
    before rendering, so these two tests drive the real entry point over the real
    390/2025 design rather than asserting that the wiring is spelled a particular
    way in the module text.
    """

    def test_the_expired_rate_slots_render_scaled_with_no_caller_involvement(
        self,
        m390_2025_render_authorities,
        tmp_path: Path,
    ) -> None:
        joined, semantic_map, transport, render_profile, evidence = m390_2025_render_authorities

        rendered = render_complete_export_tree(
            tmp_path / "export",
            revision_id="2025",
            joined=joined,
            semantic_map=semantic_map,
            transport_profile=transport,
            render_profile=render_profile,
            render_profile_source_evidence=evidence,
        )

        adjudicated = tuple(
            derivation
            for derivation in rendered.field_derivations
            if derivation.derivation_code == "numeric-note-governed-amount-v1"
        )
        assert len(adjudicated) == 80, "the expired-rate slots the 2025 design points at Nota 2"
        assert {derivation.parser_field.sheet for derivation in adjudicated} == {
            "Pág. 2",
            "Pág. 2 bis",
            "Pág. 3",
            "Pág. 4",
        }
        for derivation in adjudicated:
            assert derivation.parser_field.content == "Nota 2"
            assert str(derivation.field.data_type) == "money"
            assert derivation.field.signed is True
            # The note mandates a value as well as implying a scale, and both
            # halves reach the layout: every one of the eighty slots is closed
            # to the quantity zero.
            assert derivation.field.allowed_values == ("0",)
        assert not any(
            derivation.derivation_code == "numeric-integer-v1" and derivation.parser_field.length == 17
            for derivation in rendered.field_derivations
        ), "no width-17 amount may still emit unscaled"

    def test_a_source_the_declarations_are_not_pinned_to_is_refused_by_the_renderer(
        self,
        m390_2025_render_authorities,
        tmp_path: Path,
    ) -> None:
        """Validation runs inside the render path, not merely beside it."""
        joined, semantic_map, transport, render_profile, evidence = m390_2025_render_authorities
        drifted = joined.model_copy(update={"source": joined.source.model_copy(update={"source_sha256": _OTHER_SHA})})
        drifted_transport = transport.model_copy(update={"source_sha256": _OTHER_SHA})

        with pytest.raises(RegistryValidationError, match="not pinned to the parser"):
            render_complete_export_tree(
                tmp_path / "export",
                revision_id="2025",
                joined=drifted,
                semantic_map=semantic_map,
                transport_profile=drifted_transport,
                render_profile=render_profile,
                render_profile_source_evidence=evidence,
            )


class TestNoteStatedApplicabilityAdmission:
    """A note that states WHEN a slot applies leaves its wire fact unstated.

    Modelo 353's 2026 design gives its 'Pago a cuenta de entregas de gasolinas'
    slot the ``Contenido`` cell ``Nota 4.`` and leaves the Contenido cell of its
    twenty-eight structurally identical siblings -- same record, same width,
    same amount family -- empty. The note reads "Solo para periodos 02 y
    siguientes." in full: it names the periods the slot applies to and states no
    scale, decimal count, sign or alignment. The siblings reach the reviewed
    width-17 render profile; this one alone fell through to an unscaled integer,
    emitting euros into a run that emits cents.

    A declaration admits the field to that same reviewed profile. It adjudicates
    NO representation -- the model carries no digit counts to adjudicate one
    with -- so the field inherits the profile's reviewed project inference on
    exactly the standing its siblings have, and no better.

    These tests hold the two properties that keep the mechanism from spreading:
    the gate is the declaration and never the pointer-shaped text, and one
    predicate answers for both the renderer's routing and the profile's own
    eligibility, so a field cannot be admitted on one side and refused on the
    other.
    """

    _M353_2026_SHA: Final = "cb1374a79a87b7c8282ff3c964d78b250bedfa11750decfa0e5e7f90e8f97380"
    _POINTER: Final = "Nota 4."

    @staticmethod
    def _amount_field(*, sheet: str = "35301", content: str = "Nota 4.") -> RecordDesignIntermediateField:
        return RecordDesignIntermediateField.model_validate(
            {
                "sheet": sheet,
                "record_identity": sheet,
                "source_row": 132,
                "source_cell": "A132",
                "ordinal": "127",
                "offset": 1211,
                "length": 17,
                "aeat_type": "Num",
                "normalized_description": (
                    "Liquidacion. Pago a cuenta de entregas de gasolinas, gasoleos y biocarburantes [10]"
                ),
                "content": content,
            }
        )

    def test_the_live_catalogue_records_the_note_that_was_read(self) -> None:
        declarations = note_stated_applicability_for("aeat-dr-353-2026")

        assert len(declarations) == 1
        declaration = declarations[0]
        assert declaration.source_sha256 == self._M353_2026_SHA
        assert (declaration.sheet, declaration.published_content) == ("35301", self._POINTER)
        assert declaration.note_statement == "Solo para periodos 02 y siguientes."
        assert "no scale" in declaration.evidence

    def test_the_declaration_cannot_state_a_representation(self) -> None:
        """The family adjudicates admission and nothing about the wire.

        A digit count on this model would let an author adjudicate a scale
        through the family that exists precisely because none was stated.
        """
        with pytest.raises(ValidationError):
            NoteStatedApplicabilityDeclaration.model_validate(
                {
                    "source_ref": "aeat-dr-353-2026",
                    "source_sha256": self._M353_2026_SHA,
                    "sheet": "35301",
                    "published_content": self._POINTER,
                    "note_cell": "B157",
                    "note_statement": "Solo para periodos 02 y siguientes.",
                    "integer_digits": 15,
                    "decimal_digits": 2,
                    "evidence": "x",
                }
            )

    def test_an_undeclared_pointer_cell_still_states_a_wire_fact(self) -> None:
        """The gate is the reading, not the shape: an unopened note moves nothing."""
        field = self._amount_field()

        assert not _states_no_wire_fact(field)
        assert not project_render_profile_eligibility([field]).all_fields

    def test_a_declared_pointer_cell_reaches_the_profile_exactly_as_a_blank_one_does(self) -> None:
        declarations = note_stated_applicability_for("aeat-dr-353-2026")
        field = self._amount_field()

        assert _states_no_wire_fact(field, applicability_notes=declarations)
        eligible = project_render_profile_eligibility([field], applicability_notes=declarations)
        assert eligible.width_17_fields == (field,)
        # The same field with the cell left empty, which is what the declaration
        # says this one amounts to, lands in exactly the same partition.
        assert project_render_profile_eligibility([self._amount_field(content="")]).width_17_fields == (
            self._amount_field(content=""),
        )

    def test_a_declaration_does_not_reach_another_sheet(self) -> None:
        """A note label identifies a note only together with the sheet printing it."""
        assert not _states_no_wire_fact(
            self._amount_field(sheet="35302"),
            applicability_notes=note_stated_applicability_for("aeat-dr-353-2026"),
        )

    def test_a_declaration_pinned_to_another_digest_is_refused(self) -> None:
        stale = tuple(
            item.model_copy(update={"source_sha256": _OTHER_SHA})
            for item in note_stated_applicability_for("aeat-dr-353-2026")
        )

        with pytest.raises(RegistryValidationError, match="not pinned to the parser"):
            validate_note_stated_applicability_declarations(
                stale,
                _intermediate(source_ref="aeat-dr-353-2026", sha=self._M353_2026_SHA).source,
            )


class TestTheOneMatcherEachDeclarationFamilyIsAdmittedBy:
    """The sheet-and-content match that decides coverage, tested where it lives.

    Both families resolve a cell through exactly one accessor --
    :func:`note_governed_amount_for` and
    :func:`note_stated_applicability_reading_for` -- and every consumer takes
    the covering declaration from it rather than repeating the comparison. The
    renderer, the eligibility predicate and the footnote census therefore all
    inherit whatever this match decides, which is why its boundary is asserted
    here directly and not only through a consumer.

    Two boundaries carry the weight. The published content must match EXACTLY,
    so a declaration for ``Nota 2`` leaves a cell reading ``Nota 2.`` to its
    caller's own derivation; and the scope is the sheet that PRINTS the note,
    because the same label on another sheet names another note.

    The declarations are written here rather than read from the shipped table:
    what is under test is the matcher's boundary, and a locally constructed
    pair states the near-miss cases the corpus does not happen to contain.
    """

    _SHEET: Final = "Pág. 2"
    _OTHER_SHEET: Final = "Pág. 3"
    _POINTER: Final = "Nota 2"

    def _amount(self) -> NoteGovernedAmountDeclaration:
        return NoteGovernedAmountDeclaration(
            source_ref=_M390_2025_SOURCE_REF,
            source_sha256=_SHA,
            sheet=self._SHEET,
            published_content=self._POINTER,
            note_cell="A119",
            note_statement="Nota 2: estas casillas deben estar rellenas a 0",
            integer_digits=15,
            decimal_digits=2,
            sign_policy="unsigned",
            mandated_values=("0",),
            evidence="Written here to state the matcher's boundary cases.",
        )

    def _applicability(self) -> NoteStatedApplicabilityDeclaration:
        return NoteStatedApplicabilityDeclaration(
            source_ref=_M390_2025_SOURCE_REF,
            source_sha256=_SHA,
            sheet=self._SHEET,
            published_content=self._POINTER,
            note_cell="A119",
            note_statement="Solo para periodos 02 y siguientes.",
            evidence="Written here to state the matcher's boundary cases.",
        )

    def test_a_covered_cell_returns_the_declaration_itself(self) -> None:
        """The caller receives the adjudication, not a verdict it must re-find."""
        amount = self._amount()
        applicability = self._applicability()

        assert note_governed_amount_for((amount,), sheet=self._SHEET, published_content=self._POINTER) is amount
        assert (
            note_stated_applicability_reading_for((applicability,), sheet=self._SHEET, published_content=self._POINTER)
            is applicability
        )

    def test_an_empty_declaration_set_covers_nothing(self) -> None:
        assert note_governed_amount_for((), sheet=self._SHEET, published_content=self._POINTER) is None
        assert note_stated_applicability_reading_for((), sheet=self._SHEET, published_content=self._POINTER) is None

    def test_content_the_declaration_does_not_name_exactly_is_not_covered(self) -> None:
        """A trailing period is a different cell, and the caller's own reading stands.

        The whole mechanism is that a reviewed reading covers the exact bytes it
        was adjudicated against. A matcher admitting a near miss would extend
        somebody's reading of one cell to a cell they never read.
        """
        near_miss = f"{self._POINTER}."

        assert note_governed_amount_for((self._amount(),), sheet=self._SHEET, published_content=near_miss) is None
        assert (
            note_stated_applicability_reading_for(
                (self._applicability(),), sheet=self._SHEET, published_content=near_miss
            )
            is None
        )

    def test_a_declaration_does_not_reach_the_same_label_on_another_sheet(self) -> None:
        """A design numbers each page's notes from one, so the label needs its sheet."""
        assert (
            note_governed_amount_for((self._amount(),), sheet=self._OTHER_SHEET, published_content=self._POINTER)
            is None
        )
        assert (
            note_stated_applicability_reading_for(
                (self._applicability(),), sheet=self._OTHER_SHEET, published_content=self._POINTER
            )
            is None
        )

    def test_the_boolean_form_agrees_with_the_declaration_form_on_every_input(self) -> None:
        """The eligibility predicate cannot answer differently from the census.

        ``note_states_only_applicability`` is the boolean of the same matcher, so
        the two answers are one answer by construction. This asserts that
        property at the cases where it would matter -- the hit, the near miss and
        the other sheet -- so a future implementation that re-scanned instead of
        delegating would have to keep them agreeing.
        """
        declarations = (self._applicability(),)
        for sheet, content in (
            (self._SHEET, self._POINTER),
            (self._SHEET, f"{self._POINTER}."),
            (self._OTHER_SHEET, self._POINTER),
            (self._SHEET, "Nota 3"),
        ):
            reading = note_stated_applicability_reading_for(declarations, sheet=sheet, published_content=content)
            assert note_states_only_applicability(declarations, sheet=sheet, published_content=content) == (
                reading is not None
            ), f"the two forms disagree for {sheet!r} {content!r}"
