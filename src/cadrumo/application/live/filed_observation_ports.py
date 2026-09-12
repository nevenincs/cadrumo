"""Application-owned ports for filed-observation persistence.

The filed-history use case consumes an authenticated declaration observation,
turns it into calculation evidence, and records the resulting local evidence.
This module names the small surfaces that use case needs.  Sede readers,
receipt parsers, and encrypted repositories are composed outside the
application layer and implement these ports there.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from ...core.casilla_value_kind import CasillaValueKind
from ...core.observed_header_fact import ObservedHeaderFact
from ...core.period import Period

if TYPE_CHECKING:
    from ...domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
    from ...domain.calculations.registry.bindings import RegistryModeloObservation
    from ...domain.calculations.registry.schema_references import RegistrySnapshotRef
    from ...domain.justificante.protocols import JustificanteRepositoryProtocol
    from ...domain.justificante.schema import Justificante
    from ...domain.modelos.filing_record import ModeloRecord
    from ...domain.modelos.protocols import ModeloRecordCatalogueRepositoryProtocol
    from ..calculations.iva_compensation_history import IvaCompensationPeriodState
    from ..calculations.observations_repository import ObservationEnvelopePayload, ObservationSourceKind
    from ..modelo.external_import_actions import ExternalFilingBaselineSource


class FiledObservationArtefactProtocol(Protocol):
    """The captured artefact facts read by persistence and receipt matching."""

    @property
    def kind(self) -> str:
        """Return the captured artefact kind."""
        ...

    @property
    def source_url(self) -> object:
        """Return the source URL associated with the artefact."""
        ...

    @property
    def byte_count(self) -> int:
        """Return the byte count recorded in the manifest."""
        ...

    @property
    def sha256(self) -> str:
        """Return the manifest SHA-256 digest."""
        ...

    @property
    def captured_at(self) -> datetime:
        """Return the capture timestamp."""
        ...

    @property
    def storage_ref(self) -> str | None:
        """Return the encrypted storage reference, when persisted."""
        ...


class FiledObservedCasillaProtocol(Protocol):
    """The observed casilla facts used by baseline and skip projections."""

    @property
    def casilla_id(self) -> str:
        """Return the observed casilla identifier."""
        ...

    @property
    def value(self) -> str:
        """Return the observed lexical value."""
        ...

    @property
    def value_kind(self) -> CasillaValueKind:
        """Return the parser's value-kind classification."""
        ...


class FiledObservationProtocol(Protocol):
    """Application view of one authenticated filed declaration observation."""

    @property
    def modelo(self) -> str:
        """Return the declaration modelo code."""
        ...

    @property
    def ejercicio(self) -> int:
        """Return the declaration filing year."""
        ...

    @property
    def period(self) -> Period:
        """Return the declaration fiscal period."""
        ...

    @property
    def expediente_id(self) -> str:
        """Return the Sede expediente identifier."""
        ...

    @property
    def status(self) -> str:
        """Return the register status."""
        ...

    @property
    def presented_at(self) -> datetime:
        """Return the filing presentation timestamp."""
        ...

    @property
    def authenticated_identity(self) -> str:
        """Return the authenticated taxpayer identity token."""
        ...

    @property
    def artefacts(self) -> Sequence[FiledObservationArtefactProtocol]:
        """Return the captured artefact manifest."""
        ...

    @property
    def casillas(self) -> Sequence[FiledObservedCasillaProtocol]:
        """Return observed casilla values."""
        ...

    @property
    def headers(self) -> tuple[ObservedHeaderFact, ...]:
        """Return typed submitted-file header facts."""
        ...

    @property
    def metadata(self) -> Mapping[str, str]:
        """Return untyped register provenance metadata."""
        ...

    @property
    def registry_snapshot_ref(self) -> RegistrySnapshotRef:
        """Return the registry revision selected for this observation."""
        ...


class FiledDeclarationProtocol(Protocol):
    """Period-bearing register row facts used for latest-row selection."""

    @property
    def modelo(self) -> str:
        """Return the declaration modelo code."""
        ...

    @property
    def period(self) -> Period:
        """Return the declaration period."""
        ...

    @property
    def expediente_id(self) -> str:
        """Return the Sede expediente identifier."""
        ...

    @property
    def estado(self) -> str:
        """Return the register declaration status."""
        ...

    @property
    def presented_at(self) -> datetime:
        """Return the declaration presentation timestamp."""
        ...


