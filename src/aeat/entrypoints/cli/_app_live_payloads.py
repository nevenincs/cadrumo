"""Typed ``--json`` payload schemas for app live CLI commands.

Each class declared here is a strict :class:`OutputSchema` subclass and is
decorated with :func:`register_schema` so the JSON-contract test suite can
enumerate every live-command surface this module covers.

Field sets match the production payload dicts constructed in ``_app_live.py``
at their emit sites.  All sequence fields use ``list`` rather than ``tuple``
because ``model_dump(mode='json')`` serialises pydantic tuples as JSON arrays,
and the strict ``OutputSchema`` base does not coerce lists to tuples on
re-validation.
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
    """One filed declaration row in a filed-list result."""

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
    """One failed declaration capture row in a filed pull result."""

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
    """Payload for ``aeat app live filed list``."""

    modelo_filter: str | None
    year_from: int
    year_to: int
    row_count: int
    failed_count: int = 0
    rows: list[FiledListingRowPayload]
    failures: list[FiledCaptureFailurePayload] = []


@register_schema("app.live.filed.pull")
class FiledCaptureResult(OutputSchema):
    """Payload for ``aeat app live filed pull``."""

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
    """Payload for ``aeat app live filed pull-sources``."""

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
    """One profile-local IVA compensation history row."""

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
    """One carry-forward lot row."""

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
    """One persisted wallet authority decision."""

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
    """Payload for ``aeat app live iva-wallet pull``."""

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
    """Payload for ``aeat app live iva-wallet history``."""

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
    """Payload for ``aeat app live iva-wallet pull-history``."""

    output_root: str
    year_from: int
    year_to: int
    captured_count: int
    calculation_observation_count: int
    reloaded_history_count: int


class LiveIvaSurfaceOutcomePayload(OutputSchema):
    """One per-surface live IVA acquisition outcome."""

    surface: str
    status: str
    outcome_mode: str
    failure_mode: str | None
    failure_type: str | None
    failure_context: dict[str, Any] | None
    captured_count: int | None
    calculation_observation_count: int | None


class LiveIvaAuthOutcomePayload(OutputSchema):
    """Redacted live IVA auth outcome."""

    status: str
    outcome_mode: str
    failure_mode: str | None
    failure_type: str | None
    provider_kind: str | None
    reused_persisted_session: bool | None
    fresh: bool | None


@register_schema("app.live.iva_wallet.pull_evidence")
class IvaWalletPullEvidenceResult(OutputSchema):
    """Payload for ``aeat app live iva-wallet pull-evidence``."""

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
    """One DEHú notification snapshot row in a viewed/captured snapshot."""

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
    """One portal-registry catalogue entry."""

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
    """Payload for ``aeat app live portals list``."""

    count: int
    rows: list[PortalEntryPayload]


@register_schema("app.live.portals.view")
class PortalsViewResult(PortalEntryPayload):
    """Payload for ``aeat app live portals view``."""


# ---------------------------------------------------------------------------
# Expedientes leaves (bucket-scoped AEAT register snapshots)
# ---------------------------------------------------------------------------


class ExpedienteDeclarationPayload(OutputSchema):
    """One Declaracion row inside an expedientes-view payload."""

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
    """One failed expedientes pull row."""

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
    """One persisted verify observation row."""

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
    """Payload for ``aeat app live justificante pull``."""

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
    """One justificante-capture snapshot summary row in a listing."""

    snapshot_id: str
    modelo: str
    filing_year: int
    period: str
    pdf_sha256: str
    state: str
    captured_at: str


@register_schema("app.live.justificante.list")
class JustificanteListResult(OutputSchema):
    """Payload for ``aeat app live justificante list``."""

    bucket_id: str
    count: int
    rows: list[JustificanteSnapshotSummaryPayload]


@register_schema("app.live.justificante.view")
class JustificanteViewResult(OutputSchema):
    """Payload for ``aeat app live justificante view``."""

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
    """One row in the verify-list result (no bucket_id field per row)."""

    observation_id: str
    surface: str
    nif: str
    verdict: str
    expected: str | None
    matched_expectation: bool | None
    checked_at: str


@register_schema("app.live.verify.list")
class VerifyListResult(OutputSchema):
    """Payload for ``aeat app live verify list``."""

    bucket_id: str
    count: int
    rows: list[VerifyObservationSummaryPayload]


@register_schema("app.live.verify.view")
class VerifyViewResult(VerifyObservationPayload):
    """Payload for ``aeat app live verify view``."""


@register_schema("app.live.verify.latest")
class VerifyLatestResult(OutputSchema):
    """Payload for ``aeat app live verify latest``.

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
    """Payload for ``aeat app live verify nif-iva``."""


@register_schema("app.live.verify.tgvi")
class VerifyTgviResult(VerifyObservationPayload):
    """Payload for ``aeat app live verify tgvi``."""


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
