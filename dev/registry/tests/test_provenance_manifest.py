"""Real-contract tests for export-fragment provenance and semantic digests."""

from __future__ import annotations

import ast
import inspect

import pytest
from pydantic import ValidationError

from cadrumo.core.hashing import canonical_json_bytes
from cadrumo.domain.calculations.registry import ExportLayoutDefinition, RegistryValidationError

from .. import _provenance_manifest
from .._provenance_manifest import (
    EXPORT_FRAGMENT_GENERATOR_SCHEMA_VERSION,
    EXPORT_FRAGMENT_PROVENANCE_SCHEMA_VERSION,
    ExportFragmentOutputDigest,
    ExportFragmentProvenanceManifest,
    ExportFragmentTarget,
    build_export_fragment_provenance_manifest,
    export_fragment_provenance_manifest_json_bytes,
    load_export_fragment_provenance_manifest,
    loader_semantic_digest,
)
from .._record_design_ir import RecordDesignIntermediate, RecordDesignWorkbookFormat
from .._semantic_map import SemanticMap

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _intermediate() -> RecordDesignIntermediate:
    return RecordDesignIntermediate.model_validate(
        {
            "source": {
                "source_ref": "aeat-dr-200-2025",
                "source_sha256": "a" * 64,
                "workbook_format": RecordDesignWorkbookFormat.XLSX,
                "design_epoch": "2025",
            },
            "sheets": (
                {
                    "sheet": "Registro tipo 1",
                    "record_identity": "registro-tipo-1",
                    "declared_total": 1,
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
                            "normalized_description": "Literal de prueba",
                        },
                    ),
                },
            ),
        },
    )


def _semantic_map() -> SemanticMap:
    return SemanticMap.model_validate(
        {
            "modelo": "200",
            "design_epoch": "2025",
            "entries": (
                {
                    "anchor": {
                        "sheet": "Registro tipo 1",
                        "source_row": 14,
                        "source_cell": "A14",
                        "ordinal": 1,
                        "record_identity": "registro-tipo-1",
                    },
                    "export_field_id": "registro-tipo-1.literal",
                    "kind": "literal",
                    "literal": "T",
                    "legal_refs": ("ley-27-2014:art-40",),
                    "source_refs": ("aeat-dr-200-2025",),
                },
            ),
        },
    )


def _loaded_layout(*, records_reversed: bool = False, first_offset: int = 1) -> ExportLayoutDefinition:
    records = (
        {
            "id": "registro-tipo-1",
            "record_type": "1",
            "order": 1,
            "encoding": "latin-1",
            "line_ending": "crlf",
            "fields": (
                {
                    "id": "registro-tipo-1.literal",
                    "offset": first_offset,
                    "length": 1,
                    "kind": "literal",
                    "literal": "T",
                    "data_type": "text",
                    "required": True,
                    "padding": "none",
                    "justification": "none",
                    "signed": False,
                    "legal_refs": ("ley-27-2014:art-40",),
                    "source_refs": ("aeat-dr-200-2025",),
                },
            ),
        },
        {
            "id": "registro-tipo-2",
            "record_type": "2",
            "order": 2,
            "encoding": "latin-1",
            "line_ending": "crlf",
            "fields": (
                {
                    "id": "registro-tipo-2.literal",
                    "offset": 1,
                    "length": 1,
                    "kind": "literal",
                    "literal": "0",
                    "data_type": "text",
                    "required": True,
                    "padding": "none",
                    "justification": "none",
                    "signed": False,
                    "legal_refs": ("ley-27-2014:art-40",),
                    "source_refs": ("aeat-dr-200-2025",),
                },
            ),
        },
    )
    return ExportLayoutDefinition.model_validate(
        {
            "id": "generated-modelo-200-fichero",
            "format": "fixed_width",
            "legal_refs": ("ley-27-2014:art-40",),
            "source_refs": ("aeat-dr-200-2025",),
            "records": tuple(reversed(records)) if records_reversed else records,
        },
    )


