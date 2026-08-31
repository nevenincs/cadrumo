"""Runtime schema provider backed by registry definitions."""

from __future__ import annotations

import pytest

from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.runtime_graph import expression_casilla_refs
from ....domain.filing import ModeloBuilderError
from ..runtime import build_runtime_schema_provider

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_runtime_schema_provider_reads_modelo_130_registry_schema() -> None:
    provider = build_runtime_schema_provider()

    collection = provider.get_collection("130")

    casillas = collection.all()
    assert collection.schema_version.startswith("registry:130:")
    assert casillas
    known_ids = {casilla.casilla_id for casilla in casillas}
    by_id = {casilla.casilla_id: casilla for casilla in casillas}
    snapshot = bundled_authority().snapshot("130", filing_year=2026, period="1T")
    formulas = {formula.id: formula for formula in snapshot.revision.formulas}
    formula_bound = {
        casilla.id: tuple(dict.fromkeys(expression_casilla_refs(formulas[casilla.formula].expression)))
        for casilla in snapshot.revision.casillas
        if casilla.formula is not None
    }
    assert formula_bound
    for casilla_id, expected_inputs in formula_bound.items():
        casilla = by_id[casilla_id]
        assert casilla.formula_input_casilla_ids == expected_inputs
        assert set(expected_inputs) <= known_ids

    subview = provider.get_subview("130")
    assert subview.schema_version == collection.schema_version
    assert subview.revision_id
    assert subview.extraction_profile_ids
    assert subview.verification_expectation_ids
    assert subview.export_layout_ids
    assert subview.application_link_ids
    assert subview.deadline_window_ids


def test_runtime_schema_provider_rejects_unknown_modelo() -> None:
    provider = build_runtime_schema_provider()

    # Assert the translated key rather than English prose: these refusals are
    # localized, so matching the rendered sentence tracks the catalogue's wording
    # instead of the contract and drifts the moment a message is reworded.
    with pytest.raises(ModeloBuilderError) as collection_error:
        provider.get_collection("999")
    assert collection_error.value.translated_message == "application.filing.runtime.errors.modelo_not_in_registry"

    with pytest.raises(ModeloBuilderError) as subview_error:
        provider.get_subview("999")
    assert subview_error.value.translated_message == "application.filing.runtime.errors.modelo_not_in_registry"
