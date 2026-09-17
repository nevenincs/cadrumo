"""In-memory ports for application-level filed-history composition tests."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Generator, Iterator, Mapping
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from ....core.observed_header_fact import ObservedHeaderFact
from ....core.period import Period
from ....domain.buckets.event import BucketEventHistoryCatalogue
from ....domain.calculations.registry.bindings import RegistryModeloObservation
from ....domain.justificante.schema import Justificante
from ....domain.modelos.filing_record import ModeloRecord, ModeloRecordCatalogue
from ...calculations.observations_repository import (
    ObservationEnvelopePayload,
    ObservationSourceKind,
)
from ..errors import LiveApplicationError
from ..filed_data_ports import (
    FiledArtefactSink,
    FiledDataCapturePort,
    FiledDataRegisterPort,
    FiledDeclarationAvailabilityReportProtocol,
    FiledRegisterDeclarationProtocol,
)
from ..filed_observation_ports import (
    FiledCalculationObservationRepositoryPort,
    FiledIvaHistoryRepositoryPort,
    FiledObservationArtefactProtocol,
    FiledObservationPersistencePorts,
    FiledObservationProtocol,
    FiledObservationSkipProtocol,
)
from ..iva_remote_state_ports import IvaRemoteStatePort

if TYPE_CHECKING:
    from ....core.config import Settings
    from ....core.secure_object_write import SecureObjectWrite
    from ....domain.calculations.registry.schema import ModeloRevision
    from ....domain.iva_compensation.carry_forward import IvaCompensationPeriodState
    from ...auth.session_types import AeatSession
    from ...auth.sessions import AuthenticatedAeatSessionResult
    from ...modelo.filing_chain_reconciliation import AeatRegisterEntry, FilingReconciliationResult
    from ..remote_state_models import (
        IvaCompensationHistoryCaptureReport,
        IvaCompensationHistoryReport,
        IvaRemoteStateAcquisitionManifest,
        IvaWalletCaptureReport,
    )


@dataclass(frozen=True, slots=True)
class _InMemoryObservationArtefact:
    """Persisted artefact view returned by the in-memory custody fake."""

    kind: str
    source_url: str
    byte_count: int
    sha256: str
    captured_at: datetime
    storage_ref: str | None


@dataclass(slots=True)
class _InMemoryObservationPersistence:
    """Keep captured manifests and artefacts in process memory."""

    observations: list[FiledObservationProtocol] = field(default_factory=list)
    artefacts: dict[str, bytes] = field(default_factory=dict)
    _next_ref: int = 0

    def persist_observation(self, observation: FiledObservationProtocol) -> Path:
        """Record one manifest and return a deterministic logical path."""
        self.observations.append(observation)
        return Path(f"memory-observations/{len(self.observations)}/manifest.json")

    def persist_artefact(
        self,
        observation_key: tuple[str, int, Period, str],
        artefact: FiledObservationArtefactProtocol,
        body: bytes,
    ) -> FiledObservationArtefactProtocol:
        """Keep one artefact body and return its typed in-memory manifest."""
        del observation_key
        self._next_ref += 1
        storage_ref = f"memory-artefact:{self._next_ref}"
        self.artefacts[storage_ref] = body
        return _InMemoryObservationArtefact(
            kind=artefact.kind,
            source_url=str(artefact.source_url),
            byte_count=artefact.byte_count,
            sha256=artefact.sha256,
            captured_at=artefact.captured_at,
            storage_ref=storage_ref,
        )

    def load_artefact(self, storage_ref: str) -> bytes:
        """Load an artefact body previously retained by this fake."""
        return self.artefacts[storage_ref]


class _InMemoryParser:
    """Receipt parser surface with no external-document implementation."""

    def parse_justificante(self, body: bytes) -> Justificante:
        """Refuse receipt parsing because these tests do not supply receipt bytes."""
        del body
        raise ValueError("test bundle has no justificante parser")

    def csv_from_source_url(self, source_url: str) -> str:
        """Refuse source-URL parsing because no receipt is expected here."""
        del source_url
        raise ValueError("test bundle has no AEAT source URL parser")


class _InMemoryTransformation:
    """Translate only the coordinates needed by the finalizer's calculation path."""

    def registry_observation(self, observation: FiledObservationProtocol) -> RegistryModeloObservation:
        """Project the filed observation's identity and fiscal coordinates."""
        return RegistryModeloObservation(
            modelo=observation.modelo,
            filing_year=observation.ejercicio,
            period=observation.period.registry_token,
            filing_period=observation.period,
        )

    def non_numeric_casillas(self, observation: FiledObservationProtocol) -> tuple[FiledObservationSkipProtocol, ...]:
        """Return no skips; no operator projection is under test here."""
        del observation
        return ()


