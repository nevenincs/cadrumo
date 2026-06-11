"""Tests for tax_domain enum hydration at the registry schema boundary."""

from __future__ import annotations

from functools import lru_cache

import pytest

from .....core import TaxDomain
from .....core.resources import bundled_path
from .. import load_registry_tree
from .._schema import ModeloDefinition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@lru_cache(maxsize=1)
def _load_modelos() -> tuple[ModeloDefinition, ...]:
    modelos, _ = load_registry_tree(bundled_path("registry", "aeat"))
    return modelos


def test_loaded_modelo_tax_domain_is_typed_enum_not_bare_string() -> None:
    """The registry loader hydrates tax_domain to the closed TaxDomain enum."""
    iva_modelo = next(m for m in _load_modelos() if m.id == "303")
    assert isinstance(iva_modelo.tax_domain, TaxDomain)
    assert iva_modelo.tax_domain is TaxDomain.IVA


def test_every_committed_modelo_carries_a_recognised_tax_domain() -> None:
    """Every committed TOML manifest declares a recognised tax_domain."""
    for modelo in _load_modelos():
        assert isinstance(modelo.tax_domain, TaxDomain), (
            f"modelo {modelo.id} carries non-enum tax_domain {modelo.tax_domain!r}"
        )


def test_unknown_tax_domain_string_is_rejected_at_enum_construction() -> None:
    """An unknown value cannot construct a TaxDomain at the hydration boundary."""
    with pytest.raises(ValueError):
        TaxDomain("not_a_real_domain")


def test_every_committed_tax_domain_value_round_trips_through_str() -> None:
    """Every loaded enum member str-roundtrips back to the same enum member."""
    seen = {modelo.tax_domain for modelo in _load_modelos()}
    assert seen, "registry must contain at least one modelo"
    for value in seen:
        assert TaxDomain(str(value)) is value
