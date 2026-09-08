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

from pathlib import Path
from typing import Final

import pytest
from pydantic import ValidationError

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.fixed_width_codec import ExportEncoding
from cadrumo.domain.calculations.registry.loader import load_registry_tree
from cadrumo.domain.calculations.registry.static_inspection import RegistryRevisionInspection

from ..pipeline._export_tree import (
    ExportTreeTransportProfile,
    _literal_derivation,
    _numeric_derivation,
    render_complete_export_tree,
)
from ..pipeline._record_design_ir import (
    RecordDesignIntermediate,
    RecordDesignIntermediateField,
    RecordDesignWorkbookFormat,
    load_record_design_intermediate,
)
from ..pipeline._render_profile import load_render_profile, load_render_profile_source_evidence
from ..pipeline._semantic_map import SemanticMapEntry
from ..pipeline._semantic_map_join import JoinedRecordDesignField, join_record_design_semantics
from ..pipeline._semantic_map_loader import load_semantic_map
from ..pipeline.source_defects import (
    NoteGovernedAmountDeclaration,
    SourceDefectDeclaration,
    adjudicated_literal_for,
    note_governed_amounts_for,
    source_defects_for,
    validate_note_governed_amount_declarations,
    validate_source_defect_declarations,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: The hash-pinned 2025 Modelo 390 design both adjudication mechanisms are read from.
_M390_2025_SOURCE_REF: Final = "aeat-dr-390-2025"

#: The real modelo 390 filing-year 2022 workbook digest this mechanism was built for.
_SHA: Final = "7c6554f3182df51daaec37284dd891eb925e1f92df7e69bc01b8ccfb8e4f26fe"
_SHA_2023: Final = "179c02eddc8bab411c249fc3fda19c7015d668e1dd7930d4af79f38998b9c5a7"
_OTHER_SHA: Final = "58f731b0c72eff7fd23484000c74e73e0ac803a5167065176d78cac8712f5fe7"

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

        from ..pipeline import _export_tree

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
            "evidence": "the surviving rates on the same sheet state 15 enteros 2 decimales at the same width",
        }
        fields.update(overrides)
        return NoteGovernedAmountDeclaration.model_validate(fields)

    @staticmethod
    def _joined_amount_field(*, sheet: str = "Pág. 2", length: int = 17) -> JoinedRecordDesignField:
        parser_field = RecordDesignIntermediateField.model_validate(
            {
                "sheet": sheet,
                "record_identity": sheet,
                "source_row": 14,
                "source_cell": "A14",
                "ordinal": "9",
                "offset": 64,
                "length": length,
                "aeat_type": "N",
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
            assert (declaration.integer_digits, declaration.decimal_digits) == (15, 2)

    def test_an_adjudicated_pointer_renders_the_scale_its_run_states(self) -> None:
        derived = _numeric_derivation(
            self._joined_amount_field(),
            export_record_id="modelo-390-page-02",
            note_governed_amounts=(self._declaration(),),
        )

        assert derived.derivation_code == "numeric-note-governed-amount-v1"
        assert str(derived.field.data_type) == "decimal"
        assert derived.field.decimals == 2

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
            assert str(derivation.field.data_type) == "decimal"
            assert derivation.field.decimals == 2
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
