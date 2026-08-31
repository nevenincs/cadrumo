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

from typing import Final

import pytest
from pydantic import ValidationError

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.fixed_width_codec import ExportEncoding

from ..pipeline._export_tree import ExportTreeTransportProfile, _literal_derivation
from ..pipeline._record_design_ir import RecordDesignIntermediate, RecordDesignWorkbookFormat
from ..pipeline._semantic_map import SemanticMapEntry
from ..pipeline._semantic_map_join import JoinedRecordDesignField
from ..pipeline._source_defects import (
    SourceDefectDeclaration,
    adjudicated_literal_for,
    validate_source_defect_declarations,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: The real modelo 390 filing-year 2022 workbook digest this mechanism was built for.
_SHA: Final = "7c6554f3182df51daaec37284dd891eb925e1f92df7e69bc01b8ccfb8e4f26fe"
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
            "encoding": ExportEncoding.LATIN_1,
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
        with pytest.raises(ValidationError):
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
