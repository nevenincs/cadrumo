"""Adversarial red-team of the same-year local-chain relaxation safety boundary.

These tests actively try to launder a bad cross-period chain through the same-year
admission. Each case that should STAY BLOCKING must not relax; a single relaxed
bad case would be a real under-declaration / laundering hole.
"""

from __future__ import annotations

import pytest

from ....core import Period
from .._cross_period_clean_state import (
    _OFFICIAL_EVIDENCE_DELTA_BLOCKERS,
    _relax_same_year_local_chain,
    CrossPeriodCleanStateBlocker,
    CrossPeriodDependencyEvidence,
    CrossPeriodDependencyOrigin,
    CrossPeriodDependencyRequirement,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_DELTA = tuple(_OFFICIAL_EVIDENCE_DELTA_BLOCKERS)


def _evidence(*, filing_year: int, source_kind: str | None, blockers: tuple) -> CrossPeriodDependencyEvidence:
    req = CrossPeriodDependencyRequirement(
        source_modelo="130",
        filing_year=filing_year,
        period=Period.from_year_and_code(filing_year, "1T"),
        source_casillas=("19",),
        origin=CrossPeriodDependencyOrigin.PREVIOUS_FILING_BINDING,
        origin_ids=("modelo-130-pagos-fraccionados-anteriores",),
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


@pytest.mark.parametrize(
    "extra",
    [
        CrossPeriodCleanStateBlocker.OPERATOR_MANUAL_SOURCE,
        CrossPeriodCleanStateBlocker.OBSERVATION_REVISION_VALUE_DIVERGENCE,
        CrossPeriodCleanStateBlocker.REGISTRY_REVISION_DIVERGENCE,
        CrossPeriodCleanStateBlocker.MISSING_OBSERVED_CASILLA,
        CrossPeriodCleanStateBlocker.MISSING_CURRENT_FILING_RECORD,
        CrossPeriodCleanStateBlocker.UNFILED_CALCULATION_REVISION,
        CrossPeriodCleanStateBlocker.MISSING_COMPLETE_VERIFICATION_REPORT,
        CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD,
    ],
)
def test_same_year_app_filing_with_extra_blocker_stays_blocking(extra) -> None:
    """ATTACK: a same-year app_filing chain with ANY non-delta blocker must NOT relax.

    A value divergence, operator-manual source, revision divergence, or missing
    record is a genuine defect; relaxing it would launder a corrupt chain.
    """
    ev = _evidence(filing_year=2026, source_kind="app_filing", blockers=(*_DELTA, extra))
    out = _relax_same_year_local_chain(ev, target_filing_year=2026)
    assert not out.clean, f"{extra.value} must keep the row blocking"
    assert not out.non_official_local_chain_advisory
    assert extra in out.blockers


def test_cross_year_app_filing_stays_blocking() -> None:
    """ATTACK: a cross-year (prior-year) app_filing chain must NOT relax (anti-laundering)."""
    ev = _evidence(filing_year=2025, source_kind="app_filing", blockers=_DELTA)
    out = _relax_same_year_local_chain(ev, target_filing_year=2026)
    assert not out.clean
    assert not out.non_official_local_chain_advisory


@pytest.mark.parametrize("kind", ["operator_manual", "aeat_sede_justificante", "aeat_csv_register", None])
def test_non_app_filing_source_stays_blocking(kind) -> None:
    """ATTACK: only app_filing relaxes; operator_manual/official/None must NOT."""
    ev = _evidence(filing_year=2026, source_kind=kind, blockers=_DELTA)
    out = _relax_same_year_local_chain(ev, target_filing_year=2026)
    assert not out.non_official_local_chain_advisory


def test_clean_row_is_not_falsely_flagged() -> None:
    """A row with no blockers is returned unchanged (no spurious advisory)."""
    ev = _evidence(filing_year=2026, source_kind="app_filing", blockers=())
    out = _relax_same_year_local_chain(ev, target_filing_year=2026)
    assert out.clean
    assert not out.non_official_local_chain_advisory


# --- C3: modelo-not-applicable suppression safety boundary ---

from .._cross_period_clean_state import (  # noqa: E402
    _suppressed_modelo_not_applicable_evidence,
    partition_cross_period_requirements_by_modelo_applicability,
)


def _requirement(source_modelo: str) -> CrossPeriodDependencyRequirement:
    return CrossPeriodDependencyRequirement(
        source_modelo=source_modelo,
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        source_casillas=("01",),
        origin=CrossPeriodDependencyOrigin.PREVIOUS_FILING_BINDING,
        origin_ids=("b1",),
    )


def test_modelo_the_taxpayer_does_not_file_is_suppressed() -> None:
    """A dependency on a modelo absent from the applicable set is scoped out (not-applicable)."""
    reqs = (_requirement("111"), _requirement("130"))
    part = partition_cross_period_requirements_by_modelo_applicability(
        reqs, applicable_source_modelos=frozenset({"130"})
    )
    assert [r.source_modelo for r in part.in_scope] == ["130"]
    assert [r.source_modelo for r in part.suppressed] == ["111"]


def test_modelo_the_taxpayer_DOES_file_is_NEVER_suppressed() -> None:
    """SAFETY BOUNDARY: an applicable modelo must NEVER be scoped out (silent-under-declaration guard)."""
    for applicable in (frozenset({"130"}), frozenset({"130", "111"}), frozenset({"100", "130", "111", "115"})):
        part = partition_cross_period_requirements_by_modelo_applicability(
            (_requirement("130"),), applicable_source_modelos=applicable
        )
        assert [r.source_modelo for r in part.in_scope] == ["130"], applicable
        assert part.suppressed == ()


def test_none_applicable_set_suppresses_nothing() -> None:
    """``None`` means no applicability data -> every requirement stays in scope (fail-safe)."""
    reqs = (_requirement("111"), _requirement("130"))
    part = partition_cross_period_requirements_by_modelo_applicability(reqs, applicable_source_modelos=None)
    assert len(part.in_scope) == 2
    assert part.suppressed == ()


def test_not_applicable_evidence_is_clean_and_explicitly_flagged() -> None:
    """A suppressed not-applicable row is clean (no blockers) and carries the explicit advisory facet."""
    ev = _suppressed_modelo_not_applicable_evidence(_requirement("111"))
    assert ev.clean
    assert ev.blockers == ()
    assert ev.modelo_not_applicable_advisory
