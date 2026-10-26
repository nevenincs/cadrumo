"""Previous-filing period-offset anchor regression.

The offset arithmetic is shared: a previous-filing binding and a
relation-prefill fold both state their source window through the same closed
temporal member, and both derive anchors through that member rather than
through a family-private helper. These tests lock the anchor the offset member
yields for a recognised period, and the diagnostic context it attaches when the
target period code cannot be interpreted at all.
"""

from __future__ import annotations

import pytest

from .....core.casilla_id import validated_casilla_id
from ..binding_temporal import TargetPeriodOffset
from ..bindings_previous_filing import PreviousFilingProvider
from ..errors import RegistryValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _provider() -> PreviousFilingProvider:
    """Return a previous-filing provider carrying a one-period backward offset."""
    return PreviousFilingProvider(
        source_modelo="303",
        temporal=TargetPeriodOffset(periods=-1),
        source_casilla_id=validated_casilla_id("01", surface="_provider"),
    )


def test_offset_resolves_recognised_quarterly_period() -> None:
    """A recognised quarterly target resolves to the prior-quarter anchor."""

    assert _provider().required_period_anchors_for_target("1T") == ((-1, "4T"),)


def test_uninterpretable_period_raises_with_offset_member_context() -> None:
    """An un-interpretable target period raises naming the member that refused it.

    The bare arithmetic message alone would not say which declaration axis
    rejected the code. The offset member re-wraps it with its own identity and
    the offending period, so an operator can locate the declaration rather than
    only the arithmetic.
    """

    with pytest.raises(RegistryValidationError, match="target_period_offset cannot interpret the target period"):
        _provider().required_period_anchors_for_target("ANUAL")
