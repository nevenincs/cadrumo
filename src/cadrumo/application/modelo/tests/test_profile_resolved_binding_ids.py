"""Which channels count as a profile-resolved binding is stated once.

:class:`CalculationSourceResolution` is the shared envelope for every source
resolver and carries seven value channels; a profile resolution populates
three of them. That "three" was re-encoded independently by the Modelo
binding-readiness gate, the operator state projection, and the resolver's own
provenance computation, so a fourth channel would have been picked up by
whichever site was edited and silently missed by the others -- and the two
consumers disagreeing means one surface reports a binding satisfied while the
other reports the same binding missing.
"""

from __future__ import annotations

import inspect
from datetime import date
from decimal import Decimal

import pytest

from ...aggregation import CalculationSourceResolution
from ..profile_binding import profile_resolved_binding_ids

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _resolution(**channels: object) -> CalculationSourceResolution:
    return CalculationSourceResolution.model_validate({"resolver_id": "test-profile", **channels})


class TestAccessor:
    def test_every_populated_channel_contributes(self) -> None:
        resolution = _resolution(
            binding_values={"b.decimal": Decimal("1")},
            enum_binding_values={"b.enum": "x"},
            date_binding_values={"b.date": date(2026, 1, 1)},
        )

        assert profile_resolved_binding_ids(resolution) == frozenset(
            {"b.decimal", "b.enum", "b.date"},
        )

    def test_an_empty_resolution_satisfies_nothing(self) -> None:
        assert profile_resolved_binding_ids(_resolution()) == frozenset()

    @pytest.mark.parametrize(
        ("channel", "value"),
        [
            ("binding_values", {"only": Decimal("0")}),
            ("enum_binding_values", {"only": "v"}),
            ("date_binding_values", {"only": date(2026, 1, 1)}),
        ],
    )
    def test_each_channel_alone_is_sufficient(self, channel: str, value: object) -> None:
        assert profile_resolved_binding_ids(_resolution(**{channel: value})) == frozenset({"only"})

    def test_a_channel_the_profile_resolver_does_not_populate_is_excluded(self) -> None:
        """The envelope is shared; only the profile channels count."""
        resolution = _resolution(
            binding_values={"b.decimal": Decimal("1")},
            relation_values={"r.not-a-binding": Decimal("5")},
        )

        assert profile_resolved_binding_ids(resolution) == frozenset({"b.decimal"})


def test_no_consumer_re_encodes_the_channel_union() -> None:
    """Both readiness surfaces must ask, not re-derive.

    Source inspection rather than behaviour, because two independent copies
    agreeing today is exactly the state this consolidation removes -- an
    equality assertion would pass against the duplication it exists to
    prevent.
    """
    from importlib import import_module

    from ... import state_projection

    _binding_readiness = import_module("cadrumo.application.modelo.binding_readiness")

    for module in (_binding_readiness, state_projection):
        source = inspect.getsource(module)
        assert "profile_resolved_binding_ids" in source, module.__name__
        assert "enum_binding_values) | set(" not in source, module.__name__
        assert "profile_resolution.enum_binding_values" not in source, module.__name__
