"""Unit tests for the ``aeat workflow`` CLI sub-app.

The tests exercise the typer surface via :class:`typer.testing.CliRunner`.
Real :class:`aeat.workflow.WorkflowEngine` instances are wired through
the ``set_test_hooks`` module seam — no mocks, no patches.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import cast

import pytest
from typer.testing import CliRunner

from ...config import Settings
from ...deadlines import (
    AutonomoProfile,
    FilingObligation,
    IVARegime,
    ObligationStatus,
    Schedule,
)
from ...submission import DraftStatus, FilingFinding
from ...workflow import (
    FilingDraftBuilderProtocol,
    SubmissionEngineProtocol,
    SubmittedFilingLike,
    WorkflowEngine,
)
from .. import app as root_app
from ._helpers import clear_test_hooks, set_test_hooks

pytestmark = [pytest.mark.unit, pytest.mark.domain_infra]


@dataclass
class _Draft:
    draft_id: str = "draft-x"
    modelo: str = "130"
    period: str = "2026Q1"
    profile_tax_id: str = "X1234567L"
    status: DraftStatus = DraftStatus.APPROVED
    values: Mapping[str, str] = field(default_factory=lambda: {"01": "1000"})
    findings: tuple[FilingFinding, ...] = ()


class _DeadlineEngine:
    def compute(
        self,
        profile: AutonomoProfile,
        year: int,
        *,
        today: date | None = None,
    ) -> Schedule:
        return Schedule(
            profile=profile,
            year=year,
            obligations=(
                FilingObligation(
                    modelo="130",
                    period="2026Q1",
                    opens_on=date(2026, 4, 1),
                    closes_on=date(2099, 12, 31),
                    status=ObligationStatus.UPCOMING,
                    applies_because="test",
                ),
            ),
            generated_at=datetime(2026, 4, 12, tzinfo=UTC),
        )


class _DraftBuilder:
    def build(
        self,
        *,
        modelo: str,
        period: str,
        profile: AutonomoProfile,
        inputs: Mapping[str, object],
        fail_on_warning: bool = False,
    ) -> _Draft:
        return _Draft(modelo=modelo, period=period, profile_tax_id=profile.tax_id)


class _SubmissionEngine:
    def preflight(self, draft: _Draft, *, today: date) -> None:
        return None

    async def submit_draft(
        self,
        draft: _Draft,
        *,
        dry_run: bool,
        today: date | None = None,
    ) -> SubmittedFilingLike:
        return SubmittedFilingLike(
            submission_id="sub-x",
            draft_id=draft.draft_id,
            modelo=draft.modelo,
            period=draft.period,
            status="PENDING",
            submitted_at=datetime(2026, 4, 12, tzinfo=UTC),
        )


class _InputsProvider:
    def load_inputs(
        self,
        *,
        modelo: str,
        period: str,
        profile: AutonomoProfile,
    ) -> Mapping[str, object]:
        return {"01": "1000"}


def _profile() -> AutonomoProfile:
    return AutonomoProfile(
        tax_id="X1234567L",
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
    )


@pytest.fixture(autouse=True)
def _isolated_runs_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Redirect AEAT_WORKFLOW_RUNS_DIR to an isolated tmp dir per test."""
    runs_dir = tmp_path / "runs"
    monkeypatch.setenv("AEAT_WORKFLOW_RUNS_DIR", str(runs_dir))
    yield runs_dir


@pytest.fixture(autouse=True)
def _wire_hooks() -> Iterator[None]:
    """Wire real test doubles into the CLI helper seam."""

    def _engine() -> WorkflowEngine:
        return WorkflowEngine(
            deadline_engine=_DeadlineEngine(),
            filing_draft_builder=cast(FilingDraftBuilderProtocol, _DraftBuilder()),
            submission_engine=cast(SubmissionEngineProtocol, _SubmissionEngine()),
            sync_runner=None,
            session=None,
            certificate_bundle=None,
            inputs_provider=_InputsProvider(),
            settings=Settings(),
        )

    set_test_hooks(engine_factory=_engine, profile_factory=_profile)
    yield None
    clear_test_hooks()


class TestWorkflowCli:
    def test_next_json_round_trips(self, _isolated_runs_dir: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(root_app, ["workflow", "next", "--json", "--no-sync"])
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["final_stage"] == "DONE"
        run_id = payload["run_id"]
        persisted = _isolated_runs_dir / f"{run_id}.json"
        assert persisted.exists()

    def test_run_for_period(self, _isolated_runs_dir: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            root_app,
            [
                "workflow",
                "run",
                "--modelo",
                "130",
                "--period",
                "2026Q1",
                "--json",
                "--no-sync",
            ],
        )
        assert result.exit_code == 0, result.output

    def test_show_round_trips(self, _isolated_runs_dir: Path) -> None:
        runner = CliRunner()
        first = runner.invoke(root_app, ["workflow", "next", "--json", "--no-sync"])
        assert first.exit_code == 0
        run_id = json.loads(first.output)["run_id"]
        second = runner.invoke(root_app, ["workflow", "show", run_id, "--json"])
        assert second.exit_code == 0, second.output
        assert run_id in second.output

    def test_list_enumerates(self, _isolated_runs_dir: Path) -> None:
        runner = CliRunner()
        runner.invoke(root_app, ["workflow", "next", "--json", "--no-sync"])
        listing = runner.invoke(root_app, ["workflow", "list", "--json"])
        assert listing.exit_code == 0, listing.output
        payload = json.loads(listing.output)
        assert len(payload) >= 1
