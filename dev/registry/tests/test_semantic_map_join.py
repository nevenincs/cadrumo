"""Real-authority tests for exact parser-to-semantic-map joining."""

from __future__ import annotations

import inspect

import pytest
from pydantic import ValidationError

from cadrumo.domain.calculations.registry import RegistryValidationError, bundled_authority

from .. import _semantic_map_join
from .._record_design_ir import RecordDesignIntermediate, RecordDesignWorkbookFormat
from .._semantic_map import SemanticMap
from .._semantic_map_join import JoinedRecordDesignField, join_record_design_semantics

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.fixture
def _m200_snapshot():
    return bundled_authority().snapshot("200", filing_year=2025, period="0A")


def _intermediate(snapshot) -> RecordDesignIntermediate:
    return RecordDesignIntermediate.model_validate(
        {
            "source": {
                "source_ref": "aeat-dr-200-2025",
                "source_sha256": snapshot.sources["aeat-dr-200-2025"].sha256,
                "workbook_format": RecordDesignWorkbookFormat.XLSX,
                "design_epoch": "2025",
            },
            "sheets": (
                {
                    "sheet": "Registro tipo 1",
                    "record_identity": "registro-tipo-1",
                    "declared_total": 2,
                    "fields": (
                        {
                            "sheet": "Registro tipo 1",
                            "record_identity": "registro-tipo-1",
                            "source_row": 14,
                            "source_cell": "A14",
                            "ordinal": 1,
                            "offset": 1,
                            "length": 1,
                            "aeat_type": "AN",
                            "normalized_description": "Campo uno",
                        },
                        {
                            "sheet": "Registro tipo 1",
                            "record_identity": "registro-tipo-1",
                            "source_row": 15,
                            "source_cell": "A15",
                            "ordinal": 2,
                            "offset": 2,
                            "length": 1,
                            "aeat_type": "AN",
                            "normalized_description": "Campo dos",
                        },
                    ),
                },
            ),
        },
    )


def _entry(*, row: int, ordinal: int, field_id: str, literal: str) -> dict[str, object]:
    return {
        "anchor": {
            "sheet": "Registro tipo 1",
            "source_row": row,
            "source_cell": f"A{row}",
            "ordinal": ordinal,
            "record_identity": "registro-tipo-1",
        },
        "export_field_id": field_id,
        "kind": "literal",
        "literal": literal,
        "legal_refs": ("ley-27-2014:art-40",),
        "source_refs": ("aeat-dr-200-2025",),
    }


def _semantic_map(*, entries: tuple[dict[str, object], ...]) -> SemanticMap:
    return SemanticMap.model_validate(
        {
            "modelo": "200",
            "design_epoch": "2025",
            "records": (
                {
                    "sheet": "Registro tipo 1",
                    "record_identity": "registro-tipo-1",
                    "export_record_id": "registro-tipo-1",
                    "record_type": "declaracion",
                },
            ),
            "entries": entries,
        },
    )


def test_join_preserves_parser_coordinates_and_source_order_with_reviewed_meaning(_m200_snapshot) -> None:
    """Map declaration order cannot alter the official parser's field sequence."""
    intermediate = _intermediate(_m200_snapshot)
    semantic_map = _semantic_map(
        entries=(
            _entry(row=15, ordinal=2, field_id="registro-tipo-1.literal.two", literal="0"),
            _entry(row=14, ordinal=1, field_id="registro-tipo-1.literal.one", literal="T"),
        ),
    )

    joined = join_record_design_semantics(semantic_map, intermediate, _m200_snapshot)

    assert joined.source == intermediate.source
    assert joined.records[0].semantic_record.export_record_id == "registro-tipo-1"
    assert tuple(
        (field.parser_field.offset, field.parser_field.length, field.semantic_entry.export_field_id)
        for field in joined.fields
    ) == (
        (1, 1, "registro-tipo-1.literal.one"),
        (2, 1, "registro-tipo-1.literal.two"),
    )
    assert tuple(field.semantic_entry.literal for field in joined.fields) == ("T", "0")


def test_join_refuses_nearby_anchor_instead_of_matching_by_map_position(_m200_snapshot) -> None:
    """A field with changed official anchor cannot be paired to a nearby entry."""
    intermediate = _intermediate(_m200_snapshot)
    semantic_map = _semantic_map(
        entries=(
            _entry(row=14, ordinal=1, field_id="registro-tipo-1.literal.one", literal="T"),
            _entry(row=16, ordinal=2, field_id="registro-tipo-1.literal.two", literal="0"),
        ),
    )

    with pytest.raises(RegistryValidationError, match=r"missing semantic entries.*extra semantic entries"):
        join_record_design_semantics(semantic_map, intermediate, _m200_snapshot)


def test_joined_field_refuses_direct_nonidentical_anchor_pair(_m200_snapshot) -> None:
    """The joined value preserves the exact-anchor invariant beyond the factory."""
    parser_field = _intermediate(_m200_snapshot).sheets[0].fields[0]
    semantic_entry = _semantic_map(
        entries=(_entry(row=15, ordinal=2, field_id="registro-tipo-1.literal.two", literal="0"),),
    ).entries[0]

    with pytest.raises(ValidationError, match="same complete exact anchor"):
        JoinedRecordDesignField(parser_field=parser_field, semantic_entry=semantic_entry)


def test_join_module_rejects_forbidden_non_authoritative_surfaces() -> None:
    """Structural red guard prevents silently restoring an old admission path."""
    source = inspect.getsource(_semantic_map_join).lower()

    for forbidden in (
        "resolve_export_layout",
        "export_layouts",
        "bundled_authority",
        "legacy",
        "fuzzy",
        "positional",
        "fallback",
        "extracted",
        "derivative",
        "provenance",
        "render",
        "load_export_layout",
    ):
        assert forbidden not in source
