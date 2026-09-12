"""Real-registry tests for canonical handoff path classification."""

from __future__ import annotations

import pytest

from .....core.aggregation import BindingSourceKind
from .....core.modelo import Modelo
from ..authority import bundled_authority
from ..binding_selector_utils import selector_as_dict
from ..iva_wallet_carry_targets import is_iva_wallet_owned_relation_target

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_M303_WALLET_REVISIONS = (
    "2022",
    "2023",
    "2024-hasta-08-y-2t",
    "2024-desde-09-y-3t",
    "2025",
    "2026-y-siguientes",
)


def test_iva_wallet_exception_requires_the_exact_relation_coordinate() -> None:
    """Reusing the binding id cannot grant the M303 wallet carve-out."""
    binding_id = "modelo-303-compensacion-pendiente-anteriores"
    relation_id = "modelo-303-rel-self-compensacion-anteriores"

    for revision_id in _M303_WALLET_REVISIONS:
        assert is_iva_wallet_owned_relation_target(
            modelo_id="303",
            revision_id=revision_id,
            relation_id=relation_id,
            target_binding=binding_id,
        )
    assert not is_iva_wallet_owned_relation_target(
        modelo_id="100",
        revision_id="2025",
        relation_id=relation_id,
        target_binding=binding_id,
    )
    assert not is_iva_wallet_owned_relation_target(
        modelo_id="303",
        revision_id="2022",
        relation_id="reused-binding-under-another-relation",
        target_binding=binding_id,
    )


def test_iva_wallet_exception_preserves_direct_local_recurrence_selector() -> None:
    """Every wallet-owned M303 slot keeps its direct prior-period comparison path."""
    modelo = bundled_authority().modelo(Modelo.M303.value)
    binding_id = "modelo-303-compensacion-pendiente-anteriores"

    for revision_id in _M303_WALLET_REVISIONS:
        revision = modelo.revisions[revision_id]
        binding = next(item for item in revision.bindings if item.id == binding_id)
        assert binding.source is BindingSourceKind.PREVIOUS_FILING
        assert selector_as_dict(binding)["source_period_offset_from_target"] == -1
