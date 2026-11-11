"""The comparing precedence overlay: which replacements it reports, on which channel, and in what order it admits tiers.

Every expected divergence is stated from the two values the test lays down; a
value the overlay keeps is always the higher tier's.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal

import pytest

from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.modelos.source_disagreement import (
    DisagreementBooleanValue,
    DisagreementDateValue,
    DisagreementDecimalValue,
    DisagreementRelationValue,
    DisagreementRowsValue,
    DisagreementTextValue,
    SourceDisagreementRole,
)
from ..errors import AggregationValidationError
from ..source_mesh import CalculationSourceResolution
from ..source_precedence import PRECEDENCE_OVERLAY_ORDER
from ..source_resolution_operations import (
    PrecedenceKeyKind,
    PrecedenceOverlay,
    PrecedenceTier,
    TierValueProvenance,
    merge_source_resolutions_by_precedence,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = SourceDisagreementRole.PROFILE
_BACKEND = SourceDisagreementRole.BACKEND
_BORRADOR = SourceDisagreementRole.BORRADOR
_CALLER = SourceDisagreementRole.CALLER
_BINDING = "test-binding"
_RELATION = "test-fold-slot"
_CASILLA = "01"
_YEAR = filing_year_envelope().horizon


def _tier(
    role: SourceDisagreementRole,
    provenance: Mapping[str, TierValueProvenance] | None = None,
    /,
    **channels: object,
) -> PrecedenceTier:
    resolution = CalculationSourceResolution.model_validate({"resolver_id": f"test-{role.value}", **channels})
    return PrecedenceTier(
        role=role, resolution=resolution, source_family=f"family-{role.value}", provenance=provenance or {}
    )


def _overlay(*tiers: PrecedenceTier) -> PrecedenceOverlay:
    return merge_source_resolutions_by_precedence(tiers)


@pytest.mark.parametrize(
    ("channel", "lower", "higher", "diverges"),
    [
        pytest.param("binding_values", Decimal("10.0"), Decimal("10.00"), False, id="decimal-scale-only"),
        pytest.param("binding_values", Decimal("10.00"), Decimal("10.001"), True, id="decimal-sub-cent"),
        pytest.param("binding_values", Decimal("-0.00"), Decimal("0"), False, id="decimal-signed-zero"),
        pytest.param("enum_binding_values", "madrid", "madrid", False, id="enum-same-token"),
        pytest.param("enum_binding_values", "madrid", "Madrid", True, id="enum-token-against-label"),
        pytest.param("date_binding_values", date(_YEAR, 3, 1), date(_YEAR, 3, 1), False, id="date-same-day"),
        pytest.param("date_binding_values", date(_YEAR, 3, 1), date(_YEAR, 3, 2), True, id="date-next-day"),
        pytest.param("boolean_binding_values", True, True, False, id="boolean-same"),
        pytest.param("boolean_binding_values", True, False, True, id="boolean-flipped"),
        pytest.param("relation_values", Decimal("5"), Decimal("5.000"), False, id="relation-scale-only"),
        pytest.param("relation_values", Decimal("5"), Decimal("5.01"), True, id="relation-cent"),
        pytest.param("bound_inputs_by_casilla_id", Decimal("1"), Decimal("1.00"), False, id="casilla-scale-only"),
        pytest.param("bound_inputs_by_casilla_id", Decimal("1"), Decimal("2"), True, id="casilla-different"),
    ],
)
def test_each_channel_compares_by_its_own_equality(channel: str, lower: object, higher: object, diverges: bool) -> None:
    key = "01" if channel == "bound_inputs_by_casilla_id" else _BINDING
    overlay = _overlay(_tier(_BACKEND, **{channel: {key: lower}}), _tier(_CALLER, **{channel: {key: higher}}))

    assert getattr(overlay.resolution, channel)[key] == higher
    assert bool(overlay.divergences) is diverges
    if diverges:
        (divergence,) = overlay.divergences
        assert divergence.key == key
        assert divergence.selected_role is _CALLER
        assert [source.role for source in divergence.sources] == [_BACKEND, _CALLER]


def test_a_key_only_one_tier_holds_is_no_divergence() -> None:
    overlay = _overlay(
        _tier(_PROFILE, binding_values={"profile-only": Decimal("1")}),
        _tier(_CALLER, binding_values={"caller-only": Decimal("2")}),
    )

    assert overlay.divergences == ()
    assert dict(overlay.selected_binding_roles) == {"profile-only": _PROFILE, "caller-only": _CALLER}


@pytest.mark.parametrize(
    ("lower", "higher", "selected"),
    [
        pytest.param(_BACKEND, _BORRADOR, _BORRADOR, id="borrador-over-backend"),
        pytest.param(_PROFILE, _BORRADOR, _BORRADOR, id="borrador-over-profile"),
        pytest.param(_PROFILE, _CALLER, _CALLER, id="caller-over-profile"),
        pytest.param(_BORRADOR, _CALLER, _CALLER, id="caller-over-borrador"),
        pytest.param(_BACKEND, _CALLER, _CALLER, id="caller-over-carried-backend"),
    ],
)
def test_every_transition_states_both_tiers_values_and_provenance(
    lower: SourceDisagreementRole, higher: SourceDisagreementRole, selected: SourceDisagreementRole
) -> None:
    lower_provenance = TierValueProvenance(
        source_family="previous_filing", source_ref=f"{lower.value}:binding:{_BINDING}", evidence_ref="f" * 64
    )
    overlay = _overlay(
        _tier(lower, {_BINDING: lower_provenance}, binding_values={_BINDING: Decimal("100.00")}),
        _tier(higher, binding_values={_BINDING: Decimal("90.00")}),
    )

    (divergence,) = overlay.divergences
    low, high = divergence.sources
    assert divergence.selected_role is selected
    assert divergence.key_kind is PrecedenceKeyKind.BINDING
    assert divergence.value_channel == "decimal"
    assert (low.role, low.value, low.source_family, low.source_ref, low.evidence_ref) == (
        lower,
        DisagreementDecimalValue.of(Decimal("100.00")),
        "previous_filing",
        f"{lower.value}:binding:{_BINDING}",
        "f" * 64,
    )
    assert (high.role, high.value, high.source_family, high.source_ref) == (
        higher,
        DisagreementDecimalValue.of(Decimal("90.00")),
        f"family-{higher.value}",
        None,
    )
    assert overlay.resolution.binding_values[_BINDING] == Decimal("90.00")


def test_three_tiers_state_every_value_in_order_and_keep_the_highest() -> None:
    overlay = _overlay(
        _tier(_PROFILE, date_binding_values={_BINDING: date(_YEAR, 1, 1)}),
        _tier(_BORRADOR, date_binding_values={_BINDING: date(_YEAR, 1, 2)}),
        _tier(_CALLER, date_binding_values={_BINDING: date(_YEAR, 1, 3)}),
    )

    (divergence,) = overlay.divergences
    assert [(source.role, source.value) for source in divergence.sources] == [
        (_PROFILE, DisagreementDateValue(value=date(_YEAR, 1, 1))),
        (_BORRADOR, DisagreementDateValue(value=date(_YEAR, 1, 2))),
        (_CALLER, DisagreementDateValue(value=date(_YEAR, 1, 3))),
    ]
    assert overlay.resolution.date_binding_values[_BINDING] == date(_YEAR, 1, 3)


def test_a_middle_tier_that_differs_is_reported_even_when_the_highest_equals_the_lowest() -> None:
    overlay = _overlay(
        _tier(_PROFILE, boolean_binding_values={_BINDING: True}),
        _tier(_BORRADOR, boolean_binding_values={_BINDING: False}),
        _tier(_CALLER, boolean_binding_values={_BINDING: True}),
    )

    (divergence,) = overlay.divergences
    assert [source.value for source in divergence.sources] == [
        DisagreementBooleanValue(value=True),
        DisagreementBooleanValue(value=False),
        DisagreementBooleanValue(value=True),
    ]


def test_a_relation_divergence_is_keyed_as_a_relation() -> None:
    overlay = _overlay(
        _tier(_BACKEND, relation_values={"fold-slot": Decimal("7")}),
        _tier(_CALLER, relation_values={"fold-slot": Decimal("8")}),
    )

    (divergence,) = overlay.divergences
    assert (divergence.key_kind, divergence.value_channel) == (PrecedenceKeyKind.RELATION, "relation")
    assert divergence.sources[0].value == DisagreementRelationValue.of(Decimal("7"))


def test_a_row_set_differing_in_cardinality_is_one_divergence_naming_the_extra_row() -> None:
    overlay = _overlay(
        _tier(_BACKEND, row_binding_values={(_BINDING, 1): Decimal("1"), (_BINDING, 2): Decimal("2")}),
        _tier(_CALLER, row_binding_values={(_BINDING, 1): Decimal("1")}),
    )

    (divergence,) = overlay.divergences
    assert (divergence.key, divergence.value_channel, divergence.differing_row_indices) == (_BINDING, "rows", (2,))
    assert divergence.sources[0].value == DisagreementRowsValue(
        rows=(DisagreementDecimalValue.of(Decimal("1")), DisagreementDecimalValue.of(Decimal("2")))
    )
    # The whole set comes from the highest tier: the backend's second row does not survive beside it.
    assert dict(overlay.resolution.row_binding_values) == {(_BINDING, 1): Decimal("1")}


def test_a_row_set_differing_in_one_row_names_only_that_row() -> None:
    overlay = _overlay(
        _tier(_BORRADOR, row_binding_values={(_BINDING, 1): "ES", (_BINDING, 2): Decimal("3"), (_BINDING, 3): True}),
        _tier(_CALLER, row_binding_values={(_BINDING, 1): "ES", (_BINDING, 2): Decimal("4"), (_BINDING, 3): True}),
    )

    (divergence,) = overlay.divergences
    assert divergence.differing_row_indices == (2,)
    assert divergence.sources[1].value == DisagreementRowsValue(
        rows=(
            DisagreementTextValue(value="ES"),
            DisagreementDecimalValue.of(Decimal("4")),
            DisagreementBooleanValue(value=True),
        )
    )


def test_equal_row_sets_are_silent_whatever_the_decimal_scale() -> None:
    overlay = _overlay(
        _tier(_BACKEND, row_binding_values={(_BINDING, 1): Decimal("1.0")}),
        _tier(_CALLER, row_binding_values={(_BINDING, 1): Decimal("1.00")}),
    )

    assert overlay.divergences == ()


@pytest.mark.parametrize(
    "roles",
    [
        pytest.param((_CALLER, _PROFILE), id="reversed"),
        pytest.param((_BACKEND, _BACKEND), id="repeated"),
        pytest.param((_BORRADOR, _BACKEND), id="borrador-below-backend"),
        pytest.param((SourceDisagreementRole.VALUE_SOURCE, _CALLER), id="a-cross-check-role-is-no-tier"),
    ],
)
def test_tiers_laid_out_of_the_declared_order_are_refused(roles: tuple[SourceDisagreementRole, ...]) -> None:
    with pytest.raises(AggregationValidationError) as refused:
        _overlay(*(_tier(role) for role in roles))

    assert str(refused.value) == "aggregation.source_mesh.errors.precedence_tier_out_of_order"


def test_the_declared_order_admits_every_tier_once() -> None:
    overlay = _overlay(
        *(_tier(role, binding_values={_BINDING: Decimal(index)}) for index, role in enumerate(PRECEDENCE_OVERLAY_ORDER))
    )

    assert overlay.selected_binding_roles[_BINDING] is PRECEDENCE_OVERLAY_ORDER[-1]
    assert [source.role for source in overlay.divergences[0].sources] == list(PRECEDENCE_OVERLAY_ORDER)


def test_a_long_text_cell_is_stated_truncated_but_compared_whole() -> None:
    shared = "x" * 600
    overlay = _overlay(
        _tier(_BACKEND, row_binding_values={(_BINDING, 1): shared + "a"}),
        _tier(_CALLER, row_binding_values={(_BINDING, 1): shared + "b"}),
    )

    (divergence,) = overlay.divergences
    low, high = (source.value for source in divergence.sources)
    assert low == high
    assert divergence.differing_row_indices == (1,)


def test_an_amount_at_three_fraction_digits_is_stated_at_its_own_scale() -> None:
    """``12.500`` reaches a finding stated exactly as resolved, on every scalar and relation channel."""
    overlay = _overlay(
        _tier(
            _BACKEND,
            binding_values={_BINDING: Decimal("12.500")},
            relation_values={_RELATION: Decimal("5.000")},
            bound_inputs_by_casilla_id={_CASILLA: Decimal("10.001")},
        ),
        _tier(
            _CALLER,
            binding_values={_BINDING: Decimal("12.600")},
            relation_values={_RELATION: Decimal("5.001")},
            bound_inputs_by_casilla_id={_CASILLA: Decimal("10.002")},
        ),
    )

    stated = {divergence.key: [source.value for source in divergence.sources] for divergence in overlay.divergences}
    assert stated == {
        _BINDING: [DisagreementDecimalValue(amount="12.500"), DisagreementDecimalValue(amount="12.600")],
        _RELATION: [DisagreementRelationValue(amount="5.000"), DisagreementRelationValue(amount="5.001")],
        _CASILLA: [DisagreementDecimalValue(amount="10.001"), DisagreementDecimalValue(amount="10.002")],
    }


def test_a_binding_the_lower_tier_settles_as_not_applying_is_filled_without_a_divergence() -> None:
    """A not-applicable answer states no value, so a higher tier's value is a fill, not a contest."""
    overlay = _overlay(
        _tier(_BACKEND, inapplicable_binding_ids=(_BINDING,)),
        _tier(_CALLER, binding_values={_BINDING: Decimal("40.00")}),
    )

    assert overlay.divergences == ()
    assert overlay.resolution.binding_values[_BINDING] == Decimal("40.00")
    assert overlay.selected_binding_roles[_BINDING] is _CALLER


def test_a_binding_the_lower_tier_leaves_unresolved_is_filled_without_a_divergence() -> None:
    overlay = _overlay(
        _tier(_BACKEND, unresolved_binding_ids=(_BINDING,)),
        _tier(_CALLER, binding_values={_BINDING: Decimal("-150.00")}),
    )

    assert overlay.divergences == ()
    assert overlay.resolution.binding_values[_BINDING] == Decimal("-150.00")


def test_a_row_fed_binding_holds_no_scalar_for_a_higher_scalar_to_contest() -> None:
    """Row values settle a binding for formula operands without stating a scalar the overlay could compare.

    A scalar for the same binding is a channel defect, which the registry's
    channel check refuses; the overlay itself reports no divergence for it.
    """
    overlay = _overlay(
        _tier(_BACKEND, row_binding_values={(_BINDING, 1): Decimal("0.00")}),
        _tier(_CALLER, binding_values={_BINDING: Decimal("12.00")}),
    )

    assert overlay.divergences == ()
