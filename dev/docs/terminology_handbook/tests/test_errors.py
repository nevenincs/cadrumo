"""Canonical ownership tests for the Terminology Handbook errors."""

from __future__ import annotations

import pytest

import dev.docs.terminology_handbook as handbook_package
from dev.docs.terminology_handbook import errors

from ..errors import TerminologyError, TerminologyLoadError, TerminologyValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_errors_live_in_public_defining_module_without_facade_reexports() -> None:
    """The public module owns the hierarchy and the package has no error facade."""
    error_types = (TerminologyError, TerminologyLoadError, TerminologyValidationError)
    assert errors.__name__ == "dev.docs.terminology_handbook.errors"
    assert {error_type.__module__ for error_type in error_types} == {errors.__name__}
    assert not any(name.startswith("Terminology") and name.endswith("Error") for name in handbook_package.__all__)
    assert not hasattr(handbook_package, "TerminologyError")
    assert not hasattr(handbook_package, "TerminologyValidationError")
