"""Real-authority tests for exact parser-to-semantic-map joining."""

from __future__ import annotations

import inspect

import pytest
from pydantic import ValidationError

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.static_inspection import RegistryRevisionInspection
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope

from ..compiler.authority import compiled_bundled_authority
from ..pipeline import joined_record_design
from ..pipeline.joined_record_design import JoinedRecordDesignField, join_record_design_semantics
from ..pipeline.record_design_intermediate import (
    RecordDesignIntermediate,
)
from ..pipeline.semantic_map import SemanticMap
from ..pipeline.semantic_map_validation import SemanticMapAnomalyException
from .semantic_map_intermediate_support import intermediate_payload

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _design_epoch(source_ref: str) -> str:
    """Return the record-design epoch the published authority declares for one design source."""
    with bundled_indexed_authority().operation() as operation:
        epoch = operation.source_reference(source_ref).record_design_epoch
    assert epoch is not None, f"design source {source_ref} declares no record-design epoch"
    return str(epoch)


_M130_EPOCH = _design_epoch("aeat-dr-130-2019-v12")


@pytest.fixture
def _m130_inspection() -> RegistryRevisionInspection:
    return compiled_bundled_authority().inspect_revision("130", filing_year=filing_year_envelope().horizon, period="1T")


#: Validated against modelo 130, not modelo 200. The 200 revision declares 578
#: projection endpoints that semantic-map validation checks as a bijection, and
#: a synthetic two-entry map cannot satisfy them, so every case here refused on
#: "omits target-revision projection declarations" before reaching the join it
#: asserts. Modelo 130 is a real revision authority declaring none.
def _intermediate(snapshot) -> RecordDesignIntermediate:
    return RecordDesignIntermediate.model_validate(
        intermediate_payload(
            source_ref="aeat-dr-130-2019-v12",
            source_sha256=snapshot.sources["aeat-dr-130-2019-v12"].sha256,
            design_epoch=_M130_EPOCH,
        )
    )


def _entry(
    *,
    row: int,
    ordinal: int,
    field_id: str,
    literal: str,
    source_cell: str | None = None,
) -> dict[str, object]:
    return {
        "anchor": {
            "sheet": "Registro tipo 1",
            "source_row": row,
            "source_cell": source_cell if source_cell is not None else f"A{row}",
            # Stringified: the anchor ordinal is the design's PRINTED ordinal,
            # which the model requires as a string. Passing the int made every
            # case here die on a ValidationError cascade rather than on the
            # join behaviour it asserts.
            "ordinal": str(ordinal),
            "record_identity": "registro-tipo-1",
        },
        "export_field_id": field_id,
        "kind": "literal",
        "literal": literal,
        "legal_refs": ("rd-439-2007:art-110",),
        "source_refs": ("aeat-dr-130-2019-v12",),
    }


