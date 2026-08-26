"""Registry-owned tolerance projection tests over bundled law-resolved snapshots."""

from __future__ import annotations

from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.verification_tolerance import verification_tolerance_or_exact

from ..authority import bundled_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_the_projection_uses_each_real_modelos_published_policy_or_exact_fallback() -> None:
    """One helper preserves the regulatory difference and the no-policy refusal.

    Modelo 130 publishes a one-cent tolerance, Modelo 303 folds to exact
    equality, and Modelo 349 publishes no expectation at all. Those real
    snapshots make a hardcoded tolerance or a permissive missing-policy fallback
    observably wrong.
    """
    authority = bundled_authority()

    modelo_130 = authority.snapshot("130", filing_year=2026, period="1T")
    modelo_303 = authority.snapshot("303", filing_year=2025, period="1T")
    modelo_349 = authority.snapshot("349", filing_year=2025, period="1T")

    assert verification_tolerance_or_exact(modelo_130) == Decimal("0.01")
    assert verification_tolerance_or_exact(modelo_303) == Decimal("0.00")
    assert verification_tolerance_or_exact(modelo_349) == Decimal("0")
