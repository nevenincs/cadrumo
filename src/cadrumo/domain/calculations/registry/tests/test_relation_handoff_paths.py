"""Real-registry tests for canonical handoff path classification."""

from __future__ import annotations

import pytest

from .....core.modelo import Modelo
from .....core.aggregation import BindingSourceKind
from ..authority import bundled_authority
from ..binding_selector_utils import selector_as_dict
from ..handoffs import audit_registry_handoff_paths
from ..iva_wallet_relation_targets import is_iva_wallet_owned_relation_target

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_M303_WALLET_REVISIONS = (
    "2022",
    "2023",
    "2024-hasta-08-y-2t",
    "2024-desde-09-y-3t",
    "2025",
    "2026-y-siguientes",
)


def test_bundled_handoff_paths_have_one_owner_and_preserve_provenance() -> None:
    """The live registry has canonical relation paths plus the one wallet exception."""
    audit = audit_registry_handoff_paths(bundled_authority())

    assert all(record.legal_refs and record.source_refs for record in audit.records)
    assert all(record.resolver_owner in {"relation_mesh", "iva_wallet"} for record in audit.records)
    assert all(not record.parallel_binding_ids and not record.parallel_casilla_ids for record in audit.records)

    wallet_rows = [record for record in audit.records if record.classification == "iva_wallet_exception"]
    assert {(record.target_modelo, record.target_revision, record.target_binding) for record in wallet_rows} == {
        ("303", revision_id, "modelo-303-compensacion-pendiente-anteriores") for revision_id in _M303_WALLET_REVISIONS
    }
    assert audit.classification.total == audit.relation_count
    assert audit.classification.iva_wallet_exception == len(wallet_rows)
    assert audit.classification.canonical_relation_prefill == audit.relation_count - len(wallet_rows)
    assert audit.classification.non_canonical == 0
    assert audit.classification.parallel == 0
    assert all(record.resolver_owner == "iva_wallet" for record in wallet_rows)


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
