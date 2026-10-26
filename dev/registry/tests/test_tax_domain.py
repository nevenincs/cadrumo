"""Tests for syntax-only tax-domain hydration at the registry schema boundary."""

from __future__ import annotations

import pytest

from cadrumo.core.errors.hierarchy import CoreValidationError
from cadrumo.core.tax_domain import TaxDomain
from cadrumo.domain.calculations.registry.schema import ModeloDefinition

from ..conformance.registry_schema_support import committed_registry_tree as _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _load_modelos() -> tuple[ModeloDefinition, ...]:
    modelos, _ = _committed_registry_tree()
    return modelos


def test_loaded_modelo_tax_domain_is_typed_value_not_bare_string() -> None:
    """The registry loader hydrates tax_domain to the distinct value type."""
    iva_modelo = next(m for m in _load_modelos() if m.id == "303")
    assert isinstance(iva_modelo.tax_domain, TaxDomain)
    assert iva_modelo.tax_domain == TaxDomain("iva")


def test_every_committed_modelo_carries_a_syntax_valid_tax_domain() -> None:
    """Every committed TOML manifest hydrates to a syntax-valid tax domain."""
    for modelo in _load_modelos():
        assert isinstance(modelo.tax_domain, TaxDomain), (
            f"modelo {modelo.id} carries an untyped tax_domain {modelo.tax_domain!r}"
        )


def test_well_formed_unpublished_tax_domain_is_accepted_by_syntax_constructor() -> None:
    """Construction does not duplicate the authority-owned membership catalogue."""
    assert TaxDomain("not_a_real_domain") == "not_a_real_domain"


def test_malformed_tax_domain_is_rejected_at_syntax_construction() -> None:
    """Stable lexical constraints remain enforced without consulting authority."""
    with pytest.raises(CoreValidationError):
        TaxDomain("not-a-domain")


def test_every_committed_tax_domain_value_round_trips_through_str() -> None:
    """Every loaded value str-roundtrips by value and retains its type."""
    seen = {modelo.tax_domain for modelo in _load_modelos()}
    assert seen, "registry must contain at least one modelo"
    for value in seen:
        round_tripped = TaxDomain(str(value))
        assert round_tripped == value
        assert isinstance(round_tripped, TaxDomain)
