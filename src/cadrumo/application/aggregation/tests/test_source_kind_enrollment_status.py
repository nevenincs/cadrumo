"""Enrollment-status pins for the deferred binding source kinds.

A deferred kind is known to the closed taxonomy but has no live mesh resolver,
so it emits a standing calculate-path advisory rather than a silent blank. Once
a kind is promoted to a live resolver it must leave
:data:`DEFERRED_SOURCE_KINDS`, or the advisory would keep firing for a source
that now resolves.

The advisory floor itself (every deferred kind emits an
``unhandled_binding_source`` advisory and none sits on the manual-input
allowlist) is asserted against the calculate boundary in
``application/modelo/tests/test_deferred_detalle_source_advisories.py``.
"""

from __future__ import annotations

import pytest

from ....core import BindingSourceKind
from ...aggregation import DEFERRED_SOURCE_KINDS, BindingSourceDisposition
from ...modelo.calculation_route import CALCULATION_ROUTE_SOURCE_DISPOSITIONS

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_bienes_inversion_regularizacion_is_not_deferred_after_live_m303_promotion() -> None:
    """The casilla-43 source must not remain deferred after live M303 enrollment."""
    assert BindingSourceKind.BIENES_INVERSION_REGULARIZACION not in DEFERRED_SOURCE_KINDS


def test_inventory_is_enrolled_and_no_longer_deferred() -> None:
    """The route-derived disposition owns inventory's promoted status."""
    assert BindingSourceKind.INVENTORY not in DEFERRED_SOURCE_KINDS
    assert CALCULATION_ROUTE_SOURCE_DISPOSITIONS[BindingSourceKind.INVENTORY] is BindingSourceDisposition.ENROLLED
