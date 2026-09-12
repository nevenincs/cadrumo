"""An override keying no binding of the revision is advised, never silently dropped.

The relation channel is keyed by binding id since relations were absorbed into
binding providers. An override under any other key -- a retired pre-absorption
relation id above all -- is merged into a channel nothing reads and disappears
without a word, which is exactly the shape of a silent under-declaration: the
operator entered a figure, the result does not contain it, and the output alone
cannot distinguish that from the figure never having been entered.

The suite pairs each positive with its negative. The advisory must fire on the
orphan AND stay silent on a key the revision really declares, because a
diagnostic that fires on everything trains an operator to ignore the channel and
is no better than one that fires on nothing.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....domain.calculations.registry.authority import bundled_authority
from ..calculation_actions import _orphaned_override_diagnostics

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ORPHANED_KEY = "modelo-303-rel-self-compensacion-anteriores"
"""A retired pre-absorption relation id: the concrete key a stored override
carries after the cut, and the one this advisory exists for."""


def _m303_revision():
    """Return the live Modelo 303 revision, not a stand-in for one."""
    return bundled_authority().snapshot("303", filing_year=2026, period="1T").revision


def test_retired_relation_key_surfaces_a_structured_advisory() -> None:
    """An override under a key no binding carries is reported, with its key named."""
    revision = _m303_revision()
    assert _ORPHANED_KEY not in {binding.id for binding in revision.bindings}

    (diagnostic,) = _orphaned_override_diagnostics(
        revision,
        caller_relation_values={_ORPHANED_KEY: Decimal("50.00")},
    )

    assert diagnostic.reason == "orphaned_override"
    assert diagnostic.relation_id == _ORPHANED_KEY
    assert _ORPHANED_KEY in diagnostic.message
    assert diagnostic.remedy is not None


def test_override_on_a_declared_binding_raises_nothing() -> None:
    """The advisory stays silent on the ordinary case it must not crowd out."""
    revision = _m303_revision()
    declared = next(
        binding.id for binding in revision.bindings if binding.id == "modelo-303-compensacion-pendiente-anteriores"
    )

    assert (
        _orphaned_override_diagnostics(
            revision,
            caller_relation_values={declared: Decimal("50.00")},
        )
        == ()
    )


def test_no_overrides_raise_nothing() -> None:
    """An empty override channel is not a gap and produces no advisory."""
    assert _orphaned_override_diagnostics(_m303_revision(), caller_relation_values={}) == ()
