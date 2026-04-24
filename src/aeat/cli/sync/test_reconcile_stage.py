"""Unit tests for the Phase-5 reconcile stage (#239).

No mocks. Every collaborator is a strict pydantic record built inline
or a real Protocol-conforming Python class. The suite exercises the
pure stage surface: APPROVED-only gating, session reuse across
multiple ``(modelo, period)`` pairs, ``NOT_YET_FOUND`` summary
surfacing, and persistence of ``DIVERGENT`` / ``NOT_YET_FOUND`` reports
through the Phase-3 wrapping record.
"""

from __future__ import annotations

import asyncio
import io
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Final

import pytest
from rich.console import Console

from ...filing import (
    FilingDraft,
    FilingDraftStatus,
    FilingValue,
    FilingValueKind,
)
from ...filing.reconciliation import (
    FilingDivergenceKind,
    FilingReconciliationDivergenceRecord,
)
from ...remote import (
    RemoteCasilla,
    RemoteFiling,
    RemoteFilingStatus,
)
from ...schema import CasillaDataType
from ._reconcile_stage import (
    ReconcileStageSummary,
    emit_reconcile_summary,
    iter_approved_drafts,
    run_reconcile_stage,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_infra]


_FROZEN_NOW: Final[datetime] = datetime(2026, 4, 24, 12, 0, tzinfo=UTC)


def _frozen_now() -> datetime:
    return _FROZEN_NOW


def _build_draft(
    *,
    draft_id: str,
    modelo: str = "303",
    period: str = "2025-1T",
    status: FilingDraftStatus = FilingDraftStatus.APPROVED,
    values: tuple[FilingValue, ...] = (),
) -> FilingDraft:
    """Build a deterministic draft for stage tests."""
    return FilingDraft(
        draft_id=draft_id,
        modelo=modelo,
        period=period,
        profile_tax_id="00000000T",
        status=status,
        values=values,
        findings=(),
        created_at=_FROZEN_NOW,
        updated_at=_FROZEN_NOW,
        approved_at=_FROZEN_NOW if status is FilingDraftStatus.APPROVED else None,
        approved_by="kent" if status is FilingDraftStatus.APPROVED else None,
        schema_version="filing-schema-0.1.0",
    )


def _value(casilla_id: str, value: Decimal) -> FilingValue:
    return FilingValue(
        casilla_id=casilla_id,
        value=value,
        kind=FilingValueKind.LITERAL,
        source="user-supplied",
    )


def _remote_filing(
    *,
    modelo: str = "303",
    period: str = "2025-1T",
    status: RemoteFilingStatus = RemoteFilingStatus.PRESENTADA,
    raw_status: str = "Presentada",
    casillas: tuple[RemoteCasilla, ...] = (),
) -> RemoteFiling:
    return RemoteFiling(
        modelo=modelo,
        period=period,
        expediente_id=f"exp-{modelo}-{period}",
        status=status,
        raw_status=raw_status,
        submitted_at=_FROZEN_NOW,
        casillas=casillas,
        receipts=(),
        complementaria_of=None,
    )


def _remote_casilla(casilla_id: str, value: Decimal) -> RemoteCasilla:
    return RemoteCasilla(
        casilla_id=casilla_id,
        raw_value=format(value, "f"),
        data_type=CasillaDataType.CURRENCY_EUR,
        coerced_value=value,
    )


def _write_draft(drafts_dir: Path, draft: FilingDraft) -> Path:
    """Persist a draft to the canonical ``{modelo}_{period}_{id}.json`` path."""
    path = drafts_dir / f"{draft.modelo}_{draft.period}_{draft.draft_id}.json"
    path.write_text(draft.model_dump_json(indent=2), encoding="utf-8")
    return path


