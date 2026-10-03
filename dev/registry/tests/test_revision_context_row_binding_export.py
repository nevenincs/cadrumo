"""A repeated row binding is an exported casilla only through its exact selector."""

from __future__ import annotations

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.export import (
    derive_export_layouts_from_bindings,
    row_binding_casilla_ids_by_field,
)
from cadrumo.domain.calculations.registry.revision_context import _exported_casilla_ids

from ..compiler.loader import load_modelo_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.mark.parametrize("revision_id", ["2019-2022", "2023-y-siguientes"])
def test_m180_repeated_binding_targets_are_exported_casillas(revision_id: str) -> None:
    """The same 27 source-backed recipient casillas remain visible after binding derivation."""
    modelo = load_modelo_directory(bundled_path("registry", "aeat", "modelos", "180"))
    revision = modelo.revisions[revision_id]
    derived = derive_export_layouts_from_bindings(revision)[0]
    bound = row_binding_casilla_ids_by_field(revision, derived)
    candidate = revision.model_copy(update={"export_layouts": (derived,)})

    assert len(set(bound.values())) == 27
    assert set(bound.values()) <= _exported_casilla_ids(candidate)


def test_unresolved_row_binding_does_not_claim_an_exported_casilla() -> None:
    """An unrelated binding ID cannot provide extraction-profile coverage."""
    modelo = load_modelo_directory(bundled_path("registry", "aeat", "modelos", "180"))
    revision = modelo.revisions["2019-2022"]
    derived = derive_export_layouts_from_bindings(revision)[0]
    row_casillas = row_binding_casilla_ids_by_field(revision, derived)
    target = next(casilla for casilla in row_casillas.values() if str(casilla) == "perc.ejercicio-devengo")
    records = []
    for record in derived.records:
        fields = tuple(
            field.model_copy(update={"binding": "missing-unrelated-binding"})
            if row_casillas.get(field.id) == target
            else field
            for field in record.fields
        )
        records.append(record.model_copy(update={"fields": fields}))
    broken_layout = derived.model_copy(update={"records": tuple(records)})
    broken_revision = revision.model_copy(update={"export_layouts": (broken_layout,)})

    assert target not in _exported_casilla_ids(broken_revision)
