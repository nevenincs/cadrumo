"""Encrypted persistence for per-perceptor retención records (Modelo 180/190/193).

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

Sensitivity is :class:`SensitivityClass` ``FINANCIAL`` — perceptor NIFs are
identity-bearing financial data, stored encrypted at rest through an
:class:`Envelope`-wrapped repository. The plaintext NIF lives only inside the
encrypted payload; the object key carries the sha256 of the NIF (the
iva-wallet-decision key convention), never the cleartext value
(``sensitive-financial-data-secure-storage-only``).

ADR ``2026-06-24-retenciones-perceptor-count-adr``. Producers (the pull/aggregate
entrypoints) write here through one shared helper; the P02 calc-mesh resolver
reads here and calls the distinct-count primitive.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator, Mapping, Sequence
from datetime import datetime
from typing import ClassVar, override

from pydantic import BaseModel, Field

from ...adapters.persistence.storage import (
    RETENCION_OBSERVATIONS_NAMESPACE,
    SensitivityClass,
    safe_repository_id,
)
from ...adapters.persistence.storage.envelope import SecureBoundRepository
from ...core import STRICT_FROZEN_CONFIG, Period
from ...core.external_constants import UTF_8_ENCODING
from ...core.time import now
from ._errors import AggregationValidationError, t
from ._retenciones import RetencionObservation, RetencionScheme


class _RetencionObservationEnvelopePayload(BaseModel):
    """Serialisable wrapper around one per-perceptor :class:`RetencionObservation`.

    Carries the (modelo, filing_year, period) keying the registry resolver needs
    alongside the validated retención row, plus capture provenance. Wrapping keeps
    the envelope schema identical to the other repositories' one-``payload`` shape
    and leaves room for future per-record metadata without breaking the inner
    record.
    """

    model_config = STRICT_FROZEN_CONFIG

    modelo: str = Field(min_length=1, max_length=8)
    filing_year: int = Field(ge=2000, le=2099)
    period: Period
    observation: RetencionObservation
    captured_at: datetime
    source_kind: str = Field(min_length=1)
    source_metadata: Mapping[str, str] = Field(default_factory=dict)


def _hashed_perceptor_token(perceptor_nif: str) -> str:
    token = perceptor_nif.strip().upper()
    if not token:
        raise AggregationValidationError(
            t("aggregation.retenciones.errors.perceptor_nif_blank"),
            context={"field": "perceptor_nif"},
        )
    return hashlib.sha256(token.encode(UTF_8_ENCODING)).hexdigest()


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
    safe_repository_id(modelo, context="modelo")
    period_token = period.registry_token
    safe_repository_id(period_token, context="period")
    safe_repository_id(str(scheme.value), context="scheme")
    return f"{modelo}:{filing_year}:{period_token}:{_hashed_perceptor_token(perceptor_nif)}:{scheme.value}"


class RetencionObservationRepository(SecureBoundRepository[_RetencionObservationEnvelopePayload]):
    """Repository over encrypted SQL-backed per-perceptor retención observations."""

    namespace: ClassVar[str] = RETENCION_OBSERVATIONS_NAMESPACE.namespace
    sensitivity: ClassVar[SensitivityClass] = RETENCION_OBSERVATIONS_NAMESPACE.sensitivity
    schema_version: ClassVar[int] = RETENCION_OBSERVATIONS_NAMESPACE.schema_version
    payload_type: ClassVar[type[BaseModel]] = _RetencionObservationEnvelopePayload

    @override
    def extract_identifier(self, payload: _RetencionObservationEnvelopePayload) -> str:
        return retencion_observation_key(
            payload.modelo,
            payload.filing_year,
            payload.period,
            payload.observation.perceptor_nif,
            payload.observation.scheme,
        )

    def save_observation(
        self,
        *,
        modelo: str,
        filing_year: int,
        period: Period,
        observation: RetencionObservation,
        source_kind: str,
        captured_at: datetime | None = None,
        source_metadata: Mapping[str, str] | None = None,
    ) -> None:
        """Persist one per-perceptor retención row keyed by (modelo, filing_year, period, NIF, scheme)."""
        payload = _RetencionObservationEnvelopePayload(
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            observation=observation,
            captured_at=captured_at if captured_at is not None else now(),
            source_kind=source_kind,
            source_metadata=dict(source_metadata or {}),
        )
        self.save(payload)

    def replace_observations(
        self,
        *,
        modelo: str,
        filing_year: int,
        period: Period,
        observations: Sequence[RetencionObservation],
        source_kind: str,
        captured_at: datetime | None = None,
        source_metadata: Mapping[str, str] | None = None,
    ) -> None:
        """Replace the FULL per-perceptor set for one (modelo, filing_year, period).

        SET-REPLACE, not additive upsert: clears any prior rows for the exact
        key-tuple, then writes the supplied set. A re-pull where the operator
        DROPPED a perceptor must not leave the stale row behind — otherwise the
        next calculate's distinct count is inflated by a perceptor no longer
        declared (a silent over-count, the inverse of the bug RET-1 fixes). An
        empty ``observations`` clears the window (the operator declared none); the
        P02 resolver surfaces a no-silent advisory when it then reads empty on
        positive activity.
        """
        safe_repository_id(modelo, context="modelo")
        when = captured_at if captured_at is not None else now()
        for payload in tuple(self.iter_records()):
            if (
                payload.modelo == modelo
                and payload.filing_year == filing_year
                and payload.period.registry_token == period.registry_token
            ):
                self.delete(self.extract_identifier(payload))
        for observation in observations:
            self.save_observation(
                modelo=modelo,
                filing_year=filing_year,
                period=period,
                observation=observation,
                source_kind=source_kind,
                captured_at=when,
                source_metadata=source_metadata,
            )

    def load_observations(
        self,
        modelo: str,
        period: Period,
    ) -> tuple[RetencionObservation, ...]:
        """Return every persisted per-perceptor observation for one (modelo, filing_year, period).

        The calc-mesh perceptor-count resolver (P02) folds these through the
        validated distinct-count primitive. An empty tuple means no per-perceptor
        records were persisted for the window — the resolver MUST surface a
        no-silent advisory rather than materialising a zero count.
        """
        safe_repository_id(modelo, context="modelo")
        return tuple(
            payload.observation
            for payload in self.iter_records()
            if payload.modelo == modelo
            and payload.filing_year == period.filing_year
            and payload.period.registry_token == period.registry_token
        )

    def iter_modelo(self, modelo: str) -> Iterator[_RetencionObservationEnvelopePayload]:
        """Yield every persisted per-perceptor payload for `modelo` in unspecified order."""
        safe_repository_id(modelo, context="modelo")
        for payload in self.iter_records():
            if payload.modelo == modelo:
                yield payload


def persist_retencion_observations(
    *,
    modelo: str,
    filing_year: int,
    period: Period,
    observations: Sequence[RetencionObservation],
    source_kind: str = "aggregate_pull",
) -> None:
    """The ONE shared write path every per-perceptor producer calls.

    Factoring the persist behind a single application helper makes store
    completeness STRUCTURAL rather than per-entrypoint discipline a future
    producer could forget (an unwritten producer → an incomplete store → the exact
    pull≠calculate divergence RET-1 fixes). Writes to the active bucket's encrypted
    store with SET-REPLACE semantics so pull and calculate read one source.
    aggregate_per_modelo stays pure — persistence is the entrypoint's job, not the
    aggregator's (aeat-architecture-boundaries).
    """
    RetencionObservationRepository().replace_observations(
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        observations=observations,
        source_kind=source_kind,
    )


__all__ = [
    "RetencionObservationRepository",
    "persist_retencion_observations",
    "retencion_observation_key",
]
