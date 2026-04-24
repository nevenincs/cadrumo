"""Unit tests for :func:`aeat.filing.reconciliation.reconcile`.

Exhaustively walks the decision table the ADR locks: the terminal
triad (``MATCH`` / ``DIVERGENT`` / ``NOT_YET_FOUND``) crossed with
each of the six :class:`FilingDivergenceKind` variants and the
rounding edge cases (exact-on-tolerance, one-cent-over,
one-cent-under, negative delta, zero-on-both-sides).

No mocks. Every collaborator is a real strict-pydantic record built
inline; the comparator is pure so no I/O seam needs faking. The
deterministic timestamp seam is the ``now`` keyword on
:func:`reconcile`.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ...remote import (
    RemoteCasilla,
    RemoteFiling,
    RemoteFilingStatus,
)
from ...schema import CasillaDataType
from .._schema import (
    FilingDraft,
    FilingDraftStatus,
    FilingScalar,
    FilingValue,
    FilingValueKind,
)
from ._kind import FilingDivergenceKind
from ._reconcile import reconcile
from ._schema import (
    CasillaDelta,
    ReconciliationReport,
    ReconciliationStatus,
)
from ._tolerance import RECONCILIATION_TOLERANCE

pytestmark = [pytest.mark.unit, pytest.mark.domain_submission]


_FROZEN_NOW = datetime(2026, 4, 24, 12, 0, tzinfo=UTC)


def _frozen_now() -> Callable[[], datetime]:
    return lambda: _FROZEN_NOW


def _draft(
    *,
    values: tuple[FilingValue, ...] = (),
    status: FilingDraftStatus = FilingDraftStatus.APPROVED,
    modelo: str = "303",
    period: str = "2026-1T",
) -> FilingDraft:
    """Build a strict :class:`FilingDraft` with deterministic identity."""
    return FilingDraft(
        draft_id="draft-001",
        modelo=modelo,
        period=period,
        profile_tax_id="00000000T",
        status=status,
        values=values,
        findings=(),
        created_at=_FROZEN_NOW,
        updated_at=_FROZEN_NOW,
        schema_version="filing-schema-0.1.0",
    )


def _value(casilla_id: str, value: FilingScalar) -> FilingValue:
    return FilingValue(
        casilla_id=casilla_id,
        value=value,
        kind=FilingValueKind.LITERAL,
        source="test",
    )


def _casilla(
    casilla_id: str,
    raw: str,
    coerced: Decimal | str | bool | None,
) -> RemoteCasilla:
    return RemoteCasilla(
        casilla_id=casilla_id,
        raw_value=raw,
        data_type=CasillaDataType.CURRENCY_EUR,
        coerced_value=coerced,
    )


def _filing(
    *,
    casillas: tuple[RemoteCasilla, ...],
    status: RemoteFilingStatus = RemoteFilingStatus.PRESENTADA,
    raw_status: str = "Presentada",
    modelo: str = "303",
    period: str = "2026-1T",
) -> RemoteFiling:
    return RemoteFiling(
        modelo=modelo,
        period=period,
        expediente_id="EXP-001",
        status=status,
        raw_status=raw_status,
        submitted_at=_FROZEN_NOW,
        casillas=casillas,
    )


# --- NOT_YET_FOUND --------------------------------------------------------


def test_remote_none_emits_not_yet_found() -> None:
    report = reconcile(_draft(), None, now=_frozen_now())
    assert report.status is ReconciliationStatus.NOT_YET_FOUND
    assert len(report.casilla_deltas) == 1
    sentinel = report.casilla_deltas[0]
    assert sentinel.kind is FilingDivergenceKind.FILING_NOT_YET_FOUND
    assert sentinel.casilla_id == "*"
    assert report.remote_ref is None
    assert report.draft_ref.draft_id == "draft-001"
    assert report.reconciled_at == _FROZEN_NOW


def test_remote_none_narrative_is_trilingual() -> None:
    report = reconcile(_draft(), None, now=_frozen_now())
    for lang in ("es", "en", "hu"):
        assert report.narrative.get(lang)


# --- MATCH (exact + rounding-only) ---------------------------------------


def test_match_zero_deltas() -> None:
    """Local and remote agree byte-for-byte on every casilla."""
    draft = _draft(values=(_value("46", Decimal("1234.56")),))
    filing = _filing(casillas=(_casilla("46", "1234.56", Decimal("1234.56")),))
    report = reconcile(draft, filing, now=_frozen_now())
    assert report.status is ReconciliationStatus.MATCH
    assert report.casilla_deltas == ()
    assert report.remote_ref is not None
    assert report.remote_ref.expediente_id == "EXP-001"


def test_rounding_only_classifies_as_match() -> None:
    """Sub-tolerance delta produces a ROUNDING_ONLY entry that does not flip status."""
    draft = _draft(values=(_value("46", Decimal("1234.56")),))
    filing = _filing(casillas=(_casilla("46", "1234.55", Decimal("1234.55")),))
    report = reconcile(draft, filing, now=_frozen_now())
    assert report.status is ReconciliationStatus.MATCH
    assert len(report.casilla_deltas) == 1
    assert report.casilla_deltas[0].kind is FilingDivergenceKind.ROUNDING_ONLY


def test_rounding_only_at_exact_tolerance_boundary_classifies_as_match() -> None:
    """``abs(delta) == tolerance`` lands as ROUNDING_ONLY (inclusive boundary)."""
    draft = _draft(values=(_value("46", Decimal("1234.56")),))
    filing = _filing(casillas=(_casilla("46", "1234.55", Decimal("1234.55")),))
    report = reconcile(draft, filing, tolerance=RECONCILIATION_TOLERANCE, now=_frozen_now())
    assert report.status is ReconciliationStatus.MATCH


def test_rounding_only_one_cent_over_tolerance_classifies_as_value_mismatch() -> None:
    draft = _draft(values=(_value("46", Decimal("1234.58")),))
    filing = _filing(casillas=(_casilla("46", "1234.56", Decimal("1234.56")),))
    report = reconcile(draft, filing, now=_frozen_now())
    assert report.status is ReconciliationStatus.DIVERGENT
    assert report.casilla_deltas[0].kind is FilingDivergenceKind.CASILLA_VALUE_MISMATCH


def test_negative_delta_within_tolerance_classifies_as_match() -> None:
    draft = _draft(values=(_value("46", Decimal("1234.55")),))
    filing = _filing(casillas=(_casilla("46", "1234.56", Decimal("1234.56")),))
    report = reconcile(draft, filing, now=_frozen_now())
    assert report.status is ReconciliationStatus.MATCH


def test_negative_delta_outside_tolerance_classifies_as_divergent() -> None:
    draft = _draft(values=(_value("46", Decimal("1234.50")),))
    filing = _filing(casillas=(_casilla("46", "1234.56", Decimal("1234.56")),))
    report = reconcile(draft, filing, now=_frozen_now())
    assert report.status is ReconciliationStatus.DIVERGENT
    delta = report.casilla_deltas[0]
    assert delta.kind is FilingDivergenceKind.CASILLA_VALUE_MISMATCH
    assert delta.delta == Decimal("-0.06")


def test_zero_on_both_sides_does_not_surface_a_delta() -> None:
    draft = _draft(values=(_value("46", Decimal("0")),))
    filing = _filing(casillas=(_casilla("46", "0", Decimal("0")),))
    report = reconcile(draft, filing, now=_frozen_now())
    assert report.status is ReconciliationStatus.MATCH
    assert report.casilla_deltas == ()


# --- DIVERGENT (each kind individually) ----------------------------------


def test_value_mismatch_outside_tolerance() -> None:
    """One-euro error on casilla 46 surfaces as a DIVERGENT report."""
    draft = _draft(values=(_value("46", Decimal("1234.56")),))
    filing = _filing(casillas=(_casilla("46", "1235.56", Decimal("1235.56")),))
    report = reconcile(draft, filing, now=_frozen_now())
    assert report.status is ReconciliationStatus.DIVERGENT
    assert len(report.casilla_deltas) == 1
    delta = report.casilla_deltas[0]
    assert delta.kind is FilingDivergenceKind.CASILLA_VALUE_MISMATCH
    assert delta.casilla_id == "46"
    assert delta.local_value == "1234.56"
    assert delta.remote_value == "1235.56"
    assert delta.delta == Decimal("-1.00")


def test_casilla_missing_local() -> None:
    """AEAT reports a casilla the local draft never set."""
    draft = _draft(values=())
    filing = _filing(casillas=(_casilla("46", "100.00", Decimal("100.00")),))
    report = reconcile(draft, filing, now=_frozen_now())
    assert report.status is ReconciliationStatus.DIVERGENT
    delta = next(d for d in report.casilla_deltas if d.kind is FilingDivergenceKind.CASILLA_MISSING_LOCAL)
    assert delta.casilla_id == "46"
    assert delta.local_value is None
    assert delta.remote_value == "100.00"
    assert delta.delta is None


def test_casilla_extra_local() -> None:
    """Local draft has a value AEAT does not report."""
    draft = _draft(values=(_value("46", Decimal("100.00")),))
    filing = _filing(casillas=())
    report = reconcile(draft, filing, now=_frozen_now())
    assert report.status is ReconciliationStatus.DIVERGENT
    delta = next(d for d in report.casilla_deltas if d.kind is FilingDivergenceKind.CASILLA_EXTRA_LOCAL)
    assert delta.casilla_id == "46"
    assert delta.local_value == "100.00"
    assert delta.remote_value is None


def test_filing_status_divergence_when_remote_is_rechazada() -> None:
    """Remote ``RECHAZADA`` against local ``APPROVED`` flags the divergence."""
    draft = _draft(values=(), status=FilingDraftStatus.APPROVED)
    filing = _filing(
        casillas=(),
        status=RemoteFilingStatus.RECHAZADA,
        raw_status="Rechazada",
    )
    report = reconcile(draft, filing, now=_frozen_now())
    assert report.status is ReconciliationStatus.DIVERGENT
    assert any(d.kind is FilingDivergenceKind.FILING_STATUS_DIVERGENCE for d in report.casilla_deltas)


def test_filing_status_divergence_when_remote_is_unknown() -> None:
    draft = _draft(values=(), status=FilingDraftStatus.APPROVED)
    filing = _filing(
        casillas=(),
        status=RemoteFilingStatus.UNKNOWN,
        raw_status="MysteryStatus",
    )
    report = reconcile(draft, filing, now=_frozen_now())
    assert report.status is ReconciliationStatus.DIVERGENT
    assert any(d.kind is FilingDivergenceKind.FILING_STATUS_DIVERGENCE for d in report.casilla_deltas)


def test_filing_status_divergence_when_local_is_pre_upload() -> None:
    """Pre-upload local statuses (DRAFT) flag any remote presence as divergent."""
    draft = _draft(values=(), status=FilingDraftStatus.DRAFT)
    filing = _filing(casillas=())
    report = reconcile(draft, filing, now=_frozen_now())
    assert report.status is ReconciliationStatus.DIVERGENT
    assert any(d.kind is FilingDivergenceKind.FILING_STATUS_DIVERGENCE for d in report.casilla_deltas)


def test_no_filing_status_divergence_when_states_align() -> None:
    """``APPROVED`` against ``PRESENTADA`` does not produce a status divergence."""
    draft = _draft(values=(), status=FilingDraftStatus.APPROVED)
    filing = _filing(casillas=(), status=RemoteFilingStatus.PRESENTADA)
    report = reconcile(draft, filing, now=_frozen_now())
    assert report.status is ReconciliationStatus.MATCH
    assert not any(d.kind is FilingDivergenceKind.FILING_STATUS_DIVERGENCE for d in report.casilla_deltas)


# --- Multi-divergence aggregation ----------------------------------------


def test_mixed_divergences_aggregate_to_divergent() -> None:
    """Multiple divergences on different kinds compose into a single DIVERGENT report."""
    draft = _draft(
        values=(
            _value("46", Decimal("1234.56")),
            _value("71", Decimal("100.00")),
        )
    )
    filing = _filing(
        casillas=(
            _casilla("46", "1300.00", Decimal("1300.00")),
            _casilla("73", "200.00", Decimal("200.00")),
        ),
    )
    report = reconcile(draft, filing, now=_frozen_now())
    assert report.status is ReconciliationStatus.DIVERGENT
    kinds = {d.kind for d in report.casilla_deltas}
    assert FilingDivergenceKind.CASILLA_VALUE_MISMATCH in kinds
    assert FilingDivergenceKind.CASILLA_EXTRA_LOCAL in kinds
    assert FilingDivergenceKind.CASILLA_MISSING_LOCAL in kinds


def test_rounding_plus_value_mismatch_remains_divergent() -> None:
    draft = _draft(
        values=(
            _value("46", Decimal("1234.55")),  # rounding-only against 1234.56
            _value("71", Decimal("100.00")),
        )
    )
    filing = _filing(
        casillas=(
            _casilla("46", "1234.56", Decimal("1234.56")),
            _casilla("71", "200.00", Decimal("200.00")),  # value mismatch
        ),
    )
    report = reconcile(draft, filing, now=_frozen_now())
    assert report.status is ReconciliationStatus.DIVERGENT
    kinds = {d.kind for d in report.casilla_deltas}
    assert FilingDivergenceKind.ROUNDING_ONLY in kinds
    assert FilingDivergenceKind.CASILLA_VALUE_MISMATCH in kinds


# --- Determinism / ordering ----------------------------------------------


def test_deltas_are_emitted_in_canonical_casilla_order() -> None:
    """Per-casilla deltas walk in lexicographic id order for stable diffs."""
    draft = _draft(
        values=(
            _value("71", Decimal("999.00")),
            _value("46", Decimal("1234.56")),
        )
    )
    filing = _filing(
        casillas=(
            _casilla("46", "1300.00", Decimal("1300.00")),
            _casilla("71", "100.00", Decimal("100.00")),
        ),
    )
    report = reconcile(draft, filing, now=_frozen_now())
    casilla_deltas = [d for d in report.casilla_deltas if d.casilla_id != "*"]
    ids = [d.casilla_id for d in casilla_deltas]
    assert ids == sorted(ids)


def test_report_is_a_frozen_record() -> None:
    """The :class:`ReconciliationReport` is a frozen pydantic record."""
    report = reconcile(_draft(), None, now=_frozen_now())
    with pytest.raises(ValidationError):
        report.status = ReconciliationStatus.MATCH  # type: ignore[misc]


def test_round_trips_via_model_dump() -> None:
    """The report serialises and re-validates losslessly."""
    report = reconcile(_draft(), None, now=_frozen_now())
    assert ReconciliationReport.model_validate(report.model_dump()) == report


# --- Local-empty values are skipped --------------------------------------


def test_empty_local_values_are_skipped() -> None:
    """``FilingValueKind.EMPTY`` entries do not surface as ``CASILLA_EXTRA_LOCAL``."""
    empty = FilingValue(
        casilla_id="46",
        value=None,
        kind=FilingValueKind.EMPTY,
        source="default",
    )
    draft = _draft(values=(empty,))
    filing = _filing(casillas=())
    report = reconcile(draft, filing, now=_frozen_now())
    assert report.status is ReconciliationStatus.MATCH
    assert report.casilla_deltas == ()


# --- Sanity check on CasillaDelta fields ---------------------------------


def test_value_mismatch_delta_carries_signed_decimal() -> None:
    draft = _draft(values=(_value("46", Decimal("100.00")),))
    filing = _filing(casillas=(_casilla("46", "150.00", Decimal("150.00")),))
    report = reconcile(draft, filing, now=_frozen_now())
    delta_record = next(d for d in report.casilla_deltas if d.kind is FilingDivergenceKind.CASILLA_VALUE_MISMATCH)
    assert isinstance(delta_record, CasillaDelta)
    assert delta_record.delta == Decimal("-50.00")
