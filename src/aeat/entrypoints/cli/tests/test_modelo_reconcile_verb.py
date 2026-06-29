"""CLI surface tests for the `aeat app modelo reconcile` group.

`reconcile file --file PATH` reconciles a local justificante; `reconcile history`
lists past runs. `reconcile pull` fetches from AEAT (a live read) and is covered
by the application-layer orchestrator + reconcile_capture tests, not here.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....application.user_profile._orchestration import profile_create_storage_span
from ....application.user_profile._testing import register_minimal_profile
from ....application.workflow._persistence import workflow_state_repository
from ....core import Period
from ....domain.modelos._codes import ModeloCode
from ....domain.modelos._repository import WorkUnitCatalogueRepository, upsert_work_unit
from ....domain.modelos._work_unit import WorkUnit, derive_work_unit_id
from ....tests import FIXTURES_DIR
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

MODELO_130_FIXTURE = FIXTURES_DIR / "justificantes" / "modelo_130_2026Q1.pdf"

# The committed justificante fixtures all print the canonical AEAT demo NIF
# ``00000000T``. The active profile's ``identity.tax_id`` is what the reconciler
# compares against the parsed evidence ``tax_id``; aligning the seeded operator
# profile to the fixture's printed NIF lets the happy-path reconcile genuinely
# resolve to ``matches`` (instead of a tax_id mismatch against the auto-derived
# per-profile NIF ``register_minimal_profile`` would otherwise assign).
_FIXTURE_PROFILE_TAX_ID = "00000000T"


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span("operator"),
    ):
        workflow_state_repository().update(
            lambda state: register_minimal_profile(
                state,
                profile_id="operator",
                overrides={"identity.tax_id": _FIXTURE_PROFILE_TAX_ID},
            )
        )
        yield


def _seed_work_unit(*, modelo: str, filing_year: int, period: str) -> str:
    state = workflow_state_repository().load()
    bucket_id = state.active_profile_bucket_id()
    assert bucket_id is not None
    revision_id = "r" + "0" * 63
    filing_period = Period.from_year_and_code(filing_year, period)
    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=filing_period,
        revision_id=revision_id,
    )
    work_unit = WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=bucket_id,
        modelo=ModeloCode(modelo),
        filing_year=filing_year,
        period=filing_period,
        revision_id=revision_id,
        name=f"{modelo}-{filing_year}-{period}",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    repo = WorkUnitCatalogueRepository()
    repo.save(upsert_work_unit(repo.load(), work_unit))
    return work_unit_id


def test_reconcile_file_happy_path() -> None:
    """`reconcile file --file` matches when the work unit and the committed
    modelo_130 fixture align on modelo and ejercicio."""
    work_unit_id = _seed_work_unit(modelo="130", filing_year=2026, period="1T")

    result = invoke_cached_cli(
        ["app", "modelo", "reconcile", "file", work_unit_id, "--file", str(MODELO_130_FIXTURE)],
    )
    assert result.exit_code == 0, result.output
    assert f"work_unit_id\t{work_unit_id}" in result.output
    assert "source_kind\tjustificante" in result.output
    assert "verdict\tmatches" in result.output
    assert "diffs\t0" in result.output


def test_reconcile_file_mismatch_renders_diff_rows() -> None:
    """A modelo=303 work unit against the modelo_130 fixture mismatches with a modelo diff."""
    work_unit_id = _seed_work_unit(modelo="303", filing_year=2026, period="1T")

    result = invoke_cached_cli(
        ["app", "modelo", "reconcile", "file", work_unit_id, "--file", str(MODELO_130_FIXTURE)],
    )
    assert result.exit_code == 0, result.output
    assert "verdict\tmismatches" in result.output
    assert "diff\tmodelo\twork_unit=303\tevidence=130" in result.output


def test_reconcile_file_requires_the_file_option() -> None:
    """`reconcile file` without `--file` is a usage error, not a silent default."""
    work_unit_id = _seed_work_unit(modelo="130", filing_year=2026, period="1T")
    result = invoke_cached_cli(["app", "modelo", "reconcile", "file", work_unit_id])
    assert result.exit_code != 0, result.output


def test_reconcile_file_refuses_unknown_work_unit() -> None:
    """A work unit id absent from the active bucket catalogue refuses at the exit code."""
    result = invoke_cached_cli(
        ["app", "modelo", "reconcile", "file", "0" * 64, "--file", str(MODELO_130_FIXTURE)],
    )
    assert result.exit_code != 0, result.output


def test_reconcile_file_by_flag_lands_in_modelo_reconciled_event() -> None:
    """The --by override attaches to the MODELO_RECONCILED event's actor field."""
    from ....domain.buckets import BucketEventHistoryRepository, BucketEventType

    work_unit_id = _seed_work_unit(modelo="130", filing_year=2026, period="1T")
    result = invoke_cached_cli(
        [
            "app",
            "modelo",
            "reconcile",
            "file",
            work_unit_id,
            "--file",
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


def test_reconcile_history_empty_is_instructive() -> None:
    """With no reconciliations recorded, `reconcile history` lists a clean empty."""
    result = invoke_cached_cli(["app", "modelo", "reconcile", "history"])
    assert result.exit_code == 0, result.output
    assert "reconciliation_count\t0" in result.output
    assert "No reconciliations recorded yet" in result.output


def test_reconcile_history_lists_recorded_reconciliation() -> None:
    """After a reconcile, `reconcile history` lists the recorded verdict row."""
    work_unit_id = _seed_work_unit(modelo="130", filing_year=2026, period="1T")
    reconcile = invoke_cached_cli(
        ["app", "modelo", "reconcile", "file", work_unit_id, "--file", str(MODELO_130_FIXTURE)],
    )
    assert reconcile.exit_code == 0, reconcile.output

    result = invoke_cached_cli(["app", "modelo", "reconcile", "history"])
    assert result.exit_code == 0, result.output
    assert "reconciliation_count\t1" in result.output
