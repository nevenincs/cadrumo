"""CLI surface tests for ``aeat app modelo export``."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aeat.adapters.persistence.storage import EphemeralMasterKeyProvider
from aeat.adapters.persistence.storage.sql.engine import dispose_engine
from aeat.application.user_profile._orchestration import set_active_fields
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
from aeat.domain.user_profile import UserProfileFact
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


_MODELO_111_INPUTS: dict[str, str] = {
    "03": "180.25",
    "06": "12.10",
    "09": "300.00",
    "12": "14.40",
    "15": "25.00",
    "18": "0.50",
    "21": "7.00",
    "24": "8.00",
    "27": "9.00",
    "29": "40.00",
}


def _seed_exportable_modelo_111_revision(
    *, modelo: str = "111", filing_year: int = 2026, period: str = "2026Q1",
) -> tuple[str, str]:
    """Persist a verified-complete modelo-111 revision ready for export.

    The work unit carries a canonical quarterly period token and the
    revision captures a real modelo-111 casilla input snapshot so the
    registry-backed draft build produces a populated fichero-BOE file.
    """

    state = workflow_state_repository().load()
    bucket_id = state.active_profile_bucket_id()
    assert bucket_id is not None
    revision_id = "r" + "1" * 63
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

    calculation_revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        inputs_snapshot=_MODELO_111_INPUTS,
        binding_overrides={},
        casilla_values={},
    )
    revision = CalculationRevision(
        calculation_revision_id=calculation_revision_id,
        work_unit_id=work_unit_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        inputs_snapshot=_MODELO_111_INPUTS,
        created_at=now,
        updated_at=now,
        verified_at=now,
        verified_by="operator",
    )
    cr_repo = CalculationRevisionCatalogueRepository()
    cr_repo.save(upsert_calculation_revision(cr_repo.load(), revision))
    return work_unit_id, calculation_revision_id


def test_export_modelo_111_end_to_end_writes_file_with_composed_headers(
    cli_runner: CliRunner, tmp_path: Path,
) -> None:
    """Exporting a verified-complete modelo-111 revision end-to-end
    writes a fichero-BOE file without a header-validation error.

    Modelo 111 declares ``declaration_type``, ``surnames``, and
    ``name`` as required export header keys. The export service must
    compose all of them — the operator name from the persisted profile
    facts — or ``_header_field_value`` raises FilingExportValidationError.
    This locks the header-composition contract: a real registry-backed
    export of a non-130 modelo succeeds.
    """

    workflow_state_repository().update(
        lambda state: set_active_fields(
            state,
            (
                UserProfileFact(path="identity.name", value="Ana"),
                UserProfileFact(path="identity.surnames", value="Export Test"),
            ),
        ),
    )
    work_unit_id, _ = _seed_exportable_modelo_111_revision()
    out = tmp_path / "modelo-111.txt"

    result = cli_runner.invoke(
        app,
        ["app", "modelo", "export", work_unit_id, "--output", str(out)],
    )

    assert result.exit_code == 0, result.output
    assert out.exists()
    assert out.stat().st_size > 0


def test_export_modelo_111_refuses_when_profile_name_missing(
    cli_runner: CliRunner, tmp_path: Path,
) -> None:
    """When the active profile lacks ``identity.surnames`` the export
    must refuse with a clear error naming the missing profile fact
    rather than fabricating a placeholder name. ``register_minimal_profile``
    sets ``identity.name`` but not ``identity.surnames``."""

    work_unit_id, _ = _seed_exportable_modelo_111_revision()
    out = tmp_path / "modelo-111.txt"

    result = cli_runner.invoke(
        app,
        ["app", "modelo", "export", work_unit_id, "--output", str(out)],
    )

    assert result.exit_code != 0, result.output
    assert not out.exists()


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
