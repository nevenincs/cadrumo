"""Parity tests for the single shared revision-carry gate.

The carry gate (period-revision-resolution-adr, Ruling 3 /
R2) was implemented across three carry-read sites:

- ``_binding_prefill._revision_carry_outcome`` (returns ``(diverges, advisory)``);
- ``_cross_period_clean_state._revision_carry_check`` (returns ``(blockers, advisory)``);
- ``_relation_prefill._gather_observations_for_snapshot`` (drops divergent priors).

They were later collapsed onto the one
``_revision_carry_gate.revision_carry_outcome`` implementation. These tests prove
the two adapter sites map the SAME shared decision onto their respective shapes
for every R2 outcome — matching, divergent, missing-stamp, and indeterminate —
so the gate cannot drift across the three sites again.

Real registry authority, real law-determined revision ids, no mocks.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....core import Period
from ....core.resources import resources
from ....domain.calculations.registry import CasillaObservation, RegistryModeloObservation
from .._binding_prefill import _revision_carry_outcome
from .._cross_period_clean_state import CrossPeriodCleanStateBlocker, _revision_carry_check
from .._observations_repository import _ObservationEnvelopePayload
from .._revision_carry_gate import revision_carry_outcome

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO = "303"
_YEAR = 2025
_PERIOD = "1T"
_CLOCK = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)
_FAKE_REVISION_ID = "definitely-not-the-right-revision-id-xyzzy"
_NONEXISTENT_MODELO = "999"


def _law_revision_id(modelo: str = _MODELO, year: int = _YEAR, period: str = _PERIOD) -> str:
    snapshot = resources().modelos.authority.snapshot(modelo, filing_year=year, period=period)
    return str(snapshot.revision.id)


def _observation(modelo: str = _MODELO, year: int = _YEAR, period: str = _PERIOD) -> RegistryModeloObservation:
    return RegistryModeloObservation(
        modelo=modelo,
        filing_year=year,
        period=period,
        observations=(CasillaObservation(casilla_id="c", value=Decimal("1")),),
    )


def _payload(stamped_revision_id: str | None, observation: RegistryModeloObservation) -> _ObservationEnvelopePayload:
    return _ObservationEnvelopePayload(
        observation=observation,
        captured_at=_CLOCK,
        source_kind="aeat_sede_justificante",
        stamped_revision_id=stamped_revision_id,
    )


def _binding_adapter_outcome(
    stamped_revision_id: str | None, observation: RegistryModeloObservation
) -> tuple[bool, bool]:
    """``(diverges, advisory)`` as the binding-prefill adapter reports it."""
    return _revision_carry_outcome(_payload(stamped_revision_id, observation))


def _cross_period_adapter_outcome(
    stamped_revision_id: str | None,
    *,
    modelo: str,
    year: int,
    period: str,
) -> tuple[bool, bool]:
    """``(diverges, advisory)`` reconstructed from the cross-period adapter's shape.

    The cross-period site maps a divergence onto a
    ``REGISTRY_REVISION_DIVERGENCE`` blocker; we invert that mapping to compare
    the underlying decision against the shared gate.
    """
    blockers, advisory = _revision_carry_check(
        stamped_revision_id,
        modelo,
        year,
        Period.from_year_and_code(year, period),
    )
    diverges = CrossPeriodCleanStateBlocker.REGISTRY_REVISION_DIVERGENCE in blockers
    return diverges, advisory


@pytest.mark.parametrize(
    "case",
    ["matching", "divergent", "missing", "indeterminate"],
)
def test_three_carry_sites_agree_via_shared_gate(case: str) -> None:
    """The binding-prefill and cross-period adapters report the shared decision.

    For each R2 case the shared ``revision_carry_outcome`` is the single source of
    truth; both adapters MUST surface the same ``(diverges, advisory)`` pair so the
    gate cannot drift across sites.
    """
    if case == "matching":
        stamp: str | None = _law_revision_id()
        modelo, year, period = _MODELO, _YEAR, _PERIOD
        expected = (False, False)
    elif case == "divergent":
        stamp = _FAKE_REVISION_ID
        modelo, year, period = _MODELO, _YEAR, _PERIOD
        expected = (True, False)
    elif case == "missing":
        stamp = None
        modelo, year, period = _MODELO, _YEAR, _PERIOD
        expected = (False, True)
    else:  # indeterminate: a source context the authority cannot resolve
        stamp = _FAKE_REVISION_ID
        modelo, year, period = _NONEXISTENT_MODELO, _YEAR, _PERIOD
        expected = (False, True)

    observation = _observation(modelo, year, period)

    shared = revision_carry_outcome(
        stamp,
        source_modelo=modelo,
        source_filing_year=year,
        source_period=period,
    )
    binding = _binding_adapter_outcome(stamp, observation)
    cross_period = _cross_period_adapter_outcome(stamp, modelo=modelo, year=year, period=period)

    assert shared == expected, f"shared gate disagreed with the spec for {case!r}"
    assert binding == expected, f"binding-prefill adapter diverged from the shared gate for {case!r}"
    assert cross_period == expected, f"cross-period adapter diverged from the shared gate for {case!r}"


def test_divergent_stamp_maps_to_registry_revision_divergence_blocker() -> None:
    """The cross-period adapter still raises the divergence blocker on a divergent stamp.

    Behaviour-preservation check: unification must not weaken the cross-period
    site's blocking semantics.
    """
    blockers, advisory = _revision_carry_check(
        _FAKE_REVISION_ID,
        _MODELO,
        _YEAR,
        Period.from_year_and_code(_YEAR, _PERIOD),
    )
    assert blockers == [CrossPeriodCleanStateBlocker.REGISTRY_REVISION_DIVERGENCE]
    assert advisory is False
