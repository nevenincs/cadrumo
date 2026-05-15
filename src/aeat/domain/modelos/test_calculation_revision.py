"""Calculation revision identity contract tests."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal

import pytest

from ._calculation_revision import derive_calculation_revision_id

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def test_revision_id_without_borrador_metadata_keeps_original_payload_shape() -> None:
    payload = {
        "work_unit_id": "a" * 64,
        "inputs": {"001": "10.00"},
        "overrides": {},
        "outputs": {"002": "15"},
        "source_transaction_ids": (),
    }
    expected = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"),
    ).hexdigest()

    assert (
        derive_calculation_revision_id(
            work_unit_id="a" * 64,
            inputs_snapshot={"001": "10.00"},
            binding_overrides={},
            casilla_values={"002": Decimal("15.00")},
        )
        == expected
    )


def test_revision_id_includes_present_borrador_metadata() -> None:
    base = derive_calculation_revision_id(
        work_unit_id="b" * 64,
        inputs_snapshot={"001": "10.00"},
        binding_overrides={},
        casilla_values={"002": Decimal("15.00")},
    )
    with_borrador = derive_calculation_revision_id(
        work_unit_id="b" * 64,
        inputs_snapshot={"001": "10.00"},
        binding_overrides={},
        casilla_values={"002": Decimal("15.00")},
        borrador_snapshot_id="snapshot-100-2025",
        bindings_sourced_from_borrador=("casilla_001",),
    )

    assert with_borrador != base