class FiledObservationSkipProtocol(Protocol):
    """Non-numeric casilla projection returned for the operator report."""

    @property
    def casilla_id(self) -> str:
        """Return the skipped casilla identifier."""
        ...

    @property
    def label(self) -> str:
        """Return the operator-facing casilla label."""
        ...

    @property
    def value_kind(self) -> CasillaValueKind:
        """Return the skipped value-kind classification."""
        ...

    @property
    def reason(self) -> str:
        """Return the reason the casilla was skipped."""
        ...


class FiledObservationParserPort(Protocol):
    """Parse receipt bytes and recover the independent AEAT CSV witness."""

    def parse_justificante(self, body: bytes) -> Justificante:
        """Parse receipt bytes into domain justificante metadata."""
        ...

    def csv_from_source_url(self, source_url: str) -> str:
        """Recover the independent CSV witness from a source URL."""
        ...


class FiledDeclarationTransformationPort(Protocol):
    """Translate filed evidence into application/domain projections."""

    def registry_observation(self, observation: FiledObservationProtocol) -> RegistryModeloObservation:
        """Translate one filed observation into a registry-grounded row."""
        ...

    def non_numeric_casillas(
        self,
        observation: FiledObservationProtocol,
    ) -> Sequence[FiledObservationSkipProtocol]:
        """Return non-numeric casillas for the operator skip report."""
        ...


class FiledObservationPersistencePort(Protocol):
    """Encrypted custody of captured observation manifests and artefacts."""

    def persist_observation(self, observation: FiledObservationProtocol) -> Path:
        """Persist an observation manifest and return its logical path."""
        ...

    def persist_artefact(
        self,
        observation_key: tuple[str, int, Period, str],
        artefact: FiledObservationArtefactProtocol,
        body: bytes,
    ) -> FiledObservationArtefactProtocol:
        """Persist artefact bytes and return the manifest with its storage reference."""
        ...

    def load_artefact(self, storage_ref: str) -> bytes:
        """Load plaintext bytes addressed by an encrypted storage reference."""
        ...


class FiledCalculationObservationRepositoryPort(Protocol):
    """Calculation-observation repository operations used by this capability."""

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
        """Build a validated calculation-observation envelope."""
        ...

    def save(self, payload: ObservationEnvelopePayload) -> None:
        """Persist a prepared calculation-observation envelope."""
        ...


class FiledIvaHistoryRepositoryPort(Protocol):
    """Read the persisted IVA history row after a M303 co-commit."""

    def load_period(self, period: Period) -> IvaCompensationPeriodState | None:
        """Load one persisted IVA compensation history period."""
        ...


class FiledIvaObservationPersistencePort(Protocol):
    """Atomically persist a calculation envelope and its M303 history state."""

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
        ...


class FiledBaselineImportPort(Protocol):
    """Persist a complete numeric filed observation as an external baseline."""

    def import_source(
        self,
        source: ExternalFilingBaselineSource,
        *,
        bucket_id: str,
        actor: str,
        clock: datetime,
    ) -> ModeloRecord:
        """Import a complete numeric observation as an external baseline."""
        ...


@dataclass(frozen=True, slots=True)
class FiledObservationPersistencePorts:
    """Immutable dependency bundle for the filed-observation capability."""

    parser: FiledObservationParserPort
    transformation: FiledDeclarationTransformationPort
    observation_persistence: FiledObservationPersistencePort
    calculation_repository: FiledCalculationObservationRepositoryPort
    iva_history_repository: FiledIvaHistoryRepositoryPort
    iva_observation_persistence: FiledIvaObservationPersistencePort
    justificante_repository: JustificanteRepositoryProtocol
    filing_repository: ModeloRecordCatalogueRepositoryProtocol
    bucket_event_repository: BucketEventHistoryRepositoryProtocol
    baseline_import: FiledBaselineImportPort


__all__ = [
    "FiledBaselineImportPort",
    "FiledCalculationObservationRepositoryPort",
    "FiledDeclarationProtocol",
    "FiledDeclarationTransformationPort",
    "FiledIvaHistoryRepositoryPort",
    "FiledIvaObservationPersistencePort",
    "FiledObservationArtefactProtocol",
    "FiledObservationParserPort",
    "FiledObservationPersistencePort",
    "FiledObservationPersistencePorts",
    "FiledObservationProtocol",
    "FiledObservationSkipProtocol",
    "FiledObservedCasillaProtocol",
]
