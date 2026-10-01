"""A sheet-qualified casilla binding names the casilla printed on the field's own sheet.

Modelo 200 prints the same box number on several sheets, so its casilla ids are
qualified by sheet (``DP200010:00399``) and a number is an identity only with
its sheet. A field bound to the right number on another sheet addresses a
different concept, and nothing downstream can tell: the value is written into
the slot of whichever casilla the number happened to resolve to.

Every generated field bound to a sheet-qualified casilla must therefore bind
one on its own anchor sheet or an independently evidenced echo of another
sheet's amount. A missing own-sheet declaration does not authorize an
unexplained cross-sheet binding.
"""

from __future__ import annotations

from collections.abc import Iterable

import pytest

from cadrumo.core.resources.bundled_data import bundled_path

from ..compiler.authority import compiled_bundled_authority
from ..conformance.modelo_200_echoes import MODELO_200_ECHO_CELLS
from ..pipeline.render_check import revision_render_inputs

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def wrong_sheet_bindings(
    bindings: Iterable[tuple[str, str, str]],
    declared_casillas: frozenset[str],
    *,
    declared_echoes: frozenset[tuple[str, str]] = frozenset(),
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
        if (anchor_sheet.upper(), casilla_id) in declared_echoes:
            continue
        target = f"{anchor_sheet}:{number}"
        (rebindable if target in declared_casillas else unrebindable).append(f"{field_id} -> {casilla_id}")
    return rebindable, unrebindable


def _generated_bindings() -> dict[str, tuple[list[str], list[str]]]:
    authority = compiled_bundled_authority()
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
            echoes = MODELO_200_ECHO_CELLS if str(modelo.id) == "200" else frozenset()
            rebindable, unrebindable = wrong_sheet_bindings(bindings, declared, declared_echoes=echoes)
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


def test_no_generated_field_uses_an_unexplained_cross_sheet_binding(generated_bindings) -> None:
    unexplained = [f"{subject}: {row}" for subject, (_, rows) in generated_bindings.items() for row in rows]
    assert not unexplained, "missing own-sheet declarations do not establish a shared concept:\n" + "\n".join(
        unexplained
    )


def test_an_evidenced_applied_total_echo_is_allowed_without_widening_other_bindings() -> None:
    """Only the named echo may share an amount; another sheet's same number remains a defect."""
    bindings = [
        ("applied-total", "DP200016", "DP200014:00573"),
        ("different-concept", "DP200042", "DP200014:00573"),
    ]
    rebindable, unexplained = wrong_sheet_bindings(
        bindings, frozenset({"DP200014:00573"}), declared_echoes=MODELO_200_ECHO_CELLS
    )
    assert not rebindable
    assert unexplained == ["different-concept -> DP200014:00573"]


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
