"""Historical 390 summary source corrections preserve the immutable handoff."""

from pathlib import Path

import pytest

from cadrumo.domain.calculations.export_field_kind import CasillaFieldKind
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.export_field_casilla import derive_casilla_export_refs
from cadrumo.domain.calculations.registry.manual_input_selector import ManualInputProvider

from ...compiler.form_layout_integrity import form_layout_failures, form_layout_source_digest
from ...compiler.loader import load_modelo_directory
from ..scalar_source_reconciliation import reconcile_scalar_export_sources

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# Official page 5 record positions, independently paired to printed boxes.
TARGETS = {
    1033: "iva.anual.regimen-simplificado.cuota-resultante-no-agricola",
    1050: "iva.anual.regimen-simplificado.cuota-resultante-agricola",
    1067: "iva.anual.regimen-simplificado.aic-bienes-cuota-devengada",
    1084: "iva.anual.regimen-simplificado.inversion-sujeto-pasivo",
    1101: "iva.anual.regimen-simplificado.entrega-activos-fijos",
    1135: "iva.anual.regimen-simplificado.iva-soportado-activos-fijos",
    1152: "iva.anual.regimen-simplificado.regularizacion-bienes-inversion",
    1169: "iva.anual.regimen-simplificado.suma-deducciones",
    1186: "iva.anual.regimen-simplificado.resultado",
}


@pytest.fixture(scope="module", params=["2024", "2025"])
def pair(request):
    before = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/390")).revisions[request.param]
    # Reconstruct the old defect explicitly after the live exports are repaired.
    # Historical declarations remain available; no production source is changed.
    old_bindings = {
        b.provider.offset: b.id
        for b in before.bindings
        if isinstance(b.provider, ManualInputProvider)
        and b.provider.record == "page_5"
        and b.provider.offset in TARGETS
    }
    assert len(old_bindings) == 9
    old_layouts = tuple(
        layout.model_copy(
            update={
                "records": tuple(
                    record.model_copy(
                        update={
                            "fields": tuple(
                                field.model_copy(
                                    update={
                                        "kind": CasillaFieldKind.BINDING,
                                        "binding": old_bindings[field.offset],
                                        "casilla_id": None,
                                    }
                                )
                                if str(record.id) == "modelo-390-page-05" and field.offset in TARGETS
                                else field
                                for field in record.fields
                            )
                        }
                    )
                    for record in layout.records
                )
            }
        )
        for layout in before.export_layouts
    )
    before = before.model_copy(update={"export_layouts": old_layouts})
    refs = derive_casilla_export_refs(before.export_layouts, before.bindings)
    before = before.model_copy(
        update={"casillas": tuple(c.model_copy(update={"export_refs": refs.get(c.id, ())}) for c in before.casillas)}
    )
    before = before.model_copy(
        update={
            "form_layouts": (
                before.form_layouts[0].model_copy(update={"source_state_digest": form_layout_source_digest(before)}),
            )
        }
    )
    replacements = {}
    layouts = []
    for layout in before.export_layouts:
        records = []
        for record in layout.records:
            fields = []
            for field in record.fields:
                if str(record.id) == "modelo-390-page-05" and field.offset in TARGETS:
                    target = TARGETS[field.offset]
                    replacements[str(field.id)] = (str(field.binding), target)
                    field = field.model_copy(
                        update={"kind": CasillaFieldKind.CASILLA, "binding": None, "casilla_id": target}
                    )
                fields.append(field)
            records.append(record.model_copy(update={"fields": tuple(fields)}))
        layouts.append(layout.model_copy(update={"records": tuple(records)}))
    after = before.model_copy(update={"export_layouts": tuple(layouts)})
    refs = derive_casilla_export_refs(after.export_layouts, after.bindings)
    after = after.model_copy(
        update={"casillas": tuple(c.model_copy(update={"export_refs": refs.get(c.id, ())}) for c in after.casillas)}
    )
    return before, after, replacements


def test_exact_summary_sources_preserve_form_and_handoff(pair):
    before, after, replacements = pair
    result = reconcile_scalar_export_sources(before, after, replacements=replacements)
    assert len(replacements) == 9
    assert result.model_dump(exclude={"source_state_digest"}) == before.form_layouts[0].model_dump(
        exclude={"source_state_digest"}
    )
    assert not form_layout_failures(after.model_copy(update={"form_layouts": (result,)}))
    for casilla in after.casillas:
        if str(casilla.id) in TARGETS.values():
            assert casilla.binding == next(c.binding for c in before.casillas if c.id == casilla.id)
            assert str(casilla.binding).startswith("modelo-390-m303-simplificado-")
            assert len(casilla.export_refs) == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"offset": 1034},
        {"length": 16},
        {"signed": False},
        {"decimals": 3},
        {"source_refs": ()},
        {"legal_refs": ()},
        {"required": True},
    ],
)
def test_refuses_geometry_policy_and_evidence_changes(pair, changes):
    before, after, replacements = pair
    layouts = tuple(
        layout.model_copy(
            update={
                "records": tuple(
                    record.model_copy(
                        update={
                            "fields": tuple(
                                field.model_copy(update=changes) if str(field.id) in replacements else field
                                for field in record.fields
                            )
                        }
                    )
                    for record in layout.records
                )
            }
        )
        for layout in after.export_layouts
    )
    with pytest.raises(RegistryValidationError):
        reconcile_scalar_export_sources(
            before, after.model_copy(update={"export_layouts": layouts}), replacements=replacements
        )


@pytest.mark.parametrize(
    "defect",
    ["missing", "extra", "wrong_binding", "wrong_casilla", "empty", "noop", "refs", "authority", "stale", "reviewed"],
)
def test_refuses_unpinned_or_unrelated_changes(pair, defect):
    before, after, replacements = pair
    replacements = dict(replacements)
    key = next(iter(replacements))
    binding, target = replacements[key]
    if defect == "missing":
        del replacements[key]
    elif defect == "extra":
        replacements["nonexistent"] = (binding, target)
    elif defect == "wrong_binding":
        replacements[key] = ("nonexistent", target)
    elif defect == "wrong_casilla":
        replacements[key] = (binding, "nonexistent")
    elif defect == "empty":
        replacements.clear()
    elif defect == "noop":
        after = before
    elif defect == "refs":
        after = after.model_copy(update={"casillas": before.casillas})
    elif defect == "authority":
        after = after.model_copy(update={"bindings": ()})
    else:
        form = before.form_layouts[0]
        update = (
            {"source_state_digest": "0" * 64}
            if defect == "stale"
            else {"review": form.review.model_copy(update={"state": type(form.review.state)("reviewed")})}
        )
        forms = (form.model_copy(update=update),)
        before = before.model_copy(update={"form_layouts": forms})
        after = after.model_copy(update={"form_layouts": forms})
    with pytest.raises(RegistryValidationError):
        reconcile_scalar_export_sources(before, after, replacements=replacements)