def _semantic_map(*, entries: tuple[dict[str, object], ...]) -> SemanticMap:
    return SemanticMap.model_validate(
        {
            "modelo": "130",
            "design_epoch": _M130_EPOCH,
            "source_ref": "aeat-dr-130-2019-v12",
            "source_sha256": "58f731b0c72eff7fd23484000c74e73e0ac803a5167065176d78cac8712f5fe7",
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


def test_join_preserves_parser_coordinates_and_source_order_with_reviewed_meaning(_m130_inspection) -> None:
    """Map declaration order cannot alter the official parser's field sequence."""
    intermediate = _intermediate(_m130_inspection)
    semantic_map = _semantic_map(
        entries=(
            _entry(row=15, ordinal=2, field_id="registro-tipo-1.literal.two", literal="0"),
            _entry(row=14, ordinal=1, field_id="registro-tipo-1.literal.one", literal="T"),
        ),
    )

    joined = join_record_design_semantics(semantic_map, intermediate, _m130_inspection)

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


def test_join_refuses_nearby_anchor_instead_of_matching_by_map_position(_m130_inspection) -> None:
    """A field with changed official anchor cannot be paired to a nearby entry."""
    intermediate = _intermediate(_m130_inspection)
    semantic_map = _semantic_map(
        entries=(
            _entry(row=14, ordinal=1, field_id="registro-tipo-1.literal.one", literal="T"),
            _entry(row=16, ordinal=2, field_id="registro-tipo-1.literal.two", literal="0"),
        ),
    )

    with pytest.raises(RegistryValidationError, match=r"missing semantic entries.*extra semantic entries"):
        join_record_design_semantics(semantic_map, intermediate, _m130_inspection)


@pytest.mark.parametrize(
    ("entries", "message"),
    [
        (
            (_entry(row=14, ordinal=1, field_id="registro-tipo-1.literal.one", literal="T"),),
            "missing semantic entries",
        ),
        (
            (
                _entry(row=14, ordinal=1, field_id="registro-tipo-1.literal.one", literal="T"),
                _entry(row=14, ordinal=1, field_id="registro-tipo-1.literal.two", literal="0"),
                _entry(row=15, ordinal=2, field_id="registro-tipo-1.literal.three", literal="0"),
            ),
            "duplicate exact anchors",
        ),
    ],
)
def test_join_refuses_incomplete_or_duplicate_map_before_constructing_any_design(
    _m130_inspection,
    entries: tuple[dict[str, object], ...],
    message: str,
) -> None:
    """The join factory rejects the full design instead of retaining valid slots."""
    intermediate = _intermediate(_m130_inspection)
    semantic_map = _semantic_map(entries=entries)

    with pytest.raises(RegistryValidationError, match=message):
        join_record_design_semantics(semantic_map, intermediate, _m130_inspection)


def test_join_refuses_cell_only_anchor_variant_without_fuzzy_matching(_m130_inspection) -> None:
    """Sharing row, ordinal, and record identity cannot substitute a workbook cell."""
    intermediate = _intermediate(_m130_inspection)
    semantic_map = _semantic_map(
        entries=(
            _entry(row=14, ordinal=1, field_id="registro-tipo-1.literal.one", literal="T"),
            _entry(
                row=15,
                ordinal=2,
                field_id="registro-tipo-1.literal.two",
                literal="0",
                source_cell="B15",
            ),
        ),
    )

    with pytest.raises(RegistryValidationError, match=r"missing semantic entries.*extra semantic entries"):
        join_record_design_semantics(semantic_map, intermediate, _m130_inspection)


def test_join_refuses_ambiguous_parser_anchor_before_constructing_any_design(_m130_inspection) -> None:
    """Duplicate parser identities cannot select one matching semantic entry."""
    base_intermediate = _intermediate(_m130_inspection)
    base_payload = base_intermediate.model_dump()
    first_sheet = base_payload["sheets"][0]
    ambiguous_intermediate = RecordDesignIntermediate.model_validate(
        {
            **base_payload,
            "sheets": (
                {
                    **first_sheet,
                    "fields": (first_sheet["fields"][0], first_sheet["fields"][0]),
                },
            ),
        },
    )
    semantic_map = _semantic_map(
        entries=(
            _entry(row=14, ordinal=1, field_id="registro-tipo-1.literal.one", literal="T"),
            _entry(row=15, ordinal=2, field_id="registro-tipo-1.literal.two", literal="0"),
        ),
    )

    with pytest.raises(RegistryValidationError, match="duplicate exact anchors"):
        join_record_design_semantics(semantic_map, ambiguous_intermediate, _m130_inspection)


def test_join_never_uses_anomaly_exception_as_missing_mapping_authority(_m130_inspection) -> None:
    """A valid hash-pinned explanation cannot supply the absent semantic slot."""
    intermediate = _intermediate(_m130_inspection)
    semantic_map = _semantic_map(
        entries=(_entry(row=14, ordinal=1, field_id="registro-tipo-1.literal.one", literal="T"),),
    )
    exception = SemanticMapAnomalyException(
        source_ref="aeat-dr-130-2019-v12",
        source_sha256=_m130_inspection.sources["aeat-dr-130-2019-v12"].sha256,
        category="parser_anomaly",
        reason="The source condition is reviewed but cannot waive map coverage.",
    )

    with pytest.raises(RegistryValidationError, match="missing semantic entries"):
        join_record_design_semantics(
            semantic_map,
            intermediate,
            _m130_inspection,
            anomaly_exceptions=(exception,),
        )


def test_joined_field_refuses_direct_nonidentical_anchor_pair(_m130_inspection) -> None:
    """The joined value preserves the exact-anchor invariant beyond the factory."""
    parser_field = _intermediate(_m130_inspection).sheets[0].fields[0]
    semantic_entry = _semantic_map(
        entries=(_entry(row=15, ordinal=2, field_id="registro-tipo-1.literal.two", literal="0"),),
    ).entries[0]

    with pytest.raises(ValidationError, match="same complete exact anchor"):
        JoinedRecordDesignField(parser_field=parser_field, semantic_entry=semantic_entry)


def test_join_module_rejects_forbidden_non_authoritative_surfaces() -> None:
    """Structural red guard prevents silently restoring an old admission path."""
    source = inspect.getsource(joined_record_design).lower()

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
        "single_file",
        "direct_revision",
        "difflib",
        "rapidfuzz",
        "get_close_matches",
        "similarity",
        "nearest",
    ):
        assert forbidden not in source
