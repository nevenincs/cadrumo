"""Typed report models for live AEAT filed-data and IVA remote-state services.

These frozen records are renderer-facing summaries, not raw evidence stores.
They carry typed :class:`~cadrumo.core.Period` values, secure-storage references,
redacted diagnostic fields, and counts/ids needed by CLI and workflow surfaces
after live capture has persisted the underlying observations.

See Also:
    :class:`cadrumo.application.live.IvaRemoteStateAcquisitionReport`
        Combined read-only IVA remote-state acquisition result.
    :class:`cadrumo.application.live.IvaRemoteStateStoredEvidenceReport`
        Stored-evidence view that can be loaded without live AEAT contact.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from ...core import IvaCompensationStateProvenance, Period
from ...core.identity import AeatExpedienteId, BucketId
from ...core.json_contract import Notice
from ...domain.iva_compensation import IvaCompensationDecisionReason
from ..storage.sync_runs import SyncRunRecordReference
from .errors import LiveIvaAcquisitionFailureMode


class FiledCaptureEvidenceTally(BaseModel):
    """What one filed-declaration capture produced, counted and referenced.

    Every filed-declaration capture report — single, bulk, and source-scoped —
    reports the same tally: how many observations were captured, where their
    encrypted stores and artefacts live, how much justificante and
    filing-evidence metadata was enrolled (including conflicts), and how many
    casillas and calculation observations came back.

    Declared once so the three reports cannot drift apart. A counter added to
    one report but forgotten on another would leave that capture path silently
    under-reporting its own evidence, which is precisely the divergence a
    single declaration prevents.
    """

    model_config = ConfigDict(frozen=True)

    captured_count: int
    #: Units REACHED, counted in every mode. ``captured_count`` is the
    #: persisted-path tally and a preview leaves it at zero, so only this
    #: one can answer whether a limited sweep was truncated.
    reached_count: int = 0
    observation_paths: tuple[str, ...]
    artefact_refs: tuple[str, ...]
    justificante_metadata_count: int = 0
    justificante_csvs: tuple[str, ...] = ()
    filing_evidence_stamped_count: int = 0
    filing_record_ids: tuple[str, ...] = ()
    filing_evidence_conflict_count: int = 0
    filing_evidence_conflict_record_ids: tuple[str, ...] = ()
    #: Per-observation capture advisories, each retaining the concrete cause.
    #:
    #: These are internal capture-report transport, not a command result
    #: payload: CLI entrypoints forward them on the shared envelope ``notices``
    #: channel. Keeping the lane on the shared tally means single, bulk, and
    #: source capture cannot silently diverge.
    evidence_notices: tuple[Notice, ...] = ()
    casilla_count: int
    calculation_observation_count: int
    calculation_observation_keys: tuple[str, ...]


class FiledDataCaptureReport(FiledCaptureEvidenceTally):
    """Read-only filed-declaration capture report."""

    output_root: str
    modelo: str
    year: int


class FiledDataCaptureFailureRow(BaseModel):
    """One failed filed-declaration capture attempt in a bulk run."""

    model_config = ConfigDict(frozen=True)

    modelo: str
    year: int
    period: Period | None = None
    expediente_id: AeatExpedienteId | None = None
    error_type: str
    message: str


class FiledCasillaSkipRow(BaseModel):
    """One casilla a filing carries that the registry channel cannot read.

    Sibling of :class:`FiledDataCaptureFailureRow` and keyed the same way, but a
    different kind of event: the capture succeeded and this row says what the
    artefact holds that could not be enrolled as an amount. A failure row says
    the capture did not happen.

    Carries no value, by the same rule as
    :class:`~adapters.outbound.aeat.sede.ObservedCasillaSkip`: these casillas are
    the non-numeric ones, which include a referencia catastral and the
    taxpayer's address, and this row is built to be rendered.
    """

    model_config = ConfigDict(frozen=True)

    modelo: str
    year: int
    period: Period | None = None
    expediente_id: AeatExpedienteId | None = None
    casilla_id: str
    label: str
    value_kind: str
    reason: str


class BulkFiledDataCaptureReport(FiledCaptureEvidenceTally):
    """Read-only bulk filed-declaration capture report."""

    output_root: str
    modelos: tuple[str, ...]
    year_from: int
    year_to: int
    failed_count: int
    sync_run_ref: SyncRunRecordReference | None = None
    failures: tuple[FiledDataCaptureFailureRow, ...] = ()
    skipped_casillas: tuple[FiledCasillaSkipRow, ...] = ()
    #: One advisory per re-captured filing whose casilla values this sweep
    #: changed, read before each upsert while the prior values still existed.
    recapture_notices: tuple[Notice, ...] = ()
    #: True when the sweep ran as a preview: it read AEAT and computed the
    #: recapture advisories above, and wrote nothing.
    dry_run: bool = False


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

    bucket_id: BucketId
    modelos: tuple[str, ...]
    year_from: int
    year_to: int
    captured_snapshot_count: int
    declaration_count: int
    snapshot_ids: tuple[str, ...]
    failures: tuple[ExpedientesBulkCaptureFailureRow, ...] = ()


class SourceFiledDataCaptureReport(FiledCaptureEvidenceTally):
    """Read-only source-observation capture report for one target filing."""

    output_root: str
    target_modelo: str
    target_year: int
    target_period: Period


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
    provenance: IvaCompensationStateProvenance
    register_status: str | None
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
    reason_identity: IvaCompensationDecisionReason
    operator_explanation: str | None
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
    auth: LiveIvaAuthOutcome
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
    auth: LiveIvaAuthOutcome
    filed_history_succeeded: bool
    wallet_succeeded: bool
    surfaces: tuple[IvaRemoteStateAcquisitionSurfaceManifest, ...]


__all__ = [
    "BulkFiledDataCaptureReport",
    "ExpedientesBulkCaptureFailureRow",
    "ExpedientesBulkCaptureReport",
    "FiledCasillaSkipRow",
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
