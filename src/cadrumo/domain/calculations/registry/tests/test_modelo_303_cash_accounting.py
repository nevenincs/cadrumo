"""Committed-registry guards for Modelo 303 criterio-de-caja bindings."""

from __future__ import annotations

import pytest

from .....core.aggregation import BindingSourceKind
from cadrumo.domain.calculations.registry.schema_input_kind import InputKind
from cadrumo.domain.calculations.registry.binding_selector_utils import selector_as_dict
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_CASH_BINDINGS = {
    "62": ("modelo-303-criterio-caja-entregas-art75-base", ("taxpayer_regime",)),
    "63": ("modelo-303-criterio-caja-entregas-art75-cuota", ("taxpayer_regime",)),
    "74": ("modelo-303-criterio-caja-adquisiciones-base", ("taxpayer_regime", "supplier_regime")),
    "75": ("modelo-303-criterio-caja-adquisiciones-cuota", ("taxpayer_regime", "supplier_regime")),
}


@pytest.mark.parametrize(
    "revision_id",
    [
        "2022",
        "2023",
        "2024-hasta-08-y-2t",
        "2024-desde-09-y-3t",
        "2025",
        "2026-y-siguientes",
    ],
)
def test_modelo_303_cash_accounting_casillas_are_bound_as_a_four_box_set(revision_id: str) -> None:
    modelo, _catalogues = _committed_modelo("303")
    revision = modelo.revisions[revision_id]
    casillas = {casilla.id: casilla for casilla in revision.casillas}
    bindings = {binding.id: binding for binding in revision.bindings}

    for casilla_id, (binding_id, cash_treatments) in _CASH_BINDINGS.items():
        casilla = casillas[casilla_id]
        assert casilla.input_kind is InputKind.BOUND
        assert casilla.binding == binding_id
        assert binding_id in bindings
        binding = bindings[binding_id]
        assert binding.source == BindingSourceKind.LEDGER_IVA_AGGREGATION
        selector = selector_as_dict(binding)
        treatments = selector.get("cash_accounting_treatments")
        assert isinstance(treatments, tuple)
        assert all(isinstance(treatment, str) for treatment in treatments)
        assert treatments == cash_treatments
        assert "none" not in treatments

    assert "ley-37-1992:art-75" in casillas["62"].legal_refs
    assert "ley-37-1992:art-163-terdecies" in casillas["63"].legal_refs
    assert "ley-37-1992:art-163-quinquiesdecies" in casillas["75"].legal_refs
