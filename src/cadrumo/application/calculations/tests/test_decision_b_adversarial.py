"""Adversarial red-team of the same-year local-chain relaxation safety boundary.

These tests actively try to launder a bad cross-period chain through the same-year
admission. Each case that should STAY BLOCKING must not relax; a single relaxed
bad case would be a real under-declaration / laundering hole.
"""

from __future__ import annotations

import pytest

from ....core.period import Period
from ....core.casilla_id import CasillaId, validated_casilla_id
from ..cross_period_clean_state import (
    _OFFICIAL_EVIDENCE_DELTA_BLOCKERS,
    CrossPeriodCleanStateBlocker,
    CrossPeriodDependencyEvidence,
    CrossPeriodDependencyOrigin,
    CrossPeriodDependencyRequirement,
    _relax_same_year_local_chain,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_DELTA: tuple[CrossPeriodCleanStateBlocker, ...] = tuple(_OFFICIAL_EVIDENCE_DELTA_BLOCKERS)
_M130_SOURCE_CASILLA_19: CasillaId = validated_casilla_id("19", surface="_M130_SOURCE_CASILLA_19")
_M130_REQUIREMENT_LEGAL_REFS = ("rd-439-2007:art-110",)
_M130_REQUIREMENT_SOURCE_REFS = ("aeat-modelo-130-instructions",)
_NON_DELTA_BLOCKERS: tuple[CrossPeriodCleanStateBlocker, ...] = (
    CrossPeriodCleanStateBlocker.OPERATOR_MANUAL_SOURCE,
    CrossPeriodCleanStateBlocker.OBSERVATION_REVISION_VALUE_DIVERGENCE,
    CrossPeriodCleanStateBlocker.REGISTRY_REVISION_DIVERGENCE,
    CrossPeriodCleanStateBlocker.MISSING_OBSERVED_CASILLA,
    CrossPeriodCleanStateBlocker.MISSING_CURRENT_FILING_RECORD,
    CrossPeriodCleanStateBlocker.UNFILED_CALCULATION_REVISION,
    CrossPeriodCleanStateBlocker.MISSING_COMPLETE_VERIFICATION_REPORT,
    CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD,
)
_NON_APP_SOURCE_KINDS: tuple[str | None, ...] = (
    "operator_manual",
    "aeat_sede_justificante",
    "aeat_csv_register",
    None,
)


def _evidence(
    *,
    filing_year: int,
    source_kind: str | None,
    blockers: tuple[CrossPeriodCleanStateBlocker, ...],
) -> CrossPeriodDependencyEvidence:
    req = CrossPeriodDependencyRequirement(
        source_modelo="130",
        filing_year=filing_year,
        period=Period.from_year_and_code(filing_year, "1T"),
        source_casilla_ids=(_M130_SOURCE_CASILLA_19,),
        origin=CrossPeriodDependencyOrigin.PREVIOUS_FILING_BINDING,
        origin_ids=("modelo-130-pagos-fraccionados-anteriores",),
        legal_refs=_M130_REQUIREMENT_LEGAL_REFS,
        source_refs=_M130_REQUIREMENT_SOURCE_REFS,
    )
    return CrossPeriodDependencyEvidence(
        requirement=req,
        observation_source_kind=source_kind,
        blockers=blockers,
    )


def test_same_year_app_filing_only_delta_is_admitted() -> None:
    """The legitimate case: same-year app_filing, only official-evidence delta -> admitted."""
    ev = _evidence(filing_year=2026, source_kind="app_filing", blockers=_DELTA)
    out = _relax_same_year_local_chain(ev, target_filing_year=2026)
    assert out.clean
    assert out.non_official_local_chain_advisory
    assert out.blockers == ()


def test_same_year_app_filing_with_extra_blocker_stays_blocking() -> None:
    """ATTACK: a same-year app_filing chain with ANY non-delta blocker must NOT relax.

    A value divergence, operator-manual source, revision divergence, or missing
    record is a genuine defect; relaxing it would launder a corrupt chain.
    """
    for extra in _NON_DELTA_BLOCKERS:
        ev = _evidence(filing_year=2026, source_kind="app_filing", blockers=(*_DELTA, extra))
        out = _relax_same_year_local_chain(ev, target_filing_year=2026)
        assert not out.clean, f"{extra.value} must keep the row blocking"
        assert not out.non_official_local_chain_advisory, extra.value
        assert extra in out.blockers, extra.value


def test_cross_year_app_filing_stays_blocking() -> None:
    """ATTACK: a cross-year (prior-year) app_filing chain must NOT relax (anti-laundering)."""
    ev = _evidence(filing_year=2025, source_kind="app_filing", blockers=_DELTA)
    out = _relax_same_year_local_chain(ev, target_filing_year=2026)
    assert not out.clean
    assert not out.non_official_local_chain_advisory


def test_non_app_filing_source_stays_blocking() -> None:
    """ATTACK: only app_filing relaxes; operator_manual/official/None must NOT."""
    for kind in _NON_APP_SOURCE_KINDS:
        ev = _evidence(filing_year=2026, source_kind=kind, blockers=_DELTA)
        out = _relax_same_year_local_chain(ev, target_filing_year=2026)
        assert not out.non_official_local_chain_advisory, kind


def test_clean_row_is_not_falsely_flagged() -> None:
    """A row with no blockers is returned unchanged (no spurious advisory)."""
    ev = _evidence(filing_year=2026, source_kind="app_filing", blockers=())
    out = _relax_same_year_local_chain(ev, target_filing_year=2026)
    assert out.clean
    assert not out.non_official_local_chain_advisory
