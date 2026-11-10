"""A calculation input the filer supplied that contradicts its own sources is refused, not failed.

A box typed over a computed figure, a Modelo 210 income type chosen against
the ledger route, or detail rows that disagree with the rows the records give
are all the filer's to put right, so the calculation is refused before anything
is written. A resolver handoff the code itself wired wrongly is no input of the
filer's and stays a failure.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.errors.error_codes import ErrorCategory, get_registered_error_code
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ..action_errors import ModeloAggregationBindingError, ModeloAggregationInputConflictError
from ..calculation_bucket_actions import _merge_bucket_bound_inputs

pytestmark = [pytest.mark.usefixtures("authority_operation"), pytest.mark.unit, pytest.mark.hex_application]


def test_an_input_conflict_is_registered_as_a_refusal() -> None:
    """DISCRIMINATING: the supervisor settles a REFUSED registration as refused."""
    assert get_registered_error_code(ModeloAggregationInputConflictError).category is ErrorCategory.REFUSED
    assert issubclass(ModeloAggregationInputConflictError, ModeloAggregationBindingError)


def test_a_figure_typed_over_a_computed_box_is_an_input_conflict() -> None:
    revision = published_snapshot("303", filing_year=filing_year_envelope().horizon, period="1T").revision
    computed = next(casilla.id for casilla in revision.casillas if casilla.input_kind.value == "computed")

    with pytest.raises(ModeloAggregationInputConflictError) as refused:
        _merge_bucket_bound_inputs(revision=revision, casilla_inputs={}, bound_inputs={computed: Decimal("1")})

    assert get_registered_error_code(refused.value).category is ErrorCategory.REFUSED


def test_a_miswired_resolver_handoff_stays_a_failure() -> None:
    """ANTI-VACUITY: the base error, raised for wiring the filer never touches, stays ERROR."""
    assert get_registered_error_code(ModeloAggregationBindingError).category is ErrorCategory.ERROR
