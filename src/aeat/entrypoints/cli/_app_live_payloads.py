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

from typing import Any

from ...core import Period
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
    """One failed declaration capture row in a filed pull-all result."""

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

    output_root: str
    modelo: str
    year: int
    captured_count: int
    observation_paths: list[str]
    artefact_refs: list[str]
    casilla_count: int
    calculation_observation_count: int
    calculation_observation_keys: list[str]


@register_schema("app.live.filed.pull_all")
class FiledCaptureAllResult(OutputSchema):
    """Payload for ``aeat app live filed pull-all``."""

    output_root: str
    modelos: list[str]
    year_from: int
    year_to: int
    captured_count: int
    failed_count: int
    observation_paths: list[str]
    artefact_refs: list[str]
    casilla_count: int
    calculation_observation_count: int
    calculation_observation_keys: list[str]
    failures: list[FiledCaptureFailurePayload]


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
    casilla_count: int
    calculation_observation_count: int
    calculation_observation_keys: list[str]


# ---------------------------------------------------------------------------
# IVA wallet leaves
# ---------------------------------------------------------------------------
#
# The pull/history/pull-history/pull-remote-state verbs surface
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


@register_schema("app.live.iva_wallet.pull_remote_state")
class IvaWalletCaptureRemoteStateResult(OutputSchema):
    """Payload for ``aeat app live iva-wallet pull-remote-state``."""

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
    """One snapshot summary in the notifications list result."""

    snapshot_id: str
    captured_at: str
    row_count: int


@register_schema("app.live.notifications.pull")
class NotificationsCaptureResult(OutputSchema):
    """Payload for ``aeat app live notifications pull``."""

    bucket_id: str
    snapshot_id: str
    captured_at: str
    persisted_at: str
    row_count: int
    source_url: str


@register_schema("app.live.notifications.list")
class NotificationsListResult(OutputSchema):
    """Payload for ``aeat app live notifications list``."""

    bucket_id: str
    count: int
    rows: list[NotificationSnapshotListingPayload]


@register_schema("app.live.notifications.view")
class NotificationsViewResult(OutputSchema):
    """Payload for ``aeat app live notifications view``."""

    bucket_id: str
    snapshot_id: str
    captured_at: str
    source_url: str
    row_count: int
    rows: list[NotificationRowPayload]


@register_schema("app.live.notifications.latest")
class NotificationsLatestResult(OutputSchema):
    """Payload for ``aeat app live notifications latest``."""

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
    """One expedientes snapshot summary row in a listing or latest payload."""

    snapshot_id: str
    captured_at: str
    source_url: str
    declaration_count: int


@register_schema("app.live.expedientes.pull")
class ExpedientesCaptureResult(OutputSchema):
    """Payload for ``aeat app live expedientes pull``."""

    bucket_id: str
    snapshot_id: str
    captured_at: str
    persisted_at: str
    declaration_count: int
    source_url: str


class ExpedientesCaptureFailurePayload(OutputSchema):
    """One failed expedientes pull-all row."""

    modelo: str
    year: int
    error_type: str
    message: str


@register_schema("app.live.expedientes.pull_all")
class ExpedientesCaptureAllResult(OutputSchema):
    """Payload for ``aeat app live expedientes pull-all``."""

    bucket_id: str
    modelos: list[str]
    year_from: int
    year_to: int
    captured_snapshot_count: int
    declaration_count: int
    snapshot_ids: list[str]
    failed_count: int
    failures: list[ExpedientesCaptureFailurePayload]


@register_schema("app.live.expedientes.list")
class ExpedientesListResult(OutputSchema):
    """Payload for ``aeat app live expedientes list``."""

    bucket_id: str
    count: int
    rows: list[ExpedienteSnapshotSummaryPayload]


@register_schema("app.live.expedientes.view")
class ExpedientesViewResult(OutputSchema):
    """Payload for ``aeat app live expedientes view``."""

    bucket_id: str
    snapshot_id: str
    captured_at: str
    source_url: str
    declaration_count: int
    declarations: list[ExpedienteDeclarationPayload]


@register_schema("app.live.expedientes.latest")
class ExpedientesLatestResult(OutputSchema):
    """Payload for ``aeat app live expedientes latest``.

    ``snapshot_id`` is ``None`` when the bucket has no captured
    expedientes snapshot; in that case every snapshot-derived field is
    also ``None`` to keep the payload shape stable.
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
    """One borrador-100 snapshot summary row."""

    snapshot_id: str
    filing_year: int
    period: str
    captured_at: str
    source_url: str
    binding_count: int
    state: str


@register_schema("app.live.borrador.100.list")
class Borrador100ListResult(OutputSchema):
    """Payload for ``aeat app live borrador 100 list``."""

    bucket_id: str
    count: int
    rows: list[Borrador100SnapshotSummaryPayload]


@register_schema("app.live.borrador.100.view")
class Borrador100ViewResult(OutputSchema):
    """Payload for ``aeat app live borrador 100 view``.

    ``binding_values`` is a ``{casilla_id: string_amount}`` mapping;
    Decimal values are rendered as their canonical string form before
    they reach the envelope so the strict :class:`OutputSchema` never
    encounters a non-JSON-native scalar at validation time.
    """

    bucket_id: str
    snapshot_id: str
    filing_year: int
    period: str
    captured_at: str
    source_url: str
    binding_count: int
    state: str
    binding_values: dict[str, str]


@register_schema("app.live.borrador.100.latest")
class Borrador100LatestResult(OutputSchema):
    """Payload for ``aeat app live borrador 100 latest``.

    ``snapshot_id`` is ``None`` when no active snapshot exists for the
    requested filing year; in that case every snapshot-derived field is
    also ``None`` to keep the payload shape stable.
    """

    bucket_id: str
    filing_year: int
    snapshot_id: str | None
    captured_at: str | None = None
    period: str | None = None
    source_url: str | None = None
    binding_count: int | None = None
    state: str | None = None
