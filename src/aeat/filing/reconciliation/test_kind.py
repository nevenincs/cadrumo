"""Unit tests for :mod:`aeat.filing.reconciliation._kind`.

Locks the closed-enum surface — every variant the ADR catalogues is
declared and round-trips via :class:`enum.StrEnum`. Also asserts the
disjoint-vocabulary invariant: no member of
:class:`FilingDivergenceKind` collides with any member of
:class:`aeat.sync.DivergenceKind`.
"""

from __future__ import annotations

import pytest

from ...sync import DivergenceKind
from ._kind import FilingDivergenceKind

pytestmark = [pytest.mark.unit, pytest.mark.domain_submission]


_EXPECTED_VARIANTS: frozenset[str] = frozenset(
    {
        "casilla_value_mismatch",
        "casilla_missing_local",
        "casilla_extra_local",
        "filing_status_divergence",
        "rounding_only",
        "filing_not_yet_found",
    }
)


def test_filing_divergence_kind_carries_exactly_six_variants() -> None:
    actual = {member.value for member in FilingDivergenceKind}
    assert actual == _EXPECTED_VARIANTS


def test_filing_divergence_kind_round_trips_via_strenum() -> None:
    for member in FilingDivergenceKind:
        assert FilingDivergenceKind(member.value) is member


def test_filing_divergence_kind_is_strenum() -> None:
    for member in FilingDivergenceKind:
        assert isinstance(member, str)


def test_filing_divergence_kind_disjoint_from_sync_divergence_kind() -> None:
    """The reconciliation enum and the sync enum share zero string values."""
    sync_values = {member.value for member in DivergenceKind}
    reconcile_values = {member.value for member in FilingDivergenceKind}
    assert sync_values.isdisjoint(reconcile_values)
