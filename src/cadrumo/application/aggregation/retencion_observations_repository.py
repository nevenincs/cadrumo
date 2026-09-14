"""Application contracts for per-perceptor retención observations (Modelo 180/193).

The DEDICATED store the retenciones-summary family reads to count perceptors
DISTINCTLY. Modelo 180 casilla ``decl.total-perceptores`` ("Número total de
perceptores … Número de registros de tipo 2", AEAT Diseño de Registro) is the
count of distinct perceptor NIFs on the annual declaration, NOT the sum of the
quarterly Modelo 115 aggregate counts. The validated distinct-count primitive
``aggregate_retenciones_180`` already exists; what it lacked was a persisted,
calc-mesh-readable per-perceptor source so the calculate path could compute the
distinct count instead of falling back to the wrong quarterly sum. This module is
that source: it persists each :class:`RetencionObservation` (perceptor NIF +
scheme + taxable base + retención) keyed by ``(modelo, filing_year, period)`` plus
the per-perceptor identity, so the pull and calculate surfaces read ONE store.

The encrypted persistence implementation is an outer adapter. This module owns
the application repository capability, key grammar, and shared producer helper;
the calc-mesh resolver consumes the same required capability and calls the
distinct-count primitive.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from ...core.aggregation import AggregationCaptureKind, RetencionScheme
from ...core.errors.hierarchy import CadrumoError
from ...core.i18n.translatable import Translatable as t
from ...core.period import Period
from .errors import AggregationValidationError
from .observation_window import hashed_tax_id_token
from .retenciones import RetencionObservation


def retencion_observation_key(
    modelo: str,
    filing_year: int,
    period: Period,
    perceptor_nif: str,
    scheme: RetencionScheme,
) -> str:
    """Opaque per-perceptor object key — the NIF is hashed, never cleartext.

    Secure-object payloads are encrypted, but object keys are storage metadata, so
    the perceptor NIF is sha256-hashed (the iva-wallet-decision key convention).
    Distinct (perceptor NIF, scheme) pairs persist as distinct rows so a perceptor
    paid under more than one scheme is preserved while the distinct-NIF count stays
    correct.
    """
    if not 2000 <= filing_year <= 2099:
        raise AggregationValidationError(
            t("aggregation.retenciones.errors.filing_year_out_of_range"),
            context={"filing_year": str(filing_year), "min_year": "2000", "max_year": "2099"},
        )
    _validate_key_component(modelo, context="modelo")
    period_token = period.registry_token
    _validate_key_component(period_token, context="period")
    _validate_key_component(str(scheme.value), context="scheme")
    hashed_token = hashed_tax_id_token(perceptor_nif, field_name="perceptor_nif")
    return f"{modelo}:{filing_year}:{period_token}:{hashed_token}:{scheme.value}"


def _validate_key_component(token: str, *, context: str) -> str:
    """Reject key components that would compose an unsafe persistence identifier."""
    if not token:
        violation = "empty_repository_id"
    elif "/" in token or "\\" in token:
        violation = "repository_id_separator"
    elif token in {".", ".."} or token.startswith("."):
        violation = "repository_id_dot_token"
    else:
        return token
    raise AggregationValidationError(
        t("errors.integrity.integrity_storage_path_containment"),
        context={"path_context": context, "violation": violation},
    )


class RetencionObservationPersistenceError(CadrumoError):
    """Translated failure from the retención-observation persistence port."""

    def __init__(self, operation: str) -> None:
        """Carry only the application operation, never storage details."""
        self.operation = operation
        super().__init__(f"retención observation persistence operation failed: {operation}")


class RetencionObservationRepository(Protocol):
    """Application persistence capability for per-perceptor observations."""

    def replace_observations(
        self,
        *,
        modelo: str,
        filing_year: int,
        period: Period,
        observations: Sequence[RetencionObservation],
        source_kind: AggregationCaptureKind,
        captured_at: datetime | None = None,
        source_metadata: Mapping[str, str] | None = None,
    ) -> None:
        """Atomically replace the complete observation window."""
        ...

    def load_observations(self, modelo: str, period: Period) -> tuple[RetencionObservation, ...]:
        """Return observations for one modelo and filing period."""
        ...


@dataclass(frozen=True, slots=True)
class RetencionObservationPorts:
    """Required retención observation capabilities for one profile session."""

    repository: RetencionObservationRepository


class RetencionObservationPortsFactory(Protocol):
    """Construct the retención observation capabilities for one bucket."""

    def __call__(self, *, bucket_id: str) -> RetencionObservationPorts:
        """Return the required application bundle for ``bucket_id``."""
        ...


def persist_retencion_observations(
    *,
    ports: RetencionObservationPorts,
    modelo: str,
    filing_year: int,
    period: Period,
    observations: Sequence[RetencionObservation],
    source_kind: AggregationCaptureKind = AggregationCaptureKind.AGGREGATE_PULL,
) -> None:
    """The ONE shared write path every per-perceptor producer calls.

    Factoring the persist behind a single application helper makes store
    completeness STRUCTURAL rather than per-entrypoint discipline a future
    producer could forget (an unwritten producer -> an incomplete store -> a
    pull≠calculate divergence). Writes to the active bucket's encrypted
    store with SET-REPLACE semantics so pull and calculate read one source.
    aggregate_per_modelo stays pure — persistence is the entrypoint's job, not the
    aggregator's (aeat-architecture-boundaries).
    """
    ports.repository.replace_observations(
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        observations=observations,
        source_kind=source_kind,
    )


__all__ = [
    "RetencionObservationPersistenceError",
    "RetencionObservationPorts",
    "RetencionObservationPortsFactory",
    "RetencionObservationRepository",
    "persist_retencion_observations",
    "retencion_observation_key",
]
