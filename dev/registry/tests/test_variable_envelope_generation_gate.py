"""Real-source gate for variable-envelope retention and generation refusal."""

from __future__ import annotations

from functools import partial
from pathlib import Path

import pytest

from cadrumo.core import M303ProductSoftwareEvidence, M303ProductSoftwareIdentity, Period
from cadrumo.core.resources import bundled_path
from cadrumo.domain.calculations.registry import (
    ExportEncoding,
    RegistryValidationError,
    bundled_authority,
    load_catalogue_file,
)

from .._export_tree import ExportTreeTransportProfile, render_complete_export_tree
from .._m303_variable_envelope import M303EnvelopeBodyRecordValues, M303EnvelopeGenerationInput
from .._record_design_ir import RecordDesignIntermediateRelativeSuffixMarker, load_record_design_intermediate
from .._render_profile import RenderProfile, RenderProfileDesignIdentity, RenderProfileSourceEvidence
from .._semantic_map import M303EnvelopePrefixRole, SemanticMap
from .._semantic_map_join import join_record_design_semantics

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_M303_GENERATION_EPOCHS = (
    ("aeat-dr-303-2023", 2023, "2023", "4T"),
    ("aeat-dr-303-2024-early", 2024, "2024-early", "2T"),
    ("aeat-dr-303-2024-late", 2024, "2024-late", "3T"),
    ("aeat-dr-303-2025", 2025, "2025", "4T"),
    ("aeat-dr-303-2026", 2026, "2026", "4T"),
)


def test_real_m200_variable_envelope_survives_join_and_refuses_fixed_generation(tmp_path: Path) -> None:
    """The parsed DP200000 composition cannot disappear before rendering."""
    source_root = bundled_path()
    catalogues = load_catalogue_file(bundled_path("registry", "aeat", "legal", "is.toml"))
    snapshot = bundled_authority().snapshot("200", filing_year=2025, period="0A")
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

    joined = join_record_design_semantics(semantic_map, focused, snapshot)
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
    snapshot = bundled_authority().snapshot("220", filing_year=2025, period="0A")
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

    joined = join_record_design_semantics(semantic_map, focused, snapshot)
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


