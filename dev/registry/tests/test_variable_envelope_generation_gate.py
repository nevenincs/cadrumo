"""Real-source gate for variable-envelope retention and generation refusal."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.core.resources import bundled_path
from cadrumo.domain.calculations.registry import (
    RegistryValidationError,
    bundled_authority,
    load_catalogue_file,
)

from .._export_tree import ExportRenderProfile, render_complete_export_tree
from .._record_design_ir import load_record_design_intermediate
from .._semantic_map import SemanticMap
from .._semantic_map_join import join_record_design_semantics

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


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
            profile=ExportRenderProfile(
                modelo="200",
                design_epoch="2025",
                source_ref="aeat-dr-200-2025",
                source_sha256=parsed.source.source_sha256,
                layout_id="m200-envelope-gate",
                format="fixed_width",
                encoding="latin-1",
                line_ending="crlf",
                serializer_convention="rtoml-pretty-v1",
            ),
        )

    assert not target.exists()
