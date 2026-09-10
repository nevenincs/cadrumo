"""A sheet-qualified casilla binding names the casilla printed on the field's own sheet.

Modelo 200 prints the same box number on several sheets, so its casilla ids are
qualified by sheet (``DP200010:00399``) and a number is an identity only with
its sheet. A field bound to the right number on another sheet addresses a
different concept, and nothing downstream can tell: the value is written into
the slot of whichever casilla the number happened to resolve to.

Every generated field bound to a sheet-qualified casilla must therefore bind
one on its own anchor sheet. The exception is a field whose own-sheet casilla
has never been declared: it cannot be rebound until that casilla is authored.
Those are declared below per revision, and each is checked to be genuinely
unrebindable, so an exception whose casilla has since been authored fails and
names the binding to repair.
"""

from __future__ import annotations

from collections.abc import Iterable

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import bundled_authority

from ..pipeline.render_check import revision_render_inputs

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: Wrong-sheet bindings whose own-sheet casilla has not been declared, per
#: revision. Each is waiting on an authored casilla, not on a rebinding.
_UNREBINDABLE_PER_REVISION: dict[str, int] = {"200/2025-y-siguientes": 63}


def wrong_sheet_bindings(
    bindings: Iterable[tuple[str, str, str]], declared_casillas: frozenset[str]
) -> tuple[list[str], list[str]]:
    """Split ``(field_id, anchor_sheet, casilla_id)`` bindings that miss their own sheet.

    Returns ``(rebindable, unrebindable)``: the first bind another sheet although
    the own-sheet casilla exists, the second bind another sheet because it does
    not. A binding whose casilla id carries no sheet qualifier is out of scope.
    """
    rebindable: list[str] = []
    unrebindable: list[str] = []
    for field_id, anchor_sheet, casilla_id in bindings:
        if ":" not in casilla_id:
            continue
        sheet, number = casilla_id.split(":", 1)
        if sheet.upper() == anchor_sheet.upper():
            continue
        target = f"{anchor_sheet}:{number}"
        (rebindable if target in declared_casillas else unrebindable).append(f"{field_id} -> {casilla_id}")
    return rebindable, unrebindable


def _generated_bindings() -> dict[str, tuple[list[str], list[str]]]:
    authority = bundled_authority()
    found: dict[str, tuple[list[str], list[str]]] = {}
    for modelo in sorted(authority.modelos, key=lambda item: str(item.id)):
        for revision in sorted(modelo.revisions.values(), key=lambda item: str(item.id)):
            export_root = bundled_path(
                "registry", "aeat", "modelos", str(modelo.id), "revisions", str(revision.id), "export"
            )
            if not (export_root / "_generation.provenance.json").is_file():
                continue
            inputs = revision_render_inputs(authority, modelo=str(modelo.id), revision=str(revision.id))
            bindings = [
                (
                    str(field.semantic_entry.export_field_id),
                    (field.parser_field.sheet or "").strip(),
                    str(field.semantic_entry.casilla_id),
                )
                for field in inputs.joined.fields
                if field.semantic_entry.casilla_id is not None
            ]
            declared = frozenset(str(casilla.id) for casilla in revision.casillas)
            rebindable, unrebindable = wrong_sheet_bindings(bindings, declared)
            if rebindable or unrebindable:
                found[f"{modelo.id}/{revision.id}"] = (rebindable, unrebindable)
    return found


@pytest.fixture(scope="module")
def generated_bindings() -> dict[str, tuple[list[str], list[str]]]:
    return _generated_bindings()


def test_no_generated_field_binds_another_sheet_while_its_own_casilla_exists(generated_bindings) -> None:
    rebindable = [row for rows, _unrebindable in generated_bindings.values() for row in rows]
    assert not rebindable, "fields bound to another sheet although their own-sheet casilla exists:\n" + "\n".join(
        rebindable[:40]
    )


def test_unrebindable_bindings_are_exactly_the_declared_ones(generated_bindings) -> None:
    live = {subject: len(unrebindable) for subject, (_rebindable, unrebindable) in generated_bindings.items()}
    assert {subject: count for subject, count in live.items() if count} == _UNREBINDABLE_PER_REVISION


def test_a_planted_wrong_sheet_binding_is_caught_and_classified() -> None:
    """The split distinguishes a repairable binding from one waiting on an authored casilla."""
    declared = frozenset({"DP200010:00399", "DP200014B:00399"})
    bindings = [
        ("own-sheet", "DP200010", "DP200010:00399"),
        ("repairable", "DP200010", "DP200014B:00399"),
        ("waiting", "DP200042", "DP200014B:00399"),
        ("unqualified", "DP200042", "00399"),
    ]

    rebindable, unrebindable = wrong_sheet_bindings(bindings, declared)

    assert rebindable == ["repairable -> DP200014B:00399"]
    assert unrebindable == ["waiting -> DP200014B:00399"]
