"""Application services for explicit read-only AEAT live workflows."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, ConfigDict

from ...adapters.outbound.aeat.auth import AeatSession as _AeatSession
from ...adapters.outbound.aeat.sede import (
    PRE303_PRESENTATION_SERVICE_URL as _PRE303_PRESENTATION_SERVICE_URL,
)
from ...adapters.outbound.aeat.sede import (
    Declaracion as _Declaracion,
)
from ...adapters.outbound.aeat.sede import (
    FiledDeclaracionObservation as _FiledDeclaracionObservation,
)
from ...adapters.outbound.aeat.sede import (
    FiledDeclaracionObservationStore as _FiledDeclaracionObservationStore,
)
from ...adapters.outbound.aeat.sede import (
    IvaCompensationWalletObservation as _IvaCompensationWalletObservation,
)
from ...adapters.outbound.aeat.sede import (
    SedeParseError as _SedeParseError,
)
from ...adapters.outbound.aeat.sede import (
    capture_previous_filing_observations as _capture_previous_filing_observations,
)
from ...adapters.outbound.aeat.sede import (
    capture_relation_source_observations as _capture_relation_source_observations,
)
from ...adapters.outbound.aeat.sede import (
    fetch_iva_compensation_wallet as _fetch_iva_compensation_wallet,
)
from ...adapters.outbound.aeat.sede import (
    open_declarations_register as _open_declarations_register,
)
from ...adapters.outbound.aeat.sede import (
    registry_observation_from_filed_declaration as _registry_observation_from_filed_declaration,
)
from ...adapters.outbound.aeat.sede import (
    shared_playwright as _shared_playwright,
)
from ...adapters.persistence.storage import (
    LIVE_IVA_REMOTE_STATE_ACQUISITIONS_NAMESPACE as _LIVE_IVA_REMOTE_STATE_ACQUISITIONS_STORAGE_NAMESPACE,
)
from ...adapters.persistence.storage.envelope import SecureBoundRepository as _SecureBoundRepository
from ...adapters.persistence.storage.runtime_repository import (
    secure_object_repository_for_active_bucket as _secure_object_repository_for_active_bucket,
)
from ...adapters.persistence.storage.sql import SecureObjectRepository as _SecureObjectRepository
from ...application.auth import ensure_authenticated_aeat_session as _ensure_authenticated_aeat_session
from ...application.calculations import (
    CalculationObservationRepository as _CalculationObservationRepository,
)
from ...application.calculations import (
    IvaCompensationAuthoritySource as _IvaCompensationAuthoritySource,
)
from ...application.calculations import (
    IvaCompensationCarryForwardLot as _IvaCompensationCarryForwardLot,
)
from ...application.calculations import (
    IvaCompensationHistoryRepository as _IvaCompensationHistoryRepository,
)
from ...application.calculations import (
    IvaCompensationPeriodState as _IvaCompensationPeriodState,
)
from ...application.calculations import (
    IvaCompensationReconciliationDecision as _IvaCompensationReconciliationDecision,
)
from ...application.calculations import (
    IvaWalletDecisionRepository as _IvaWalletDecisionRepository,
)
from ...application.calculations import (
    build_iva_compensation_carry_forward_report as _build_iva_compensation_carry_forward_report,
)
from ...application.calculations import (
    iva_compensation_state_from_filed_observation as _iva_compensation_state_from_filed_observation,
)
from ...application.calculations import (
    iva_wallet_decision_key as _iva_wallet_decision_key,
)
from ...application.calculations import (
    observation_key as _observation_key,
)
from ...application.calculations import (
    reconcile_modelo_303_iva_compensation as _reconcile_modelo_303_iva_compensation,
)
from ...core.access_gate import AeatAccessGate as _AeatAccessGate
from ...core.config import Settings as _Settings
from ...core.config import load_settings as _load_settings
from ...core.resources import bundled_path as _bundled_path
from ...core.resources import resources as _resources
from ...domain.calculations.registry import (
    CasillaObservation as _CasillaObservation,
)
from ...domain.calculations.registry import (
    RegistryModeloObservation as _RegistryModeloObservation,
)
from ...domain.calculations.registry._authority import ValidatedRegistryAuthority as _ValidatedRegistryAuthority
from ._borrador_100 import (
    BORRADOR_100_SNAPSHOT_NAMESPACE,
    Borrador100Snapshot,
    Borrador100SnapshotRepository,
    Borrador100SnapshotService,
    BorradorSnapshotNotFoundError,
    borrador_100_snapshot_object_key,
    derive_borrador_100_snapshot_id,
)
from ._censo import CensoSnapshotNotFoundError
from ._errors import (
    LiveApplicationError,
    LiveApplicationInputError,
    LiveIvaAcquisitionFailureMode,
    classify_live_iva_acquisition_failure,
)
from ._snapshot_base import SnapshotLifecycleState


class FiledDataCaptureReport(BaseModel):
    """Read-only filed-declaration capture report."""

    model_config = ConfigDict(frozen=True)

    output_root: str
    modelo: str
    year: int
    captured_count: int
    observation_paths: tuple[str, ...]
    artefact_refs: tuple[str, ...]
    casilla_count: int
    calculation_observation_count: int
    calculation_observation_keys: tuple[str, ...]


class SourceFiledDataCaptureReport(BaseModel):
    """Read-only source-observation capture report for one target filing."""

    model_config = ConfigDict(frozen=True)

    output_root: str
    target_modelo: str
    target_year: int
    target_period: str
    captured_count: int
    observation_paths: tuple[str, ...]
    artefact_refs: tuple[str, ...]
    casilla_count: int
    calculation_observation_count: int
    calculation_observation_keys: tuple[str, ...]


class IvaWalletCaptureReport(BaseModel):
    """Read-only IVA compensation wallet capture report."""

    model_config = ConfigDict(frozen=True)

    taxpayer_ref: str
    target_year: int
    target_period: str
    observation_path: str
    decision_key: str
    row_count: int
    total_pending: str
    selected_authority: str
    selected_amount: str | None
    local_recurrence_amount: str | None
    divergence: str
    blocked: bool
    captured_at: datetime


class IvaCompensationHistoryRow(BaseModel):
    """One secure stored Modelo 303 IVA compensation history row."""

    model_config = ConfigDict(frozen=True)

    year: int
    period: str
    status: str
    presented_at: datetime
    prior_pending_amount: str | None
    applied_amount: str | None
    pending_for_later_amount: str | None
    period_result_amount: str | None
    final_result_amount: str | None
    generated_amount: str
    available_end_amount: str


class IvaCompensationHistoryReport(BaseModel):
    """Profile-local IVA compensation history report."""

    model_config = ConfigDict(frozen=True)

    row_count: int
    rows: tuple[IvaCompensationHistoryRow, ...]
    as_of_year: int
    carry_forward_lot_count: int
    carry_forward_lots: tuple[IvaCompensationCarryForwardLotRow, ...] = ()
    unallocated_applied_amount: str
    authority_decision_count: int
    authority_decisions: tuple[IvaWalletAuthorityDecisionRow, ...] = ()


class IvaCompensationCarryForwardLotRow(BaseModel):
    """One CLI-safe IVA compensation carry-forward lot."""

    model_config = ConfigDict(frozen=True)

    taxpayer_ref: str
    source_filing_year: int
    source_period: str
    generated_amount: str
    applied_amount: str
    remaining_amount: str
    age_years: int
    expiry_review_state: str
    source_observation_key: str


class IvaWalletAuthorityDecisionRow(BaseModel):
    """One persisted wallet/local/override authority decision for CLI display."""

    model_config = ConfigDict(frozen=True)

    taxpayer_ref: str
    target_year: int
    target_period: str
    selected_authority: str
    selected_amount: str | None
    wallet_amount: str | None
    local_recurrence_amount: str | None
    override_amount: str | None
    divergence: str
    blocked: bool
    stale_wallet: bool
    reason: str
    wallet_captured_at: datetime | None
    decided_at: datetime
    authority_sources: tuple[str, ...] = ()


class StoredIvaWalletObservationRow(BaseModel):
    """One redacted stored wallet observation summary reloaded from secure storage."""

    model_config = ConfigDict(frozen=True)

    taxpayer_ref: str
    target_year: int
    target_period: str
    row_count: int
    total_pending: str
    captured_at: datetime
    raw_sha256: str | None


class IvaRemoteStateStoredEvidenceReport(BaseModel):
    """Stored remote IVA evidence available without a live AEAT read."""

    model_config = ConfigDict(frozen=True)

    history: IvaCompensationHistoryReport
    wallet_observation_count: int
    wallet_observations: tuple[StoredIvaWalletObservationRow, ...]


class IvaCompensationHistoryCaptureReport(BaseModel):
    """Read-only multi-year Modelo 303 IVA compensation history capture report."""

    model_config = ConfigDict(frozen=True)

    output_root: str
    year_from: int
    year_to: int
    captured_count: int
    observation_paths: tuple[str, ...]
    artefact_refs: tuple[str, ...]
    casilla_count: int
    calculation_observation_count: int
    calculation_observation_keys: tuple[str, ...]
    reloaded_history_count: int
    reloaded_rows: tuple[IvaCompensationHistoryRow, ...]


class LiveIvaReadSurface(StrEnum):
    """Read-only IVA remote-state surfaces acquired from AEAT."""

    FILED_HISTORY = "filed_history"
    WALLET_CARTERA = "wallet_cartera"


class LiveIvaReadStatus(StrEnum):
    """Per-surface outcome for one live IVA read attempt."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"


