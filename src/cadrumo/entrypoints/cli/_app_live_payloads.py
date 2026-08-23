"""Typed ``--json`` payload schemas for app live CLI commands.

Each class declared here is a strict :class:`OutputSchema` subclass. Production
CommandSpec declarations own the schema identities and deferred class targets
used to enumerate every live-command surface this module covers.

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

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, Field, field_validator, model_validator

from ...application.calculations import ObservationSourceKind
from ...application.live import (
    LiveIvaAcquisitionFailureMode,
    LiveIvaReadStatus,
    LiveIvaReadSurface,
    SnapshotLifecycleState,
)
from ...core import IvaCompensationStateProvenance, Modelo, Period
from ...core.errors import CoreValidationError
from ...core.identity import (
    AeatCertificadoId,
    AeatClaveLiquidacion,
    AeatCsv,
    AeatExpedienteId,
    BucketId,
    ContentDigest,
    FilingRecordId,
    SnapshotId,
)
from ...core.json_contract import OutputSchema
from ...core.time import validate_utc_aware
from ...domain.calculations.registry import BindingId


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
    expediente_id: AeatExpedienteId
    status: str
    presented_at: str
    has_submitted_file: bool
    has_declaration_copy: bool
    has_justificante: bool


class FiledHistoryDiscoveryPairPayload(OutputSchema):
    """JSON projection of one :class:`FiledHistoryDiscoveryPair`.

    ``signals`` is the load-bearing field and is deliberately NOT collapsed to a
    boolean or dropped once the union is built: it is what tells a reader whether
    an empty result for this pair means anything. ``zero_rows_is_an_anomaly``
    carries the derived answer so a consumer of the JSON does not have to
    reimplement the rule and possibly get it wrong.
    """

    modelo: str
    ejercicio: int
    signals: list[str]
    zero_rows_is_an_anomaly: bool


class FiledCaptureFailurePayload(OutputSchema):
    """JSON projection of one :class:`FiledDataCaptureFailureRow`."""

    modelo: str
    year: int
    period: str | None = None
    expediente_id: AeatExpedienteId | None = None
    error_type: str
    message: str


# ---------------------------------------------------------------------------
# Graph-declared schema targets
# ---------------------------------------------------------------------------


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


class FiledDiscoverResult(OutputSchema):
    """Discovery result: which ``(modelo, ejercicio)`` pairs a history pull would walk.

    Mirrors :class:`FiledHistoryDiscoveryReport`. Read-only; nothing is captured
    or persisted by the verb that emits this.

    The two count fields are not decoration. ``profile_expected_count`` is the
    only number in this payload that supports a completeness claim, because only
    the profile signal is taxpayer-specific by construction;
    ``register_options_only_count`` counts pairs offered by a list whose scoping
    is unconfirmed, which widens the walk but proves nothing about this
    taxpayer's history.

    Attributes:
        pairs: Every pair a history pull would walk, each tagged with the
            signal(s) that nominated it.
        pair_count: Total pairs in the walk grid.
        profile_expected_count: Pairs the taxpayer's own declared facts expected.
        register_options_only_count: Pairs offered ONLY by the register's option
            list. A zero-row outcome for one of these is a plain negative.
        profile_year_span_determined: Whether the profile declared the activity
            start date the year axis needs. ``False`` means the profile signal
            contributed nothing and this payload is NOT a coverage denominator.
        register_options_read: Whether the register's option lists were read.
        carries_a_taxpayer_specific_denominator: Whether any coverage claim can
            rest on this report at all.
    """

    pairs: list[FiledHistoryDiscoveryPairPayload]
    pair_count: int
    profile_expected_count: int
    register_options_only_count: int
    profile_year_span_determined: bool
    register_options_read: bool
    carries_a_taxpayer_specific_denominator: bool


class FiledHistoryPairOutcomePayload(OutputSchema):
    """What one walked ``(modelo, ejercicio)`` pair actually produced.

    ``failure_message`` being set is a DIFFERENT fact from ``row_count`` being
    zero, and the two are carried separately on purpose. A truncated register
    page is refused by the walker and absorbed into a failure row, so folding it
    into "zero rows" would render a parse refusal as "no filings found" — the
    silent under-report this whole cluster exists to remove. Read
    :attr:`refused` before reading :attr:`row_count`.

    Attributes:
        modelo: Modelo code.
        ejercicio: Filing year.
        signals: The discovery signal(s) that nominated this pair.
        row_count: Register rows the walk returned. Meaningful only when the
            pair did not refuse.
        captured_count: Declaraciones actually captured from those rows.
        refused: Whether the pair produced a failure row instead of an answer.
        failure_type: Exception type of the refusal, when refused.
        failure_message: Bounded refusal text, when refused.
    """

    modelo: str
    ejercicio: int
    signals: list[str]
    row_count: int = 0
    captured_count: int = 0
    refused: bool = False
    failure_type: str | None = None
    failure_message: str | None = None


class FiledHistoryOnboardingResult(OutputSchema):
    """One history-onboarding run: what was walked, captured and reconciled.

    **This payload carries no completeness percentage and no fraction, and that
    absence is a decision rather than an omission.** A ratio computed over the
    walked pairs would be a ratio over a denominator that partly comes from
    AEAT's offered option list, whose scoping to this NIF is unconfirmed — so the
    number would look like coverage while resting on a set that may have nothing
    to do with this taxpayer. ``denominator_note`` says in prose what the
    denominator actually was, which is the honest form of the same information.
    A gate asserts no percentage or fraction field regrows here.

    Attributes:
        pairs: Per-pair outcomes, each tagged with the signal(s) behind it.
        pair_count: Pairs walked.
        profile_expected_count: Pairs the taxpayer's declared facts expected.
        register_options_only_count: Pairs offered only by the unconfirmed list.
        refused_count: Pairs that produced a failure row rather than an answer.
        empty_count: Pairs that legitimately returned no rows.
        captured_count: Declaraciones captured across the run.
        reached_count: Declaraciones the sweep REACHED. Distinct from
            ``captured_count``, which counts written observation paths and so
            stays zero in a preview — leaving it unable to say whether a limited
            sweep stopped early on the very path where that matters most.
        scoping_signal: The offline reading of whether the register's option list
            looks NIF-scoped. Advisory; every value is a hedge.
        denominator_note: Prose statement of what the coverage denominator was
            and what it does not establish.
        iva_wallet_status: Outcome token for the IVA wallet stage.
        iva_wallet_divergence: The wallet reconciliation's divergence verdict.
        iva_wallet_blocked: Whether the wallet divergence blocks verify/file.
        notificaciones_status: Outcome token for the notificaciones stage.
        notificaciones_row_count: Notificaciones rows the pull observed.
        stage_failures: One line per stage that did not complete, so a partial
            run reports which part failed instead of reading as a whole one.
    """

    pairs: list[FiledHistoryPairOutcomePayload]
    pair_count: int
    profile_expected_count: int
    register_options_only_count: int
    refused_count: int
    empty_count: int
    captured_count: int
    reached_count: int
    scoping_signal: str
    denominator_note: str
    iva_wallet_status: str
    iva_wallet_divergence: str | None = None
    iva_wallet_blocked: bool = False
    notificaciones_status: str
    notificaciones_row_count: int = 0
    stage_failures: list[str] = []


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
    dry_run: bool = False
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
# read-only IVA compensation reports. Each graph-declared schema below mirrors
# the dict payload emitted at the corresponding call site in
# ``_app_live.py``; tuple-typed report fields are flattened to ``list``
# because :func:`model_dump` serialises tuples as JSON arrays and
# :class:`OutputSchema`'s strict re-validation does not coerce
# ``list`` back to ``tuple``.


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

    certificado_id: AeatCertificadoId
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


class NotificationsListResult(OutputSchema):
    """Typed listing of persisted DEHu notification snapshots.

    ``rows`` contains :class:`NotificationSnapshotListingPayload` summaries
    returned by :class:`NotificationsService` ``list_snapshots``; message
    detail stays on :class:`NotificationsViewResult`.
    """

    bucket_id: BucketId
    count: int = Field(ge=0)
    rows: list[NotificationSnapshotListingPayload]


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


class SancionReadingPayload(OutputSchema):
    """JSON projection of one :class:`SancionLiquidacion` reading.

    Every amount is the figure PRINTED on the document AEAT served, carried as
    a string so the persisted ``Decimal`` scale survives the wire exactly —
    ``774.29`` and ``774.290`` are different printings and JSON's float would
    lose the difference. Nothing here is computed by this application, and an
    absent reducción stays ``None`` rather than becoming ``"0"``, because a
    reducción AEAT did not grant is not a reducción it granted at zero.
    """

    certificado_id: AeatCertificadoId
    clave_liquidacion: AeatClaveLiquidacion
    referencia: str
    nif: str
    objeto_tributario: str
    base_sancion: str
    porcentaje_minimo: str
    sancion_resultante: str
    reduccion_conformidad: str | None
    reduccion_pronto_pago: str | None
    diferencia: str | None
    importe_a_ingresar: str
    document_sha256: ContentDigest


class NotificationDocumentPayload(OutputSchema):
    """Shared projection of one stored :class:`NotificationDocumentRecord`.

    The bytes themselves never appear here and never will: they live in the
    encrypted attachment store, and this payload carries their content address
    and digest so an operator can tie a reading back to the exact custody bytes
    without the document leaving secure storage.

    ``sancion`` and ``parse_refusal`` are mutually exclusive by construction —
    the reader either vouched for a reading or refused to — and the refusal is
    reported as primary result data rather than smuggled into a bespoke
    advisory field, with the operator-facing diagnostic riding the envelope's
    ``notices`` channel.
    """

    bucket_id: BucketId
    certificado_id: AeatCertificadoId
    attachment_id: ContentDigest
    document_sha256: ContentDigest
    byte_size: int = Field(ge=1)
    source_url: str = Field(min_length=1)
    fetched_at: datetime
    sancion_parsed: bool
    sancion: SancionReadingPayload | None = None
    parse_refusal: str | None = Field(default=None, min_length=1, max_length=512)
    mode: Literal["read"] = "read"

    @model_validator(mode="after")
    def _a_reading_is_present_or_refused_never_both_nor_neither(self) -> NotificationDocumentPayload:
        """Keep the reading flag honest against the two fields it summarises.

        A payload claiming ``sancion_parsed`` with no reading, or reporting
        neither a reading nor a reason, would let an operator conclude the
        document held no figures when the truth is that nobody looked.
        """
        if self.sancion_parsed != (self.sancion is not None):
            raise ValueError("sancion_parsed must agree with the presence of a sancion reading")
        if (self.sancion is None) == (self.parse_refusal is None):
            raise ValueError("a stored document carries either a sancion reading or the reason there is none")
        return self


class NotificationDocumentPullResult(NotificationDocumentPayload):
    """Typed result for one guarded notification-document fetch.

    ``already_in_custody`` is the idempotency outcome: a retry against a
    certificado already held stores nothing and returns the row that was there,
    which is otherwise indistinguishable from a first store. It is result data
    rather than a diagnostic — the matching operator-facing advisory rides the
    envelope's ``notices`` channel — and an agent routing on retries needs the
    field, not the prose.
    """

    already_in_custody: bool


class NotificationDocumentViewResult(NotificationDocumentPayload):
    """Typed read-back of one stored notification document.

    Resolved entirely from bucket-local encrypted custody through
    :class:`NotificationDocumentService`. The verb that emits this contacts
    AEAT not at all, so it can never be the act that serves a notification.
    """


class NotificationDocumentHistoryEntry(OutputSchema):
    """One parsed document in custody, with only its own reported figures."""

    certificado_id: AeatCertificadoId
    fetched_at: datetime
    sancion: SancionReadingPayload


class NotificationDocumentHistoryResult(OutputSchema):
    """Parsed notification documents held by this profile, without a total."""

    bucket_id: BucketId
    count: int = Field(ge=0)
    documents: list[NotificationDocumentHistoryEntry]


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


class PortalsListResult(OutputSchema):
    """Typed local-catalogue result for ``aeat app live portals list``.

    Rows are selected from :data:`PORTAL_REGISTRY` directly or through
    :func:`portals_by_category` / :func:`portals_for_modelo`, then projected as
    :class:`PortalEntryPayload`; the command never opens a browser or contacts
    AEAT.
    """

    count: int
    rows: list[PortalEntryPayload]


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
    expediente_id: AeatExpedienteId
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

    snapshot_id: SnapshotId
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


class ExpedientesCaptureResult(OutputSchema):
    """Typed result for one or more persisted expedientes pulls.

    ``mode`` distinguishes a single-modelo capture from a bulk year-range
    capture. Successful :class:`PersistedExpedientesSnapshot` records are
    persisted by :class:`ExpedientesService`; failed modelo/year pairs are
    reported as :class:`ExpedientesCaptureFailurePayload` rows without inventing
    declaration data.
    """

    mode: Literal["single", "bulk"] = "single"
    bucket_id: BucketId
    snapshot_id: SnapshotId | None = None
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


class ExpedientesListResult(OutputSchema):
    """Typed listing of persisted expedientes snapshots.

    ``rows`` is the compact :class:`ExpedienteSnapshotSummaryPayload`
    projection returned by :class:`ExpedientesService` ``list_snapshots``; use
    :class:`ExpedientesViewResult` for per-declaration detail.
    """

    bucket_id: BucketId
    count: int
    rows: list[ExpedienteSnapshotSummaryPayload]


class ExpedientesViewResult(OutputSchema):
    """Typed detail view for one persisted expedientes snapshot.

    The command resolves a stored :class:`PersistedExpedientesSnapshot` through
    :class:`ExpedientesService` and projects each declaration into
    :class:`ExpedienteDeclarationPayload`.
    """

    bucket_id: BucketId
    snapshot_id: SnapshotId
    captured_at: str
    source_url: str
    declaration_count: int
    declarations: list[ExpedienteDeclarationPayload]


class ExpedientesLatestResult(OutputSchema):
    """Typed newest-snapshot response for expedientes.

    ``snapshot_id`` is ``None`` when the bucket has no captured expedientes
    snapshot from :class:`ExpedientesService`; in that case every
    :class:`PersistedExpedientesSnapshot`-derived field is also ``None`` to keep
    the payload shape stable for JSON clients.
    """

    bucket_id: BucketId
    snapshot_id: SnapshotId | None
    captured_at: str | None = None
    source_url: str | None = None
    declaration_count: int | None = None


# ---------------------------------------------------------------------------
# Deudas leaves (AEAT-reported liabilities, read and display only)
# ---------------------------------------------------------------------------


class DeudaRowPayload(OutputSchema):
    """One AEAT-reported liability inside a deudas-view payload.

    Mirrors :class:`Deuda` rows persisted in a
    :class:`PersistedDeudasSnapshot`. Every field reports what AEAT's debts
    consulta stated; nothing here is computed by this application, and nothing
    here is an input to any modelo casilla.

    ``importe_pendiente`` is a non-negative magnitude carried as a string so
    the JSON payload preserves the persisted ``Decimal`` scale exactly.
    Direction lives on ``direccion``, never in the sign of the amount.
    """

    clave_liquidacion: AeatClaveLiquidacion
    objeto_tributario: str
    importe_pendiente: str
    direccion: str
    periodo: str | None
    situacion: str
    mode: str


class DeudaSnapshotSummaryPayload(OutputSchema):
    """Summary row for one persisted deudas snapshot.

    Used by :class:`DeudasListResult` for rows returned from
    :class:`DeudasService`; full :class:`DeudaRowPayload` detail remains on
    :class:`DeudasViewResult`.
    """

    snapshot_id: SnapshotId
    captured_at: str
    source_url: str
    deuda_count: int


class DeudasListResult(OutputSchema):
    """Typed listing of persisted deudas snapshots.

    ``rows`` is the compact :class:`DeudaSnapshotSummaryPayload` projection
    returned by :class:`DeudasService` ``list_snapshots``; use
    :class:`DeudasViewResult` for per-liability detail.
    """

    bucket_id: BucketId
    count: int
    rows: list[DeudaSnapshotSummaryPayload]


class DeudasViewResult(OutputSchema):
    """Typed detail view for one persisted deudas snapshot.

    The command resolves a stored :class:`PersistedDeudasSnapshot` through
    :class:`DeudasService` and projects each liability into
    :class:`DeudaRowPayload`.
    """

    bucket_id: BucketId
    snapshot_id: SnapshotId
    captured_at: str
    source_url: str
    deuda_count: int
    deudas: list[DeudaRowPayload]


class DeudasLatestResult(OutputSchema):
    """Typed newest-snapshot response for deudas.

    ``snapshot_id`` is ``None`` when the bucket has no captured deudas
    snapshot from :class:`DeudasService`; in that case every
    :class:`PersistedDeudasSnapshot`-derived field is also ``None`` to keep the
    payload shape stable for JSON clients. An empty register is reported as
    empty rather than triggering a live AEAT read.
    """

    bucket_id: BucketId
    snapshot_id: SnapshotId | None
    captured_at: str | None = None
    source_url: str | None = None
    deuda_count: int | None = None


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

    bucket_id: BucketId
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
    snapshot_id: SnapshotId
    modelo: Modelo
    filing_year: int = Field(ge=1900, le=9999)
    period: JustificantePeriodToken
    expediente_id: AeatExpedienteId
    csv: AeatCsv
    pdf_sha256: ContentDigest
    source_kind: ObservationSourceKind
    state: SnapshotLifecycleState
    captured_at: datetime
    justificante_metadata_registered: bool
    calendar_evidence_available: bool
    modelo_filing_record_required: bool
    filing_evidence_stamped: bool
    filing_record_id: FilingRecordId | None = None


class JustificanteSnapshotSummaryPayload(OutputSchema):
    """Summary projection of one :class:`JustificanteCaptureSnapshot`.

    Used by :class:`JustificanteListResult` for active snapshots returned from
    :class:`JustificanteCaptureSnapshotService`.
    """

    snapshot_id: SnapshotId
    modelo: Modelo
    filing_year: int = Field(ge=1900, le=9999)
    period: JustificantePeriodToken
    pdf_sha256: ContentDigest
    state: SnapshotLifecycleState
    captured_at: datetime


class JustificanteListResult(OutputSchema):
    """List result from :class:`JustificanteCaptureSnapshotService`.

    ``rows`` contains :class:`JustificanteSnapshotSummaryPayload` projections
    for active :class:`JustificanteCaptureSnapshot` records in the active
    bucket, ordered by capture time and carrying the period token,
    :class:`SnapshotLifecycleState`, and raw-PDF hash needed to identify the
    official receipt without exposing the encrypted PDF bytes.
    """

    bucket_id: BucketId
    count: int
    rows: list[JustificanteSnapshotSummaryPayload]


class JustificanteViewResult(OutputSchema):
    """Detail view for one persisted :class:`JustificanteCaptureSnapshot`.

    The view resolves through :class:`JustificanteCaptureSnapshotService` and
    surfaces the AEAT expediente, CSV, official ``source_kind``,
    :class:`SnapshotLifecycleState`, and ``pdf_sha256`` so operators can
    reconcile the local evidence chain without printing the stored receipt body.
    """

    bucket_id: BucketId
    snapshot_id: SnapshotId
    modelo: Modelo
    filing_year: int = Field(ge=1900, le=9999)
    period: JustificantePeriodToken
    expediente_id: AeatExpedienteId
    csv: AeatCsv
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


class VerifyListResult(OutputSchema):
    """Typed listing of persisted NIF verification observations.

    ``rows`` contains :class:`VerifyObservationSummaryPayload` projections read
    through :class:`VerifyService`; the command does not contact AEAT.
    """

    bucket_id: BucketId
    count: int
    rows: list[VerifyObservationSummaryPayload]


class VerifyViewResult(VerifyObservationPayload):
    """Typed detail view for one persisted :class:`VerifyObservation`.

    The inherited :class:`VerifyObservationPayload` fields are resolved through
    :class:`VerifyService` storage, not by performing a fresh live check.
    """


class VerifyLatestResult(OutputSchema):
    """Typed newest-observation response for one surface/NIF pair.

    ``observation_id`` is ``None`` when :class:`VerifyService` finds no
    :class:`VerifyObservation` matching the requested (:class:`VerifySurface`,
    NIF) pair; ``surface`` and ``nif`` are still populated to identify the
    lookup, and every observation-derived field is ``None``.
    """

    bucket_id: BucketId
    observation_id: str | None
    surface: str
    nif: str
    verdict: str | None = None
    expected: str | None = None
    matched_expectation: bool | None = None
    checked_at: str | None = None


class VerifyNifIvaResult(VerifyObservationPayload):
    """Typed result for an IXVI NIF-IVA live-read observation.

    The command persists the read-only AEAT verdict through
    :class:`VerifyService` before emitting the inherited
    :class:`VerifyObservationPayload` fields.
    """


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
    try:
        validate_utc_aware(timestamp)
    except CoreValidationError as exc:
        raise ValueError("must be a UTC timestamp") from exc
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
