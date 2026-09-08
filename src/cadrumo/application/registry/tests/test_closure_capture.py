"""Real-behavior proofs for the public registry-closure capture contract.

The composer this capture wraps walks the whole bundled registry with live
byte proof, so this suite is deliberately economical: it
mints two real captures (module-scoped) and reuses them across every
assertion rather than recomposing per test.
"""

from __future__ import annotations

from dataclasses import fields
from inspect import signature

import pytest

from ..closure_capture import (
    RegistryClosureCapture,
    RegistryClosureCaptureError,
    RegistryClosureCurrentCoordinate,
    capture_registry_closure,
    read_registry_closure_current_coordinate,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture(scope="module")
def _early_capture(registry_authority) -> RegistryClosureCapture:
    return capture_registry_closure(authority=registry_authority)


@pytest.fixture(scope="module")
def _early_capture_again(registry_authority) -> RegistryClosureCapture:
    return capture_registry_closure(authority=registry_authority)


def test_capture_republishes_filing_export_without_a_second_derivation(_early_capture) -> None:
    """The capture carries exactly the filing-export limbs."""
    names = {limb.name for limb in _early_capture.limbs}
    assert names == {"filing_export"}
    coordinates = {(limb.modelo, limb.revision, limb.name) for limb in _early_capture.limbs}
    assert len(coordinates) == len(_early_capture.limbs)


def test_capture_is_singleflight_and_current_against_its_own_coordinate(
    registry_authority,
    _early_capture,
    _early_capture_again,
) -> None:
    """An unchanged closure state shares one generation and stays current."""
    assert _early_capture.generation == _early_capture_again.generation
    assert _early_capture.comparison_domain == _early_capture_again.comparison_domain

    current = read_registry_closure_current_coordinate(authority=registry_authority)
    assert _early_capture.require_current(current) is _early_capture


def test_a_superseded_generation_is_refused_within_one_owner_scope(_early_capture) -> None:
    """A coordinate from a different closure observation refuses the earlier capture."""
    superseded = RegistryClosureCurrentCoordinate(
        comparison_domain=_early_capture.comparison_domain,
        generation=_early_capture.generation + 1,
    )
    with pytest.raises(RegistryClosureCaptureError):
        _early_capture.require_current(superseded)


def test_capture_exposes_no_composer_internals_and_no_second_closure_shape() -> None:
    """The capture adds a coordinate only; it derives no parallel closure shape."""
    assert {field.name for field in fields(RegistryClosureCapture)} == {
        "limbs",
        "comparison_domain",
        "generation",
    }
    assert {field.name for field in fields(RegistryClosureCurrentCoordinate)} == {
        "comparison_domain",
        "generation",
    }


def test_closure_capture_accepts_only_executable_authorities() -> None:
    """Development censuses cannot return as inputs to the product closure API."""
    expected = {"authority", "filing_proof_authority"}
    assert set(signature(capture_registry_closure).parameters) == expected
    assert set(signature(read_registry_closure_current_coordinate).parameters) == expected


def test_closure_capture_authority_is_owned_by_its_defining_module() -> None:
    """Every closure-capture symbol is defined here and bound nowhere in the package namespace."""
    from ... import registry as registry_namespace

    for owned in (
        RegistryClosureCapture,
        RegistryClosureCurrentCoordinate,
        RegistryClosureCaptureError,
        capture_registry_closure,
        read_registry_closure_current_coordinate,
    ):
        assert owned.__module__ == "cadrumo.application.registry.closure_capture"
        assert not hasattr(registry_namespace, owned.__name__)
