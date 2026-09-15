"""Real-registry parity checks for foreign-asset declaration thresholds."""

from __future__ import annotations

from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority as _indexed_authority_for_test

from ....core.foreign_asset_obligation import ForeignAssetObligationGroup
from ...foreign_asset_thresholds import foreign_asset_declaration_thresholds

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.mark.parametrize(
    ("modelo", "filing_year", "groups", "legal_refs", "source_refs"),
    [
        (
            "720",
            2025,
            (
                ForeignAssetObligationGroup.from_registry("cuentas"),
                ForeignAssetObligationGroup.from_registry("valores_derechos_seguros"),
                ForeignAssetObligationGroup.from_registry("inmuebles"),
            ),
            {
                "rd-1065-2007:art-42-bis",
                "rd-1065-2007:art-42-ter",
                "rd-1065-2007:art-54-bis",
            },
            {"aeat-modelo-720-procedure"},
        ),
        (
            "721",
            2024,
            (ForeignAssetObligationGroup.from_registry("monedas_virtuales"),),
            {"rd-1065-2007:art-42-quater", "ley-58-2003:da-18"},
            {"aeat-modelo-721-procedure"},
        ),
    ],
)
def test_effective_registry_revision_supplies_each_modelos_threshold_and_grounding(
    modelo: str,
    filing_year: int,
    groups: tuple[ForeignAssetObligationGroup, ...],
    legal_refs: set[str],
    source_refs: set[str],
) -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        thresholds = foreign_asset_declaration_thresholds(
            modelo=modelo, filing_year=filing_year, operation=_authority_operation_for_test
        )

        assert set(thresholds) == set(groups)
        for group in groups:
            threshold = thresholds[group]
            assert threshold.initial_declaration_floor_eur == Decimal("50000.00")
            assert threshold.redeclaration_increase_delta_eur == Decimal("20000.00")
            assert set(threshold.legal_refs) == legal_refs
            assert set(threshold.source_refs) == source_refs