class LiveIvaReadOutcome(BaseModel):
    """Redacted per-surface acquisition outcome."""

    model_config = ConfigDict(frozen=True)

    surface: LiveIvaReadSurface
    status: LiveIvaReadStatus
    failure_mode: LiveIvaAcquisitionFailureMode | None = None
    failure_type: str | None = None
    captured_count: int | None = None
    calculation_observation_count: int | None = None


class IvaRemoteStateAcquisitionReport(BaseModel):
    """Combined read-only IVA remote-state acquisition report."""

    model_config = ConfigDict(frozen=True)

    acquisition_manifest_id: str | None = None
    output_root: str
    year_from: int
    year_to: int
    target_year: int
    target_period: str
    filed_history: IvaCompensationHistoryCaptureReport | None
    wallet: IvaWalletCaptureReport | None
    outcomes: tuple[LiveIvaReadOutcome, ...]

    @property
    def filed_history_succeeded(self) -> bool:
        return any(
            outcome.surface is LiveIvaReadSurface.FILED_HISTORY and outcome.status is LiveIvaReadStatus.SUCCEEDED
            for outcome in self.outcomes
        )

    @property
    def wallet_succeeded(self) -> bool:
        return any(
            outcome.surface is LiveIvaReadSurface.WALLET_CARTERA and outcome.status is LiveIvaReadStatus.SUCCEEDED
            for outcome in self.outcomes
        )


class IvaRemoteStateAcquisitionSurfaceManifest(BaseModel):
    """One persisted redacted surface outcome from a live IVA acquisition."""

    model_config = ConfigDict(frozen=True)

    surface: LiveIvaReadSurface
    status: LiveIvaReadStatus
    failure_mode: LiveIvaAcquisitionFailureMode | None = None
    failure_type: str | None = None
    captured_count: int | None = None
    calculation_observation_count: int | None = None
    reloaded_history_count: int | None = None
    wallet_row_count: int | None = None
    decision_ref: str | None = None
    selected_authority: str | None = None
    divergence: str | None = None
    blocked: bool | None = None


class IvaRemoteStateAcquisitionManifest(BaseModel):
    """Encrypted profile-local manifest for one read-only live IVA acquisition."""

    model_config = ConfigDict(frozen=True)

    acquisition_id: str
    captured_at: datetime
    year_from: int
    year_to: int
    target_year: int
    target_period: str
    filed_history_succeeded: bool
    wallet_succeeded: bool
    surfaces: tuple[IvaRemoteStateAcquisitionSurfaceManifest, ...]


class IvaRemoteStateAcquisitionManifestRepository(
    _SecureBoundRepository[IvaRemoteStateAcquisitionManifest]
):
    """Repository for encrypted live IVA acquisition manifests."""

    namespace: ClassVar[str] = _LIVE_IVA_REMOTE_STATE_ACQUISITIONS_STORAGE_NAMESPACE.namespace
    sensitivity: ClassVar = _LIVE_IVA_REMOTE_STATE_ACQUISITIONS_STORAGE_NAMESPACE.sensitivity
    schema_version: ClassVar[int] = _LIVE_IVA_REMOTE_STATE_ACQUISITIONS_STORAGE_NAMESPACE.schema_version
    payload_type: ClassVar[type[IvaRemoteStateAcquisitionManifest]] = IvaRemoteStateAcquisitionManifest

    def __init__(self, *, objects: _SecureObjectRepository | None = None) -> None:
        super().__init__(objects=objects or _secure_object_repository_for_active_bucket())

    def extract_identifier(self, payload: IvaRemoteStateAcquisitionManifest) -> str:
        return payload.acquisition_id


