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
from ...aggregation import DEFERRED_SOURCE_KINDS

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_bienes_inversion_regularizacion_is_not_deferred_after_live_m303_promotion() -> None:
    """The casilla-43 source must not remain deferred after live M303 enrollment."""
    assert BindingSourceKind.BIENES_INVERSION_REGULARIZACION not in DEFERRED_SOURCE_KINDS


def test_inventory_is_deferred_until_its_mesh_resolver_is_enrolled() -> None:
    """The canonical inventory source must not imply premature live routing."""
    assert BindingSourceKind.INVENTORY in DEFERRED_SOURCE_KINDS
