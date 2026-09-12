"""Shared composition for live IVA state and filed-observation persistence.

This is the single outer binding used by CLI, TUI, and recorded operations.
It deliberately lives beside the entrypoint composition rather than inside the
CLI package: shared operation registration must not acquire a transitive
dependency on a frontend package.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ..adapters.outbound.aeat.sede.declarations import open_declarations_register, shared_playwright
from ..adapters.outbound.aeat.sede.iva_compensation_wallet import (
    PRE303_PRESENTATION_SERVICE_URL,
    fetch_iva_compensation_wallet,
)
from ..adapters.outbound.aeat.sede.observation_store import FiledDeclaracionObservationStore
from ..adapters.outbound.aeat.sede.schema import IvaCompensationWalletObservation
from ..adapters.outbound.aeat.sede.filed_observation_persistence import (
    BaselineImportAdapter,
    BucketEventRepositoryAdapter,
    CalculationObservationRepositoryAdapter,
    FiledDeclarationTransformationAdapter,
    FiledObservationParserAdapter,
    FiledObservationStoreAdapter,
    FilingRepositoryAdapter,
    IvaHistoryRepositoryAdapter,
    IvaObservationPersistenceAdapter,
    JustificanteRepositoryAdapter,
)
from ..adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ..adapters.persistence.profile.iva_remote_state import IvaRemoteStateAcquisitionManifestRepository
from ..adapters.persistence.profile.justificante import JustificanteRepository
from ..adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ..adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ..adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ..adapters.persistence.storage.errors import StorageValidationError
from ..adapters.persistence.storage.master_key.active_session import active_bucket_session_serves
from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from ..adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ..application.auth.session_types import AeatSession
from ..application.auth.sessions import AuthenticatedAeatSessionResult, ensure_authenticated_aeat_session
from ..application.calculations.iva_compensation_history import IvaCompensationHistoryRepository
from ..application.calculations.iva_wallet_reconciliation import reconcile_modelo_303_iva_compensation
from ..application.calculations.observations_repository import (
    CalculationObservationRepository,
    IvaWalletDecisionRepository,
    iva_wallet_decision_key,
)
from ..application.live.errors import LiveApplicationError
from ..application.live.filed_data_capture import capture_report_path
from ..application.live.filed_observation_persistence import (
    latest_declarations_by_period,
    persist_iva_compensation_history_observations_strict,
)
from ..application.live.filed_observation_ports import FiledObservationPersistencePorts
from ..application.live.iva_remote_state_ports import IvaRemoteStatePort
from ..application.live.remote_state_models import (
    IvaCompensationCarryForwardLotRow,
    IvaCompensationHistoryCaptureReport,
    IvaCompensationHistoryReport,
    IvaCompensationHistoryRow,
    IvaRemoteStateAcquisitionManifest,
    IvaWalletAuthorityDecisionRow,
    IvaWalletCaptureReport,
)
from ..application.live.remote_state_outcomes import evidence_ref
from ..application.live.session import active_verified_session
from ..core.bucket_pointer import require_active_bucket_id
from ..core.config import Settings, load_settings
from ..core.errors.hierarchy import CadrumoError
from ..core.hashing import sha256_hex
from ..core.identity.tax_id import tax_id_identity_token
from ..core.modelo import Modelo
from ..core.period import Period
from ..core.storage_taxonomy import StorageCategory
from ..core.storage_taxonomy_locations import storage_location
from ..core.time.clock import now
from ..domain.calculations.registry.authority import bundled_authority
from ..domain.iva_compensation.carry_forward import build_iva_compensation_carry_forward_report

_WALLET_DIRNAME = Path(storage_location(StorageCategory.LIVE_STATE_IVA_WALLET).subpath).name


@dataclass(frozen=True, slots=True)
class LiveStateComposition:
    """One immutable live-state dependency bundle for one bucket and root."""

    bucket_id: str
    output_root: Path
    objects: SecureObjectRepository
    ports: FiledObservationPersistencePorts
    iva_remote_state_port: IvaRemoteStatePort


def compose_filed_observation_persistence_ports(
    *,
    bucket_id: str,
    output_root: Path,
    objects: SecureObjectRepository,
) -> FiledObservationPersistencePorts:
    """Compose every filed-observation port against one secure backend."""
    work_unit_repository = WorkUnitCatalogueRepository(bucket_id=bucket_id, objects=objects)
    calculation_revision_repository = CalculationRevisionCatalogueRepository(bucket_id=bucket_id, objects=objects)
    filing_repository = ModeloRecordCatalogueRepository(bucket_id=bucket_id, objects=objects)
    bucket_event_repository = BucketEventHistoryRepository(objects=objects)
    justificante_repository = JustificanteRepository(objects=objects)
    calculation_repository = CalculationObservationRepository(bucket_id=bucket_id, objects=objects)
    iva_history_repository = IvaCompensationHistoryRepository(bucket_id=bucket_id, objects=objects)
    return FiledObservationPersistencePorts(
        parser=FiledObservationParserAdapter(),
        transformation=FiledDeclarationTransformationAdapter(),
        observation_persistence=FiledObservationStoreAdapter(root=output_root, objects=objects),
        calculation_repository=CalculationObservationRepositoryAdapter(repository=calculation_repository),
        iva_history_repository=IvaHistoryRepositoryAdapter(repository=iva_history_repository),
        iva_observation_persistence=IvaObservationPersistenceAdapter(),
        justificante_repository=JustificanteRepositoryAdapter(repository=justificante_repository),
        filing_repository=FilingRepositoryAdapter(repository=filing_repository),
        bucket_event_repository=BucketEventRepositoryAdapter(repository=bucket_event_repository),
        baseline_import=BaselineImportAdapter(
            work_unit_repository=work_unit_repository,
            calculation_repository=calculation_revision_repository,
            filing_repository=filing_repository,
            bucket_event_repository=bucket_event_repository,
            justificante_repository=justificante_repository,
            observation_repository=calculation_repository,
        ),
    )


def compose_live_state(
    output_root: Path | None = None,
    *,
    bucket_id: str | None = None,
    objects: SecureObjectRepository | None = None,
) -> LiveStateComposition:
    """Compose the shared live-state port and filed-observation ports once."""
    settings = load_settings()
    resolved_bucket_id = (bucket_id or require_active_bucket_id()).strip()
    if not resolved_bucket_id:
        raise LiveApplicationError(translated_message="application.workflow.errors.no_active_profile_bucket")
    resolved_root = Path(output_root) if output_root is not None else settings.cadrumo_live_state_dir / _WALLET_DIRNAME
    secure_objects = objects or secure_object_repository_for_bucket(resolved_bucket_id)
    filed_ports = compose_filed_observation_persistence_ports(
        bucket_id=resolved_bucket_id,
        output_root=resolved_root,
        objects=secure_objects,
    )
    remote_port = AppIvaRemoteStatePort(objects=secure_objects, filed_observation_ports=filed_ports)
    return LiveStateComposition(
        bucket_id=resolved_bucket_id,
        output_root=resolved_root,
        objects=secure_objects,
        ports=filed_ports,
        iva_remote_state_port=remote_port,
    )


class AppIvaRemoteStatePort:
    """Outer implementation of the live IVA application port."""

    def __init__(self, *, objects: SecureObjectRepository, filed_observation_ports: FiledObservationPersistencePorts) -> None:
        """Bind the port to one secure backend and filed-observation bundle."""
        self._objects = objects
        self._filed_observation_ports = filed_observation_ports

    @property
    def wallet_target_url(self) -> str:
        """Return the read-only AEAT wallet endpoint."""
        return PRE303_PRESENTATION_SERVICE_URL

    @contextmanager
    def active_storage_span(self) -> AbstractContextManager[None]:
        """Require the active bucket session for every storage operation."""
        bucket_id = require_active_bucket_id()
        if not active_bucket_session_serves(bucket_id):
            raise StorageValidationError(translated_message="errors.storage.runtime.not_ready")
        yield

    def persist_manifest(self, manifest: IvaRemoteStateAcquisitionManifest) -> None:
        """Persist one redacted remote-state acquisition manifest."""
        IvaRemoteStateAcquisitionManifestRepository(objects=self._objects).save(manifest)

    async def active_verified_session(self, *, operation: str, target_url: str | None) -> tuple[AeatSession, Settings]:
        """Resolve the active authenticated AEAT session."""
        return await active_verified_session(operation=operation, target_url=target_url)

    def ensure_authenticated_session(
        self,
        settings: Settings,
        *,
        operation: str,
        target_url: str | None,
    ) -> Awaitable[AuthenticatedAeatSessionResult]:
        """Start the configured authentication flow."""
        return ensure_authenticated_aeat_session(settings, operation=operation, target_url=target_url)

    def list_history(self, *, as_of_year: int | None) -> IvaCompensationHistoryReport:
        """List persisted IVA history and authority decisions."""
        states = IvaCompensationHistoryRepository(objects=self._objects).list_periods()
        decisions = IvaWalletDecisionRepository(objects=self._objects).list_decisions()
        carry_forward = build_iva_compensation_carry_forward_report(states, as_of_year=as_of_year or now().year)
        return IvaCompensationHistoryReport(
            row_count=len(states),
            rows=tuple(_history_row(state) for state in states),
            as_of_year=carry_forward.as_of_year,
            carry_forward_lot_count=len(carry_forward.lots),
            carry_forward_lots=tuple(carry_forward_lot_row(lot) for lot in carry_forward.lots),
            unallocated_applied_amount=str(carry_forward.unallocated_applied_amount),
            authority_decision_count=len(decisions),
            authority_decisions=tuple(_decision_row(decision) for decision in decisions),
        )

    async def capture_history(
        self,
        session: AeatSession,
        *,
        settings: Settings,
        year_from: int,
        year_to: int,
        output_root: Path,
        progress_context: dict[str, object] | None,
    ) -> IvaCompensationHistoryCaptureReport:
        """Capture and persist filed Modelo 303 history."""
        store = self._filed_observation_ports.observation_persistence
        paths: list[str] = []
        artefacts: list[str] = []
        observations = []
        failures: list[str] = []
        casilla_count = 0
        async with (
            shared_playwright(session) as playwright,
            open_declarations_register(session, settings=settings, playwright=playwright) as register,
        ):
            for year in range(year_to, year_from - 1, -1):
                if progress_context is not None:
                    progress_context.update(
                        {"stage": "walk_declarations_register", "modelo": Modelo.M303.value, "ejercicio": year}
                    )
                declarations = await register.walk(modelo=Modelo.M303.value, ejercicio=year)
                for declaration in latest_declarations_by_period(declarations):
                    if progress_context is not None:
                        progress_context.update(
                            {
                                "stage": "capture_declaration_observation",
                                "modelo": declaration.modelo,
                                "ejercicio": declaration.ejercicio,
                                "period": declaration.period.registry_token,
                            }
                        )
                    try:
                        observation = await asyncio.wait_for(
                            register.capture_observation(declaration, artefact_sink=store.persist_artefact),
                            timeout=settings.cadrumo_live_iva_declaration_capture_timeout_ms / 1000,
                        )
                    except (TimeoutError, CadrumoError, OSError) as exc:
                        failures.append(
                            f"modelo={declaration.modelo};ejercicio={declaration.ejercicio};period={declaration.period.registry_token};failure_type={type(exc).__name__}"
                        )
                        continue
                    manifest_path = store.persist_observation(observation)
                    paths.append(capture_report_path(manifest_path, output_root=output_root))
                    artefacts.extend(
                        artefact.storage_ref for artefact in observation.artefacts if artefact.storage_ref is not None
                    )
                    casilla_count += len(observation.casillas)
                    observations.append(observation)
        keys = persist_iva_compensation_history_observations_strict(
            tuple(observations),
            ports=self._filed_observation_ports,
        )
        reloaded = self.list_history(as_of_year=None)
        return IvaCompensationHistoryCaptureReport(
            output_root=str(output_root),
            year_from=year_from,
            year_to=year_to,
            captured_count=len(paths),
            observation_paths=tuple(paths),
            artefact_refs=tuple(artefacts),
            casilla_count=casilla_count,
            calculation_observation_count=len(keys),
            calculation_observation_keys=tuple(keys),
            reloaded_history_count=reloaded.row_count,
            reloaded_rows=reloaded.rows,
            failed_declaration_count=len(failures),
            failed_declarations=tuple(failures),
        )

    async def capture_wallet(
        self,
        session: AeatSession,
        *,
        settings: Settings,
        target_year: int,
        target_period: Period,
        taxpayer_nif: str | None,
        output_root: Path | None,
        progress_context: dict[str, object] | None,
    ) -> IvaWalletCaptureReport:
        """Capture, persist, and reconcile one IVA wallet observation."""
        if progress_context is not None:
            progress_context.update(
                {
                    "stage": "fetch_iva_compensation_wallet",
                    "target_year": target_year,
                    "target_period": target_period.registry_token,
                }
            )
        observation = await fetch_iva_compensation_wallet(
            session,
            target_year=target_year,
            target_period=target_period,
            taxpayer_nif=taxpayer_nif,
            settings=settings,
        )
        root = output_root or settings.cadrumo_live_state_dir / _WALLET_DIRNAME
        return persist_and_reconcile_iva_compensation_wallet(
            observation,
            output_root=root,
            objects=self._objects,
        )


def persist_and_reconcile_iva_compensation_wallet(
    observation: IvaCompensationWalletObservation,
    *,
    output_root: Path,
    objects: SecureObjectRepository | None = None,
    repository: CalculationObservationRepository | None = None,
    decision_repository: IvaWalletDecisionRepository | None = None,
    decided_at: datetime | None = None,
) -> IvaWalletCaptureReport:
    """Persist, reload, reconcile, and project one wallet observation."""
    if repository is None and objects is None:
        raise LiveApplicationError(
            translated_message="application.live.iva_wallet.errors.observation_reload_diverged",
            context={"reason": "secure_backend_required"},
        )
    resolved_repository = repository or CalculationObservationRepository(objects=objects)
    store = FiledDeclaracionObservationStore(
        output_root,
        objects=resolved_repository.secure_object_repository,
    )
    path = store.persist_iva_wallet_observation(observation)
    reloaded = store.load_iva_wallet_observation(path)
    if reloaded != observation:
        raise LiveApplicationError(
            translated_message="application.live.iva_wallet.errors.observation_reload_diverged",
            context={
                "target_year": observation.target_year,
                "target_period": observation.target_period.registry_token,
            },
        )
    snapshot = bundled_authority().snapshot(
        Modelo.M303.value,
        filing_year=reloaded.target_year,
        period=reloaded.target_period.registry_token,
    )
    from ..application.calculations.binding_prefill import extract_modelo_303_local_iva_compensation_recurrence

    recurrence, prefill = extract_modelo_303_local_iva_compensation_recurrence(
        snapshot,
        repository=resolved_repository,
        captured_at=decided_at,
    )
    reconciliation = reconcile_modelo_303_iva_compensation(
        snapshot,
        taxpayer_nif=reloaded.taxpayer_nif,
        wallet=reloaded,
        repository=resolved_repository,
        decision_repository=decision_repository,
        decided_at=decided_at,
        local_recurrence=recurrence,
        prefill_report=prefill,
    )
    decision = reconciliation.decision
    resolved_decision_repository = decision_repository or IvaWalletDecisionRepository(
        objects=resolved_repository.secure_object_repository,
    )
    loaded = resolved_decision_repository.load_decision(decision.taxpayer_nif, decision.target_period)
    if loaded != decision:
        raise LiveApplicationError(
            translated_message="application.live.iva_wallet.errors.decision_reload_diverged",
            context={"target_period": decision.target_period.registry_token},
        )
    return IvaWalletCaptureReport(
        taxpayer_ref=taxpayer_ref(reloaded.taxpayer_nif),
        target_year=reloaded.target_year,
        target_period=reloaded.target_period,
        observation_path=str(path),
        decision_key=iva_wallet_decision_key(decision.taxpayer_nif, decision.target_period),
        row_count=len(reloaded.rows),
        total_pending=str(reloaded.total_pending),
        selected_authority=decision.selected_authority,
        selected_amount=str(decision.selected_amount) if decision.selected_amount is not None else None,
        local_recurrence_amount=str(decision.local_recurrence_amount)
        if decision.local_recurrence_amount is not None
        else None,
        divergence=decision.divergence,
        blocked=decision.blocked,
        captured_at=reloaded.captured_at,
    )


def aggregate_iva_compensation_history_reports(
    reports: list[IvaCompensationHistoryCaptureReport],
    *,
    output_root: Path,
    year_from: int,
    year_to: int,
) -> IvaCompensationHistoryCaptureReport:
    """Combine per-year history reports at the shared composition boundary."""
    composition = compose_live_state(output_root=output_root)
    reloaded = composition.iva_remote_state_port.list_history(as_of_year=None)
    return IvaCompensationHistoryCaptureReport(
        output_root=str(output_root),
        year_from=year_from,
        year_to=year_to,
        captured_count=sum(report.captured_count for report in reports),
        observation_paths=tuple(path for report in reports for path in report.observation_paths),
        artefact_refs=tuple(ref for report in reports for ref in report.artefact_refs),
        casilla_count=sum(report.casilla_count for report in reports),
        calculation_observation_count=sum(report.calculation_observation_count for report in reports),
        calculation_observation_keys=tuple(key for report in reports for key in report.calculation_observation_keys),
        reloaded_history_count=reloaded.row_count,
        reloaded_rows=reloaded.rows,
        failed_declaration_count=sum(report.failed_declaration_count for report in reports),
        failed_declarations=tuple(failure for report in reports for failure in report.failed_declarations),
    )


async def pull_filed_history_with_shared_composition(
    payload: object,
    profile: object,
    repository: object,
    events: object,
    ports: FiledObservationPersistencePorts,
    iva_remote_state_port: IvaRemoteStatePort,
):
    """Invoke the filed-history service with the explicitly composed bundle."""
    from ..application.live.filed_data_capture import pull_filed_history

    return await pull_filed_history(
        iva_remote_state_port=iva_remote_state_port,
        ports=ports,
        output_root=payload.output_root,
        profile=profile,
        today=payload.today,
        limit=payload.limit,
        dry_run=payload.dry_run,
        sync_run_repository=repository,
        events=events,
    )


def taxpayer_ref(value: str | None) -> str:
    """Return a redacted taxpayer identity reference."""
    token = tax_id_identity_token(value) if value is not None else ""
    return "absent" if not token else f"sha256:{sha256_hex(token.encode('utf-8'))[:12]}"


def _history_row(state: object) -> IvaCompensationHistoryRow:
    return IvaCompensationHistoryRow(
        year=state.filing_year,
        period=state.period,
        provenance=state.provenance,
        register_status=state.status,
        presented_at=state.presented_at,
        prior_pending_amount=_decimal(state.prior_pending_amount),
        applied_amount=_decimal(state.applied_amount),
        pending_for_later_amount=_decimal(state.pending_for_later_amount),
        period_result_amount=_decimal(state.period_result_amount),
        final_result_amount=_decimal(state.final_result_amount),
        generated_amount=str(state.generated_amount),
        available_end_amount=str(state.available_end_amount),
    )


def carry_forward_lot_row(lot: object) -> IvaCompensationCarryForwardLotRow:
    return IvaCompensationCarryForwardLotRow(
        taxpayer_ref=taxpayer_ref(lot.taxpayer_nif),
        source_filing_year=lot.source_filing_year,
        source_period=lot.source_period,
        generated_amount=str(lot.generated_amount),
        applied_amount=str(lot.applied_amount),
        remaining_amount=str(lot.remaining_amount),
        age_years=lot.age_years,
        expiry_review_state=lot.expiry_review_state.value,
        source_observation_key=evidence_ref(lot.source_observation_key),
    )


def _decision_row(decision: object) -> IvaWalletAuthorityDecisionRow:
    return IvaWalletAuthorityDecisionRow(
        taxpayer_ref=taxpayer_ref(decision.taxpayer_nif),
        target_year=decision.target_year,
        target_period=decision.target_period,
        selected_authority=decision.selected_authority,
        selected_amount=_decimal(decision.selected_amount),
        wallet_amount=_decimal(decision.wallet_amount),
        local_recurrence_amount=_decimal(decision.local_recurrence_amount),
        override_amount=_decimal(decision.override_amount),
        divergence=decision.divergence,
        blocked=decision.blocked,
        stale_wallet=decision.stale_wallet,
        reason_identity=decision.reason_identity,
        operator_explanation=decision.operator_explanation,
        wallet_captured_at=decision.wallet_captured_at,
        decided_at=decision.decided_at,
        authority_sources=tuple(_authority_source_text(source) for source in decision.authority_sources),
    )


def _authority_source_text(source: object) -> str:
    parts = [str(source.source_kind)]
    if source.source_modelo is not None:
        parts.append(f"modelo={source.source_modelo}")
    if source.source_filing_year is not None:
        parts.append(f"year={source.source_filing_year}")
    if source.source_periods:
        parts.append(f"periods={','.join(period.registry_token for period in source.source_periods)}")
    if source.amount is not None:
        parts.append(f"amount={source.amount}")
    parts.append(f"ref={evidence_ref(source.source_locator)}")
    return " ".join(parts)


def _decimal(value: object) -> str | None:
    return str(value) if value is not None else None


__all__ = [
    "AppIvaRemoteStatePort",
    "LiveStateComposition",
    "aggregate_iva_compensation_history_reports",
    "carry_forward_lot_row",
    "compose_filed_observation_persistence_ports",
    "compose_live_state",
    "persist_and_reconcile_iva_compensation_wallet",
    "pull_filed_history_with_shared_composition",
    "taxpayer_ref",
]
