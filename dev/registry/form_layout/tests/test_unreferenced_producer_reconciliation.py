"""Reconcile unseen producer corrections without blessing other form changes."""

from pathlib import Path

import pytest

from cadrumo.core.filing_producer_key import FilingProducerKey
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema_form_layouts import FormContextFieldBlock

from ...compiler.form_layout_integrity import form_layout_failures, form_layout_source_digest
from ...compiler.loader import load_modelo_directory
from ..reconciliation import reconcile_unreferenced_export_producers

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _change(revision, field_ids, **updates):
    if "producer_key" in updates:
        updates["producer_key"] = FilingProducerKey(updates["producer_key"])
    layouts = tuple(
        layout.model_copy(
            update={
                "records": tuple(
                    record.model_copy(
                        update={
                            "fields": tuple(
                                field.model_copy(update=updates) if field.id in field_ids else field
                                for field in record.fields
                            )
                        }
                    )
                    for record in layout.records
                )
            }
        )
        for layout in revision.export_layouts
    )
    return revision.model_copy(update={"export_layouts": layouts})


@pytest.fixture
def revision():
    current = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/190")).revisions["2022"]
    ids = {
        field.id
        for layout in current.export_layouts
        for record in layout.records
        for field in record.fields
        if field.producer_key == FilingProducerKey.TAXPAYER_TAX_ID
    }
    before = _change(current, ids, producer_key="presenter.tax_id")
    original = before.form_layouts[0]
    pages = tuple(
        page.model_copy(
            update={
                "sections": tuple(
                    section.model_copy(
                        update={
                            "blocks": tuple(
                                block
                                for block in section.blocks
                                if not (
                                    isinstance(block, FormContextFieldBlock)
                                    and block.export_field_id == "modelo-190-decl-nif"
                                )
                            )
                        }
                    )
                    for section in page.sections
                )
            }
        )
        for page in original.pages
    )
    before = before.model_copy(update={"form_layouts": (original.model_copy(update={"pages": pages}),)})
    form = before.form_layouts[0].model_copy(update={"source_state_digest": form_layout_source_digest(before)})
    return before.model_copy(update={"form_layouts": (form,)})


def test_unseen_nif_correction_preserves_every_presentation_field(revision):
    ids = {
        f.id
        for layout in revision.export_layouts
        for record in layout.records
        for f in record.fields
        if f.producer_key == "presenter.tax_id"
    }
    assert len(ids) == 2
    after = _change(revision, ids, producer_key="taxpayer.tax_id")
    reconciled = reconcile_unreferenced_export_producers(revision, after)
    assert reconciled.model_dump(exclude={"source_state_digest"}) == revision.form_layouts[0].model_dump(
        exclude={"source_state_digest"}
    )
    assert not form_layout_failures(after.model_copy(update={"form_layouts": (reconciled,)}))


def test_displayed_name_change_is_not_a_digest_refresh(revision):
    after = _change(revision, {"modelo-190-decl-apellidos-razon-social"}, producer_key="taxpayer.legal_name")
    with pytest.raises(RegistryValidationError, match="displayed"):
        reconcile_unreferenced_export_producers(revision, after)


@pytest.mark.parametrize("updates", [{"offset": 10}, {"required": True}, {"length": 10}])
def test_unseen_identity_correction_cannot_hide_another_export_change(revision, updates):
    after = _change(revision, {"modelo-190-decl-nif"}, producer_key="taxpayer.tax_id", **updates)
    with pytest.raises(RegistryValidationError, match="beyond"):
        reconcile_unreferenced_export_producers(revision, after)


def test_unchanged_or_stale_form_is_not_reconciled(revision):
    with pytest.raises(RegistryValidationError, match="beyond"):
        reconcile_unreferenced_export_producers(revision, revision)
    stale = revision.model_copy(
        update={"form_layouts": (revision.form_layouts[0].model_copy(update={"source_state_digest": "0" * 64}),)}
    )
    with pytest.raises(RegistryValidationError, match="stale"):
        reconcile_unreferenced_export_producers(
            stale, _change(stale, {"modelo-190-decl-nif"}, producer_key="taxpayer.tax_id")
        )
