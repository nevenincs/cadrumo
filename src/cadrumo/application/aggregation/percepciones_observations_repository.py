"""Application-owned capabilities for Modelo 190 percepciones observations.

The percepciones source stores one :class:`WithholdingObservation` for every
``(perceptor, clave, subclave)`` in a ``(modelo, filing_year, period)`` window.
The application owns the key grammar and the required read/write capability;
the encrypted persistence implementation is bound by an outer composition
root. Keeping this module free of storage imports makes the calculate mesh
usable with an inward fake and prevents persistence details from becoming an
implicit application dependency.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from ...core.aggregation import AggregationCaptureKind
from ...core.errors.hierarchy import CadrumoError
from ...core.external_constants import UTF_8_ENCODING
from ...core.hashing import sha256_hex
from ...core.i18n.translatable import Translatable as tr
from ...core.identity.tax_id import tax_id_identity_token
from ...core.period import Period
from ...domain.calculations.registry.withholding_bindings import WithholdingObservation
from .errors import AggregationValidationError


def _validate_key_component(token: str, *, context: str) -> str:
    """Reject key components that would compose an unsafe repository id."""
    if not token:
        violation = "empty_repository_id"
    elif "/" in token or "\\" in token:
        violation = "repository_id_separator"
    elif token in {".", ".."} or token.startswith("."):
        violation = "repository_id_dot_token"
    else:
        return token
    raise AggregationValidationError(
        tr("errors.integrity.integrity_storage_path_containment"),
        context={"path_context": context, "violation": violation},
    )


def _hashed_tax_id_token(tax_id: str) -> str:
    """Return the stable opaque identity segment for one perceptor NIF."""
    token = tax_id_identity_token(tax_id)
    if not token:
        raise AggregationValidationError(
            tr("aggregation.retenciones.errors.perceptor_nif_blank"),
            context={"field": "perceptor_tax_id"},
        )
    return sha256_hex(token.encode(UTF_8_ENCODING))


def percepcion_observation_key(
    modelo: str,
    filing_year: int,
    period: Period,
    perceptor_tax_id: str,
    clave: str,
    subclave: str,
) -> str:
    """Build the opaque per-perceptor-clave observation key.

    The NIF is hashed because object keys are storage metadata. ``clave`` and
    ``subclave`` remain explicit because they are non-identifying AEAT codes
    and distinguish the separate registro-tipo-2 observations.
    """
    if not 2000 <= filing_year <= 2099:
        raise AggregationValidationError(
            tr("aggregation.retenciones.errors.filing_year_out_of_range"),
            context={"filing_year": str(filing_year), "min_year": "2000", "max_year": "2099"},
        )
    _validate_key_component(modelo, context="modelo")
    period_token = period.registry_token
    _validate_key_component(period_token, context="period")
    _validate_key_component(clave, context="clave")
    subclave_token = subclave or "-"
    _validate_key_component(subclave_token, context="subclave")
    return f"{modelo}:{filing_year}:{period_token}:{_hashed_tax_id_token(perceptor_tax_id)}:{clave}:{subclave_token}"


class PercepcionObservationPersistenceError(CadrumoError):
    """Translated failure from the perceptor-observation persistence port."""

    def __init__(self, operation: str) -> None:
        """Carry only the application operation, never storage details."""
        self.operation = operation
        super().__init__(f"percepcion observation persistence operation failed: {operation}")


class PercepcionObservationRepository(Protocol):
    """Application-facing read/write capability for percepciones windows."""

    def replace_observations(
        self,
        *,
        modelo: str,
        filing_year: int,
        period: Period,
        observations: Sequence[WithholdingObservation],
        source_kind: AggregationCaptureKind,
        captured_at: datetime | None = None,
        source_metadata: Mapping[str, str] | None = None,
    ) -> None:
        """Atomically replace the complete observation window."""
        ...

    def load_observations(self, modelo: str, period: Period) -> tuple[WithholdingObservation, ...]:
        """Return observations for one modelo and filing period."""
        ...


@dataclass(frozen=True, slots=True)
class PercepcionObservationPorts:
    """Required percepciones capabilities for one profile calculation context."""

    repository: PercepcionObservationRepository


class PercepcionObservationPortsFactory(Protocol):
    """Construct the percepciones capabilities for one profile bucket."""

    def __call__(self, *, bucket_id: str) -> PercepcionObservationPorts:
        """Return the required application bundle for ``bucket_id``."""
        ...


def persist_percepcion_observations(
    *,
    ports: PercepcionObservationPorts,
    modelo: str,
    filing_year: int,
    period: Period,
    observations: Sequence[WithholdingObservation],
    source_kind: AggregationCaptureKind = AggregationCaptureKind.AGGREGATE_PULL,
) -> None:
    """Persist the complete per-perceptor-clave window through the required port."""
    ports.repository.replace_observations(
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        observations=observations,
        source_kind=source_kind,
    )


__all__ = [
    "PercepcionObservationPersistenceError",
    "PercepcionObservationPorts",
    "PercepcionObservationPortsFactory",
    "PercepcionObservationRepository",
    "percepcion_observation_key",
    "persist_percepcion_observations",
]
