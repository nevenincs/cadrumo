"""Fictional template identity cannot become a filing or publication identity."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ..export_tables import IDENTITY_STAMP_KEYS, export_identity_stamps, guide_stamps
from ..records import (
    SheetExportMetadata,
    SheetExportPlan,
    SheetGuideContent,
    SheetReviewMetadata,
    SheetTemplatePreviewMetadata,
)
from ..workbook_cells import evidence_cell_blocks, guide_cell_blocks

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _preview() -> SheetExportPlan[SheetTemplatePreviewMetadata]:
    return SheetExportPlan[SheetTemplatePreviewMetadata](
        metadata=SheetTemplatePreviewMetadata(
            kind="template_preview",
            modelo_id="232",
            revision_id="2016-2017",
            preview_year=2017,
            preview_period="0A",
            template_digest="a" * 64,
            engine_version="test",
            title="Modelo 232 · Ejemplo ficticio 2017",
            exported_at=datetime(2026, 10, 6, tzinfo=UTC),
        ),
        guide=SheetGuideContent(title="Ejemplo ficticio", paragraphs=("No válido para presentar.",)),
    )


def test_preview_round_trip_cannot_decode_as_production_metadata_or_plan() -> None:
    plan = _preview()
    assert SheetExportPlan[SheetTemplatePreviewMetadata].model_validate_json(plan.model_dump_json()) == plan
    for metadata_type in (SheetExportMetadata, SheetReviewMetadata):
        with pytest.raises(ValidationError):
            metadata_type.model_validate_json(plan.metadata.model_dump_json())
    with pytest.raises(ValidationError):
        SheetExportPlan.model_validate_json(plan.model_dump_json())
    with pytest.raises(ValidationError):
        SheetExportPlan[SheetReviewMetadata].model_validate_json(plan.model_dump_json())


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("kind", "calculation"),
        ("preview_period", "invented"),
        ("template_digest", "bad"),
        ("exported_at", datetime(2026, 10, 6)),
        ("registry_snapshot_ref", "invented"),
    ],
)
def test_preview_rejects_invalid_identity(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        SheetTemplatePreviewMetadata.model_validate({**dict(_preview().metadata), field: value})


def test_preview_never_emits_production_stamps_or_evidence_fingerprint() -> None:
    plan = _preview()
    stamps = dict(export_identity_stamps(plan))
    assert stamps["cadrumo_preview_kind"] == "template_preview"
    assert all(key.startswith("cadrumo_preview_") for key in stamps)
    assert not set(stamps).intersection(IDENTITY_STAMP_KEYS)
    assert guide_stamps(plan) == ()
    assert guide_cell_blocks(plan) == ()
    assert evidence_cell_blocks(plan) == ()
    assert export_identity_stamps(plan.model_copy(update={"human_presentation": True})) == ()
