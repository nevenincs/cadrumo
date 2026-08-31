"""Every declared row-field binding is reachable from the export layout.

A binding whose selector is ``fact = "row_field"`` declares ONE export row per
source row. A layout that carries records must therefore consume it, either
through a record with ``repeat = "binding_rows"`` or through explicit
``kind = "binding"`` fields. A row binding no field reaches is declared and
unreachable: the modelo can emit exactly one row where its diseño prescribes
one per socio, per contraparte, or per operation, and every later row is
silently dropped.

Scoped by two preconditions, each of which is a real shape in this tree rather
than a convenience:

* A revision with NO export layout records cannot consume anything. Modelo 100's
  2025 layout has zero records and its row bindings feed the inventory casillas
  0177, 0181 and 0182 rather than export rows, so requiring consumption there
  would assert a structure the revision does not have.
* Consumption does not require a repeat. Modelo 232 declares six row bindings and
  no repeat at all, consuming them through 140 explicit binding fields across two
  records, because its diseño lays operations out as fixed numbered slots. A gate
  demanding ``binding_rows`` specifically would refuse correct content -- an
  earlier draft of this check did exactly that.

Known-defective revisions are ENROLLED below with a stated reason rather than
excluded silently, so fixing one reds this test until its entry is removed.
"""

from __future__ import annotations

from typing import Final

import pytest

from ..authority import bundled_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: (modelo, revision) -> why its row bindings are currently unreachable.
#: An entry is a defect awaiting repair, never a permanent exemption.
_UNCONSUMED_ROW_BINDING_DEFECTS: Final[dict[tuple[str, str], str]] = {
    ("184", "2023-2024"): (
        "19 modelo-184-member-row-* bindings, 0 binding fields on m184-socio. The diseño "
        "prescribes '1 y tantos registros del tipo 2 como claves y subclaves declaradas ... "
        "por cada socio, heredero, comunero o participe', so the shipped layout can declare "
        "ONE socio. Live under-declaration, not a regeneration hazard."
    ),
    ("184", "2025-y-siguientes"): (
        "Same defect as 2023-2024, carried into the successor revision: 19 member-row "
        "bindings against a m184-socio record with no repeat and no binding fields."
    ),
    ("360", "2010-y-siguientes"): (
        "5 modelo-360-refund-row-* bindings, 0 consumed across 235 fields on two page "
        "records. The bundled diseno extract does not settle whether the refund block "
        "repeats or uses fixed slots, so the SHAPE of the repair is open -- but the "
        "bindings are unreachable under either reading."
    ),
}


def _unconsumed_row_bindings() -> dict[tuple[str, str], int]:
    """Return every revision whose layout has records but reaches no row binding."""
    unconsumed: dict[tuple[str, str], int] = {}
    for modelo in bundled_authority().modelos:
        for revision_id, revision in modelo.revisions.items():
            row_bindings = [
                binding
                for binding in revision.bindings
                if getattr(getattr(binding, "selector", None), "fact", None) == "row_field"
            ]
            if not row_bindings:
                continue
            records = [record for layout in revision.export_layouts for record in layout.records]
            if not records:
                continue
            consumed = any(
                record.repeat == "binding_rows"
                or any(field.kind == "binding" for field in record.fields)
                for record in records
            )
            if not consumed:
                unconsumed[(str(modelo.id), str(revision_id))] = len(row_bindings)
    return unconsumed


def test_every_declared_row_binding_is_reachable_from_its_layout() -> None:
    """No revision may declare row bindings its own layout cannot emit."""
    unconsumed = _unconsumed_row_bindings()
    undeclared = sorted(key for key in unconsumed if key not in _UNCONSUMED_ROW_BINDING_DEFECTS)

    assert not undeclared, (
        "these revisions declare row-field bindings that no export field reaches, so each "
        "emits ONE row where its diseno prescribes one per source row and drops the rest:\n  "
        + "\n  ".join(f"modelo {modelo} revision {revision}" for modelo, revision in undeclared)
        + "\nConsume them with a repeat='binding_rows' record or explicit binding fields. "
        "If a revision legitimately cannot, enroll it in _UNCONSUMED_ROW_BINDING_DEFECTS "
        "with the diseno reading that justifies it."
    )


def test_every_enrolled_defect_is_still_unconsumed() -> None:
    """A repaired revision must red this test so its enrollment is removed.

    Without this the dict would quietly outlive the defects it records, and the
    gate above would keep excusing revisions that no longer need excusing.
    """
    unconsumed = _unconsumed_row_bindings()
    repaired = sorted(key for key in _UNCONSUMED_ROW_BINDING_DEFECTS if key not in unconsumed)

    assert not repaired, (
        "these revisions now consume their row bindings and must be removed from "
        "_UNCONSUMED_ROW_BINDING_DEFECTS:\n  "
        + "\n  ".join(f"modelo {modelo} revision {revision}" for modelo, revision in repaired)
    )


@pytest.mark.parametrize(("modelo_id", "revision_id"), [("347", "2011-2024"), ("232", "2018-y-siguientes")])
def test_both_consumption_shapes_are_present_in_the_corpus(modelo_id: str, revision_id: str) -> None:
    """The control: both ways of consuming a row binding really occur here.

    Without this the check above could pass by never encountering a consuming
    revision at all. Modelo 347 consumes through repeat='binding_rows'; modelo
    232 consumes through explicit binding fields and declares no repeat.
    """
    revision = bundled_authority().modelo(modelo_id).revisions[revision_id]
    row_bindings = [
        binding
        for binding in revision.bindings
        if getattr(getattr(binding, "selector", None), "fact", None) == "row_field"
    ]
    assert row_bindings, f"modelo {modelo_id} {revision_id} must declare row bindings for this control to mean anything"
    assert (str(modelo_id), str(revision_id)) not in _unconsumed_row_bindings()
