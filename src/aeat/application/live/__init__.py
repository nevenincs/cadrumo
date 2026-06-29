"""Application facade for explicit read-only AEAT live workflows.

Every remote navigation path enters through the live-read access gate before it
authenticates or opens an AEAT sede surface. Most surfaces use
:func:`~aeat.application.live._session.active_verified_session`; IVA remote-state
acquisition enforces the same read gate before coordinating its filed-history and
wallet reads. The package has no live-submit surface: captured notifications,
expedientes, filed declarations, justificantes, IVA wallet rows, Borrador 100
snapshots, and verification checks are local evidence objects, not remote filing
mutations.

Live capture services persist encrypted active-bucket evidence through
:class:`~aeat.adapters.persistence.storage.sql.SecureObjectRepository` or the
snapshot repositories re-exported by this facade. Parsed filed-declaration
observations are typed as
:class:`~aeat.domain.calculations.registry.CasillaObservation` rows and routed
through :class:`~aeat.domain.calculations.registry.ValidatedRegistryAuthority`
to bind them to the correct revision. Justificante capture may stamp the
matching current :class:`~aeat.domain.modelos.ModeloRecord` with
:class:`~aeat.domain.modelos.ExternalEvidence` only after the local filing record
already exists.

IVA remote-state helpers separate stored-evidence reads from live acquisition.
:func:`~aeat.application.live.load_iva_remote_state` returns the local
:class:`~aeat.application.live.IvaRemoteStateStoredEvidenceReport` without
contacting AEAT, while
:func:`~aeat.application.live.capture_iva_remote_state` returns an
:class:`~aeat.application.live.IvaRemoteStateAcquisitionReport`, persists a
redacted :class:`~aeat.application.live.IvaRemoteStateAcquisitionManifest`, and
reports each remote surface independently so partial failures remain explicit.

See Also:
    :func:`~aeat.application.live._filed_observation_persistence.enroll_filed_justificante_evidence`
        Filed-history path that persists justificante metadata and stamps
        current filing records with live-capture evidence.
    :class:`~aeat.application.live.SecureSnapshotRepository`
        Bucket-scoped encrypted snapshot repository base used by live snapshot
        services.
    :mod:`aeat.application.overview`
        Local-only summary surface that reads captured live evidence without
        contacting AEAT.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence

    from ...adapters.outbound.aeat.auth import AeatSession
    from ...adapters.outbound.aeat.sede import Declaracion, Expediente, SedeCapture
    from ...core import Period
    from ...core.config import Settings
    from ...domain.justificante import Justificante
    from ...domain.modelos import ModeloRecord
    from ._expedientes import ExpedientesCapture, ExpedientesService
    from ._notifications import NotificationsService
    from ._verify import VerifyService, VerifySurface, VerifyVerdict

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
from ._censo import CensoSnapshotNotFoundError
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
    capture_filed_data,
    capture_filed_data_bulk,
    capture_source_filed_data,
    filed_data_capture_failure_row,
    list_filed_data,
    list_filed_data_bulk,
)
from ._filed_observation_persistence import (
    enroll_filed_justificante_evidence,
    persist_filed_calculation_observation,
    persist_filed_justificante_metadata,
)
from ._filed_observation_persistence import (
    latest_declarations_by_period as _latest_declarations_by_period,
)
from ._filed_observation_persistence import (
    persist_iva_compensation_history_observations_strict as _persist_iva_compensation_history_observations_strict,
)
from ._filed_observation_persistence import (
    persist_latest_filed_calculation_observations as _persist_latest_filed_calculation_observations,
)
from ._iva_remote_state import (
    IvaRemoteStateAcquisitionManifestRepository,
    _aggregate_iva_compensation_history_reports,
    _await_live_iva_surface,
    _filed_history_surface_timeout_ms,
    _suppress_live_iva_playwright_cancellation_noise,
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
    SecureSnapshotRepository,
    SnapshotLifecycleState,
    SnapshotNotFoundError,
    SnapshotRepository,
)


@dataclass(frozen=True, slots=True)
class JustificanteCaptureOutcome:
    """Outcome of one live justificante pull and local filing-evidence enrolment.

    The :class:`JustificanteCaptureSnapshot` is always the persisted live
    evidence. ``justificante`` is populated only when the PDF parsed into domain
    metadata, and ``filing_record`` is populated only when an existing current
    :class:`ModeloRecord` could be stamped with live
    :class:`ExternalEvidence`.
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
    its session via :func:`aeat.application.live._session.active_verified_session`,
    so the read access gate is enforced before any remote contact.
    """
    from ._expedientes import ExpedientesCapture, ExpedientesService

    session, settings = await _active_verified_session()
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
    session, settings = await _active_verified_session(operation="live-expedientes-read")
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
       ``aeat.application.live.notifications`` namespace.
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


async def _default_justificante_session() -> tuple[AeatSession, Settings]:
    return await _active_verified_session(operation="live-justificante-read")


async def _default_justificante_declarations(
    session: AeatSession,
    settings: Settings,
    *,
    modelo: str,
    year: int,
) -> tuple[Declaracion, ...]:
    async with (
        _shared_playwright(session) as playwright,
        _open_declarations_register(session, settings=settings, playwright=playwright) as register,
    ):
        return tuple(await register.walk(modelo=modelo, ejercicio=year))


async def _default_justificante_expedientes(
    session: AeatSession,
    settings: Settings,
    *,
    modelo: str,
) -> tuple[Expediente, ...]:
    from ...adapters.outbound.aeat.sede import walk_expedientes_tree

    return await walk_expedientes_tree(session, modelo=modelo, settings=settings)


async def _default_justificante_capture(
    session: AeatSession,
    settings: Settings,
    *,
    expediente: Expediente,
) -> SedeCapture:
    from ...adapters.outbound.aeat.sede import capture_justificante

    return await capture_justificante(session, expediente, settings=settings)


async def capture_justificante_snapshot(
    *,
    bucket_id: str,
    modelo: str,
    year: int,
    period: Period,
    session_provider: Callable[[], Awaitable[tuple[AeatSession, Settings]]] = _default_justificante_session,
    declarations_provider: Callable[..., Awaitable[Sequence[Declaracion]]] = _default_justificante_declarations,
    expedientes_provider: Callable[..., Awaitable[Sequence[Expediente]]] = _default_justificante_expedientes,
    justificante_provider: Callable[..., Awaitable[SedeCapture]] = _default_justificante_capture,
) -> JustificanteCaptureSnapshot:
    """Live-pull the AEAT justificante for one work unit and persist it.

    The flow gates entry through ``_active_verified_session`` (the
    ``require_live_read`` + authenticated-session boundary), resolves the
    period-correct expediente by cross-referencing the period-bearing
    declarations register against the procedure tree
    (:func:`resolve_period_expediente`), pulls the signed PDF via
    ``capture_justificante``, and persists it through
    :class:`JustificanteCaptureSnapshotService` under the active bucket.

    The four ``*_provider`` seams default to the live sede implementations;
    tests inject canned typed records to exercise the wiring offline without
    a network round-trip. The persistence path always uses the real service.

    Returns:
        The persisted :class:`JustificanteCaptureSnapshot`.
    """
    outcome = await capture_justificante_snapshot_outcome(
        bucket_id=bucket_id,
        modelo=modelo,
        year=year,
        period=period,
        session_provider=session_provider,
        declarations_provider=declarations_provider,
        expedientes_provider=expedientes_provider,
        justificante_provider=justificante_provider,
    )
    return outcome.snapshot


async def capture_justificante_snapshot_outcome(
    *,
    bucket_id: str,
    modelo: str,
    year: int,
    period: Period,
    session_provider: Callable[[], Awaitable[tuple[AeatSession, Settings]]] = _default_justificante_session,
    declarations_provider: Callable[..., Awaitable[Sequence[Declaracion]]] = _default_justificante_declarations,
    expedientes_provider: Callable[..., Awaitable[Sequence[Expediente]]] = _default_justificante_expedientes,
    justificante_provider: Callable[..., Awaitable[SedeCapture]] = _default_justificante_capture,
) -> JustificanteCaptureOutcome:
    """Live-pull one AEAT justificante and report local filing-evidence enrolment.

    The persisted :class:`JustificanteCaptureSnapshot` is the durable evidence.
    Metadata registration and current-record evidence stamping are best-effort
    follow-up steps reported separately in :class:`JustificanteCaptureOutcome`.
    A missing local filing record does not discard the captured receipt.

    Returns:
        A :class:`JustificanteCaptureOutcome` with the capture and enrolment result.
    """
    session, settings = await session_provider()
    declarations = await declarations_provider(session, settings, modelo=modelo, year=year)
    expedientes = await expedientes_provider(session, settings, modelo=modelo)
    expediente = resolve_period_expediente(
        declarations=declarations,
        expedientes=expedientes,
        modelo=modelo,
        period=period,
    )
    capture = await justificante_provider(session, settings, expediente=expediente)
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
    # Per the ADR, the capture flow stamps the official evidence onto the work
    # unit's filing record in the same flow. Best-effort: a no-op when the period
    # is not yet filed in-app (the snapshot is still persisted).
    justificante = register_capture_justificante_metadata(snapshot=persisted)
    filing_record = stamp_capture_evidence_if_filed(persisted)
    return JustificanteCaptureOutcome(snapshot=persisted, justificante=justificante, filing_record=filing_record)


def __getattr__(name: str):
    """Lazy-load the heavy service classes through the package boundary.

    Promoted per the ``service-imports-via-top-level-reexports``
    rule so CLI handlers and other consumers consume these symbols
    through ``aeat.application.live`` rather than dotting into
    ``_verify`` / ``_notifications`` / ``_expedientes``. Lazy
    semantics preserve the existing module-load-time profile (the
    services trigger their own heavy imports only on first
    access).
    """
    if name in ("VerifyService", "VerifyVerdict", "VerifySurface"):
        from . import _verify as _impl_mod

        return getattr(_impl_mod, name)
    if name == "NotificationsService":
        from . import _notifications as _impl_mod

        return getattr(_impl_mod, name)
    if name in ("ExpedientesService", "ExpedientesCapture"):
        from . import _expedientes as _impl_mod

        return getattr(_impl_mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "BORRADOR_100_SNAPSHOT_NAMESPACE",
    "JUSTIFICANTE_CAPTURE_SNAPSHOT_NAMESPACE",
    "JUSTIFICANTE_CAPTURE_SOURCE_KIND",
    "Borrador100Snapshot",
    "Borrador100SnapshotRepository",
    "Borrador100SnapshotService",
    "BorradorSnapshotNotFoundError",
    "BulkFiledDataCaptureReport",
    "BulkFiledDataListingReport",
    "CensoSnapshotNotFoundError",
    "ExpedientesBulkCaptureFailureRow",
    "ExpedientesBulkCaptureReport",
    "ExpedientesCapture",
    "ExpedientesService",
    "FiledDataCaptureFailureRow",
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
    "NotificationsService",
    "SecureSnapshotRepository",
    "SnapshotLifecycleState",
    "SnapshotNotFoundError",
    "SnapshotRepository",
    "SourceFiledDataCaptureReport",
    "StoredIvaRemoteStateAcquisitionRow",
    "StoredIvaWalletObservationRow",
    "VerifyService",
    "VerifySurface",
    "VerifyVerdict",
    "_aggregate_iva_compensation_history_reports",
    "_await_live_iva_surface",
    "_filed_history_surface_timeout_ms",
    "_latest_declarations_by_period",
    "_persist_iva_compensation_history_observations_strict",
    "_persist_latest_filed_calculation_observations",
    "_suppress_live_iva_playwright_cancellation_noise",
    "borrador_100_snapshot_object_key",
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
    "classify_live_iva_acquisition_failure",
    "derive_borrador_100_snapshot_id",
    "derive_justificante_capture_snapshot_id",
    "enroll_filed_justificante_evidence",
    "filed_data_capture_failure_row",
    "filed_data_listing_row",
    "justificante_capture_snapshot_object_key",
    "list_filed_data",
    "list_filed_data_bulk",
    "list_iva_compensation_history",
    "list_iva_remote_state_acquisition_manifests",
    "load_iva_remote_state",
    "load_iva_remote_state_acquisition_manifest",
    "parse_capture_to_justificante",
    "persist_and_reconcile_iva_compensation_wallet",
    "persist_filed_calculation_observation",
    "persist_filed_justificante_metadata",
    "persist_iva_remote_state_acquisition_report",
    "reconcile_capture",
    "register_capture_as_filing_evidence",
    "register_capture_justificante_metadata",
    "resolve_period_expediente",
    "select_declarations_for_capture",
    "stamp_capture_evidence_if_filed",
]
