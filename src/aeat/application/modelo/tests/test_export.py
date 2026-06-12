"""Real-behavior tests for ``export_modelo_revision``.

Covers the application-service safety gates (active-bucket required,
revision must exist, revision state must be exportable, work unit must
belong to the active bucket). Happy-path file emission is covered by
the CLI surface tests, which exercise the full registry-backed draft
build through a typer invocation.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import ExitStack
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.storage.runtime import inspect_bucket_storage_runtime
from ....adapters.persistence.storage.sql.engine import dispose_engine
from ....core import Period
from ....core.config import Settings, override_settings
from ....core.identity import nif_check_letter
from ....core.resources import resources
from ....domain.buckets import BucketEventHistoryRepository, BucketEventType
from ....domain.calculations.registry import CasillaObservation, RegistryModeloObservation
from ....domain.deadlines import TaxpayerProfile
from ....domain.deadlines._models import IVARegime
from ....domain.filing import ModeloCasillaProvenance
from ....domain.iva_compensation._reconciliation import (
    IvaCompensationAuthoritySource,
    IvaCompensationReconciliationDecision,
)
from ....domain.modelos._calculation_repository import (
    CalculationRevisionCatalogueRepository,
    upsert_calculation_revision,
)
from ....domain.modelos._calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos._codes import ModeloCode
from ....domain.modelos._filing_record import ExternalEvidenceKind
from ....domain.modelos._filing_repository import ModeloRecordCatalogueRepository
from ....domain.modelos._repository import WorkUnitCatalogueRepository, upsert_work_unit
from ....domain.modelos._verification_repository import VerificationReportCatalogueRepository
from ....domain.modelos._work_unit import WorkUnit, derive_work_unit_id
from ....tests.secure_sql import isolated_profile_storage_root
from ...calculations import (
    CalculationObservationRepository,
    IvaWalletDecisionRepository,
    cross_period_dependency_requirements,
)
from ...user_profile._orchestration import profile_create_storage_span
from ...user_profile._testing import register_minimal_profile
from ...workflow._persistence import workflow_state_repository
from .._actions import (
    CalculationRevisionNotFoundError,
    CalculationRevisionStateError,
    ModeloIvaWalletReconciliationBlocked,
    calculate_modelo_revision,
    create_work_unit,
    file_modelo_revision,
    import_external_filing_evidence,
    mark_revision_verificado_completo,
    verify_modelo_revision,
)
from .._export import (
    ModeloExportCommand,
    ModeloExportCrossBucketRefusedError,
    ModeloExportNoActiveBucketError,
    ModeloExportResult,
    ModeloIvaWalletDecisionProvenance,
    _compose_export_headers,
    _iva_wallet_decision_export_provenance,
    export_modelo_revision,
)
from .._selectors import ModeloCalculationRevisionSelectorStateError, select_exportable_revision
from .justificante_metadata import persist_justificante_metadata

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ACTIVE_STORAGE_STACK: ExitStack | None = None
_PROFILE_SPAN_OPEN = False


def _profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="taxpayerdefault",
        iva_regime=IVARegime.GENERAL,
    )


@pytest.fixture(autouse=True)
def isolated_backend(tmp_path: Path) -> Iterator[None]:
    global _ACTIVE_STORAGE_STACK, _PROFILE_SPAN_OPEN

    with ExitStack() as stack:
        stack.enter_context(isolated_profile_storage_root(tmp_path=tmp_path))
        _ACTIVE_STORAGE_STACK = stack
        _PROFILE_SPAN_OPEN = False
        try:
            yield
        finally:
            _PROFILE_SPAN_OPEN = False
            _ACTIVE_STORAGE_STACK = None


def _ensure_operator_storage_span() -> None:
    global _PROFILE_SPAN_OPEN

    if _PROFILE_SPAN_OPEN:
        return
    if _ACTIVE_STORAGE_STACK is None:
        raise RuntimeError("modelo export test storage span is not active")
    _ACTIVE_STORAGE_STACK.enter_context(profile_create_storage_span("operator"))
    _PROFILE_SPAN_OPEN = True


def _seed_profile(*, tax_id: str | None = None, profile_overrides: dict[str, str] | None = None) -> str:
    _ensure_operator_storage_span()
    overrides = dict(profile_overrides or {})
    if tax_id is not None:
        overrides["identity.tax_id"] = tax_id
    workflow_state_repository().update(
        lambda state: register_minimal_profile(state, profile_id="operator", overrides=overrides or None),
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
    period: str = "1T",
) -> tuple[str, str]:
    revision_id_suffix = state.value.lower()[:3]
    base = revision_id_suffix + "0" * (63 - len(revision_id_suffix))
    revision_id = "r" + base
    typed_period = Period.from_year_and_code(filing_year, period)
    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=typed_period,
        revision_id=revision_id,
    )
    now = datetime.now(UTC)
    work_unit = WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=bucket_id,
        modelo=ModeloCode(modelo),
        filing_year=filing_year,
        period=typed_period,
        revision_id=revision_id,
        name=f"{modelo}-{filing_year}-{typed_period.registry_token}",
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


def test_export_headers_use_typed_instalment_period_dates(isolated_backend: None) -> None:
    bucket_id = _seed_profile(profile_overrides={"identity.surnames": "Test Surnames", "identity.name": "Test Name"})
    work_unit_id, calculation_revision_id = _seed_revision(
        bucket_id=bucket_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        modelo="202",
        filing_year=2026,
        period="2P",
    )
    work_unit = WorkUnitCatalogueRepository().load().get(work_unit_id)
    revision = CalculationRevisionCatalogueRepository().load().get(calculation_revision_id)
    assert work_unit is not None
    assert revision is not None

    headers = _compose_export_headers(
        work_unit=work_unit,
        revision=revision,
        workflow_profile=_profile(),
        period=Period.from_year_and_code(2026, "2P"),
    )

    assert headers["fecha_inicio_periodo"] == "01102026"
    assert headers["fecha_fin_periodo"] == "31102026"
    assert headers["devengo_start_date"] == "01102026"


def _blocked_wallet_decision(*, taxpayer_nif: str, period: str = "2T") -> IvaCompensationReconciliationDecision:
    now = datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC)
    return IvaCompensationReconciliationDecision(
        taxpayer_nif=taxpayer_nif,
        target_year=2026,
        target_period=Period.from_year_and_code(2026, period),
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


def _filed_history_only_wallet_decision(
    *,
    taxpayer_nif: str,
    period: str = "2T",
) -> IvaCompensationReconciliationDecision:
    now = datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC)
    return IvaCompensationReconciliationDecision(
        taxpayer_nif=taxpayer_nif,
        target_year=2026,
        target_period=Period.from_year_and_code(2026, period),
        selected_authority="filed_history",
        selected_amount=Decimal("800.00"),
        wallet_amount=None,
        local_recurrence_amount=Decimal("800.00"),
        override_amount=None,
        divergence="filed_history_only",
        blocked=True,
        stale_wallet=False,
        reason=(
            "Direct AEAT wallet/cartera evidence is unavailable; AEAT filed-history-derived recurrence "
            "is recorded as fallback evidence but requires explicit taxpayer override before automatic output."
        ),
        wallet_captured_at=None,
        decided_at=now,
    )


def _wallet_only_decision(*, taxpayer_nif: str, period: str = "2T") -> IvaCompensationReconciliationDecision:
    now = datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC)
    return IvaCompensationReconciliationDecision(
        taxpayer_nif=taxpayer_nif,
        target_year=2026,
        target_period=Period.from_year_and_code(2026, period),
        selected_authority="aeat_wallet",
        selected_amount=Decimal("1200.00"),
        wallet_amount=Decimal("1200.00"),
        local_recurrence_amount=None,
        override_amount=None,
        divergence="wallet_only",
        blocked=False,
        stale_wallet=False,
        reason="synthetic wallet-only authority for Modelo 303 export",
        wallet_captured_at=now,
        authority_sources=(
            IvaCompensationAuthoritySource(
                source_kind="aeat_wallet",
                amount=Decimal("1200.00"),
                source_locator="aeat-wallet:synthetic-modelo-303-export-wallet-only",
                captured_at=now,
            ),
        ),
        decided_at=now,
    )


def _modelo_303_engine_inputs() -> dict[str, Decimal]:
    return {
        "modelo-303-iva-repercutido-general-cuota": Decimal("1000.00"),
        "modelo-303-iva-repercutido-reducido-cuota": Decimal("0.00"),
        "modelo-303-iva-repercutido-super-reducido-cuota": Decimal("0.00"),
        "modelo-303-iva-soportado-interiores-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-intracomunitaria-cuota": Decimal("0.00"),
        "modelo-303-profile-state-attribution-ratio": Decimal("100"),
    }


def _seed_modelo_303_1t_clean_state(
    *,
    bucket_id: str,
    taxpayer_tax_id: str = "taxpayerdefault",
    work_unit_repository: WorkUnitCatalogueRepository | None = None,
    calculation_repository: CalculationRevisionCatalogueRepository | None = None,
    bucket_event_repository: BucketEventHistoryRepository | None = None,
) -> None:
    snapshot = resources().modelos.authority.snapshot("303", filing_year=2026, period="2T")
    source_casillas = sorted(
        {
            casilla_id
            for requirement in cross_period_dependency_requirements(snapshot)
            if requirement.source_modelo == "303"
            and requirement.filing_year == 2026
            and requirement.period == Period.from_year_and_code(2026, "1T")
            for casilla_id in requirement.source_casillas
        },
    )
    assert source_casillas, "Modelo 303 2T fixture must declare a 1T filed-history dependency"
    values = {casilla_id: Decimal(index + 1) for index, casilla_id in enumerate(source_casillas)}
    source_snapshot = resources().modelos.authority.snapshot("303", filing_year=2026, period="1T")
    persist_justificante_metadata(
        "JUST-303-2026-1T",
        modelo="303",
        filing_year=2026,
        period="1T",
        captured_at=datetime(2026, 5, 21, 11, 0, tzinfo=UTC),
        tax_id=taxpayer_tax_id,
    )
    work_unit = create_work_unit(
        bucket_id=bucket_id,
        modelo="303",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        revision_id=source_snapshot.revision.id,
        repository=work_unit_repository,
        bucket_event_repository=bucket_event_repository,
        clock=datetime(2026, 5, 21, 11, 0, tzinfo=UTC),
    )
    import_external_filing_evidence(
        work_unit_id=work_unit.work_unit_id,
        casilla_values=values,
        evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
        evidence_reference_id="JUST-303-2026-1T",
        actor="aeat-import-test",
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
        filing_repository=ModeloRecordCatalogueRepository(),
        bucket_event_repository=bucket_event_repository,
        expected_tax_id=taxpayer_tax_id,
        clock=datetime(2026, 5, 21, 11, 1, tzinfo=UTC),
    )
    CalculationObservationRepository().save_observation(
        RegistryModeloObservation(
            modelo="303",
            filing_year=2026,
            period="1T",
            observations=tuple(
                CasillaObservation(casilla_id=casilla_id, value=value) for casilla_id, value in values.items()
            ),
        ),
        source_kind="aeat_sede_justificante",
        captured_at=datetime(2026, 5, 21, 11, 2, tzinfo=UTC),
        stamped_revision_id=source_snapshot.revision.id,
        source_metadata={
            "aeat_register_status": "ALTA",
            "authenticated_identity": taxpayer_tax_id,
        },
    )


def _synthetic_valid_nif(number: int) -> str:
    return f"{number:08d}{nif_check_letter(number)}"


def _wallet_decision_repository_at(sidecar_root: Path) -> tuple[IvaWalletDecisionRepository, Settings]:
    settings = Settings(aeat_local_storage_root=sidecar_root, aeat_active_profile="operator")
    objects = inspect_bucket_storage_runtime("operator", settings).secure_object_repository()
    return IvaWalletDecisionRepository(objects=objects), settings


def test_export_result_json_surfaces_casilla_provenance(tmp_path: Path) -> None:
    result = ModeloExportResult(
        calculation_revision_id="a" * 64,
        work_unit_id="b" * 64,
        bucket_id="bucket-operator",
        modelo="130",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
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

    assert payload["period"] == {"filing_year": 2026, "code": "1T"}
    assert payload["casilla_provenance"] == [
        {
            "casilla_id": "03",
            "formula_id": None,
            "legal_refs": ["ley-35-2006:art-101"],
            "source_refs": ["aeat-modelo-130-manual-2026"],
        },
    ]


def test_export_result_json_surfaces_redacted_iva_wallet_decision_provenance(tmp_path: Path) -> None:
    result = ModeloExportResult(
        calculation_revision_id="a" * 64,
        work_unit_id="b" * 64,
        bucket_id="bucket-operator",
        modelo="303",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "2T"),
        output_path=tmp_path / "modelo-303.txt",
        byte_size=128,
        file_sha256="a" * 64,
        format="fichero-boe",
        exported_at=datetime(2026, 5, 21, 12, 0, tzinfo=UTC),
        actor="operator",
        bucket_event_id="event-1",
        iva_wallet_decision_provenance=ModeloIvaWalletDecisionProvenance(
            decision_ref="sha256:" + "1" * 64,
            selected_authority="aeat_wallet",
            divergence="wallet_only",
            target_year=2026,
            target_period=Period.from_year_and_code(2026, "2T"),
            authority_source_kinds=("aeat_wallet",),
            authority_source_refs=("sha256:" + "2" * 64,),
        ),
    )

    payload = result.model_dump(mode="json")

    assert payload["period"] == {"filing_year": 2026, "code": "2T"}
    assert payload["iva_wallet_decision_provenance"] == {
        "decision_ref": "sha256:" + "1" * 64,
        "selected_authority": "aeat_wallet",
        "divergence": "wallet_only",
        "target_year": 2026,
        "target_period": {"filing_year": 2026, "code": "2T"},
        "authority_source_kinds": ["aeat_wallet"],
        "authority_source_refs": ["sha256:" + "2" * 64],
    }


def test_iva_wallet_export_provenance_redacts_taxpayer_amounts_and_source_locators() -> None:
    decided_at = datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC)
    decision = IvaCompensationReconciliationDecision(
        taxpayer_nif="synthetic-sensitive-marker",
        target_year=2026,
        target_period=Period.from_year_and_code(2026, "2T"),
        selected_authority="aeat_wallet",
        selected_amount=Decimal("1200.00"),
        wallet_amount=Decimal("1200.00"),
        local_recurrence_amount=None,
        override_amount=None,
        divergence="wallet_only",
        blocked=False,
        stale_wallet=False,
        reason="wallet-only synthetic decision",
        wallet_captured_at=decided_at,
        authority_sources=(
            IvaCompensationAuthoritySource(
                source_kind="aeat_wallet",
                amount=Decimal("1200.00"),
                source_locator="aeat-wallet-reference-containing-synthetic-sensitive-marker",
                captured_at=decided_at,
            ),
        ),
        decided_at=decided_at,
    )

    provenance = _iva_wallet_decision_export_provenance(decision)

    assert provenance is not None
    payload_text = provenance.model_dump_json()
    assert provenance.selected_authority == "aeat_wallet"
    assert provenance.divergence == "wallet_only"
    assert provenance.decision_ref.startswith("sha256:")
    assert provenance.authority_source_refs[0].startswith("sha256:")
    assert "synthetic-sensitive-marker" not in payload_text
    assert "1200" not in payload_text
    assert "aeat-wallet-reference" not in payload_text


def test_export_refuses_when_no_active_bucket(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    """Without an active profile bucket the service cannot scope the
    MODELO_EXPORTED event and must refuse cleanly."""

    with pytest.raises(ModeloExportNoActiveBucketError) as exc_info, override_settings(aeat_active_profile=None):
        export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id="0" * 64,
                output_path=tmp_path / "out.txt",
                actor="operator",
            ),
            workflow_profile=_profile(),
        )
    assert exc_info.value.translated_message == "application.modelo.errors.export_no_active_bucket"
    assert exc_info.value.context is None


def test_export_refuses_unknown_revision(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    """An addressed calculation revision id that is not in the
    catalogue surfaces as CalculationRevisionNotFoundError."""

    _seed_profile()

    with pytest.raises(CalculationRevisionNotFoundError) as exc_info:
        export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id="f" * 64,
                output_path=tmp_path / "out.txt",
                actor="operator",
            ),
            workflow_profile=_profile(),
        )
    assert exc_info.value.translated_message == "application.modelo.errors.calculation_revision_not_found"
    assert exc_info.value.context == {"calculation_revision_id": "f" * 64}


def test_export_refuses_borrador_revision(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    """A revision still in BORRADOR state cannot be exported; only
    verificado-completo or filed revisions are legal export sources.

    The export artefact must reflect a revision the operator has
    already verified, not a work-in-progress."""

    bucket_id = _seed_profile()
    _, calc_rev_id = _seed_revision(bucket_id=bucket_id, state=CalculationRevisionState.BORRADOR)

    with pytest.raises(CalculationRevisionStateError) as exc_info:
        export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=calc_rev_id,
                output_path=tmp_path / "out.txt",
                actor="operator",
            ),
            workflow_profile=_profile(),
        )
    assert exc_info.value.translated_message == "application.modelo.errors.export_revision_state_refused"
    assert exc_info.value.context == {
        "calculation_revision_id": calc_rev_id,
        "state": CalculationRevisionState.BORRADOR.value,
    }


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

    with pytest.raises(ModeloExportCrossBucketRefusedError) as exc_info:
        export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=calc_rev_id,
                output_path=tmp_path / "out.txt",
                actor="operator",
            ),
            workflow_profile=_profile(),
        )
    assert exc_info.value.translated_message == "application.modelo.errors.export_cross_bucket_refused"
    assert isinstance(exc_info.value.context, dict)
    assert "work_unit_id" in exc_info.value.context


def test_export_refuses_modelo_303_when_persisted_wallet_decision_is_blocked(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    taxpayer_nif = "taxpayerbeta"
    bucket_id = _seed_profile(tax_id=taxpayer_nif)
    _, calc_rev_id = _seed_revision(
        bucket_id=bucket_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        modelo="303",
        filing_year=2026,
        period="2T",
    )
    _seed_modelo_303_1t_clean_state(bucket_id=bucket_id)
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


def test_export_refuses_modelo_303_when_persisted_wallet_decision_is_filed_history_only(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    taxpayer_nif = "taxpayeralpha"
    bucket_id = _seed_profile(tax_id=taxpayer_nif)
    _, calc_rev_id = _seed_revision(
        bucket_id=bucket_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        modelo="303",
        filing_year=2026,
        period="2T",
    )
    _seed_modelo_303_1t_clean_state(bucket_id=bucket_id)
    IvaWalletDecisionRepository().save_decision(_filed_history_only_wallet_decision(taxpayer_nif=taxpayer_nif))

    with pytest.raises(ModeloIvaWalletReconciliationBlocked, match="filed_history_only"):
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
    taxpayer_nif = "taxpayerbeta"
    bucket_id = _seed_profile(tax_id=taxpayer_nif)
    _, calc_rev_id = _seed_revision(
        bucket_id=bucket_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        modelo="303",
        filing_year=2026,
        period="2T",
    )
    _seed_modelo_303_1t_clean_state(bucket_id=bucket_id)
    decision_repo, decision_settings = _wallet_decision_repository_at(tmp_path / "wallet-decisions-export.db")
    decision_repo.save_decision(_blocked_wallet_decision(taxpayer_nif=taxpayer_nif))
    assert IvaWalletDecisionRepository().load_decision(taxpayer_nif, Period.from_year_and_code(2026, "2T")) is None

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


def test_export_modelo_303_wallet_only_revision_writes_fichero_with_redacted_wallet_provenance(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    taxpayer_nif = _synthetic_valid_nif(12_345_678)
    bucket_id = _seed_profile(
        tax_id=taxpayer_nif,
        profile_overrides={"identity.surnames": "Test Surnames"},
    )
    snapshot = resources().modelos.authority.snapshot("303", filing_year=2026, period="2T")
    work_repo = WorkUnitCatalogueRepository()
    calc_repo = CalculationRevisionCatalogueRepository()
    event_repo = BucketEventHistoryRepository()
    decision = _wallet_only_decision(taxpayer_nif=taxpayer_nif)
    IvaWalletDecisionRepository().save_decision(decision)

    work_unit = create_work_unit(
        bucket_id=bucket_id,
        modelo="303",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "2T"),
        revision_id=snapshot.revision.id,
        repository=work_repo,
        bucket_event_repository=event_repo,
        clock=datetime(2026, 5, 21, 12, 0, tzinfo=UTC),
    )
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        actor="operator",
        casilla_inputs={
            "iva.prorrata-volumen-con-derecho": Decimal("100.00"),
            "iva.prorrata-volumen-total": Decimal("100.00"),
        },
        binding_values=_modelo_303_engine_inputs(),
        iva_compensation_decision=decision,
        filing_period_date=date(2026, 6, 30),
        work_unit_repository=work_repo,
        calculation_repository=calc_repo,
        bucket_event_repository=event_repo,
        clock=datetime(2026, 5, 21, 12, 1, tzinfo=UTC),
    )
    verified = mark_revision_verificado_completo(
        revision.calculation_revision_id,
        actor="operator",
        calculation_repository=calc_repo,
        clock=datetime(2026, 5, 21, 12, 2, tzinfo=UTC),
    )
    _seed_modelo_303_1t_clean_state(
        bucket_id=bucket_id,
        taxpayer_tax_id=taxpayer_nif,
        work_unit_repository=work_repo,
        calculation_repository=calc_repo,
        bucket_event_repository=event_repo,
    )

    output_path = tmp_path / "modelo-303-wallet-only.txt"
    result = export_modelo_revision(
        ModeloExportCommand(
            calculation_revision_id=verified.calculation_revision_id,
            output_path=output_path,
            actor="operator",
        ),
        workflow_profile=TaxpayerProfile(tax_id=taxpayer_nif, iva_regime=IVARegime.GENERAL),
        work_unit_repository=work_repo,
        calculation_repository=calc_repo,
        bucket_event_repository=event_repo,
        clock=datetime(2026, 5, 21, 12, 3, tzinfo=UTC),
    )

    assert output_path.exists()
    assert result.modelo == "303"
    assert result.byte_size == output_path.stat().st_size
    assert result.file_sha256
    assert result.casilla_provenance
    provenance = result.iva_wallet_decision_provenance
    assert provenance is not None
    assert provenance.selected_authority == "aeat_wallet"
    assert provenance.divergence == "wallet_only"
    assert provenance.target_year == 2026
    assert provenance.target_period == Period.from_year_and_code(2026, "2T")
    assert provenance.decision_ref.startswith("sha256:")
    assert provenance.authority_source_kinds == ("aeat_wallet",)
    assert provenance.authority_source_refs[0].startswith("sha256:")

    event = event_repo.load().for_bucket(bucket_id, event_types=(BucketEventType.MODELO_EXPORTED,))[-1]
    assert event.payload["period"] == "2T"
    assert event.payload["iva_wallet_selected_authority"] == "aeat_wallet"
    assert event.payload["iva_wallet_divergence"] == "wallet_only"
    assert event.payload["iva_wallet_target_period"] == "2T"
    result_json = result.model_dump_json()
    event_json = event.model_dump_json()
    exported_text = output_path.read_text(encoding="utf-8")
    assert taxpayer_nif in exported_text
    assert taxpayer_nif not in result_json
    assert taxpayer_nif not in event_json
    assert "1200" not in result_json
    assert "1200" not in event_json
    assert "synthetic-modelo-303-export" not in result_json
    assert "synthetic-modelo-303-export" not in event_json


def test_verify_modelo_303_surfaces_filed_history_only_wallet_decision_as_blocking_readiness(
    isolated_backend: None,
) -> None:
    taxpayer_nif = "taxpayeralpha"
    bucket_id = _seed_profile(tax_id=taxpayer_nif)
    _, calc_rev_id = _seed_revision(
        bucket_id=bucket_id,
        state=CalculationRevisionState.BORRADOR,
        modelo="303",
        filing_year=2026,
        period="2T",
    )
    IvaWalletDecisionRepository().save_decision(_filed_history_only_wallet_decision(taxpayer_nif=taxpayer_nif))

    report = verify_modelo_revision(
        calc_rev_id,
        actor="operator",
        workflow_profile=_profile(),
        work_unit_repository=WorkUnitCatalogueRepository(),
        calculation_repository=CalculationRevisionCatalogueRepository(),
        verification_repository=VerificationReportCatalogueRepository(),
    )

    assert report.granted_verificado_completo is False
    assert any("filed_history_only" in finding.message for finding in report.findings)
    revision = CalculationRevisionCatalogueRepository().load().get(calc_rev_id)
    assert revision is not None
    assert revision.state is CalculationRevisionState.BORRADOR


def test_verify_modelo_303_uses_injected_wallet_decision_repository(
    isolated_backend: None,
    tmp_path: Path,
) -> None:
    taxpayer_nif = "taxpayerbeta"
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
    assert IvaWalletDecisionRepository().load_decision(taxpayer_nif, Period.from_year_and_code(2026, "2T")) is None

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
    taxpayer_nif = "taxpayerbeta"
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
    assert IvaWalletDecisionRepository().load_decision(taxpayer_nif, Period.from_year_and_code(2026, "2T")) is None

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
        .current_for(bucket_id=bucket_id, modelo="303", filing_year=2026, period=Period.from_year_and_code(2026, "2T"))
        is None
    )
    work_unit = WorkUnitCatalogueRepository().load().get(work_unit_id)
    assert work_unit is not None
    assert work_unit.filed_calculation_revision_id is None


def test_exportable_selector_refuses_verified_fallback_when_current_draft_conflicts(
    isolated_backend: None,
) -> None:
    bucket_id = _seed_profile()
    work_repo = WorkUnitCatalogueRepository()
    calc_repo = CalculationRevisionCatalogueRepository()
    work_unit = create_work_unit(
        bucket_id=bucket_id,
        modelo="130",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        revision_id="2019-y-siguientes",
        repository=work_repo,
        clock=datetime(2026, 6, 4, 10, 0, tzinfo=UTC),
    )
    verified_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        inputs_snapshot={"01": "10"},
        binding_overrides={},
        casilla_values={"01": Decimal("10")},
    )
    draft_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        inputs_snapshot={"01": "20"},
        binding_overrides={},
        casilla_values={"01": Decimal("20")},
    )
    verified = CalculationRevision(
        calculation_revision_id=verified_id,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        inputs_snapshot={"01": "10"},
        casilla_values={"01": Decimal("10")},
        created_at=datetime(2026, 6, 4, 10, 1, tzinfo=UTC),
        updated_at=datetime(2026, 6, 4, 10, 1, tzinfo=UTC),
        verified_at=datetime(2026, 6, 4, 10, 1, tzinfo=UTC),
        verified_by="operator",
    )
    draft = CalculationRevision(
        calculation_revision_id=draft_id,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        inputs_snapshot={"01": "20"},
        casilla_values={"01": Decimal("20")},
        created_at=datetime(2026, 6, 4, 10, 2, tzinfo=UTC),
        updated_at=datetime(2026, 6, 4, 10, 2, tzinfo=UTC),
    )
    catalogue = upsert_calculation_revision(calc_repo.load(), verified)
    calc_repo.save(upsert_calculation_revision(catalogue, draft))
    work_unit = work_unit.model_copy(update={"current_calculation_revision_id": draft.calculation_revision_id})
    work_repo.save(upsert_work_unit(work_repo.load(), work_unit))

    with pytest.raises(ModeloCalculationRevisionSelectorStateError, match="still draft"):
        select_exportable_revision(work_unit, calculation_repository=calc_repo)
