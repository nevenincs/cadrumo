"""Real-contract tests for export-fragment provenance and semantic digests."""

from __future__ import annotations

import ast
import inspect

import pytest
from pydantic import ValidationError

from cadrumo.core.casilla_id import validated_casilla_id
from cadrumo.core.filing_projection_ref import (
    M303ProrrataActivityProjectionField,
    M303ProrrataActivityProjectionRef,
)
from cadrumo.core.hashing import canonical_json_bytes
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.fixed_width_codec import ExportEncoding
from cadrumo.domain.calculations.registry.export_value_policy import ExportValuePolicy
from cadrumo.domain.calculations.registry.schema_exports import ExportFieldDefinition, ExportLayoutDefinition

from ..pipeline import _provenance_manifest
from ..pipeline._provenance_manifest import (
    EXPORT_FRAGMENT_GENERATOR_SCHEMA_VERSION,
    EXPORT_FRAGMENT_PROVENANCE_SCHEMA_VERSION,
    EXPORT_RENDER_NORMALIZATION_SCHEMA_VERSION,
    ExportFieldDerivation,
    ExportFragmentOutputDigest,
    ExportFragmentProvenanceManifest,
    ExportFragmentTarget,
    build_export_fragment_provenance_manifest,
    export_fragment_provenance_manifest_json_bytes,
    load_export_fragment_provenance_manifest,
    loader_semantic_digest,
    semantic_map_digest,
)
from ..pipeline._record_design_ir import (
    RECORD_DESIGN_INTERMEDIATE_SCHEMA_VERSION,
    RecordDesignIntermediate,
    RecordDesignWorkbookFormat,
)
from ..pipeline._render_profile import (
    RENDER_PROFILE_SCHEMA_VERSION,
    RenderProfile,
    RenderProfileDesignIdentity,
    RenderProfileSourceEvidence,
    render_profile_digest,
)
from ..pipeline._semantic_map import SemanticMap
from ..pipeline._semantic_map_join import JoinedRecordDesign, JoinedRecordDesignField, JoinedRecordDesignRecord

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
                            "ordinal": "1",
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
            "source_ref": "aeat-dr-200-2025",
            "source_sha256": "a" * 64,
            "records": (
                {
                    "sheet": "Registro tipo 1",
                    "record_identity": "registro-tipo-1",
                    "export_record_id": "registro-tipo-1",
                    "record_type": "declaracion",
                },
            ),
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


def _projection_ref(
    field: M303ProrrataActivityProjectionField = M303ProrrataActivityProjectionField.CNAE,
) -> M303ProrrataActivityProjectionRef:
    return M303ProrrataActivityProjectionRef(
        projection_kind="m303_prorrata_activity",
        slot=1,
        field=field,
        casilla_id=validated_casilla_id("500", surface="test"),
    )


def _projection_semantic_map(reference: M303ProrrataActivityProjectionRef) -> SemanticMap:
    return SemanticMap.model_validate(
        {
            "modelo": "200",
            "design_epoch": "2025",
            "source_ref": "aeat-dr-200-2025",
            "source_sha256": "a" * 64,
            "records": (
                {
                    "sheet": "Registro tipo 1",
                    "record_identity": "registro-tipo-1",
                    "export_record_id": "registro-tipo-1",
                    "record_type": "declaracion",
                },
            ),
            "entries": (
                {
                    "anchor": {
                        "sheet": "Registro tipo 1",
                        "source_row": 14,
                        "source_cell": "A14",
                        "ordinal": 1,
                        "record_identity": "registro-tipo-1",
                    },
                    "export_field_id": "registro-tipo-1.prorrata-cnae",
                    "kind": "projection",
                    "projection_ref": reference,
                    "legal_refs": ("ley-27-2014:art-40",),
                    "source_refs": ("aeat-dr-200-2025",),
                },
            ),
        },
    )


def _projection_field(reference: M303ProrrataActivityProjectionRef) -> ExportFieldDefinition:
    return ExportFieldDefinition.model_validate(
        {
            "id": "registro-tipo-1.prorrata-cnae",
            "offset": 1,
            "length": 1,
            "kind": "projection",
            "projection_ref": reference,
            "data_type": "text",
            "required": True,
            "padding": "none",
            "justification": "none",
            "signed": False,
            "legal_refs": ("ley-27-2014:art-40",),
            "source_refs": ("aeat-dr-200-2025",),
        },
    )


