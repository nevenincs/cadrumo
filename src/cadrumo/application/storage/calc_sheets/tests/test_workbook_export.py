"""The workbook export entry: one plan, one injected transport, honest facts.

The transport here is a recording stand-in, which is the point of these cases:
what is under test is the sequence the entry owns -- resolve the snapshot, build
the one canonical plan, hand exactly that plan to the transport, and report facts
that describe the bytes it returned. The real transport is exercised where it
lives, beside the offline materializer.
"""

from __future__ import annotations

import hashlib
from datetime import date

import pytest
from pydantic import ValidationError

from .....core.period import Period
from .....domain.calculations.registry.ids import ModeloId
from .....domain.calculations.registry.schema import RegistrySnapshot
from .....domain.calculations.registry.tests.published_authority import published_snapshot
from ..engine import build_export_plan
from ..records import AnySheetExportPlan, SheetExportMetadata, TabName
from ..workbook_export import ModeloWorkbookExport, export_modelo_workbook

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_PAYLOAD = b"workbook-payload"


class _RecordingMaterializer:
    """Stands in for a transport and keeps the plan it was handed."""

    def __init__(self) -> None:
        self.plans: list[AnySheetExportPlan] = []

    def __call__(self, plan: AnySheetExportPlan, /) -> bytes:
        self.plans.append(plan)
        return _PAYLOAD


def _m303_snapshot() -> RegistrySnapshot:
    return published_snapshot("303", filing_year=2025, period="1T", on=date(2025, 4, 1))


def _resolver(_modelo: ModeloId, _period: Period) -> RegistrySnapshot:
    return _m303_snapshot()


def test_entry_hands_the_canonical_plan_to_the_transport() -> None:
    materializer = _RecordingMaterializer()
    expected = build_export_plan(_m303_snapshot())

    export_modelo_workbook(
        modelo="303",
        period=Period.from_year_and_code(2025, "1T"),
        materializer=materializer,
        snapshot_resolver=_resolver,
    )

    assert len(materializer.plans) == 1
    handed = materializer.plans[0]
    assert isinstance(handed.metadata, SheetExportMetadata)
    # Same plan as the engine's own for this snapshot; the export timestamp is the
    # only thing two builds of one snapshot legitimately differ on.
    assert handed.model_dump(exclude={"metadata"}) == expected.model_dump(exclude={"metadata"})
    assert handed.metadata.modelo_id == expected.metadata.modelo_id
    assert handed.metadata.revision_id == expected.metadata.revision_id


def test_reported_facts_describe_the_returned_payload() -> None:
    materializer = _RecordingMaterializer()

    export = export_modelo_workbook(
        modelo="303",
        period=Period.from_year_and_code(2025, "1T"),
        materializer=materializer,
        snapshot_resolver=_resolver,
    )

    plan = materializer.plans[0]
    assert isinstance(plan.metadata, SheetExportMetadata)
    covered = {cell.casilla_id for cell in plan.value_cells if cell.casilla_id is not None}
    covered |= {cell.casilla_id for cell in plan.formula_cells if cell.casilla_id is not None}

    assert export.payload == _PAYLOAD
    assert export.byte_size == len(_PAYLOAD)
    assert export.sha256 == hashlib.sha256(_PAYLOAD).hexdigest()
    assert export.tab_names == tuple(tab.value for tab in plan.tabs)
    assert export.casilla_count == len(covered)
    assert export.modelo == "303"
    assert export.period == "1T"
    assert export.filing_year == 2025
    assert export.revision == plan.metadata.revision_id


def test_facts_that_do_not_describe_the_payload_are_refused() -> None:
    # The record exists so a caller can trust the digest it logs or stores; a
    # digest of something else must not be constructible.
    with pytest.raises(ValidationError):
        ModeloWorkbookExport(
            modelo="303",
            revision="2022",
            period="1T",
            filing_year=2025,
            payload=_PAYLOAD,
            byte_size=len(_PAYLOAD),
            sha256=hashlib.sha256(b"other-payload").hexdigest(),
            tab_names=(TabName.ENTRADAS.value,),
            casilla_count=0,
        )


def test_a_byte_size_that_contradicts_the_payload_is_refused() -> None:
    with pytest.raises(ValidationError):
        ModeloWorkbookExport(
            modelo="303",
            revision="2022",
            period="1T",
            filing_year=2025,
            payload=_PAYLOAD,
            byte_size=len(_PAYLOAD) + 1,
            sha256=hashlib.sha256(_PAYLOAD).hexdigest(),
            tab_names=(TabName.ENTRADAS.value,),
            casilla_count=0,
        )
