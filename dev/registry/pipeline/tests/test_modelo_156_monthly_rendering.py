"""Twelve independent status/amount pairs reproduce the official monthly bytes."""

from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.fixed_width_codec import render_fixed_width_export_field
from cadrumo.domain.calculations.registry.schema_exports import ExportLayoutDefinition

from ...compiler.loader import load_modelo_directory, load_shared_catalogues
from .._export_tree import render_complete_export_tree
from ..render_check import _revision_render_inputs

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(scope="module")
def rendered(tmp_path_factory: pytest.TempPathFactory) -> ExportLayoutDefinition:
    root = Path("src/cadrumo/_data")
    inputs = _revision_render_inputs(
        load_modelo_directory(root / "registry/aeat/modelos/156"),
        load_shared_catalogues(root / "registry/aeat"),
        modelo="156",
        revision="2003-y-siguientes",
        source_ref="enrolled-modelo-156-layout",
        bootstrap_transport=None,
        filing_year=2025,
        period="0A",
        source_root=root,
    )
    return render_complete_export_tree(
        tmp_path_factory.mktemp("modelo156-months") / "export",
        revision_id="2003-y-siguientes",
        joined=inputs.joined,
        semantic_map=inputs.semantic_map,
        transport_profile=inputs.transport_profile,
        render_profile=inputs.render_profile,
        render_profile_source_evidence=inputs.render_profile_source_evidence,
    ).layout


@pytest.mark.parametrize("index", range(12))
def test_each_month_keeps_status_separate_from_euro_cents(rendered: ExportLayoutDefinition, index: int) -> None:
    (_, member) = rendered.records
    fields = {field.offset: field for field in member.fields}
    start = 88 + index * 9
    status, amount = fields[start], fields[start + 1]
    assert (status.length, amount.length) == (1, 8)
    assert status.binding == f"modelo-156-row-cotizacion-{index + 1:02d}-situacion"
    assert amount.binding == f"modelo-156-row-cotizacion-{index + 1:02d}-importe"
    assert (
        member.row_field_casilla_ids[f"cotizacion_{index + 1:02d}_situacion"]
        != member.row_field_casilla_ids[f"cotizacion_{index + 1:02d}_importe"]
    )
    # Letter membership is checked by the casilla constraints; the generic
    # text codec owns padding, not the source's business-value vocabulary.
    assert (
        render_fixed_width_export_field(status, "S") + render_fixed_width_export_field(amount, Decimal("100.25"))
        == "S00010025"
    )
    assert (
        render_fixed_width_export_field(status, "N") + render_fixed_width_export_field(amount, Decimal("0"))
        == "N00000000"
    )
    for invalid in (Decimal("-0.01"), Decimal("1000000")):
        with pytest.raises(RegistryValidationError):
            render_fixed_width_export_field(amount, invalid)


def test_record_geometry_remains_exactly_250_bytes(rendered: ExportLayoutDefinition) -> None:
    for record in rendered.records:
        cursor = 1
        for field in record.fields:
            assert field.offset == cursor and field.length is not None
            cursor += field.length
        assert cursor == 251
