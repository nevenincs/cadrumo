"""Hard-cut proof that declaration rendering is snapshot-owned."""

from __future__ import annotations

import inspect
from operator import attrgetter

import pytest

from ... import filing
from .._export import export_draft
from ._export_support import (
    _approved_modelo_131_historical_registry_draft,
    _schema_provider,
    _typed_modelo_131_producer_snapshot,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_snapshot_free_renderer_and_external_projection_arguments_are_unreachable() -> None:
    """The removed injection seam must stay absent from both facade and exporter."""
    assert not hasattr(filing, "render_layout")
    with pytest.raises(AttributeError):
        attrgetter("render_layout")(filing)
    assert "render_layout" not in filing.__all__

    parameters = inspect.signature(export_draft).parameters
    assert "layout" not in parameters
    assert "projection_values" not in parameters
    assert "projection_mapping" not in parameters
    assert "projection_refs" not in parameters


def test_export_uses_the_selected_snapshot_owned_layout(tmp_path) -> None:
    """The public positive path selects its layout from the exact provider snapshot."""
    output_path = tmp_path / "modelo-131.txt"
    result = export_draft(
        _approved_modelo_131_historical_registry_draft(),
        output_path=output_path,
        producer_snapshot=_typed_modelo_131_producer_snapshot(),
        schema_provider=_schema_provider(filing_year=2023, period="4T", modelos=("131",)),
    )

    assert result.output_path == output_path
    assert result.byte_size == len(output_path.read_bytes())
    assert result.byte_size > 0
