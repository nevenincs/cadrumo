"""Resolver identity projection into persisted calculation source references."""

from __future__ import annotations

import pytest

from ....core import BindingSourceKind
from ...aggregation import CalculationSourceProvenance, CalculationSourceResolution
from .._calculation_actions import _source_provenance_refs

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_source_provenance_projection_retains_exact_resolver_identity() -> None:
    resolution = CalculationSourceResolution(
        resolver_id="invoice_catalogue",
        owned_sources=(BindingSourceKind.COLLECTIBLE_INVOICE,),
        provenance=(
            CalculationSourceProvenance(
                resolver_id="invoice_catalogue",
                binding_source=BindingSourceKind.COLLECTIBLE_INVOICE,
                source_kind=BindingSourceKind.COLLECTIBLE_INVOICE.value,
                source_ref="collectible_invoice:inv-0001",
                fingerprint="sha256:" + "a" * 64,
            ),
        ),
    )

    persisted = _source_provenance_refs(resolution)

    assert len(persisted) == 1
    assert persisted[0].resolver_id == resolution.resolver_id
    assert persisted[0].source_ref == resolution.provenance[0].source_ref
