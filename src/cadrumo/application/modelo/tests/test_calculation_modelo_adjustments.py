"""Canonical binding-to-casilla use in Modelo-specific calculation adjustments."""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition

from ....core import Modelo
from ....domain.calculations.registry.authority import bundled_authority
from .._calculation_modelo_adjustments import _m390_303_reconciliation_targets

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_TARGET_BINDING = "modelo-390-prev-303-cuota-devengada-total"
_OTHER_BINDING = "modelo-390-prev-303-cuota-deducible-total"
_TARGET_CASILLA = "iva.anual.reconciliacion.devengada-303"
_RELATION = "modelo-390-rel-303-cuota-devengada-total"


def test_m390_reconciliation_target_reaches_a_binding_declared_only_as_an_alternate() -> None:
    """The adjustment consumes the canonical reverse join, including alternates."""
    snapshot = bundled_authority().snapshot(Modelo.M390.value, filing_year=2025, period="0A")
    revised_casillas = tuple(
        CasillaDefinition.model_validate(
            {
                **casilla.model_dump(),
                "localization_keys": casilla.localization_keys,
                "binding": _OTHER_BINDING,
                "alternate_bindings": (_TARGET_BINDING,),
            },
        )
        if casilla.id == _TARGET_CASILLA
        else casilla
        for casilla in snapshot.revision.casillas
    )
    revised_snapshot = snapshot.model_copy(
        update={"revision": snapshot.revision.model_copy(update={"casillas": revised_casillas})},
    )

    relation_targets = _m390_303_reconciliation_targets(revised_snapshot)
    target = next(row for row in relation_targets if row[0] == _RELATION)

    assert target[1] == _TARGET_BINDING
    assert target[2] == (_TARGET_CASILLA,)
