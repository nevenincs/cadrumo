"""Real-behavior tests for ``export_modelo_revision``.

Covers the application-service safety gates (active-bucket required,
revision must exist, revision state must be exportable, work unit must
belong to the active bucket). Happy-path file emission is covered by
the CLI surface tests, which exercise the full registry-backed draft
build through a typer invocation.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from aeat.adapters.persistence.storage import EphemeralMasterKeyProvider
from aeat.adapters.persistence.storage.sql.engine import dispose_engine
from aeat.application.user_profile._testing import register_minimal_profile
from aeat.application.workflow._persistence import workflow_state_repository
from aeat.domain.deadlines import AutonomoProfile
from aeat.domain.deadlines._models import IVARegime
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

from ._actions import CalculationRevisionNotFoundError, CalculationRevisionStateError
from ._export import (
    ModeloExportCommand,
    ModeloExportCrossBucketRefusedError,
    ModeloExportNoActiveBucketError,
    export_modelo_revision,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def _profile() -> AutonomoProfile:
    return AutonomoProfile(
        tax_id="X1234567L",
        iva_regime=IVARegime.GENERAL,
    )


@pytest.fixture
def isolated_backend(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'export.db').as_posix()}")
    dispose_engine()
    with EphemeralMasterKeyProvider():
        try:
            yield
        finally:
            dispose_engine()


def _seed_profile() -> str:
    workflow_state_repository().update(
        lambda state: register_minimal_profile(state, profile_id="operator"),
    )
    bucket_id = workflow_state_repository().load().active_profile_bucket_id()
    assert bucket_id is not None
    return bucket_id


def _seed_revision(
    *,
    bucket_id: str,
    state: CalculationRevisionState,
    modelo: str = "130",
    filing_year: int = 2026,
    period: str = "Q1",
) -> tuple[str, str]:
    revision_id_suffix = state.value.lower()[:3]
    base = revision_id_suffix + "0" * (63 - len(revision_id_suffix))
    revision_id = "r" + base
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
    WorkUnitCatalogueRepository().save(
        upsert_work_unit(WorkUnitCatalogueRepository().load(), work_unit),
    )
    calculation_revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        inputs_snapshot={},
        binding_overrides={},
        casilla_values={},
    )
    revision = CalculationRevision(
        calculation_revision_id=calculation_revision_id,
        work_unit_id=work_unit_id,
        state=state,
        created_at=now,
        updated_at=now,
        verified_at=now if state is not CalculationRevisionState.DRAFT else None,
        verified_by="operator" if state is not CalculationRevisionState.DRAFT else None,
    )
    cr_repo = CalculationRevisionCatalogueRepository()
    cr_repo.save(upsert_calculation_revision(cr_repo.load(), revision))
    return work_unit_id, calculation_revision_id


def test_export_refuses_when_no_active_bucket(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    """Without an active profile bucket the service cannot scope the
    MODELO_EXPORTED event and must refuse cleanly."""

    with pytest.raises(ModeloExportNoActiveBucketError, match=r"aeat config profile create NAME"):
        export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id="r" + "0" * 63,
                output_path=tmp_path / "out.txt",
                actor="operator",
            ),
            workflow_profile=_profile(),
        )


def test_export_refuses_unknown_revision(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    """An addressed calculation revision id that is not in the
    catalogue surfaces as CalculationRevisionNotFoundError."""

    _seed_profile()

    with pytest.raises(CalculationRevisionNotFoundError, match=r"no calculation revision"):
        export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id="r" + "f" * 63,
                output_path=tmp_path / "out.txt",
                actor="operator",
            ),
            workflow_profile=_profile(),
        )


def test_export_refuses_draft_revision(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    """A revision still in DRAFT state cannot be exported; only
    verified-complete or filed revisions are legal export sources.

    Locks the contract from app-modelo-shape ADR §export: the export
    artefact must reflect a revision the operator has already
    verified, not a work-in-progress."""

    bucket_id = _seed_profile()
    _, calc_rev_id = _seed_revision(bucket_id=bucket_id, state=CalculationRevisionState.DRAFT)

    with pytest.raises(CalculationRevisionStateError, match=r"verified-complete or filed"):
        export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=calc_rev_id,
                output_path=tmp_path / "out.txt",
                actor="operator",
            ),
            workflow_profile=_profile(),
        )


def test_export_refuses_cross_bucket_revision(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    """A revision whose parent work unit lives in a non-active bucket
    is refused. Allowing the service to emit the MODELO_EXPORTED
    event into a foreign bucket would let any caller pollute another
    operator's history."""

    _seed_profile()
    foreign_bucket_id = "other-bucket-7" * 4
    _, calc_rev_id = _seed_revision(
        bucket_id=foreign_bucket_id,
        state=CalculationRevisionState.VERIFIED_COMPLETE,
    )

    with pytest.raises(ModeloExportCrossBucketRefusedError, match=r"active profile bucket"):
        export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=calc_rev_id,
                output_path=tmp_path / "out.txt",
                actor="operator",
            ),
            workflow_profile=_profile(),
        )
