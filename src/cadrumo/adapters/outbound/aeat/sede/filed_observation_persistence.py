"""Concrete adapters for the filed-observation application ports.

The live filed-history service owns only protocols.  This module is the outer
binding for those protocols: it joins the existing Sede parser and observation
store to the encrypted calculation, filing, IVA-history, event, and baseline
repositories.  Adapter failures are translated at this boundary so an
application caller never has to know a Sede or secure-object exception type.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, override

from .....adapters.persistence.profile.calculation_observations import (
    CalculationObservationRepository,
)
from .....adapters.persistence.profile.iva_compensation_history import IvaCompensationHistoryRepository
from .....application.calculations.iva_compensation_history import persist_observation_envelope_and_iva_history
from .....application.calculations.observations_repository import (
    ObservationEnvelopePayload,
    ObservationSourceKind,
)
from .....application.live.errors import LiveApplicationError
from .....application.live.filed_observation_ports import (
    FiledBaselineImportPort,
    FiledCalculationObservationRepositoryPort,
    FiledDeclarationTransformationPort,
    FiledIvaHistoryRepositoryPort,
    FiledIvaObservationPersistencePort,
    FiledObservationArtefactProtocol,
    FiledObservationParserPort,
    FiledObservationPersistencePort,
    FiledObservationProtocol,
    FiledObservationSkipProtocol,
)
from .....application.modelo.external_import_actions import (
    ExternalFilingBaselineSource,
    import_external_filing_source,
)
from .....application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from .....core.iva_compensation_provenance import IvaCompensationStateProvenance
from .....core.observed_header_fact import ObservedHeaderFact
from .....core.period import Period
from .....domain.buckets.event import BucketEventHistoryCatalogue
from .....domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
from .....domain.calculations.registry.authority import bundled_indexed_authority
from .....domain.calculations.registry.bindings import RegistryModeloObservation
from .....domain.iva_compensation.carry_forward import IvaCompensationPeriodState
from .....domain.justificante.protocols import JustificanteRepositoryProtocol
from .....domain.justificante.schema import Justificante
from .....domain.modelos.filing_record import ModeloRecord, ModeloRecordCatalogue
from .....domain.modelos.protocols import ModeloRecordCatalogueRepositoryProtocol
from ....inbound.justificante.parser import parse_justificante_bytes
from ....persistence.profile.buckets import BucketEventHistoryRepository
from ....persistence.profile.justificante import JustificanteRepository
from ....persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ....persistence.storage.sql.secure_objects import SecureObjectRepository
from .declarations_observations import (
    non_numeric_observed_casillas,
    registry_observation_from_filed_declaration,
)
from .declarations_remote import extract_csv_from_url
from .observation_store import FiledDeclaracionObservationStore
from .schema import FiledDeclaracionArtefact, FiledDeclaracionObservation

if TYPE_CHECKING:
    from .....core.secure_object_write import SecureObjectWrite
    from .....domain.calculations.registry.authority import PinnedAuthorityOperation


_DEFAULT_FAILURE_KEY = "application.live.filed_observations.errors.registry_enrollment_failed"


def _call_adapter[T](
    operation: str,
    callback: Callable[[], T],
    *,
    fallback_key: str = _DEFAULT_FAILURE_KEY,
) -> T:
    """Invoke one adapter and translate its exception at the app boundary."""
    try:
        return callback()
    except LiveApplicationError:
        raise
    except Exception as exc:
        translated_message = getattr(exc, "translated_message", None) or fallback_key
        raise LiveApplicationError(
            translated_message=translated_message,
            context={"operation": operation, "cause_type": type(exc).__name__},
        ) from exc


def _concrete_observation(observation: FiledObservationProtocol) -> FiledDeclaracionObservation:
    """Keep the concrete Sede observation at the adapter boundary."""
    if not isinstance(observation, FiledDeclaracionObservation):
        raise TypeError("filed observation port returned a non-Sede observation")
    return observation


def _concrete_artefact(artefact: FiledObservationArtefactProtocol) -> FiledDeclaracionArtefact:
    """Keep the concrete Sede artefact at the adapter boundary."""
    if not isinstance(artefact, FiledDeclaracionArtefact):
        raise TypeError("filed observation port returned a non-Sede artefact")
    return artefact


class FiledObservationParserAdapter(FiledObservationParserPort):
    """Adapt receipt parsing and Sede CSV extraction to application types."""

    @override
    def parse_justificante(self, body: bytes) -> Justificante:
        """Parse receipt bytes without creating a plaintext temporary file."""
        return _call_adapter("parse_justificante", lambda: parse_justificante_bytes(body))

    @override
    def csv_from_source_url(self, source_url: str) -> str:
        """Extract the independent AEAT CSV witness from a source URL."""
        return _call_adapter("csv_from_source_url", lambda: str(extract_csv_from_url(source_url)))


class FiledDeclarationTransformationAdapter(FiledDeclarationTransformationPort):
    """Adapt Sede observation projections to registry-grounded application ports."""

    def __init__(self, *, operation: PinnedAuthorityOperation) -> None:
        """Bind the generation-pinned operation used by every transformation."""
        self._operation = operation

    @override
    def registry_observation(self, observation: FiledObservationProtocol) -> RegistryModeloObservation:
        """Build the registry-grounded numeric projection."""
        return _call_adapter(
            "registry_observation",
            lambda: registry_observation_from_filed_declaration(
                _concrete_observation(observation),
                operation=self._operation,
            ),
        )

    @override
    def non_numeric_casillas(
        self,
        observation: FiledObservationProtocol,
    ) -> Sequence[FiledObservationSkipProtocol]:
        """Return non-numeric observed casillas for the operator projection."""
        return _call_adapter(
            "non_numeric_casillas",
            lambda: non_numeric_observed_casillas(
                _concrete_observation(observation),
                operation=self._operation,
            ),
        )


class FiledObservationStoreAdapter(FiledObservationPersistencePort):
    """Adapt the encrypted Sede observation store to the application port."""

    def __init__(self, *, root: Path, objects: SecureObjectRepository) -> None:
        """Bind one logical output root and one secure-object backend."""
        self._store = FiledDeclaracionObservationStore(Path(root), objects=objects)

    @override
    def persist_observation(self, observation: FiledObservationProtocol) -> Path:
        """Persist one encrypted observation manifest."""
        return _call_adapter(
            "persist_observation",
            lambda: self._store.persist_observation(_concrete_observation(observation)),
        )

    @override
    def persist_artefact(
        self,
        observation_key: tuple[str, int, Period, str],
        artefact: FiledObservationArtefactProtocol,
        body: bytes,
    ) -> FiledObservationArtefactProtocol:
        """Persist one encrypted artefact and return its storage reference."""
        return _call_adapter(
            "persist_artefact",
            lambda: self._store.persist_artefact(observation_key, _concrete_artefact(artefact), body),
        )

    @override
    def load_artefact(self, storage_ref: str) -> bytes:
        """Load and verify one encrypted artefact by its content address."""
        return _call_adapter("load_artefact", lambda: self._store.load_artefact(storage_ref))


class CalculationObservationRepositoryAdapter(FiledCalculationObservationRepositoryPort):
    """Adapt the encrypted calculation-observation repository."""

    def __init__(self, *, repository: CalculationObservationRepository) -> None:
        """Bind one already-composed repository instance."""
        self._repository = repository

    @override
    def load_observation(self, modelo: str, period: Period) -> ObservationEnvelopePayload | None:
        """Load one existing calculation-observation envelope."""
        return _call_adapter("load_calculation_observation", lambda: self._repository.load_observation(modelo, period))

    @override
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
        """Prepare one validated calculation-observation envelope."""
        return _call_adapter(
            "prepare_observation_envelope",
            lambda: self._repository.prepare_observation_envelope(
                observation,
                source_kind=source_kind,
                stamped_revision_id=stamped_revision_id,
                captured_at=captured_at,
                source_metadata=source_metadata,
                source_headers=source_headers,
            ),
        )

    @override
    def save(self, payload: ObservationEnvelopePayload) -> None:
        """Persist one prepared calculation-observation envelope."""
        _call_adapter("save_calculation_observation", lambda: self._repository.save(payload))


class IvaHistoryRepositoryAdapter(FiledIvaHistoryRepositoryPort):
    """Adapt the encrypted IVA compensation-history repository."""

    def __init__(self, *, repository: IvaCompensationHistoryRepository) -> None:
        """Bind one already-composed repository instance."""
        self._repository = repository

    @override
    def load_period(self, period: Period) -> IvaCompensationPeriodState | None:
        """Reload one persisted IVA history period."""
        return _call_adapter("load_iva_history_period", lambda: self._repository.load_period(period))


def _calculation_repository(value: FiledCalculationObservationRepositoryPort) -> CalculationObservationRepository:
    """Recover the concrete repository hidden behind this adapter boundary."""
    if isinstance(value, CalculationObservationRepositoryAdapter):
        return value._repository
    raise LiveApplicationError(
        translated_message=_DEFAULT_FAILURE_KEY,
        context={"operation": "iva_history_persistence", "reason": "repository_adapter_mismatch"},
    )


def _history_repository(value: FiledIvaHistoryRepositoryPort) -> IvaCompensationHistoryRepository:
    """Recover the concrete history repository hidden behind this adapter boundary."""
    if isinstance(value, IvaHistoryRepositoryAdapter):
        return value._repository
    raise LiveApplicationError(
        translated_message="application.live.filed_observations.errors.iva_history_promotion_failed",
        context={"operation": "iva_history_persistence", "reason": "repository_adapter_mismatch"},
    )


class IvaObservationPersistenceAdapter(FiledIvaObservationPersistencePort):
    """Adapt the canonical atomic Modelo 303/history co-commit operation."""

    @override
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
        """Atomically persist the calculation envelope and IVA history state."""
        with bundled_indexed_authority().operation() as operation:
            return _call_adapter(
                "persist_iva_history",
                lambda: persist_observation_envelope_and_iva_history(
                    observation_repository=_calculation_repository(observation_repository),
                    history_repository=_history_repository(history_repository),
                    envelope=envelope,
                    taxpayer_nif=taxpayer_nif,
                    provenance=IvaCompensationStateProvenance.AEAT_CAPTURE,
                    expediente_id=expediente_id,
                    status=status,
                    source_observation_key=source_observation_key,
                    operation=operation,
                    source_artefact_sha256=source_artefact_sha256,
                ),
                fallback_key="application.live.filed_observations.errors.iva_history_promotion_failed",
            )


class JustificanteRepositoryAdapter(JustificanteRepositoryProtocol):
    """Adapt encrypted justificante metadata persistence."""

    def __init__(self, *, repository: JustificanteRepository) -> None:
        """Bind one already-composed repository instance."""
        self._repository = repository

    @override
    def load(self, csv: str, /) -> Justificante | None:
        """Load one receipt by CSV."""
        return _call_adapter("load_justificante", lambda: self._repository.load(csv))

    @override
    def save(self, justificante: Justificante, /) -> None:
        """Persist one parsed receipt."""
        _call_adapter("save_justificante", lambda: self._repository.save(justificante))

    @override
    def iter_justificantes(self) -> Iterator[Justificante]:
        """Yield all receipts after translating scan failures."""
        records = _call_adapter("iter_justificantes", lambda: tuple(self._repository.iter_justificantes()))
        return iter(records)


class FilingRepositoryAdapter(ModeloRecordCatalogueRepositoryProtocol):
    """Adapt encrypted modelo filing-record catalogue persistence."""

    def __init__(self, *, repository: ModeloRecordCatalogueRepository) -> None:
        """Bind one already-composed repository instance."""
        self._repository = repository

    @property
    @override
    def bucket_id(self) -> str | None:
        """Return the repository's bucket binding."""
        return self._repository.bucket_id

    @override
    def exists(self) -> bool:
        """Return whether the filing catalogue exists."""
        return _call_adapter("filing_exists", self._repository.exists)

    @override
    def load(self) -> ModeloRecordCatalogue:
        """Load the filing catalogue."""
        return _call_adapter("filing_load", self._repository.load)

    @override
    def load_revisioned(self) -> tuple[ModeloRecordCatalogue, str]:
        """Load the filing catalogue and its revision marker."""
        return _call_adapter("filing_load_revisioned", self._repository.load_revisioned)

    @override
    def save(self, catalogue: ModeloRecordCatalogue) -> None:
        """Persist the filing catalogue."""
        _call_adapter("filing_save", lambda: self._repository.save(catalogue))

    @override
    def mutate(self, mutation: Callable[[ModeloRecordCatalogue], ModeloRecordCatalogue]) -> ModeloRecordCatalogue:
        """Apply one guarded filing-catalogue mutation."""
        return _call_adapter("filing_mutate", lambda: self._repository.mutate(mutation))

    @override
    def to_secure_object_write(
        self,
        catalogue: ModeloRecordCatalogue,
        *,
        expected_revision_id: str | None = None,
    ) -> SecureObjectWrite:
        """Prepare a filing-catalogue secure-object write."""
        return _call_adapter(
            "filing_to_secure_object_write",
            lambda: self._repository.to_secure_object_write(
                catalogue,
                expected_revision_id=expected_revision_id,
            ),
        )

    @override
    def save_with_secure_object_writes(
        self,
        catalogue: ModeloRecordCatalogue,
        extra_writes: tuple[SecureObjectWrite, ...],
        *,
        expected_revision_id: str | None = None,
    ) -> None:
        """Persist filing state and co-emitted writes atomically."""
        _call_adapter(
            "filing_save_with_secure_object_writes",
            lambda: self._repository.save_with_secure_object_writes(
                catalogue,
                extra_writes,
                expected_revision_id=expected_revision_id,
            ),
        )


