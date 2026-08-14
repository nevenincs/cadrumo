"""Shared fixtures for development registry tests."""

import pytest

from cadrumo.domain.calculations.registry import bundled_revision_inspection


@pytest.fixture
def m200_inspection_snapshot():
    return bundled_revision_inspection("200", filing_year=2025, period="0A")
