"""CLI surface tests for `aeat app modelo reconcile`."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ....application.user_profile._orchestration import profile_create_storage_span
from ....application.user_profile._testing import register_minimal_profile
from ....application.workflow._persistence import workflow_state_repository
from ....domain.modelos._codes import ModeloCode
from ....domain.modelos._repository import WorkUnitCatalogueRepository, upsert_work_unit
from ....domain.modelos._work_unit import WorkUnit, derive_work_unit_id
from ....tests import FIXTURES_DIR
from ....tests.secure_sql import isolated_profile_storage_root
from .. import app

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

MODELO_130_FIXTURE = FIXTURES_DIR / "justificantes" / "modelo_130_2026Q1.pdf"


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span("operator"),
    ):
        workflow_state_repository().update(lambda state: register_minimal_profile(state, profile_id="operator"))
        yield


def _seed_work_unit(*, modelo: str, filing_year: int, period: str) -> str:
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
    work_unit = WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=bucket_id,
        modelo=ModeloCode(modelo),
        filing_year=filing_year,
        period=period,
        revision_id=revision_id,
        name=f"{modelo}-{filing_year}-{period}",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    repo = WorkUnitCatalogueRepository()
    repo.save(upsert_work_unit(repo.load(), work_unit))
    return work_unit_id


def test_reconcile_happy_path_against_justificante(cli_runner: CliRunner) -> None:
    """The verb produces a `matches` verdict when the work unit and the
    committed modelo_130 fixture align on modelo and ejercicio."""

    work_unit_id = _seed_work_unit(modelo="130", filing_year=2026, period="Q1")

    result = cli_runner.invoke(
        app,
        ["app", "modelo", "reconcile", work_unit_id, "--from-justificante", str(MODELO_130_FIXTURE)],
    )
    assert result.exit_code == 0, result.output
    assert f"work_unit_id\t{work_unit_id}" in result.output
    assert "source_kind\tjustificante" in result.output
    assert "verdict\tmatches" in result.output
    assert "diffs\t0" in result.output


def test_reconcile_mismatch_renders_diff_rows(cli_runner: CliRunner) -> None:
    """A modelo=303 work unit against the modelo_130 fixture renders a
    mismatches verdict with the modelo diff line."""

    work_unit_id = _seed_work_unit(modelo="303", filing_year=2026, period="Q1")

    result = cli_runner.invoke(
        app,
        ["app", "modelo", "reconcile", work_unit_id, "--from-justificante", str(MODELO_130_FIXTURE)],
    )
    assert result.exit_code == 0, result.output
    assert "verdict\tmismatches" in result.output
    assert "diff\tmodelo\twork_unit=303\tevidence=130" in result.output


def test_reconcile_refuses_when_both_source_flags_supplied(cli_runner: CliRunner, tmp_path: Path) -> None:
    """The two source flags are mutually exclusive.
    Supplying both surfaces as typer.BadParameter (exit_code != 0)
    rather than letting the service silently pick one."""

    work_unit_id = _seed_work_unit(modelo="130", filing_year=2026, period="Q1")
    other = tmp_path / "extra.pdf"
    other.write_bytes(b"%PDF-1.4\n")

    result = cli_runner.invoke(
        app,
        [
            "app",
            "modelo",
            "reconcile",
            work_unit_id,
            "--from-justificante",
            str(MODELO_130_FIXTURE),
            "--from-declaration",
            str(other),
        ],
    )
    assert result.exit_code != 0, result.output


def test_reconcile_refuses_when_neither_source_flag_supplied(cli_runner: CliRunner) -> None:
    """Exactly one source must be supplied. Without either flag the
    operator sees a BadParameter rather than a silent default."""

    work_unit_id = _seed_work_unit(modelo="130", filing_year=2026, period="Q1")

    result = cli_runner.invoke(app, ["app", "modelo", "reconcile", work_unit_id])
    assert result.exit_code != 0, result.output


def test_reconcile_refuses_unknown_work_unit(cli_runner: CliRunner) -> None:
    """A work unit id that is not in the active bucket catalogue
    surfaces as a refusal at the CLI exit code."""

    result = cli_runner.invoke(
        app,
        ["app", "modelo", "reconcile", "0" * 64, "--from-justificante", str(MODELO_130_FIXTURE)],
    )
    assert result.exit_code != 0, result.output


def test_reconcile_declaration_source_refused_until_parser_lands(cli_runner: CliRunner, tmp_path: Path) -> None:
    """The --from-declaration variant is reserved (no parser shipped).
    The CLI surfaces the typed refusal from the service layer."""

    work_unit_id = _seed_work_unit(modelo="130", filing_year=2026, period="Q1")
    fake_declaration = tmp_path / "declaration.pdf"
    fake_declaration.write_bytes(b"%PDF-1.4\n")

    result = cli_runner.invoke(
        app,
        ["app", "modelo", "reconcile", work_unit_id, "--from-declaration", str(fake_declaration)],
    )
    assert result.exit_code != 0, result.output


def test_reconcile_by_flag_lands_in_modelo_reconciled_event(cli_runner: CliRunner) -> None:
    """The --by override attaches to the MODELO_RECONCILED event's actor
    field, replacing the default (the active profile display_name).
    Without this thread-through the audit trail would falsely attribute
    every reconciliation to the active profile even when a teammate
    ran the command."""

    from ....domain.buckets import BucketEventHistoryRepository, BucketEventType

    work_unit_id = _seed_work_unit(modelo="130", filing_year=2026, period="Q1")

    result = cli_runner.invoke(
        app,
        [
            "app",
            "modelo",
            "reconcile",
            work_unit_id,
            "--from-justificante",
            str(MODELO_130_FIXTURE),
            "--by",
            "auditor@team",
        ],
    )

    assert result.exit_code == 0, result.output
    catalogue = BucketEventHistoryRepository().load()
    matching = [
        event
        for event in catalogue.events.values()
        if event.event_type is BucketEventType.MODELO_RECONCILED and event.object_id == work_unit_id
    ]
    assert matching, "MODELO_RECONCILED event must land on the catalogue"
    assert matching[-1].actor == "auditor@team"


def test_reconciliation_history_empty_is_instructive(cli_runner: CliRunner) -> None:
    """With no reconciliations recorded, the history verb lists a clean empty."""
    result = cli_runner.invoke(app, ["app", "modelo", "reconciliation-history"])

    assert result.exit_code == 0, result.output
    assert "reconciliation_count\t0" in result.output
    assert "No reconciliations recorded yet" in result.output


def test_reconciliation_history_lists_recorded_reconciliation(cli_runner: CliRunner) -> None:
    """After a reconcile, the history verb lists the recorded verdict row."""
    work_unit_id = _seed_work_unit(modelo="130", filing_year=2026, period="Q1")
    reconcile = cli_runner.invoke(
        app,
        ["app", "modelo", "reconcile", work_unit_id, "--from-justificante", str(MODELO_130_FIXTURE)],
    )
    assert reconcile.exit_code == 0, reconcile.output

    result = cli_runner.invoke(app, ["app", "modelo", "reconciliation-history"])

    assert result.exit_code == 0, result.output
    assert "reconciliation_count\t1" in result.output
    assert work_unit_id in result.output
    assert "matches" in result.output
