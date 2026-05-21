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
from decimal import Decimal
from pathlib import Path

import pytest

from aeat.adapters.persistence.storage import EphemeralMasterKeyProvider
from aeat.adapters.persistence.storage.sql import SecureObjectRepository
from aeat.adapters.persistence.storage.sql.engine import dispose_engine, get_engine
from aeat.application.calculations import IvaCompensationReconciliationDecision, IvaWalletDecisionRepository
from aeat.application.user_profile._testing import register_minimal_profile
from aeat.application.workflow._persistence import workflow_state_repository
from aeat.core.config import Settings
from aeat.domain.deadlines import AutonomoProfile
from aeat.domain.deadlines._models import IVARegime
from aeat.domain.filing import ModeloCasillaProvenance
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
from aeat.domain.modelos._filing_repository import ModeloRecordCatalogueRepository
from aeat.domain.modelos._repository import WorkUnitCatalogueRepository, upsert_work_unit
from aeat.domain.modelos._verification_repository import VerificationReportCatalogueRepository
from aeat.domain.modelos._work_unit import WorkUnit, derive_work_unit_id

from ._actions import (
    CalculationRevisionNotFoundError,
    CalculationRevisionStateError,
    ModeloIvaWalletReconciliationBlocked,
    file_modelo_revision,
    verify_modelo_revision,
)
from ._export import (
    ModeloExportCommand,
    ModeloExportCrossBucketRefusedError,
    ModeloExportNoActiveBucketError,
    ModeloExportResult,
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


def _seed_profile(*, tax_id: str | None = None) -> str:
    overrides = {"identity.tax_id": tax_id} if tax_id is not None else None
    workflow_state_repository().update(
        lambda state: register_minimal_profile(state, profile_id="operator", overrides=overrides),
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
        verified_at=now if state is not CalculationRevisionState.BORRADOR else None,
        verified_by="operator" if state is not CalculationRevisionState.BORRADOR else None,
    )
    cr_repo = CalculationRevisionCatalogueRepository()
    cr_repo.save(upsert_calculation_revision(cr_repo.load(), revision))
    return work_unit_id, calculation_revision_id


def _blocked_wallet_decision(*, taxpayer_nif: str, period: str = "2T") -> IvaCompensationReconciliationDecision:
    now = datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC)
    return IvaCompensationReconciliationDecision(
        taxpayer_nif=taxpayer_nif,
        target_year=2026,
        target_period=period,
        selected_authority="missing",
        selected_amount=None,
        wallet_amount=Decimal("1200.00"),
        local_recurrence_amount=Decimal("800.00"),
        override_amount=None,
        divergence="wallet_higher",
        blocked=True,
        stale_wallet=False,
        reason="AEAT wallet and local recurrence diverge; review is required before automatic output.",
        wallet_captured_at=now,
        decided_at=now,
    )


def _wallet_decision_repository_at(database_path: Path) -> tuple[IvaWalletDecisionRepository, Settings]:
    settings = Settings(aeat_database_url=f"sqlite:///{database_path.as_posix()}")
    objects = SecureObjectRepository(engine=get_engine(settings))
    return IvaWalletDecisionRepository(objects=objects), settings


def test_export_result_json_surfaces_casilla_provenance(tmp_path: Path) -> None:
    result = ModeloExportResult(
        calculation_revision_id="r" + "1" * 63,
        work_unit_id="w" + "2" * 63,
        bucket_id="bucket-operator",
        modelo="130",
        filing_year=2026,
        period="Q1",
        output_path=tmp_path / "modelo-130.txt",
        byte_size=128,
        file_sha256="a" * 64,
        format="fichero-boe",
        exported_at=datetime(2026, 5, 21, 12, 0, tzinfo=UTC),
        actor="operator",
        bucket_event_id="event-1",
        casilla_provenance=(
            ModeloCasillaProvenance(
                casilla_id="03",
                legal_refs=("ley-35-2006:art-101",),
                source_refs=("aeat-modelo-130-manual-2026",),
            ),
        ),
    )

    payload = result.model_dump(mode="json")

    assert payload["casilla_provenance"] == [
        {
            "casilla_id": "03",
            "legal_refs": ["ley-35-2006:art-101"],
            "source_refs": ["aeat-modelo-130-manual-2026"],
        }
    ]


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


def test_export_refuses_borrador_revision(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    """A revision still in BORRADOR state cannot be exported; only
    verificado-completo or filed revisions are legal export sources.

    Locks the contract from app-modelo-shape ADR §export: the export
    artefact must reflect a revision the operator has already
    verified, not a work-in-progress."""

    bucket_id = _seed_profile()
    _, calc_rev_id = _seed_revision(bucket_id=bucket_id, state=CalculationRevisionState.BORRADOR)

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
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
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


def test_export_refuses_modelo_303_when_persisted_wallet_decision_is_blocked(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    taxpayer_nif = "12345678Z"
    bucket_id = _seed_profile(tax_id=taxpayer_nif)
    _, calc_rev_id = _seed_revision(
        bucket_id=bucket_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        modelo="303",
        filing_year=2026,
        period="2T",
    )
    IvaWalletDecisionRepository().save_decision(_blocked_wallet_decision(taxpayer_nif=taxpayer_nif))

    with pytest.raises(ModeloIvaWalletReconciliationBlocked, match="wallet_higher"):
        export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=calc_rev_id,
                output_path=tmp_path / "out.txt",
                actor="operator",
            ),
            workflow_profile=_profile(),
        )
    assert not (tmp_path / "out.txt").exists()


