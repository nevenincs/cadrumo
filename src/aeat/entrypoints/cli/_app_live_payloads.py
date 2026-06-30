"""Typed ``--json`` payload schemas for app live CLI commands.

Each class declared here is a strict
:class:`~aeat.entrypoints.cli._schemas.OutputSchema` subclass and is decorated
with :func:`~aeat.entrypoints.cli._schemas.register_schema` so the
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
:class:`~aeat.entrypoints.cli._schemas.SchemaEnvelope`; they do not define a
live-write surface or a second persistence contract.
"""

from __future__ import annotations

from typing import Any, Literal

from ...core import Period
from ...domain.calculations.registry import BindingId
from ._schemas import OutputSchema, register_schema

# ---------------------------------------------------------------------------
# Shared sub-models (not registered — used as nested types)
# ---------------------------------------------------------------------------


class FiledListingRowPayload(OutputSchema):
    """JSON projection of one :class:`~aeat.application.live.FiledDataListingRow`.

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
    """JSON projection of one :class:`~aeat.application.live.FiledDataCaptureFailureRow`."""

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
    :class:`~aeat.application.live.FiledDataListingReport`; registry-wide calls
    mirror :class:`~aeat.application.live.BulkFiledDataListingReport` and may
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
    :class:`~aeat.application.live.FiledDataCaptureReport`; in ``bulk`` mode it
    mirrors :class:`~aeat.application.live.BulkFiledDataCaptureReport`. The
    ``observation_paths`` and ``artefact_refs`` fields identify local encrypted
    stores, while justificante and filing-evidence counts report local metadata
    enrolment against existing :class:`~aeat.domain.modelos.ModeloRecord`
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

    Mirrors :class:`~aeat.application.live.SourceFiledDataCaptureReport`: the
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
    """JSON projection of one :class:`~aeat.application.live.IvaCompensationHistoryRow`."""

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
    """JSON projection of one :class:`~aeat.application.live.IvaCompensationCarryForwardLotRow`."""

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
    """JSON projection of one :class:`~aeat.application.live.IvaWalletAuthorityDecisionRow`.

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
    authority_sources: list[str]


