"""Every declared row-field binding is emitted once per source row.

A binding whose selector is ``fact = "row_field"`` declares ONE export row per
source row, and the renderer addresses its values by row index. Two shapes let
a modelo emit exactly one row where its diseño prescribes one per socio, per
perceptor, per contraparte or per operation:

* unreachable - no export field reaches any of the revision's row bindings and
  no record repeats binding rows, so every row is silently dropped;
* not repeated - a record carries ``kind = "binding"`` fields over row bindings
  without declaring ``repeat = "binding_rows"``. A record without that repeat
  renders once with no row index, so its row-binding fields never resolve a
  value and the file carries one blank occurrence instead of one per row.

A revision with NO export layout records cannot consume anything. Modelo 100's
2025 layout has zero records and its row bindings feed the inventory casillas
0177, 0181 and 0182 rather than export rows, so requiring consumption there
would assert a structure the revision does not have.

Known-defective revisions are ENROLLED below with a stated reason rather than
excluded silently, so fixing one reds this test until its entry is removed.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Final, Literal

import pytest

from ..schema import ModeloRevision
from ..schema_exports import ExportRecordRepeat
from .registry_tree import bundled_modelo_components, bundled_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

RowBindingDefect = Literal["unreachable", "not_repeated"]

#: (modelo, revision) -> why its row bindings are currently not emitted per row.
#: An entry is a defect awaiting repair, never a permanent exemption.
_ROW_BINDING_DEFECTS: Final[dict[tuple[str, str], str]] = {}


def _row_binding_ids(revision: ModeloRevision) -> frozenset[str]:
    return frozenset(
        str(binding.id) for binding in revision.bindings if getattr(binding.provider, "fact", None) == "row_field"
    )


def _row_binding_defect(revision: ModeloRevision) -> RowBindingDefect | None:
    """Classify how one revision fails to emit its row bindings once per row, if it does."""
    row_binding_ids = _row_binding_ids(revision)
    records = [record for layout in revision.export_layouts for record in layout.records]
    if not row_binding_ids or not records:
        return None
    reaching = [record for record in records if any(str(field.binding) in row_binding_ids for field in record.fields)]
    if any(record.repeat != ExportRecordRepeat.BINDING_ROWS for record in reaching):
        return "not_repeated"
    if not reaching and not any(record.repeat == ExportRecordRepeat.BINDING_ROWS for record in records):
        return "unreachable"
    return None


def _row_binding_defects(
    revisions: Iterable[tuple[str, str, ModeloRevision]],
) -> dict[tuple[str, str], RowBindingDefect]:
    """Return every revision whose row bindings are not emitted once per row."""
    return {
        (modelo_id, revision_id): defect
        for modelo_id, revision_id, revision in revisions
        if (defect := _row_binding_defect(revision)) is not None
    }


def _published_revisions() -> Iterator[tuple[str, str, ModeloRevision]]:
    for modelo in bundled_registry_tree()[0]:
        for revision_id, revision in modelo.revisions.items():
            yield str(modelo.id), str(revision_id), revision


def test_every_declared_row_binding_is_emitted_per_row() -> None:
    """No revision may declare row bindings its own layout cannot emit once per row."""
    defects = _row_binding_defects(_published_revisions())
    undeclared = sorted((key, defect) for key, defect in defects.items() if key not in _ROW_BINDING_DEFECTS)

    assert not undeclared, (
        "these revisions declare row-field bindings their export layout does not emit once per "
        "source row, so each files ONE row where its diseno prescribes one per source row:\n  "
        + "\n  ".join(f"modelo {modelo} revision {revision}: {defect}" for (modelo, revision), defect in undeclared)
        + "\nunreachable: carry the row bindings in a repeat='binding_rows' record. not_repeated: "
        "declare repeat='binding_rows' on the record whose binding fields read them. If a revision "
        "legitimately cannot, enroll it in _ROW_BINDING_DEFECTS with the diseno reading that justifies it."
    )


def test_every_enrolled_defect_is_still_present() -> None:
    """A repaired revision must red this test so its enrollment is removed.

    Without this the dict would quietly outlive the defects it records, and the
    gate above would keep excusing revisions that no longer need excusing.
    """
    defects = _row_binding_defects(_published_revisions())
    repaired = sorted(key for key in _ROW_BINDING_DEFECTS if key not in defects)

    assert not repaired, (
        "these revisions now emit their row bindings per row and must be removed from "
        "_ROW_BINDING_DEFECTS:\n  "
        + "\n  ".join(f"modelo {modelo} revision {revision}" for modelo, revision in repaired)
    )


def _control_revision(modelo_id: str, revision_id: str) -> ModeloRevision:
    revision = bundled_modelo_components(modelo_id)[0].revisions[revision_id]
    assert _row_binding_ids(revision), (
        f"modelo {modelo_id} {revision_id} must declare row bindings for this control to mean anything"
    )
    return revision


@pytest.mark.parametrize(("modelo_id", "revision_id"), [("347", "2011-2024")])
def test_a_repeating_revision_is_present_in_the_corpus(modelo_id: str, revision_id: str) -> None:
    """The control: a revision that declares row bindings and repeats their record really occurs here.

    Without this the check above could pass by never encountering a consuming
    revision at all. Modelo 347 consumes through repeat='binding_rows'.
    """
    assert _row_binding_defect(_control_revision(modelo_id, revision_id)) is None


@pytest.mark.parametrize(("modelo_id", "revision_id"), [("347", "2011-2024")])
def test_a_row_binding_record_without_its_repeat_is_detected(modelo_id: str, revision_id: str) -> None:
    """Teeth: the control with its repeat withdrawn is reported as not repeated.

    The input is a private copy of the published revision in which only the
    repeat of the records reading row bindings changes, so the verdict can only
    come from the repeat policy.
    """
    revision = _control_revision(modelo_id, revision_id)
    row_binding_ids = _row_binding_ids(revision)
    layouts = tuple(
        layout.model_copy(
            update={
                "records": tuple(
                    record.model_copy(update={"repeat": None})
                    if any(str(field.binding) in row_binding_ids for field in record.fields)
                    else record
                    for record in layout.records
                ),
            },
        )
        for layout in revision.export_layouts
    )
    assert layouts != revision.export_layouts, "the control must carry a record whose repeat can be withdrawn"
    without_repeat = revision.model_copy(update={"export_layouts": layouts})

    assert _row_binding_defects([(modelo_id, revision_id, without_repeat)]) == {
        (modelo_id, revision_id): "not_repeated"
    }


@pytest.mark.parametrize(("modelo_id", "revision_id"), [("347", "2011-2024")])
def test_a_layout_reaching_no_row_binding_is_detected(modelo_id: str, revision_id: str) -> None:
    """Teeth: the control with every row-binding record removed is reported as unreachable."""
    revision = _control_revision(modelo_id, revision_id)
    row_binding_ids = _row_binding_ids(revision)
    layouts = tuple(
        layout.model_copy(
            update={
                "records": tuple(
                    record
                    for record in layout.records
                    if record.repeat != ExportRecordRepeat.BINDING_ROWS
                    and not any(str(field.binding) in row_binding_ids for field in record.fields)
                ),
            },
        )
        for layout in revision.export_layouts
    )
    assert any(layout.records for layout in layouts), "the control must keep a record outside the row binding"
    unreachable = revision.model_copy(update={"export_layouts": layouts})

    assert _row_binding_defects([(modelo_id, revision_id, unreachable)]) == {(modelo_id, revision_id): "unreachable"}
