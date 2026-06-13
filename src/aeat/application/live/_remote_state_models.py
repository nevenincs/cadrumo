"""Typed report models for live AEAT filed-data and IVA remote-state services."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from ...core import Period
from ._errors import LiveIvaAcquisitionFailureMode


class FiledDataCaptureReport(BaseModel):
    """Read-only filed-declaration capture report."""

    model_config = ConfigDict(frozen=True)

    output_root: str
    modelo: str
    year: int
    captured_count: int
    observation_paths: tuple[str, ...]
    artefact_refs: tuple[str, ...]
    justificante_metadata_count: int = 0
    justificante_csvs: tuple[str, ...] = ()
    filing_evidence_stamped_count: int = 0
    filing_record_ids: tuple[str, ...] = ()
    filing_evidence_conflict_count: int = 0
    filing_evidence_conflict_record_ids: tuple[str, ...] = ()
    casilla_count: int
    calculation_observation_count: int
    calculation_observation_keys: tuple[str, ...]


class FiledDataCaptureFailureRow(BaseModel):
    """One failed filed-declaration capture attempt in a bulk run."""

    model_config = ConfigDict(frozen=True)

    modelo: str
    year: int
    period: Period | None = None
    expediente_id: str | None = None
    error_type: str
    message: str


class BulkFiledDataCaptureReport(BaseModel):
    """Read-only bulk filed-declaration capture report."""

    model_config = ConfigDict(frozen=True)

    output_root: str
    modelos: tuple[str, ...]
    year_from: int
    year_to: int
    captured_count: int
    failed_count: int
    observation_paths: tuple[str, ...]
    artefact_refs: tuple[str, ...]
    justificante_metadata_count: int = 0
    justificante_csvs: tuple[str, ...] = ()
    filing_evidence_stamped_count: int = 0
    filing_record_ids: tuple[str, ...] = ()
    filing_evidence_conflict_count: int = 0
    filing_evidence_conflict_record_ids: tuple[str, ...] = ()
    casilla_count: int
    calculation_observation_count: int
    calculation_observation_keys: tuple[str, ...]
    failures: tuple[FiledDataCaptureFailureRow, ...] = ()


class ExpedientesBulkCaptureFailureRow(BaseModel):
    """One failed expedientes register walk in a bulk run."""

    model_config = ConfigDict(frozen=True)

    modelo: str
    year: int
    error_type: str
    message: str


class ExpedientesBulkCaptureReport(BaseModel):
    """Read-only bulk expedientes snapshot capture report."""

    model_config = ConfigDict(frozen=True)

    bucket_id: str
    modelos: tuple[str, ...]
    year_from: int
    year_to: int
    captured_snapshot_count: int
    declaration_count: int
    snapshot_ids: tuple[str, ...]
    failures: tuple[ExpedientesBulkCaptureFailureRow, ...] = ()


class SourceFiledDataCaptureReport(BaseModel):
    """Read-only source-observation capture report for one target filing."""

    model_config = ConfigDict(frozen=True)

    output_root: str
    target_modelo: str
    target_year: int
    target_period: Period
    captured_count: int
    observation_paths: tuple[str, ...]
    artefact_refs: tuple[str, ...]
    justificante_metadata_count: int = 0
    justificante_csvs: tuple[str, ...] = ()
    filing_evidence_stamped_count: int = 0
    filing_record_ids: tuple[str, ...] = ()
    filing_evidence_conflict_count: int = 0
    filing_evidence_conflict_record_ids: tuple[str, ...] = ()
    casilla_count: int
    calculation_observation_count: int
    calculation_observation_keys: tuple[str, ...]


class IvaWalletCaptureReport(BaseModel):
    """Read-only IVA compensation wallet capture report."""

    model_config = ConfigDict(frozen=True)

    taxpayer_ref: str
    target_year: int
    target_period: Period
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
    period: Period
    status: str
    presented_at: datetime
    prior_pending_amount: str | None
    applied_amount: str | None
    pending_for_later_amount: str | None
    period_result_amount: str | None
    final_result_amount: str | None
    generated_amount: str
    available_end_amount: str


class IvaCompensationCarryForwardLotRow(BaseModel):
    """One CLI-safe IVA compensation carry-forward lot."""

    model_config = ConfigDict(frozen=True)

    taxpayer_ref: str
    source_filing_year: int
    source_period: Period
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
    target_period: Period
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


class StoredIvaWalletObservationRow(BaseModel):
    """One redacted stored wallet observation summary reloaded from secure storage."""

    model_config = ConfigDict(frozen=True)

    taxpayer_ref: str
    target_year: int
    target_period: Period
    row_count: int
    total_pending: str
    captured_at: datetime
    raw_sha256: str | None


class StoredIvaRemoteStateAcquisitionRow(BaseModel):
    """One redacted stored live IVA acquisition manifest summary."""

    model_config = ConfigDict(frozen=True)

    acquisition_ref: str
    captured_at: datetime
    auth_status: str
    auth_outcome_mode: str
    auth_failure_mode: str | None = None
    auth_failure_type: str | None = None
    auth_diagnostic_ref: str | None = None
    auth_provider_kind: str | None = None
    auth_reused_persisted_session: bool | None = None
    year_from: int
    year_to: int
    target_year: int
    target_period: Period
    filed_history_succeeded: bool
    wallet_succeeded: bool
    surfaces: tuple[str, ...]


class IvaRemoteStateStoredEvidenceReport(BaseModel):
    """Stored remote IVA evidence available without a live AEAT read."""

    model_config = ConfigDict(frozen=True)

    history: IvaCompensationHistoryReport
    wallet_observation_count: int
    wallet_observations: tuple[StoredIvaWalletObservationRow, ...]
    acquisition_manifest_count: int = 0
    acquisition_manifests: tuple[StoredIvaRemoteStateAcquisitionRow, ...] = ()


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
    failed_declaration_count: int = 0
    failed_declarations: tuple[str, ...] = ()


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
    outcome_mode: LiveIvaAcquisitionFailureMode = LiveIvaAcquisitionFailureMode.UNKNOWN
    failure_mode: LiveIvaAcquisitionFailureMode | None = None
    failure_type: str | None = None
    failure_context: dict[str, object] | None = None
    captured_count: int | None = None
    calculation_observation_count: int | None = None


class LiveIvaAuthOutcome(BaseModel):
    """Redacted authentication outcome for a live IVA acquisition."""

    model_config = ConfigDict(frozen=True)

    status: LiveIvaReadStatus
    outcome_mode: LiveIvaAcquisitionFailureMode
    failure_mode: LiveIvaAcquisitionFailureMode | None = None
    failure_type: str | None = None
    diagnostic_ref: str | None = None
    provider_kind: str | None = None
    reused_persisted_session: bool | None = None
    fresh: bool | None = None


class IvaRemoteStateAcquisitionReport(BaseModel):
    """Combined read-only IVA remote-state acquisition report."""

    model_config = ConfigDict(frozen=True)

    acquisition_manifest_id: str | None = None
    output_root: str
    year_from: int
    year_to: int
    target_year: int
    target_period: Period
    auth: LiveIvaAuthOutcome = LiveIvaAuthOutcome(
        status=LiveIvaReadStatus.FAILED,
        outcome_mode=LiveIvaAcquisitionFailureMode.UNKNOWN,
        failure_mode=LiveIvaAcquisitionFailureMode.UNKNOWN,
        failure_type="MissingAuthResult",
    )
    filed_history: IvaCompensationHistoryCaptureReport | None
    wallet: IvaWalletCaptureReport | None
    outcomes: tuple[LiveIvaReadOutcome, ...]

    @property
    def filed_history_succeeded(self) -> bool:
        """Return ``True`` when the filed-history surface outcome is ``SUCCEEDED``."""
        return any(
            outcome.surface is LiveIvaReadSurface.FILED_HISTORY and outcome.status is LiveIvaReadStatus.SUCCEEDED
            for outcome in self.outcomes
        )

    @property
    def wallet_succeeded(self) -> bool:
        """Return ``True`` when the wallet-cartera surface outcome is ``SUCCEEDED``."""
        return any(
            outcome.surface is LiveIvaReadSurface.WALLET_CARTERA and outcome.status is LiveIvaReadStatus.SUCCEEDED
            for outcome in self.outcomes
        )


class IvaRemoteStateAcquisitionSurfaceManifest(BaseModel):
    """One persisted redacted surface outcome from a live IVA acquisition."""

    model_config = ConfigDict(frozen=True)

    surface: LiveIvaReadSurface
    status: LiveIvaReadStatus
    outcome_mode: LiveIvaAcquisitionFailureMode = LiveIvaAcquisitionFailureMode.UNKNOWN
    failure_mode: LiveIvaAcquisitionFailureMode | None = None
    failure_type: str | None = None
    failure_context: dict[str, object] | None = None
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
    target_period: Period
    auth: LiveIvaAuthOutcome = LiveIvaAuthOutcome(
        status=LiveIvaReadStatus.FAILED,
        outcome_mode=LiveIvaAcquisitionFailureMode.UNKNOWN,
        failure_mode=LiveIvaAcquisitionFailureMode.UNKNOWN,
        failure_type="LegacyManifestAuthOutcome",
    )
    filed_history_succeeded: bool
    wallet_succeeded: bool
    surfaces: tuple[IvaRemoteStateAcquisitionSurfaceManifest, ...]


__all__ = [
    "BulkFiledDataCaptureReport",
    "ExpedientesBulkCaptureFailureRow",
    "ExpedientesBulkCaptureReport",
    "FiledDataCaptureFailureRow",
    "FiledDataCaptureReport",
    "IvaCompensationCarryForwardLotRow",
    "IvaCompensationHistoryCaptureReport",
    "IvaCompensationHistoryReport",
    "IvaCompensationHistoryRow",
    "IvaRemoteStateAcquisitionManifest",
    "IvaRemoteStateAcquisitionReport",
    "IvaRemoteStateAcquisitionSurfaceManifest",
    "IvaRemoteStateStoredEvidenceReport",
    "IvaWalletAuthorityDecisionRow",
    "IvaWalletCaptureReport",
    "LiveIvaAuthOutcome",
    "LiveIvaReadOutcome",
    "LiveIvaReadStatus",
    "LiveIvaReadSurface",
    "SourceFiledDataCaptureReport",
    "StoredIvaRemoteStateAcquisitionRow",
    "StoredIvaWalletObservationRow",
]