@register_schema("app.live.iva_wallet.pull")
class IvaWalletPullResult(OutputSchema):
    """Read-only wallet capture result from :class:`~aeat.application.live.IvaWalletCaptureReport`.

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
    """Stored IVA evidence report from :class:`~aeat.application.live.IvaCompensationHistoryReport`.

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
    """Filed-history capture result from :class:`~aeat.application.live.IvaCompensationHistoryCaptureReport`.

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


class LiveIvaSurfaceOutcomePayload(OutputSchema):
    """Redacted JSON projection of one :class:`~aeat.application.live.LiveIvaReadOutcome`.

    Filed history and wallet/cartera outcomes are reported independently so a
    successful surface can persist evidence even when the other surface fails
    closed with redacted diagnostics.
    """

    surface: str
    status: str
    outcome_mode: str
    failure_mode: str | None
    failure_type: str | None
    failure_context: dict[str, Any] | None
    captured_count: int | None
    calculation_observation_count: int | None


class LiveIvaAuthOutcomePayload(OutputSchema):
    """Redacted JSON projection of :class:`~aeat.application.live.LiveIvaAuthOutcome`."""

    status: str
    outcome_mode: str
    failure_mode: str | None
    failure_type: str | None
    provider_kind: str | None
    reused_persisted_session: bool | None
    fresh: bool | None


@register_schema("app.live.iva_wallet.pull_evidence")
class IvaWalletPullEvidenceResult(OutputSchema):
    """Combined IVA acquisition payload for :class:`~aeat.application.live.IvaRemoteStateAcquisitionReport`.

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

    Mirrors :class:`~aeat.adapters.outbound.aeat.sede.RemoteNotification` rows
    stored inside
    :class:`~aeat.application.live._notifications.PersistedNotificationsSnapshot`.
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
    :class:`~aeat.application.live.NotificationsService` without expanding the
    underlying notification rows.
    """

    snapshot_id: str
    captured_at: str
    row_count: int


@register_schema("app.live.notifications.pull")
class NotificationsCaptureResult(OutputSchema):
    """Typed result for a persisted DEHu notification pull.

    The pull command performs the live read before this schema is built; the
    payload records the bucket-scoped snapshot written by
    :class:`~aeat.application.live.NotificationsService`, not an AEAT-side write
    or acknowledgement.
    """

    bucket_id: str
    snapshot_id: str
    captured_at: str
    persisted_at: str
    row_count: int
    source_url: str


@register_schema("app.live.notifications.list")
class NotificationsListResult(OutputSchema):
    """Typed listing of persisted DEHu notification snapshots.

    ``rows`` contains :class:`NotificationSnapshotListingPayload` summaries
    returned by :class:`~aeat.application.live.NotificationsService`
    ``list_snapshots``; message detail stays on the view payload.
    """

    bucket_id: str
    count: int
    rows: list[NotificationSnapshotListingPayload]


@register_schema("app.live.notifications.view")
class NotificationsViewResult(OutputSchema):
    """Typed detail view for one persisted DEHu notification snapshot.

    The command resolves a stored snapshot through
    :class:`~aeat.application.live.NotificationsService` ``show`` and expands
    its rows as :class:`NotificationRowPayload` records. It is a bucket read,
    not a remote notification-state mutation.
    """

    bucket_id: str
    snapshot_id: str
    captured_at: str
    source_url: str
    row_count: int
    rows: list[NotificationRowPayload]


@register_schema("app.live.notifications.latest")
class NotificationsLatestResult(OutputSchema):
    """Typed newest-snapshot response for DEHu notifications.

    ``snapshot_id`` is ``None`` when the bucket has no captured notification
    snapshot; in that empty case every snapshot-derived field is also ``None``
    so JSON clients can keep one stable schema for present and absent data.
    """

    bucket_id: str
    snapshot_id: str | None
    captured_at: str | None = None
    source_url: str | None = None
    row_count: int | None = None


# ---------------------------------------------------------------------------
# Portals leaves (local catalogue)
# ---------------------------------------------------------------------------


class PortalEntryPayload(OutputSchema):
    """One local portal-registry catalogue entry.

    Projects :class:`~aeat.domain.portals.PortalMetadata` from
    :data:`~aeat.domain.portals.PORTAL_REGISTRY`, resolving translatable labels
    before the value enters the CLI envelope.  Category, auth-method, and URL
    stability fields carry the domain enum values from
    :class:`~aeat.domain.portals.PortalCategory`,
    :class:`~aeat.domain.portals.AuthMethod`, and
    :class:`~aeat.domain.portals.UrlStability`.
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

    Rows are selected from :data:`~aeat.domain.portals.PORTAL_REGISTRY` directly
    or through :func:`~aeat.domain.portals.portals_by_category` /
    :func:`~aeat.domain.portals.portals_for_modelo`; the command never opens a
    browser or contacts AEAT.
    """

    count: int
    rows: list[PortalEntryPayload]


@register_schema("app.live.portals.view")
class PortalsViewResult(PortalEntryPayload):
    """Typed local-catalogue result for ``aeat app live portals view``.

    The requested portal id resolves through
    :func:`~aeat.domain.portals.get_portal` and emits the same
    :class:`PortalEntryPayload` projection as the list surface.
    """


# ---------------------------------------------------------------------------
# Expedientes leaves (bucket-scoped AEAT register snapshots)
# ---------------------------------------------------------------------------


class ExpedienteDeclarationPayload(OutputSchema):
    """One declaration-register row inside an expedientes-view payload.

    Mirrors :class:`~aeat.adapters.outbound.aeat.sede.Declaracion` rows
    persisted in a
    :class:`~aeat.application.live._expedientes.PersistedExpedientesSnapshot`.
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
    :class:`~aeat.application.live.ExpedientesService`; full declaration detail
    remains on :class:`ExpedientesViewResult`.
    """

    snapshot_id: str
    captured_at: str
    source_url: str
    declaration_count: int


class ExpedientesCaptureFailurePayload(OutputSchema):
    """One failed modelo/year row from a bulk expedientes pull.

    Mirrors
    :class:`~aeat.application.live.ExpedientesBulkCaptureFailureRow` entries in
    :class:`~aeat.application.live.ExpedientesBulkCaptureReport`, preserving the
    failed input coordinates and redacted diagnostic text without inventing a
    partial snapshot.
    """

    modelo: str
    year: int
    error_type: str
    message: str


@register_schema("app.live.expedientes.pull")
class ExpedientesCaptureResult(OutputSchema):
    """Typed result for one or more persisted expedientes pulls.

    ``mode`` distinguishes a single-modelo capture from a bulk year-range
    capture. Successful snapshots are persisted by
    :class:`~aeat.application.live.ExpedientesService`; failed modelo/year pairs
    are reported as :class:`ExpedientesCaptureFailurePayload` rows without
    inventing declaration data.
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
    projection returned by :class:`~aeat.application.live.ExpedientesService`
    ``list_snapshots``; use the view schema for per-declaration detail.
    """

    bucket_id: str
    count: int
    rows: list[ExpedienteSnapshotSummaryPayload]


@register_schema("app.live.expedientes.view")
class ExpedientesViewResult(OutputSchema):
    """Typed detail view for one persisted expedientes snapshot.

    The command resolves a stored snapshot through
    :class:`~aeat.application.live.ExpedientesService` and projects each
    declaration into :class:`ExpedienteDeclarationPayload`.
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
    snapshot; in that case every snapshot-derived field is also ``None`` to
    keep the payload shape stable for JSON clients.
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

    Mirrors :class:`aeat.application.live._verify.VerifyObservation` while
    keeping ``bucket_id`` on detail and capture responses. ``surface`` is the
    :class:`~aeat.application.live.VerifySurface` value, and
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
    """Result envelope for a persisted :class:`~aeat.application.live.JustificanteCaptureSnapshot`.

    The pull command stores the signed receipt PDF through
    :class:`~aeat.application.live.JustificanteCaptureSnapshotService` and
    reports both the content-addressed ``pdf_sha256`` snapshot identity inputs
    and the best-effort local enrolment outcome. ``filing_evidence_stamped`` is
    false when no current local filing record exists; the live capture remains
    persisted and can still back calendar evidence once metadata parses.
    """

    bucket_id: str
    snapshot_id: str
    modelo: str
    filing_year: int
    period: str
    expediente_id: str
    csv: str
    pdf_sha256: str
    source_kind: str
    state: str
    captured_at: str
    justificante_metadata_registered: bool
    calendar_evidence_available: bool
    modelo_filing_record_required: bool
    filing_evidence_stamped: bool
    filing_record_id: str | None = None


