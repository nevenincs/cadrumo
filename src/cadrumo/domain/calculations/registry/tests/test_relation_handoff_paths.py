"""Real-registry tests for canonical handoff path classification."""

from __future__ import annotations

import pytest

from .. import audit_registry_handoff_paths, bundled_authority
from .._validate_relation_sources import is_iva_wallet_owned_relation_target

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_bundled_handoff_paths_have_one_owner_and_preserve_provenance() -> None:
    """The live registry has canonical relation paths plus the one wallet exception."""
    audit = audit_registry_handoff_paths(bundled_authority())

    assert audit.relation_count == 74
    assert audit.classification.model_dump() == {
        "total": 74,
        "canonical_relation_prefill": 72,
        "iva_wallet_exception": 2,
        "non_canonical": 0,
        "parallel": 0,
    }
    assert all(record.legal_refs and record.source_refs for record in audit.records)
    assert all(record.resolver_owner in {"relation_mesh", "iva_wallet"} for record in audit.records)
    assert all(not record.parallel_binding_ids and not record.parallel_casilla_ids for record in audit.records)

    wallet_rows = [record for record in audit.records if record.classification == "iva_wallet_exception"]
    assert {(record.target_modelo, record.target_revision, record.target_binding) for record in wallet_rows} == {
        ("303", "2009-y-siguientes", "modelo-303-compensacion-pendiente-anteriores"),
        ("303", "2023-y-siguientes", "modelo-303-compensacion-pendiente-anteriores"),
    }
    assert all(record.resolver_owner == "iva_wallet" for record in wallet_rows)


def test_iva_wallet_exception_requires_the_exact_relation_coordinate() -> None:
    """Reusing the binding id cannot grant the M303 wallet carve-out."""
    binding_id = "modelo-303-compensacion-pendiente-anteriores"
    relation_id = "modelo-303-rel-self-compensacion-anteriores"

    assert is_iva_wallet_owned_relation_target(
        modelo_id="303",
        revision_id="2009-y-siguientes",
        relation_id=relation_id,
        target_binding=binding_id,
    )
    assert is_iva_wallet_owned_relation_target(
        modelo_id="303",
        revision_id="2023-y-siguientes",
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
        revision_id="2009-y-siguientes",
        relation_id="reused-binding-under-another-relation",
        target_binding=binding_id,
    )
