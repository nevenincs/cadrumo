"""Profile-backed fixed-width header fields remain visible as read-only export context."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from cadrumo.application.modelo.tests.work_form_fixture import uncalculated_review
from cadrumo.application.modelo.work_form import build_modelo_work_form
from cadrumo.application.modelo.work_form_field_vocabulary import ModeloFormScalar
from cadrumo.application.modelo.work_form_models import ModeloFormContextFieldBlock
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.period import Period
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.form_context import resolve_form_context_field
from cadrumo.domain.calculations.registry.modelo_localization import binding_locale_key
from cadrumo.domain.calculations.registry.profile_bindings import ProfileProvider
from cadrumo.domain.calculations.registry.schema_form_layouts import FormContextFieldBlock, FormFieldBlock
from cadrumo.domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)

from ...compiler.form_layout_integrity import form_layout_failures
from ..generator import generate_revision_layout
from ..serialization import render_form_layout_toml

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _generated_profile_layout(operation: PinnedAuthorityOperation, rename_bindings: bool):
    snapshot = operation.reading_snapshot("720", filing_year=operation.supported_filing_years().horizon, period="0A")
    old_phone = "modelo-720.type_1.telefono-contacto"
    old_name = "modelo-720.type_1.nombre-contacto"
    renamed = {old_phone: "opaque-header-a", old_name: "opaque-header-b"} if rename_bindings else {}
    providers = {
        old_phone: ProfileProvider(profile_key="contact.contact_person_phone"),
        old_name: ProfileProvider(profile_key="contact.contact_person_name"),
    }
    bindings = tuple(
        binding.model_copy(update={"id": renamed.get(binding.id, binding.id), "provider": providers[binding.id]})
        if binding.id in providers
        else binding
        for binding in snapshot.revision.bindings
    )
    layouts = tuple(
        layout.model_copy(
            update={
                "records": tuple(
                    record.model_copy(
                        update={
                            "fields": tuple(
                                field.model_copy(update={"binding": renamed[field.binding]})
                                if field.binding in renamed
                                else field
                                for field in record.fields
                            )
                        }
                    )
                    for record in layout.records
                )
            }
        )
        for layout in snapshot.revision.export_layouts
    )
    revision = snapshot.revision.model_copy(
        update={"bindings": bindings, "export_layouts": layouts, "form_layouts": ()}
    )
    generated = generate_revision_layout(
        "720", revision, sources=snapshot.sources, data_root=bundled_path(), headings=()
    ).layout
    assert generated is not None
    return snapshot.model_copy(update={"revision": revision}), generated, renamed


@pytest.mark.parametrize("rename_bindings", [False, True])
def test_profile_context_keeps_export_order_and_exact_owner_without_becoming_an_input(
    operation: PinnedAuthorityOperation, rename_bindings: bool
) -> None:
    snapshot, generated, renamed = _generated_profile_layout(operation, rename_bindings)
    revision = snapshot.revision
    old_phone = "modelo-720.type_1.telefono-contacto"
    old_name = "modelo-720.type_1.nombre-contacto"
    blocks = generated.pages[0].sections[0].blocks
    assert isinstance(blocks[0], FormFieldBlock)
    assert blocks[0].binding_id == "modelo-720.type_1.tipo-de-soporte"
    contexts = [block for block in blocks if isinstance(block, FormContextFieldBlock)]
    assert len(contexts) == 2
    phone, name = contexts
    assert tuple(resolve_form_context_field(revision, block).binding for block in contexts) == (
        renamed.get(old_phone, old_phone),
        renamed.get(old_name, old_name),
    )
    assert blocks[1:3] == (phone, name)
    assert phone.export_field_id == "modelo-720-type_1-telefono-contacto"
    assert name.export_field_id == "modelo-720-type_1-nombre-contacto"
    assert all(block.export_layout_id == "modelo-720-fichero-aeat" for block in contexts)
    assert all(block.export_record_id == "modelo-720-type-1" for block in contexts)
    assert phone.heading_key == binding_locale_key("720", renamed.get(old_phone, old_phone), "label")
    assert name.heading_key == binding_locale_key("720", renamed.get(old_name, old_name), "label")
    with_layout = revision.model_copy(update={"form_layouts": (generated,)})
    assert form_layout_failures(with_layout) == ()
    assert 'kind = "context_field"' in render_form_layout_toml(str(revision.id), generated)


@pytest.mark.parametrize("saved_raw", [None, "", "0", "false", "900000001"])
def test_saved_binding_membership_wins_over_live_profile_in_readonly_context(
    operation: PinnedAuthorityOperation, saved_raw: str | None
) -> None:
    snapshot, layout, _ = _generated_profile_layout(operation, False)
    phone_id = "modelo-720.type_1.telefono-contacto"
    review = uncalculated_review(
        snapshot,
        operation,
        modelo="720",
        filing_year=snapshot.filing_year,
        period=Period.from_year_and_code(snapshot.filing_year, "0A"),
    )
    bindings = {} if saved_raw is None else {phone_id: saved_raw}
    instant = datetime(snapshot.filing_year, 1, 1, tzinfo=UTC)
    saved = CalculationRevision(
        calculation_revision_id=derive_calculation_revision_id(
            work_unit_id=review.work_unit_id,
            input_values_by_casilla_id={},
            binding_overrides=bindings,
            casilla_values={},
            filing_instance_evidence=None,
            source_provenance=(),
        ),
        work_unit_id=review.work_unit_id,
        registry_snapshot_ref=snapshot.snapshot_ref,
        state=CalculationRevisionState.BORRADOR,
        binding_overrides=bindings,
        filing_instance_evidence=None,
        source_provenance=(),
        created_at=instant,
        updated_at=instant,
    )
    form = build_modelo_work_form(
        review=review.model_copy(update={"calculation_revision_id": saved.calculation_revision_id}),
        snapshot=snapshot,
        layout=layout,
        revision=saved,
        permitted_surface=None,
        entered_casilla_ids=None,
        overridden_binding_ids=None,
        language=OutputLanguage.ES,
        profile_binding_values={phone_id: "900000000"},
    )
    phone = form.pages[0].sections[0].blocks[1]
    assert isinstance(phone, ModeloFormContextFieldBlock)
    assert phone.value == ("900000000" if saved_raw is None else saved_raw)


@pytest.mark.parametrize("profile_value", [False, Decimal("0"), "", None])
def test_first_projection_preserves_admitted_false_zero_empty_and_absent_scalars(
    operation: PinnedAuthorityOperation, profile_value: ModeloFormScalar
) -> None:
    snapshot, layout, _ = _generated_profile_layout(operation, False)
    review = uncalculated_review(
        snapshot,
        operation,
        modelo="720",
        filing_year=snapshot.filing_year,
        period=Period.from_year_and_code(snapshot.filing_year, "0A"),
    )
    form = build_modelo_work_form(
        review=review,
        snapshot=snapshot,
        layout=layout,
        revision=None,
        permitted_surface=None,
        entered_casilla_ids=None,
        overridden_binding_ids=None,
        language=OutputLanguage.ES,
        profile_binding_values={"modelo-720.type_1.telefono-contacto": profile_value},
    )
    phone = form.pages[0].sections[0].blocks[1]
    assert isinstance(phone, ModeloFormContextFieldBlock)
    assert type(phone.value) is type(profile_value)
    assert phone.value == profile_value