class FiledDataListingRow(BaseModel):
    """One filed declaration row listed from AEAT without downloading artefacts."""

    model_config = ConfigDict(frozen=True)

    modelo: str
    year: int
    period: str
    expediente_id: str
    status: str
    presented_at: datetime
    has_submitted_file: bool
    has_declaration_copy: bool
    has_justificante: bool


class FiledDataListingReport(BaseModel):
    """Read-only filed-declaration listing report."""

    model_config = ConfigDict(frozen=True)

    modelo: str
    year_from: int
    year_to: int
    row_count: int
    rows: tuple[FiledDataListingRow, ...]


def select_declarations_for_capture(
    declarations: tuple[_Declaracion, ...],
    *,
    period: str | None = None,
    expediente_id: str | None = None,
    limit: int | None = None,
) -> tuple[_Declaracion, ...]:
    """Select filed-declaration rows for capture from one register query."""

    selected = declarations
    if period is not None:
        selected = tuple(row for row in selected if row.period.upper() == period.upper())
    if expediente_id is not None:
        selected = tuple(row for row in selected if row.expediente_id == expediente_id)
    if expediente_id is not None and not selected:
        raise LiveApplicationInputError(f"AEAT declaration register did not return expediente {expediente_id!r}")
    if limit is not None:
        selected = selected[:limit]
    return selected


def filed_data_listing_row(declaration: _Declaracion) -> FiledDataListingRow:
    """Map one AEAT declaration-register row into the application report shape."""

    return FiledDataListingRow(
        modelo=declaration.modelo,
        year=declaration.ejercicio,
        period=declaration.period,
        expediente_id=declaration.expediente_id,
        status=declaration.estado,
        presented_at=declaration.presented_at,
        has_submitted_file=bool(declaration.archive_link_text and declaration.archive_cell_index is not None),
        has_declaration_copy=bool(
            declaration.declaration_copy_link_text and declaration.declaration_copy_cell_index is not None
        ),
        has_justificante=bool(declaration.justificante_link_text and declaration.justificante_cell_index is not None),
    )


async def list_filed_data(
    *,
    modelo: str,
    year_from: int,
    year_to: int,
) -> FiledDataListingReport:
    """List filed declaration rows through the active AEAT session without downloading artefacts."""

    if year_from > year_to:
        raise LiveApplicationInputError("from-year must be less than or equal to to-year")

    session, settings = await _active_verified_session()
    rows: list[FiledDataListingRow] = []
    async with (
        _shared_playwright(session) as playwright,
        _open_declarations_register(
            session,
            settings=settings,
            playwright=playwright,
        ) as register,
    ):
        for year in range(year_to, year_from - 1, -1):
            declarations = await register.walk(
                modelo=modelo,
                ejercicio=year,
            )
            rows.extend(filed_data_listing_row(declaration) for declaration in declarations)
    return FiledDataListingReport(
        modelo=modelo,
        year_from=year_from,
        year_to=year_to,
        row_count=len(rows),
        rows=tuple(rows),
    )


async def capture_filed_data(
    *,
    modelo: str,
    year: int,
    output_root: Path,
    period: str | None = None,
    expediente_id: str | None = None,
    limit: int | None = None,
) -> FiledDataCaptureReport:
    """Capture filed-declaration artefacts through the active AEAT session."""

    session, _settings = await _active_verified_session()
    store = _FiledDeclaracionObservationStore(output_root)
    observation_paths: list[str] = []
    artefact_refs: list[str] = []
    observations_for_calculation: list[_FiledDeclaracionObservation] = []
    casilla_count = 0

    async with (
        _shared_playwright(session) as playwright,
        _open_declarations_register(
            session,
            playwright=playwright,
        ) as register,
    ):
        declarations = await register.walk(
            modelo=modelo,
            ejercicio=year,
        )
        selected = select_declarations_for_capture(
            declarations,
            period=period,
            expediente_id=expediente_id,
            limit=limit,
        )
        for declaration in selected:
            observation = await register.capture_observation(
                declaration,
                artefact_sink=store.persist_artefact,
            )
            manifest_path = store.persist_observation(observation)
            observation_paths.append(_capture_report_path(manifest_path, output_root=output_root))
            artefact_refs.extend(
                storage_ref
                for artefact in observation.artefacts
                for storage_ref in (artefact.storage_ref,)
                if storage_ref is not None
            )
            casilla_count += len(observation.casillas)
            observations_for_calculation.append(observation)

    calculation_observation_keys = _persist_latest_filed_calculation_observations(tuple(observations_for_calculation))

    return FiledDataCaptureReport(
        output_root=str(output_root),
        modelo=modelo,
        year=year,
        captured_count=len(observation_paths),
        observation_paths=tuple(observation_paths),
        artefact_refs=tuple(artefact_refs),
        casilla_count=casilla_count,
        calculation_observation_count=len(calculation_observation_keys),
        calculation_observation_keys=tuple(calculation_observation_keys),
    )


async def capture_source_filed_data(
    *,
    modelo: str,
    year: int,
    period: str,
    output_root: Path,
    registry_root: Path | None = None,
    source_root: Path | None = None,
) -> SourceFiledDataCaptureReport:
    """Capture filed observations required by a target filing's registry dependencies."""

    from ...core.resources import resources as _resources

    session, settings = await _active_verified_session()
    if registry_root is None and source_root is None:
        authority = _resources().modelos.authority
    else:
        authority = _ValidatedRegistryAuthority.load(
            registry_root or _bundled_path("registry", "aeat"),
            source_root=source_root or _bundled_path(),
        )
    snapshot = authority.snapshot(
        modelo,
        filing_year=year,
        period=period,
    )
    store = _FiledDeclaracionObservationStore(output_root)
    observation_paths: list[str] = []
    artefact_refs: list[str] = []
    observations_for_calculation: list[_FiledDeclaracionObservation] = []
    casilla_count = 0
    seen: set[tuple[str, int, str, str]] = set()

    async with _shared_playwright(session) as playwright:
        observations = (
            await _capture_previous_filing_observations(
                session,
                snapshot.revision,
                filing_year=year,
                period=period,
                settings=settings,
                playwright=playwright,
                artefact_sink=store.persist_artefact,
            )
        ) + (
            await _capture_relation_source_observations(
                session,
                snapshot.revision,
                filing_year=year,
                period=period,
                settings=settings,
                playwright=playwright,
                artefact_sink=store.persist_artefact,
            )
        )
    for observation in observations:
        key = (observation.modelo, observation.ejercicio, observation.period, observation.expediente_id)
        if key in seen:
            continue
        seen.add(key)
        manifest_path = store.persist_observation(observation)
        observation_paths.append(_capture_report_path(manifest_path, output_root=output_root))
        artefact_refs.extend(
            storage_ref
            for artefact in observation.artefacts
            for storage_ref in (artefact.storage_ref,)
            if storage_ref is not None
        )
        casilla_count += len(observation.casillas)
        observations_for_calculation.append(observation)

    calculation_observation_keys = _persist_latest_filed_calculation_observations(tuple(observations_for_calculation))

    return SourceFiledDataCaptureReport(
        output_root=str(output_root),
        target_modelo=modelo,
        target_year=year,
        target_period=period,
        captured_count=len(observation_paths),
        observation_paths=tuple(observation_paths),
        artefact_refs=tuple(artefact_refs),
        casilla_count=casilla_count,
        calculation_observation_count=len(calculation_observation_keys),
        calculation_observation_keys=tuple(calculation_observation_keys),
    )


