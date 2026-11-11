"""The Modelo 100 projection baseline never reaches the engine on a channel the profile also owns."""

from __future__ import annotations

import pytest

from cadrumo.core.aggregation import BindingSourceKind
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.binding_value_contract import BindingValueChannel

from ....domain.calculations.registry.tests.authored_editions import supported_authored_exercises
from ..projection import verb_baseline_projection_bindings

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PARAMETER_ENUM = "renta-profile-tax-residence-ccaa"


@pytest.mark.parametrize("year", supported_authored_exercises("100"))
def test_the_baseline_supplies_no_profile_sourced_binding_except_the_verbs_own_ccaa(year: int) -> None:
    with bundled_indexed_authority().operation() as operation:
        revision = operation.snapshot("100", filing_year=year, period="0A").revision
    profile_sourced = {binding.id for binding in revision.bindings if binding.source is BindingSourceKind.PROFILE}
    assert "renta-profile-family-minor-children-in-unit" in profile_sourced

    decimal, enum, boolean = verb_baseline_projection_bindings("madrid", revision)

    assert profile_sourced.isdisjoint(decimal)
    assert profile_sourced.isdisjoint(boolean)
    assert set(enum) <= {_PARAMETER_ENUM}
    assert enum == {_PARAMETER_ENUM: "madrid"}
    assert not set(decimal) & set(boolean) & set(enum)


@pytest.mark.parametrize("year", supported_authored_exercises("100"))
def test_every_baseline_binding_travels_on_the_channel_its_registry_declaration_names(year: int) -> None:
    with bundled_indexed_authority().operation() as operation:
        revision = operation.snapshot("100", filing_year=year, period="0A").revision
    declared = {binding.id: binding.value.channel for binding in revision.bindings}

    decimal, enum, boolean = verb_baseline_projection_bindings("madrid", revision)

    assert decimal
    assert enum
    assert {declared[key] for key in decimal} <= {BindingValueChannel.DECIMAL, BindingValueChannel.INTEGER}
    assert {declared[key] for key in enum} == {BindingValueChannel.ENUM}
    assert {declared[key] for key in boolean} <= {BindingValueChannel.BOOLEAN}
    # The modality is the profile's regime, so no baseline states it on the filer's behalf.
    assert "renta-modelo-100-estimacion-directa-es-normal" not in {*decimal, *enum, *boolean}
