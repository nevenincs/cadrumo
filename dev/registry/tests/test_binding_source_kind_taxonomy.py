"""Structural contracts for the binding-source taxonomy."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from cadrumo.core.aggregation import (
    COUNTERPART_SOURCE_KINDS,
    INVOICE_BINDING_SOURCE_KINDS,
    LEDGER_BINDING_SOURCE_KINDS,
    BindingSourceKind,
)
from cadrumo.domain.calculations.registry.schema import DataBindingDefinition

from ..conformance.registry_schema_support import committed_registry_tree as _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_compiled_registry_sources_are_typed_enum_members() -> None:
    modelos, _ = _committed_registry_tree()
    assert all(
        isinstance(binding.source, BindingSourceKind)
        for modelo in modelos
        for revision in modelo.revisions.values()
        for binding in revision.bindings
    )


def test_semantic_source_families_are_typed_and_non_overlapping() -> None:
    families = (COUNTERPART_SOURCE_KINDS, INVOICE_BINDING_SOURCE_KINDS, LEDGER_BINDING_SOURCE_KINDS)
    assert all(all(isinstance(source, BindingSourceKind) for source in family) for family in families)
    assert COUNTERPART_SOURCE_KINDS.isdisjoint(LEDGER_BINDING_SOURCE_KINDS)


def test_unknown_source_token_is_refused_by_the_binding_contract() -> None:
    with pytest.raises(ValidationError):
        DataBindingDefinition.model_validate(
            {"id": "unknown-source", "source": "not_a_source", "selector": {"fact": "value"}}
        )


@pytest.mark.parametrize("source", tuple(BindingSourceKind))
def test_each_source_kind_round_trips_through_its_enum(source: BindingSourceKind) -> None:
    assert BindingSourceKind(source.value) is source