def _capture_report_path(path: Path, *, output_root: Path) -> str:
    try:
        return path.relative_to(output_root).as_posix()
    except ValueError:
        return str(path)


def persist_filed_calculation_observation(
    observation: _FiledDeclaracionObservation,
    *,
    repository: _CalculationObservationRepository | None = None,
) -> str:
    """Promote one AEAT filed-declaration observation into calculation history."""

    registry_observation = _registry_observation_from_filed_declaration(observation)
    registry_observation = _with_derived_303_compensation_available(registry_observation)
    repo = repository if repository is not None else _CalculationObservationRepository()
    repo.save_observation(
        registry_observation,
        source_kind="aeat_sede_justificante",
        captured_at=observation.presented_at,
    )
    if observation.modelo == "303":
        _IvaCompensationHistoryRepository().save_period(
            _iva_compensation_state_from_filed_observation(observation)
        )
    return _observation_key(registry_observation.modelo, registry_observation.filing_year, registry_observation.period)


def list_iva_compensation_history(
    *,
    repository: _IvaCompensationHistoryRepository | None = None,
    decision_repository: _IvaWalletDecisionRepository | None = None,
    as_of_year: int | None = None,
) -> IvaCompensationHistoryReport:
    """List profile-local IVA compensation history derived from filed Modelo 303 observations."""

    repo = repository if repository is not None else _IvaCompensationHistoryRepository()
    decision_repo = decision_repository if decision_repository is not None else _IvaWalletDecisionRepository()
    states = repo.list_periods()
    rows = tuple(_history_row(state) for state in states)
    resolved_as_of_year = as_of_year if as_of_year is not None else datetime.now(UTC).year
    carry_forward = _build_iva_compensation_carry_forward_report(states, as_of_year=resolved_as_of_year)
    authority_decisions = tuple(_authority_decision_row(decision) for decision in decision_repo.list_decisions())
    return IvaCompensationHistoryReport(
        row_count=len(rows),
        rows=rows,
        as_of_year=carry_forward.as_of_year,
        carry_forward_lot_count=len(carry_forward.lots),
        carry_forward_lots=tuple(_carry_forward_lot_row(lot) for lot in carry_forward.lots),
        unallocated_applied_amount=str(carry_forward.unallocated_applied_amount),
        authority_decision_count=len(authority_decisions),
        authority_decisions=authority_decisions,
    )


def load_iva_remote_state(
    *,
    as_of_year: int | None = None,
    wallet_store: _FiledDeclaracionObservationStore | None = None,
    repository: _IvaCompensationHistoryRepository | None = None,
    decision_repository: _IvaWalletDecisionRepository | None = None,
) -> IvaRemoteStateStoredEvidenceReport:
    """Reload stored remote IVA evidence from the active profile without contacting AEAT."""

    history = list_iva_compensation_history(
        repository=repository,
        decision_repository=decision_repository,
        as_of_year=as_of_year,
    )
    store = wallet_store if wallet_store is not None else _FiledDeclaracionObservationStore(Path("."))
    wallet_rows = tuple(
        _stored_wallet_observation_row(observation) for observation in store.list_iva_wallet_observations()
    )
    return IvaRemoteStateStoredEvidenceReport(
        history=history,
        wallet_observation_count=len(wallet_rows),
        wallet_observations=wallet_rows,
    )


async def capture_iva_compensation_history(
    *,
    year_from: int,
    year_to: int,
    output_root: Path,
) -> IvaCompensationHistoryCaptureReport:
    """Capture filed Modelo 303s across years and verify secure history reload."""

    if year_from > year_to:
        raise LiveApplicationInputError("from-year must be less than or equal to to-year")

    session, settings = await _active_verified_session()
    return await _capture_iva_compensation_history_with_session(
        session,
        settings=settings,
        year_from=year_from,
        year_to=year_to,
        output_root=output_root,
    )


async def _capture_iva_compensation_history_with_session(
    session: _AeatSession,
    *,
    settings: _Settings,
    year_from: int,
    year_to: int,
    output_root: Path,
) -> IvaCompensationHistoryCaptureReport:
    """Capture filed Modelo 303s using an already-acquired AEAT session."""

    store = _FiledDeclaracionObservationStore(output_root)
    observation_paths: list[str] = []
    artefact_refs: list[str] = []
    observations_for_calculation: list[_FiledDeclaracionObservation] = []
    casilla_count = 0

    async with (
        _shared_playwright(session) as playwright,
        _open_declarations_register(
            session,
            settings=settings,
            playwright=playwright,
        ) as register,
    ):
        for year in range(year_to, year_from - 1, -1):
            declarations = await register.walk(modelo="303", ejercicio=year)
            for declaration in _latest_declarations_by_period(declarations):
                observation = await register.capture_observation(
                    declaration,
                    artefact_sink=store.persist_artefact,
                )
                manifest_path = store.persist_observation(observation)
                observation_paths.append(_capture_report_path(manifest_path, output_root=output_root))
                artefact_refs.extend(
                    storage_ref
                    for artefact in observation.artefacts
                    for storage_ref in (artefact.storage_ref,)
                    if storage_ref is not None
                )
                casilla_count += len(observation.casillas)
                observations_for_calculation.append(observation)

    calculation_observation_keys = _persist_iva_compensation_history_observations_strict(
        tuple(observations_for_calculation)
    )
    reloaded = list_iva_compensation_history()

    return IvaCompensationHistoryCaptureReport(
        output_root=str(output_root),
        year_from=year_from,
        year_to=year_to,
        captured_count=len(observation_paths),
        observation_paths=tuple(observation_paths),
        artefact_refs=tuple(artefact_refs),
        casilla_count=casilla_count,
        calculation_observation_count=len(calculation_observation_keys),
        calculation_observation_keys=tuple(calculation_observation_keys),
        reloaded_history_count=reloaded.row_count,
        reloaded_rows=reloaded.rows,
    )


