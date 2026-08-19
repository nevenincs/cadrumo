"""Shared fixtures for development registry tests."""

import pytest

from cadrumo.domain.calculations.registry import bundled_revision_inspection


@pytest.fixture
def m200_inspection_snapshot():
    return bundled_revision_inspection("200", filing_year=2025, period="0A")


@pytest.fixture
def m130_inspection_snapshot():
    """A real revision authority that declares NO projection endpoint.

    Modelo 200 gained 578 projection declarations, and semantic-map validation
    checks a map against them as a bijection, so a synthetic map can no longer
    be validated against it except to test that very bijection.
    """
    return bundled_revision_inspection("130", filing_year=2026, period="1T")