class JustificanteSnapshotSummaryPayload(OutputSchema):
    """Summary projection of one :class:`~aeat.application.live.JustificanteCaptureSnapshot`."""

    snapshot_id: str
    modelo: str
    filing_year: int
    period: str
    pdf_sha256: str
    state: str
    captured_at: str


@register_schema("app.live.justificante.list")
class JustificanteListResult(OutputSchema):
    """List result from :class:`~aeat.application.live.JustificanteCaptureSnapshotService`.

    Rows are active justificante-capture snapshots for the active bucket,
    ordered by capture time and carrying the period token, lifecycle state, and
    raw-PDF hash needed to identify the official receipt without exposing the
    encrypted PDF bytes.
    """

    bucket_id: str
    count: int
    rows: list[JustificanteSnapshotSummaryPayload]


@register_schema("app.live.justificante.view")
class JustificanteViewResult(OutputSchema):
    """Detail view for one persisted :class:`~aeat.application.live.JustificanteCaptureSnapshot`.

    The view surfaces the AEAT expediente, CSV, official ``source_kind``,
    lifecycle state, and ``pdf_sha256`` so operators can reconcile the local
    evidence chain without printing the stored receipt body.
    """

    bucket_id: str
    snapshot_id: str
    modelo: str
    filing_year: int
    period: str
    expediente_id: str
    csv: str
    pdf_sha256: str
    source_kind: str
    state: str
    captured_at: str