def _history_row(state: _IvaCompensationPeriodState) -> IvaCompensationHistoryRow:
    return IvaCompensationHistoryRow(
        year=state.filing_year,
        period=state.period,
        status=state.status,
        presented_at=state.presented_at,
        prior_pending_amount=_decimal_text(state.prior_pending_amount),
        applied_amount=_decimal_text(state.applied_amount),
        pending_for_later_amount=_decimal_text(state.pending_for_later_amount),
        period_result_amount=_decimal_text(state.period_result_amount),
        final_result_amount=_decimal_text(state.final_result_amount),
        generated_amount=str(state.generated_amount),
        available_end_amount=str(state.available_end_amount),
    )


def _carry_forward_lot_row(lot: _IvaCompensationCarryForwardLot) -> IvaCompensationCarryForwardLotRow:
    return IvaCompensationCarryForwardLotRow(
        taxpayer_ref=_taxpayer_ref(lot.taxpayer_nif),
        source_filing_year=lot.source_filing_year,
        source_period=lot.source_period,
        generated_amount=str(lot.generated_amount),
        applied_amount=str(lot.applied_amount),
        remaining_amount=str(lot.remaining_amount),
        age_years=lot.age_years,
        expiry_review_state=lot.expiry_review_state.value,
        source_observation_key=_evidence_ref(lot.source_observation_key),
    )


def _authority_decision_row(decision: _IvaCompensationReconciliationDecision) -> IvaWalletAuthorityDecisionRow:
    return IvaWalletAuthorityDecisionRow(
        taxpayer_ref=_taxpayer_ref(decision.taxpayer_nif),
        target_year=decision.target_year,
        target_period=decision.target_period,
        selected_authority=decision.selected_authority,
        selected_amount=_decimal_text(decision.selected_amount),
        wallet_amount=_decimal_text(decision.wallet_amount),
        local_recurrence_amount=_decimal_text(decision.local_recurrence_amount),
        override_amount=_decimal_text(decision.override_amount),
        divergence=decision.divergence,
        blocked=decision.blocked,
        stale_wallet=decision.stale_wallet,
        reason=decision.reason,
        wallet_captured_at=decision.wallet_captured_at,
        decided_at=decision.decided_at,
        authority_sources=tuple(_authority_source_text(source) for source in decision.authority_sources),
    )


def _stored_wallet_observation_row(observation: _IvaCompensationWalletObservation) -> StoredIvaWalletObservationRow:
    return StoredIvaWalletObservationRow(
        taxpayer_ref=_taxpayer_ref(observation.taxpayer_nif),
        target_year=observation.target_year,
        target_period=observation.target_period,
        row_count=len(observation.rows),
        total_pending=str(observation.total_pending),
        captured_at=observation.captured_at,
        raw_sha256=observation.raw_sha256,
    )


def _authority_source_text(source: _IvaCompensationAuthoritySource) -> str:
    parts = [str(source.source_kind)]
    if source.source_modelo is not None:
        parts.append(f"modelo={source.source_modelo}")
    if source.source_filing_year is not None:
        parts.append(f"year={source.source_filing_year}")
    if source.source_periods:
        parts.append(f"periods={','.join(source.source_periods)}")
    if source.amount is not None:
        parts.append(f"amount={source.amount}")
    parts.append(f"ref={_evidence_ref(source.source_locator)}")
    return " ".join(parts)


