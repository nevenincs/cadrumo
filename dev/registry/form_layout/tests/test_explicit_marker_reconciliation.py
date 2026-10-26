"""An explicit activity fact replaces only its old computed export owner."""

from pathlib import Path

import pytest

from cadrumo.domain.calculations.export_field_kind import CasillaFieldKind
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.export_field_casilla import derive_casilla_export_refs
from cadrumo.domain.calculations.registry.export_semantics import ExportComputedKey

from ...compiler.form_layout_integrity import form_layout_failures, form_layout_source_digest
from ...compiler.loader import load_modelo_directory
from ..reconciliation import reconcile_unreferenced_export_producers

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _field_owner(revision, **updates):
    layouts = tuple(
        layout.model_copy(
            update={
                "records": tuple(
                    record.model_copy(
                        update={
                            "fields": tuple(
                                field.model_copy(update=updates) if field.id == "modelo-322-page-02-338" else field
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
    refs = derive_casilla_export_refs(layouts, revision.bindings)
    return revision.model_copy(
        update={
            "export_layouts": layouts,
            "casillas": tuple(
                c.model_copy(update={"export_refs": tuple(refs.get(c.id, ()))}) for c in revision.casillas
            ),
        }
    )


@pytest.fixture
def before():
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/322")).revisions["2026-y-siguientes"]
    revision = _field_owner(
        revision,
        kind=CasillaFieldKind.COMPUTED,
        casilla_id=None,
        computed_key=ExportComputedKey("m303_no_activity_marker"),
    )
    layout = revision.form_layouts[0].model_copy(update={"source_state_digest": form_layout_source_digest(revision)})
    return revision.model_copy(update={"form_layouts": (layout,)})


def test_explicit_marker_preserves_the_complete_presentation(before):
    after = _field_owner(before, kind=CasillaFieldKind.CASILLA, casilla_id="decl.sin-actividad", computed_key=None)
    reconciled = reconcile_unreferenced_export_producers(before, after)
    assert reconciled.model_dump(exclude={"source_state_digest"}) == before.form_layouts[0].model_dump(
        exclude={"source_state_digest"}
    )
    assert not form_layout_failures(after.model_copy(update={"form_layouts": (reconciled,)}))


@pytest.mark.parametrize(
    "changes", [{"offset": 339}, {"length": 2}, {"required": True}, {"casilla_id": "70"}, {"source_refs": ()}]
)
def test_marker_rebinding_cannot_hide_geometry_or_semantic_changes(before, changes):
    updates = dict(kind=CasillaFieldKind.CASILLA, casilla_id="decl.sin-actividad", computed_key=None)
    updates.update(changes)
    after = _field_owner(before, **updates)
    with pytest.raises(RegistryValidationError):
        reconcile_unreferenced_export_producers(before, after)
