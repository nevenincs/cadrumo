"""Committed recargo partitions refuse export while observations lack a rate."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.rate_box_partition import derive_rate_box_partitions
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.filing.schema import ModeloDraft, ModeloValue, ModeloValueKind, registry_schema_version
from ....domain.submission.models import ModeloDraftStatus
from ..errors import ModeloApplicationError
from ..export_parity import assert_rate_boxes_account_for_total

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.mark.parametrize("year", (2022, 2023, 2024, 2025))
@pytest.mark.parametrize("unallocated", (False, True))
def test_committed_recargo_coverage_controls_export(
    operation: PinnedAuthorityOperation, year: int, unallocated: bool
) -> None:
    snapshot = operation.snapshot("390", filing_year=year, period="0A")
    partitions = derive_rate_box_partitions(snapshot.revision)
    recargo = [item for item in partitions if item.total_casilla_id == "iva.anual.repercutido.recargo.reducido"]
    assert len(recargo) == 1, "the committed recargo control must remain visible to export"
    partition = recargo[0]
    assert "iva.anual.repercutido.recargo.tipo-1-4.cuota" in partition.box_casilla_ids
    stamped = datetime(2026, 10, 7, tzinfo=UTC)
    draft = ModeloDraft(
        draft_id="recargo-coverage-proof",
        modelo="390",
        period=Period.from_year_and_code(year, "0A"),
        profile_tax_id="12345678Z",
        subject_tax_id="12345678Z",
        snapshot_ref=RegistrySnapshotRef(
            modelo="390", revision_id=str(snapshot.revision.id), modelo_year=year, period="0A"
        ),
        status=ModeloDraftStatus.BORRADOR,
        values=(
            ModeloValue(
                casilla_id=partition.total_casilla_id,
                value=Decimal("9.00") if unallocated else Decimal("3.00"),
                kind=ModeloValueKind.LITERAL,
                source="independent coverage fixture",
            ),
            ModeloValue(
                casilla_id="iva.anual.repercutido.recargo.tipo-1-4.cuota",
                value=Decimal("3.00"),
                kind=ModeloValueKind.LITERAL,
                source="independent coverage fixture",
            ),
        ),
        created_at=stamped,
        updated_at=stamped,
        schema_version=registry_schema_version(modelo="390", revision_id=str(snapshot.revision.id)),
    )
    if not unallocated:
        assert_rate_boxes_account_for_total(partitions, draft=draft)
        return
    with pytest.raises(ModeloApplicationError) as caught:
        assert_rate_boxes_account_for_total(partitions, draft=draft)
    assert caught.value.translated_message == "application.filing.export_parity.errors.rate_boxes_understate_total"
    context = caught.value.context
    assert context is not None
    assert context["shortfall_count"] == 1
    shortfalls = context["shortfalls"]
    assert isinstance(shortfalls, tuple) and len(shortfalls) == 1
    assert isinstance(shortfalls[0], dict)
    assert shortfalls[0]["unaccounted"] == "6.00"
