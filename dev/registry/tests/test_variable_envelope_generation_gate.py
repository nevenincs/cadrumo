"""Real-source gate for variable-envelope retention and generation refusal."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from cadrumo.core.resources import bundled_path
from cadrumo.domain.calculations.registry import (
    ExportEncoding,
    RegistryValidationError,
    bundled_revision_inspection,
    load_catalogue_file,
)

from .._export_tree import ExportTreeTransportProfile, RenderedExportTree, render_complete_export_tree
from .._record_design_ir import load_record_design_intermediate
from .._render_profile import RenderProfile, RenderProfileDesignIdentity, RenderProfileSourceEvidence
from .._semantic_map import SemanticMap
from .._semantic_map_join import join_record_design_semantics

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_static_generator_exposes_no_filing_instance_channels() -> None:
    """The generator carries grammar only; application owns a filing instance."""
    assert {
        "product_software_identity",
        "m303_envelope_input",
        "filing_period",
        "casilla_values",
        "body_members",
        "payload",
        "payload_sha256",
        "total_length",
    }.isdisjoint(inspect.signature(render_complete_export_tree).parameters)
    assert "variable_envelope_contract" not in RenderedExportTree.model_fields


def test_real_m200_variable_envelope_survives_join_and_refuses_fixed_generation(tmp_path: Path) -> None:
    """The parsed DP200000 composition cannot disappear before rendering."""
    source_root = bundled_path()
    catalogues = load_catalogue_file(bundled_path("registry", "aeat", "legal", "is.toml"))
    inspection = bundled_revision_inspection("200", filing_year=2025, period="0A")
    parsed = load_record_design_intermediate(
        source_root,
        catalogues.sources,
        source_ref="aeat-dr-200-2025",
        filing_year=2025,
        design_epoch="2025",
    )
    real_sheet = parsed.sheets[0]
    real_field = real_sheet.fields[0]
    focused_sheet = real_sheet.model_copy(
        update={
            "declared_total": real_field.offset + real_field.length - 1,
            "fields": (real_field,),
        },
    )
    focused = parsed.model_copy(update={"sheets": (focused_sheet,)})
    semantic_map = SemanticMap.model_validate(
        {
            "modelo": "200",
            "design_epoch": "2025",
            "source_ref": parsed.source.source_ref,
            "source_sha256": parsed.source.source_sha256,
            "records": (
                {
                    "sheet": real_sheet.sheet,
                    "record_identity": real_sheet.record_identity,
                    "export_record_id": "m200-envelope-gate-record",
                    "record_type": "declaracion",
                },
            ),
            "entries": (
                {
                    "anchor": {
                        "sheet": real_field.sheet,
                        "source_row": real_field.source_row,
                        "source_cell": real_field.source_cell,
                        "ordinal": real_field.ordinal,
                        "record_identity": real_field.record_identity,
                    },
                    "export_field_id": "m200-envelope-gate-field",
                    "kind": "filler",
                    "legal_refs": ("ley-27-2014:art-40",),
                    "source_refs": ("aeat-dr-200-2025",),
                },
            ),
        },
    )

    joined = join_record_design_semantics(semantic_map, focused, inspection)
    target = tmp_path / "export"

    assert joined.variable_envelopes == parsed.variable_envelopes
    assert joined.variable_envelopes[0].record_identity == "DP200000"
    with pytest.raises(RegistryValidationError, match="refuses variable envelopes"):
        render_complete_export_tree(
            target,
            revision_id="2025-y-siguientes",
            joined=joined,
            semantic_map=semantic_map,
            transport_profile=ExportTreeTransportProfile(
                modelo="200",
                design_epoch="2025",
                source_ref="aeat-dr-200-2025",
                source_sha256=parsed.source.source_sha256,
                layout_id="m200-envelope-gate",
                format="fixed_width",
                encoding=ExportEncoding.LATIN_1,
                line_ending="crlf",
                serializer_convention="rtoml-pretty-v1",
            ),
            render_profile=RenderProfile(
                schema_version=1,
                design_identity=RenderProfileDesignIdentity(
                    modelo="200",
                    design_epoch="2025",
                    source_ref="aeat-dr-200-2025",
                    source_sha256="b" * 64,
                ),
                fragment_ids=(),
                width_17_rules=(),
                singleton_rules=(),
            ),
            render_profile_source_evidence=RenderProfileSourceEvidence(
                design_identity=RenderProfileDesignIdentity(
                    modelo="200",
                    design_epoch="2025",
                    source_ref="aeat-dr-200-2025",
                    source_sha256="b" * 64,
                ),
                entries=(),
            ),
        )

    assert not target.exists()


def test_real_m220_composite_envelope_survives_join_and_refuses_fixed_generation(tmp_path: Path) -> None:
    """The six typed closing rows cannot be truncated into a fixed M220 record."""
    source_root = bundled_path()
    catalogues = load_catalogue_file(bundled_path("registry", "aeat", "legal", "is.toml"))
    inspection = bundled_revision_inspection("220", filing_year=2025, period="0A")
    parsed = load_record_design_intermediate(
        source_root,
        catalogues.sources,
        source_ref="aeat-dr-220-2025",
        filing_year=2025,
        design_epoch="2025",
    )
    real_sheet = parsed.sheets[0]
    real_field = real_sheet.fields[0]
    focused = parsed.model_copy(
        update={
            "sheets": (
                real_sheet.model_copy(
                    update={
                        "declared_total": real_field.offset + real_field.length - 1,
                        "fields": (real_field,),
                    },
                ),
            ),
        },
    )
    semantic_map = SemanticMap.model_validate(
        {
            "modelo": "220",
            "design_epoch": "2025",
            "source_ref": parsed.source.source_ref,
            "source_sha256": parsed.source.source_sha256,
            "records": (
                {
                    "sheet": real_sheet.sheet,
                    "record_identity": real_sheet.record_identity,
                    "export_record_id": "m220-envelope-gate-record",
                    "record_type": "declaracion",
                },
            ),
            "entries": (
                {
                    "anchor": {
                        "sheet": real_field.sheet,
                        "source_row": real_field.source_row,
                        "source_cell": real_field.source_cell,
                        "ordinal": real_field.ordinal,
                        "record_identity": real_field.record_identity,
                    },
                    "export_field_id": "m220-envelope-gate-field",
                    "kind": "filler",
                    "legal_refs": ("ley-27-2014:art-124",),
                    "source_refs": ("aeat-dr-220-2025",),
                },
            ),
        },
    )

    joined = join_record_design_semantics(semantic_map, focused, inspection)
    target = tmp_path / "export"

    assert joined.variable_envelopes == parsed.variable_envelopes
    assert joined.variable_envelopes[0].record_identity == "T220000000"
    with pytest.raises(RegistryValidationError, match="refuses variable envelopes"):
        render_complete_export_tree(
            target,
            revision_id="2024-y-siguientes",
            joined=joined,
            semantic_map=semantic_map,
            transport_profile=ExportTreeTransportProfile(
                modelo="220",
                design_epoch="2025",
                source_ref="aeat-dr-220-2025",
                source_sha256=parsed.source.source_sha256,
                layout_id="m220-envelope-gate",
                format="fixed_width",
                encoding=ExportEncoding.LATIN_1,
                line_ending="crlf",
                serializer_convention="rtoml-pretty-v1",
            ),
            render_profile=RenderProfile(
                schema_version=1,
                design_identity=RenderProfileDesignIdentity(
                    modelo="220",
                    design_epoch="2025",
                    source_ref="aeat-dr-220-2025",
                    source_sha256=parsed.source.source_sha256,
                ),
                fragment_ids=(),
                width_17_rules=(),
                singleton_rules=(),
            ),
            render_profile_source_evidence=RenderProfileSourceEvidence(
                design_identity=RenderProfileDesignIdentity(
                    modelo="220",
                    design_epoch="2025",
                    source_ref="aeat-dr-220-2025",
                    source_sha256=parsed.source.source_sha256,
                ),
                entries=(),
            ),
        )

    assert not target.exists()
