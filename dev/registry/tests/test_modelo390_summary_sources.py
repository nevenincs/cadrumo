"""Printed summary cells and filing bytes use the same canonical saved amounts."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from cadrumo.application.filing.producer_snapshot import FilingProducerSnapshot
from cadrumo.application.filing.record_field_renderer import render_record
from cadrumo.application.filing.record_types import RecordRenderRow
from cadrumo.application.storage.calc_sheets.engine import build_export_plan
from cadrumo.application.storage.calc_sheets.form_workbook import add_form_workbook
from cadrumo.application.storage.calc_sheets.layout import plan_layout
from cadrumo.application.storage.calc_sheets.records import TabName
from cadrumo.core.modelo import Modelo
from cadrumo.core.period import Period
from cadrumo.domain.calculations.export_field_kind import CasillaFieldKind
from cadrumo.domain.calculations.registry.governed_fact_scope import validating_governed_facts
from cadrumo.domain.calculations.registry.manual_input_selector import ManualInputProvider
from cadrumo.domain.filing.schema import ModeloDraft, registry_schema_version
from cadrumo.domain.submission.models import ModeloDraftStatus

from ..compiler.authority import compiled_bundled_authority
from ..workbook_demo import DemoCase, demonstration_producer, demonstration_snapshot

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]


@pytest.mark.parametrize("year", (2024, 2025))
@pytest.mark.parametrize("amount", (Decimal("123.45"), Decimal("-67.89"), Decimal("0"), None))
def test_printed_summary_and_filing_ignore_obsolete_manual_amounts(year, amount):
    snapshot = demonstration_snapshot(DemoCase("390", str(year), None, None, filing_year=year, period="0A"))
    revision = snapshot.revision
    record = next(r for layout in revision.export_layouts for r in layout.records if str(r.id) == "modelo-390-page-05")
    offsets = (1033, 1050, 1067, 1084, 1101, 1118, 1135, 1152, 1169, 1186)
    fields = tuple(f for f in record.fields if f.offset in offsets)
    assert len(fields) == 10
    assert all(f.kind is CasillaFieldKind.CASILLA and f.casilla_id is not None for f in fields)
    old_bindings = tuple(
        b
        for b in revision.bindings
        if isinstance(b.provider, ManualInputProvider)
        and b.provider.record == "page_5"
        and b.provider.offset in offsets
    )
    assert len(old_bindings) == 9
    values = {f.casilla_id: amount for f in fields if f.casilla_id is not None}
    layout = plan_layout(revision)
    assert not {b.id for b in old_bindings}.intersection(layout.binding_cells)
    addresses = {layout.address_for(key) for key in values}
    source = build_export_plan(snapshot)
    source = source.model_copy(
        update={
            "value_cells": tuple(
                c.model_copy(update={"value": amount}) if c.address in addresses else c for c in source.value_cells
            )
        }
    )
    plan = add_form_workbook(source, snapshot)
    assert {c.address for c in plan.value_cells if c.address in addresses and c.value == amount} == addresses
    for address in addresses:
        expected = f'IF(ISBLANK({address.qualified()}),"Sin dato",{address.qualified()})'
        assert sum(c.address.tab is TabName.FORM and c.formula == expected for c in plan.formula_cells) == 1

    with validating_governed_facts(compiled_bundled_authority()):
        instant = datetime(year, 12, 31, tzinfo=UTC)
        draft = ModeloDraft(
            draft_id="summary-render-test",
            modelo="390",
            period=Period.from_year_and_code(year, "0A"),
            profile_tax_id="12345678Z",
            subject_tax_id="12345678Z",
            snapshot_ref=snapshot.snapshot_ref,
            status=ModeloDraftStatus.BORRADOR,
            values=(),
            created_at=instant,
            updated_at=instant,
            schema_version=registry_schema_version(modelo="390", revision_id=revision.id),
        )
        # Reuse fictional general-profile facts, validating them for the actual modelo.
        producer = demonstration_producer(DemoCase("130", "2019-y-siguientes", None, None))
        assert producer is not None
        producer = FilingProducerSnapshot.model_validate({**producer.model_dump(), "modelo": Modelo("390")})
    wire = render_record(
        record.model_copy(update={"fields": fields}),
        draft=draft,
        producer_values={},
        producer_snapshot=producer,
        casilla_values=values,
        binding_values={(b.id, None): Decimal("99999.99") for b in old_bindings},
        row=RecordRenderRow(None, frozenset(b.id for b in old_bindings)),
        render_context=None,
        projection_values={},
    )
    # Independent 17-character signed-money oracle: 15 integers and two decimals.
    expected_wire = {
        Decimal("123.45"): "00000000000012345",
        Decimal("-67.89"): "N0000000000006789",
        Decimal("0"): "00000000000000000",
        None: "00000000000000000",
    }[amount]
    for offset in offsets:
        assert wire[offset - 1 : offset + 16] == expected_wire