class _InMemoryCalculationRepository:
    """Retain prepared calculation payloads without secure-storage concerns."""

    def __init__(self) -> None:
        self.payloads: list[ObservationEnvelopePayload] = []

    def load_observation(self, modelo: str, period: Period) -> ObservationEnvelopePayload | None:
        """Return a prepared payload for one filed observation coordinate."""
        return next(
            (
                payload
                for payload in self.payloads
                if str(payload.observation.modelo) == modelo and payload.observation.filing_period == period
            ),
            None,
        )

    def prepare_observation_envelope(
        self,
        observation: RegistryModeloObservation,
        *,
        source_kind: ObservationSourceKind | str,
        stamped_revision_id: str,
        captured_at: datetime | None = None,
        source_metadata: Mapping[str, str] | None = None,
        source_headers: tuple[ObservedHeaderFact, ...] = (),
    ) -> ObservationEnvelopePayload:
        """Build one validated payload accepted by this test repository."""
        if captured_at is None:
            raise ValueError("in-memory calculation repository requires captured_at")
        payload = ObservationEnvelopePayload(
            observation=observation,
            source_kind=source_kind,
            stamped_revision_id=stamped_revision_id,
            captured_at=captured_at,
            source_metadata=dict(source_metadata or {}),
            source_headers=source_headers,
        )
        self.payloads.append(payload)
        return payload

    def save(self, payload: ObservationEnvelopePayload) -> None:
        """Keep the prepared payload in memory."""
        if payload not in self.payloads:
            self.payloads.append(payload)


class _InMemoryIvaHistoryRepository:
    """Keep no IVA history because this bundle does not provide M303 ingress."""

    def load_period(self, period: Period) -> IvaCompensationPeriodState | None:
        """Report that no IVA history is available in this application-only fake."""
        del period
        return None


class _InMemoryIvaObservationPersistence:
    """Refuse M303 co-commits that need the canonical carry-ingress adapter."""

    def persist(
        self,
        *,
        observation_repository: FiledCalculationObservationRepositoryPort,
        history_repository: FiledIvaHistoryRepositoryPort,
        envelope: ObservationEnvelopePayload,
        taxpayer_nif: str,
        source_observation_key: str,
        expediente_id: str | None,
        status: str | None,
        source_artefact_sha256: str | None,
    ) -> IvaCompensationPeriodState:
        """Refuse instead of manufacturing a disposition-aware history state."""
        del (
            observation_repository,
            history_repository,
            envelope,
            taxpayer_nif,
            source_observation_key,
            expediente_id,
            status,
            source_artefact_sha256,
        )
        raise RuntimeError("test bundle does not provide IVA history co-commit")


class _InMemoryJustificanteRepository:
    """Minimal receipt repository for the application contract."""

    def __init__(self) -> None:
        self.records: list[Justificante] = []

    def load(self, csv: str, /) -> Justificante | None:
        """No receipt has been enrolled by this bundle."""
        del csv
        return None

    def save(self, justificante: Justificante, /) -> None:
        """Accept a parsed receipt if a test supplies one."""
        self.records.append(justificante)

    def iter_justificantes(self) -> Iterator[Justificante]:
        """Yield no receipts."""
        return iter(tuple(self.records))


class _InMemoryFilingCatalogue:
    """Empty filing catalogue sufficient for evidence-stamping lookups."""

    def __init__(self) -> None:
        self._catalogue = ModeloRecordCatalogue()

    def current_for(
        self,
        *,
        bucket_id: str,
        modelo: str,
        filing_year: int,
        period: Period,
        member_nif: str | None = None,
    ) -> ModeloRecord | None:
        """Report that no current local filing exists."""
        return self._catalogue.current_for(
            bucket_id=bucket_id,
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            member_nif=member_nif,
        )

    @property
    def records(self) -> Mapping[str, ModeloRecord]:
        """Expose the real catalogue records for repository bookkeeping."""
        return self._catalogue.records

    def replace(self, catalogue: ModeloRecordCatalogue) -> None:
        """Replace the in-memory catalogue with a validated catalogue."""
        self._catalogue = catalogue

    def as_model(self) -> ModeloRecordCatalogue:
        """Return the validated catalogue held by this fake."""
        return self._catalogue


