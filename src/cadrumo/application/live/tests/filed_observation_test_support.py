"""In-memory ports for application-level filed-history composition tests."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from ..filed_observation_ports import FiledObservationPersistencePorts
from ..iva_remote_state_ports import IvaRemoteStatePort


@dataclass(frozen=True, slots=True)
class _RegistryObservation:
    """Small registry-row shape consumed by the calculation persistence port."""

    modelo: str
    filing_year: int
    period: str


@dataclass(frozen=True, slots=True)
class _PreparedObservationEnvelope:
    """Opaque calculation payload accepted by the in-memory repository."""

    observation: object


@dataclass(slots=True)
class _InMemoryObservationPersistence:
    """Keep captured manifests and artefacts in process memory."""

    observations: list[object] = field(default_factory=list)
    artefacts: dict[str, bytes] = field(default_factory=dict)
    _next_ref: int = 0

    def persist_observation(self, observation: object) -> Path:
        """Record one manifest and return a deterministic logical path."""
        self.observations.append(observation)
        return Path(f"memory-observations/{len(self.observations)}/manifest.json")

    def persist_artefact(self, observation_key: tuple[object, ...], artefact: object, body: bytes) -> object:
        """Keep one artefact body and attach its in-memory reference when possible."""
        del observation_key
        self._next_ref += 1
        storage_ref = f"memory-artefact:{self._next_ref}"
        self.artefacts[storage_ref] = body
        model_copy = getattr(artefact, "model_copy", None)
        if model_copy is None:
            return artefact
        return model_copy(update={"storage_ref": storage_ref})

    def load_artefact(self, storage_ref: str) -> bytes:
        """Load an artefact body previously retained by this fake."""
        return self.artefacts[storage_ref]


class _InMemoryParser:
    """Receipt parser surface with no external-document implementation."""

    def parse_justificante(self, body: bytes) -> object:
        """Refuse receipt parsing because these tests do not supply receipt bytes."""
        del body
        raise ValueError("test bundle has no justificante parser")

    def csv_from_source_url(self, source_url: str) -> str:
        """Refuse source-URL parsing because no receipt is expected here."""
        del source_url
        raise ValueError("test bundle has no AEAT source URL parser")


class _InMemoryTransformation:
    """Translate only the coordinates needed by the finalizer's calculation path."""

    def registry_observation(self, observation: object) -> _RegistryObservation:
        """Project the filed observation's identity and fiscal coordinates."""
        return _RegistryObservation(
            modelo=observation.modelo,
            filing_year=observation.ejercicio,
            period=observation.period.registry_token,
        )

    def non_numeric_casillas(self, observation: object) -> tuple[object, ...]:
        """Return no skips; no operator projection is under test here."""
        del observation
        return ()


class _InMemoryCalculationRepository:
    """Retain prepared calculation payloads without secure-storage concerns."""

    def __init__(self) -> None:
        self.payloads: list[_PreparedObservationEnvelope] = []

    def prepare_observation_envelope(self, observation: object, **_: object) -> _PreparedObservationEnvelope:
        """Build the opaque payload accepted by this test repository."""
        payload = _PreparedObservationEnvelope(observation=observation)
        self.payloads.append(payload)
        return payload

    def save(self, payload: _PreparedObservationEnvelope) -> None:
        """Keep the prepared payload in memory."""
        if payload not in self.payloads:
            self.payloads.append(payload)


class _InMemoryIvaHistoryRepository:
    """Answer the strict history reload check after an in-memory co-commit."""

    def load_period(self, period: object) -> object:
        """Return a marker for every period accepted by the fake persistence."""
        del period
        return object()


class _InMemoryIvaObservationPersistence:
    """Accept calculation/history co-commits without a storage adapter."""

    def persist(self, **_: object) -> None:
        """Record no additional state; the history fake answers reload checks."""


