"""Real-behavior proofs for the public registry-closure capture contract.

Each composer this capture wraps walks the whole bundled registry with live
byte and connectivity proofs, so this suite is deliberately economical: it
mints exactly three real captures (module-scoped) and reuses them across every
assertion rather than recomposing per test.
"""

from __future__ import annotations

from dataclasses import fields
from datetime import date

import pytest

from .. import load_source_connectivity_census
from ..closure_capture import (
    RegistryClosureCapture,
    RegistryClosureCaptureError,
    RegistryClosureCurrentCoordinate,
    capture_registry_closure,
    read_registry_closure_current_coordinate,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_AS_OF = date(2026, 8, 24)
_LATER_AS_OF = date(2026, 12, 31)


@pytest.fixture(scope="module")
def _census():
    return load_source_connectivity_census()


@pytest.fixture(scope="module")
def _early_capture(registry_authority, _census) -> RegistryClosureCapture:
    return capture_registry_closure(authority=registry_authority, census=_census, as_of=_AS_OF)


@pytest.fixture(scope="module")
def _early_capture_again(registry_authority, _census) -> RegistryClosureCapture:
    return capture_registry_closure(authority=registry_authority, census=_census, as_of=_AS_OF)


@pytest.fixture(scope="module")
def _late_capture(registry_authority, _census) -> RegistryClosureCapture:
    return capture_registry_closure(authority=registry_authority, census=_census, as_of=_LATER_AS_OF)


def test_capture_republishes_both_composers_without_a_third_derivation(_early_capture) -> None:
    """The capture carries exactly the filing-export and source-connectivity limbs."""
    names = {limb.name for limb in _early_capture.limbs}
    assert names == {"filing_export", "source_connectivity"}
    coordinates = {(limb.modelo, limb.revision, limb.name) for limb in _early_capture.limbs}
    assert len(coordinates) == len(_early_capture.limbs)


def test_capture_is_singleflight_and_current_against_its_own_coordinate(
    registry_authority,
    _census,
    _early_capture,
    _early_capture_again,
) -> None:
    """An unchanged closure state shares one generation and stays current."""
    assert _early_capture.generation == _early_capture_again.generation
    assert _early_capture.comparison_domain == _early_capture_again.comparison_domain

    current = read_registry_closure_current_coordinate(authority=registry_authority, census=_census, as_of=_AS_OF)
    assert _early_capture.require_current(current) is _early_capture


def test_closure_state_moves_independently_of_the_registry_snapshot(_early_capture, _late_capture) -> None:
    """Advancing only the assessment date, with the same authority and census, changes closure.

    This is the evidence for building a native generation here at all: if
    closure were a pure function of the registry snapshot, the same authority
    and census could never disagree with themselves across two dates.
    """
    assert _early_capture.limbs != _late_capture.limbs
    assert _early_capture.generation != _late_capture.generation


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
