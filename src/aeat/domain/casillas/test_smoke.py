"""Smoke tests for the casillas subpackage."""

from __future__ import annotations

import pytest

from ...core import errors, logging
from . import __all__ as casillas_all
from . import __doc__ as casillas_doc
from . import CasillaError, UnreviewedRecordError, VerifyError
from . import __name__ as _package_name

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def test_smoke_casillas() -> None:
    """Assert the subpackage is importable and conventions hold."""
    assert casillas_doc is not None
    assert issubclass(CasillaError, errors.AeatError)
    assert issubclass(UnreviewedRecordError, VerifyError)
    assert logging.get_logger(__name__).name == __name__


def test_public_surface_is_complete() -> None:
    """Every exported symbol must be importable from the package root."""
    import importlib

    package = importlib.import_module(_package_name)
    for name in casillas_all:
        assert hasattr(package, name), f"missing public export: {name}"
