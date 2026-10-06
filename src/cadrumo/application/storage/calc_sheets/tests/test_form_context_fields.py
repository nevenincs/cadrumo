"""Declared filing context is a read-only value, never a guessed workbook field."""

from decimal import Decimal

import pytest

from cadrumo.core.filing_producer_key import FilingProducerKey
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.export import derive_export_layouts_from_bindings
from cadrumo.domain.calculations.registry.export_semantics import ExportDraftAttribute
from cadrumo.domain.calculations.registry.schema_form_layouts import FormContextFieldBlock

from ..engine import build_export_plan
from ..form_workbook import add_form_workbook
from ..records import TabName
from .test_form_workbook import form_source as form_source

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _with_context(snapshot, *, producer=None, draft=None):
    layout, record, field = next(
        (layout, record, field)
        for layout in derive_export_layouts_from_bindings(snapshot.revision)
        for record in layout.records
        for field in record.fields
        if record.repeat is None and (field.producer_key == producer if producer else field.draft_attribute == draft)
    )
    block = FormContextFieldBlock(
        id="context",
        export_layout_id=layout.id,
        export_record_id=record.id,
        export_field_id=field.id,
        heading_key="test.context.caption",
        official_heading="Dato declarado",
    )
    form = snapshot.revision.form_layouts[0]
    page = form.pages[0]
    section = page.sections[0]
    section = section.model_copy(update={"blocks": (block, *section.blocks)})
    page = page.model_copy(update={"sections": (section, *page.sections[1:])})
    form = form.model_copy(update={"pages": (page, *form.pages[1:])})
    snapshot = snapshot.model_copy(update={"revision": snapshot.revision.model_copy(update={"form_layouts": (form,)})})
    return snapshot, block


def test_year_comes_from_bound_snapshot_and_is_read_only(form_source):
    snapshot, _ = form_source
    snapshot, _ = _with_context(snapshot, draft=ExportDraftAttribute.FILING_YEAR)
    result = add_form_workbook(build_export_plan(snapshot), snapshot)
    label = next(c for c in result.value_cells if c.address.tab is TabName.FORM and c.value == "Dato declarado")
    value = next(
        c
        for c in result.value_cells
        if c.address.tab is TabName.FORM and c.address.row == label.address.row and c.address.column == 9
    )
    assert value.value == Decimal(snapshot.filing_year)
    assert value.casilla_id is None
    assert not any(c.address == value.address for c in result.cell_constraints)
    assert any(p.tab is TabName.FORM and p.start_row <= value.address.row <= p.end_row for p in result.protected_ranges)


def test_absent_taxpayer_is_unknown_and_not_invented(form_source):
    snapshot, _ = form_source
    snapshot, _ = _with_context(snapshot, producer=FilingProducerKey.TAXPAYER_TAX_ID)
    result = add_form_workbook(build_export_plan(snapshot), snapshot)
    label = next(c for c in result.value_cells if c.address.tab is TabName.FORM and c.value == "Dato declarado")
    assert (
        next(
            c.value
            for c in result.value_cells
            if c.address.tab is TabName.FORM and c.address.row == label.address.row and c.address.column == 9
        )
        == "Sin dato"
    )


def test_unknown_context_export_reference_is_refused(form_source):
    snapshot, _ = form_source
    snapshot, block = _with_context(snapshot, producer=FilingProducerKey.TAXPAYER_TAX_ID)
    form = snapshot.revision.form_layouts[0]
    page = form.pages[0]
    section = page.sections[0].model_copy(
        update={"blocks": (block.model_copy(update={"export_field_id": "missing-field"}), *page.sections[0].blocks[1:])}
    )
    form = form.model_copy(update={"pages": (page.model_copy(update={"sections": (section,)}),)})
    snapshot = snapshot.model_copy(update={"revision": snapshot.revision.model_copy(update={"form_layouts": (form,)})})
    with pytest.raises(RegistryValidationError, match="exactly one"):
        add_form_workbook(build_export_plan(snapshot), snapshot)


