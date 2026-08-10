"""Real-authority tests for semantic-map to parser-intermediate validation."""

from __future__ import annotations

import ast
import inspect

import pytest
from pydantic import ValidationError

from cadrumo.domain.calculations.registry import RegistryValidationError, bundled_authority, resolve_export_layout

from .. import _semantic_map_validation
from .._record_design_ir import RecordDesignIntermediate, RecordDesignWorkbookFormat
from .._semantic_map import SemanticMap
from .._semantic_map_validation import SemanticMapAnomalyException, validate_semantic_map

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.fixture
def _m200_snapshot():
    return bundled_authority().snapshot("200", filing_year=2025, period="0A")


def _intermediate_payload(*, source_sha256: str = "0" * 64) -> dict[str, object]:
    return {
        "source": {
            "source_ref": "aeat-dr-200-2025",
            "source_sha256": source_sha256,
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
    }


def _semantic_map_payload(*, entries: tuple[dict[str, object], ...]) -> dict[str, object]:
    return {
        "modelo": "200",
        "design_epoch": "2025",
        "entries": entries,
    }


def _entry(*, row: int, ordinal: int, field_id: str, kind: str = "literal", **payload: object) -> dict[str, object]:
    return {
        "anchor": {
            "sheet": "Registro tipo 1",
            "source_row": row,
            "source_cell": f"A{row}",
            "ordinal": ordinal,
            "record_identity": "registro-tipo-1",
        },
        "export_field_id": field_id,
        "kind": kind,
        "legal_refs": ("ley-27-2014:art-40",),
        "source_refs": ("aeat-dr-200-2025",),
        **payload,
    }


def _real_source_sha256(snapshot) -> str:
    return snapshot.sources["aeat-dr-200-2025"].sha256


def test_validation_accepts_complete_exact_map_with_live_revision_authority(_m200_snapshot) -> None:
    """A complete map resolves through the real M200 source and target revision."""
    source_sha256 = _real_source_sha256(_m200_snapshot)
    intermediate = RecordDesignIntermediate.model_validate(_intermediate_payload(source_sha256=source_sha256))
    semantic_map = SemanticMap.model_validate(
        _semantic_map_payload(
            entries=(
                _entry(row=14, ordinal=1, field_id="generated.literal.one", literal="T"),
                _entry(row=15, ordinal=2, field_id="generated.literal.two", literal="0"),
            ),
        ),
    )

    validate_semantic_map(semantic_map, intermediate, _m200_snapshot)


@pytest.mark.parametrize(
    ("entries", "message"),
    [
        (
            (_entry(row=14, ordinal=1, field_id="generated.literal.one", literal="T"),),
            "missing semantic entries",
        ),
        (
            (
                _entry(row=14, ordinal=1, field_id="generated.literal.one", literal="T"),
                _entry(row=14, ordinal=1, field_id="generated.literal.two", literal="0"),
                _entry(row=15, ordinal=2, field_id="generated.literal.three", literal="0"),
            ),
            "duplicate exact anchors",
        ),
        (
            (
                _entry(row=14, ordinal=1, field_id="generated.literal.one", literal="T"),
                _entry(row=15, ordinal=2, field_id="generated.literal.two", literal="0"),
                _entry(row=16, ordinal=3, field_id="generated.literal.three", literal="0"),
            ),
            "extra semantic entries",
        ),
    ],
)
def test_validation_refuses_missing_duplicate_or_extra_anchor_mappings(
    _m200_snapshot,
    entries: tuple[dict[str, object], ...],
    message: str,
) -> None:
    """No anomaly declaration can turn an incomplete or ambiguous map into a join."""
    source_sha256 = _real_source_sha256(_m200_snapshot)
    intermediate = RecordDesignIntermediate.model_validate(_intermediate_payload(source_sha256=source_sha256))
    semantic_map = SemanticMap.model_validate(_semantic_map_payload(entries=entries))
    exception = SemanticMapAnomalyException(
        source_ref="aeat-dr-200-2025",
        source_sha256=source_sha256,
        category="parser_anomaly",
        reason="Reviewed parser anomaly does not waive map completeness.",
    )

    with pytest.raises(RegistryValidationError, match=message):
        validate_semantic_map(semantic_map, intermediate, _m200_snapshot, anomaly_exceptions=(exception,))


@pytest.mark.parametrize(
    ("entry", "message"),
    [
        (
            _entry(
                row=14,
                ordinal=1,
                field_id="generated.casilla.one",
                kind="casilla",
                casilla_id="casilla.999999",
            ),
            "unknown target-revision casilla",
        ),
        (
            _entry(
                row=14,
                ordinal=1,
                field_id="generated.binding.one",
                kind="binding",
                binding="unknown.binding",
            ),
            "unknown target-revision binding",
        ),
        (
            _entry(
                row=14,
                ordinal=1,
                field_id="generated.literal.one",
                literal="T",
                legal_refs=("unknown:legal",),
            ),
            "unresolved legal refs",
        ),
        (
            _entry(
                row=14,
                ordinal=1,
                field_id="generated.literal.one",
                literal="T",
                source_refs=("unknown-source",),
            ),
            "unresolved source refs",
        ),
    ],
)
def test_validation_refuses_unresolved_canonical_semantic_references(
    _m200_snapshot,
    entry: dict[str, object],
    message: str,
) -> None:
    """Casilla, binding, and evidence references resolve only through the snapshot."""
    source_sha256 = _real_source_sha256(_m200_snapshot)
    intermediate = RecordDesignIntermediate.model_validate(_intermediate_payload(source_sha256=source_sha256))
    second = _entry(row=15, ordinal=2, field_id="generated.literal.two", literal="0")
    semantic_map = SemanticMap.model_validate(
        _semantic_map_payload(entries=(entry, second)),
    )

    with pytest.raises(RegistryValidationError, match=message):
        validate_semantic_map(semantic_map, intermediate, _m200_snapshot)


def test_validation_refuses_duplicate_export_id_without_consulting_legacy_layout(_m200_snapshot) -> None:
    """Generated-layout identifiers are grammar-validated and map-local unique."""
    source_sha256 = _real_source_sha256(_m200_snapshot)
    intermediate = RecordDesignIntermediate.model_validate(_intermediate_payload(source_sha256=source_sha256))
    semantic_map = SemanticMap.model_validate(
        _semantic_map_payload(
            entries=(
                _entry(row=14, ordinal=1, field_id="generated.literal", literal="T"),
                _entry(row=15, ordinal=2, field_id="generated.literal", literal="0"),
            ),
        ),
    )

    with pytest.raises(RegistryValidationError, match="duplicate canonical export field ids"):
        validate_semantic_map(semantic_map, intermediate, _m200_snapshot)


def test_anomaly_exception_is_hash_pinned_and_cannot_supply_coordinates(_m200_snapshot) -> None:
    """Anomalies name only a source condition and retain the full bijection gate."""
    source_sha256 = _real_source_sha256(_m200_snapshot)
    intermediate = RecordDesignIntermediate.model_validate(_intermediate_payload(source_sha256=source_sha256))
    semantic_map = SemanticMap.model_validate(
        _semantic_map_payload(
            entries=(
                _entry(row=14, ordinal=1, field_id="generated.literal.one", literal="T"),
                _entry(row=15, ordinal=2, field_id="generated.literal.two", literal="0"),
            ),
        ),
    )
    exception = SemanticMapAnomalyException(
        source_ref="aeat-dr-200-2025",
        source_sha256=source_sha256,
        category="source_anomaly",
        reason="Official workbook records a reviewable source anomaly.",
    )

    validate_semantic_map(semantic_map, intermediate, _m200_snapshot, anomaly_exceptions=(exception,))

    with pytest.raises(RegistryValidationError, match="not pinned to the parser intermediate SHA-256"):
        validate_semantic_map(
            semantic_map,
            intermediate,
            _m200_snapshot,
            anomaly_exceptions=(exception.model_copy(update={"source_sha256": "1" * 64}),),
        )
    with pytest.raises(ValidationError, match="extra_forbidden"):
        SemanticMapAnomalyException.model_validate(
            {
                **exception.model_dump(),
                "source_row": 14,
            },
        )


def test_validation_uses_no_legacy_export_layout_membership_or_identifier_inference(_m200_snapshot) -> None:
    """A novel generated ID validates without consulting the unverified legacy tree."""
    source_sha256 = _real_source_sha256(_m200_snapshot)
    intermediate = RecordDesignIntermediate.model_validate(_intermediate_payload(source_sha256=source_sha256))
    semantic_map = SemanticMap.model_validate(
        _semantic_map_payload(
            entries=(
                _entry(row=14, ordinal=1, field_id="generated.s05.literal.one", literal="T"),
                _entry(row=15, ordinal=2, field_id="generated.s05.literal.two", literal="0"),
            ),
        ),
    )
    legacy_fields = resolve_export_layout(_m200_snapshot, "modelo-200-fichero-boe").fields_by_id

    assert "generated.s05.literal.one" not in legacy_fields
    assert "generated.s05.literal.two" not in legacy_fields
    validate_semantic_map(semantic_map, intermediate, _m200_snapshot)


def test_validation_module_carries_no_legacy_layout_dependency() -> None:
    """Structural guard: validation cannot read a legacy layout as an admission oracle."""
    module = ast.parse(inspect.getsource(_semantic_map_validation))
    attribute_names = {node.attr for node in ast.walk(module) if isinstance(node, ast.Attribute)}
    referenced_names = {node.id for node in ast.walk(module) if isinstance(node, ast.Name)}
    string_constants = {
        node.value for node in ast.walk(module) if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    imported_modules = {
        node.module for node in ast.walk(module) if isinstance(node, ast.ImportFrom) and node.module is not None
    }

    assert "export_layouts" not in attribute_names
    assert "resolve_export_layout" not in referenced_names
    assert "export_layouts" not in string_constants
    assert "cadrumo.domain.calculations.registry._export" not in imported_modules
