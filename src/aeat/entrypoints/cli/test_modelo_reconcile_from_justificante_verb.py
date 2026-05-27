"""CLI surface tests for ``aeat app modelo reconcile-from-justificante``.

The hyphenated sugar verb shares the ``modelo_reconcile`` application
service entry point with the canonical ``aeat app modelo reconcile
WORK_UNIT_ID --from-justificante PATH`` form. These tests lock the
behaviour expected by the complementaria-external-filing-path ADR
2026-05-15 amendment (with the hyphenated-form deviation queued for
ADR amendment).
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aeat.adapters.persistence.storage.sql.engine import dispose_engine
from aeat.application.user_profile._orchestration import profile_create_storage_span
from aeat.application.user_profile._testing import register_minimal_profile
from aeat.application.workflow._persistence import workflow_state_repository
from aeat.domain.modelos._codes import ModeloCode
from aeat.domain.modelos._repository import WorkUnitCatalogueRepository, upsert_work_unit
from aeat.domain.modelos._work_unit import WorkUnit, derive_work_unit_id
from aeat.entrypoints.cli import app
from aeat.tests import FIXTURES_DIR
from aeat.tests.secure_sql import isolated_profile_storage_root

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

MODELO_130_FIXTURE = FIXTURES_DIR / "justificantes" / "modelo_130_2026Q1.pdf"


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    dispose_engine()
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span("operator"),
    ):
        try:
            workflow_state_repository().update(
                lambda state: register_minimal_profile(state, profile_id="operator"),
            )
            yield
        finally:
            dispose_engine()


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
    repo = WorkUnitCatalogueRepository()
    repo.save(
        upsert_work_unit(
            repo.load(),
            WorkUnit(
                work_unit_id=work_unit_id,
                bucket_id=bucket_id,
                modelo=ModeloCode(modelo),
                filing_year=filing_year,
                period=period,
                revision_id=revision_id,
                name=f"{modelo}-{filing_year}-{period}",
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            ),
        ),
    )
    return work_unit_id


def test_reconcile_from_justificante_renders_matches_verdict(cli_runner: CliRunner) -> None:
    """Happy path: the sugar verb produces a `matches` verdict for the
    committed modelo_130 fixture, identical to the flag-based form."""

    work_unit_id = _seed_work_unit(modelo="130", filing_year=2026, period="Q1")

    result = cli_runner.invoke(
        app,
        [
            "app", "modelo", "reconcile-from-justificante",
            str(MODELO_130_FIXTURE),
            work_unit_id,
        ],
    )
    assert result.exit_code == 0, result.output
    assert f"work_unit_id\t{work_unit_id}" in result.output
    assert "source_kind\tjustificante" in result.output
    assert "verdict\tmatches" in result.output


def test_reconcile_from_justificante_requires_both_positional_args(cli_runner: CliRunner) -> None:
    """Both PATH and WORK_UNIT_ID are required positionals."""

    result = cli_runner.invoke(
        app,
        ["app", "modelo", "reconcile-from-justificante", str(MODELO_130_FIXTURE)],
    )
    assert result.exit_code != 0, result.output


def test_reconcile_from_justificante_refuses_unknown_work_unit(
    cli_runner: CliRunner,
) -> None:
    """An unknown work_unit_id is refused through the same service-layer
    typed error the flag form surfaces."""

    result = cli_runner.invoke(
        app,
        [
            "app", "modelo", "reconcile-from-justificante",
            str(MODELO_130_FIXTURE),
            "0" * 64,
        ],
    )
    assert result.exit_code != 0, result.output


def test_reconcile_from_justificante_help_advertises_local_only(
    cli_runner: CliRunner,
) -> None:
    """Help text must signal `local-only` across locales."""

    result = cli_runner.invoke(
        app, ["app", "modelo", "reconcile-from-justificante", "--help"],
    )
    assert result.exit_code == 0, result.output
    assert any(
        token in result.output.lower()
        for token in ("local-only", "local;", "nunca", "mai contacta", "csak helyi")
    ), result.output