def _producer(modelo="130"):
    from cadrumo.application.filing.producer_snapshot import (
        FilingElectionFacts,
        FilingProducerSnapshot,
        GeneralFilingProfileFacts,
        PresenterIdentity,
        TaxpayerIdentityFacts,
    )
    from cadrumo.core.modelo import Modelo
    from cadrumo.core.payment_election import PaymentElection
    from cadrumo.core.prior_domiciliation_election import PriorDomiciliationElection
    from cadrumo.core.refund_election import RefundElection

    return FilingProducerSnapshot(
        modelo=Modelo(modelo),
        taxpayer_tax_id="12345678Z",
        taxpayer_identity=TaxpayerIdentityFacts(legal_name=None, given_name="=1+1", surnames="=1+1", full_name="=1+1"),
        presenter=PresenterIdentity(tax_id="00000000T", full_name="Ejemplo"),
        model_profile=GeneralFilingProfileFacts(),
        elections=FilingElectionFacts(
            result_disposition=None,
            payment=PaymentElection.INGRESO,
            refund=RefundElection.COMPENSAR,
            prior_domiciliation=PriorDomiciliationElection.KEEP,
        ),
        amendment_evidence=None,
        selected_account=None,
        m303_filing_facts=None,
    )


@pytest.mark.usefixtures("operation")
def test_explicit_producer_text_remains_literal(form_source):
    snapshot, _ = form_source
    producer_key = next(
        field.producer_key
        for layout in derive_export_layouts_from_bindings(snapshot.revision)
        for record in layout.records
        for field in record.fields
        if field.producer_key
        in {
            FilingProducerKey.TAXPAYER_GIVEN_NAME,
            FilingProducerKey.TAXPAYER_FULL_NAME,
            FilingProducerKey.TAXPAYER_SURNAMES,
        }
    )
    snapshot, _ = _with_context(snapshot, producer=producer_key)
    result = add_form_workbook(build_export_plan(snapshot), snapshot, producer_snapshot=_producer())
    cell = next(c for c in result.value_cells if c.address.tab is TabName.FORM and c.value == "=1+1")
    assert not any(c.address == cell.address for c in result.formula_cells)
    assert any(f.address == cell.address and f.pattern == "@" for f in result.number_formats)


@pytest.mark.usefixtures("operation")
def test_other_model_producer_refused_even_for_year(form_source):
    snapshot, _ = form_source
    snapshot, _ = _with_context(snapshot, draft=ExportDraftAttribute.FILING_YEAR)
    with pytest.raises(RegistryValidationError, match="another modelo"):
        add_form_workbook(build_export_plan(snapshot), snapshot, producer_snapshot=_producer("131"))


def _with_summary(snapshot, *, wire_policy=None, unused=False):
    from cadrumo.domain.calculations.export_field_kind import CasillaFieldKind

    binding = next(b for b in snapshot.revision.bindings if b.value.channel.value == "decimal")
    if unused:
        binding = binding.model_copy(update={"id": "test-unconsumed-summary"})
        snapshot = snapshot.model_copy(
            update={
                "revision": snapshot.revision.model_copy(update={"bindings": (*snapshot.revision.bindings, binding)})
            }
        )
    export = snapshot.revision.export_layouts[0]
    record = next(r for r in export.records if r.repeat is None)
    original = record.fields[0]
    field = original.model_copy(
        update={
            "kind": CasillaFieldKind.BINDING,
            "value_policy": wire_policy,
            "binding": binding.id,
            "producer_key": None,
            "draft_attribute": None,
            "casilla_id": None,
        }
    )
    record = record.model_copy(update={"fields": (field, *record.fields[1:])})
    export = export.model_copy(update={"records": tuple(record if r.id == record.id else r for r in export.records)})
    revision = snapshot.revision.model_copy(update={"export_layouts": (export,)})
    snapshot = snapshot.model_copy(update={"revision": revision})
    block = FormContextFieldBlock(
        id="summary",
        export_layout_id=export.id,
        export_record_id=record.id,
        export_field_id=field.id,
        heading_key="test.summary.caption",
        official_heading="Importe total",
        box_number="02",
    )
    form = revision.form_layouts[0]
    page = form.pages[0]
    section = page.sections[0].model_copy(update={"blocks": (block, *page.sections[0].blocks)})
    page = page.model_copy(update={"sections": (section, *page.sections[1:])})
    form = form.model_copy(update={"pages": (page, *form.pages[1:])})
    return (
        snapshot.model_copy(update={"revision": revision.model_copy(update={"form_layouts": (form,)})}),
        block,
        binding,
    )