class _SessionCountingFetcher:
    """Protocol-conforming fetcher that tracks instantiation and call counts.

    Unit tests assert there is one instance per stage invocation (session
    reuse) and one call per ``(modelo, period)`` pair.
    """

    _instance_counter = 0

    def __init__(self, filings: tuple[RemoteFiling, ...]) -> None:
        type(self)._instance_counter += 1
        self._filings = filings
        self.calls: list[tuple[str, str]] = []

    async def fetch_filing_detail(
        self,
        modelo: str,
        period: str,
        *,
        use_cache: bool = True,
    ) -> tuple[RemoteFiling, ...]:
        _ = use_cache
        self.calls.append((modelo, period))
        return tuple(f for f in self._filings if f.modelo == modelo and f.period == period)

    @classmethod
    def reset_counter(cls) -> None:
        cls._instance_counter = 0

    @classmethod
    def instance_count(cls) -> int:
        return cls._instance_counter


class _CapturingSink:
    """Protocol-conforming reconciliation sink that records every save."""

    def __init__(self) -> None:
        self.saved: list[FilingReconciliationDivergenceRecord] = []

    def save(self, record: FilingReconciliationDivergenceRecord) -> None:
        self.saved.append(record)


@pytest.fixture
def drafts_dir(tmp_path: Path) -> Path:
    target = tmp_path / "drafts"
    target.mkdir()
    return target


def _run(
    *,
    drafts_dir: Path,
    fetcher: _SessionCountingFetcher,
    sink: _CapturingSink,
    now: Callable[[], datetime] = _frozen_now,
) -> ReconcileStageSummary:
    summary, _reports = asyncio.run(
        run_reconcile_stage(
            drafts_dir=drafts_dir,
            fetcher=fetcher,
            sink=sink,
            now=now,
        )
    )
    return summary