def _manifest() -> ExportFragmentProvenanceManifest:
    return ExportFragmentProvenanceManifest(
        manifest_schema_version=EXPORT_FRAGMENT_PROVENANCE_SCHEMA_VERSION,
        source_ref="aeat-dr-200-2025",
        source_sha256="a" * 64,
        parser_schema_version=1,
        generator_schema_version=EXPORT_FRAGMENT_GENERATOR_SCHEMA_VERSION,
        semantic_map_sha256="b" * 64,
        modelo="200",
        revision_id="2025-y-siguientes",
        design_epoch="2025",
        loader_semantic_sha256="c" * 64,
        output_files=(ExportFragmentOutputDigest(relative_path="records/0002.toml", sha256="d" * 64),),
    )


def test_manifest_records_real_output_files_and_roundtrips_canonical_bytes(tmp_path) -> None:
    """Manifest hashes supplied output bytes but neither renders nor publishes them."""
    export_root = tmp_path / "export"
    (export_root / "records").mkdir(parents=True)
    first = export_root / "records" / "0001.toml"
    second = export_root / "records" / "0002.toml"
    first.write_bytes(b"id = 'first'\n")
    second.write_bytes(b"id = 'second'\n")

    manifest = build_export_fragment_provenance_manifest(
        intermediate=_intermediate(),
        semantic_map=_semantic_map(),
        target=ExportFragmentTarget(modelo="200", revision_id="2025-y-siguientes", design_epoch="2025"),
        loaded_layout=_loaded_layout(),
        export_root=export_root,
    )
    serialised = export_fragment_provenance_manifest_json_bytes(manifest)

    assert manifest.source_ref == "aeat-dr-200-2025"
    assert manifest.source_sha256 == "a" * 64
    assert manifest.modelo == "200"
    assert manifest.revision_id == "2025-y-siguientes"
    assert tuple(item.relative_path for item in manifest.output_files) == (
        "records/0001.toml",
        "records/0002.toml",
    )
    assert load_export_fragment_provenance_manifest(serialised) == manifest


def test_loader_semantic_digest_normalises_loader_order_but_detects_coordinate_change() -> None:
    """Fragment order is non-semantic, while a loader-visible offset is digest-visible."""
    baseline = loader_semantic_digest(_loaded_layout())

    assert loader_semantic_digest(_loaded_layout(records_reversed=True)) == baseline
    assert loader_semantic_digest(_loaded_layout(first_offset=2)) != baseline


def test_manifest_refuses_legacy_shapes_schema_drift_duplicate_outputs_and_unsafe_paths() -> None:
    """Old/incomplete shapes cannot parse as current provenance evidence."""
    manifest = _manifest()
    raw = export_fragment_provenance_manifest_json_bytes(manifest)

    with pytest.raises(RegistryValidationError, match="not canonical JSON"):
        load_export_fragment_provenance_manifest(raw + b"\n")
    with pytest.raises(ValidationError, match="must not contain empty, current, or parent segments"):
        ExportFragmentOutputDigest(relative_path="../outside.toml", sha256="d" * 64)
    with pytest.raises(ValidationError, match="must not contain duplicate relative paths"):
        ExportFragmentProvenanceManifest(
            **(manifest.model_dump() | {"output_files": manifest.output_files + manifest.output_files}),
        )
    with pytest.raises(ValidationError, match="parser schema drift"):
        ExportFragmentProvenanceManifest(**(manifest.model_dump() | {"parser_schema_version": 2}))
    with pytest.raises(RegistryValidationError, match="duplicate object key"):
        load_export_fragment_provenance_manifest(
            canonical_json_bytes(manifest.model_dump(mode="json"))[:-1] + b',"modelo":"200"}',
        )


def test_provenance_contract_has_no_legacy_layout_lookup_or_fallback_surface() -> None:
    """A manifest must only attest supplied generated output, never consult old layouts."""
    module = ast.parse(inspect.getsource(_provenance_manifest))
    referenced_names = {node.id for node in ast.walk(module) if isinstance(node, ast.Name)}
    imported_modules = {
        node.module for node in ast.walk(module) if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    string_constants = {
        node.value for node in ast.walk(module) if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }

    assert "resolve_export_layout" not in referenced_names
    assert "bundled_authority" not in referenced_names
    assert "cadrumo.domain.calculations.registry._export" not in imported_modules
    assert "src/cadrumo/_data/registry" not in string_constants
