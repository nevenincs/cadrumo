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
from ...core.filing_year import FILING_YEAR_MAX, FILING_YEAR_MIN
from ...core.i18n.translatable import Translatable as tr
from ...core.period import Period
from .errors import AggregationValidationError
from .observation_key_component import validate_observation_key_component
from .observation_window import hashed_tax_id_token
from .retenciones import RetencionObservation


def retencion_observation_key(
    modelo: str,
    filing_year: int,
    period: Period,
    perceptor_nif: str,
    scheme: RetencionScheme,
    projection_identity: str | None = None,
) -> str:
    """Opaque per-perceptor object key — the NIF is hashed, never cleartext.

    Secure-object payloads are encrypted, but object keys are storage metadata, so
    the perceptor NIF is sha256-hashed (the iva-wallet-decision key convention).
    Distinct (perceptor NIF, scheme) pairs persist as distinct rows so a perceptor
    paid under more than one scheme is preserved while the distinct-NIF count stays
    correct.
    """
    if not FILING_YEAR_MIN <= filing_year <= FILING_YEAR_MAX:
        raise AggregationValidationError(
            tr("aggregation.retenciones.errors.filing_year_out_of_range"),
            context={
                "filing_year": str(filing_year),
                "min_year": str(FILING_YEAR_MIN),
                "max_year": str(FILING_YEAR_MAX),
            },
        )
    validate_observation_key_component(modelo, context="modelo")
    period_token = period.registry_token
    validate_observation_key_component(period_token, context="period")
    validate_observation_key_component(str(scheme.value), context="scheme")
    hashed_token = hashed_tax_id_token(perceptor_nif, field_name="perceptor_nif")
    if projection_identity is None:
        return f"{modelo}:{filing_year}:{period_token}:{hashed_token}:{scheme.value}"
    validate_observation_key_component(projection_identity, context="projection_identity")
    return f"{modelo}:{filing_year}:{period_token}:{hashed_token}:{scheme.value}:{projection_identity}"


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

    def load_annual_source_observations(self, source_modelo: str, filing_year: int) -> tuple[RetencionObservation, ...]:
        """Return all active periodic projections feeding one annual family."""
        ...

    def load_source_observations_through_year(
        self,
        source_modelo: str,
        last_filing_year: int,
    ) -> tuple[RetencionObservation, ...]:
        """Return every active periodic projection of ``source_modelo`` up to ``last_filing_year``.

        An annual disclosure can depend on an allocation recognised in an
        earlier year and settled in this one, so the read spans every periodic
        window whose filing year is at or before ``last_filing_year``.
        """
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


__all__ = [
    "RetencionObservationPersistenceError",
    "RetencionObservationPorts",
    "RetencionObservationPortsFactory",
    "RetencionObservationRepository",
    "retencion_observation_key",
]