class BucketEventRepositoryAdapter(BucketEventHistoryRepositoryProtocol):
    """Adapt encrypted bucket-event-history persistence."""

    def __init__(self, *, repository: BucketEventHistoryRepository) -> None:
        """Bind one already-composed repository instance."""
        self._repository = repository

    @override
    def exists(self) -> bool:
        """Return whether the event catalogue exists."""
        return _call_adapter("bucket_events_exists", self._repository.exists)

    @override
    def load(self) -> BucketEventHistoryCatalogue:
        """Load the event catalogue."""
        return _call_adapter("bucket_events_load", self._repository.load)

    @override
    def save(self, catalogue: BucketEventHistoryCatalogue) -> None:
        """Persist the event catalogue."""
        _call_adapter("bucket_events_save", lambda: self._repository.save(catalogue))

    @override
    def to_secure_object_write(
        self,
        catalogue: BucketEventHistoryCatalogue,
        *,
        expected_revision_id: str | None = None,
    ) -> SecureObjectWrite:
        """Prepare an event-catalogue secure-object write."""
        return _call_adapter(
            "bucket_events_to_secure_object_write",
            lambda: self._repository.to_secure_object_write(
                catalogue,
                expected_revision_id=expected_revision_id,
            ),
        )


class BaselineImportAdapter(FiledBaselineImportPort):
    """Adapt the external-baseline application operation with explicit ports."""

    def __init__(
        self,
        *,
        work_lifecycle_ports: WorkLifecyclePorts,
        calculation_repository: CalculationRevisionCatalogueRepository,
        filing_repository: ModeloRecordCatalogueRepository,
        justificante_repository: JustificanteRepository,
        observation_repository: CalculationObservationRepository,
    ) -> None:
        """Bind all baseline dependencies to one secure-object backend."""
        self._calculation_repository = calculation_repository
        self._filing_repository = filing_repository
        self._work_lifecycle_ports = work_lifecycle_ports
        self._justificante_repository = justificante_repository
        self._observation_repository = observation_repository

    @override
    def import_source(
        self,
        source: ExternalFilingBaselineSource,
        *,
        bucket_id: str,
        actor: str,
        clock: datetime,
    ) -> ModeloRecord:
        """Import one complete filed observation as an amendable baseline."""

        def import_with_authority() -> ModeloRecord:
            with bundled_indexed_authority().operation() as operation:
                return import_external_filing_source(
                    source,
                    bucket_id=bucket_id,
                    actor=actor,
                    work_lifecycle_ports=self._work_lifecycle_ports,
                    operation=operation,
                    calculation_repository=self._calculation_repository,
                    filing_repository=self._filing_repository,
                    justificante_repository=self._justificante_repository,
                    observation_repository=self._observation_repository,
                    clock=clock,
                )

        return _call_adapter("import_filed_baseline", import_with_authority)


__all__ = [
    "BaselineImportAdapter",
    "BucketEventRepositoryAdapter",
    "CalculationObservationRepositoryAdapter",
    "FiledDeclarationTransformationAdapter",
    "FiledObservationParserAdapter",
    "FiledObservationStoreAdapter",
    "FilingRepositoryAdapter",
    "IvaHistoryRepositoryAdapter",
    "IvaObservationPersistenceAdapter",
    "JustificanteRepositoryAdapter",
]
