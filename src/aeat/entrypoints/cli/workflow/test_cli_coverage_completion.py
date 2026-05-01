"""Coverage-completion tests for the ``aeat workflow`` CLI surfaces.

Closes the pre-existing coverage gaps in ``_helpers.py``, ``list_cmd.py``,
and ``show.py`` that pre-dated issue ``#393``. Bundled into PR #427 by
explicit user direction ("well-rounded terminated code that is healthy
rather than leaving feature fragments").

The tests target every previously-missing line by exercising the real
production paths through the CLI surface and one direct unit-level
call into ``_helpers._build_profile`` for the bare-fallback branch
that the CLI cannot otherwise reach without test hooks installed.

Deterministic stand-ins for the engine collaborators live inline below.
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

from ....adapters.outbound.aeat.export import DraftStatus, FilingFinding
from ....application.workflow import (
    FilingDraftBuilderProtocol,
    SubmissionEngineProtocol,
    WorkflowEngine,
    WorkflowError,
)
from ....core.config import Settings
from ....core.errors import ErrorCategory, get_error_exit_code
from ....domain.deadlines import (
    AutonomoProfile,
    FilingObligation,
    IVARegime,
    ObligationStatus,
    Schedule,
)
from .. import app as root_app
from . import _helpers
from ._helpers import clear_test_hooks, set_test_hooks

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@dataclass
class _Draft:
    """Deterministic test draft."""

    draft_id: str = "draft-x"
    modelo: str = "130"
    period: str = "2026Q1"
    profile_tax_id: str = "X1234567L"
    status: DraftStatus = DraftStatus.APPROVED
    values: Mapping[str, str] = field(default_factory=lambda: {"01": "1000"})
    findings: tuple[FilingFinding, ...] = ()


class _DeadlineEngine:
    """Deadline engine stand-in returning one fixed UPCOMING obligation."""

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
    """Draft builder stand-in returning a deterministic ``_Draft``."""

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
    """Submission engine stand-in for read-only preflight paths."""

    def preflight(self, draft: _Draft, *, today: date) -> None:
        return None


class _InputsProvider:
    """Inputs provider stand-in returning a single casilla."""

    def load_inputs(
        self,
        *,
        modelo: str,
        period: str,
        profile: AutonomoProfile,
    ) -> Mapping[str, object]:
        return {"01": "1000"}


def make_profile() -> AutonomoProfile:
    """Return the canonical test :class:`AutonomoProfile`."""
    return AutonomoProfile(
        tax_id="X1234567L",
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
    )


def make_engine() -> WorkflowEngine:
    """Return a fully wired :class:`WorkflowEngine` using the stand-ins."""
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


def make_failing_engine() -> WorkflowEngine:
    """Engine factory that raises :class:`WorkflowError` to drive the
    helpers' catch-and-exit-1 path under test.
    """
    raise WorkflowError("simulated wiring failure")


def _unwrap_result(output: str):
    return json.loads(output)["result"]


@pytest.fixture(autouse=True)
def _clean_hooks() -> Iterator[None]:
    clear_test_hooks()
    yield None
    clear_test_hooks()


@pytest.fixture()
def isolated_runs_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    runs_dir = tmp_path / "runs"
    monkeypatch.setenv("AEAT_WORKFLOW_RUNS_DIR", str(runs_dir))
    return runs_dir


@pytest.fixture()
def working_hooks() -> None:
    set_test_hooks(engine_factory=make_engine, profile_factory=make_profile)


# ---------- _helpers.py: WorkflowError wrap on profile-load failure ----------


def test_build_profile_wraps_arbitrary_load_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Hitting `_build_profile` without test hooks must convert any load
    error into a `WorkflowError` so the CLI catch-and-exit-1 layer can
    handle it uniformly."""
    bogus_path = tmp_path / "does-not-exist.json"
    monkeypatch.setenv("AEAT_DEFAULT_PROFILE_PATH", str(bogus_path))
    with pytest.raises(WorkflowError):
        _helpers._build_profile()


# ---------- _helpers.py: WorkflowError catch in run_engine_next ----------