def test_export_modelo_303_uses_injected_wallet_decision_repository(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    taxpayer_nif = "12345678Z"
    bucket_id = _seed_profile(tax_id=taxpayer_nif)
    _, calc_rev_id = _seed_revision(
        bucket_id=bucket_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        modelo="303",
        filing_year=2026,
        period="2T",
    )
    decision_repo, decision_settings = _wallet_decision_repository_at(tmp_path / "wallet-decisions-export.db")
    decision_repo.save_decision(_blocked_wallet_decision(taxpayer_nif=taxpayer_nif))
    assert IvaWalletDecisionRepository().load_decision(taxpayer_nif, 2026, "2T") is None

    try:
        with pytest.raises(ModeloIvaWalletReconciliationBlocked, match="wallet_higher"):
            export_modelo_revision(
                ModeloExportCommand(
                    calculation_revision_id=calc_rev_id,
                    output_path=tmp_path / "out.txt",
                    actor="operator",
                ),
                workflow_profile=_profile(),
                iva_compensation_decision_repository=decision_repo,
            )
    finally:
        dispose_engine(decision_settings)
    assert not (tmp_path / "out.txt").exists()


def test_verify_modelo_303_uses_injected_wallet_decision_repository(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    taxpayer_nif = "12345678Z"
    bucket_id = _seed_profile(tax_id=taxpayer_nif)
    _, calc_rev_id = _seed_revision(
        bucket_id=bucket_id,
        state=CalculationRevisionState.BORRADOR,
        modelo="303",
        filing_year=2026,
        period="2T",
    )
    decision_repo, decision_settings = _wallet_decision_repository_at(tmp_path / "wallet-decisions.db")
    decision_repo.save_decision(_blocked_wallet_decision(taxpayer_nif=taxpayer_nif))
    assert IvaWalletDecisionRepository().load_decision(taxpayer_nif, 2026, "2T") is None

    try:
        report = verify_modelo_revision(
            calc_rev_id,
            actor="operator",
            workflow_profile=_profile(),
            work_unit_repository=WorkUnitCatalogueRepository(),
            calculation_repository=CalculationRevisionCatalogueRepository(),
            verification_repository=VerificationReportCatalogueRepository(),
            iva_compensation_decision_repository=decision_repo,
        )
    finally:
        dispose_engine(decision_settings)

    assert report.granted_verificado_completo is False
    assert any("wallet_higher" in finding.message for finding in report.findings)
    revision = CalculationRevisionCatalogueRepository().load().get(calc_rev_id)
    assert revision is not None
    assert revision.state is CalculationRevisionState.BORRADOR


def test_file_modelo_303_uses_injected_wallet_decision_repository_before_mutation(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    taxpayer_nif = "12345678Z"
    bucket_id = _seed_profile(tax_id=taxpayer_nif)
    work_unit_id, calc_rev_id = _seed_revision(
        bucket_id=bucket_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        modelo="303",
        filing_year=2026,
        period="2T",
    )
    decision_repo, decision_settings = _wallet_decision_repository_at(tmp_path / "wallet-decisions-file.db")
    decision_repo.save_decision(_blocked_wallet_decision(taxpayer_nif=taxpayer_nif))
    assert IvaWalletDecisionRepository().load_decision(taxpayer_nif, 2026, "2T") is None

    try:
        with pytest.raises(ModeloIvaWalletReconciliationBlocked, match="wallet_higher"):
            file_modelo_revision(
                calc_rev_id,
                actor="operator",
                workflow_profile=_profile(),
                work_unit_repository=WorkUnitCatalogueRepository(),
                calculation_repository=CalculationRevisionCatalogueRepository(),
                filing_repository=ModeloRecordCatalogueRepository(),
                iva_compensation_decision_repository=decision_repo,
            )
    finally:
        dispose_engine(decision_settings)

    revision = CalculationRevisionCatalogueRepository().load().get(calc_rev_id)
    assert revision is not None
    assert revision.state is CalculationRevisionState.VERIFICADO_COMPLETO
    assert (
        ModeloRecordCatalogueRepository()
        .load()
        .current_for(bucket_id=bucket_id, modelo="303", filing_year=2026, period="2T")
        is None
    )
    work_unit = WorkUnitCatalogueRepository().load().get(work_unit_id)
    assert work_unit is not None
    assert work_unit.filed_calculation_revision_id is None
