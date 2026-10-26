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
from cadrumo.domain.calculations.registry.schema import BindingDefinition

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


def test_unknown_provider_kind_is_refused_by_the_binding_contract() -> None:
    """An unknown provider ``kind`` is refused on the discriminator, not incidentally.

    The refusal must name the union tag: a payload that is merely malformed would
    raise for a missing sibling field instead, which would prove nothing about the
    taxonomy being closed.
    """
    with pytest.raises(ValidationError) as refused:
        BindingDefinition.model_validate(
            {
                "id": "unknown-provider-kind",
                "provider": {"kind": "not_a_source", "profile_key": "censo.status"},
                "value": {"data_type": "money", "channel": "decimal"},
                "legal_refs": ("rd-1065-2007:art-9",),
                "source_refs": ("aeat-modelo-036-procedure",),
            },
        )

    assert any(error["type"] == "union_tag_invalid" for error in refused.value.errors())


def test_a_declared_provider_kind_is_accepted_by_the_same_contract() -> None:
    """Anti-tautology: the payload above is refused only for its unknown kind."""
    binding = BindingDefinition.model_validate(
        {
            "id": "known-provider-kind",
            "provider": {"kind": "profile", "profile_key": "censo.status"},
            "value": {"data_type": "money", "channel": "decimal"},
            "legal_refs": ("rd-1065-2007:art-9",),
            "source_refs": ("aeat-modelo-036-procedure",),
        },
    )

    assert binding.source is BindingSourceKind.PROFILE


@pytest.mark.parametrize("source", tuple(BindingSourceKind))
def test_each_source_kind_round_trips_through_its_enum(source: BindingSourceKind) -> None:
    assert BindingSourceKind(source.value) is source
