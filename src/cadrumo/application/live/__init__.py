"""Application facade for explicit read-only AEAT live workflows.

Every remote navigation path enters through the live-read access gate before it
authenticates or opens an AEAT sede surface. Most surfaces use
:func:`_session.active_verified_session`; IVA remote-state
acquisition enforces the same read gate before coordinating its filed-history and
wallet reads. The package has no live-submit surface: captured notifications,
expedientes, filed declarations, justificantes, IVA wallet rows, Borrador 100
snapshots, and verification checks are local evidence objects, not remote filing
mutations.

Live capture services persist encrypted active-bucket evidence through
:class:`adapters.persistence.storage.SecureObjectRepository` or the
snapshot repositories re-exported by this facade. Parsed filed-declaration
observations are typed as
:class:`domain.calculations.registry.CasillaObservation` rows and routed
through :class:`domain.calculations.registry.ValidatedRegistryAuthority`
to bind them to the correct revision. Justificante capture may stamp the
matching current :class:`domain.modelos.ModeloRecord` with
:class:`domain.modelos.ExternalEvidence` only after the local filing record
already exists.

Snapshot payloads that depend on an authenticated taxpayer carry a normalised
``authenticated_identity`` when the upstream AEAT session exposes it. The
notifications snapshot id includes that identity so captures from different
taxpayers do not collapse to the same local row; expedientes and notifications
calendar projection compares the snapshot identity and row-level taxpayer ids
against the expected active-profile tax id before surfacing observed events.
Persisted capture/enrolment orchestration emits bucket events with sanitized
summary payloads; non-persisting read/list surfaces remain event-free.

IVA remote-state helpers separate stored-evidence reads from live acquisition.
:func:`load_iva_remote_state` returns the local
:class:`IvaRemoteStateStoredEvidenceReport` without
contacting AEAT, while
:func:`capture_iva_remote_state` returns an
:class:`IvaRemoteStateAcquisitionReport`, persists a
redacted :class:`IvaRemoteStateAcquisitionManifest`, and
reports each remote surface independently so partial failures remain explicit.

See Also:
    :func:`enroll_filed_justificante_evidence`
        Filed-history path that persists justificante metadata and stamps
        current filing records with live-capture evidence.
    :class:`SnapshotRepository`
        Bucket-scoped snapshot persistence port the live snapshot services
        depend on; its encrypted secure-object backend lives in the
        persistence adapter.
    :mod:`application.overview`
        Local-only summary surface that reads captured live evidence without
        contacting AEAT and filters calendar events by active-profile identity.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from importlib import import_module
from types import ModuleType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...core import Period
    from ...domain.justificante import Justificante
    from ...domain.modelos import ModeloRecord
    from ._deudas import (
        DeudasCapture,
        DeudasService,
        DeudasSnapshotNotFoundError,
        PersistedDeudasSnapshot,
        deudas_snapshot_object_key,
    )
    from ._expedientes import (
        ExpedientesCapture,
        ExpedientesService,
        PersistedExpedientesSnapshot,
        expedientes_snapshot_object_key,
    )
    from ._filed_history_operation import (
        FILED_HISTORY_OPERATION_DEFINITION_ID as FILED_HISTORY_OPERATION_DEFINITION_ID,
    )
    from ._filed_history_operation import (
        FiledHistoryOperationRequest as FiledHistoryOperationRequest,
    )
    from ._filed_history_operation import (
        build_filed_history_operation_definition as build_filed_history_operation_definition,
    )
    from ._notification_documents import (
        NotificationDocumentCustody,
        NotificationDocumentNotFoundError,
        NotificationDocumentRecord,
        NotificationDocumentService,
        notification_document_object_key,
    )
    from ._notification_ports import NotificationDocumentProtocol
    from ._notifications import (
        NotificationsService,
        PersistedNotificationsSnapshot,
        notifications_snapshot_object_key,
    )
    from ._verify import (
        VerifyObservation,
        VerifyObservationRepository,
        VerifyService,
        VerifySurface,
        VerifyVerdict,
        verify_observation_object_key,
    )

from ...adapters.outbound.aeat.sede import Declaracion as _Declaracion
from ...adapters.outbound.aeat.sede import open_declarations_register as _open_declarations_register
from ...adapters.outbound.aeat.sede import shared_playwright as _shared_playwright
from ...core.resources import resources as _resources
from ...core.time import now as _now
from ._borrador_100 import (
    BORRADOR_100_SNAPSHOT_NAMESPACE,
    Borrador100Snapshot,
    Borrador100SnapshotRepository,
    Borrador100SnapshotService,
    BorradorSnapshotNotFoundError,
    borrador_100_snapshot_object_key,
    derive_borrador_100_snapshot_id,
)
from ._errors import (
    LiveApplicationError,
    LiveApplicationInputError,
    LiveIvaAcquisitionFailureMode,
    LiveIvaSurfaceTimeoutError,
    classify_live_iva_acquisition_failure,
)
from ._filed_data import (
    BulkFiledDataListingReport,
    FiledDataListingReport,
    FiledDataListingRow,
    filed_data_listing_row,
    select_declarations_for_capture,
)
from ._filed_data_capture import (
    ExpectedFiledDeclarationGrid,
    FiledHistoryDiscoveryPair,
    FiledHistoryDiscoveryReport,
    FiledHistoryOnboardingRun,
    FiledHistoryPairOutcome,
    FiledPeriodSelectionRow,
    capture_filed_data,
    capture_filed_data_bulk,
    capture_source_filed_data,
    casillas_a_recapture_would_change,
    classify_register_scoping_signal,
    discover_filed_history,
    expected_but_not_found_notice,
    expected_filed_declaration_grid,
    filed_data_capture_failure_row,
    filed_history_discovery_report,
    filed_period_selection_rows,
    found_more_than_expected_notices,
    list_filed_data,
    list_filed_data_bulk,
    pull_filed_history,
    recapture_divergence_notices,
)
from ._filed_observation_persistence import (
    FILED_JUSTIFICANTE_UNREACHED_NOTICE_CODE,
    FiledJustificanteEnrollmentResult,
    FiledJustificanteMetadataResult,
    FiledJustificanteUnreachedReason,
    enroll_filed_justificante_evidence,
    persist_filed_calculation_observation,
    persist_filed_justificante_metadata,
)
from ._iva_remote_state import (
    IvaRemoteStateAcquisitionManifestRepository,
    build_iva_remote_state_acquisition_report,
    capture_iva_compensation_history,
    capture_iva_compensation_wallet,
    capture_iva_remote_state,
    list_iva_compensation_history,
    list_iva_remote_state_acquisition_manifests,
    load_iva_remote_state,
    load_iva_remote_state_acquisition_manifest,
    persist_and_reconcile_iva_compensation_wallet,
    persist_iva_remote_state_acquisition_report,
)
from ._justificante import (
    JUSTIFICANTE_CAPTURE_SNAPSHOT_NAMESPACE,
    JUSTIFICANTE_CAPTURE_SOURCE_KIND,
    JustificanteCaptureSnapshot,
    JustificanteCaptureSnapshotNotFoundError,
    JustificanteCaptureSnapshotRepository,
    JustificanteCaptureSnapshotService,
    derive_justificante_capture_snapshot_id,
    justificante_capture_snapshot_object_key,
    parse_capture_to_justificante,
    reconcile_capture,
    register_capture_as_filing_evidence,
    register_capture_justificante_metadata,
    resolve_period_expediente,
    stamp_capture_evidence_if_filed,
)
from ._remote_state_models import (
    BulkFiledDataCaptureReport,
    ExpedientesBulkCaptureFailureRow,
    ExpedientesBulkCaptureReport,
    FiledCasillaSkipRow,
    FiledDataCaptureFailureRow,
    FiledDataCaptureReport,
    IvaCompensationCarryForwardLotRow,
    IvaCompensationHistoryCaptureReport,
    IvaCompensationHistoryReport,
    IvaCompensationHistoryRow,
    IvaRemoteStateAcquisitionManifest,
    IvaRemoteStateAcquisitionReport,
    IvaRemoteStateAcquisitionSurfaceManifest,
    IvaRemoteStateStoredEvidenceReport,
    IvaWalletAuthorityDecisionRow,
    IvaWalletCaptureReport,
    LiveIvaAuthOutcome,
    LiveIvaReadOutcome,
    LiveIvaReadStatus,
    LiveIvaReadSurface,
    SourceFiledDataCaptureReport,
    StoredIvaRemoteStateAcquisitionRow,
    StoredIvaWalletObservationRow,
)
from ._remote_state_outcomes import bounded_context_text as _bounded_context_text
from ._session import active_verified_session as _active_verified_session
from ._snapshot_base import (
    SnapshotLifecycleState,
    SnapshotNotFoundError,
    SnapshotRepository,
    SnapshotStateFilter,
)

LIVE_EXPEDIENTES_READ_OPERATION = "live-expedientes-read"


@dataclass(frozen=True, slots=True)
class JustificanteCaptureOutcome:
    """Outcome of one live justificante pull and local filing-evidence enrolment.

    The :class:`JustificanteCaptureSnapshot` is always the persisted live
    evidence. ``justificante`` is populated only when the PDF parsed into domain
    metadata, and ``filing_record`` is populated only when an existing current
    :class:`domain.modelos.ModeloRecord` could be stamped with live
    :class:`domain.modelos.ExternalEvidence`.
    """

    snapshot: JustificanteCaptureSnapshot
    justificante: Justificante | None
    filing_record: ModeloRecord | None

    @property
    def justificante_metadata_registered(self) -> bool:
        """Return whether the captured receipt parsed into stored justificante metadata."""
        return self.justificante is not None

    @property
    def filing_evidence_stamped(self) -> bool:
        """Return whether the live receipt is locked to a local filing record."""
        return self.filing_record is not None

    @property
    def filing_record_id(self) -> str | None:
        """Return the stamped local filing record id, when one was found."""
        return self.filing_record.filing_record_id if self.filing_record is not None else None


async def capture_expedientes(*, bucket_id: str, modelo: str, year: int):
    """Live-walk the AEAT declaration register and persist a bucket-scoped snapshot.

    Uses ``walk_declarations_register`` (the same register adapter the
    filed-data list/capture verbs drive), wraps the typed declarations
    in an :class:`ExpedientesCapture`, and persists through
    :class:`ExpedientesService` against the active bucket. The helper obtains
    its session via :func:`_session.active_verified_session`,
    so the read access gate is enforced before any remote contact.
    """
    from ._expedientes import ExpedientesCapture, ExpedientesService

    session, settings = await _active_verified_session(operation=LIVE_EXPEDIENTES_READ_OPERATION)
    async with (
        _shared_playwright(session) as playwright,
        _open_declarations_register(session, settings=settings, playwright=playwright) as register,
    ):
        declarations = await register.walk(modelo=modelo, ejercicio=year)
    capture = ExpedientesCapture(
        declarations=tuple(declarations),
        captured_at=_now(),
        source_url=f"declarations:modelo={modelo}:ejercicio={year}",
        authenticated_identity=session.identity_nif,
    )
    persisted = ExpedientesService(settings=settings).capture(bucket_id=bucket_id, capture=capture)
    return persisted


async def capture_expedientes_bulk(
    *,
    bucket_id: str,
    year_from: int,
    year_to: int,
    modelos: tuple[str, ...] | None = None,
) -> ExpedientesBulkCaptureReport:
    """Live-walk AEAT declaration-register rows and return an :class:`ExpedientesBulkCaptureReport`."""
    if year_from > year_to:
        raise LiveApplicationInputError(
            message="from-year must be less than or equal to to-year",
            translated_message="live.errors.year_range_invalid",
        )

    from ._expedientes import ExpedientesCapture, ExpedientesService

    resolved_modelos = modelos if modelos is not None else tuple(str(m.id) for m in _resources().modelos.all())
    session, settings = await _active_verified_session(operation=LIVE_EXPEDIENTES_READ_OPERATION)
    service = ExpedientesService(settings=settings)
    snapshot_ids: list[str] = []
    failures: list[ExpedientesBulkCaptureFailureRow] = []
    declarations_for_snapshot: list[_Declaracion] = []
    successful_query_count = 0

    async with (
        _shared_playwright(session) as playwright,
        _open_declarations_register(session, settings=settings, playwright=playwright) as register,
    ):
        for code in resolved_modelos:
            for year in range(year_to, year_from - 1, -1):
                try:
                    declarations = await register.walk(modelo=code, ejercicio=year)
                except Exception as exc:
                    failures.append(
                        ExpedientesBulkCaptureFailureRow(
                            modelo=code,
                            year=year,
                            error_type=exc.__class__.__name__,
                            message=_bounded_context_text(exc),
                        ),
                    )
                    continue
                successful_query_count += 1
                declarations_for_snapshot.extend(declarations)

    if successful_query_count:
        capture = ExpedientesCapture(
            declarations=tuple(declarations_for_snapshot),
            captured_at=_now(),
            source_url=(f"declarations:bulk:modelos={','.join(resolved_modelos)}:ejercicios={year_from}-{year_to}"),
            authenticated_identity=session.identity_nif,
        )
        persisted = service.capture(bucket_id=bucket_id, capture=capture)
        snapshot_ids.append(persisted.snapshot_id)

    return ExpedientesBulkCaptureReport(
        bucket_id=bucket_id,
        modelos=tuple(resolved_modelos),
        year_from=year_from,
        year_to=year_to,
        captured_snapshot_count=len(snapshot_ids),
        declaration_count=len(declarations_for_snapshot),
        snapshot_ids=tuple(snapshot_ids),
        failures=tuple(failures),
    )


async def capture_notifications(*, bucket_id: str):
    """Live-fetch DEHú notifications and persist a bucket-scoped snapshot.

    The flow is:

    1. ``_AeatAccessGate.require_live_read()`` — keeps pytest live
       reads behind the live-test opt-in while allowing operator reads
       to continue to auth/profile/read-only guards.
    2. ``_ensure_authenticated_aeat_session(operation="live-notifications-read")``
       — acquires or refreshes the authenticated session
       (e.g. triggers a Cl@ve Móvil push).
    3. ``fetch_notifications_query`` — drives Playwright against the
       authenticated DEHú surface and parses the HTML response.
    4. :class:`NotificationsService.capture` — persists the typed
       snapshot in the active bucket under the
       ``cadrumo.application.live.notifications`` namespace.
    5. Bucket event ``live.notifications.snapshot_captured`` is
       emitted by the caller through the standard bucket-event
       repository so this function stays unit-testable against
       a stubbed snapshot.

    Args:
        bucket_id: The active profile bucket id the notification snapshot
            is scoped to.

    Returns:
        A tuple of (snapshot_id, fetched_row_count, persisted_at).
    """
    from ...adapters.outbound.aeat.sede import fetch_notifications_query
    from ._notifications import NotificationsService

    session, settings = await _active_verified_session()
    snapshot = await fetch_notifications_query(session, settings=settings)
    persisted = NotificationsService(settings=settings).capture(
        bucket_id=bucket_id,
        snapshot=snapshot,
        authenticated_identity=session.identity_nif,
    )
    return persisted


def resolve_notification_row(*, bucket_id: str, certificado_id: str):
    """Find one notification row by certificado across the bucket's stored snapshots.

    The document fetch needs the ROW, not just the id, because the row carries
    the ``leida`` fact the comparecencia guard turns on. Resolving it from a
    locally-captured snapshot rather than accepting operator-supplied flags is
    deliberate: the guard must key on what AEAT reported, and a caller-supplied
    "yes it is read" would be exactly the override that makes an agent serve a
    notification on the taxpayer's behalf.

    The newest snapshot mentioning the certificado wins, so a re-pull that
    observed the row becoming read is the reading that governs.

    Args:
        bucket_id: The active profile bucket to search.
        certificado_id: AEAT's número de certificado for the notification.

    Returns:
        The most recently captured matching
        :class:`~adapters.outbound.aeat.sede.RemoteNotification`.

    Raises:
        LiveApplicationInputError: When no captured snapshot mentions the
            certificado. The refusal names the pull that would fix it rather
            than reaching for AEAT on the operator's behalf.
    """
    from ._errors import LiveApplicationInputError
    from ._notifications import NotificationsService

    wanted = certificado_id.strip()
    snapshots = sorted(
        NotificationsService().list_snapshots(bucket_id=bucket_id),
        key=lambda snapshot: snapshot.captured_at,
        reverse=True,
    )
    for snapshot in snapshots:
        for row in snapshot.rows:
            if str(row.certificado_id) == wanted:
                return row
    raise LiveApplicationInputError(
        translated_message="application.live.notifications.errors.certificado_not_in_any_snapshot",
        context={"certificado_id": wanted, "snapshots_searched": str(len(snapshots))},
    )


async def pull_notification_document(
    *,
    bucket_id: str,
    certificado_id: str,
    service: NotificationDocumentService,
):
    """Fetch one already-read notification's document and take encrypted custody.

    The one application-layer door onto a notification's content. It gates
    through ``_active_verified_session`` exactly as the other live reads do,
    resolves the row locally so the comparecencia guard keys on AEAT's own
    ``leida`` report, and hands off to
    :class:`NotificationDocumentService`, which refuses anything AEAT does not
    already record as read before a request is issued.

    Args:
        bucket_id: The active profile bucket taking custody.
        certificado_id: AEAT's número de certificado for the notification.
        service: Composed notification-document use case supplied by the
            entrypoint.

    Returns:
        The ``NotificationDocumentCustody`` outcome: the persisted record, and
        whether the certificado was already held so the store was a no-op.

    Raises:
        SedeNavigationError: When the notification is not already read.
        LiveApplicationInputError: When no captured snapshot mentions it.
    """
    row = resolve_notification_row(bucket_id=bucket_id, certificado_id=certificado_id)
    session, _settings = await _active_verified_session()
    return await service.pull_document(
        bucket_id=bucket_id,
        session=session,
        row=row,
    )


#: Operation label forwarded to the auth service for the censal read, so a
#: provider prompt (a Cl@ve Móvil push) names the surface it is unlocking.
LIVE_CENSAL_READ_OPERATION = "live-censal-read"


async def pull_censal_datos():
    """Read the authenticated taxpayer's censal state from AEAT's consulta.

    AEAT publishes the taxpayer's own censal state at *Mis Datos
    Censales*, and this is the one application-layer door onto it. The
    flow gates through ``_active_verified_session`` (the
    ``require_live_read`` + authenticated-session boundary), navigates to
    the consulta view, and parses the rendered DOM. It never submits a
    form, and the reader refuses at runtime if AEAT lands it on a censal
    modification surface — the write sibling is one link away from the
    page it reads, which is why reading the DOM is the whole of what this
    door can do.

    It persists nothing and decides nothing. Projecting the read onto
    profile paths, splitting it against what the operator already
    declared, and committing the result belong to
    :func:`~cadrumo.application.user_profile.censal_facts_from_read`,
    :func:`~cadrumo.application.user_profile.reconcile_censal_read`, and
    :func:`~cadrumo.application.user_profile.apply_censal_read`, the last
    routing through the single cotejo apply authority. Keeping
    acquisition apart from adoption is what lets an operator preview a
    read without writing anything.

    The taxpayer read is always the authenticated session's own identity:
    the product does not support acting as a representative, so the NIF
    comes off the session rather than from a parameter a caller could
    point at a third party.

    Returns:
        The parsed application-owned censal observation. Nothing is persisted; the
        caller decides what to adopt.
    """
    from ...adapters.outbound.aeat.sede import fetch_censal_datos

    session, settings = await _active_verified_session(operation=LIVE_CENSAL_READ_OPERATION)
    return await fetch_censal_datos(session, taxpayer_nif=session.identity_nif, settings=settings)


async def capture_justificante_snapshot(
    *,
    bucket_id: str,
    modelo: str,
    year: int,
    period: Period,
) -> JustificanteCaptureSnapshot:
    """Live-pull the AEAT justificante for one work unit and persist it.

    The flow gates entry through ``_active_verified_session`` (the
    ``require_live_read`` + authenticated-session boundary), resolves the
    period-correct expediente by cross-referencing the period-bearing
    declarations register against the procedure tree
    (:func:`resolve_period_expediente`), pulls the signed PDF via
    ``capture_justificante``, and persists it through
    :class:`JustificanteCaptureSnapshotService` under the active bucket.

    Returns:
        The persisted :class:`JustificanteCaptureSnapshot`.
    """
    outcome = await capture_justificante_snapshot_outcome(
        bucket_id=bucket_id,
        modelo=modelo,
        year=year,
        period=period,
    )
    return outcome.snapshot


async def capture_justificante_snapshot_outcome(
    *,
    bucket_id: str,
    modelo: str,
    year: int,
    period: Period,
) -> JustificanteCaptureOutcome:
    """Live-pull one AEAT justificante and report local filing-evidence enrolment.

    The persisted :class:`JustificanteCaptureSnapshot` is the durable evidence.
    Metadata registration and current-record evidence stamping are best-effort
    follow-up steps reported separately in :class:`JustificanteCaptureOutcome`.
    A missing local filing record does not discard the captured receipt.

    Returns:
        A :class:`JustificanteCaptureOutcome` with the capture and enrolment result.
    """
    from ...adapters.outbound.aeat.sede import capture_justificante, walk_expedientes_tree

    session, settings = await _active_verified_session(operation="live-justificante-read")
    async with (
        _shared_playwright(session) as playwright,
        _open_declarations_register(session, settings=settings, playwright=playwright) as register,
    ):
        declarations = tuple(await register.walk(modelo=modelo, ejercicio=year))
    expedientes = await walk_expedientes_tree(session, modelo=modelo, settings=settings)
    expediente = resolve_period_expediente(
        declarations=declarations,
        expedientes=expedientes,
        modelo=modelo,
        period=period,
    )
    capture = await capture_justificante(session, expediente, settings=settings)
    persisted = JustificanteCaptureSnapshotService(bucket_id=bucket_id).capture(
        modelo=modelo,
        filing_year=year,
        period=period,
        expediente_id=capture.expediente.expediente_id,
        csv=capture.ref.csv,
        pdf_bytes=capture.pdf_bytes,
        pdf_sha256=capture.pdf_sha256,
        captured_at=_now(),
    )
    # The capture flow stamps the official evidence onto the work unit's
    # filing record in the same flow. Best-effort: a no-op when the period
    # is not yet filed in-app (the snapshot is still persisted).
    justificante = register_capture_justificante_metadata(snapshot=persisted)
    filing_record = stamp_capture_evidence_if_filed(persisted)
    return JustificanteCaptureOutcome(snapshot=persisted, justificante=justificante, filing_record=filing_record)


#: Re-exported name -> owning module. This literal is the canonical lazy-facade
#: manifest: every name previously handled by the resolution ladder is listed
#: exactly once, alongside the filed-history operation contract.
_LAZY_EXPORTS: dict[str, str] = {
    "DeudasCapture": "._deudas",
    "DeudasService": "._deudas",
    "DeudasSnapshotNotFoundError": "._deudas",
    "PersistedDeudasSnapshot": "._deudas",
    "deudas_snapshot_object_key": "._deudas",
    "ExpedientesCapture": "._expedientes",
    "ExpedientesService": "._expedientes",
    "PersistedExpedientesSnapshot": "._expedientes",
    "expedientes_snapshot_object_key": "._expedientes",
    "FILED_HISTORY_OPERATION_DEFINITION_ID": "._filed_history_operation",
    "FiledHistoryOperationRequest": "._filed_history_operation",
    "build_filed_history_operation_definition": "._filed_history_operation",
    "build_filed_history_operation_registration": "._filed_history_operation",
    "NotificationDocumentCustody": "._notification_documents",
    "NotificationDocumentNotFoundError": "._notification_documents",
    "NotificationDocumentRecord": "._notification_documents",
    "NotificationDocumentService": "._notification_documents",
    "notification_document_object_key": "._notification_documents",
    "NotificationDocumentProtocol": "._notification_ports",
    "NotificationsService": "._notifications",
    "PersistedNotificationsSnapshot": "._notifications",
    "notifications_snapshot_object_key": "._notifications",
    "VerifyObservation": "._verify",
    "VerifyObservationRepository": "._verify",
    "VerifyService": "._verify",
    "VerifySurface": "._verify",
    "VerifyVerdict": "._verify",
    "verify_observation_object_key": "._verify",
}

_LAZY_MODULE_LOADERS: dict[str, Callable[[], ModuleType]] = {
    module_path: partial(import_module, module_path, __name__) for module_path in frozenset(_LAZY_EXPORTS.values())
}


def __getattr__(name: str):
    """Lazy-load the heavy service classes and operation contract exports."""
    module_path = _LAZY_EXPORTS.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    loader = _LAZY_MODULE_LOADERS.get(module_path)
    if loader is None:
        raise RuntimeError(f"missing lazy loader for {module_path!r}")
    value = getattr(loader(), name)
    globals()[name] = value
    return value


__all__ = [
    "BORRADOR_100_SNAPSHOT_NAMESPACE",
    "FILED_HISTORY_OPERATION_DEFINITION_ID",
    "FILED_JUSTIFICANTE_UNREACHED_NOTICE_CODE",
    "JUSTIFICANTE_CAPTURE_SNAPSHOT_NAMESPACE",
    "JUSTIFICANTE_CAPTURE_SOURCE_KIND",
    "LIVE_CENSAL_READ_OPERATION",
    "LIVE_EXPEDIENTES_READ_OPERATION",
    "Borrador100Snapshot",
    "Borrador100SnapshotRepository",
    "Borrador100SnapshotService",
    "BorradorSnapshotNotFoundError",
    "BulkFiledDataCaptureReport",
    "BulkFiledDataListingReport",
    "DeudasCapture",
    "DeudasService",
    "DeudasSnapshotNotFoundError",
    "ExpectedFiledDeclarationGrid",
    "ExpedientesBulkCaptureFailureRow",
    "ExpedientesBulkCaptureReport",
    "ExpedientesCapture",
    "ExpedientesService",
    "FiledCasillaSkipRow",
    "FiledDataCaptureFailureRow",
    "FiledDataCaptureReport",
    "FiledDataListingReport",
    "FiledDataListingRow",
    "FiledHistoryDiscoveryPair",
    "FiledHistoryDiscoveryReport",
    "FiledHistoryOnboardingRun",
    "FiledHistoryOperationRequest",
    "FiledHistoryPairOutcome",
    "FiledJustificanteEnrollmentResult",
    "FiledJustificanteMetadataResult",
    "FiledJustificanteUnreachedReason",
    "FiledPeriodSelectionRow",
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
    "JustificanteCaptureOutcome",
    "JustificanteCaptureSnapshot",
    "JustificanteCaptureSnapshotNotFoundError",
    "JustificanteCaptureSnapshotRepository",
    "JustificanteCaptureSnapshotService",
    "LiveApplicationError",
    "LiveApplicationInputError",
    "LiveIvaAcquisitionFailureMode",
    "LiveIvaAuthOutcome",
    "LiveIvaReadOutcome",
    "LiveIvaReadStatus",
    "LiveIvaReadSurface",
    "LiveIvaSurfaceTimeoutError",
    "NotificationDocumentCustody",
    "NotificationDocumentNotFoundError",
    "NotificationDocumentProtocol",
    "NotificationDocumentRecord",
    "NotificationDocumentService",
    "NotificationsService",
    "PersistedDeudasSnapshot",
    "PersistedExpedientesSnapshot",
    "PersistedNotificationsSnapshot",
    "SnapshotLifecycleState",
    "SnapshotNotFoundError",
    "SnapshotRepository",
    "SnapshotStateFilter",
    "SourceFiledDataCaptureReport",
    "StoredIvaRemoteStateAcquisitionRow",
    "StoredIvaWalletObservationRow",
    "VerifyObservation",
    "VerifyObservationRepository",
    "VerifyService",
    "VerifySurface",
    "VerifyVerdict",
    "borrador_100_snapshot_object_key",
    "build_filed_history_operation_definition",
    "build_filed_history_operation_registration",
    "build_iva_remote_state_acquisition_report",
    "capture_expedientes_bulk",
    "capture_filed_data",
    "capture_filed_data_bulk",
    "capture_iva_compensation_history",
    "capture_iva_compensation_wallet",
    "capture_iva_remote_state",
    "capture_justificante_snapshot",
    "capture_justificante_snapshot_outcome",
    "capture_notifications",
    "capture_source_filed_data",
    "casillas_a_recapture_would_change",
    "classify_live_iva_acquisition_failure",
    "classify_register_scoping_signal",
    "derive_borrador_100_snapshot_id",
    "derive_justificante_capture_snapshot_id",
    "deudas_snapshot_object_key",
    "discover_filed_history",
    "enroll_filed_justificante_evidence",
    "expected_but_not_found_notice",
    "expected_filed_declaration_grid",
    "expedientes_snapshot_object_key",
    "filed_data_capture_failure_row",
    "filed_data_listing_row",
    "filed_history_discovery_report",
    "filed_period_selection_rows",
    "found_more_than_expected_notices",
    "justificante_capture_snapshot_object_key",
    "list_filed_data",
    "list_filed_data_bulk",
    "list_iva_compensation_history",
    "list_iva_remote_state_acquisition_manifests",
    "load_iva_remote_state",
    "load_iva_remote_state_acquisition_manifest",
    "notification_document_object_key",
    "notifications_snapshot_object_key",
    "parse_capture_to_justificante",
    "persist_and_reconcile_iva_compensation_wallet",
    "persist_filed_calculation_observation",
    "persist_filed_justificante_metadata",
    "persist_iva_remote_state_acquisition_report",
    "pull_censal_datos",
    "pull_filed_history",
    "pull_notification_document",
    "recapture_divergence_notices",
    "reconcile_capture",
    "register_capture_as_filing_evidence",
    "register_capture_justificante_metadata",
    "resolve_notification_row",
    "resolve_period_expediente",
    "select_declarations_for_capture",
    "stamp_capture_evidence_if_filed",
    "verify_observation_object_key",
]
