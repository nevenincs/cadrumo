"""CLI surface tests for ``aeat app modelo export``."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aeat.adapters.persistence.storage import EphemeralMasterKeyProvider
from aeat.adapters.persistence.storage.sql.engine import dispose_engine
from aeat.application.user_profile._testing import register_minimal_profile
from aeat.application.workflow._persistence import workflow_state_repository
from aeat.domain.modelos._calculation_repository import (
    CalculationRevisionCatalogueRepository,
    upsert_calculation_revision,
)
from aeat.domain.modelos._calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from aeat.domain.modelos._codes import ModeloCode
from aeat.domain.modelos._repository import WorkUnitCatalogueRepository, upsert_work_unit
from aeat.domain.modelos._work_unit import WorkUnit, derive_work_unit_id
from aeat.entrypoints.cli import app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'export-cli.db').as_posix()}")
    dispose_engine()
    with EphemeralMasterKeyProvider():
        try:
            workflow_state_repository().update(
                lambda state: register_minimal_profile(state, profile_id="operator"),
            )
            yield
        finally:
            dispose_engine()


def _seed_work_unit_only(*, modelo: str = "130", filing_year: int = 2026, period: str = "Q1") -> str:
    state = workflow_state_repository().load()
    bucket_id = state.active_profile_bucket_id()
    assert bucket_id is not None
    revision_id = "r" + "0" * 63
    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        revision_id=revision_id,
    )
    now = datetime.now(UTC)
    work_unit = WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=bucket_id,
        modelo=ModeloCode(modelo),
        filing_year=filing_year,
        period=period,
        revision_id=revision_id,
        name=f"{modelo}-{filing_year}-{period}",
        created_at=now,
        updated_at=now,
    )
    repo = WorkUnitCatalogueRepository()
    repo.save(upsert_work_unit(repo.load(), work_unit))
    return work_unit_id


def _seed_work_unit_with_draft_revision() -> tuple[str, str]:
    work_unit_id = _seed_work_unit_only()
    now = datetime.now(UTC)
    calculation_revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        inputs_snapshot={},
        binding_overrides={},
        casilla_values={},
    )
    revision = CalculationRevision(
        calculation_revision_id=calculation_revision_id,
        work_unit_id=work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        created_at=now,
        updated_at=now,
    )
    cr_repo = CalculationRevisionCatalogueRepository()
    cr_repo.save(upsert_calculation_revision(cr_repo.load(), revision))
    return work_unit_id, calculation_revision_id


def test_export_requires_output_flag(cli_runner: CliRunner) -> None:
    """``--output`` is required; missing it surfaces as Typer usage error."""

    work_unit_id = _seed_work_unit_only()

    result = cli_runner.invoke(app, ["app", "modelo", "export", work_unit_id])
    assert result.exit_code != 0, result.output


def test_export_refuses_unknown_work_unit(cli_runner: CliRunner, tmp_path: Path) -> None:
    """A work unit id that resolves to no exportable revision must
    refuse rather than write an empty file."""

    out = tmp_path / "out.txt"
    result = cli_runner.invoke(
        app,
        ["app", "modelo", "export", "0" * 64, "--output", str(out)],
    )
    assert result.exit_code != 0, result.output
    assert not out.exists()


def test_export_refuses_work_unit_with_no_exportable_revision(
    cli_runner: CliRunner, tmp_path: Path,
) -> None:
    """A work unit whose only revision is in DRAFT state must refuse;
    only verified-complete or filed revisions are exportable."""

    work_unit_id, _ = _seed_work_unit_with_draft_revision()
    out = tmp_path / "out.txt"

    result = cli_runner.invoke(
        app,
        ["app", "modelo", "export", work_unit_id, "--output", str(out)],
    )
    assert result.exit_code != 0, result.output
    assert not out.exists()


def test_export_help_advertises_local_only(cli_runner: CliRunner) -> None:
    """The export verb help string must state ``Local-only`` so the
    operator cannot mistake the verb for an AEAT-contacting submit."""

    result = cli_runner.invoke(app, ["app", "modelo", "export", "--help"])
    assert result.exit_code == 0, result.output
    assert "modelo" in result.output.lower()
    assert any(
        token in result.output.lower()
        for token in ("local-only", "local;", "local.", "nunca")
    ), result.output


def test_export_refuses_explicit_revision_in_draft_state(
    cli_runner: CliRunner, tmp_path: Path,
) -> None:
    """When --revision targets a DRAFT revision explicitly, the service
    raises CalculationRevisionStateError; the CLI surfaces it as a
    refusal."""

    work_unit_id, calc_rev_id = _seed_work_unit_with_draft_revision()
    out = tmp_path / "out.txt"

    result = cli_runner.invoke(
        app,
        [
            "app", "modelo", "export", work_unit_id,
            "--output", str(out),
            "--revision", calc_rev_id,
        ],
    )
    assert result.exit_code != 0, result.output
    assert not out.exists()
