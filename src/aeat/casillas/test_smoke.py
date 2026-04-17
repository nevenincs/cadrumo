"""Smoke tests for the casillas subpackage."""

from __future__ import annotations

import pytest

import aeat.casillas
import aeat.errors
import aeat.logging

pytestmark = [pytest.mark.unit, pytest.mark.domain_aeat_remote]


def test_smoke_casillas() -> None:
    """Assert the subpackage is importable and conventions hold."""
    assert aeat.casillas.__doc__ is not None
    assert issubclass(aeat.casillas.CasillaError, aeat.errors.AeatError)
    assert issubclass(aeat.casillas.UnreviewedRecordError, aeat.casillas.VerifyError)
    assert aeat.logging.get_logger(__name__).name == __name__


def test_public_surface_is_complete() -> None:
    """Every exported symbol must be importable from the package root."""
    for name in aeat.casillas.__all__:
        assert hasattr(aeat.casillas, name), f"missing public export: {name}"