@pytest.mark.parametrize(("source_ref", "filing_year", "design_epoch", "period"), _M303_GENERATION_EPOCHS)
def test_real_m303_envelope_with_explicit_product_authority_reaches_generation(
    tmp_path: Path,
    source_ref: str,
    filing_year: int,
    design_epoch: str,
    period: str,
) -> None:
    """Every selected epoch renders only with its exact snapshot filing period."""
    source_root = bundled_path()
    catalogues = load_catalogue_file(bundled_path("registry", "aeat", "legal", "iva.toml"))
    snapshot = bundled_authority().snapshot("303", filing_year=filing_year, period=period)
    parsed = load_record_design_intermediate(
        source_root,
        catalogues.sources,
        source_ref=source_ref,
        filing_year=filing_year,
        design_epoch=design_epoch,
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
    envelope = parsed.variable_envelopes[0]
    closing = envelope.closing
    assert isinstance(closing, RecordDesignIntermediateRelativeSuffixMarker)
    semantic_map = SemanticMap.model_validate(
        {
            "modelo": "303",
            "design_epoch": design_epoch,
            "source_ref": parsed.source.source_ref,
            "source_sha256": parsed.source.source_sha256,
            "records": (
                {
                    "sheet": real_sheet.sheet,
                    "record_identity": real_sheet.record_identity,
                    "export_record_id": "m303-body-1",
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
                    "export_field_id": "m303-envelope-gate-field",
                    "kind": "filler",
                    "legal_refs": ("ley-12-2002:art-29",),
                    "source_refs": (source_ref,),
                },
            ),
            "variable_envelopes": (
                {
                    "source_ref": parsed.source.source_ref,
                    "source_sha256": parsed.source.source_sha256,
                    "record_identity": "DP30300",
                    "prefix_fields": tuple(
                        {
                            "role": role,
                            "anchor": {
                                "sheet": field.sheet,
                                "source_row": field.source_row,
                                "source_cell": field.source_cell,
                                "ordinal": field.ordinal,
                                "record_identity": field.record_identity,
                            },
                        }
                        for role, field in zip(M303EnvelopePrefixRole, envelope.prefix_fields, strict=True)
                    ),
                    "body_anchor": {
                        "sheet": envelope.sheet,
                        "source_row": envelope.body_source_row,
                        "source_cell": envelope.body_source_cell,
                        "ordinal": envelope.body_ordinal,
                        "record_identity": envelope.record_identity,
                    },
                    "body_record_ids": ("m303-body-1",),
                    "closer_anchor": {
                        "sheet": envelope.sheet,
                        "source_row": closing.source_row,
                        "source_cell": closing.source_cell,
                        "ordinal": closing.ordinal,
                        "record_identity": envelope.record_identity,
                    },
                    "total_anchor": {
                        "source_row": envelope.total_source_row,
                        "source_cell": envelope.total_source_cell,
                        "label": envelope.total_label,
                        "length": envelope.total_length,
                    },
                },
            ),
        },
    )
    joined = join_record_design_semantics(semantic_map, focused, snapshot)
    render_tree = partial(
        render_complete_export_tree,
        revision_id=snapshot.revision.id,
        joined=joined,
        semantic_map=semantic_map,
        transport_profile=ExportTreeTransportProfile(
            modelo="303",
            design_epoch=design_epoch,
            source_ref=source_ref,
            source_sha256=parsed.source.source_sha256,
            layout_id="m303-envelope-gate",
            format="fixed_width",
            encoding=ExportEncoding.LATIN_1,
            line_ending="crlf",
            serializer_convention="rtoml-pretty-v1",
        ),
        render_profile=RenderProfile(
            schema_version=1,
            design_identity=RenderProfileDesignIdentity(
                modelo="303",
                design_epoch=design_epoch,
                source_ref=source_ref,
                source_sha256=parsed.source.source_sha256,
            ),
            fragment_ids=(),
            width_17_rules=(),
            singleton_rules=(),
        ),
        render_profile_source_evidence=RenderProfileSourceEvidence(
            design_identity=RenderProfileDesignIdentity(
                modelo="303",
                design_epoch=design_epoch,
                source_ref=source_ref,
                source_sha256=parsed.source.source_sha256,
            ),
            entries=(),
        ),
        product_software_identity=M303ProductSoftwareIdentity(
            program_identifier="C303",
            developer_tax_id="Y0000001S",
            evidence=(
                M303ProductSoftwareEvidence(
                    reference="aeat-software-registration:c303",
                    digest="a" * 64,
                ),
            ),
        ),
    )
    target = tmp_path / "export"
    if source_ref == "aeat-dr-303-2026":
        mismatched_target = tmp_path / "mismatched-period" / "export"
        with pytest.raises(RegistryValidationError, match="does not match the exact selected snapshot period"):
            render_tree(
                mismatched_target,
                m303_envelope_input=M303EnvelopeGenerationInput(
                    filing_period=Period.from_year_and_code(2023, "4T"),
                    body_records=(M303EnvelopeBodyRecordValues(record_id="m303-body-1"),),
                ),
            )
        assert not mismatched_target.exists()
    rendered = render_tree(
        target,
        m303_envelope_input=M303EnvelopeGenerationInput(
            filing_period=Period.from_year_and_code(filing_year, period),
            body_records=(M303EnvelopeBodyRecordValues(record_id="m303-body-1"),),
        ),
    )

    assert target.is_dir()
    assert rendered.m303_variable_envelope is not None
    assert rendered.m303_variable_envelope.prefix[92:96] == b"C303"
    assert rendered.m303_variable_envelope.prefix[100:109] == b"Y0000001S"
    assert rendered.m303_variable_envelope.body_members[0].payload == b" " * real_field.length + b"\r\n"
    assert rendered.m303_variable_envelope.closer == f"</T3030{filing_year:04d}{period}0000>".encode("ascii")
    assert rendered.m303_variable_envelope.total_length == len(rendered.m303_variable_envelope.payload)
    assert rendered.provenance_manifest.m303_variable_envelope is not None
    assert rendered.provenance_manifest.m303_variable_envelope.product_software_identity.program_identifier == "C303"
    assert rendered.provenance_manifest.m303_variable_envelope.revision_id == snapshot.revision.id
    assert rendered.provenance_manifest.m303_variable_envelope.filing_period == snapshot.filing_period