class _InMemoryFilingRepository:
    """Mutable in-memory filing catalogue port."""

    def __init__(self) -> None:
        self.catalogue = _InMemoryFilingCatalogue()

    @property
    def bucket_id(self) -> str | None:
        """Report that this application-only fake is not profile-bound."""
        return None

    def exists(self) -> bool:
        """Report whether a filing record has been retained."""
        return bool(self.catalogue.records)

    def load(self) -> ModeloRecordCatalogue:
        """Return the current empty catalogue."""
        return self.catalogue.as_model()

    def load_revisioned(self) -> tuple[ModeloRecordCatalogue, str]:
        """Refuse revisioned reads because this fake has no secure object revision."""
        raise RuntimeError("test bundle does not provide filing catalogue revisions")

    def save(self, catalogue: ModeloRecordCatalogue) -> None:
        """Retain a validated filing catalogue in memory."""
        self.catalogue.replace(catalogue)

    def mutate(self, mutation: Callable[[ModeloRecordCatalogue], ModeloRecordCatalogue]) -> ModeloRecordCatalogue:
        """Apply one catalogue mutation in memory."""
        updated = mutation(self.catalogue.as_model())
        self.catalogue.replace(updated)
        return updated

    def to_secure_object_write(
        self,
        catalogue: ModeloRecordCatalogue,
        *,
        expected_revision_id: str | None = None,
    ) -> SecureObjectWrite:
        """Refuse secure writes because this fake has no encrypted backend."""
        del catalogue, expected_revision_id
        raise RuntimeError("test bundle does not provide secure filing writes")

    def save_with_secure_object_writes(
        self,
        catalogue: ModeloRecordCatalogue,
        extra_writes: tuple[SecureObjectWrite, ...],
        *,
        expected_revision_id: str | None = None,
    ) -> None:
        """Refuse atomic secure writes because this fake has no encrypted backend."""
        del catalogue, extra_writes, expected_revision_id
        raise RuntimeError("test bundle does not provide secure filing writes")


class _InMemoryBucketEventRepository:
    """Small event-history repository used only if a fake filing is supplied."""

    def __init__(self) -> None:
        self.catalogue = BucketEventHistoryCatalogue()

    def exists(self) -> bool:
        """Report whether an event has been accepted."""
        return bool(self.catalogue.events)

    def load(self) -> BucketEventHistoryCatalogue:
        """Return the validated event catalogue expected by append logic."""
        return self.catalogue

    def save(self, catalogue: BucketEventHistoryCatalogue) -> None:
        """Retain the catalogue's events in memory."""
        self.catalogue = catalogue

    def to_secure_object_write(
        self,
        catalogue: BucketEventHistoryCatalogue,
        *,
        expected_revision_id: str | None = None,
    ) -> SecureObjectWrite:
        """Refuse secure writes because this fake has no encrypted backend."""
        del catalogue, expected_revision_id
        raise RuntimeError("test bundle does not provide secure event writes")


class _UnavailableIvaRemoteStatePort:
    """Keep the unrelated IVA wallet stage local and deterministically refused."""

    @property
    def wallet_target_url(self) -> str:
        """Return a non-network placeholder URL for the protocol property."""
        return "https://test.invalid/iva-wallet"

    @contextmanager
    def active_storage_span(self) -> Generator[None]:
        """Provide the storage span without opening a secure backend."""
        yield

    def list_history(self, *, as_of_year: int | None) -> IvaCompensationHistoryReport:
        """The operation tests do not query IVA history through this fake."""
        del as_of_year
        raise RuntimeError("test bundle does not provide IVA history")

    def persist_manifest(self, manifest: IvaRemoteStateAcquisitionManifest) -> None:
        """Accept no remote-state manifest because no remote state is read."""
        del manifest

    async def active_verified_session(self, *, operation: str, target_url: str | None) -> tuple[AeatSession, Settings]:
        """Refuse before any live session or network can be requested."""
        del operation, target_url
        raise RuntimeError("test bundle does not provide live IVA access")

    async def ensure_authenticated_session(
        self,
        settings: Settings,
        *,
        operation: str,
        target_url: str | None,
    ) -> AuthenticatedAeatSessionResult:
        """Refuse before any live authentication can be requested."""
        del settings, operation, target_url
        raise RuntimeError("test bundle does not provide live IVA access")

    async def capture_history(
        self,
        session: AeatSession,
        *,
        settings: Settings,
        year_from: int,
        year_to: int,
        output_root: Path,
        progress_context: dict[str, object] | None,
    ) -> IvaCompensationHistoryCaptureReport:
        """Refuse direct IVA history capture in application tests."""
        del session, settings, year_from, year_to, output_root, progress_context
        raise RuntimeError("test bundle does not provide live IVA access")

    async def capture_wallet(
        self,
        session: AeatSession,
        *,
        settings: Settings,
        target_year: int,
        target_period: Period,
        taxpayer_nif: str | None,
        output_root: Path | None,
        progress_context: dict[str, object] | None,
    ) -> IvaWalletCaptureReport:
        """Refuse direct IVA wallet capture in application tests."""
        del session, settings, target_year, target_period, taxpayer_nif, output_root, progress_context
        raise RuntimeError("test bundle does not provide live IVA access")


