"""The clave letters a binding selects and a producer yields are the ones the registry declares."""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.application.aggregation.counterpart import counterpart_operation_catalogue_entries
from cadrumo.core.aggregation import IntracomOperationType
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.invoice_bindings import (
    CollectibleInvoiceProvider,
    M347ThirdPartyOperationProvider,
    M349IntracommunityOperationProvider,
    PayableInvoiceProvider,
)
from cadrumo.domain.calculations.registry.tests.published_authority import bundled_indexed_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_VOCABULARY_KEYS = {
    "347": "modelo.347.operation_claves",
    "349": "modelo.349.operation_claves",
}
_CLAVE_PROVIDERS = (
    CollectibleInvoiceProvider,
    M347ThirdPartyOperationProvider,
    M349IntracommunityOperationProvider,
    PayableInvoiceProvider,
)


def _vocabulary(operation: PinnedAuthorityOperation, modelo: str, effective_date: date) -> frozenset[str]:
    entries = counterpart_operation_catalogue_entries(effective_date, operation=operation)
    return frozenset(entries[_VOCABULARY_KEYS[modelo]].split(","))


def _floor_date(operation: PinnedAuthorityOperation) -> date:
    return date(operation.supported_filing_years().floor, 1, 1)


def test_the_m349_enum_spells_the_declared_vocabulary() -> None:
    with bundled_indexed_authority().operation() as operation:
        declared = _vocabulary(operation, "349", _floor_date(operation))
    assert frozenset(member.value for member in IntracomOperationType) == declared


@pytest.mark.parametrize("modelo", ["347", "349"])
def test_every_published_binding_selects_declared_claves(modelo: str) -> None:
    with bundled_indexed_authority().operation() as operation:
        floor = _floor_date(operation)
        selected: list[str] = []
        for metadata in operation.modelo_directory(modelo).revisions:
            if metadata.valid_to is not None and metadata.valid_to < floor:
                continue
            for binding in operation.revision(modelo, metadata.id).bindings:
                if isinstance(binding.provider, _CLAVE_PROVIDERS):
                    selected += binding.provider.claves
        declared = _vocabulary(operation, modelo, floor)
    assert selected or modelo == "347", "Modelo 347 selects by row field and names no clave in its bindings"
    assert set(selected) <= declared, sorted(set(selected) - declared)


def test_the_two_vocabularies_are_declared_apart() -> None:
    with bundled_indexed_authority().operation() as operation:
        floor = _floor_date(operation)
        assert _vocabulary(operation, "347", floor) != _vocabulary(operation, "349", floor)
