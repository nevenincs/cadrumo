"""Tests for the committed Modelo 187/188/194 registry foundations.

See Also:
    :func:`~domain.calculations.registry.tests._registry_schema_support._committed_modelo`
        Bundled-registry loader used to validate the promoted definitions.
    :func:`~domain.calculations.registry.tests._registry_schema_support._committed_snapshot`
        Snapshot fixture used for committed-form arithmetic tests.
    :class:`~domain.calculations.registry.RegistryValidator`
        Registry integrity gate proving each promoted TOML tree is loadable.
    :func:`~domain.calculations.registry.calculate_registry_snapshot`
        Formula runtime entry point used for official form arithmetic.
    :class:`~domain.calculations.registry.ModeloRevision`
        Registry revision carrier whose construct-owned formulas are asserted.
    :class:`~domain.calculations.registry.CasillaId`
        Typed casilla identifier used for the copied-total assertion.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core import CasillaId, validated_casilla_id
from .....core.resources import bundled_path
from .._formula_runtime import calculate_registry_snapshot
from .._validate import RegistryValidator
from ._registry_schema_support import _committed_modelo, _committed_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELOS = ("187", "188", "194")
_SOURCE_CASILLA: CasillaId = validated_casilla_id("04", surface="_SOURCE_CASILLA")
_TARGET_CASILLA: CasillaId = validated_casilla_id("05", surface="_TARGET_CASILLA")


@pytest.mark.parametrize("modelo_id", _MODELOS)
def test_modelo_187_188_194_validators_accept_committed_definitions(modelo_id: str) -> None:
    modelo, catalogues = _committed_modelo(modelo_id)
    assert modelo.id == modelo_id
    assert modelo.revisions, f"{modelo_id} must declare at least one revision"
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)


@pytest.mark.parametrize("modelo_id", _MODELOS)
def test_modelo_187_188_194_formulas_are_owned_by_constructs(modelo_id: str) -> None:
    modelo, _ = _committed_modelo(modelo_id)
    revision = modelo.revisions["2019-y-siguientes"]
    owned = set().union(*(set(construct.formulas) for construct in revision.constructs))
    assert f"modelo-{modelo_id}-total" in owned


@pytest.mark.parametrize("modelo_id", _MODELOS)
def test_modelo_187_188_194_totals_copy_source_casilla(modelo_id: str) -> None:
    """Casilla 05 equals casilla 04 per each AEAT form's own printed total row."""
    snapshot = _committed_snapshot(modelo_id, 2019, "0A")
    result = calculate_registry_snapshot(
        snapshot,
        inputs={_SOURCE_CASILLA: Decimal("500.00")},
        date_context={"filing_period": date(2019, 12, 31)},
        m303_regimen_simplificado_scope=None,
        m303_annual_orden=None,
    )
    assert result.values[_TARGET_CASILLA] == Decimal("500.00")