def _loaded_layout(*, records_reversed: bool = False, first_offset: int = 1) -> ExportLayoutDefinition:
    records = (
        {
            "id": "registro-tipo-1",
            "record_type": "1",
            "order": 1,
            "encoding": ExportEncoding.ISO_8859_1,
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
            "encoding": ExportEncoding.ISO_8859_1,
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


def _joined() -> JoinedRecordDesign:
    intermediate = _intermediate()
    semantic_map = _semantic_map()
    joined_field = JoinedRecordDesignField(
        parser_field=intermediate.sheets[0].fields[0],
        semantic_entry=semantic_map.entries[0],
    )
    return JoinedRecordDesign(
        modelo=semantic_map.modelo,
        source=intermediate.source,
        records=(
            JoinedRecordDesignRecord(
                parser_sheet=intermediate.sheets[0],
                semantic_record=semantic_map.records[0],
                fields=(joined_field,),
            ),
        ),
        fields=(joined_field,),
    )


def _field_derivation() -> ExportFieldDerivation:
    intermediate = _intermediate()
    semantic_map = _semantic_map()
    return ExportFieldDerivation(
        export_record_id="registro-tipo-1",
        parser_field=intermediate.sheets[0].fields[0],
        semantic_entry=semantic_map.entries[0],
        field=ExportFieldDefinition.model_validate(
            {
                "id": "registro-tipo-1.literal",
                "offset": 1,
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
        normalization_schema_version=EXPORT_RENDER_NORMALIZATION_SCHEMA_VERSION,
        derivation_code="literal-exact-v1",
    )


def _render_profile() -> RenderProfile:
    return RenderProfile(
        schema_version=1,
        design_identity=RenderProfileDesignIdentity(
            modelo="200",
            design_epoch="2025",
            source_ref="aeat-dr-200-2025",
            source_sha256="a" * 64,
        ),
        fragment_ids=(),
        width_17_rules=(),
        singleton_rules=(),
    )


def _render_profile_evidence() -> RenderProfileSourceEvidence:
    return RenderProfileSourceEvidence(
        design_identity=_render_profile().design_identity,
        entries=(),
    )


def _one_field_layout() -> ExportLayoutDefinition:
    return ExportLayoutDefinition.model_validate(
        {
            "id": "generated-modelo-200-fichero",
            "format": "fixed_width",
            "legal_refs": ("ley-27-2014:art-40",),
            "source_refs": ("aeat-dr-200-2025",),
            "records": (
                {
                    "id": "registro-tipo-1",
                    "record_type": "1",
                    "order": 1,
                    "encoding": ExportEncoding.ISO_8859_1,
                    "line_ending": "crlf",
                    "fields": (_field_derivation().field,),
                },
            ),
        },
    )


def _manifest() -> ExportFragmentProvenanceManifest:
    render_profile = _render_profile()
    source_evidence = _render_profile_evidence()
    return ExportFragmentProvenanceManifest(
        manifest_schema_version=EXPORT_FRAGMENT_PROVENANCE_SCHEMA_VERSION,
        source_ref="aeat-dr-200-2025",
        source_sha256="a" * 64,
        parser_schema_version=RECORD_DESIGN_INTERMEDIATE_SCHEMA_VERSION,
        generator_schema_version=EXPORT_FRAGMENT_GENERATOR_SCHEMA_VERSION,
        semantic_map_sha256="b" * 64,
        render_profile_schema_version=RENDER_PROFILE_SCHEMA_VERSION,
        render_profile_sha256=render_profile_digest(render_profile, source_evidence),
        modelo="200",
        revision_id="2025-y-siguientes",
        design_epoch="2025",
        loader_semantic_sha256="c" * 64,
        output_files=(ExportFragmentOutputDigest(relative_path="records/0002.toml", sha256="d" * 64),),
        field_derivations=(_field_derivation(),),
    )


def test_manifest_records_real_output_files_and_roundtrips_canonical_bytes(tmp_path) -> None:
    """Manifest binds supplied generated bytes and every rendered-field derivation."""
    export_root = tmp_path / "export"
    (export_root / "records").mkdir(parents=True)
    first = export_root / "records" / "0001.toml"
    second = export_root / "records" / "0002.toml"
    first.write_bytes(b"id = 'first'\n")
    second.write_bytes(b"id = 'second'\n")

    manifest = build_export_fragment_provenance_manifest(
        joined=_joined(),
        semantic_map=_semantic_map(),
        target=ExportFragmentTarget(modelo="200", revision_id="2025-y-siguientes", design_epoch="2025"),
        loaded_layout=_one_field_layout(),
        export_root=export_root,
        field_derivations=(_field_derivation(),),
        render_profile=_render_profile(),
        render_profile_source_evidence=_render_profile_evidence(),
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
    assert manifest.field_derivations == (_field_derivation(),)
    assert load_export_fragment_provenance_manifest(serialised) == manifest


def test_loader_semantic_digest_normalises_loader_order_but_detects_coordinate_change() -> None:
    """Fragment order is non-semantic, while a loader-visible offset is digest-visible."""
    baseline = loader_semantic_digest(_loaded_layout())

    assert loader_semantic_digest(_loaded_layout(records_reversed=True)) == baseline
    assert loader_semantic_digest(_loaded_layout(first_offset=2)) != baseline


def test_loader_semantic_digest_detects_value_policy_change() -> None:
    """A runtime value transform is loader-visible meaning, never omitted metadata."""
    plain = ExportFieldDefinition.model_validate(
        {
            "id": "selected",
            "offset": 1,
            "length": 1,
            "kind": "casilla",
            "casilla_id": "01",
            "data_type": "integer",
            "required": False,
            "padding": "left_zero",
            "justification": "right",
            "signed": False,
            "legal_refs": ("ley-27-2014:art-40",),
            "source_refs": ("aeat-dr-200-2025",),
        },
    )
    selected = plain.model_copy(update={"value_policy": ExportValuePolicy.SELECTED_1_UNSELECTED_0})
    plain_layout = _one_field_layout().model_copy(
        update={"records": (_one_field_layout().records[0].model_copy(update={"fields": (plain,)}),)},
    )
    selected_layout = plain_layout.model_copy(
        update={"records": (plain_layout.records[0].model_copy(update={"fields": (selected,)}),)},
    )

    assert loader_semantic_digest(selected_layout) != loader_semantic_digest(plain_layout)


def test_loader_semantic_digest_keeps_day_first_date_policy_and_format_distinct() -> None:
    """A DDMMAAAA field retains both its policy and its exact wire ordering in provenance."""
    day_first = ExportFieldDefinition.model_validate(
        {
            "id": "power-date",
            "offset": 1,
            "length": 8,
            "kind": "casilla",
            "casilla_id": "01",
            "data_type": "date",
            "required": False,
            "padding": "none",
            "justification": "none",
            "date_format": "ddmmaaaa",
            "signed": False,
            "value_policy": ExportValuePolicy.DDMMYYYY,
            "legal_refs": ("ley-27-2014:art-40",),
            "source_refs": ("aeat-dr-200-2025",),
        },
    )
    year_first = day_first.model_copy(
        update={
            "date_format": "aaaammdd",
            "value_policy": ExportValuePolicy.YYYYMMDD,
        },
    )
    day_first_layout = _one_field_layout().model_copy(
        update={"records": (_one_field_layout().records[0].model_copy(update={"fields": (day_first,)}),)},
    )
    year_first_layout = day_first_layout.model_copy(
        update={"records": (day_first_layout.records[0].model_copy(update={"fields": (year_first,)}),)},
    )

    assert loader_semantic_digest(day_first_layout) != loader_semantic_digest(year_first_layout)


def test_loader_semantic_digest_detects_allowed_values_change() -> None:
    """The exact reviewed enumeration domain is loader-visible meaning."""
    constrained = ExportFieldDefinition.model_validate(
        {
            "id": "enumerated",
            "offset": 1,
            "length": 1,
            "kind": "casilla",
            "casilla_id": "01",
            "data_type": "integer",
            "required": False,
            "padding": "left_zero",
            "justification": "right",
            "signed": False,
            "value_policy": ExportValuePolicy.ENUMERATED_DIGITS,
            "allowed_values": ("3", "1"),
            "legal_refs": ("ley-27-2014:art-40",),
            "source_refs": ("aeat-dr-200-2025",),
        },
    )
    reordered = ExportFieldDefinition.model_validate(
        constrained.model_dump(mode="python") | {"allowed_values": ("1", "3")},
    )
    changed = ExportFieldDefinition.model_validate(
        constrained.model_dump(mode="python") | {"allowed_values": ("1", "4")},
    )
    base_layout = _one_field_layout()
    constrained_layout = base_layout.model_copy(
        update={
            "records": (base_layout.records[0].model_copy(update={"fields": (constrained,)}),),
        },
    )
    reordered_layout = base_layout.model_copy(
        update={"records": (base_layout.records[0].model_copy(update={"fields": (reordered,)}),)},
    )
    changed_layout = base_layout.model_copy(
        update={"records": (base_layout.records[0].model_copy(update={"fields": (changed,)}),)},
    )

    assert loader_semantic_digest(constrained_layout) == loader_semantic_digest(reordered_layout)
    assert loader_semantic_digest(constrained_layout) != loader_semantic_digest(changed_layout)


def test_provenance_digests_and_derivation_equality_include_the_typed_projection_ref() -> None:
    """A changed repeated-row owner cannot retain semantic or loader provenance."""
    initial_ref = _projection_ref()
    changed_ref = _projection_ref(M303ProrrataActivityProjectionField.OPERACIONES_TOTAL)
    initial_map = _projection_semantic_map(initial_ref)
    changed_map = _projection_semantic_map(changed_ref)
    initial_field = _projection_field(initial_ref)
    changed_field = _projection_field(changed_ref)
    base_layout = _one_field_layout()
    initial_layout = base_layout.model_copy(
        update={"records": (base_layout.records[0].model_copy(update={"fields": (initial_field,)}),)},
    )
    changed_layout = base_layout.model_copy(
        update={"records": (base_layout.records[0].model_copy(update={"fields": (changed_field,)}),)},
    )

    assert semantic_map_digest(initial_map) != semantic_map_digest(changed_map)
    assert semantic_map_digest(initial_map) != semantic_map_digest(
        initial_map.model_copy(update={"source_sha256": "b" * 64}),
    )
    assert loader_semantic_digest(initial_layout) != loader_semantic_digest(changed_layout)

    with pytest.raises(ValidationError, match="emitted projection_ref does not match semantic-map entry"):
        ExportFieldDerivation(
            export_record_id="registro-tipo-1",
            parser_field=_intermediate().sheets[0].fields[0],
            semantic_entry=initial_map.entries[0],
            field=changed_field,
            normalization_schema_version=EXPORT_RENDER_NORMALIZATION_SCHEMA_VERSION,
            derivation_code="text-an-v1",
        )


def test_manifest_refuses_legacy_shapes_schema_drift_duplicate_outputs_and_unsafe_paths() -> None:
    """Old/incomplete shapes cannot parse as current provenance evidence."""
    manifest = _manifest()
    raw = export_fragment_provenance_manifest_json_bytes(manifest)

    with pytest.raises(RegistryValidationError, match="not canonical JSON"):
        load_export_fragment_provenance_manifest(raw + b"\n")
    with pytest.raises(ValidationError, match="must not contain empty, current, or parent segments"):
        ExportFragmentOutputDigest(relative_path="../outside.toml", sha256="d" * 64)
    with pytest.raises(ValidationError, match="must refer to a generated TOML file"):
        ExportFragmentOutputDigest(relative_path="export.provenance.json", sha256="d" * 64)
    with pytest.raises(ValidationError, match="must not contain duplicate relative paths"):
        ExportFragmentProvenanceManifest(
            **(manifest.model_dump() | {"output_files": manifest.output_files + manifest.output_files}),
        )
    for obsolete_parser_schema_version in (1, 2):
        with pytest.raises(ValidationError, match="parser schema drift"):
            ExportFragmentProvenanceManifest(
                **(manifest.model_dump() | {"parser_schema_version": obsolete_parser_schema_version}),
            )
    without_render_profile = manifest.model_dump()
    without_render_profile.pop("render_profile_schema_version")
    without_render_profile.pop("render_profile_sha256")
    with pytest.raises(ValidationError, match="render_profile"):
        ExportFragmentProvenanceManifest.model_validate(without_render_profile)
    with pytest.raises(RegistryValidationError, match="duplicate object key"):
        load_export_fragment_provenance_manifest(
            canonical_json_bytes(manifest.model_dump(mode="json"))[:-1] + b',"modelo":"200"}',
        )
    with pytest.raises(RegistryValidationError, match="current contract"):
        load_export_fragment_provenance_manifest(
            canonical_json_bytes(manifest.model_dump(mode="json") | {"timestamp": "2026-08-10T00:00:00Z"}),
        )
    with pytest.raises(ValidationError):
        ExportFieldDerivation.model_validate(_field_derivation().model_dump() | {"derivation_code": "default"})


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
    assert "load_record_design_intermediate" not in referenced_names
    assert "extract_record_design" not in referenced_names
    assert "cadrumo.domain.calculations.registry.export" not in imported_modules
    assert "src/cadrumo/_data/registry" not in string_constants
    build_parameters = inspect.signature(build_export_fragment_provenance_manifest).parameters
    assert "intermediate" not in build_parameters
    assert build_parameters["semantic_map"].default is inspect.Signature.empty
    assert build_parameters["field_derivations"].default is inspect.Signature.empty
