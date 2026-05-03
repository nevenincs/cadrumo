"""Unit tests for the CLI-private family-alias mapping.

Pins the contract of
:data:`aeat.entrypoints.cli.financial._profile_aliases.FAMILY_ALIASES`:
membership, immutability, eligibility against
:data:`aeat.domain.usage_ratios.ELIGIBLE_USAGE_RATIO_CATEGORIES`, and
that the Typer help text stays in sync with the mapping.
"""

from __future__ import annotations

from types import MappingProxyType

import pytest

from ....domain.categories import SpendingCategory
from ....domain.usage_ratios import ELIGIBLE_USAGE_RATIO_CATEGORIES
from ._profile_aliases import FAMILY_ALIASES

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def test_home_office_area_covers_six_categories() -> None:
    """``home_office_area`` expands to every USAGE_RATIO_HOME_AREA category."""
    expected = (
        SpendingCategory.ARRENDAMIENTO_VIVIENDA_AFECTO,
        SpendingCategory.SUMINISTROS_HOME_OFFICE_AGUA,
        SpendingCategory.SUMINISTROS_HOME_OFFICE_GAS,
        SpendingCategory.SUMINISTROS_HOME_OFFICE_INTERNET,
        SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ,
        SpendingCategory.TELEFONIA_FIJA,
    )
    assert FAMILY_ALIASES["home_office_area"] == expected


def test_mileage_business_covers_five_vehicle_categories() -> None:
    """``mileage_business`` expands to every vehicle USAGE_RATIO_PERSONAL category."""
    assert FAMILY_ALIASES["mileage_business"] == (
        SpendingCategory.VEHICULO_COMBUSTIBLE,
        SpendingCategory.VEHICULO_MANTENIMIENTO,
        SpendingCategory.VEHICULO_SEGURO,
        SpendingCategory.VEHICULO_PEAJE,
        SpendingCategory.VEHICULO_PARKING,
    )


def test_no_alias_overlap_across_the_mapping() -> None:
    """Alias expansions must be disjoint.

    Overlapping aliases would silently clobber prior ``set-ratio``
    values when two aliases are set in sequence. ``phone_fixed_business``
    was removed for this exact reason; this test guards against a
    future regression.
    """
    seen: set[SpendingCategory] = set()
    for members in FAMILY_ALIASES.values():
        overlap = seen.intersection(members)
        assert not overlap, f"alias members overlap: {overlap}"
        seen.update(members)


def test_every_aliased_category_is_eligible() -> None:
    """Every category exposed via an alias must be persistable."""
    for members in FAMILY_ALIASES.values():
        for category in members:
            assert category in ELIGIBLE_USAGE_RATIO_CATEGORIES


def test_aliases_reject_mutation_at_runtime() -> None:
    """Attempting to add an alias at runtime raises at the mapping level."""
    # cast through Any so the static checker doesn't flag the attempted
    # assignment — the POINT of the test is that the runtime rejects it.
    import typing

    mapping = typing.cast(typing.Any, FAMILY_ALIASES)
    with pytest.raises(TypeError):
        mapping["new_alias"] = (SpendingCategory.TELEFONIA_MOVIL,)


def test_aliases_are_mapping_proxy() -> None:
    """``FAMILY_ALIASES`` is wrapped in ``MappingProxyType``."""
    assert isinstance(FAMILY_ALIASES, MappingProxyType)


def test_set_ratio_help_lists_only_current_aliases() -> None:
    """Regression guard: Typer argument help must not advertise removed aliases.

    The help string previously hard-coded the alias list; following
    ``--help`` for a removed alias would then surface an
    ``unknown key`` error. The help text now derives from
    :data:`aeat.entrypoints.cli.financial._profile_aliases.FAMILY_ALIASES`
    and this test pins the guarantee.
    """
    from typer.testing import CliRunner

    from .profile import app as profile_app

    runner = CliRunner()
    result = runner.invoke(profile_app, ["set-ratio", "--help"])
    assert result.exit_code == 0
    # Every advertised alias must still exist.
    for alias in FAMILY_ALIASES:
        assert alias in result.output
    # No stale alias (guard against accidental reintroduction).
    assert "phone_fixed_business" not in result.output
