"""The prior-return boxes a Modelo 100 opens its savings carries from."""

from __future__ import annotations

from cadrumo.core.casilla_id import CasillaId
from cadrumo.domain.calculations.registry.bindings import binding_source_casilla_ids
from cadrumo.domain.calculations.registry.schema import BindingDefinition
from cadrumo.domain.calculations.registry.tests.published_authority import (
    published_snapshot,
    published_supported_filing_years,
)

_SAVINGS_CARRY_PREFIX = "renta-saldo-negativo-"
_SAVINGS_CARRY_SUFFIX = "-pendiente-inicio"


def _savings_carry_bindings() -> tuple[BindingDefinition, ...]:
    """The previous-filing bindings of the negative savings balances (LIRPF art. 49), read from the newest edition."""
    support = published_supported_filing_years()
    assert support is not None
    revision = published_snapshot("100", filing_year=support.horizon, period="0A").revision
    return tuple(
        binding
        for binding in revision.bindings
        if binding.provider.kind == "previous_filing"
        and binding.id.startswith(_SAVINGS_CARRY_PREFIX)
        and binding.id.endswith(_SAVINGS_CARRY_SUFFIX)
    )


def prior_savings_remainder_bindings() -> tuple[str, ...]:
    """The savings carries a Modelo 100 reads from the previous return."""
    return tuple(binding.id for binding in _savings_carry_bindings())


def prior_savings_remainder_boxes() -> tuple[CasillaId, ...]:
    """The previous-return boxes those carries open from, read from the bindings themselves."""
    return tuple(
        casilla_id for binding in _savings_carry_bindings() for casilla_id in binding_source_casilla_ids(binding)
    )