def test_run_engine_next_exits_1_when_engine_factory_raises_workflow_error(
    isolated_runs_dir: Path,
) -> None:
    """A `WorkflowError` from `_build_engine` must be caught by `run_engine_next`
    and surface through the shared structured stderr boundary."""
    set_test_hooks(engine_factory=make_failing_engine, profile_factory=make_profile)
    runner = CliRunner()
    result = runner.invoke(root_app, ["workflow", "next", "--no-sync"])
    assert result.exit_code == get_error_exit_code(ErrorCategory.ERROR), result.output
    assert result.stdout == ""
    assert "ERROR:" in result.stderr
    assert "simulated wiring failure" in result.stderr


# ---------- _helpers.py: WorkflowError catch in run_engine_for_period ----------


def test_run_engine_for_period_exits_1_when_engine_factory_raises_workflow_error(
    isolated_runs_dir: Path,
) -> None:
    """Symmetric: `run_engine_for_period` must also emit structured stderr."""
    set_test_hooks(engine_factory=make_failing_engine, profile_factory=make_profile)
    runner = CliRunner()
    result = runner.invoke(
        root_app,
        ["workflow", "run", "--modelo", "130", "--period", "2026Q1", "--no-sync"],
    )
    assert result.exit_code == get_error_exit_code(ErrorCategory.ERROR), result.output
    assert result.stdout == ""
    assert "ERROR:" in result.stderr
    assert "simulated wiring failure" in result.stderr


def test_workflow_next_json_error_envelope_stays_on_stderr(
    isolated_runs_dir: Path,
) -> None:
    """`workflow next --json` must keep failure payloads off stdout."""
    set_test_hooks(engine_factory=make_failing_engine, profile_factory=make_profile)
    runner = CliRunner()
    result = runner.invoke(root_app, ["workflow", "next", "--json", "--no-sync"])

    assert result.exit_code == get_error_exit_code(ErrorCategory.ERROR), result.output
    assert result.stdout == ""
    payload = json.loads(result.stderr)
    assert payload["error"]["category"] == ErrorCategory.ERROR.value
    assert payload["error"]["message"] == "simulated wiring failure"


# ---------- _helpers.py: rich JSON render branch in _emit ----------


def test_emit_renders_rich_when_not_json(isolated_runs_dir: Path, working_hooks: None) -> None:
    """`_emit` must take the Rich render branch when `as_json=False`."""
    runner = CliRunner()
    result = runner.invoke(root_app, ["workflow", "next", "--no-sync"])
    assert result.exit_code == 0, result.output
    assert "run_id" in result.output


# ---------- list_cmd.py: invalid --since exits 2 ----------


def test_list_invalid_since_exits_2(isolated_runs_dir: Path) -> None:
    """`workflow list --since not-a-date` must exit 2 with `invalid --since`."""
    runner = CliRunner()
    result = runner.invoke(root_app, ["workflow", "list", "--since", "not-a-date"])
    assert result.exit_code == 2, result.output
    assert "invalid --since" in result.output.lower()


# ---------- list_cmd.py: rich-table render branch ----------


def test_list_renders_table_when_not_json(isolated_runs_dir: Path, working_hooks: None) -> None:
    """`workflow list` (no `--json`) must render the Rich table."""
    runner = CliRunner()
    seed = runner.invoke(root_app, ["workflow", "next", "--no-sync", "--json"])
    assert seed.exit_code == 0, seed.output
    listing = runner.invoke(root_app, ["workflow", "list"])
    assert listing.exit_code == 0, listing.output
    assert "workflow runs" in listing.output


# ---------- show.py: missing run exits 1 ----------


def test_show_missing_run_exits_1(isolated_runs_dir: Path) -> None:
    """`workflow show <bogus-id>` must exit 1 with `not found`."""
    runner = CliRunner()
    result = runner.invoke(root_app, ["workflow", "show", "no-such-run"])
    assert result.exit_code == 1, result.output
    assert "not found" in result.output.lower()


# ---------- show.py: rich-render branch when not --json ----------


def test_show_renders_rich_when_not_json(isolated_runs_dir: Path, working_hooks: None) -> None:
    """`workflow show <real-id>` (no `--json`) must render via Rich."""
    runner = CliRunner()
    seed = runner.invoke(root_app, ["workflow", "next", "--no-sync", "--json"])
    assert seed.exit_code == 0, seed.output
    run_id = _unwrap_result(seed.output)["run_id"]
    result = runner.invoke(root_app, ["workflow", "show", run_id])
    assert result.exit_code == 0, result.output
    assert run_id in result.output