class _InMemoryJustificanteRepository:
    """Minimal receipt repository for the application contract."""

    def load(self, csv: str) -> None:
        """No receipt has been enrolled by this bundle."""
        del csv
        return None

    def save(self, justificante: object) -> None:
        """Accept a parsed receipt if a test supplies one."""
        del justificante

    def iter_justificantes(self) -> Iterator[object]:
        """Yield no receipts."""
        return iter(())


class _InMemoryFilingCatalogue:
    """Empty filing catalogue sufficient for evidence-stamping lookups."""

    def current_for(self, **_: object) -> None:
        """Report that no current local filing exists."""
        return None


class _InMemoryFilingRepository:
    """Mutable in-memory filing catalogue port."""

    def __init__(self) -> None:
        self.catalogue = _InMemoryFilingCatalogue()

    def load(self) -> _InMemoryFilingCatalogue:
        """Return the current empty catalogue."""
        return self.catalogue

    def mutate(self, mutation):
        """Apply one catalogue mutation in memory."""
        self.catalogue = mutation(self.catalogue)
        return self.catalogue


class _InMemoryBucketEventRepository:
    """Small event-history repository used only if a fake filing is supplied."""

    def __init__(self) -> None:
        self.events: list[object] = []

    def exists(self) -> bool:
        """Report whether an event has been accepted."""
        return bool(self.events)

    def load(self):
        """Return an object exposing the event mapping expected by append logic."""
        return _InMemoryEventCatalogue(events={str(index): event for index, event in enumerate(self.events)})

    def save(self, catalogue: _InMemoryEventCatalogue) -> None:
        """Retain the catalogue's events in memory."""
        self.events = list(catalogue.events.values())


@dataclass(frozen=True, slots=True)
class _InMemoryEventCatalogue:
    """Minimal event catalogue shape for the shared bucket-event primitive."""

    events: dict[str, object]


class _UnavailableIvaRemoteStatePort:
    """Keep the unrelated IVA wallet stage local and deterministically refused."""

    @property
    def wallet_target_url(self) -> str:
        """Return a non-network placeholder URL for the protocol property."""
        return "https://test.invalid/iva-wallet"

    @contextmanager
    def active_storage_span(self):
        """Provide the storage span without opening a secure backend."""
        yield

    def list_history(self, *, as_of_year: int | None):
        """The operation tests do not query IVA history through this fake."""
        del as_of_year
        raise RuntimeError("test bundle does not provide IVA history")

    def persist_manifest(self, manifest: object) -> None:
        """Accept no remote-state manifest because no remote state is read."""
        del manifest

    async def active_verified_session(self, *, operation: str, target_url: str | None):
        """Refuse before any live session or network can be requested."""
        del operation, target_url
        raise RuntimeError("test bundle does not provide live IVA access")

    async def ensure_authenticated_session(self, settings: object, *, operation: str, target_url: str | None):
        """Refuse before any live authentication can be requested."""
        del settings, operation, target_url
        raise RuntimeError("test bundle does not provide live IVA access")

    async def capture_history(self, session: object, **_: object):
        """Refuse direct IVA history capture in application tests."""
        del session
        raise RuntimeError("test bundle does not provide live IVA access")

    async def capture_wallet(self, session: object, **_: object):
        """Refuse direct IVA wallet capture in application tests."""
        del session
        raise RuntimeError("test bundle does not provide live IVA access")


@dataclass(frozen=True, slots=True)
class InMemoryFiledObservationTestBundle:
    """Composed test ports for the filed-history application boundary."""

    ports: FiledObservationPersistencePorts
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
            baseline_import=_InMemoryBaselineImport(),
        ),
        iva_remote_state_port=_UnavailableIvaRemoteStatePort(),
    )


class _InMemoryBaselineImport:
    """Decline complete-baseline import because it is outside these tests."""

    def import_source(self, source: object, *, bucket_id: str, actor: str, clock: object) -> None:
        """Return no filing record from the test-only baseline surface."""
        del source, bucket_id, actor, clock
        return None


__all__ = ["InMemoryFiledObservationTestBundle", "in_memory_filed_observation_test_bundle"]
