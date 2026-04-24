"""Unit tests for ``aeat filing reconcile`` (#239, Phase 4).

No mocks. Every collaborator is a strict pydantic record built inline
or a real Protocol-conforming Python class. The unit suite exercises
the pure-CLI surface: draft resolution, remote-fetcher injection,
forbidden-flag refusal, JSON emission, and exit-code mapping against
the ADR-locked terminal triad.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Final

import pytest
import typer
from typer.testing import CliRunner

from ...filing import (
    FilingDraft,
    FilingDraftStatus,
    FilingValue,
    FilingValueKind,
)
from ...remote import (
    RemoteCasilla,
    RemoteFiling,
    RemoteFilingFetcher,
    RemoteFilingStatus,
)
from ...schema import CasillaDataType
from ._reconcile import (
    _FORBIDDEN_FLAGS,
    ReconcileCliArgs,
    register,
    reject_forbidden_flags,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_submission]


_FROZEN_NOW: Final[datetime] = datetime(2026, 4, 24, 12, 0, tzinfo=UTC)


def _frozen_now_factory() -> Callable[[], datetime]:
    return lambda: _FROZEN_NOW


def _build_draft(
    *,
    draft_id: str = "draft-reconcile-001",
    modelo: str = "303",
    period: str = "2025-1T",
    status: FilingDraftStatus = FilingDraftStatus.APPROVED,
    values: tuple[FilingValue, ...] = (),
) -> FilingDraft:
    """Build a deterministic approved draft for the reconcile tests."""
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
    """Build a deterministic RemoteFiling anchor."""
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


class _StaticFetcher:
    """Protocol-conforming :class:`RemoteFilingFetcher` for CLI tests."""

    def __init__(self, filings: tuple[RemoteFiling, ...]) -> None:
        self._filings = filings

    async def fetch_filing_detail(
        self,
        modelo: str,
        period: str,
        *,
        use_cache: bool = True,
    ) -> tuple[RemoteFiling, ...]:
        _ = use_cache
        return tuple(f for f in self._filings if f.modelo == modelo and f.period == period)


def _write_draft(drafts_dir: Path, draft: FilingDraft) -> Path:
    """Persist a draft to the canonical ``{modelo}_{period}_{id}.json`` path."""
    path = drafts_dir / f"{draft.modelo}_{draft.period}_{draft.draft_id}.json"
    path.write_text(draft.model_dump_json(indent=2), encoding="utf-8")
    return path


@pytest.fixture
def drafts_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = tmp_path / "drafts"
    target.mkdir()
    monkeypatch.setenv("AEAT_DRAFTS_DIR", str(target))
    return target


def _build_cli(
    filings: tuple[RemoteFiling, ...] = (),
    *,
    offline: bool = False,
) -> typer.Typer:
    """Build a fresh Typer app with the reconcile command registered."""
    app = typer.Typer()
    fetcher: RemoteFilingFetcher | None = None if offline else _StaticFetcher(filings)
    register(
        app,
        fetcher_provider=lambda: fetcher,
        now_provider=_frozen_now_factory,
    )
    return app


runner = CliRunner()


class TestRejectForbiddenFlags:
    """Pre-parser refusal of every write-verb flag."""

    @pytest.mark.parametrize("flag", _FORBIDDEN_FLAGS)
    def test_raises_on_bare_flag(self, flag: str) -> None:
        with pytest.raises(typer.BadParameter):
            reject_forbidden_flags(["some-draft", flag])

    @pytest.mark.parametrize("flag", _FORBIDDEN_FLAGS)
    def test_raises_on_flag_with_equals_value(self, flag: str) -> None:
        with pytest.raises(typer.BadParameter):
            reject_forbidden_flags(["some-draft", f"{flag}=1"])

    def test_passes_clean_argv(self) -> None:
        reject_forbidden_flags(["--last", "--modelo", "303", "--period", "2025-1T"])


class TestReconcileCliArgs:
    """The normalised-arguments record enforces strict/frozen/forbid."""

    def test_frozen(self) -> None:
        from pydantic import ValidationError

        args = ReconcileCliArgs(draft_id="d-1")
        with pytest.raises(ValidationError):
            args.draft_id = "d-2"  # type: ignore[misc]

    def test_extra_forbid(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ReconcileCliArgs.model_validate({"draft_id": "d-1", "unexpected": True})


class TestReconcileHappyPath:
    """MATCH + DIVERGENT + NOT_YET_FOUND triad rendering + exit codes."""

    def test_match_exit_zero_green_narrative(self, drafts_dir: Path) -> None:
        draft = _build_draft(values=(_value("01", Decimal("12500.00")),))
        _write_draft(drafts_dir, draft)
        filing = _remote_filing(casillas=(_remote_casilla("01", Decimal("12500.00")),))

        app = _build_cli(filings=(filing,))
        result = runner.invoke(app, [draft.draft_id])

        assert result.exit_code == 0, result.output
        assert "MATCH" in result.output

    def test_divergent_exit_one_red_narrative_with_casilla_delta(
        self,
        drafts_dir: Path,
    ) -> None:
        draft = _build_draft(values=(_value("46", Decimal("100.00")),))
        _write_draft(drafts_dir, draft)
        filing = _remote_filing(casillas=(_remote_casilla("46", Decimal("101.00")),))

        app = _build_cli(filings=(filing,))
        result = runner.invoke(app, [draft.draft_id])

        assert result.exit_code == 1, result.output
        assert "DIVERGENT" in result.output
        assert "46" in result.output

    def test_not_yet_found_exit_two_warning_narrative(self, drafts_dir: Path) -> None:
        draft = _build_draft()
        _write_draft(drafts_dir, draft)

        app = _build_cli(offline=True)
        result = runner.invoke(app, [draft.draft_id])

        assert result.exit_code == 2, result.output
        assert "NOT_YET_FOUND" in result.output


class TestForbiddenFlagRefusalViaCli:
    """Every forbidden flag must be refused with a non-empty stderr message."""

    @pytest.mark.parametrize("flag", _FORBIDDEN_FLAGS)
    def test_flag_refused_with_exit_code_two(self, drafts_dir: Path, flag: str) -> None:
        draft = _build_draft()
        _write_draft(drafts_dir, draft)

        app = _build_cli(offline=True)
        result = runner.invoke(app, [draft.draft_id, flag])

        assert result.exit_code == 2, result.output
        stderr = (result.stderr or "").strip()
        assert stderr, f"expected non-empty stderr for {flag!r}"


class TestJsonOutput:
    """``--json`` emits deterministic, documented fields."""

    def test_json_is_parseable_and_contains_every_report_field(
        self,
        drafts_dir: Path,
    ) -> None:
        draft = _build_draft(values=(_value("01", Decimal("12500.00")),))
        _write_draft(drafts_dir, draft)
        filing = _remote_filing(casillas=(_remote_casilla("01", Decimal("12500.00")),))

        app = _build_cli(filings=(filing,))
        result = runner.invoke(app, [draft.draft_id, "--json"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.stdout)
        assert payload["status"] == "match"
        assert "casilla_deltas" in payload
        assert "remote_ref" in payload
        assert "draft_ref" in payload
        assert "reconciled_at" in payload
        assert "narrative" in payload
        assert payload["draft_ref"]["draft_id"] == draft.draft_id

    def test_json_divergent_still_exits_zero(self, drafts_dir: Path) -> None:
        draft = _build_draft(values=(_value("46", Decimal("100.00")),))
        _write_draft(drafts_dir, draft)
        filing = _remote_filing(casillas=(_remote_casilla("46", Decimal("101.00")),))

        app = _build_cli(filings=(filing,))
        result = runner.invoke(app, [draft.draft_id, "--json"])

        # Per plan §4.2, machine consumers check the status field; JSON
        # mode exits 0 regardless of the terminal-triad member.
        assert result.exit_code == 0, result.output
        payload = json.loads(result.stdout)
        assert payload["status"] == "divergent"


class TestLastLookup:
    """``--last --modelo M --period P`` picks the newest APPROVED draft."""

    def test_last_returns_most_recent_approved(self, drafts_dir: Path) -> None:
        older = _build_draft(
            draft_id="draft-old",
            values=(_value("03", Decimal("100.00")),),
        ).model_copy(
            update={"approved_at": datetime(2026, 1, 1, tzinfo=UTC)},
        )
        newer = _build_draft(
            draft_id="draft-new",
            values=(_value("03", Decimal("200.00")),),
        ).model_copy(
            update={"approved_at": datetime(2026, 4, 1, tzinfo=UTC)},
        )
        _write_draft(drafts_dir, older)
        _write_draft(drafts_dir, newer)
        filing = _remote_filing(casillas=(_remote_casilla("03", Decimal("200.00")),))

        app = _build_cli(filings=(filing,))
        result = runner.invoke(
            app,
            ["--last", "--modelo", "303", "--period", "2025-1T", "--json"],
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.stdout)
        assert payload["status"] == "match"
        assert payload["draft_ref"]["draft_id"] == "draft-new"

    def test_last_without_match_fails_with_helpful_message(
        self,
        drafts_dir: Path,
    ) -> None:
        app = _build_cli(offline=True)
        result = runner.invoke(
            app,
            ["--last", "--modelo", "130", "--period", "2025-1T"],
        )
        assert result.exit_code != 0
        stderr = (result.stderr or "") + result.output
        assert "APPROVED" in stderr or "no " in stderr.lower()

    def test_last_requires_modelo_and_period(self, drafts_dir: Path) -> None:
        app = _build_cli(offline=True)
        result = runner.invoke(app, ["--last"])
        assert result.exit_code != 0

    def test_last_and_draft_id_conflict(self, drafts_dir: Path) -> None:
        draft = _build_draft()
        _write_draft(drafts_dir, draft)
        app = _build_cli(offline=True)
        result = runner.invoke(
            app,
            [draft.draft_id, "--last", "--modelo", "303", "--period", "2025-1T"],
        )
        assert result.exit_code != 0


class TestDraftResolution:
    """Draft resolution edge cases surface helpful messages, not stack traces."""

    def test_unknown_draft_id_is_friendly_error(self, drafts_dir: Path) -> None:
        app = _build_cli(offline=True)
        result = runner.invoke(app, ["does-not-exist"])
        assert result.exit_code != 0, result.output
        combined = (result.stderr or "") + result.output
        assert "does-not-exist" in combined
        assert "Traceback" not in combined

    def test_missing_draft_id_and_missing_last_is_friendly_error(
        self,
        drafts_dir: Path,
    ) -> None:
        app = _build_cli(offline=True)
        result = runner.invoke(app, [])
        assert result.exit_code != 0


class TestDryRunAlias:
    """``--dry-run`` is a no-op alias for sibling-command symmetry."""

    def test_dry_run_behaves_identically_to_no_flag(self, drafts_dir: Path) -> None:
        draft = _build_draft(values=(_value("01", Decimal("12500.00")),))
        _write_draft(drafts_dir, draft)
        filing = _remote_filing(casillas=(_remote_casilla("01", Decimal("12500.00")),))

        app = _build_cli(filings=(filing,))
        result = runner.invoke(app, [draft.draft_id, "--dry-run"])
        assert result.exit_code == 0, result.output
        assert "MATCH" in result.output