class TestApprovedGating:
    """Only ``FilingDraftStatus.APPROVED`` drafts reconcile; every other is skipped."""

    def test_approved_draft_reconciles(self, drafts_dir: Path) -> None:
        draft = _build_draft(draft_id="d-approved", values=(_value("01", Decimal("100.00")),))
        _write_draft(drafts_dir, draft)
        filing = _remote_filing(casillas=(_remote_casilla("01", Decimal("100.00")),))
        fetcher = _SessionCountingFetcher(filings=(filing,))
        sink = _CapturingSink()

        summary = _run(drafts_dir=drafts_dir, fetcher=fetcher, sink=sink)

        assert summary.total_considered == 1
        assert summary.skipped_count == 0
        assert summary.match_count == 1
        assert fetcher.calls == [(draft.modelo, draft.period)]
        assert sink.saved == []

    @pytest.mark.parametrize(
        "status",
        [s for s in FilingDraftStatus if s is not FilingDraftStatus.APPROVED],
    )
    def test_non_approved_draft_is_skipped(
        self,
        drafts_dir: Path,
        status: FilingDraftStatus,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        draft = _build_draft(draft_id=f"d-{status.value}", status=status)
        _write_draft(drafts_dir, draft)
        fetcher = _SessionCountingFetcher(filings=())
        sink = _CapturingSink()

        with caplog.at_level(logging.INFO, logger="aeat.cli.sync._reconcile_stage"):
            summary = _run(drafts_dir=drafts_dir, fetcher=fetcher, sink=sink)

        assert summary.total_considered == 1
        assert summary.skipped_count == 1
        assert summary.match_count == 0
        assert summary.divergent_count == 0
        assert summary.not_yet_found_count == 0
        assert fetcher.calls == []
        assert sink.saved == []
        # INFO-level log surfaces the skip with the correct status context.
        assert any(
            "is not APPROVED" in record.getMessage() and status.value in record.getMessage()
            for record in caplog.records
        )

    def test_iter_approved_drafts_filters_directly(self, drafts_dir: Path) -> None:
        approved = _build_draft(draft_id="a", status=FilingDraftStatus.APPROVED)
        draft = _build_draft(draft_id="d", status=FilingDraftStatus.DRAFT)
        submitted = _build_draft(draft_id="s", status=FilingDraftStatus.SUBMITTED)
        _write_draft(drafts_dir, approved)
        _write_draft(drafts_dir, draft)
        _write_draft(drafts_dir, submitted)

        found = list(iter_approved_drafts(drafts_dir))

        assert len(found) == 1
        assert found[0].draft_id == "a"

    def test_mixed_approved_and_non_approved_drafts(self, drafts_dir: Path) -> None:
        approved = _build_draft(draft_id="ok", values=(_value("01", Decimal("50.00")),))
        _write_draft(drafts_dir, approved)
        other = _build_draft(draft_id="pending", status=FilingDraftStatus.READY_TO_SUBMIT)
        _write_draft(drafts_dir, other)
        filing = _remote_filing(casillas=(_remote_casilla("01", Decimal("50.00")),))
        fetcher = _SessionCountingFetcher(filings=(filing,))
        sink = _CapturingSink()

        summary = _run(drafts_dir=drafts_dir, fetcher=fetcher, sink=sink)

        assert summary.total_considered == 2
        assert summary.skipped_count == 1
        assert summary.match_count == 1
        assert fetcher.calls == [(approved.modelo, approved.period)]


class TestSessionReuse:
    """One fetcher instance backs every ``(modelo, period)`` in a single pass."""

    def test_single_fetcher_services_multiple_modelo_period_pairs(
        self,
        drafts_dir: Path,
    ) -> None:
        _SessionCountingFetcher.reset_counter()
        drafts = (
            _build_draft(draft_id="d1", modelo="303", period="2025-1T"),
            _build_draft(draft_id="d2", modelo="130", period="2025-1T"),
            _build_draft(draft_id="d3", modelo="303", period="2025-2T"),
        )
        for draft in drafts:
            _write_draft(drafts_dir, draft)
        filings = (
            _remote_filing(modelo="303", period="2025-1T"),
            _remote_filing(modelo="130", period="2025-1T"),
            _remote_filing(modelo="303", period="2025-2T"),
        )
        fetcher = _SessionCountingFetcher(filings=filings)
        sink = _CapturingSink()

        summary = _run(drafts_dir=drafts_dir, fetcher=fetcher, sink=sink)

        # Exactly one fetcher instance across the whole pass — session reuse.
        assert _SessionCountingFetcher.instance_count() == 1
        # The fetcher fielded one call per ``(modelo, period)`` pair.
        assert sorted(fetcher.calls) == [
            ("130", "2025-1T"),
            ("303", "2025-1T"),
            ("303", "2025-2T"),
        ]
        assert summary.total_considered == 3
        assert summary.match_count == 3


class TestNotYetFoundSurfacing:
    """APPROVED draft with no AEAT record → NOT_YET_FOUND warning + marker."""

    def test_not_yet_found_returns_warning_and_summary_marker(
        self,
        drafts_dir: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        draft = _build_draft(draft_id="kent-unseen")
        _write_draft(drafts_dir, draft)
        fetcher = _SessionCountingFetcher(filings=())  # AEAT knows nothing.
        sink = _CapturingSink()

        with caplog.at_level(logging.WARNING, logger="aeat.cli.sync._reconcile_stage"):
            summary = _run(drafts_dir=drafts_dir, fetcher=fetcher, sink=sink)

        assert summary.not_yet_found_count == 1
        assert summary.match_count == 0
        assert summary.divergent_count == 0
        assert summary.not_yet_found_refs == ((draft.modelo, draft.period, draft.draft_id),)
        # One WARNING log with the explicit marker and the draft id.
        messages = [record.getMessage() for record in caplog.records]
        assert any("NOT_YET_FOUND" in msg and draft.draft_id in msg for msg in messages)

    def test_summary_emitter_surfaces_not_yet_found_prominently(self) -> None:
        summary = ReconcileStageSummary(
            total_considered=2,
            skipped_count=0,
            match_count=1,
            divergent_count=0,
            not_yet_found_count=1,
            not_yet_found_refs=(("303", "2025-1T", "kent-draft-001"),),
            persisted_record_ids=("record-0",),
        )
        buf = io.StringIO()
        console = Console(file=buf, force_terminal=False, color_system=None, width=120)

        emit_reconcile_summary(summary, console=console)
        rendered = buf.getvalue()

        assert "NOT_YET_FOUND" in rendered
        assert "kent-draft-001" in rendered
        assert "303" in rendered
        assert "2025-1T" in rendered

    def test_persists_not_yet_found_record_through_sink(
        self,
        drafts_dir: Path,
    ) -> None:
        draft = _build_draft(draft_id="kent-no-remote")
        _write_draft(drafts_dir, draft)
        fetcher = _SessionCountingFetcher(filings=())
        sink = _CapturingSink()

        summary = _run(drafts_dir=drafts_dir, fetcher=fetcher, sink=sink)

        assert len(sink.saved) == 1
        record = sink.saved[0]
        assert record.modelo == draft.modelo
        assert record.period == draft.period
        assert record.draft_ref.draft_id == draft.draft_id
        assert record.record_id in summary.persisted_record_ids


class TestDivergentPersistence:
    """DIVERGENT reports are persisted through the Phase-3 adapter."""

    def test_value_mismatch_persists_one_record_per_delta(
        self,
        drafts_dir: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        draft = _build_draft(
            draft_id="kent-divergent",
            values=(
                _value("46", Decimal("100.00")),
                _value("47", Decimal("200.00")),
            ),
        )
        _write_draft(drafts_dir, draft)
        filing = _remote_filing(
            casillas=(
                _remote_casilla("46", Decimal("101.00")),
                _remote_casilla("47", Decimal("200.00")),
            ),
        )
        fetcher = _SessionCountingFetcher(filings=(filing,))
        sink = _CapturingSink()

        with caplog.at_level(logging.WARNING, logger="aeat.cli.sync._reconcile_stage"):
            summary = _run(drafts_dir=drafts_dir, fetcher=fetcher, sink=sink)

        assert summary.divergent_count == 1
        assert summary.match_count == 0
        assert summary.not_yet_found_count == 0
        # One non-rounding delta on casilla 46 is persisted.
        assert len(sink.saved) == 1
        persisted = sink.saved[0]
        assert persisted.modelo == draft.modelo
        assert persisted.period == draft.period
        assert persisted.draft_ref.draft_id == draft.draft_id
        assert persisted.payload.kind is FilingDivergenceKind.CASILLA_VALUE_MISMATCH
        # Every non-filing-scope payload variant carries a casilla_id;
        # dump-and-inspect avoids the union discriminator typechecker dance.
        dumped = persisted.payload.model_dump()
        assert dumped["casilla_id"] == "46"
        # WARNING-level log surfaces the divergent draft.
        messages = [record.getMessage() for record in caplog.records]
        assert any("DIVERGENT" in msg and draft.draft_id in msg for msg in messages)

    def test_matching_draft_persists_no_records(self, drafts_dir: Path) -> None:
        draft = _build_draft(
            draft_id="kent-match",
            values=(_value("01", Decimal("12500.00")),),
        )
        _write_draft(drafts_dir, draft)
        filing = _remote_filing(casillas=(_remote_casilla("01", Decimal("12500.00")),))
        fetcher = _SessionCountingFetcher(filings=(filing,))
        sink = _CapturingSink()

        summary = _run(drafts_dir=drafts_dir, fetcher=fetcher, sink=sink)

        assert summary.match_count == 1
        assert sink.saved == []

    def test_multi_filing_chain_picks_latest_by_submitted_at(
        self,
        drafts_dir: Path,
    ) -> None:
        draft = _build_draft(
            draft_id="kent-latest",
            values=(_value("01", Decimal("300.00")),),
        )
        _write_draft(drafts_dir, draft)
        original = RemoteFiling(
            modelo=draft.modelo,
            period=draft.period,
            expediente_id="exp-original",
            status=RemoteFilingStatus.PRESENTADA,
            raw_status="Presentada",
            submitted_at=datetime(2026, 1, 1, tzinfo=UTC),
            casillas=(_remote_casilla("01", Decimal("100.00")),),
            receipts=(),
            complementaria_of=None,
        )
        newer = RemoteFiling(
            modelo=draft.modelo,
            period=draft.period,
            expediente_id="exp-newer",
            status=RemoteFilingStatus.PRESENTADA,
            raw_status="Presentada",
            submitted_at=datetime(2026, 3, 1, tzinfo=UTC),
            casillas=(_remote_casilla("01", Decimal("300.00")),),
            receipts=(),
            complementaria_of="exp-original",
        )
        fetcher = _SessionCountingFetcher(filings=(original, newer))
        sink = _CapturingSink()

        summary = _run(drafts_dir=drafts_dir, fetcher=fetcher, sink=sink)

        # The latest-by-submitted_at anchor matches the draft -> MATCH.
        assert summary.match_count == 1


class TestMixedBatch:
    """A mixed batch exercises the whole stage end-to-end."""

    def test_mixed_match_divergent_not_yet_found(self, drafts_dir: Path) -> None:
        matching = _build_draft(
            draft_id="d-match",
            modelo="303",
            period="2025-1T",
            values=(_value("01", Decimal("100.00")),),
        )
        divergent = _build_draft(
            draft_id="d-div",
            modelo="303",
            period="2025-2T",
            values=(_value("46", Decimal("50.00")),),
        )
        missing = _build_draft(
            draft_id="d-nyf",
            modelo="130",
            period="2025-1T",
        )
        for draft in (matching, divergent, missing):
            _write_draft(drafts_dir, draft)
        filings = (
            _remote_filing(
                modelo="303",
                period="2025-1T",
                casillas=(_remote_casilla("01", Decimal("100.00")),),
            ),
            _remote_filing(
                modelo="303",
                period="2025-2T",
                casillas=(_remote_casilla("46", Decimal("999.00")),),
            ),
            # modelo=130 missing entirely -> NOT_YET_FOUND.
        )
        fetcher = _SessionCountingFetcher(filings=filings)
        sink = _CapturingSink()

        summary = _run(drafts_dir=drafts_dir, fetcher=fetcher, sink=sink)

        assert summary.total_considered == 3
        assert summary.skipped_count == 0
        assert summary.match_count == 1
        assert summary.divergent_count == 1
        assert summary.not_yet_found_count == 1
        assert summary.not_yet_found_refs == (("130", "2025-1T", "d-nyf"),)
        # Two persisted records: one per non-MATCH report.
        assert len(sink.saved) == 2
        kinds = sorted(record.payload.kind for record in sink.saved)
        assert kinds == [
            FilingDivergenceKind.CASILLA_VALUE_MISMATCH,
            FilingDivergenceKind.FILING_NOT_YET_FOUND,
        ]


class TestEmptyCorpus:
    """No drafts on disk -> empty summary, no calls, no saves."""

    def test_empty_drafts_dir_is_graceful(self, drafts_dir: Path) -> None:
        fetcher = _SessionCountingFetcher(filings=())
        sink = _CapturingSink()

        summary = _run(drafts_dir=drafts_dir, fetcher=fetcher, sink=sink)

        assert summary.total_considered == 0
        assert summary.match_count == 0
        assert summary.divergent_count == 0
        assert summary.not_yet_found_count == 0
        assert fetcher.calls == []
        assert sink.saved == []

    def test_missing_drafts_dir_is_graceful(self, tmp_path: Path) -> None:
        missing = tmp_path / "no-such-dir"
        fetcher = _SessionCountingFetcher(filings=())
        sink = _CapturingSink()

        summary = _run(drafts_dir=missing, fetcher=fetcher, sink=sink)

        assert summary.total_considered == 0


class TestSummaryRecord:
    """The :class:`ReconcileStageSummary` is strict, frozen, and extra-forbidding."""

    def test_summary_is_frozen(self) -> None:
        from pydantic import ValidationError

        summary = ReconcileStageSummary(
            total_considered=1,
            skipped_count=0,
            match_count=1,
            divergent_count=0,
            not_yet_found_count=0,
        )
        with pytest.raises(ValidationError):
            summary.match_count = 2  # type: ignore[misc]

    def test_summary_rejects_unknown_fields(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ReconcileStageSummary.model_validate(
                {
                    "total_considered": 1,
                    "skipped_count": 0,
                    "match_count": 1,
                    "divergent_count": 0,
                    "not_yet_found_count": 0,
                    "unexpected": True,
                }
            )