class VerifyObservationSummaryPayload(OutputSchema):
    """Compact verify-observation row for list output.

    The list command already carries ``bucket_id`` at the envelope result level,
    so each row keeps only the observation identity, surface, NIF, verdict, and
    expectation-match status.
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
    through :class:`~aeat.application.live.VerifyService`; the command does not
    contact AEAT.
    """

    bucket_id: str
    count: int
    rows: list[VerifyObservationSummaryPayload]


@register_schema("app.live.verify.view")
class VerifyViewResult(VerifyObservationPayload):
    """Typed detail view for one persisted verify observation."""


@register_schema("app.live.verify.latest")
class VerifyLatestResult(OutputSchema):
    """Typed newest-observation response for one surface/NIF pair.

    ``observation_id`` is ``None`` when no observation matches the
    requested (surface, NIF) pair; ``surface`` and ``nif`` are still
    populated to identify the lookup, and every observation-derived
    field is ``None``.
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
    :class:`~aeat.application.live.VerifyService` before emitting this payload.
    """


@register_schema("app.live.verify.tgvi")
class VerifyTgviResult(VerifyObservationPayload):
    """Typed result for a TGVI/GROI live-read observation.

    The command persists the read-only AEAT verdict through
    :class:`~aeat.application.live.VerifyService` before emitting this payload.
    """


# ---------------------------------------------------------------------------
# Borrador 100 leaves (bucket-scoped Modelo 100 borrador snapshots)
# ---------------------------------------------------------------------------


class Borrador100SnapshotSummaryPayload(OutputSchema):
    """Summary row for one persisted Modelo 100 borrador snapshot.

    ``state`` is the
    :class:`~aeat.application.live.SnapshotLifecycleState` value that controls
    whether :class:`~aeat.application.live.Borrador100SnapshotService` exposes
    the snapshot as active, superseded, discarded, or only through an explicit
    ``--state all`` listing.
    """

    snapshot_id: str
    filing_year: int
    period: str
    captured_at: str
    source_url: str
    binding_count: int
    state: str


@register_schema("app.live.borrador.100.list")
class Borrador100ListResult(OutputSchema):
    """Typed listing of bucket-scoped Modelo 100 borrador snapshots.

    ``rows`` contains :class:`Borrador100SnapshotSummaryPayload` projections of
    :class:`~aeat.application.live.Borrador100Snapshot` records returned by
    :class:`~aeat.application.live.Borrador100SnapshotService`.
    """

    bucket_id: str
    count: int
    rows: list[Borrador100SnapshotSummaryPayload]


@register_schema("app.live.borrador.100.view")
class Borrador100ViewResult(OutputSchema):
    """Typed detail view for one Modelo 100 borrador snapshot.

    ``binding_values`` is a ``{BindingId: string_value}`` mapping from the
    persisted :class:`~aeat.application.live.Borrador100Snapshot`. Decimal values
    are rendered as their canonical string form before they reach the envelope
    so the strict :class:`OutputSchema` never encounters a non-JSON-native
    scalar at validation time.
    """

    bucket_id: str
    snapshot_id: str
    filing_year: int
    period: str
    captured_at: str
    source_url: str
    binding_count: int
    state: str
    binding_values: dict[BindingId, str]


@register_schema("app.live.borrador.100.latest")
class Borrador100LatestResult(OutputSchema):
    """Typed newest-active response for Modelo 100 borrador snapshots.

    ``snapshot_id`` is ``None`` when no active snapshot exists for the requested
    filing year; in that case every snapshot-derived field is also ``None`` to
    keep the payload shape stable while still identifying the queried
    ``filing_year``.
    """

    bucket_id: str
    filing_year: int
    snapshot_id: str | None
    captured_at: str | None = None
    period: str | None = None
    source_url: str | None = None
    binding_count: int | None = None
    state: str | None = None
