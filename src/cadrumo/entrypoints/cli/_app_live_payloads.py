"""Typed ``--json`` payload schemas for app live CLI commands.

Each class declared here is a strict
:class:`OutputSchema` subclass and is decorated
with :func:`register_schema` so the
JSON-contract test suite can enumerate every live-command surface this module
covers.

Field sets match the production payload dicts constructed in ``_app_live.py``
at their emit sites.  All sequence fields use ``list`` rather than ``tuple``
because ``model_dump(mode='json')`` serialises pydantic tuples as JSON arrays,
and the strict ``OutputSchema`` base does not coerce lists to tuples on
re-validation.

The application live facade remains authoritative for read-only AEAT access,
bucket-scoped encrypted snapshot persistence, filed-declaration observations,
IVA wallet acquisition, justificante capture, notifications, expedientes,
verification observations, and Borrador 100 snapshots. These classes document
only the CLI transport shape that enters
:class:`SchemaEnvelope` through
:func:`_emit_envelope`; they do not define a live-write surface or a second
persistence contract.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, Field, field_validator, model_validator

from ...application.calculations import ObservationSourceKind
from ...application.live import (
    LiveIvaAcquisitionFailureMode,
    LiveIvaReadStatus,
    LiveIvaReadSurface,
    SnapshotLifecycleState,
)
from ...core import Modelo, Period
from ...core.identity import BucketId, ContentDigest, SnapshotId
from ...domain.calculations.registry import BindingId
from ._schemas import OutputSchema, register_schema


def _is_a_registry_period_token(value: str) -> str:
    """Return ``value`` when it is a bare registry period code, else refuse.

    The justificante wire carries the bare token (``"1T"``, ``"0A"``) rather
    than a structured :class:`~core.Period`, so the JSON contract stays a
    string -- but a string is not a free-form label. Parsing it back through
    the canonical period grammar is what stops ``period='bogus'`` from being
    emitted as a capture's filing period.
    """
    Period.from_year_and_code(2000, value)
    return value


JustificantePeriodToken = Annotated[str, AfterValidator(_is_a_registry_period_token)]
"""A bare registry period code, validated through the canonical period grammar."""

# ---------------------------------------------------------------------------
# Shared sub-models (not registered — used as nested types)
# ---------------------------------------------------------------------------


class FiledListingRowPayload(OutputSchema):
    """JSON projection of one :class:`FiledDataListingRow`.

    The row comes from AEAT's declaration register only; the boolean fields say
    which submitted-file, declaration-copy, or justificante links were visible
    without downloading those artefacts.
    """

    modelo: str
    year: int
    period: str
    expediente_id: str
    status: str
    presented_at: str
    has_submitted_file: bool
    has_declaration_copy: bool
    has_justificante: bool


class FiledCaptureFailurePayload(OutputSchema):
    """JSON projection of one :class:`FiledDataCaptureFailureRow`."""

    modelo: str
    year: int
    period: str | None = None
    expediente_id: str | None = None
    error_type: str
    message: str


# ---------------------------------------------------------------------------
# Registered schemas
# ---------------------------------------------------------------------------


@register_schema("app.live.filed.list")
class FiledListResult(OutputSchema):
    """List result for declaration-register rows returned by the live filed surface.

    Single-modelo calls mirror
    :class:`FiledDataListingReport`; registry-wide calls
    mirror :class:`BulkFiledDataListingReport` and may
    include per-modelo failure rows. No filed artefact bodies are captured by
    this schema.
    """

    modelo_filter: str | None
    year_from: int
    year_to: int
    row_count: int
    failed_count: int = 0
    rows: list[FiledListingRowPayload]
    failures: list[FiledCaptureFailurePayload] = []


@register_schema("app.live.filed.pull")
class FiledCaptureResult(OutputSchema):
    """Capture result for encrypted filed-declaration observations and artefacts.

    In ``single`` mode the payload mirrors
    :class:`FiledDataCaptureReport`; in ``bulk`` mode it
    mirrors :class:`BulkFiledDataCaptureReport`. The
    ``observation_paths`` and ``artefact_refs`` fields identify local encrypted
    stores, while justificante and filing-evidence counts report local metadata
    enrolment against existing :class:`ModeloRecord`
    records.
    """

    mode: Literal["single", "bulk"] = "single"
    output_root: str
    modelo: str | None = None
    year: int | None = None
    modelos: list[str] = []
    year_from: int | None = None
    year_to: int | None = None
    captured_count: int
    failed_count: int = 0
    observation_paths: list[str]
    artefact_refs: list[str]
    justificante_metadata_count: int = 0
    justificante_csvs: list[str] = []
    filing_evidence_stamped_count: int = 0
    filing_record_ids: list[str] = []
    filing_evidence_conflict_count: int = 0
    filing_evidence_conflict_record_ids: list[str] = []
    casilla_count: int
    calculation_observation_count: int
    calculation_observation_keys: list[str]
    failures: list[FiledCaptureFailurePayload] = []


@register_schema("app.live.filed.pull_sources")
class FiledCaptureSourcesResult(OutputSchema):
    """Source-observation capture result for a target filing's registry dependencies.

    Mirrors :class:`SourceFiledDataCaptureReport`: the
    target :class:`Period` is resolved through registry authority, prior filed
    observations are persisted as encrypted local evidence, and matching
    justificantes may enrol local filing evidence without mutating AEAT state.
    """

    output_root: str
    target_modelo: str
    target_year: int
    target_period: Period
    captured_count: int
    observation_paths: list[str]
    artefact_refs: list[str]
    justificante_metadata_count: int = 0
    justificante_csvs: list[str] = []
    filing_evidence_stamped_count: int = 0
    filing_record_ids: list[str] = []
    filing_evidence_conflict_count: int = 0
    filing_evidence_conflict_record_ids: list[str] = []
    casilla_count: int
    calculation_observation_count: int
    calculation_observation_keys: list[str]


# ---------------------------------------------------------------------------
# IVA wallet leaves
# ---------------------------------------------------------------------------
#
# The pull/history/pull-history/pull-evidence verbs surface
# read-only IVA compensation reports. Each registered schema below mirrors
# the dict payload emitted at the corresponding call site in
# ``_app_live.py``; tuple-typed report fields are flattened to ``list``
# because :func:`model_dump` serialises tuples as JSON arrays and
# :class:`OutputSchema`'s strict re-validation does not coerce
# ``list`` back to ``tuple``.


class IvaCompensationHistoryRowPayload(OutputSchema):
    """JSON projection of one :class:`IvaCompensationHistoryRow`."""

    year: int
    period: Period
    status: str
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
    reason: str
    wallet_captured_at: datetime | None
    decided_at: datetime
    authority_sources: list[str]


@register_schema("app.live.iva_wallet.pull")
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


@register_schema("app.live.iva_wallet.history")
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


@register_schema("app.live.iva_wallet.pull_history")
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
    casilla_count: int = Field(default=0, ge=0)
    observation_paths: list[str] = []
    artefact_refs: list[str] = []
    calculation_observation_keys: list[str] = []
    failed_declaration_count: int = Field(default=0, ge=0)
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
    """Redacted JSON projection of :class:`LiveIvaAuthOutcome`."""

    status: LiveIvaReadStatus
    outcome_mode: LiveIvaAcquisitionFailureMode
    failure_mode: LiveIvaAcquisitionFailureMode | None
    failure_type: str | None
    diagnostic_ref: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{12}$")
    provider_kind: str | None
    reused_persisted_session: bool | None
    fresh: bool | None


@register_schema("app.live.iva_wallet.pull_evidence")
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


# ---------------------------------------------------------------------------
# Notifications leaves (bucket-scoped DEHú snapshots)
# ---------------------------------------------------------------------------


class NotificationRowPayload(OutputSchema):
    """One DEHú notification row in a viewed persisted snapshot.

    Mirrors :class:`RemoteNotification` rows stored inside
    :class:`PersistedNotificationsSnapshot`.
    The payload is a CLI projection of already-captured evidence; rendering it
    does not acknowledge, mark, or mutate a notification in AEAT.
    """

    certificado_id: str
    tipo: str
    concepto: str
    titular_nif: str
    titular_nombre: str
    destinatario_nif: str
    destinatario_nombre: str
    fecha_emision: str
    fecha_notificacion: str | None
    modo_notificacion: str | None
    leida: bool | None
    source_url: str
    mode: str


class NotificationSnapshotListingPayload(OutputSchema):
    """Summary row for one persisted DEHu notification snapshot.

    Used by :class:`NotificationsListResult` to expose the bucket snapshot id,
    capture timestamp, and row count returned by
    :class:`NotificationsService` without expanding the underlying
    :class:`NotificationRowPayload` records.
    """

    snapshot_id: SnapshotId
    captured_at: datetime
    row_count: int = Field(ge=0)


@register_schema("app.live.notifications.pull")
class NotificationsCaptureResult(OutputSchema):
    """Typed result for a persisted DEHu notification pull.

    The pull command performs the live read before this schema is built; the
    payload records the bucket-scoped :class:`PersistedNotificationsSnapshot`
    written by :class:`NotificationsService`, not an AEAT-side write or
    acknowledgement.
    """

    bucket_id: BucketId
    snapshot_id: SnapshotId
    captured_at: datetime
    persisted_at: datetime
    row_count: int = Field(ge=0)
    source_url: str = Field(min_length=1)


@register_schema("app.live.notifications.list")
class NotificationsListResult(OutputSchema):
    """Typed listing of persisted DEHu notification snapshots.

    ``rows`` contains :class:`NotificationSnapshotListingPayload` summaries
    returned by :class:`NotificationsService` ``list_snapshots``; message
    detail stays on :class:`NotificationsViewResult`.
    """

    bucket_id: BucketId
    count: int = Field(ge=0)
    rows: list[NotificationSnapshotListingPayload]


@register_schema("app.live.notifications.view")
class NotificationsViewResult(OutputSchema):
    """Typed detail view for one persisted DEHu notification snapshot.

    The command resolves a stored snapshot through
    :class:`NotificationsService` ``show`` and expands its
    :class:`PersistedNotificationsSnapshot` rows as
    :class:`NotificationRowPayload` records. It is a bucket read, not a remote
    notification-state mutation.
    """

    bucket_id: BucketId
    snapshot_id: SnapshotId
    captured_at: datetime
    source_url: str = Field(min_length=1)
    row_count: int = Field(ge=0)
    rows: list[NotificationRowPayload]


@register_schema("app.live.notifications.latest")
class NotificationsLatestResult(OutputSchema):
    """Typed newest-snapshot response for DEHu notifications.

    ``snapshot_id`` is ``None`` when the bucket has no captured notification
    snapshot from :class:`NotificationsService` ``latest``; in that empty case
    every :class:`PersistedNotificationsSnapshot`-derived field is also
    ``None`` so JSON clients can keep one stable schema for present and absent
    data.
    """

    bucket_id: BucketId
    snapshot_id: SnapshotId | None
    captured_at: datetime | None = None
    source_url: str | None = None
    row_count: int | None = Field(default=None, ge=0)


# ---------------------------------------------------------------------------
# Portals leaves (local catalogue)
# ---------------------------------------------------------------------------


class PortalEntryPayload(OutputSchema):
    """One local portal-registry catalogue entry.

    Projects :class:`PortalMetadata` from :data:`PORTAL_REGISTRY`, resolving
    translatable labels before the value enters the CLI envelope. Category,
    auth-method, and URL stability fields carry the domain enum values from
    :class:`PortalCategory`, :class:`AuthMethod`, and :class:`UrlStability`.
    """

    portal: str
    category: str
    subdomain: str
    url: str
    auth_methods: str
    url_stability: str
    label: str
    purpose: str
    active: bool


@register_schema("app.live.portals.list")
class PortalsListResult(OutputSchema):
    """Typed local-catalogue result for ``aeat app live portals list``.

    Rows are selected from :data:`PORTAL_REGISTRY` directly or through
    :func:`portals_by_category` / :func:`portals_for_modelo`, then projected as
    :class:`PortalEntryPayload`; the command never opens a browser or contacts
    AEAT.
    """

    count: int
    rows: list[PortalEntryPayload]


@register_schema("app.live.portals.view")
class PortalsViewResult(PortalEntryPayload):
    """Typed local-catalogue result for ``aeat app live portals view``.

    The requested portal id resolves through :func:`get_portal` and emits the
    same :class:`PortalEntryPayload` projection as the list surface.
    """


# ---------------------------------------------------------------------------
# Expedientes leaves (bucket-scoped AEAT register snapshots)
# ---------------------------------------------------------------------------


class ExpedienteDeclarationPayload(OutputSchema):
    """One declaration-register row inside an expedientes-view payload.

    Mirrors :class:`Declaracion` rows persisted in a
    :class:`PersistedExpedientesSnapshot`.
    Link-text and cell-index fields report what the read-only AEAT register
    exposed; they are not downloaded artefacts and do not imply a remote
    mutation.
    """

    modelo: str
    ejercicio: int
    period: str
    expediente_id: str
    estado: str
    tipo_solicitud: str | None
    observaciones: str | None
    presented_at: str
    justificante_link_text: str | None
    archive_link_text: str | None
    declaration_copy_link_text: str | None
    justificante_cell_index: int
    archive_cell_index: int | None
    declaration_copy_cell_index: int | None
    mode: str


class ExpedienteSnapshotSummaryPayload(OutputSchema):
    """Summary row for one persisted expedientes snapshot.

    Used by :class:`ExpedientesListResult` for rows returned from
    :class:`ExpedientesService`; full :class:`ExpedienteDeclarationPayload`
    detail remains on :class:`ExpedientesViewResult`.
    """

    snapshot_id: str
    captured_at: str
    source_url: str
    declaration_count: int


class ExpedientesCaptureFailurePayload(OutputSchema):
    """One failed modelo/year row from a bulk expedientes pull.

    Mirrors :class:`ExpedientesBulkCaptureFailureRow` entries in
    :class:`ExpedientesBulkCaptureReport`, preserving the failed input
    coordinates and redacted diagnostic text without inventing a partial
    :class:`PersistedExpedientesSnapshot`.
    """

    modelo: str
    year: int
    error_type: str
    message: str


@register_schema("app.live.expedientes.pull")
class ExpedientesCaptureResult(OutputSchema):
    """Typed result for one or more persisted expedientes pulls.

    ``mode`` distinguishes a single-modelo capture from a bulk year-range
    capture. Successful :class:`PersistedExpedientesSnapshot` records are
    persisted by :class:`ExpedientesService`; failed modelo/year pairs are
    reported as :class:`ExpedientesCaptureFailurePayload` rows without inventing
    declaration data.
    """

    mode: Literal["single", "bulk"] = "single"
    bucket_id: str
    snapshot_id: str | None = None
    captured_at: str | None = None
    persisted_at: str | None = None
    declaration_count: int
    source_url: str | None = None
    modelos: list[str] = []
    year_from: int | None = None
    year_to: int | None = None
    captured_snapshot_count: int = 0
    snapshot_ids: list[str] = []
    failed_count: int = 0
    failures: list[ExpedientesCaptureFailurePayload] = []


@register_schema("app.live.expedientes.list")
class ExpedientesListResult(OutputSchema):
    """Typed listing of persisted expedientes snapshots.

    ``rows`` is the compact :class:`ExpedienteSnapshotSummaryPayload`
    projection returned by :class:`ExpedientesService` ``list_snapshots``; use
    :class:`ExpedientesViewResult` for per-declaration detail.
    """

    bucket_id: str
    count: int
    rows: list[ExpedienteSnapshotSummaryPayload]


@register_schema("app.live.expedientes.view")
class ExpedientesViewResult(OutputSchema):
    """Typed detail view for one persisted expedientes snapshot.

    The command resolves a stored :class:`PersistedExpedientesSnapshot` through
    :class:`ExpedientesService` and projects each declaration into
    :class:`ExpedienteDeclarationPayload`.
    """

    bucket_id: str
    snapshot_id: str
    captured_at: str
    source_url: str
    declaration_count: int
    declarations: list[ExpedienteDeclarationPayload]


@register_schema("app.live.expedientes.latest")
class ExpedientesLatestResult(OutputSchema):
    """Typed newest-snapshot response for expedientes.

    ``snapshot_id`` is ``None`` when the bucket has no captured expedientes
    snapshot from :class:`ExpedientesService`; in that case every
    :class:`PersistedExpedientesSnapshot`-derived field is also ``None`` to keep
    the payload shape stable for JSON clients.
    """

    bucket_id: str
    snapshot_id: str | None
    captured_at: str | None = None
    source_url: str | None = None
    declaration_count: int | None = None


# ---------------------------------------------------------------------------
# Verify leaves (NIF / VIES / TGVI audit log)
# ---------------------------------------------------------------------------


class VerifyObservationPayload(OutputSchema):
    """Shared JSON projection of one persisted verify observation.

    Mirrors :class:`VerifyObservation` while keeping ``bucket_id`` on detail
    and capture responses. ``surface`` is the :class:`VerifySurface` value, and
    ``matched_expectation`` records whether the optional operator expectation
    matched the live verdict.
    """

    bucket_id: str
    observation_id: str
    surface: str
    nif: str
    verdict: str
    expected: str | None
    matched_expectation: bool | None
    checked_at: str


# ---------------------------------------------------------------------------
# Justificante capture leaves
# ---------------------------------------------------------------------------


@register_schema("app.live.justificante.pull")
class JustificanteCaptureResult(OutputSchema):
    """Result envelope for a persisted :class:`JustificanteCaptureSnapshot`.

    The pull command stores the signed receipt PDF through
    :class:`JustificanteCaptureSnapshotService` and reports both the
    content-addressed ``pdf_sha256`` snapshot identity inputs and the
    best-effort local enrolment outcome from :class:`JustificanteCaptureOutcome`.
    ``filing_evidence_stamped`` is false when no current local filing record
    exists; the live capture remains persisted and can still back calendar
    evidence once metadata parses.
    """

    bucket_id: BucketId
    snapshot_id: str = Field(min_length=1, max_length=128)
    modelo: Modelo
    filing_year: int = Field(ge=1900, le=9999)
    period: JustificantePeriodToken
    expediente_id: str = Field(min_length=12, max_length=32)
    csv: str = Field(min_length=8, max_length=32)
    pdf_sha256: ContentDigest
    source_kind: ObservationSourceKind
    state: SnapshotLifecycleState
    captured_at: datetime
    justificante_metadata_registered: bool
    calendar_evidence_available: bool
    modelo_filing_record_required: bool
    filing_evidence_stamped: bool
    filing_record_id: str | None = None


class JustificanteSnapshotSummaryPayload(OutputSchema):
    """Summary projection of one :class:`JustificanteCaptureSnapshot`.

    Used by :class:`JustificanteListResult` for active snapshots returned from
    :class:`JustificanteCaptureSnapshotService`.
    """

    snapshot_id: str = Field(min_length=1, max_length=128)
    modelo: Modelo
    filing_year: int = Field(ge=1900, le=9999)
    period: JustificantePeriodToken
    pdf_sha256: ContentDigest
    state: SnapshotLifecycleState
    captured_at: datetime


@register_schema("app.live.justificante.list")
class JustificanteListResult(OutputSchema):
    """List result from :class:`JustificanteCaptureSnapshotService`.

    ``rows`` contains :class:`JustificanteSnapshotSummaryPayload` projections
    for active :class:`JustificanteCaptureSnapshot` records in the active
    bucket, ordered by capture time and carrying the period token,
    :class:`SnapshotLifecycleState`, and raw-PDF hash needed to identify the
    official receipt without exposing the encrypted PDF bytes.
    """

    bucket_id: str
    count: int
    rows: list[JustificanteSnapshotSummaryPayload]


@register_schema("app.live.justificante.view")
class JustificanteViewResult(OutputSchema):
    """Detail view for one persisted :class:`JustificanteCaptureSnapshot`.

    The view resolves through :class:`JustificanteCaptureSnapshotService` and
    surfaces the AEAT expediente, CSV, official ``source_kind``,
    :class:`SnapshotLifecycleState`, and ``pdf_sha256`` so operators can
    reconcile the local evidence chain without printing the stored receipt body.
    """

    bucket_id: BucketId
    snapshot_id: str = Field(min_length=1, max_length=128)
    modelo: Modelo
    filing_year: int = Field(ge=1900, le=9999)
    period: JustificantePeriodToken
    expediente_id: str = Field(min_length=12, max_length=32)
    csv: str = Field(min_length=8, max_length=32)
    pdf_sha256: ContentDigest
    source_kind: ObservationSourceKind
    state: SnapshotLifecycleState
    captured_at: datetime


class VerifyObservationSummaryPayload(OutputSchema):
    """Compact verify-observation row for list output.

    Used by :class:`VerifyListResult` for compact :class:`VerifyObservation`
    projections. The list command already carries ``bucket_id`` at the envelope
    result level, so each row keeps only the observation identity,
    :class:`VerifySurface` value, NIF, verdict, and expectation-match status.
    """

    observation_id: str
    surface: str
    nif: str
    verdict: str
    expected: str | None
    matched_expectation: bool | None
    checked_at: str


@register_schema("app.live.verify.list")
class VerifyListResult(OutputSchema):
    """Typed listing of persisted NIF verification observations.

    ``rows`` contains :class:`VerifyObservationSummaryPayload` projections read
    through :class:`VerifyService`; the command does not contact AEAT.
    """

    bucket_id: str
    count: int
    rows: list[VerifyObservationSummaryPayload]


@register_schema("app.live.verify.view")
class VerifyViewResult(VerifyObservationPayload):
    """Typed detail view for one persisted :class:`VerifyObservation`.

    The inherited :class:`VerifyObservationPayload` fields are resolved through
    :class:`VerifyService` storage, not by performing a fresh live check.
    """


@register_schema("app.live.verify.latest")
class VerifyLatestResult(OutputSchema):
    """Typed newest-observation response for one surface/NIF pair.

    ``observation_id`` is ``None`` when :class:`VerifyService` finds no
    :class:`VerifyObservation` matching the requested (:class:`VerifySurface`,
    NIF) pair; ``surface`` and ``nif`` are still populated to identify the
    lookup, and every observation-derived field is ``None``.
    """

    bucket_id: str
    observation_id: str | None
    surface: str
    nif: str
    verdict: str | None = None
    expected: str | None = None
    matched_expectation: bool | None = None
    checked_at: str | None = None


@register_schema("app.live.verify.nif_iva")
class VerifyNifIvaResult(VerifyObservationPayload):
    """Typed result for an IXVI NIF-IVA live-read observation.

    The command persists the read-only AEAT verdict through
    :class:`VerifyService` before emitting the inherited
    :class:`VerifyObservationPayload` fields.
    """


@register_schema("app.live.verify.tgvi")
class VerifyTgviResult(VerifyObservationPayload):
    """Typed result for a TGVI/GROI live-read observation.

    The command persists the read-only AEAT verdict through
    :class:`VerifyService` before emitting the inherited
    :class:`VerifyObservationPayload` fields.
    """


# ---------------------------------------------------------------------------
# Borrador 100 leaves (bucket-scoped Modelo 100 borrador snapshots)
# ---------------------------------------------------------------------------


def _canonical_borrador_period(value: str) -> str:
    """Validate and normalise the canonical string transport for a filing period."""
    return str(Period.from_string(value))


def _canonical_borrador_utc_timestamp(value: str) -> str:
    """Require an ISO-8601 UTC timestamp while retaining its JSON string form."""
    try:
        timestamp = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("must be an ISO-8601 timestamp") from exc
    if timestamp.tzinfo is None or timestamp.utcoffset() != timedelta(0):
        raise ValueError("must be a UTC timestamp")
    return value


class Borrador100SnapshotSummaryPayload(OutputSchema):
    """Summary row for one persisted Modelo 100 borrador snapshot.

    Projects :class:`Borrador100Snapshot` for :class:`Borrador100ListResult`.
    ``state`` is the :class:`SnapshotLifecycleState` value that controls
    whether :class:`Borrador100SnapshotService` exposes the snapshot as active,
    superseded, discarded, or only through an explicit ``--state all`` listing.
    """

    snapshot_id: SnapshotId
    filing_year: int = Field(ge=1900, le=9999)
    period: str
    captured_at: str
    source_url: str = Field(min_length=1, max_length=2048)
    binding_count: int = Field(ge=0)
    state: Literal["active", "superseded", "discarded"]

    @field_validator("period")
    @classmethod
    def _validate_period(cls, value: str) -> str:
        return _canonical_borrador_period(value)

    @field_validator("captured_at")
    @classmethod
    def _validate_captured_at(cls, value: str) -> str:
        return _canonical_borrador_utc_timestamp(value)


@register_schema("app.live.borrador.100.list")
class Borrador100ListResult(OutputSchema):
    """Typed listing of bucket-scoped Modelo 100 borrador snapshots.

    ``rows`` contains :class:`Borrador100SnapshotSummaryPayload` projections of
    :class:`Borrador100Snapshot` records returned by
    :class:`Borrador100SnapshotService`.
    """

    bucket_id: BucketId
    count: int = Field(ge=0)
    rows: list[Borrador100SnapshotSummaryPayload]

    @model_validator(mode="after")
    def _require_count_to_match_rows(self) -> Borrador100ListResult:
        if self.count != len(self.rows):
            raise ValueError("count must equal the number of Borrador snapshot rows")
        return self


@register_schema("app.live.borrador.100.view")
class Borrador100ViewResult(Borrador100SnapshotSummaryPayload):
    """Typed detail view for one Modelo 100 borrador snapshot.

    ``binding_values`` is a ``{BindingId: string_value}`` mapping keyed by
    :data:`BindingId` from the persisted :class:`Borrador100Snapshot` resolved
    through :class:`Borrador100SnapshotService`. Decimal values are rendered as
    their canonical string form before they reach the envelope so the strict
    :class:`OutputSchema` never encounters a non-JSON-native scalar at
    validation time.
    """

    bucket_id: BucketId
    binding_values: dict[BindingId, str]


@register_schema("app.live.borrador.100.latest")
class Borrador100LatestResult(OutputSchema):
    """Typed newest-active response for Modelo 100 borrador snapshots.

    ``snapshot_id`` is ``None`` when :class:`Borrador100SnapshotService` finds
    no active :class:`Borrador100Snapshot` for the requested filing year; in
    that case every snapshot-derived field, including the
    :class:`SnapshotLifecycleState` value, is also ``None`` to keep the payload
    shape stable while still identifying the queried ``filing_year``.
    """

    bucket_id: BucketId
    filing_year: int = Field(ge=1900, le=9999)
    snapshot_id: SnapshotId | None
    captured_at: str | None = None
    period: str | None = None
    source_url: str | None = Field(default=None, min_length=1, max_length=2048)
    binding_count: int | None = Field(default=None, ge=0)
    state: Literal["active"] | None = None

    @field_validator("period")
    @classmethod
    def _validate_optional_period(cls, value: str | None) -> str | None:
        return _canonical_borrador_period(value) if value is not None else None

    @field_validator("captured_at")
    @classmethod
    def _validate_optional_captured_at(cls, value: str | None) -> str | None:
        return _canonical_borrador_utc_timestamp(value) if value is not None else None

    @model_validator(mode="after")
    def _enforce_latest_empty_or_active_shape(self) -> Borrador100LatestResult:
        snapshot_fields = (self.captured_at, self.period, self.source_url, self.binding_count, self.state)
        if self.snapshot_id is None:
            if any(value is not None for value in snapshot_fields):
                raise ValueError("empty latest results cannot carry snapshot-derived fields")
            return self
        if any(value is None for value in snapshot_fields):
            raise ValueError("latest results with a snapshot_id require every snapshot-derived field")
        return self
