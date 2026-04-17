"""Smoke tests for the casillas subpackage."""

from __future__ import annotations

import pytest

from .. import casillas, errors, logging


@pytest.mark.unit
def test_smoke_casillas() -> None:
    """Assert the subpackage is importable and conventions hold."""
    assert casillas.__doc__ is not None
    assert issubclass(casillas.CasillaError, errors.AeatError)
    assert issubclass(casillas.UnreviewedRecordError, casillas.VerifyError)
    assert logging.get_logger(__name__).name == __name__


@pytest.mark.unit
def test_public_surface_is_complete() -> None:
    """Every exported symbol must be importable from the package root."""
    for name in casillas.__all__:
        assert hasattr(casillas, name), f"missing public export: {name}"
