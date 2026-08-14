"""Real-source closure proofs for the Modelo 303 2023 semantic-map corpus."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry import ExportComputedKey, ExportEncoding, bundled_revision_inspection

from .._export_tree import ExportTreeTransportProfile, _render_records, render_complete_export_tree
from .._provenance_manifest import semantic_map_digest
from .._record_design_ir import load_record_design_intermediate
from .._render_profile import (
    RenderProfileDesignIdentity,
    RenderProfileSourceEvidence,
    load_and_validate_render_profile,
    render_profile_digest,
)
from .._semantic_map_join import join_record_design_semantics
from .._semantic_map_loader import load_semantic_map
from ..m303_2023_semantic_census import (
    M303_2023_CLASS_TOTALS,
    M303_2023_REVIEW_HOME_TOTALS,
    M303_2023_SOURCE_REF,
    M303_2023_SOURCE_SHA256,
    M303_2023_TOTAL_ANCHOR_COUNT,
    census_m303_2023_semantic_map,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MAP_DIRECTORY = Path("dev/registry/mappings/modelo_303/2023")
_PROFILE_DIRECTORY = Path("dev/registry/render_profiles/modelo_303/2023")
_SEMANTIC_DIGEST = "01d7264cca47555943278500e42cba6c347511acef64ccdc43b722708c1406f6"
_PROFILE_DIGEST = "e59b3446a5f5dcfe6b2de3f0cf3befa6aaaeb6fb02a055433d584a099908de3b"


@pytest.fixture(scope="module")
def _authorities():
    inspection = bundled_revision_inspection("303", filing_year=2023, period="4T")
    intermediate = load_record_design_intermediate(
        inspection.source_root,
        inspection.sources,
        source_ref=M303_2023_SOURCE_REF,
        filing_year=2023,
        design_epoch="2023",
    )
    semantic_map = load_semantic_map(_MAP_DIRECTORY)
    joined = join_record_design_semantics(semantic_map, intermediate, inspection)
    profile = load_and_validate_render_profile(
        _PROFILE_DIRECTORY,
        joined,
        RenderProfileSourceEvidence(
            design_identity=RenderProfileDesignIdentity(
                modelo="303",
                design_epoch="2023",
                source_ref=M303_2023_SOURCE_REF,
                source_sha256=M303_2023_SOURCE_SHA256,
            ),
            entries=(),
        ),
    )
    return intermediate, semantic_map, inspection, joined, profile


def test_real_2023_source_inspection_map_and_profile_are_exhaustive(_authorities) -> None:
    intermediate, semantic_map, inspection, joined, profile = _authorities
    census = census_m303_2023_semantic_map(intermediate, semantic_map)

    assert intermediate.source.source_sha256 == M303_2023_SOURCE_SHA256
    assert inspection.revision_id == "2023"
    assert census.total_anchor_count == M303_2023_TOTAL_ANCHOR_COUNT
    assert census.class_totals == M303_2023_CLASS_TOTALS
    assert census.review_home_totals == M303_2023_REVIEW_HOME_TOTALS
    assert census.simplified_projection_anchor_count == 134
    assert sum(len(record.fields) for record in joined.records) == 393
    assert len(joined.variable_envelopes) == 1
    assert semantic_map_digest(semantic_map) == _SEMANTIC_DIGEST
    source_evidence = RenderProfileSourceEvidence(design_identity=profile.design_identity, entries=())
    assert len(profile.singleton_rules) == 3
    assert render_profile_digest(profile, source_evidence) == _PROFILE_DIGEST


def test_s63_membership_two_110_homes_and_marker_encodings_are_exact(_authorities) -> None:
    _, semantic_map, _, _, _ = _authorities
    by_anchor = {(entry.anchor.record_identity, entry.anchor.ordinal): entry for entry in semantic_map.entries}
    simplified = {
        (entry.anchor.record_identity, entry.anchor.ordinal)
        for entry in semantic_map.entries
        if entry.projection_ref is not None
        and str(entry.projection_ref.projection_kind).startswith("m303_regimen_simplificado")
    }

    assert simplified == {("DP30302", ordinal) for ordinal in (*range(6, 78), *range(90, 152))}
    assert by_anchor[("DP30303", 20)].casilla_id == "iva.compensacion-pendiente-periodos-anteriores"
    assert by_anchor[("DP30303", 22)].casilla_id == "iva.compensacion-pendiente-periodos-posteriores"
    assert by_anchor[("DP30301", 5)].literal == ""
    assert by_anchor[("DP30301", 5)].computed_key is None
    assert by_anchor[("DP30304", 5)].literal == ""
    assert by_anchor[("DP30304", 5)].computed_key is None
    assert by_anchor[("DP30302", 5)].computed_key is ExportComputedKey.M303_COMPLEMENTARIA_PAGE_MARKER
    assert by_anchor[("DP30305", 5)].computed_key is ExportComputedKey.M303_COMPLEMENTARIA_PAGE_MARKER
    assert by_anchor[("DP30303", 29)].computed_key is ExportComputedKey.M303_COMPLEMENTARIA_MARKER
    assert by_anchor[("DP30303", 28)].computed_key is ExportComputedKey.M303_NO_ACTIVITY_MARKER


def test_real_static_compiler_normalizes_the_complete_2023_map(_authorities) -> None:
    """The static compiler resolves every sourced field without filing-instance inputs."""
    _, _, _, joined, profile = _authorities
    transport = ExportTreeTransportProfile(
        modelo="303",
        design_epoch="2023",
        source_ref=M303_2023_SOURCE_REF,
        source_sha256=M303_2023_SOURCE_SHA256,
        layout_id="generated-modelo-303-2023-fichero",
        format="fixed_width",
        encoding=ExportEncoding.LATIN_1,
        line_ending="crlf",
        serializer_convention="rtoml-pretty-v1",
    )
    records, derivations = _render_records(joined.records, transport, profile)

    assert tuple(record.id for record in records) == (
        "m303-declaration",
        "m303-regimen-simplificado",
        "m303-resultados",
        "m303-exonerado-390",
        "m303-prorrata-deducciones",
        "m303-domiciliacion",
    )
    blank_page_markers = {
        str(derivation.field.id): derivation.field
        for derivation in derivations
        if str(derivation.field.id) in {"m303-2023.dp30301.f005", "m303-2023.dp30304.f005"}
    }
    assert set(blank_page_markers) == {"m303-2023.dp30301.f005", "m303-2023.dp30304.f005"}
    assert all(
        field.literal == "" and field.length == 1 and field.padding.value == "none"
        for field in blank_page_markers.values()
    )
    by_field_id = {str(derivation.field.id): derivation.field for derivation in derivations}
    assert by_field_id["m303-2023.dp30301.f006"].kind.value == "header"
    assert by_field_id["m303-2023.dp30301.f006"].producer_key.value == "filing.result_disposition"
    assert by_field_id["m303-2023.dp30301.f050"].allowed_values == ("0", "50", "62")


def test_real_2023_static_declaration_preserves_dp30300_without_instance_values(
    _authorities,
    tmp_path: Path,
) -> None:
    """The complete reviewed 2023 map compiles DP30300 without period or payload inputs."""
    _, semantic_map, inspection, joined, profile = _authorities
    transport = ExportTreeTransportProfile(
        modelo="303",
        design_epoch="2023",
        source_ref=M303_2023_SOURCE_REF,
        source_sha256=M303_2023_SOURCE_SHA256,
        layout_id="generated-modelo-303-2023-fichero",
        format="fixed_width",
        encoding=ExportEncoding.LATIN_1,
        line_ending="crlf",
        serializer_convention="rtoml-pretty-v1",
    )
    rendered = render_complete_export_tree(
        tmp_path / "export",
        revision_id=inspection.revision_id,
        joined=joined,
        semantic_map=semantic_map,
        transport_profile=transport,
        render_profile=profile,
        render_profile_source_evidence=RenderProfileSourceEvidence(
            design_identity=profile.design_identity,
            entries=(),
        ),
    )
    declaration = rendered.layout.m303_filing_envelope
    assert declaration is not None

    assert declaration.source_ref == M303_2023_SOURCE_REF
    assert declaration.source_sha256 == M303_2023_SOURCE_SHA256
    assert declaration.body_record_ids == tuple(record.id for record in rendered.layout.records)
    assert sum(field.length for field in declaration.prefix_fields) == 328
    assert declaration.product_identity_requirement == "aeat-product-software-identity-v1"
    assert rendered.provenance_manifest.m303_variable_envelope is not None
    assert rendered.provenance_manifest.m303_variable_envelope.envelope == declaration
