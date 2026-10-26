"""Rate-box export corrections preserve authored forms and refuse unrelated changes."""

from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.export_field_casilla import derive_casilla_export_refs

from ...compiler.form_layout_integrity import form_layout_failures, form_layout_source_digest
from ...compiler.loader import load_modelo_directory
from ..scalar_source_reconciliation import reconcile_scalar_export_sources

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_OWNERS = {
    "iva.anual.repercutido.recargo.super-reducido": "iva.anual.repercutido.recargo.tipo-0-5.cuota",
    "iva.anual.repercutido.recargo.reducido": "iva.anual.repercutido.recargo.tipo-1-4.cuota",
    "iva.anual.repercutido.recargo.general": "iva.anual.repercutido.recargo.tipo-5-2.cuota",
}


def _with_owners(revision, owners):
    layouts = tuple(
        layout.model_copy(
            update={
                "records": tuple(
                    record.model_copy(
                        update={
                            "fields": tuple(
                                field.model_copy(update={"casilla_id": owners[str(field.id)]})
                                if str(field.id) in owners
                                else field
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
    references = derive_casilla_export_refs(layouts, revision.bindings)
    return revision.model_copy(
        update={
            "export_layouts": layouts,
            "casillas": tuple(
                casilla.model_copy(update={"export_refs": references.get(casilla.id, ())})
                for casilla in revision.casillas
            ),
        }
    )


@pytest.fixture(scope="module", params=["2022", "2023", "2024", "2025"])
def rate_pair(request):
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/390")).revisions[request.param]
    replacements = {}
    for layout in revision.export_layouts:
        for record in layout.records:
            for field in record.fields:
                for old, new in _OWNERS.items():
                    if str(field.casilla_id) in (old, new):
                        replacements[str(field.id)] = (old, new)
    assert len(replacements) == 3
    before = _with_owners(revision, {field_id: old for field_id, (old, _) in replacements.items()})
    before = before.model_copy(
        update={
            "form_layouts": (
                before.form_layouts[0].model_copy(update={"source_state_digest": form_layout_source_digest(before)}),
            )
        }
    )
    after = _with_owners(before, {field_id: new for field_id, (_, new) in replacements.items()})
    return before, after, replacements


def test_exact_rate_sources_preserve_authored_presentation(rate_pair):
    before, after, replacements = rate_pair
    result = reconcile_scalar_export_sources(before, after, replacements=replacements)
    assert result.model_dump(exclude={"source_state_digest"}) == before.form_layouts[0].model_dump(
        exclude={"source_state_digest"}
    )
    assert not form_layout_failures(after.model_copy(update={"form_layouts": (result,)}))


@pytest.mark.parametrize("fault", ["other_quantity", "no_rate", "foreign_change", "stale_form", "missing_field"])
def test_rate_source_reconciliation_refuses_unreviewed_changes(rate_pair, fault):
    before, after, replacements = rate_pair
    if fault in {"other_quantity", "no_rate"}:
        target = next(
            casilla
            for casilla in before.casillas
            if str(casilla.id) == _OWNERS["iva.anual.repercutido.recargo.reducido"]
        )
        bindings = tuple(
            binding.model_copy(
                update={
                    "provider": binding.provider.model_copy(
                        update={"fact": "base_amount_sum"} if fault == "other_quantity" else {"applied_rates": None}
                    )
                }
            )
            if binding.id == target.binding
            else binding
            for binding in before.bindings
        )
        before = before.model_copy(update={"bindings": bindings})
        before = before.model_copy(
            update={
                "form_layouts": (
                    before.form_layouts[0].model_copy(
                        update={"source_state_digest": form_layout_source_digest(before)}
                    ),
                )
            }
        )
        after = after.model_copy(update={"bindings": bindings, "form_layouts": before.form_layouts})
    elif fault == "foreign_change":
        after = after.model_copy(update={"reviewed_by": "unreviewed-change"})
    elif fault == "stale_form":
        before = before.model_copy(
            update={"form_layouts": (before.form_layouts[0].model_copy(update={"source_state_digest": "0" * 64}),)}
        )
        after = after.model_copy(update={"form_layouts": before.form_layouts})
    else:
        replacements = {**replacements, "absent-field": next(iter(replacements.values()))}
    with pytest.raises(RegistryValidationError, match="refuses"):
        reconcile_scalar_export_sources(before, after, replacements=replacements)
