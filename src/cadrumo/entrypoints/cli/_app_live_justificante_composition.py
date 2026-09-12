"""Concrete adapter assembly for the live justificante CLI commands."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from typing import cast

from ...adapters.inbound.justificante.parser import parse_justificante_bytes
from ...adapters.outbound.aeat.sede.declarations import open_declarations_register, shared_playwright
from ...adapters.outbound.aeat.sede.walker import capture_justificante, walk_expedientes_tree
from ...adapters.outbound.aeat.verify.contract import verify_csv
from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ...adapters.persistence.profile.justificante import JustificanteRepository
from ...adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ...adapters.persistence.profile.snapshots import SecureSnapshotRepository
from ...adapters.persistence.storage.envelope.contract import Envelope
from ...adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from ...adapters.persistence.storage.secure_object_namespaces import LIVE_JUSTIFICANTE_CAPTURE_SNAPSHOT_NAMESPACE
from ...application.live.errors import LiveApplicationInputError
from ...application.live.justificante import (
    JustificanteCaptureSnapshot,
    JustificanteCaptureSnapshotNotFoundError,
    JustificanteCaptureSnapshotRepository,
    JustificanteCaptureSnapshotService,
    justificante_capture_snapshot_object_key,
)
from ...application.live.justificante_ports import (
    CapturedJustificante,
    JustificanteAuthenticityVerifierPort,
    JustificanteDeclaration,
    JustificanteExpediente,
    JustificanteLiveReadPort,
    JustificanteRegistrationPorts,
)
from ...application.live.session import active_verified_session
from ...core.external_constants import UTF_8_ENCODING
from ...domain.buckets.event import BucketEvent
from ...domain.buckets.event_repository import emit_bucket_events


class _SnapshotPersistence:
    def __init__(self, *, bucket_id: str) -> None:
        self._bucket_id = bucket_id
        self._objects = secure_object_repository_for_bucket(bucket_id)
        self._delegate = SecureSnapshotRepository(
            bucket_id=bucket_id,
            payload_model=JustificanteCaptureSnapshot,
            namespace_definition=LIVE_JUSTIFICANTE_CAPTURE_SNAPSHOT_NAMESPACE,
            object_key=justificante_capture_snapshot_object_key,
            not_found_factory=lambda snapshot_id: JustificanteCaptureSnapshotNotFoundError(
                translated_message="application.live.justificante.errors.snapshot_not_found",
                context={"snapshot_id": snapshot_id},
            ),
            ambiguous_prefix_factory=lambda snapshot_id, full_ids: JustificanteCaptureSnapshotNotFoundError(
                translated_message="application.live.justificante.errors.snapshot_prefix_ambiguous",
                context={"snapshot_id": snapshot_id, "match_count": len(full_ids)},
            ),
            domain_label="justificante capture",
            input_error_cls=LiveApplicationInputError,
            objects=self._objects,
        )

    @property
    def bucket_id(self) -> str:
        return self._bucket_id

    def exists(self, snapshot_id: str) -> bool:
        return self._delegate.exists(snapshot_id)

    def load(self, snapshot_id: str) -> JustificanteCaptureSnapshot:
        return self._delegate.load(snapshot_id)

    def list_snapshots(self) -> Sequence[JustificanteCaptureSnapshot]:
        return self._delegate.list_snapshots()

    def resolve(self, snapshot_id: str) -> JustificanteCaptureSnapshot:
        return self._delegate.resolve(snapshot_id)

    def save(self, snapshot: object) -> None:
        typed_snapshot = cast(JustificanteCaptureSnapshot, snapshot)
        envelope = Envelope[JustificanteCaptureSnapshot](
            schema_version=LIVE_JUSTIFICANTE_CAPTURE_SNAPSHOT_NAMESPACE.schema_version,
            written_at=typed_snapshot.captured_at,
            classification=LIVE_JUSTIFICANTE_CAPTURE_SNAPSHOT_NAMESPACE.sensitivity,
            payload=typed_snapshot,
        )
        self._objects.save(
            namespace=LIVE_JUSTIFICANTE_CAPTURE_SNAPSHOT_NAMESPACE.namespace,
            object_key=justificante_capture_snapshot_object_key(self._bucket_id, typed_snapshot.snapshot_id),
            classification=LIVE_JUSTIFICANTE_CAPTURE_SNAPSHOT_NAMESPACE.sensitivity,
            schema_version=LIVE_JUSTIFICANTE_CAPTURE_SNAPSHOT_NAMESPACE.schema_version,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode(UTF_8_ENCODING),
        )


class _RegistrationEvents:
    def emit(self, events: tuple[BucketEvent, ...]) -> None:
        emit_bucket_events(repository=BucketEventHistoryRepository(), events=events)


class _LiveRead:
    def __init__(self) -> None:
        self._session: object | None = None
        self._settings: object | None = None
        self._expedientes: dict[str, object] = {}

    async def declarations_and_expedientes(
        self, *, modelo: str, year: int
    ) -> tuple[Sequence[JustificanteDeclaration], Sequence[JustificanteExpediente]]:
        session, settings = await active_verified_session(operation="live-justificante-read")
        async with (
            shared_playwright(session) as playwright,
            open_declarations_register(session, settings=settings, playwright=playwright) as register,
        ):
            declarations = tuple(await register.walk(modelo=modelo, ejercicio=year))
        expedientes = await walk_expedientes_tree(session, modelo=modelo, settings=settings)
        self._session = session
        self._settings = settings
        self._expedientes = {item.expediente_id: item for item in expedientes}
        return (
            tuple(
                JustificanteDeclaration(
                    modelo=item.modelo,
                    period=item.period,
                    expediente_id=item.expediente_id,
                    estado=item.estado,
                    presented_at=item.presented_at,
                )
                for item in declarations
            ),
            tuple(JustificanteExpediente(expediente_id=item.expediente_id) for item in expedientes),
        )

    async def capture(self, *, expediente_id: str) -> CapturedJustificante:
        if self._session is None or self._settings is None or expediente_id not in self._expedientes:
            raise RuntimeError("live justificante capture requires declaration discovery")
        capture = await capture_justificante(
            self._session,
            self._expedientes[expediente_id],
            settings=self._settings,
        )
        return CapturedJustificante(
            expediente_id=capture.expediente.expediente_id,
            csv=capture.ref.csv,
            pdf_bytes=capture.pdf_bytes,
            pdf_sha256=capture.pdf_sha256,
        )


class _Verifier:
    def verify(
        self,
        csv: str,
        *,
        browser: object | None = None,
        browser_session_factory: Callable[[], object] | None = None,
    ) -> Awaitable[bool]:
        return verify_csv(csv, browser=browser, browser_session_factory=browser_session_factory)


def build_justificante_capture_service(bucket_id: str) -> JustificanteCaptureSnapshotService:
    """Bind the application service to the active bucket's secure object store."""
    return JustificanteCaptureSnapshotService(
        bucket_id=bucket_id,
        repository=JustificanteCaptureSnapshotRepository(persistence=_SnapshotPersistence(bucket_id=bucket_id)),
    )


def build_justificante_registration_ports() -> JustificanteRegistrationPorts:
    """Bind receipt metadata, filing catalogue, and event persistence adapters."""
    return JustificanteRegistrationPorts(
        parse_pdf=parse_justificante_bytes,
        metadata=JustificanteRepository(),
        filing=ModeloRecordCatalogueRepository(),
        events=_RegistrationEvents(),
    )


def build_justificante_live_read_port() -> JustificanteLiveReadPort:
    return _LiveRead()


def build_justificante_authenticity_verifier() -> JustificanteAuthenticityVerifierPort:
    return _Verifier()