def _decimal_text(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None


def _taxpayer_ref(taxpayer_nif: str) -> str:
    digest = hashlib.sha256(taxpayer_nif.strip().upper().encode("utf-8")).hexdigest()
    return f"sha256:{digest[:12]}"


def _evidence_ref(value: str) -> str:
    digest = hashlib.sha256(value.strip().encode("utf-8")).hexdigest()
    return f"sha256:{digest[:12]}"


def _persist_latest_filed_calculation_observations(
    observations: tuple[_FiledDeclaracionObservation, ...],
) -> tuple[str, ...]:
    """Persist only the latest captured observation per modelo/year/period."""

    latest: dict[tuple[str, int, str], _FiledDeclaracionObservation] = {}
    for observation in observations:
        key = (observation.modelo, observation.ejercicio, observation.period)
        current = latest.get(key)
        if current is None or (observation.presented_at, observation.expediente_id) > (
            current.presented_at,
            current.expediente_id,
        ):
            latest[key] = observation
    return tuple(
        key
        for _key, observation in sorted(latest.items())
        for key in _persist_filed_calculation_observation_if_extractable(observation)
    )


def _persist_iva_compensation_history_observations_strict(
    observations: tuple[_FiledDeclaracionObservation, ...],
) -> tuple[str, ...]:
    """Persist latest Modelo 303 observations and verify each history row reloads."""

    latest: dict[tuple[int, str], _FiledDeclaracionObservation] = {}
    for observation in observations:
        if observation.modelo != "303":
            raise LiveApplicationInputError("IVA compensation history capture only accepts Modelo 303 observations")
        key = (observation.ejercicio, observation.period)
        current = latest.get(key)
        if current is None or (observation.presented_at, observation.expediente_id) > (
            current.presented_at,
            current.expediente_id,
        ):
            latest[key] = observation

    keys: list[str] = []
    history_repo = _IvaCompensationHistoryRepository()
    for (_year, _period), observation in sorted(latest.items()):
        try:
            key = persist_filed_calculation_observation(observation)
        except _SedeParseError as exc:
            raise LiveApplicationError(
                f"filed Modelo 303 {observation.ejercicio}/{observation.period} "
                "could not be promoted into IVA compensation history"
            ) from exc
        if history_repo.load_period(observation.ejercicio, observation.period) is None:
            raise LiveApplicationError(
                f"secure IVA compensation history did not reload after persisting "
                f"Modelo 303 {observation.ejercicio}/{observation.period}"
            )
        keys.append(key)
    return tuple(keys)


def _latest_declarations_by_period(declarations: tuple[_Declaracion, ...]) -> tuple[_Declaracion, ...]:
    """Return one latest accepted declaration per period from register rows."""

    latest: dict[str, _Declaracion] = {}
    for declaration in declarations:
        current = latest.get(declaration.period)
        if current is None:
            latest[declaration.period] = declaration
            continue
        current_rank = (current.estado.upper() == "ALTA", current.presented_at, current.expediente_id)
        candidate_rank = (declaration.estado.upper() == "ALTA", declaration.presented_at, declaration.expediente_id)
        if candidate_rank > current_rank:
            latest[declaration.period] = declaration
    return tuple(latest[key] for key in sorted(latest, key=_history_period_sort_key))


def _history_period_sort_key(period: str) -> tuple[int, str]:
    upper = period.upper()
    if upper.endswith("T") and upper[:-1].isdigit():
        return (int(upper[:-1]), upper)
    if upper.isdigit():
        return (int(upper), upper)
    return (100, upper)


def _persist_filed_calculation_observation_if_extractable(
    observation: _FiledDeclaracionObservation,
) -> tuple[str, ...]:
    try:
        return (persist_filed_calculation_observation(observation),)
    except _SedeParseError:
        return ()


def _with_derived_303_compensation_available(
    observation: _RegistryModeloObservation,
) -> _RegistryModeloObservation:
    """Add the internal Modelo 303 carry-forward value from official filed casillas."""

    if observation.modelo != "303":
        return observation
    target_id = "iva.compensacion-disponible-fin-periodo"
    if target_id in observation.casilla_values:
        return observation
    posterior = _casilla_decimal(
        observation.casilla_values,
        "87",
        "iva.compensacion-pendiente-periodos-posteriores",
    )
    resultado = _casilla_decimal(observation.casilla_values, "69", "iva.resultado")
    if posterior is None or resultado is None:
        return observation

    generated = max(Decimal("0"), -resultado)
    available = posterior + generated
    snapshot = _resources().modelos.authority.snapshot(
        "303",
        filing_year=observation.filing_year,
        period=observation.period,
    )
    casilla = next(item for item in snapshot.revision.casillas if item.id == target_id)
    formula = next(item for item in snapshot.revision.formulas if item.target == target_id)
    derived = _CasillaObservation(
        casilla_id=target_id,
        value=available,
        formula_id=formula.id,
        operand_refs=("87", "69"),
        operand_values=(posterior, resultado),
        legal_refs=tuple(casilla.legal_refs),
        source_refs=tuple(casilla.source_refs),
    )
    return observation.model_copy(update={"observations": (*observation.observations, derived)})


def _casilla_decimal(values: dict[str, Decimal], *casilla_ids: str) -> Decimal | None:
    for casilla_id in casilla_ids:
        value = values.get(casilla_id)
        if value is not None:
            return value
    return None


def persist_and_reconcile_iva_compensation_wallet(
    observation: _IvaCompensationWalletObservation,
    *,
    output_root: Path,
    repository: _CalculationObservationRepository | None = None,
    decided_at: datetime | None = None,
) -> IvaWalletCaptureReport:
    """Persist, reload, reconcile, and report one AEAT IVA wallet observation.

    The reload is intentional: downstream reconciliation must use evidence that
    actually survived the encrypted storage boundary, not only the in-memory
    result returned by the browser driver.
    """

    store = _FiledDeclaracionObservationStore(output_root)
    path = store.persist_iva_wallet_observation(observation)
    reloaded = store.load_iva_wallet_observation(path)
    if reloaded != observation:
        raise LiveApplicationError("persisted IVA wallet observation did not reload with identical evidence")
    snapshot = _resources().modelos.authority.snapshot(
        "303",
        filing_year=reloaded.target_year,
        period=reloaded.target_period,
    )
    reconciliation = _reconcile_modelo_303_iva_compensation(
        snapshot,
        taxpayer_nif=reloaded.taxpayer_nif,
        wallet=reloaded,
        repository=repository,
        decided_at=decided_at,
    )
    decision = reconciliation.decision
    loaded_decision = _IvaWalletDecisionRepository().load_decision(
        decision.taxpayer_nif,
        decision.target_year,
        decision.target_period,
    )
    if loaded_decision != decision:
        raise LiveApplicationError(
            "persisted IVA wallet reconciliation decision did not reload with identical evidence"
        )
    return IvaWalletCaptureReport(
        taxpayer_ref=_taxpayer_ref(reloaded.taxpayer_nif),
        target_year=reloaded.target_year,
        target_period=reloaded.target_period,
        observation_path=str(path),
        decision_key=_iva_wallet_decision_key(decision.taxpayer_nif, decision.target_year, decision.target_period),
        row_count=len(reloaded.rows),
        total_pending=str(reloaded.total_pending),
        selected_authority=decision.selected_authority,
        selected_amount=str(decision.selected_amount) if decision.selected_amount is not None else None,
        local_recurrence_amount=(
            str(decision.local_recurrence_amount) if decision.local_recurrence_amount is not None else None
        ),
        divergence=decision.divergence,
        blocked=decision.blocked,
        captured_at=reloaded.captured_at,
    )


async def capture_expedientes(*, bucket_id: str, modelo: str, year: int):
    """Live-walk the AEAT declaration register and persist a bucket-scoped snapshot.

    Uses ``walk_declarations_register`` (the same register adapter the
    filed-data list/capture verbs drive), wraps the typed declarations
    in an :class:`ExpedientesCapture`, and persists through
    :class:`ExpedientesService` against the active bucket.
    """
    from datetime import UTC, datetime

    from ._expedientes import ExpedientesCapture, ExpedientesService

    session, settings = await _active_verified_session()
    async with (
        _shared_playwright(session) as playwright,
        _open_declarations_register(session, settings=settings, playwright=playwright) as register,
    ):
        declarations = await register.walk(modelo=modelo, ejercicio=year)
    capture = ExpedientesCapture(
        declarations=tuple(declarations),
        captured_at=datetime.now(tz=UTC),
        source_url=f"declarations:modelo={modelo}:ejercicio={year}",
    )
    persisted = ExpedientesService(settings=settings).capture(bucket_id=bucket_id, capture=capture)
    return persisted


async def capture_notifications(*, bucket_id: str):
    """Live-fetch DEHú notifications and persist a bucket-scoped snapshot.

    The flow is:

    1. ``_AeatAccessGate.require_live_read()`` — refuses unless
       ``AEAT_LIVE_TESTS_ENABLED=1`` is set in the operator's shell.
    2. ``_ensure_authenticated_aeat_session(operation="live-notifications-read")``
       — acquires or refreshes the authenticated session
       (e.g. triggers a Cl@ve Móvil push).
    3. ``fetch_notifications_query`` — drives Playwright against the
       authenticated DEHú surface and parses the HTML response.
    4. :class:`NotificationsService.capture` — persists the typed
       snapshot in the active bucket under the
       ``aeat.application.live.notifications`` namespace.
    5. Bucket event ``live.notifications.snapshot_captured`` is
       emitted by the caller through the standard bucket-event
       repository so this function stays unit-testable against
       a stubbed snapshot.

    Returns:
        A tuple of (snapshot_id, fetched_row_count, persisted_at).
    """
    from ...adapters.outbound.aeat.sede._notifications import fetch_notifications_query
    from ._notifications import NotificationsService

    session, settings = await _active_verified_session()
    snapshot = await fetch_notifications_query(session, settings=settings)
    persisted = NotificationsService(settings=settings).capture(bucket_id=bucket_id, snapshot=snapshot)
    return persisted


async def capture_iva_compensation_wallet(
    *,
    target_year: int,
    target_period: str,
    taxpayer_nif: str | None = None,
    output_root: Path | None = None,
) -> IvaWalletCaptureReport:
    """Live-fetch AEAT's IVA compensation wallet and persist the observation.

    This is the operator-approved live path. It requires
    `AEAT_LIVE_TESTS_ENABLED=1` and will acquire or reuse the configured
    AEAT session, including Cl@ve Móvil approval when the auth provider
    requires it.
    """

    session, settings = await _active_verified_session(
        operation="live-iva-wallet-read",
        target_url=_PRE303_PRESENTATION_SERVICE_URL,
    )
    return await _capture_iva_compensation_wallet_with_session(
        session,
        settings=settings,
        target_year=target_year,
        target_period=target_period,
        taxpayer_nif=taxpayer_nif,
        output_root=output_root,
    )


async def _capture_iva_compensation_wallet_with_session(
    session: _AeatSession,
    *,
    settings: _Settings,
    target_year: int,
    target_period: str,
    taxpayer_nif: str | None = None,
    output_root: Path | None = None,
) -> IvaWalletCaptureReport:
    """Capture and persist the wallet with an already-acquired AEAT session."""

    observation: _IvaCompensationWalletObservation = await _fetch_iva_compensation_wallet(
        session,
        target_year=target_year,
        target_period=target_period,
        taxpayer_nif=taxpayer_nif,
        settings=settings,
    )
    store_root = output_root if output_root is not None else settings.aeat_audit_dir / "live" / "iva-wallet"
    return persist_and_reconcile_iva_compensation_wallet(observation, output_root=store_root)


async def capture_iva_remote_state(
    *,
    year_from: int,
    year_to: int,
    target_year: int,
    target_period: str,
    taxpayer_nif: str | None = None,
    output_root: Path | None = None,
) -> IvaRemoteStateAcquisitionReport:
    """Acquire filed-history and wallet/cartera IVA state as one typed read-only operation."""

    if year_from > year_to:
        raise LiveApplicationInputError("from-year must be less than or equal to to-year")

    session, settings = await _active_verified_session(
        operation="live-iva-remote-state-read",
        target_url=_PRE303_PRESENTATION_SERVICE_URL,
    )
    store_root = output_root if output_root is not None else settings.aeat_audit_dir / "live" / "iva-remote-state"
    filed_history: IvaCompensationHistoryCaptureReport | None = None
    wallet: IvaWalletCaptureReport | None = None
    filed_error: BaseException | None = None
    wallet_error: BaseException | None = None

    try:
        filed_history = await _capture_iva_compensation_history_with_session(
            session,
            settings=settings,
            year_from=year_from,
            year_to=year_to,
            output_root=store_root / "filed-history",
        )
    except Exception as exc:
        filed_error = exc

    try:
        wallet = await _capture_iva_compensation_wallet_with_session(
            session,
            settings=settings,
            target_year=target_year,
            target_period=target_period,
            taxpayer_nif=taxpayer_nif,
            output_root=store_root / "wallet",
        )
    except Exception as exc:
        wallet_error = exc

    report = build_iva_remote_state_acquisition_report(
        output_root=store_root,
        year_from=year_from,
        year_to=year_to,
        target_year=target_year,
        target_period=target_period,
        filed_history=filed_history,
        wallet=wallet,
        filed_history_error=filed_error,
        wallet_error=wallet_error,
    )
    manifest = persist_iva_remote_state_acquisition_report(report)
    return report.model_copy(update={"acquisition_manifest_id": manifest.acquisition_id})


def build_iva_remote_state_acquisition_report(
    *,
    output_root: Path,
    year_from: int,
    year_to: int,
    target_year: int,
    target_period: str,
    acquisition_manifest_id: str | None = None,
    filed_history: IvaCompensationHistoryCaptureReport | None = None,
    wallet: IvaWalletCaptureReport | None = None,
    filed_history_error: BaseException | None = None,
    wallet_error: BaseException | None = None,
) -> IvaRemoteStateAcquisitionReport:
    """Build the redacted combined acquisition report from surface results."""

    outcomes = (
        _surface_outcome(
            LiveIvaReadSurface.FILED_HISTORY,
            report=filed_history,
            error=filed_history_error,
        ),
        _surface_outcome(
            LiveIvaReadSurface.WALLET_CARTERA,
            report=wallet,
            error=wallet_error,
        ),
    )
    return IvaRemoteStateAcquisitionReport(
        acquisition_manifest_id=acquisition_manifest_id,
        output_root=str(output_root),
        year_from=year_from,
        year_to=year_to,
        target_year=target_year,
        target_period=target_period,
        filed_history=filed_history,
        wallet=wallet,
        outcomes=outcomes,
    )


def persist_iva_remote_state_acquisition_report(
    report: IvaRemoteStateAcquisitionReport,
    *,
    captured_at: datetime | None = None,
    repository: IvaRemoteStateAcquisitionManifestRepository | None = None,
) -> IvaRemoteStateAcquisitionManifest:
    """Persist a redacted encrypted manifest for a live IVA acquisition report."""

    resolved_captured_at = captured_at if captured_at is not None else datetime.now(UTC)
    manifest = _iva_remote_state_acquisition_manifest(report, captured_at=resolved_captured_at)
    repo = repository if repository is not None else IvaRemoteStateAcquisitionManifestRepository()
    repo.save(manifest)
    return manifest


def load_iva_remote_state_acquisition_manifest(
    acquisition_id: str,
    *,
    repository: IvaRemoteStateAcquisitionManifestRepository | None = None,
) -> IvaRemoteStateAcquisitionManifest | None:
    """Load one encrypted live IVA acquisition manifest by id."""

    repo = repository if repository is not None else IvaRemoteStateAcquisitionManifestRepository()
    return repo.load(acquisition_id)


def list_iva_remote_state_acquisition_manifests(
    *,
    repository: IvaRemoteStateAcquisitionManifestRepository | None = None,
) -> tuple[IvaRemoteStateAcquisitionManifest, ...]:
    """List encrypted live IVA acquisition manifests for the active profile."""

    repo = repository if repository is not None else IvaRemoteStateAcquisitionManifestRepository()
    return tuple(sorted(repo.iter_records(), key=lambda item: item.captured_at, reverse=True))


def _iva_remote_state_acquisition_manifest(
    report: IvaRemoteStateAcquisitionReport,
    *,
    captured_at: datetime,
) -> IvaRemoteStateAcquisitionManifest:
    surfaces = tuple(_iva_remote_state_surface_manifest(report, outcome) for outcome in report.outcomes)
    manifest_seed = "|".join(
        (
            str(report.year_from),
            str(report.year_to),
            str(report.target_year),
            report.target_period,
            captured_at.isoformat(),
            *(surface.model_dump_json() for surface in surfaces),
        )
    )
    digest = hashlib.sha256(manifest_seed.encode("utf-8")).hexdigest()
    timestamp = captured_at.astimezone(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    acquisition_id = f"live-iva-acquisition:{report.target_year}:{report.target_period}:{timestamp}:{digest}"
    return IvaRemoteStateAcquisitionManifest(
        acquisition_id=acquisition_id,
        captured_at=captured_at,
        year_from=report.year_from,
        year_to=report.year_to,
        target_year=report.target_year,
        target_period=report.target_period,
        filed_history_succeeded=report.filed_history_succeeded,
        wallet_succeeded=report.wallet_succeeded,
        surfaces=surfaces,
    )


def _iva_remote_state_surface_manifest(
    report: IvaRemoteStateAcquisitionReport,
    outcome: LiveIvaReadOutcome,
) -> IvaRemoteStateAcquisitionSurfaceManifest:
    if outcome.surface is LiveIvaReadSurface.FILED_HISTORY:
        filed = report.filed_history
        return IvaRemoteStateAcquisitionSurfaceManifest(
            surface=outcome.surface,
            status=outcome.status,
            failure_mode=outcome.failure_mode,
            failure_type=outcome.failure_type,
            captured_count=outcome.captured_count,
            calculation_observation_count=outcome.calculation_observation_count,
            reloaded_history_count=filed.reloaded_history_count if filed is not None else None,
        )
    wallet = report.wallet
    return IvaRemoteStateAcquisitionSurfaceManifest(
        surface=outcome.surface,
        status=outcome.status,
        failure_mode=outcome.failure_mode,
        failure_type=outcome.failure_type,
        captured_count=outcome.captured_count,
        calculation_observation_count=outcome.calculation_observation_count,
        wallet_row_count=wallet.row_count if wallet is not None else None,
        decision_ref=_evidence_ref(wallet.decision_key) if wallet is not None else None,
        selected_authority=wallet.selected_authority if wallet is not None else None,
        divergence=wallet.divergence if wallet is not None else None,
        blocked=wallet.blocked if wallet is not None else None,
    )


def _surface_outcome(
    surface: LiveIvaReadSurface,
    *,
    report: IvaCompensationHistoryCaptureReport | IvaWalletCaptureReport | None,
    error: BaseException | None,
) -> LiveIvaReadOutcome:
    if error is not None:
        return LiveIvaReadOutcome(
            surface=surface,
            status=LiveIvaReadStatus.FAILED,
            failure_mode=classify_live_iva_acquisition_failure(error),
            failure_type=error.__class__.__name__,
        )
    if report is None:
        return LiveIvaReadOutcome(
            surface=surface,
            status=LiveIvaReadStatus.FAILED,
            failure_mode=LiveIvaAcquisitionFailureMode.UNKNOWN,
            failure_type="MissingSurfaceReport",
        )
    return LiveIvaReadOutcome(
        surface=surface,
        status=LiveIvaReadStatus.SUCCEEDED,
        captured_count=getattr(report, "captured_count", None),
        calculation_observation_count=getattr(report, "calculation_observation_count", None),
    )


async def _active_verified_session(
    *,
    operation: str = "live-filed-read",
    target_url: str | None = None,
) -> tuple[_AeatSession, _Settings]:
    settings = _load_settings()
    _AeatAccessGate(settings).require_live_read()
    result = await _ensure_authenticated_aeat_session(
        settings,
        operation=operation,
        target_url=target_url,
    )
    return result.session, settings


__all__ = [
    "BORRADOR_100_SNAPSHOT_NAMESPACE",
    "Borrador100Snapshot",
    "Borrador100SnapshotRepository",
    "Borrador100SnapshotService",
    "BorradorSnapshotNotFoundError",
    "CensoSnapshotNotFoundError",
    "FiledDataCaptureReport",
    "FiledDataListingReport",
    "FiledDataListingRow",
    "IvaCompensationCarryForwardLotRow",
    "IvaCompensationHistoryCaptureReport",
    "IvaCompensationHistoryReport",
    "IvaCompensationHistoryRow",
    "IvaRemoteStateAcquisitionManifest",
    "IvaRemoteStateAcquisitionManifestRepository",
    "IvaRemoteStateAcquisitionReport",
    "IvaRemoteStateAcquisitionSurfaceManifest",
    "IvaRemoteStateStoredEvidenceReport",
    "IvaWalletAuthorityDecisionRow",
    "IvaWalletCaptureReport",
    "LiveApplicationError",
    "LiveApplicationInputError",
    "LiveIvaAcquisitionFailureMode",
    "LiveIvaReadOutcome",
    "LiveIvaReadStatus",
    "LiveIvaReadSurface",
    "SnapshotLifecycleState",
    "SourceFiledDataCaptureReport",
    "StoredIvaWalletObservationRow",
    "borrador_100_snapshot_object_key",
    "build_iva_remote_state_acquisition_report",
    "capture_filed_data",
    "capture_iva_compensation_history",
    "capture_iva_compensation_wallet",
    "capture_iva_remote_state",
    "capture_notifications",
    "capture_source_filed_data",
    "classify_live_iva_acquisition_failure",
    "derive_borrador_100_snapshot_id",
    "filed_data_listing_row",
    "list_filed_data",
    "list_iva_compensation_history",
    "list_iva_remote_state_acquisition_manifests",
    "load_iva_remote_state",
    "load_iva_remote_state_acquisition_manifest",
    "persist_and_reconcile_iva_compensation_wallet",
    "persist_filed_calculation_observation",
    "persist_iva_remote_state_acquisition_report",
    "select_declarations_for_capture",
]
