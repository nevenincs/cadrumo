"""Authored presentation survives only an exact source-bound field subdivision."""

from pathlib import Path

import pytest

from cadrumo.domain.calculations.export_field_kind import CasillaFieldKind
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.export_field_casilla import (
    derive_casilla_export_refs,
    export_field_casilla_id,
)

from ...compiler.form_layout_integrity import form_layout_failures, form_layout_source_digest
from ...compiler.loader import load_modelo_directory, load_shared_catalogues
from ...pipeline._export_tree import render_complete_export_tree
from ...pipeline.render_check import _revision_render_inputs
from ..reconciliation import reconcile_export_casilla_splits
from ._member_scalar_history import scalar_member_history

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _with_exports(revision, layouts):
    refs = derive_casilla_export_refs(layouts, revision.bindings)
    return revision.model_copy(
        update={
            "export_layouts": layouts,
            "casillas": tuple(
                c.model_copy(update={"export_refs": tuple(refs.get(c.id, ()))}) for c in revision.casillas
            ),
        }
    )


@pytest.fixture(scope="module")
def pair(tmp_path_factory):
    root = Path("src/cadrumo/_data")
    modelo = load_modelo_directory(root / "registry/aeat/modelos/156")
    revision = scalar_member_history(modelo.revisions["2003-y-siguientes"])
    inputs = _revision_render_inputs(
        modelo,
        load_shared_catalogues(root / "registry/aeat"),
        modelo="156",
        revision=str(revision.id),
        source_ref="enrolled-modelo-156-layout",
        bootstrap_transport=None,
        filing_year=2025,
        period="0A",
        source_root=root,
    )
    layout = render_complete_export_tree(
        tmp_path_factory.mktemp("split") / "export",
        revision_id=str(revision.id),
        joined=inputs.joined,
        semantic_map=inputs.semantic_map,
        transport_profile=inputs.transport_profile,
        render_profile=inputs.render_profile,
        render_profile_source_evidence=inputs.render_profile_source_evidence,
    ).layout
    header, member = layout.records
    # Reconstruct the scalar calendar boundary even after row enrollment.
    # Its positions still come from the freshly rendered official design.
    bindings = {b.id: b for b in revision.bindings}
    member = member.model_copy(
        update={
            "fields": tuple(
                field.model_copy(
                    update={
                        "kind": CasillaFieldKind.CASILLA,
                        "casilla_id": export_field_casilla_id(member, field, bindings=bindings),
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
    # Reconstruct the previous opaque nine-byte representation independently,
    # so these checks remain meaningful after the corrected export is installed.
    fields = []
    for field in member.fields:
        assert field.offset is not None
        if 88 <= field.offset <= 195:
            if field.length == 1:
                continue
            field = field.model_copy(
                update={
                    "offset": field.offset - 1,
                    "length": 9,
                    "data_type": "text",
                    "padding": type(field.padding)("right_space"),
                    "justification": type(field.justification)("left"),
                    "decimals": None,
                    "value_policy": None,
                }
            )
        fields.append(field)
    old_layout = layout.model_copy(update={"records": (header, member.model_copy(update={"fields": tuple(fields)}))})
    before = _with_exports(revision, (old_layout,))
    form = before.form_layouts[0].model_copy(update={"source_state_digest": form_layout_source_digest(before)})
    before = before.model_copy(update={"form_layouts": (form,)})
    return before, _with_exports(before, (layout,))


def test_calendar_and_context_survive_exact_subdivision(pair):
    before, after = pair
    result = reconcile_export_casilla_splits(before, after)
    assert result.model_dump(exclude={"source_state_digest"}) == before.form_layouts[0].model_dump(
        exclude={"source_state_digest"}
    )
    assert not form_layout_failures(after.model_copy(update={"form_layouts": (result,)}))


@pytest.mark.parametrize(
    "changes",
    [
        {"offset": 90},
        {"length": 7},
        {"length": 9},
        {"source_refs": ()},
        {"legal_refs": ()},
        {"kind": "header"},
    ],
)
def test_refuses_gaps_overlap_or_ungrounded_parts(pair, changes):
    before, after = pair
    if "kind" in changes:
        changes = {**changes, "kind": type(after.export_layouts[0].records[1].fields[0].kind)(changes["kind"])}
    layout = after.export_layouts[0]
    header, member = layout.records
    member = member.model_copy(
        update={"fields": tuple(f.model_copy(update=changes) if f.offset == 89 else f for f in member.fields)}
    )
    broken = after.model_copy(update={"export_layouts": (layout.model_copy(update={"records": (header, member)}),)})
    with pytest.raises(RegistryValidationError):
        reconcile_export_casilla_splits(before, broken)


def test_refuses_changed_calculation_or_presentation(pair):
    before, after = pair
    changed = after.casillas[0].model_copy(update={"required": not after.casillas[0].required})
    with pytest.raises(RegistryValidationError):
        reconcile_export_casilla_splits(before, after.model_copy(update={"casillas": (changed, *after.casillas[1:])}))
    with pytest.raises(RegistryValidationError):
        reconcile_export_casilla_splits(before, after.model_copy(update={"form_layouts": ()}))


def test_refuses_stale_or_unchanged_source(pair):
    before, after = pair
    with pytest.raises(RegistryValidationError):
        reconcile_export_casilla_splits(before, before)
    stale = before.model_copy(
        update={"form_layouts": (before.form_layouts[0].model_copy(update={"source_state_digest": "0" * 64}),)}
    )
    with pytest.raises(RegistryValidationError):
        reconcile_export_casilla_splits(stale, after.model_copy(update={"form_layouts": stale.form_layouts}))


def test_refuses_unrelated_header_or_record_changes(pair):
    before, after = pair
    layout = after.export_layouts[0]
    header, member = layout.records
    field = header.fields[0].model_copy(update={"required": not header.fields[0].required})
    header = header.model_copy(update={"fields": (field, *header.fields[1:])})
    changed = after.model_copy(update={"export_layouts": (layout.model_copy(update={"records": (header, member)}),)})
    with pytest.raises(RegistryValidationError):
        reconcile_export_casilla_splits(before, changed)


def test_does_not_carry_human_review_forward(pair):
    before, after = pair
    form = before.form_layouts[0]
    review = form.review.model_copy(update={"state": type(form.review.state)("reviewed")})
    reviewed = form.model_copy(update={"review": review})
    with pytest.raises(RegistryValidationError, match="unreviewed"):
        reconcile_export_casilla_splits(
            before.model_copy(update={"form_layouts": (reviewed,)}),
            after.model_copy(update={"form_layouts": (reviewed,)}),
        )
