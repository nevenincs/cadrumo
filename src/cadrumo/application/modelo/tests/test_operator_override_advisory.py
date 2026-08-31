"""The operator-override advisory discloses a discarded computed figure.

The merge lets an operator casilla value win over a computed one, which is
intended. These tests pin the DISCLOSURE and its three silences: an override
that changes nothing, a casilla the engine never computed, and a casilla the
operator never set must all stay quiet, or the advisory becomes noise an
operator learns to skip.

Real registry revisions throughout, loaded through the bundled authority. No
doubles: the collector reads a :class:`ModeloRevision` and two plain mappings,
so there is nothing to stub.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.modelo import Modelo
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.schema import ModeloRevision
from .._operator_override_advisory import collect_operator_override_divergence_diagnostics
from ..action_errors import ModeloAggregationBindingError
from ..calculation_actions import _reject_caller_overrides_of_source_bindings, _source_owned_bound_casilla_ids
from ..calculation_source_policy import BUCKET_AGGREGATION_OWNED_SOURCES, CALLER_OVERRIDABLE_CARRY_SOURCES

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: The casilla-override guard's effective set: every bucket-owned source kind
#: except those a caller is explicitly allowed to carry.
_GUARDED_SOURCES = frozenset(BUCKET_AGGREGATION_OWNED_SOURCES) - frozenset(CALLER_OVERRIDABLE_CARRY_SOURCES)


@pytest.fixture(scope="module")
def m303_revision() -> ModeloRevision:
    return bundled_authority().snapshot(Modelo.M303, filing_year=2024, period="1T").revision


@pytest.fixture(scope="module")
def m390_revision() -> ModeloRevision:
    return bundled_authority().snapshot(Modelo.M390, filing_year=2024, period="0A").revision


def test_divergent_operator_value_raises_one_advisory_naming_both_figures(
    m303_revision: ModeloRevision,
) -> None:
    """The advisory carries the supplied AND the computed figure, so the operator can compare."""
    diagnostics = collect_operator_override_divergence_diagnostics(
        m303_revision,
        casilla_inputs={"44": Decimal("100.00")},
        bound_inputs={"44": Decimal("90.00")},
    )

    assert len(diagnostics) == 1
    diagnostic = diagnostics[0]
    assert diagnostic.reason == "operator_override_diverges_from_computed"
    assert diagnostic.casilla_id == "44"
    assert "100.00" in diagnostic.message
    assert "90.00" in diagnostic.message
    assert diagnostic.remedy is not None


def test_operator_value_equal_to_computed_is_silent(m303_revision: ModeloRevision) -> None:
    """Supplying the figure the engine derived overrides nothing worth announcing."""
    assert (
        collect_operator_override_divergence_diagnostics(
            m303_revision,
            casilla_inputs={"44": Decimal("90.00")},
            bound_inputs={"44": Decimal("90.00")},
        )
        == ()
    )


def test_casilla_the_engine_never_computed_is_silent(m303_revision: ModeloRevision) -> None:
    """With no computed value there is nothing to discard, so this is plain input."""
    assert (
        collect_operator_override_divergence_diagnostics(
            m303_revision,
            casilla_inputs={"44": Decimal("100.00")},
            bound_inputs={},
        )
        == ()
    )


def test_computed_casilla_the_operator_never_set_is_silent(m303_revision: ModeloRevision) -> None:
    """An untouched computed value is the ordinary path and must not raise."""
    assert (
        collect_operator_override_divergence_diagnostics(
            m303_revision,
            casilla_inputs={},
            bound_inputs={"44": Decimal("90.00")},
        )
        == ()
    )


def test_advisory_fires_in_both_directions(m303_revision: ModeloRevision) -> None:
    """A lower operator figure is as disclosable as a higher one.

    Direction-agnostic by construction: on a regularizacion neither direction is
    presumptively the error, and a one-directional screen would inherit this
    codebase's existing blindness to over-declaration rather than close it.
    """
    higher = collect_operator_override_divergence_diagnostics(
        m303_revision,
        casilla_inputs={"44": Decimal("100.00")},
        bound_inputs={"44": Decimal("90.00")},
    )
    lower = collect_operator_override_divergence_diagnostics(
        m303_revision,
        casilla_inputs={"44": Decimal("80.00")},
        bound_inputs={"44": Decimal("90.00")},
    )

    assert len(higher) == 1
    assert len(lower) == 1


def test_multiple_divergences_are_sorted_by_casilla_id(m303_revision: ModeloRevision) -> None:
    """Stable ordering, so a diff of two calculate responses is readable."""
    diagnostics = collect_operator_override_divergence_diagnostics(
        m303_revision,
        casilla_inputs={"44": Decimal("100.00"), "43": Decimal("10.00")},
        bound_inputs={"44": Decimal("90.00"), "43": Decimal("20.00")},
    )

    assert [diagnostic.casilla_id for diagnostic in diagnostics] == ["43", "44"]


def test_source_kind_is_not_a_registry_binding_source(m303_revision: ModeloRevision) -> None:
    """The override arrives on the operator's channel, so no binding source is claimed.

    ``binding_source`` hydrates only when ``source_kind`` names a canonical
    :class:`~core.BindingSourceKind`; leaving it ``None`` keeps a consumer from
    attributing the operator's own value to a registry source.
    """
    diagnostic = collect_operator_override_divergence_diagnostics(
        m303_revision,
        casilla_inputs={"44": Decimal("100.00")},
        bound_inputs={"44": Decimal("90.00")},
    )[0]

    assert diagnostic.binding_source is None


def test_m390_bienes_inversion_casilla_is_barred_from_operator_override(
    m390_revision: ModeloRevision,
    m303_revision: ModeloRevision,
) -> None:
    """The one BOUND casilla on this channel is unreachable, so the live surface is smaller.

    ``iva.anual.regularizacion-bienes-inversion`` is bound to a
    ``bienes_inversion_regularizacion`` source the bucket resolvers own, and its
    resolver reports that ownership unconditionally. The caller-override guard
    therefore refuses an operator value for it before the merge is reached.

    The Modelo 303 manual casilla is the positive control: if the guard refused
    that too it would simply be refusing everything, and the Modelo 390 refusal
    would prove nothing about this casilla in particular.
    """
    barred = "iva.anual.regularizacion-bienes-inversion"
    assert barred in _source_owned_bound_casilla_ids(m390_revision, _GUARDED_SOURCES)

    with pytest.raises(ModeloAggregationBindingError):
        _reject_caller_overrides_of_source_bindings(
            revision=m390_revision,
            owned_sources=_GUARDED_SOURCES,
            caller_binding_values={},
            caller_casilla_inputs={barred: Decimal("1.00")},
        )

    assert "44" not in _source_owned_bound_casilla_ids(m303_revision, _GUARDED_SOURCES)
    _reject_caller_overrides_of_source_bindings(
        revision=m303_revision,
        owned_sources=_GUARDED_SOURCES,
        caller_binding_values={},
        caller_casilla_inputs={"44": Decimal("1.00")},
    )