def test_summary_links_existing_scalar_without_editable_duplicate(form_source):
    snapshot, _ = form_source
    snapshot, _block, _binding = _with_summary(snapshot)
    plan = build_export_plan(snapshot)
    result = add_form_workbook(plan, snapshot)
    label = next(c for c in result.value_cells if c.address.tab is TabName.FORM and c.value == "[02] Importe total")
    cell = next(c for c in result.formula_cells if c.address.tab is TabName.FORM and c.address.row == label.address.row)
    assert "ISBLANK(" in cell.formula and '"Sin dato"' in cell.formula
    assert cell.casilla_id is None
    assert not any(c.address == cell.address for c in result.cell_constraints)
    assert any(p.tab is TabName.FORM and p.start_row <= cell.address.row <= p.end_row for p in result.protected_ranges)


def test_summary_rejects_missing_binding(form_source):
    from cadrumo.domain.calculations.registry.form_context import resolve_form_context_field

    snapshot, _ = form_source
    snapshot, block, binding = _with_summary(snapshot)
    revision = snapshot.revision.model_copy(
        update={"bindings": tuple(b for b in snapshot.revision.bindings if b.id != binding.id)}
    )
    with pytest.raises(RegistryValidationError, match="scalar binding"):
        resolve_form_context_field(revision, block)


def test_summary_rejects_row_set_binding(form_source):
    from cadrumo.domain.calculations.registry.binding_value_contract import BindingValueChannel
    from cadrumo.domain.calculations.registry.form_context import resolve_form_context_field

    snapshot, _ = form_source
    snapshot, block, binding = _with_summary(snapshot)
    changed = binding.model_copy(
        update={"value": binding.value.model_copy(update={"channel": BindingValueChannel.ROW_SET})}
    )
    revision = snapshot.revision.model_copy(
        update={"bindings": tuple(changed if b.id == binding.id else b for b in snapshot.revision.bindings)}
    )
    with pytest.raises(RegistryValidationError, match="scalar binding"):
        resolve_form_context_field(revision, block)


@pytest.mark.parametrize("wire_policy", [None, "integer-part", "fractional-digits"])
@pytest.mark.parametrize("value", [None, Decimal("0"), Decimal("-125.37")])
def test_summary_preserves_backing_scalar_and_live_reference(form_source, value, wire_policy):
    from ..form_workbook import _binding_addresses

    snapshot, _ = form_source
    from cadrumo.domain.calculations.registry.export_value_policy import ExportValuePolicy

    snapshot, _block, binding = _with_summary(
        snapshot, wire_policy=ExportValuePolicy(wire_policy) if wire_policy else None
    )
    plan = build_export_plan(snapshot)
    address = _binding_addresses(plan, snapshot.revision)[str(binding.id)]
    plan = plan.model_copy(
        update={
            "value_cells": tuple(
                c.model_copy(update={"value": value}) if c.address == address else c for c in plan.value_cells
            )
        }
    )
    result = add_form_workbook(plan, snapshot)
    label = next(c for c in result.value_cells if c.address.tab is TabName.FORM and c.value == "[02] Importe total")
    formula = next(
        c for c in result.formula_cells if c.address.tab is TabName.FORM and c.address.row == label.address.row
    )
    assert formula.formula == f'IF(ISBLANK({address.qualified()}),"Sin dato",{address.qualified()})'
    assert next(c.value for c in result.value_cells if c.address == address) == value


def test_summary_without_formula_or_manual_consumer_allocates_readonly_source(form_source):
    from ..layout import plan_layout

    snapshot, _ = form_source
    snapshot, _block, binding = _with_summary(snapshot, unused=True)
    layout = plan_layout(snapshot.revision)
    address = layout.binding_cells[binding.id]
    row = next(row for row in layout.binding_rows if row.binding == binding.id)
    assert row.readonly
    plan = build_export_plan(snapshot)
    cell = next(c for c in plan.value_cells if c.address == address)
    assert cell.role == "source_value" and cell.value is None
    assert any(p.tab is address.tab and p.start_row <= address.row <= p.end_row for p in plan.protected_ranges)
    assert not any(c.address == address for c in plan.cell_constraints)
    # Human labelling remains an independent requirement; use the exact
    # declared heading as the summary source's fallback, never its identifier.
    result = add_form_workbook(plan, snapshot)
    assert any(c.value == "Importe total" for c in result.value_cells)
    assert not any(c.value == binding.id for c in result.value_cells)