class _UnavailableFiledDataRegister:
    """Refuse live register access while preserving per-pair continuation."""

    @property
    def walk_timeout_ms(self) -> int:
        """Return the deterministic timeout used by application-only tests."""
        return 1

    async def walk(self, *, modelo: str, ejercicio: int) -> tuple[FiledRegisterDeclarationProtocol, ...]:
        """Raise the application boundary refusal for every requested pair."""
        raise LiveApplicationError(
            translated_message="application.live.filed_observations.errors.registry_enrollment_failed",
            context={"operation": "test_filed_register_walk", "modelo": modelo, "ejercicio": ejercicio},
        )

    async def capture_observation(
        self,
        declaration: FiledRegisterDeclarationProtocol,
        *,
        artefact_sink: FiledArtefactSink | None = None,
    ) -> FiledObservationProtocol:
        """Refuse capture because no live register row exists in this fake."""
        del declaration, artefact_sink
        raise LiveApplicationError(
            translated_message="application.live.filed_observations.errors.registry_enrollment_failed",
        )


class UnavailableFiledDataCapturePort:
    """Application-only filed-data port that never opens a real Sede session."""

    @asynccontextmanager
    async def open_register(self, *, operation: str) -> AsyncIterator[FiledDataRegisterPort]:
        """Yield the per-pair refusal register used by composition tests."""
        del operation
        yield _UnavailableFiledDataRegister()

    async def discover_availability(self, *, operation: str) -> FiledDeclarationAvailabilityReportProtocol:
        """Refuse direct register discovery in this in-memory bundle."""
        del operation
        raise LiveApplicationError(
            translated_message="application.live.filed_observations.errors.registry_enrollment_failed",
        )

    async def capture_source_observations(
        self,
        revision: ModeloRevision,
        *,
        filing_year: int,
        period: Period,
        artefact_sink: FiledArtefactSink | None = None,
        operation: str,
    ) -> tuple[FiledObservationProtocol, ...]:
        """Return no source rows because source capture is outside these tests."""
        del revision, filing_year, period, artefact_sink, operation
        return ()


@dataclass(frozen=True, slots=True)
class InMemoryFiledObservationTestBundle:
    """Composed test ports for the filed-history application boundary."""

    ports: FiledObservationPersistencePorts
    filed_data_port: FiledDataCapturePort
    iva_remote_state_port: IvaRemoteStatePort


def in_memory_filed_observation_test_bundle() -> InMemoryFiledObservationTestBundle:
    """Build one fresh in-memory bundle with no concrete adapter imports."""
    observation_persistence = _InMemoryObservationPersistence()
    calculation_repository = _InMemoryCalculationRepository()
    return InMemoryFiledObservationTestBundle(
        ports=FiledObservationPersistencePorts(
            parser=_InMemoryParser(),
            transformation=_InMemoryTransformation(),
            observation_persistence=observation_persistence,
            calculation_repository=calculation_repository,
            iva_history_repository=_InMemoryIvaHistoryRepository(),
            iva_observation_persistence=_InMemoryIvaObservationPersistence(),
            justificante_repository=_InMemoryJustificanteRepository(),
            filing_repository=_InMemoryFilingRepository(),
            bucket_event_repository=_InMemoryBucketEventRepository(),
            filing_reconciliation=_UnavailableFilingReconciliation(),
        ),
        filed_data_port=UnavailableFiledDataCapturePort(),
        iva_remote_state_port=_UnavailableIvaRemoteStatePort(),
    )


class _UnavailableFilingReconciliation:
    """Decline filing-chain reconciliation because it is outside these tests."""

    def reconcile(
        self,
        entry: AeatRegisterEntry,
        *,
        actor: str,
        clock: datetime,
    ) -> FilingReconciliationResult:
        """Refuse rather than fabricate a chain decision on the test-only surface."""
        del entry, actor, clock
        raise RuntimeError("test bundle does not provide filing-chain reconciliation")


__all__ = ["InMemoryFiledObservationTestBundle", "in_memory_filed_observation_test_bundle"]
