"""Typed JSON transport schemas for the live iva wallet service."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import (
    NonNegativeInt,
    field_validator,
    model_validator,
)

from ...application.live.errors import LiveIvaAcquisitionFailureMode
from ...application.live.remote_state_models import (
    LiveIvaDiagnosticRef,
    LiveIvaReadStatus,
    LiveIvaReadSurface,
)
from ...core.decimal.grammar import is_non_negative_canonical_decimal
from ...core.iva_compensation_provenance import IvaCompensationStateProvenance
from ...core.json_contract import OutputSchema
from ...core.period import Period


class IvaCompensationHistoryRowPayload(OutputSchema):
    """JSON projection of one :class:`IvaCompensationHistoryRow`."""

    year: int
    period: Period
    provenance: IvaCompensationStateProvenance
    register_status: str | None = None
    presented_at: str
    prior_pending_amount: str | None
    applied_amount: str | None
    pending_for_later_amount: str | None
    period_result_amount: str | None
    final_result_amount: str | None
    generated_amount: str
    available_end_amount: str


class IvaCompensationCarryForwardLotPayload(OutputSchema):
    """JSON projection of one :class:`IvaCompensationCarryForwardLotRow`."""

    taxpayer_ref: str
    source_filing_year: int
    source_period: Period
    generated_amount: str
    applied_amount: str
    remaining_amount: str
    age_years: int
    expiry_review_state: str
    source_observation_key: str


class IvaWalletAuthorityDecisionPayload(OutputSchema):
    """JSON projection of one :class:`IvaWalletAuthorityDecisionRow`.

    The decision records which authority source won for a target
    :class:`Period`: AEAT wallet evidence, local recurrence, or an explicit
    override. ``blocked`` and ``stale_wallet`` remain visible because they are
    filing-grade guard signals, not raw taxpayer identifiers.
    """

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
    reason_identity: str
    reason: str
    operator_explanation: str | None
    wallet_captured_at: datetime | None
    decided_at: datetime
    authority_sources: list[str]


class IvaWalletPullResult(OutputSchema):
    """Read-only wallet capture result from :class:`IvaWalletCaptureReport`.

    The payload identifies the persisted wallet observation and reconciliation
    decision for one target :class:`Period`. It reports the selected authority,
    divergence, and blocking state without exposing raw AEAT wallet rows in the
    CLI envelope.
    """

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
    captured_at: str


class IvaWalletHistoryResult(OutputSchema):
    """Stored IVA evidence report from :class:`IvaCompensationHistoryReport`.

    This command is local-only: rows, carry-forward lots, and wallet authority
    decisions are reloaded from secure profile storage without authenticating to
    AEAT or touching a live browser session.
    """

    row_count: int
    as_of_year: int | None
    carry_forward_lot_count: int
    unallocated_applied_amount: str
    authority_decision_count: int
    rows: list[IvaCompensationHistoryRowPayload]
    carry_forward_lots: list[IvaCompensationCarryForwardLotPayload]
    authority_decisions: list[IvaWalletAuthorityDecisionPayload]

    @field_validator("unallocated_applied_amount")
    @classmethod
    def _is_a_non_negative_canonical_amount(cls, value: str) -> str:
        """Re-assert on the wire the bound the record carries in Decimal form.

        The application record bounds this at ``ge=0``. Stringifying it for JSON
        drops that, so without this the payload could publish a negative balance
        the domain cannot hold -- the same assertion the sibling wallet balance
        payload already made, absent here only because this module had no
        validators at all.
        """
        if not is_non_negative_canonical_decimal(value):
            raise ValueError(f"amount must be a non-negative canonical decimal, got {value!r}")
        return value


class IvaWalletCaptureHistoryResult(OutputSchema):
    """Filed-history capture result from :class:`IvaCompensationHistoryCaptureReport`.

    The report comes from read-only Modelo 303 filed-history acquisition and
    includes the secure reload count that proves persisted observations were
    available through the profile-local evidence repositories.
    """

    output_root: str
    year_from: int
    year_to: int
    captured_count: int
    calculation_observation_count: int
    reloaded_history_count: int
    # Evidence fidelity carried from
    # :class:`IvaCompensationHistoryCaptureReport`. Without the failure fields a
    # partial capture presented its counts with no way to tell that some
    # declarations were never read; the path/ref/key fields let an operator
    # confirm what the counts are counting.
    casilla_count: NonNegativeInt = 0
    observation_paths: list[str] = []
    artefact_refs: list[str] = []
    calculation_observation_keys: list[str] = []
    failed_declaration_count: NonNegativeInt = 0
    failed_declarations: list[str] = []

    @model_validator(mode="after")
    def _failure_count_agrees_with_named_failures(self) -> IvaWalletCaptureHistoryResult:
        """A reported failure count must be backed by the declarations it counts.

        The point of carrying both is that a partial capture cannot present a
        bare number; a count without its names would reinstate exactly that.
        """
        if self.failed_declarations and self.failed_declaration_count != len(self.failed_declarations):
            raise ValueError(
                f"failed_declaration_count {self.failed_declaration_count} disagrees with "
                f"{len(self.failed_declarations)} named failed declarations",
            )
        return self


class LiveIvaSurfaceOutcomePayload(OutputSchema):
    """Redacted JSON projection of one :class:`LiveIvaReadOutcome`.

    Filed history and wallet/cartera outcomes are reported independently so a
    successful surface can persist evidence even when the other surface fails
    closed with redacted diagnostics.
    """

    surface: LiveIvaReadSurface
    status: LiveIvaReadStatus
    outcome_mode: LiveIvaAcquisitionFailureMode
    failure_mode: LiveIvaAcquisitionFailureMode | None
    failure_type: str | None
    failure_context: dict[str, Any] | None
    captured_count: int | None
    calculation_observation_count: int | None


class LiveIvaAuthOutcomePayload(OutputSchema):
    """Redacted JSON projection of :class:`LiveIvaAuthOutcome`.

    ``diagnostic_ref`` carries the projected model's own
    :data:`~cadrumo.application.live.remote_state_models.LiveIvaDiagnosticRef`
    rather than restating the digest shape, so the wire schema and the record
    it projects cannot come to disagree about the truncation width.
    """

    status: LiveIvaReadStatus
    outcome_mode: LiveIvaAcquisitionFailureMode
    failure_mode: LiveIvaAcquisitionFailureMode | None
    failure_type: str | None
    diagnostic_ref: LiveIvaDiagnosticRef | None = None
    provider_kind: str | None
    reused_persisted_session: bool | None
    fresh: bool | None


class IvaWalletPullEvidenceResult(OutputSchema):
    """Combined IVA acquisition payload for :class:`IvaRemoteStateAcquisitionReport`.

    The result carries the encrypted acquisition manifest id, redacted auth
    outcome, and per-surface read outcomes for filed history and wallet/cartera.
    It is operational evidence of read-only acquisition, not an AEAT submission
    or payment record.
    """

    output_root: str
    year_from: int
    year_to: int
    target_year: int
    target_period: Period
    acquisition_manifest_id: str
    auth: LiveIvaAuthOutcomePayload
    filed_history_succeeded: bool
    wallet_succeeded: bool
    outcomes: list[LiveIvaSurfaceOutcomePayload]


__all__ = [
    "IvaCompensationCarryForwardLotPayload",
    "IvaCompensationHistoryRowPayload",
    "IvaWalletAuthorityDecisionPayload",
    "IvaWalletCaptureHistoryResult",
    "IvaWalletHistoryResult",
    "IvaWalletPullEvidenceResult",
    "IvaWalletPullResult",
    "LiveIvaAuthOutcomePayload",
    "LiveIvaSurfaceOutcomePayload",
]
