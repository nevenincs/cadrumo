"""Repeat actual official member fields without waiving geometry or source identity."""

from pathlib import Path

import pytest

from cadrumo.domain.calculations.export_field_kind import CasillaFieldKind
from cadrumo.domain.calculations.registry.afiliado_contribution_bindings import AfiliadoContributionProvider
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.export_field_casilla import export_field_casilla_id
from cadrumo.domain.calculations.registry.schema_exports import ExportRecordRepeat

from ...compiler.form_layout_integrity import form_layout_failures, form_layout_source_digest
from ...compiler.loader import load_modelo_directory
from ..row_binding_reconciliation import reconcile_export_row_bindings
from ._member_scalar_history import scalar_member_history

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture(scope="module")
def pair():
    before = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/156")).revisions["2003-y-siguientes"]
    before = scalar_member_history(before)
    bindings = {
        binding.provider.target_casilla_id: binding
        for binding in before.bindings
        if isinstance(binding.provider, AfiliadoContributionProvider)
    }
    layout = before.export_layouts[0]
    header, member = layout.records
    if member.repeat is not None:
        by_id = {binding.id: binding for binding in before.bindings}
        member = member.model_copy(
            update={
                "fields": tuple(
                    field.model_copy(
                        update={
                            "kind": CasillaFieldKind.CASILLA,
                            "casilla_id": export_field_casilla_id(member, field, bindings=by_id),
                            "binding": None,
                        }
                    )
                    if field.kind is CasillaFieldKind.BINDING
                    else field
                    for field in member.fields
                ),
                "repeat": None,
                "row_field_casilla_ids": {},
            }
        )
        layout = layout.model_copy(update={"records": (header, member)})
        before = before.model_copy(update={"export_layouts": (layout,)})
        before = before.model_copy(
            update={
                "form_layouts": (
                    before.form_layouts[0].model_copy(
                        update={"source_state_digest": form_layout_source_digest(before)}
                    ),
                )
            }
        )
    fields = tuple(
        field.model_copy(
            update={"kind": CasillaFieldKind.BINDING, "binding": bindings[field.casilla_id].id, "casilla_id": None}
        )
        if field.kind is CasillaFieldKind.CASILLA and field.casilla_id is not None
        else field
        for field in member.fields
    )
    member = member.model_copy(
        update={
            "repeat": ExportRecordRepeat.BINDING_ROWS,
            "row_field_casilla_ids": {
                binding.provider.row_field: target
                for target, binding in bindings.items()
                if isinstance(binding.provider, AfiliadoContributionProvider)
            },
            "fields": fields,
        }
    )
    after = before.model_copy(update={"export_layouts": (layout.model_copy(update={"records": (header, member)}),)})
    return before, after


def test_preserves_form_and_all_official_positions(pair):
    before, after = pair
    result = reconcile_export_row_bindings(before, after)
    assert result.model_dump(exclude={"source_state_digest"}) == before.form_layouts[0].model_dump(
        exclude={"source_state_digest"}
    )
    assert not form_layout_failures(after.model_copy(update={"form_layouts": (result,)}))
    assert len(after.export_layouts[0].records[1].row_field_casilla_ids) == 27


@pytest.mark.parametrize(
    "changes",
    [
        {"offset": 19},
        {"length": 8},
        {"source_refs": ()},
        {"legal_refs": ()},
        {"required": True},
        {"binding": "modelo-156-row-nombre"},
    ],
)
def test_refuses_field_reinterpretation(pair, changes):
    before, after = pair
    layout = after.export_layouts[0]
    header, member = layout.records
    member = member.model_copy(
        update={
            "fields": tuple(
                field.model_copy(update=changes) if field.offset == 18 else field for field in member.fields
            )
        }
    )
    broken = after.model_copy(update={"export_layouts": (layout.model_copy(update={"records": (header, member)}),)})
    with pytest.raises(RegistryValidationError):
        reconcile_export_row_bindings(before, broken)


@pytest.mark.parametrize("changes", [{"binding_record": "afiliado"}, {"row_field_casilla_ids": {}}, {"order": 9}])
def test_refuses_record_reinterpretation(pair, changes):
    before, after = pair
    layout = after.export_layouts[0]
    header, member = layout.records
    broken = after.model_copy(
        update={"export_layouts": (layout.model_copy(update={"records": (header, member.model_copy(update=changes))}),)}
    )
    with pytest.raises(RegistryValidationError):
        reconcile_export_row_bindings(before, broken)


def test_refuses_changed_binding_authority_and_noop(pair):
    before, after = pair
    with pytest.raises(RegistryValidationError):
        reconcile_export_row_bindings(before, before)
    with pytest.raises(RegistryValidationError):
        reconcile_export_row_bindings(before, after.model_copy(update={"bindings": ()}))


def test_refuses_stale_or_reviewed_form(pair):
    before, after = pair
    form = before.form_layouts[0]
    for update in (
        {"source_state_digest": "0" * 64},
        {"review": form.review.model_copy(update={"state": type(form.review.state)("reviewed")})},
    ):
        forms = (form.model_copy(update=update),)
        with pytest.raises(RegistryValidationError):
            reconcile_export_row_bindings(
                before.model_copy(update={"form_layouts": forms}), after.model_copy(update={"form_layouts": forms})
            )
