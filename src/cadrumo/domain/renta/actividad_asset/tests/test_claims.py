"""Contract tests for activity-asset claim identity and projections."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core.period import Period
from ..claims import AmortizationClaim, effective_claims, project_m100, project_m130, record_claim
from ..errors import ActividadAssetClaimConflictError
from ..lifecycle import AssetKind

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _claim(**overrides: object) -> AmortizationClaim:
    payload: dict[str, object] = {
        "asset_id": "office-computer",
        "asset_revision_id": "a" * 64,
        "asset_kind": AssetKind.MATERIAL,
        "tax_year": 2025,
        "covered_from": date(2025, 1, 1),
        "covered_until": date(2025, 4, 1),
        "amount": Decimal("200.00"),
        "schedule_fingerprint": "b" * 64,
        "authority_generation": "2025.1",
        "source_reference": "tabla-material-2025",
        "creating_operation": "record-amortization",
    }
    payload.update(overrides)
    return AmortizationClaim.model_validate(payload)


def test_exact_retry_reuses_claim_and_changed_same_interval_refuses() -> None:
    original = _claim()
    recorded = record_claim((), original)
    replayed = record_claim(recorded.claims, original)

    assert replayed.reused_existing_claim
    assert replayed.claim.claim_id == original.claim_id
    with pytest.raises(ActividadAssetClaimConflictError, match="same asset"):
        record_claim(recorded.claims, _claim(amount=Decimal("201.00")))


def test_overlaps_refuse_but_supersession_allows_a_new_revision_of_same_asset() -> None:
    original = _claim()
    claims = record_claim((), original).claims
    with pytest.raises(ActividadAssetClaimConflictError, match="overlapping"):
        record_claim(
            claims,
            _claim(covered_from=date(2025, 3, 1), covered_until=date(2025, 5, 1)),
        )

    correction = _claim(
        asset_revision_id="d" * 64,
        amount=Decimal("199.99"),
        supersedes_claim_id=original.claim_id,
    )
    amended = record_claim(claims, correction).claims

    assert effective_claims(amended) == (correction,)
    assert correction.asset_id == original.asset_id
    assert correction.asset_revision_id != original.asset_revision_id


def test_m100_and_m130_reference_same_effective_claim_without_duplicate_basis_use() -> None:
    material = _claim()
    intangible = _claim(
        asset_revision_id="c" * 64,
        asset_kind=AssetKind.INTANGIBLE,
        covered_from=date(2025, 4, 1),
        covered_until=date(2025, 7, 1),
        amount=Decimal("300.00"),
    )
    claims = (material, intangible)

    material_m100 = project_m100(claims, asset_kind=AssetKind.MATERIAL, tax_year=2025)
    intangible_m100 = project_m100(claims, asset_kind=AssetKind.INTANGIBLE, tax_year=2025)
    material_m130 = project_m130(
        claims,
        period=Period.from_year_and_code(2025, "1T"),
        asset_kind=AssetKind.MATERIAL,
    )

    assert material_m100.target_casilla_id == "0208"
    assert intangible_m100.target_casilla_id == "0227"
    assert material_m130.target_casilla_id == "02"
    assert material_m100.claim_ids == material_m130.claim_ids == (material.claim_id,)
    assert material_m100.amount == material_m130.amount == Decimal("200.00")
