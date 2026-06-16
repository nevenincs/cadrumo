"""The binding source-resolution result types are one role, not look-alikes.

Profile-fact resolution and AEAT-borrador resolution each return their own
result model, but both fill ONE role: resolve registry bindings from a source
onto the engine ``binding_values`` / ``enum_binding_values`` channels. This gate
pins that role to the shared
:class:`~aeat.application.modelo._binding_resolution.BindingSourceResolution`
Protocol so the two results cannot silently drift into incompatible shapes.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from .._binding_resolution import BindingSourceResolution
from .._borrador_binding import Modelo100BorradorBindingResult
from .._profile_binding import ProfileSourcedBindingResult

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _profile_result() -> ProfileSourcedBindingResult:
    return ProfileSourcedBindingResult(
        binding_values={"b-dec": Decimal("1")},
        enum_binding_values={"b-enum": "x"},
        bindings_sourced_from_profile=("b-dec", "b-enum"),
    )


def _borrador_result() -> Modelo100BorradorBindingResult:
    return Modelo100BorradorBindingResult(
        borrador_snapshot_id="snap-1",
        binding_values={"b-dec": Decimal("2")},
        enum_binding_values={"b-enum": "y"},
        bindings_sourced_from_borrador=("b-dec", "b-enum"),
    )


@pytest.mark.parametrize("result", [_profile_result(), _borrador_result()])
def test_result_satisfies_the_shared_role(result: object) -> None:
    """Each source-resolution result is a structural ``BindingSourceResolution``."""
    assert isinstance(result, BindingSourceResolution)


@pytest.mark.parametrize("result", [_profile_result(), _borrador_result()])
def test_role_exposes_both_engine_channels(result: BindingSourceResolution) -> None:
    """The role guarantees the Decimal and enum engine channels with the right value types."""
    assert all(isinstance(v, Decimal) for v in result.binding_values.values())
    assert all(isinstance(v, str) for v in result.enum_binding_values.values())


def test_empty_results_still_satisfy_the_role() -> None:
    """A resolver that satisfied no binding still fills the role (empty channels)."""
    assert isinstance(ProfileSourcedBindingResult(), BindingSourceResolution)
    assert isinstance(Modelo100BorradorBindingResult(), BindingSourceResolution)
