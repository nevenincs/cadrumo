"""The 2025 Modelo 345 source renders its nested fixed-width slots exactly."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.export_value_policy import ExportValuePolicy

from ...compiler.authority import compiled_bundled_authority
from .._export_tree import render_complete_export_tree
from ..render_check import GeneratedExportBootstrapTransport, revision_render_inputs

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_modelo_345_2025_source_complete_nested_render(tmp_path: Path) -> None:
    source_ref = "aeat-dr-345-2025"
    source_sha256 = "fb0faaf68f8b0de29316bdc65eaeb3ba0dcb8a441eea4d5415d0cb4517c287fd"
    inputs = revision_render_inputs(
        compiled_bundled_authority(),
        modelo="345",
        revision="2025",
        source_ref=source_ref,
        bootstrap_transport=GeneratedExportBootstrapTransport(
            layout_id="generated-modelo-345-2025-fichero",
            line_ending="none",
            source_ref=source_ref,
            source_sha256=source_sha256,
        ),
        filing_year=2025,
        period="0A",
    )
    rendered = render_complete_export_tree(
        tmp_path / "export",
        revision_id=inputs.revision_id,
        joined=inputs.joined,
        semantic_map=inputs.semantic_map,
        transport_profile=inputs.transport_profile,
        render_profile=inputs.render_profile,
        render_profile_source_evidence=inputs.render_profile_source_evidence,
    )

    assert len(inputs.joined.fields) == len(rendered.field_derivations) == 41
    assert len(rendered.layout.records) == 2
    assert all(sum(field.length or 0 for field in record.fields) == 500 for record in rendered.layout.records)
    assert len(rendered.output_files) == 3

    fields = {str(field.id): field for record in rendered.layout.records for field in record.fields}
    support = fields["modelo-345-t1-tipo-soporte"]
    assert (support.offset, support.length, support.literal) == (58, 1, "T")
    fund_registration = fields["modelo-345-t2-fondo-pensiones-numero-registro"]
    assert (fund_registration.offset, fund_registration.length) == (147, 5)
    assert fund_registration.value_policy is ExportValuePolicy.MISTYPED_ALPHANUMERIC_TEXT
    pias_date = fields["modelo-345-t2-pias-fecha-primera-prima"]
    assert (pias_date.offset, pias_date.length) == (170, 8)
    assert pias_date.value_policy is ExportValuePolicy.YYYYMMDD
    pias_amount = fields["modelo-345-t2-pias-importe-acumulado"]
    assert (pias_amount.offset, pias_amount.length, pias_amount.decimals) == (178, 12, 2)
    assert pias_amount.value_policy is ExportValuePolicy.IMPLIED_DECIMAL
